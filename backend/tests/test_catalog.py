import json
import sqlite3
import pytest
from app.data.catalog import initialize, connect, summary, ASSETS

def test_catalog_is_extensible_and_rerun_preserves_data(tmp_path):
    p=tmp_path/'catalog.db'; initialize(p)
    db=connect(p)
    db.execute("INSERT INTO languages VALUES ('future-language','Future language fixture','Test extension','ud-egy')")
    db.commit(); db.close(); initialize(p)
    assert summary(p)['languages']==2
    db=connect(p)
    assert db.execute("SELECT count(*) FROM capabilities WHERE status<>'unavailable'").fetchone()[0]==0
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    db.close()

def test_catalog_rejects_cross_language_variety_and_unsupported_claims(tmp_path):
    p=tmp_path/'catalog.db'; initialize(p); db=connect(p)
    db.execute("INSERT INTO languages VALUES ('other','Other fixture','test','ud-egy')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO writing_systems VALUES ('bad','other','egy-old','egyptian-hieroglyphic','ud-egy','test')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE capabilities SET status='validated' WHERE writing_system_id='old-hieroglyphic'")
    db.execute("INSERT INTO text_units VALUES ('unit','object','sample',?,NULL,'test')",('a'*64,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO classification_assertions VALUES ('assertion','unit','old-hieroglyphic','reviewed','AI',NULL,NULL,NULL)")
    db.close()

def test_failed_initialization_is_atomic(tmp_path):
    assets=tmp_path/'assets'; assets.mkdir()
    (assets/'schema.sql').write_text((ASSETS/'schema.sql').read_text())
    seed=json.loads((ASSETS/'seed.json').read_text()); seed['varieties'][0]['language_id']='missing'
    (assets/'seed.json').write_text(json.dumps(seed))
    p=tmp_path/'catalog.db'
    with pytest.raises(sqlite3.IntegrityError): initialize(p,assets)
    db=connect(p); assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()==[]; db.close()
    initialize(p); assert summary(p)['varieties']==5
