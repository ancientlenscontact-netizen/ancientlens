"""Release check: independent count, fidelity, provenance and image assertions."""
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'frontend/public/curated'
rows=json.loads((out/'collection.json').read_text())
assert len(rows)==51 and len({r['accession'] for r in rows})==51
assert len({r['id'] for r in rows})==51
assert {r['collection'] for r in rows}=={'Egyptian','Greek','Roman','Chinese','Assyrian','Indian','Maya'}
assert sum(len(r['passages']) for r in rows)==58
for r in rows:
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
print('PASS: 51 identities, 58 exact source entries, provenance/rights/image hashes, deterministic rebuild')
