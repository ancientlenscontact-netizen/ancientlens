"""Seed reference identities only; source translations remain separate published data."""
import json
from pathlib import Path

def seed(db):
    records=json.loads((Path(__file__).parent/'catalog/curated.json').read_text())
    with db:
        for r in records:
            sid=r['id']+'-source'
            db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?)',(sid,r['institution']+' — '+r['title'],r['source_url'],r['retrieved_at'][:10],'CC0 museum metadata; AncientLens unreviewed'))
            db.execute('INSERT OR IGNORE INTO monuments VALUES (?,?,?,?,?)',(r['id'],r['title'],'Cleveland Museum of Art (collection)','United States (collection)',sid))
            db.execute('INSERT OR IGNORE INTO curated_artifacts VALUES (?,?)',(r['id'],r['title']))
            for n,p in enumerate(r['passages']):
                db.execute('INSERT OR IGNORE INTO passage_records VALUES (?,?,?,?,?,NULL,NULL,?,?)',
                    (p['id'],r['id'],f'Inscription {n+1}',p['field'],sid,'unreviewed','Museum source entry; no reviewed image alignment. '+r['note']))
                db.execute('INSERT OR IGNORE INTO passage_references VALUES (?,?,?,?,?)',(p['id'],sid,'translation','licensed','CC0 source; original wording published separately'))
