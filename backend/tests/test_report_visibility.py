import pytest
from test_accounts import users,visible
from test_contributions import draft
from app.data.catalog import connect

@pytest.mark.parametrize('restriction',['legacy','permission','conflicting_license'])
def test_historical_allow_does_not_bypass_rights_for_reports(users,restriction):
    alice,bravo,mod,guest,path=users
    payload=draft()
    if restriction=='permission':
        payload.update(rights_basis='permission_supported',reuse_terms='Source-specific permission')
    id=alice.post('/api/contributions',json=payload).json()['id']
    # Simulate historical/imported rows predating current publication safeguards.
    db=connect(path)
    if restriction!='permission':
        trigger=db.execute("SELECT sql FROM sqlite_master WHERE name='revisions_no_update'").fetchone()[0]
        db.execute('DROP TRIGGER revisions_no_update')
        if restriction=='legacy': db.execute('UPDATE contribution_revisions SET terms_version=NULL WHERE contribution_id=?',(id,))
        else: db.execute("UPDATE contribution_revisions SET reuse_terms='Old source terms' WHERE contribution_id=?",(id,))
        db.execute(trigger)
    actor=db.execute("SELECT id FROM accounts WHERE username='moderator'").fetchone()[0]
    db.execute("INSERT INTO moderation_events(contribution_id,revision,actor_id,action,reason,created_on) VALUES (?,1,?,'allowed','Historical fixture','2026-09-16')",(id,actor))
    db.commit();db.close()
    assert visible(bravo)==visible(guest)==[]
    url='/api/contributions/'+id+'/reports'
    assert bravo.post(url,json={'revision':1,'reason':'Fixture'}).status_code==404
    assert alice.post(url,json={'revision':1,'reason':'Owner fixture'}).status_code==201
    assert mod.post(url,json={'revision':1,'reason':'Moderator fixture'}).status_code==201
