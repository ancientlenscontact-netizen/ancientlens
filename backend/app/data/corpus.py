"""Bounded Cleveland CC0 seed acquisition. No automated label generation."""
import argparse
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import httpx
from PIL import Image, ImageOps

SEED_IDS = (102365, 93957, 113175, 94105, 94104)
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_RUN_BYTES = 30 * 1024 * 1024
POLICY = 'https://www.clevelandart.org/open-access'


def select_asset(record):
    if record.get('share_license_status') != 'CC0':
        raise ValueError('Image is not designated CC0')
    culture=' '.join(record.get('culture') or [])
    if 'egypt' not in culture.lower():
        raise ValueError('Not an Egyptian collection record')
    if 'forgery' in culture.lower():
        raise ValueError('Possible forgery excluded from seed')
    asset=record.get('images',{}).get('print') or {}
    url=asset.get('url','')
    parsed=urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'openaccess-cdn.clevelandart.org':
        raise ValueError('Unexpected image host')
    if int(asset.get('filesize',MAX_IMAGE_BYTES+1)) > MAX_IMAGE_BYTES:
        raise ValueError('Image exceeds acquisition cap')
    return url


def atomic_json(path,data):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)


def acquire(directory: Path):
    directory.mkdir(parents=True,exist_ok=True)
    for folder in ('originals','images','sources'):(directory/folder).mkdir(exist_ok=True)
    manifest_path=directory/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'schema_version':'1.0','samples':[]}
    known={s['id']:s for s in manifest['samples']}
    hashes={s.get('original_sha256') for s in manifest['samples']}
    failures=[];downloaded=0
    with httpx.Client(timeout=45,follow_redirects=False) as client:
        for object_id in SEED_IDS:
            sid=f'cma-{object_id}'
            if sid in known:
                sample=known[sid];path=directory/sample['image_path']
                if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=sample['sha256']:
                    failures.append({'id':sid,'error':'Existing normalized image missing or modified; left unchanged'})
                continue
            metadata_url=f'https://openaccess-api.clevelandart.org/api/artworks/{object_id}'
            try:
                response=client.get(metadata_url);response.raise_for_status()
                record=response.json()['data']
                if isinstance(record,list):record=record[0]
                if record['id']!=object_id:raise ValueError('Object identity mismatch')
                url=select_asset(record)
                chunks=[];size=0
                with client.stream('GET',url) as image_response:
                    image_response.raise_for_status()
                    for chunk in image_response.iter_bytes():
                        size+=len(chunk);downloaded+=len(chunk)
                        if size>MAX_IMAGE_BYTES or downloaded>MAX_RUN_BYTES:
                            raise ValueError('Download budget exceeded')
                        chunks.append(chunk)
                raw=b''.join(chunks);original_hash=hashlib.sha256(raw).hexdigest()
                if original_hash in hashes:raise ValueError('Duplicate original image')
                with Image.open(io.BytesIO(raw)) as source:
                    if source.width*source.height>20_000_000:raise ValueError('Image exceeds pixel cap')
                    image=ImageOps.exif_transpose(source).convert('RGB')
                image_path=directory/'images'/f'{sid}.png'
                image.save(image_path)
                (directory/'originals'/f'{sid}.jpg').write_bytes(raw)
                atomic_json(directory/'sources'/f'{sid}.json',record)
                sample={'id':sid,'object_id':sid,'title':record['title'],
                    'accession_number':record.get('accession_number'),
                    'image_path':f'images/{sid}.png','original_path':f'originals/{sid}.jpg',
                    'sha256':hashlib.sha256(image_path.read_bytes()).hexdigest(),
                    'original_sha256':original_hash,'width':image.width,'height':image.height,
                    'source_url':record['url'],'metadata_url':metadata_url,
                    'metadata_snapshot':f'sources/{sid}.json','image_url':url,
                    'rights':'CC0','rights_url':POLICY,'rights_evidence_field':'share_license_status=CC0',
                    'retrieved_at':datetime.now(timezone.utc).isoformat(),
                    'culture':record.get('culture',[]),'creation_date':record.get('creation_date'),
                    'normalization':'EXIF orientation correction; RGB PNG; original resolution',
                    'split':'review','regions':[],
                    'review':{'status':'unreviewed','reviewer':None,'evidence':None,'complete_regions':False},
                    'annotation_status':'No region, sign, transliteration or translation ground truth',
                    'script_status':'Candidate Egyptian inscription; language stage and visible script require expert review'}
                manifest['samples'].append(sample);hashes.add(original_hash)
                atomic_json(manifest_path,manifest)
                print(f"Acquired {record['title']} ({image.width} x {image.height})",flush=True)
            except (httpx.HTTPError,ValueError,KeyError,OSError) as exc:
                failures.append({'id':sid,'error':str(exc)})
                print(f'Acquisition failed for {sid}: {type(exc).__name__}',flush=True)
    atomic_json(directory/'acquisition-status.json',{'attempted_ids':list(SEED_IDS),'downloaded_bytes_this_run':downloaded,'sample_count':len(manifest['samples']),'failures':failures})
    if failures:raise RuntimeError('Some acquisitions failed; see acquisition-status.json')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    args=parser.parse_args();acquire(args.directory)
