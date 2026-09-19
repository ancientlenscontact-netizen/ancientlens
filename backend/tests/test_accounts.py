import sqlite3
import time
import pytest
from fastapi.testclient import TestClient
from app.api import create_app
from app.data.catalog import connect
from app.data.accounts import Accounts
from test_contributions import draft

ORIGIN={'Origin':'http://127.0.0.1:5173'}
PASSWORD='software fixture passphrase'

@pytest.fixture
def users(tmp_path):
    app=create_app(data_dir=tmp_path)
    path=tmp_path/'language-catalog.sqlite3'
    db=connect(path)
    db.execute("INSERT INTO monuments VALUES ('fixture','Test','Test','Test','ud-egy')")
    db.execute("INSERT INTO passage_records VALUES ('passage','fixture','Test','Unknown','ud-egy',NULL,NULL,'unreviewed','Fixture')")
    db.commit();db.close()
    clients=[]
    for name in ('alice','bravo','moderator'):
        c=TestClient(app,headers=ORIGIN)
        assert c.post('/api/auth/register',json={'username':name,'password':PASSWORD}).status_code==201
        clients.append(c)
    db=connect(path);db.execute("UPDATE accounts SET role='moderator' WHERE username='moderator'");db.commit();db.close()
    return (*clients,TestClient(app,headers=ORIGIN),path)

def visible(c): return c.get('/api/contributions',params={'passage_id':'passage'}).json()

def test_owner_only_edits_and_pending_privacy(users):
    alice,bravo,mod,guest,path=users
    assert guest.post('/api/contributions',json=draft()).status_code==401
    first=alice.post('/api/contributions',json=draft()).json()
    revision={k:v for k,v in draft().items() if k!='passage_id'};revision['base_revision']=1
    for c in (bravo,mod):
        assert c.post(f"/api/contributions/{first['id']}/revisions",json=revision).status_code==403
    assert visible(guest)==visible(bravo)==[]
    assert visible(alice)[0]['can_edit'] is True
    assert visible(mod)[0]['can_moderate'] is True
    assert 'owner_id' not in visible(mod)[0]

def test_moderation_history_visibility_and_new_revision_reset(users):
    alice,bravo,mod,guest,path=users
    id=alice.post('/api/contributions',json=draft()).json()['id']
    url=f'/api/contributions/{id}/moderation'
    decision={'revision':1,'base_event':0,'action':'allowed','reason':'Fixture moderation only'}
    assert alice.post(url,json=decision).status_code==403
    assert mod.post(url,json=decision).status_code==201
    assert mod.post(url,json=decision).status_code==409
    assert visible(guest)[0]['review_status']=='unreviewed'
    assert visible(guest)[0]['moderation_events']==[]
    event=visible(mod)[0]['moderation_events'][-1]['id']
    decision.update(base_event=event,action='hidden')
    assert mod.post(url,json=decision).status_code==201
    assert visible(guest)==[]
    events=visible(alice)[0]['moderation_events'];assert len(events)==2
    decision.update(base_event=events[-1]['id'],action='allowed')
    assert mod.post(url,json=decision).status_code==201
    revision={k:v for k,v in draft().items() if k!='passage_id'};revision.update(base_revision=1,translation='Second fixture')
    assert alice.post(f'/api/contributions/{id}/revisions',json=revision).status_code==201
    assert visible(guest)==[]
    assert visible(alice)[-1]['moderation_status']=='pending'
    assert mod.post(url,json=decision).status_code==409
    decision.update(revision=2,base_event=0,action='changes_requested')
    assert mod.post(url,json=decision).status_code==201
    assert visible(alice)[-1]['review_status']=='unreviewed'
    db=connect(path)
    with pytest.raises(sqlite3.IntegrityError): db.execute("UPDATE moderation_events SET reason='rewrite'")
    with pytest.raises(sqlite3.IntegrityError): db.execute('DELETE FROM moderation_events')
    assert db.execute('PRAGMA foreign_key_check').fetchall()==[];db.close()

def test_login_cookie_logout_expiry_and_no_password_leak(users):
    alice,bravo,mod,guest,path=users
    response=guest.post('/api/auth/login',json={'username':'alice','password':PASSWORD})
    assert response.status_code==200
    cookie=response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Path=/api' in cookie
    assert set(response.json())=={'id','username','role'}
    token=guest.cookies.get('ancientlens_session')
    db=connect(path);rows=db.execute('SELECT password_hash FROM accounts').fetchall()
    assert all(PASSWORD not in row[0] for row in rows)
    assert db.execute('SELECT 1 FROM sessions WHERE token_hash=?',(token,)).fetchone() is None
    assert guest.post('/api/auth/logout').status_code==200
    guest.cookies.set('ancientlens_session',token,path='/api')
    assert guest.get('/api/auth/me').json() is None
    db.execute('UPDATE sessions SET expires_at=?',(int(time.time())-1,));db.commit();db.close()
    assert alice.get('/api/auth/me').json() is None

@pytest.mark.parametrize('origin',[None,'null','https://evil.example','http://127.0.0.1:5173.evil.example'])
def test_cross_origin_writes_rejected(users,origin):
    alice,bravo,mod,guest,path=users
    guest.headers.pop('origin',None)
    if origin: guest.headers['Origin']=origin
    assert guest.post('/api/auth/login',json={'username':'alice','password':PASSWORD}).status_code==403
    assert guest.post('/api/auth/register',json={'username':'charlie','password':PASSWORD}).status_code==403
    alice.headers.pop('origin',None)
    if origin: alice.headers['Origin']=origin
    assert alice.post('/api/contributions',json=draft()).status_code==403
    assert alice.post('/api/auth/logout').status_code==403

def test_role_injection_and_rate_limit(users):
    alice,bravo,mod,guest,path=users
    assert guest.post('/api/auth/register',json={'username':'injected','password':PASSWORD,'role':'moderator'}).status_code==422
    # Count-based checks avoid exercising a costly password KDF repeatedly.
    accounts=Accounts(path)
    for _ in range(10):
        try: accounts.throttle('account:limited',10)
        except Exception: pass
    response=guest.post('/api/auth/login',json={'username':'limited','password':PASSWORD})
    assert response.status_code==429
    response=guest.post('/api/auth/login',json={'username':'alice','password':'wrong fixture password'})
    assert response.status_code==401
    assert guest.get('/api/auth/me').json() is None

def test_legacy_unowned_drafts_fail_closed(users):
    alice,bravo,mod,guest,path=users
    id=alice.post('/api/contributions',json=draft()).json()['id']
    db=connect(path);db.execute('UPDATE contributions SET owner_id=NULL WHERE id=?',(id,));db.commit();db.close()
    assert visible(alice)==[] and visible(guest)==[]
    assert len(visible(mod))==1 and not visible(mod)[0]['can_edit']


def test_invalid_password_is_not_echoed(users):
    alice,bravo,mod,guest,path=users
    response=guest.post('/api/auth/register',json={'username':'example','password':'short-secret'})
    assert response.status_code==422
    assert 'short-secret' not in response.text


def test_secure_cookie_setting(tmp_path,monkeypatch):
    monkeypatch.setenv('ANCIENTLENS_SECURE_COOKIES','1')
    client=TestClient(create_app(data_dir=tmp_path),headers=ORIGIN)
    response=client.post('/api/auth/register',json={'username':'secure_fixture','password':PASSWORD})
    assert response.status_code==201 and 'Secure' in response.headers['set-cookie']
