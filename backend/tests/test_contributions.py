import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.api import create_app
from app.data.catalog import connect, initialize, ASSETS

@pytest.fixture
def local(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path),headers={'Origin':'http://127.0.0.1:5173'})
    assert client.post('/api/auth/register',json={'username':'test_author','password':'test fixture passphrase'}).status_code==201
    path = tmp_path/'language-catalog.sqlite3'
    db = connect(path)
    db.execute("INSERT INTO monuments VALUES ('fixture','Test monument','Test site','Test country','ud-egy')")
    db.execute("INSERT INTO passage_records VALUES ('passage','fixture','Test passage','Unknown wall','ud-egy',NULL,NULL,'unreviewed','Fixture, not a reading')")
    db.commit(); db.close()
    return client, path

def draft(**changes):
    return dict(passage_id='passage', author='Test author', translation_language='Test language',
                translation='TEST FIXTURE ONLY — not an ancient reading', source='Test source',
                reuse_terms='CC BY-SA 4.0', rights_basis='original_work',
                rights_evidence='Test declaration', notes='Uncertain test text', ai_assisted=True, terms_version='2026-09-16.1', terms_accepted=True, **changes)

def test_draft_revision_history_survives_restart_and_conflict(local):
    client,path = local
    data = draft()
    first = client.post('/api/contributions',json=data)
    assert first.status_code==201
    id = first.json()['id']
    assert first.json()['review_status']=='unreviewed'
    revision = {k:v for k,v in data.items() if k!='passage_id'}
    revision.update(base_revision=1,translation='Revised fixture')
    assert client.post(f'/api/contributions/{id}/revisions',json=revision).status_code==201
    assert client.post(f'/api/contributions/{id}/revisions',json=revision).status_code==409
    restarted = TestClient(create_app(data_dir=path.parent))
    restarted.cookies.update(client.cookies)
    rows = restarted.get('/api/contributions',params={'passage_id':'passage'}).json()
    assert [r['translation'] for r in rows]==[data['translation'],'Revised fixture']
    assert all(r['review_status']=='unreviewed' and r['moderation_status']=='pending' for r in rows)
    db=connect(path)
    with pytest.raises(sqlite3.IntegrityError): db.execute("UPDATE contribution_revisions SET translation='overwrite'")
    with pytest.raises(sqlite3.IntegrityError): db.execute('DELETE FROM contribution_revisions')
    assert db.execute('SELECT count(*) FROM passage_image_links').fetchone()[0]==0
    assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
    db.close()

@pytest.mark.parametrize('field,value',[('author','  '),('source',''),('translation','x'*20001),('rights_evidence',''),('review_status','reviewed'),('moderation_status','approved'),('rights_basis','copied')])
def test_invalid_or_promoted_draft_is_not_saved(local,field,value):
    client,path=local; data=draft(); data[field]=value
    assert client.post('/api/contributions',json=data).status_code==422
    assert client.get('/api/contributions',params={'passage_id':'passage'}).json()==[]

def test_missing_passage_and_revision_are_rejected_and_alternatives_coexist(local):
    client,path=local; data=draft();data['passage_id']='missing'
    assert client.post('/api/contributions',json=data).status_code==404
    data=draft()
    ids=[client.post('/api/contributions',json=data).json()['id'] for _ in range(2)]
    assert ids[0]!=ids[1]
    revision={k:v for k,v in data.items() if k!='passage_id'};revision['base_revision']=1
    assert client.post('/api/contributions/missing/revisions',json=revision).status_code==404
    passages=client.get('/api/catalog/passages').json()
    assert passages[0]['reviewed_image_links']==0
    assert passages[0]['review_status']=='unreviewed'

def test_v2_migration_preserves_existing_rows(tmp_path):
    path=tmp_path/'v2.db';db=connect(path)
    db.executescript((ASSETS/'schema.sql').read_text())
    db.executescript((ASSETS/'migration-002.sql').read_text())
    db.execute("INSERT INTO sources VALUES ('existing','Existing source','https://example.org','2026-09-15','Keep this')")
    db.commit();db.close()
    initialize(path);initialize(path)
    db=connect(path)
    assert db.execute('SELECT version FROM catalog_version').fetchone()[0]==9
    assert db.execute('SELECT note FROM sources').fetchone()[0]=='Keep this'
    assert db.execute('SELECT count(*) FROM contribution_revisions').fetchone()[0]==0
    db.close()
