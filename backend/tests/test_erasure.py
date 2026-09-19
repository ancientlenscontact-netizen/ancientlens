import sqlite3
import pytest
from test_accounts import users,PASSWORD
from test_removals import allowed
from test_contributions import draft
from app.data.accounts import Accounts
from app.data.catalog import connect
from app.data.erasure import run,TRIGGERS
from app.data.backup import create,restore

@pytest.mark.parametrize('kind',['contribution','account'])
def test_purge_and_restore(users,tmp_path,kind):
    alice,bravo,mod,guest,path=users
    target=allowed(alice,mod)
    other=bravo.post('/api/contributions',json=draft()).json()['id']
    assert bravo.post('/api/contributions/'+target+'/reports',json={'revision':1,'reason':'Private fixture report'}).status_code==201
    accounts=Accounts(path);old=accounts.login('alice',PASSWORD)
    corpus=tmp_path/'corpus';corpus.mkdir();bundle=tmp_path/'before';create(path,corpus,bundle)
    if kind=='account': assert alice.post('/api/auth/close',json={'password':PASSWORD}).status_code==200
    else: assert alice.post('/api/contributions/'+target+'/withdraw').status_code==200
    request=mod.get('/api/removal-requests').json()[0]['id']
    preview=run(path,request)
    db=connect(path);assert db.execute('SELECT count(*) FROM contribution_revisions').fetchone()[0]==2;db.close()
    assert preview['counts']['contributions']==1 and preview['counts']['reports']==1
    result=run(path,request,preview['plan_hash']);assert result['catalog_purged'] and not result['backups_erased']
    db=connect(path)
    assert db.execute('SELECT id FROM contributions').fetchall()==[(other,)]
    assert db.execute('SELECT count(*) FROM reports').fetchone()[0]==0
    assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
    assert len(db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name IN ("+','.join('?' for _ in TRIGGERS)+')',TRIGGERS).fetchall())==len(TRIGGERS)
    with pytest.raises(sqlite3.IntegrityError): db.execute("UPDATE contribution_revisions SET notes='forged'")
    if kind=='account':
        row=db.execute('SELECT username,password_hash,closed_on FROM accounts WHERE id=?',(old['id'],)).fetchone()
        assert row[0]=='removed:'+old['id'] and row[1]=='' and row[2]
        assert accounts.login('alice',PASSWORD) is None
    db.close()
    repeat=run(path,request);assert run(path,request,repeat['plan_hash'])['already_purged']
    assert mod.get('/api/removal-requests').json()[0]['catalog_purged_on']
    restore(bundle,tmp_path/'restore',removals_from=path)
    db=connect(tmp_path/'restore/catalog.sqlite3')
    assert db.execute('SELECT id FROM contributions').fetchall()==[(other,)]
    assert db.execute('SELECT count(*) FROM erasure_events').fetchone()[0]==1;db.close()
    after=tmp_path/'after';create(path,corpus,after)
    restore(after,tmp_path/'again',removals_from=path)
    if kind=='account':
        db=connect(tmp_path/'again/catalog.sqlite3');assert db.execute('SELECT password_hash FROM accounts WHERE id=?',(old['id'],)).fetchone()[0]=='';db.close()

def test_stale_plan_and_failed_purge_are_atomic(users):
    alice,bravo,mod,guest,path=users;id=allowed(alice,mod)
    alice.post('/api/contributions/'+id+'/withdraw');request=mod.get('/api/removal-requests').json()[0]['id']
    first=run(path,request)
    mod.post('/api/contributions/'+id+'/reports',json={'revision':1,'reason':'New report'})
    with pytest.raises(ValueError,match='Plan changed'): run(path,request,first['plan_hash'])
    db=connect(path);db.execute("CREATE TRIGGER fail_erasure BEFORE INSERT ON erasure_events BEGIN SELECT RAISE(ABORT,'injected failure'); END;");db.commit();db.close()
    preview=run(path,request)
    with pytest.raises(sqlite3.IntegrityError): run(path,request,preview['plan_hash'])
    db=connect(path)
    assert db.execute('SELECT count(*) FROM contribution_revisions').fetchone()[0]==1
    assert db.execute('SELECT count(*) FROM reports').fetchone()[0]==1
    assert db.execute('SELECT count(*) FROM erasure_events').fetchone()[0]==0
    with pytest.raises(sqlite3.IntegrityError): db.execute('DELETE FROM contribution_revisions')
    db.close()

def test_unknown_request(users):
    *_,path=users
    with pytest.raises(ValueError,match='not found'): run(path,999)

def test_erasing_moderator_redacts_notes_without_reversing_decisions(users):
    alice,bravo,mod,guest,path=users;id=allowed(alice,mod)
    report=bravo.post('/api/contributions/'+id+'/reports',json={'revision':1,'reason':'Other reporter fixture'}).json()['id']
    mod.post('/api/reports/'+str(report)+'/resolve',json={'outcome':'dismissed','reason':'Private moderator note'})
    mod.post('/api/contributions/'+id+'/reports',json={'revision':1,'reason':'Moderator private report'})
    assert mod.post('/api/auth/close',json={'password':PASSWORD}).status_code==200
    db=connect(path);request=db.execute("SELECT id FROM removal_requests WHERE kind='account'").fetchone()[0];db.close()
    preview=run(path,request);run(path,request,preview['plan_hash'])
    db=connect(path)
    assert db.execute('SELECT action,reason FROM moderation_events').fetchone()==('allowed','[Removed during account erasure]')
    assert db.execute('SELECT reason FROM report_resolutions').fetchone()[0]=='[Removed during account erasure]'
    assert db.execute('SELECT reason FROM reports').fetchall()==[('Other reporter fixture',)]
    assert db.execute('SELECT count(*) FROM contributions').fetchone()[0]==1
    assert db.execute('PRAGMA foreign_key_check').fetchall()==[];db.close()
    assert guest.get('/api/contributions',params={'passage_id':'passage'}).json()[0]['id']==id
