import json
import sqlite3
import pytest
from app.data.backup import create,verify,restore
from app.data.catalog import initialize,connect
from app.data.accounts import Accounts

@pytest.fixture
def bundle(tmp_path):
    source=tmp_path/'catalog.sqlite3';initialize(source)
    accounts=Accounts(source);user=accounts.register('backup_fixture','software test password')
    accounts.session(user['id'])
    corpus=tmp_path/'corpus';corpus.mkdir();(corpus/'note.json').write_text('{"fixture":true}')
    output=tmp_path/'backup';create(source,corpus,output)
    return source,corpus,output


def test_roundtrip_preserves_data_and_revokes_sessions(bundle,tmp_path):
    source,corpus,output=bundle
    target=tmp_path/'restore';result=restore(output,target)
    assert result['sessions_revoked']==1
    assert (target/'corpus/note.json').read_bytes()==(corpus/'note.json').read_bytes()
    db=connect(target/'catalog.sqlite3');assert db.execute('SELECT username FROM accounts').fetchone()[0]=='backup_fixture'
    assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==0;db.close()
    db=connect(source);assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==1;db.close()
    assert verify(output)['catalog_version']==9
    with pytest.raises(FileExistsError): restore(output,target)
    with pytest.raises(FileExistsError): create(source,corpus,output)
    assert (output.stat().st_mode & 0o777)==0o700
    assert ((target/'catalog.sqlite3').stat().st_mode & 0o777)==0o600

@pytest.mark.parametrize('bad',['tampered','missing','traversal','extra'])
def test_invalid_bundles_do_not_restore(bundle,tmp_path,bad):
    source,corpus,output=bundle
    if bad=='tampered': (output/'corpus/note.json').write_text('tampered')
    if bad=='missing': (output/'catalog.sqlite3').unlink()
    if bad=='extra': (output/'extra').write_text('unexpected')
    if bad=='traversal':
        manifest=json.loads((output/'backup.json').read_text());manifest['files']['../escape']={'bytes':0,'sha256':'0'*64};(output/'backup.json').write_text(json.dumps(manifest))
    target=tmp_path/'restore'
    with pytest.raises(ValueError): restore(output,target)
    assert not target.exists()


def test_source_symlink_rejected_without_partial_backup(bundle,tmp_path):
    source,corpus,output=bundle
    (corpus/'link').symlink_to(source)
    target=tmp_path/'bad'
    with pytest.raises(ValueError): create(source,corpus,target)
    assert not target.exists()
