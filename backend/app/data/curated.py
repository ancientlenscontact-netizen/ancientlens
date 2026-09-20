"""Seed reference identities only; source translations remain separate published data."""
import json
from pathlib import Path

def seed(db):
    records=json.loads((Path(__file__).parent/'catalog/curated.json').read_text())
    with db:
        for r in records:
            sid=r['id']+'-source'
            db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?)',(sid,r['institution']+' — '+r['title'],r['source_url'],r['retrieved_at'][:10],r['text_license']+' published source; AncientLens unreviewed'))
            db.execute('INSERT OR IGNORE INTO monuments VALUES (?,?,?,?,?)',(r['id'],r['title'],'Cleveland Museum of Art (collection)' if r['id'].startswith('cma-') else 'See published source; findspot unverified','United States (collection)' if r['id'].startswith('cma-') else 'Mesoamerica (cultural region)',sid))
            db.execute('INSERT OR IGNORE INTO curated_artifacts VALUES (?,?)',(r['id'],r['title']))
            for n,p in enumerate(r['passages']):
                db.execute('INSERT OR IGNORE INTO passage_records VALUES (?,?,?,?,?,NULL,NULL,?,?)',
                    (p['id'],r['id'],f'Inscription {n+1}',p['field'],sid,'unreviewed','Published source entry; no reviewed image alignment. '+r['note']))
                db.execute('INSERT OR IGNORE INTO passage_references VALUES (?,?,?,?,?)',(p['id'],sid,'translation','licensed',r['text_license']+' source; attribution and wording published separately'))
