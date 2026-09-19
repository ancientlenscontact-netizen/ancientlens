"""Bounded offline public-record import with checked media; no network or scoring."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageOps
from app.data.catalog import connect, initialize

TABLES = {
 'sources': ('id','title','url','accessed_on','note'),
 'monuments': ('id','name','site','country','source_id'),
 'passage_records': ('id','monument_id','designation','locator','source_id','candidate_writing_system_id','classification_source_id','review_status','note'),
 'passage_references': ('passage_id','source_id','role','reuse_status','note'),
 'media_records': ('id','monument_id','source_id','author','license','license_url','attribution','original_path','normalized_path','original_sha256','normalized_sha256','width','height','review_status','triage'),
 'text_units': ('id','corpus_object_id','corpus_sample_id','normalized_sha256','region_ref','note'),
 'text_unit_media': ('text_unit_id','media_id'),
 'classification_assertions': ('id','text_unit_id','writing_system_id','status','author','evidence','reviewer','reviewed_on'),
}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def media_path(root, relative):
    p=Path(relative)
    if p.is_absolute(): raise ValueError('Media path must be relative')
    path=(root/p).resolve()
    if root not in path.parents: raise ValueError('Media path escapes corpus root')
    return path

def load_records(database, manifest, corpus_root):
    root=Path(corpus_root).resolve(); manifest=Path(manifest)
    raw=manifest.read_bytes(); data=json.loads(raw)
    if set(data) != {'batch_id','tables'} or set(data['tables']) != set(TABLES):
        raise ValueError('Unexpected import structure')
    if sum(len(rows) for rows in data['tables'].values())>80 or len(data['tables']['media_records'])>5:
        raise ValueError('Bounded import limit exceeded')
    for table,columns in TABLES.items():
        for row in data['tables'][table]:
            if set(row)!=set(columns): raise ValueError('Unexpected fields in '+table)
            for key in ('review_status','status'):
                if key in row and row[key]!='unreviewed': raise ValueError('Imported labels must be unreviewed')
    media={r['id']:r for r in data['tables']['media_records']}
    units={r['id']:r for r in data['tables']['text_units']}
    for row in media.values():
        if row['license']!='CC-BY-SA-2.0' or row['license_url']!='https://creativecommons.org/licenses/by-sa/2.0/':
            raise ValueError('This pilot requires its explicitly reviewed image license')
        if not row['author'].strip() or not row['attribution'].strip(): raise ValueError('Missing attribution')
        original=media_path(root,row['original_path']); normalized=media_path(root,row['normalized_path'])
        if original.stat().st_size>5*1024*1024 or normalized.stat().st_size>30*1024*1024:
            raise ValueError('Media byte limit exceeded')
        if digest(original)!=row['original_sha256'] or digest(normalized)!=row['normalized_sha256']:
            raise ValueError('Media checksum mismatch')
        with Image.open(original) as im:
            if im.width*im.height>20_000_000: raise ValueError('Pixel limit exceeded')
            pixels=ImageOps.exif_transpose(im).convert('RGB'); pixels.load()
        with Image.open(normalized) as im:
            if im.size!=(row['width'],row['height']) or im.size!=pixels.size or im.mode!='RGB' or im.tobytes()!=pixels.tobytes():
                raise ValueError('Normalization or dimensions mismatch')
    for link in data['tables']['text_unit_media']:
        u=units[link['text_unit_id']]; a=media[link['media_id']]
        if u['normalized_sha256']!=a['normalized_sha256'] or u['corpus_object_id']!=a['monument_id']:
            raise ValueError('Text unit does not match media')
    initialize(database)
    db=connect(database)
    try:
        batch_hash=hashlib.sha256(raw).hexdigest()
        with db:
            prior=db.execute('SELECT sha256 FROM public_record_imports WHERE id=?',(data['batch_id'],)).fetchone()
            if prior:
                if prior[0]!=batch_hash: raise ValueError('Batch changed; use an explicit new import/version')
                return {'status':'already_imported','batch_id':data['batch_id']}
            for table,columns in TABLES.items():
                sql=f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
                db.executemany(sql, [[row[c] for c in columns] for row in data['tables'][table]])
            db.execute('INSERT INTO public_record_imports VALUES (?,?)',(data['batch_id'],batch_hash))
        return {'status':'imported','batch_id':data['batch_id']}
    finally:
        db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',required=True,type=Path)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--corpus-root',required=True,type=Path)
    a=p.parse_args(); print(json.dumps(load_records(a.database,a.manifest,a.corpus_root)))
