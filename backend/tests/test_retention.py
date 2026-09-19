from datetime import datetime,timedelta,timezone
import json
import pytest
from app.data.catalog import initialize
from app.data.backup import create
from app.data.retention import plan,apply
from app.data.erasure import run
from test_accounts import users,PASSWORD
from test_removals import allowed


def age(bundle,days):
    p=bundle/'backup.json';data=json.loads(p.read_text());data['created_on']=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat();p.write_text(json.dumps(data))

@pytest.fixture
def copies(tmp_path):
    current=tmp_path/'catalog.sqlite3';initialize(current)
    corpus=tmp_path/'corpus';corpus.mkdir();(corpus/'note').write_text('Fixture')
    root=tmp_path/'backups';root.mkdir()
    for name in ['old','new']: create(current,corpus,root/name)
    age(root/'old',40)
    return root,current,corpus


def test_expiry_keeps_restorable_newest(copies):
    root,current,_=copies;p=plan(root,current)
    assert {b['name']:b['action'] for b in p['bundles']}=={'new':'keep','old':'delete'}
    assert (root/'old').exists()
    result=apply(root,current,p['plan_hash'])
    assert result['protected_restore_verified'] and result['deleted']==['old']
    assert (root/'new/catalog.sqlite3').exists() and current.exists()

@pytest.mark.parametrize('change',['tamper','symlink','unexpected','stale','all_old'])
def test_unsafe_or_changed_inventory_never_deletes(copies,tmp_path,change):
    root,current,corpus=copies;p=plan(root,current)
    if change=='tamper': (root/'old/corpus/note').write_text('Changed')
    if change=='symlink': (root/'link').symlink_to(corpus,target_is_directory=True)
    if change=='unexpected': (root/'random').write_text('Keep')
    if change=='stale': create(current,corpus,root/'third')
    if change=='all_old': age(root/'new',40)
    with pytest.raises(ValueError): apply(root,current,p['plan_hash'])
    assert (root/'old').exists() and (root/'new').exists()


def test_completed_erasure_expires_recent_old_copy(users,tmp_path):
    alice,_,mod,_,current=users;allowed(alice,mod)
    corpus=tmp_path/'corpus';corpus.mkdir();root=tmp_path/'backups';root.mkdir()
    create(current,corpus,root/'before')
    alice.post('/api/auth/close',json={'password':PASSWORD})
    request=mod.get('/api/removal-requests').json()[0]['id'];p=run(current,request);run(current,request,p['plan_hash'])
    with pytest.raises(ValueError,match='fresh backup'): plan(root,current)
    create(current,corpus,root/'after')
    p=plan(root,current);assert next(x for x in p['bundles'] if x['name']=='before')['action']=='delete'
    assert apply(root,current,p['plan_hash'])['deleted']==['before']
