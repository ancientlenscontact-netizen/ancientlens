"""Release check: independent count, fidelity, provenance and image assertions."""
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'frontend/public/curated'
rows=json.loads((out/'collection.json').read_text())
assert len(rows)==115 and len({r['accession'] for r in rows})==115
assert len({r['id'] for r in rows})==115
assert {r['collection'] for r in rows}=={'Egyptian','Greek','Roman','Chinese','Assyrian','Indian','Maya','Mesopotamian'}
assert sum(len(r['passages']) for r in rows)==123
for r in rows:
 if r['id'].startswith('walters-'):
  source=out/'sources'/f'{r["id"]}.json';d=json.loads(source.read_text())
  assert hashlib.sha256(source.read_bytes()).hexdigest()==r['metadata_sha256']
  assert r['text_license']==d['text_license']=='CC0'
  assert r['image_license']==d['image_license'] and r['image_license'] in ('CC0','CC BY-SA 3.0')
  if r['image_license']=='CC BY-SA 3.0':
   assert d['image_rights_evidence']['license']=='CC BY-SA 3.0' and 'Walters Art Museum' in r['image_changes']
   assert d['image_rights_evidence']['source_url']==r['image_rights_url']
  assert r['review']=='unreviewed' and d['accession']==r['accession'] and d['source_url']==r['source_url']
  assert hashlib.sha256((out/f'{r["id"]}.jpg').read_bytes()).hexdigest()==r['image_sha256']
  assert len(r['passages'])==1 and r['passages'][0]['text']==d['text'] and r['passages'][0]['source_text']==d['transcription']
  assert (not d['alternative_translation']) or r['passages'][0]['remark'].endswith(d['alternative_translation'])
  assert json.loads((out/f'{r["id"]}.json').read_text())==r
  continue
 if r['id'].startswith('maya-'):
  source=out/'sources'/f'{r["id"]}.json';d=json.loads(source.read_text())
  assert hashlib.sha256(source.read_bytes()).hexdigest()==r['metadata_sha256']
  assert r['text_license']==d['license']=='CC BY 4.0' and r['review']=='unreviewed'
  if r['image']:
   assert r['image_license']==d['image_evidence']['license']=='CC BY 4.0'
   assert hashlib.sha256((root/'frontend/public'/r['image'].lstrip('/')).read_bytes()).hexdigest()==r['image_sha256']
  else:assert r['image_license']=='Not included'
  for passage in r['passages'][1:]:
   assert any(passage['text']==e['text'] and passage['text'] in e['source_context'] for e in d['additional_passages'])
  assert r['passages'][0]['text']==d['text'] and d['text'] in d['source_context']
  assert d['authors'] in r['institution'] and d['source_url']==r['source_url']
  assert json.loads((out/f'{r["id"]}.json').read_text())==r
  continue
 source=out/'sources'/f'{r["id"]}.json';d=json.loads(source.read_text())
 assert hashlib.sha256(source.read_bytes()).hexdigest()==r['metadata_sha256']
 assert d['accession_number']==r['accession'] and d['share_license_status']=='CC0'
 assert r['review']=='unreviewed' and r['text_license']==r['image_license']=='CC0'
 assert hashlib.sha256((out/f'{r["id"]}.jpg').read_bytes()).hexdigest()==r['image_sha256']
 expected=[(n,i) for n,i in enumerate(d['inscriptions']) if (i.get('inscription_translation') or '').strip()]
 assert len(expected)==len(r['passages'])
 for p,(n,i) in zip(r['passages'],expected):
  assert p['text']==i['inscription_translation'] and p['remark']==(i.get('inscription_remark') or '')
  assert p['field']==f'inscriptions[{n}].inscription_translation'
 assert '/'+r['accession'] in r['source_url']
 assert json.loads((out/f'{r["id"]}.json').read_text())==r
 assert all(p['source_text']==(i.get('inscription') or '') for p,(_,i) in zip(r['passages'],expected))
assert json.loads((root/'backend/app/data/catalog/curated.json').read_text())==rows
before=(out/'collection.json').read_bytes()
subprocess.run([sys.executable,str(root/'scripts/build_collection.py')],check=True)
assert before==(out/'collection.json').read_bytes()
print('PASS: 115 identities, 123 source entries, provenance/rights/image hashes, deterministic rebuild')
