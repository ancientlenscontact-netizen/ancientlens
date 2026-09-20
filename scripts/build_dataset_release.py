"""Build a deterministic public dataset from pinned, individually licensed static records."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '2026-09-20.7'
PUBLIC = ROOT / 'frontend/public'
OUTPUT = PUBLIC / 'releases'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def encoded(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()

def build():
    rows = json.loads((PUBLIC / 'curated/collection.json').read_text())
    assert len(rows) == 111 and sum(len(r['passages']) for r in rows) == 119
    assert len({r['id'] for r in rows}) == len(rows)
    fields = set(rows[0])
    assert all(set(r) == fields and r['text_license'] in ('CC0','CC BY 4.0') and (r['image_license'] in ('CC0','CC BY 4.0','CC BY-SA 3.0') if r['image'] else r['image_license']=='Not included') and r['review'] == 'unreviewed' for r in rows)
    allowed = {'id','title','accession','date','culture','collection','source_language','language','review','institution','source_url','metadata_url','retrieved_at','metadata_sha256','text_license','image_license','text_rights_url','image_rights_url','image','image_url','image_sha256','image_changes','text_changes','passages','source_snapshot','record_url','note','description'}
    assert fields == allowed, 'Explicitly review any schema expansion before publishing'
    properties = {k: {'type':'string'} for k in allowed - {'culture','passages'}}
    properties['culture'] = {'type':'array','items':{'type':'string'}}
    properties['passages'] = {'type':'array','minItems':1,'items':{'type':'object','additionalProperties':False,'required':['id','field','text','source_text','remark'],'properties':{k:{'type':'string'} for k in ['id','field','text','source_text','remark']}}}
    properties['review'] = {'const':'unreviewed'}
    schema = {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':f'https://ancientlens.org/releases/schema-{VERSION}.json','title':'AncientLens curated collection','type':'array','items':{'type':'object','additionalProperties':False,'required':sorted(allowed),'properties':properties}}
    files = {'collection.json':encoded(rows),'schema.json':encoded(schema),'README.md':(ROOT/'docs/DATASET.md').read_bytes(),'LICENSES.md':(ROOT/'LICENSING.md').read_bytes()}
    selection=json.loads((PUBLIC/'curated/pilot-selection.json').read_text())
    assert len({item['id'] for item in selection['selected']})==len(selection['selected']), 'Duplicate pilot identity'
    assert all(item['area'] in selection['areas'] for item in selection['selected'])
    assert all(any(r['id']==item['id'] and r['image'] and r['metadata_sha256']==item.get('source_sha256',r['metadata_sha256']) and r['image_sha256']==item.get('image_sha256',r['image_sha256']) for r in rows) for item in selection['selected']), 'Pilot evidence missing or stale'
    assert all(sum(x['area']==area for x in selection['selected'])<=selection['target_per_area'] for area in selection['areas'])
    files['curated/pilot-selection.json']=encoded(selection)
    for row in rows:
        for key, checksum in [('image','image_sha256'),('source_snapshot','metadata_sha256')]:
            if key=='image' and not row[key]:
                assert row['image_license']=='Not included' and not row[checksum]
                continue
            name=row[key].lstrip('/')
            path=(PUBLIC/name).resolve()
            assert path.is_relative_to((PUBLIC/'curated').resolve()) if hasattr(path,'is_relative_to') else str(path).startswith(str(PUBLIC/'curated')+'/')
            data=path.read_bytes()
            assert digest(data)==row[checksum]
            files[name]=data
        name=row['record_url'].lstrip('/')
        assert name==f"curated/{row['id']}.json"
        files[name]=encoded(row)
    manifest={'version':VERSION,'artifacts':len(rows),'translation_entries':sum(len(r['passages']) for r in rows),'scope':'Museum and scholarly records with item-level CC0, CC BY 4.0 and CC BY-SA 3.0 rights; no user or community records','files':{name:{'sha256':digest(data),'bytes':len(data)} for name,data in sorted(files.items())}}
    files['manifest.json']=encoded(manifest)
    OUTPUT.mkdir(exist_ok=True)
    target=OUTPUT/f'ancientlens-dataset-{VERSION}.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,9,19,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644 << 16
            archive.writestr(info,data)
    (OUTPUT/f'schema-{VERSION}.json').write_bytes(encoded(schema))
    (OUTPUT/f'manifest-{VERSION}.json').write_bytes(encoded(manifest))
    (OUTPUT/f'ancientlens-dataset-{VERSION}.sha256').write_text(f'{digest(target.read_bytes())}  {target.name}\n')
    print(f'Built {target.name}: {len(files)} public files, {target.stat().st_size} bytes')
    return target

if __name__=='__main__': build()
