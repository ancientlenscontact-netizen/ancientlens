import pytest
from test_accounts import users,visible,PASSWORD
from test_contributions import draft
from app.data.accounts import Accounts
from app.data.catalog import connect
from app.data.contributions import Contributions,NewDraft
from app.data.backup import create,restore

def allowed(alice,mod):
    id=alice.post('/api/contributions',json=draft()).json()['id']
    assert mod.post('/api/contributions/'+id+'/moderation',json=dict(revision=1,base_event=0,action='allowed',reason='Fixture')).status_code==201
    return id

def test_withdraw_all_history_private_idempotent_and_not_reallowable(users):
    alice,bravo,mod,guest,path=users;id=allowed(alice,mod)
    assert len(visible(guest))==1
    url='/api/contributions/'+id+'/withdraw'
    assert bravo.post(url).status_code==403
    assert guest.post(url).status_code==401
    assert alice.post(url).json()['erasure_complete'] is False
    assert alice.post(url).status_code==200
    assert visible(guest)==visible(bravo)==[]
    row=visible(alice)[0];assert row['withdrawn'] and not row['can_edit']
    assert mod.post('/api/contributions/'+id+'/moderation',json=dict(revision=1,base_event=row['moderation_events'][-1]['id'],action='allowed',reason='Fixture')).status_code==409
    revision={k:v for k,v in draft().items() if k!='passage_id'};revision['base_revision']=1
    assert alice.post('/api/contributions/'+id+'/revisions',json=revision).status_code==409
    assert bravo.post('/api/contributions/'+id+'/reports',json=dict(revision=1,reason='Fixture')).status_code==404
    assert alice.get('/api/removal-requests').status_code==403
    assert len(mod.get('/api/removal-requests').json())==1

def test_closure_revokes_credentials_and_stale_writes_and_replay(users,tmp_path):
    alice,bravo,mod,guest,path=users;id=allowed(alice,mod)
    accounts=Accounts(path);user=accounts.login('alice',PASSWORD);code=accounts.issue_recovery(user['id']);token=accounts.session(user['id'])
    corpus=tmp_path/'corpus';corpus.mkdir();bundle=tmp_path/'backup';create(path,corpus,bundle)
    assert alice.post('/api/auth/close',json={'password':'incorrect fixture password'}).status_code==401
    assert alice.post('/api/auth/close',json={'password':PASSWORD}).json()['erasure_complete'] is False
    assert visible(guest)==[] and accounts.user(token) is None
    assert accounts.login('alice',PASSWORD) is None
    assert accounts.recover('alice',code,PASSWORD) is None
    with pytest.raises(ValueError): accounts.session(user['id'],user['credential_version'])
    with pytest.raises(ValueError): accounts.issue_recovery(user['id'],user['credential_version'])
    with pytest.raises(PermissionError): Contributions(path).save(NewDraft(**draft()),user=user)
    result=restore(bundle,tmp_path/'restored',removals_from=path)
    assert result['removal_requests_reconciled']==1 and not result['requires_removal_reconciliation']
    restored=tmp_path/'restored/catalog.sqlite3'
    assert Accounts(restored).login('alice',PASSWORD) is None
    assert Contributions(restored).list('passage')==[]
    db=connect(path);assert db.execute('SELECT count(*) FROM contribution_revisions').fetchone()[0]==1;db.close()
