import asyncio
import hashlib
import sqlite3
import time
import pytest
from fastapi.testclient import TestClient
from app.api import create_app
from app.api.limits import BodyLimit
from app.data.catalog import connect
from app.data.accounts import Accounts
from test_accounts import users, PASSWORD, ORIGIN, visible
from test_contributions import draft


def test_quota_is_transactional_and_persists(users):
    alice,bravo,mod,guest,path=users
    for _ in range(20): assert alice.post('/api/contributions',json=draft()).status_code==201
    before=len(visible(alice))
    response=alice.post('/api/contributions',json=draft())
    assert response.status_code==429 and 'Retry-After' in response.headers
    assert len(visible(alice))==before==10
    assert len(alice.get('/api/contributions',params={'passage_id':'passage','offset':10}).json())==10
    assert alice.get('/api/contributions',params={'passage_id':'passage','limit':11}).status_code==422
    assert visible(guest)==[]
    db=connect(path);assert db.execute('SELECT count(*) FROM contributions').fetchone()[0]==20
    assert db.execute('SELECT used FROM write_quotas WHERE kind=?',('draft saves',)).fetchone()[0]==20
    # A different account has its own allowance.
    assert bravo.post('/api/contributions',json=draft()).status_code==201
    db.close()


def test_private_report_resolution_does_not_change_visibility(users):
    alice,bravo,mod,guest,path=users
    id=alice.post('/api/contributions',json=draft()).json()['id'];url=f'/api/contributions/{id}/reports'
    data={'revision':1,'reason':'Fixture rights concern'}
    assert guest.post(url,json=data).status_code==401
    assert bravo.post(url,json=data).status_code==404
    assert mod.post(f'/api/contributions/{id}/moderation',json={'revision':1,'base_event':0,'action':'allowed','reason':'Fixture'}).status_code==201
    report=bravo.post(url,json=data);assert report.status_code==201
    assert bravo.post(url,json=data).status_code==409
    assert guest.get('/api/reports').status_code==401
    assert alice.get('/api/reports').status_code==403
    queue=mod.get('/api/reports').json();assert len(queue)==1 and queue[0]['reporter']=='bravo'
    endpoint=f"/api/reports/{report.json()['id']}/resolve"
    resolution={'outcome':'dismissed','reason':'Fixture resolution'}
    assert alice.post(endpoint,json=resolution).status_code==403
    assert mod.post(endpoint,json=resolution).status_code==200
    assert mod.post(endpoint,json=resolution).status_code==409
    assert mod.get('/api/reports').json()==[]
    assert visible(guest)[0]['moderation_status']=='allowed'
    assert visible(guest)[0]['review_status']=='unreviewed'
    db=connect(path)
    with pytest.raises(sqlite3.IntegrityError): db.execute("UPDATE reports SET reason='changed'")
    with pytest.raises(sqlite3.IntegrityError): db.execute('DELETE FROM report_resolutions')
    db.close()


def test_recovery_code_single_use_rotation_and_session_revocation(users):
    alice,bravo,mod,guest,path=users
    code_response=alice.post('/api/auth/recovery-code',json={'password':PASSWORD})
    assert code_response.status_code==200
    code=code_response.json()['recovery_code'];assert len(code)==64
    db=connect(path);assert code not in str(db.execute('SELECT * FROM recovery_codes').fetchall());db.close()
    old_token=alice.cookies.get('ancientlens_session')
    new_password='new isolated test passphrase'
    checked=Accounts(path).login('alice',PASSWORD)
    reset=guest.post('/api/auth/recover',json={'username':'alice','password':new_password,'recovery_code':code})
    assert reset.status_code==200
    assert reset.json()['recovery_code']!=code
    assert alice.get('/api/auth/me').json() is None
    assert guest.get('/api/auth/me').json() is None
    assert Accounts(path).login('alice',PASSWORD) is None
    assert Accounts(path).login('alice',new_password)
    # An old-password login already in flight cannot resurrect a usable session after reset.
    race_token=Accounts(path).session(checked['id'],checked['credential_version'])
    assert Accounts(path).user(race_token) is None
    assert Accounts(path).user(old_token) is None
    assert guest.post('/api/auth/recover',json={'username':'alice','password':PASSWORD,'recovery_code':code}).status_code==401
    assert guest.post('/api/auth/recover',json={'username':'nobody','password':PASSWORD,'recovery_code':code}).status_code==401


def test_registration_issues_code_but_login_never_repeats_it(tmp_path):
    c=TestClient(create_app(data_dir=tmp_path),headers=ORIGIN)
    payload={'username':'fresh','password':PASSWORD}
    registered=c.post('/api/auth/register',json=payload).json()
    assert len(registered['recovery_code'])==64
    assert 'recovery_code' not in c.post('/api/auth/login',json=payload).json()
    assert 'credential_version' not in registered
    assert c.post('/api/auth/recovery-code',json={'password':'wrong test passphrase'}).status_code==401


def test_oversize_chunked_body_rejected_before_app():
    reached=[];sent=[]
    async def application(scope,receive,send): reached.append(True)
    messages=iter([{'type':'http.request','body':b'x'*200000,'more_body':True},{'type':'http.request','body':b'y'*100000,'more_body':False}])
    async def receive(): return next(messages)
    async def send(message): sent.append(message)
    asyncio.run(BodyLimit(application)({'type':'http','method':'POST','path':'/api/auth/login','headers':[]},receive,send))
    assert not reached and sent[0]['status']==413


def test_oversize_json_not_parsed(tmp_path):
    c=TestClient(create_app(data_dir=tmp_path),headers=ORIGIN)
    assert c.post('/api/auth/login',content=b'x'*300000,headers={'Content-Type':'application/json'}).status_code==413


def test_community_mode_excludes_image_routes_and_requires_secure_config(tmp_path,monkeypatch):
    monkeypatch.setenv('ANCIENTLENS_SERVICE_MODE','community')
    with pytest.raises(ValueError): create_app(data_dir=tmp_path)
    monkeypatch.setenv('ANCIENTLENS_ALLOWED_ORIGINS','https://ancientlens.example')
    monkeypatch.setenv('ANCIENTLENS_SECURE_COOKIES','1')
    c=TestClient(create_app(data_dir=tmp_path))
    assert c.get('/api/features').json()['image_inspector'] is False
    assert c.post('/api/inscriptions',content=b'x').status_code==404
    assert c.get('/api/inscriptions/anything').status_code==404
    assert c.get('/media/anything').status_code==404
    assert not (tmp_path/'media').exists()
    assert not (tmp_path/'ancientlens.sqlite3').exists()
    paths=c.get('/openapi.json').json()['paths']
    assert not any('/inscriptions' in path for path in paths)


def test_local_inspector_still_available(tmp_path):
    c=TestClient(create_app(data_dir=tmp_path))
    assert c.get('/api/features').json()['image_inspector'] is True
    assert c.post('/api/inscriptions').status_code==422
