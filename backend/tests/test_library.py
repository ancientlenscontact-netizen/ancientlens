import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.api import create_app
from app.data.catalog import connect,initialize
from app.data.removals import reconcile
from test_contributions import draft

@pytest.fixture
def clients(tmp_path):
    app=create_app(data_dir=tmp_path)
    a=TestClient(app,headers={'Origin':'http://127.0.0.1:5173'})
    b=TestClient(app,headers={'Origin':'http://127.0.0.1:5173'})
    for c,name in [(a,'library_a'),(b,'library_b')]:
        assert c.post('/api/auth/register',json={'username':name,'password':'private test passphrase'}).status_code==201
    return a,b,tmp_path/'language-catalog.sqlite3'

def test_library_privacy_conflict_and_removal(clients):
    a,b,path=clients;url='/api/library/cma-102365'
    assert a.get(url).json()['version']==0
    assert a.put(url,json={'notes':'Private fixture','version':0}).status_code==200
    assert a.get('/api/library').headers['cache-control']=='no-store'
    assert b.get('/api/library').json()==[] and b.get(url).json()['notes']==''
    with connect(path) as db:db.execute("UPDATE accounts SET role='moderator' WHERE username='library_b'")
    assert b.get('/api/library').json()==[] and b.get(url).json()['notes']==''
    assert a.put(url,json={'notes':'Stale overwrite','version':0}).status_code==409
    assert a.get(url).json()['notes']=='Private fixture'
    assert a.put(url,json={'notes':'x'*4001,'version':1}).status_code==422
    assert a.put(url,json={'notes':'x','version':1},headers={'Origin':'https://evil.example'}).status_code==403
    assert a.put('/api/library/unknown',json={'version':0}).status_code==404
    guest=TestClient(create_app(data_dir=path.parent))
    assert guest.get('/api/library').status_code==401
    assert guest.get(url).status_code==401
    assert a.put(url,json={'version':1,'remove':True}).json()['notes']==''
    assert a.get('/api/library').json()==[]
    assert a.put(url,json={'version':2,'notes':'Resaved fixture'}).status_code==200
    assert len(a.get('/api/library').json())==1

def test_deleted_note_does_not_return_on_restore(clients,tmp_path):
    a,b,path=clients;url='/api/library/cma-102365'
    a.put(url,json={'version':0,'notes':'Delete this fixture'})
    older=tmp_path/'older.sqlite3'
    with sqlite3.connect(path) as src,sqlite3.connect(older) as dst:src.backup(dst)
    a.put(url,json={'version':1,'remove':True})
    reconcile(path.resolve(),older.resolve())
    with sqlite3.connect(older) as db:
        assert db.execute('SELECT notes,deleted FROM saved_artifacts').fetchone()==('',1)
    # Resaving must not erase the deletion ledger for older snapshots.
    a.put(url,json={'version':2,'notes':'New fixture'})
    reconcile(path.resolve(),older.resolve())
    with sqlite3.connect(older) as db:assert db.execute('SELECT notes FROM saved_artifacts').fetchone()[0]==''

def test_account_closure_clears_private_notes(clients):
    a,b,path=clients
    a.put('/api/library/cma-102365',json={'version':0,'notes':'Private fixture'})
    assert a.post('/api/auth/close',json={'password':'private test passphrase'}).status_code==200
    with connect(path) as db:assert db.execute('SELECT count(*) FROM saved_artifacts').fetchone()[0]==0
    assert a.get('/api/library').status_code==401

def test_curated_passages_and_moderation_unchanged(clients):
    a,b,path=clients
    initialize(path)
    passages=a.get('/api/catalog/passages').json()
    assert len([p for p in passages if p['id'].startswith('cma-')])==67
    data=draft();data['passage_id']='cma-102365-0'
    result=a.post('/api/contributions',json=data)
    assert result.status_code==201 and result.json()['review_status']=='unreviewed'
    assert b.get('/api/contributions?passage_id=cma-102365-0').json()==[]
    assert a.get('/api/contributions?passage_id=cma-102365-0').json()[0]['moderation_status']=='pending'
    with connect(path) as db:
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert db.execute('SELECT count(*) FROM curated_artifacts').fetchone()[0]==92


def test_maya_licensed_reference_and_private_note_survive_reseed(clients):
    a,b,path=clients
    ident='maya-ccit-vaso-8'
    response=a.put('/api/library/'+ident,json={'notes':'Private Maya reading note','version':0,'remove':False})
    assert response.status_code==200
    initialize(path)
    assert a.get('/api/library/'+ident).json()['notes']=='Private Maya reading note'
    assert b.get('/api/library/'+ident).json()['notes']==''
    with connect(path) as db:
        assert db.execute("SELECT count(*) FROM passage_records WHERE id LIKE 'maya-%'").fetchone()[0]==30
        source=db.execute('SELECT * FROM sources WHERE id=?',(ident+'-source',)).fetchone()
        assert 'Guido Krempel' in source[1] and 'CC BY 4.0' in source[4]
        monument=db.execute('SELECT * FROM monuments WHERE id=?',(ident,)).fetchone()
        assert 'Cleveland' not in str(monument)
        ref=db.execute('SELECT * FROM passage_references WHERE passage_id=?',(ident+'-0',)).fetchone()
        assert 'CC BY 4.0' in str(ref) and 'CC0' not in str(ref)


def test_walters_reference_is_not_mesoamerica(clients):
    a,b,path=clients
    initialize(path)
    with connect(path) as db:
        rows=db.execute("SELECT * FROM monuments WHERE id LIKE 'walters-%'").fetchall()
        assert len(rows)==3
        assert all('Walters Art Museum' in str(r) and 'Mesoamerica' not in str(r) for r in rows)
        assert db.execute("SELECT count(*) FROM passage_records WHERE id LIKE 'walters-%' AND review_status='unreviewed'").fetchone()[0]==3
