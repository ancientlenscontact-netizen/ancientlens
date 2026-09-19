import sqlite3
import pytest
from test_accounts import users, visible
from test_contributions import draft
from app.data.catalog import connect, initialize, ASSETS

@pytest.mark.parametrize('value',[None,False,1,'true'])
def test_explicit_boolean_acceptance_required(users,value):
    alice,_,_,_,path=users
    data=draft()
    if value is None: data.pop('terms_accepted')
    else: data['terms_accepted']=value
    assert alice.post('/api/contributions',json=data).status_code==422
    assert visible(alice)==[]

@pytest.mark.parametrize('field,value',[('terms_version','old'),('reuse_terms','All rights reserved'),('accepted_on','forged'),('accepted_by','forged')])
def test_stale_terms_conflicting_license_or_forged_audit_rejected(users,field,value):
    alice,_,_,_,_=users;data=draft();data[field]=value
    assert alice.post('/api/contributions',json=data).status_code==422

def test_revision_acceptance_audit_and_permission_gate(users):
    alice,_,mod,guest,path=users
    first=alice.post('/api/contributions',json=draft()).json()
    row=visible(alice)[0]
    assert row['terms_version']=='2026-09-16.1' and row['accepted_on']==row['created_on']
    assert 'accepted_by' not in row
    db=connect(path)
    assert db.execute('SELECT accepted_by FROM contribution_revisions').fetchone()[0]==db.execute("SELECT id FROM accounts WHERE username='alice'").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError): db.execute("UPDATE contribution_revisions SET terms_version='forged'")
    db.close()
    revision={k:v for k,v in draft().items() if k!='passage_id'}
    revision.update(base_revision=1,rights_basis='permission_supported',reuse_terms='Source-specific permission')
    missing=dict(revision);missing.pop('terms_accepted')
    assert alice.post('/api/contributions/'+first['id']+'/revisions',json=missing).status_code==422
    assert alice.post('/api/contributions/'+first['id']+'/revisions',json=revision).status_code==201
    decision=dict(revision=2,base_event=0,action='allowed',reason='Test visibility')
    assert mod.post('/api/contributions/'+first['id']+'/moderation',json=decision).status_code==409
    assert visible(guest)==[]
    decision['action']='changes_requested'
    assert mod.post('/api/contributions/'+first['id']+'/moderation',json=decision).status_code==201
    assert all(r['review_status']=='unreviewed' for r in visible(alice))

def test_v5_migration_does_not_invent_acceptance(tmp_path):
    path=tmp_path/'legacy.sqlite3';db=connect(path)
    db.executescript((ASSETS/'schema.sql').read_text())
    for n in range(2,6): db.executescript((ASSETS/f'migration-{n:03d}.sql').read_text())
    db.execute('PRAGMA foreign_keys=OFF')
    db.execute("INSERT INTO contributions VALUES ('legacy','unknown','old',NULL)")
    db.execute("INSERT INTO contribution_revisions VALUES ('legacy',1,'Test','Test','Fixture only','Test','Old terms','original_work','Test','',0,'old','unreviewed','pending')")
    db.commit();db.close();initialize(path)
    db=connect(path)
    assert db.execute('SELECT terms_version,accepted_on,accepted_by,reuse_terms FROM contribution_revisions').fetchone()==(None,None,None,'Old terms')
    db.close()
