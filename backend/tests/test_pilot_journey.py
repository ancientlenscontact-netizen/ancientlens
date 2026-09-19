"""One isolated HTTPS community journey covers release-critical account/data boundaries."""
from fastapi.testclient import TestClient
from app.api import create_app
from app.data.catalog import connect
from test_contributions import draft

def test_complete_community_journey(tmp_path,monkeypatch):
    monkeypatch.setenv('ANCIENTLENS_SERVICE_MODE','community')
    monkeypatch.setenv('ANCIENTLENS_SECURE_COOKIES','1')
    monkeypatch.setenv('ANCIENTLENS_ALLOWED_ORIGINS','https://pilot.test')
    app=create_app(data_dir=tmp_path)
    def client():return TestClient(app,base_url='https://pilot.test',headers={'Origin':'https://pilot.test'})
    owner,other,moderator,guest=client(),client(),client(),client()
    password='disposable fixture passphrase'
    response=owner.post('/api/auth/register',json={'username':'journey_owner','password':password})
    assert response.status_code==201
    recovery=response.json()['recovery_code']
    for c,name in [(other,'journey_other'),(moderator,'journey_moderator')]:
        assert c.post('/api/auth/register',json={'username':name,'password':password}).status_code==201
    with connect(tmp_path/'language-catalog.sqlite3') as db:db.execute("UPDATE accounts SET role='moderator' WHERE username='journey_moderator'")
    url='/api/library/cma-102365'
    assert owner.put(url,json={'version':0,'notes':'Private journey note'}).status_code==200
    assert owner.put(url,json={'version':1,'notes':'Edited private note'}).status_code==200
    assert owner.get('/api/library').json()[0]['notes']=='Edited private note'
    assert other.get('/api/library').json()==moderator.get('/api/library').json()==[]
    assert guest.get('/api/library').status_code==401
    payload=draft();payload['passage_id']='cma-102365-0'
    created=owner.post('/api/contributions',json=payload);assert created.status_code==201
    cid=created.json()['id'];listing='/api/contributions?passage_id=cma-102365-0'
    assert guest.get(listing).json()==[]
    assert moderator.post(f'/api/contributions/{cid}/moderation',json={'revision':1,'base_event':0,'action':'allowed','reason':'Fixture visibility review'}).status_code==201
    assert guest.get(listing).json()[0]['review_status']=='unreviewed'
    assert owner.post(f'/api/contributions/{cid}/withdraw').status_code==200
    assert guest.get(listing).json()==[]
    recovered=client()
    new_password='new disposable fixture passphrase'
    assert recovered.post('/api/auth/recover',json={'username':'journey_owner','password':new_password,'recovery_code':recovery}).status_code==200
    assert owner.get('/api/library').status_code==401
    assert recovered.post('/api/auth/login',json={'username':'journey_owner','password':new_password}).status_code==200
    assert recovered.get(url).json()['notes']=='Edited private note'
    assert recovered.put(url,json={'version':2,'remove':True}).status_code==200
    assert recovered.get('/api/library').json()==[]
    assert recovered.post('/api/auth/close',json={'password':new_password}).status_code==200
    assert recovered.get('/api/library').status_code==401
    assert guest.post('/api/inscriptions').status_code==404
    with connect(tmp_path/'language-catalog.sqlite3') as db:assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
