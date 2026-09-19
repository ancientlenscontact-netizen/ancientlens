from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import pytest
from app.data import offdevice
from app.data.catalog import initialize

class Repository:
    def __init__(self, storage):
        self.storage, self.fail, self.calls, self.snapshots = storage, None, [], []
    def __call__(self, args, cwd=None):
        self.calls.append(args)
        if self.fail == args[0]: raise RuntimeError('Fixture failure')
        if args[0] == 'snapshots': return json.dumps(self.snapshots)
        if args[0] == 'backup':
            identifier = str(len(self.snapshots) + 1) * 64
            shutil.copytree(cwd, self.storage / identifier)
            self.snapshots.append({'id': identifier, 'tags': [offdevice.TAG]})
            return json.dumps({'message_type': 'summary', 'snapshot_id': identifier})
        if args[0] == 'restore':
            target = Path(args[args.index('--target') + 1]) / 'bundle'
            shutil.copytree(self.storage / args[1], target)
            if '--include' in args:
                shutil.rmtree(target / 'corpus')
            if self.fail == 'corrupt': (target / 'corpus/note').write_text('corrupt')
        if args[0] == 'forget': self.snapshots = [s for s in self.snapshots if s['id'] != args[1]]
        return ''

@pytest.fixture
def setup(tmp_path):
    root = tmp_path / 'project'
    (root / '.local').mkdir(parents=True)
    initialize(root / '.local/language-catalog.sqlite3')
    (root / 'corpus').mkdir()
    (root / 'corpus/note').write_text('Fixture corpus')
    storage = tmp_path / 'remote'; storage.mkdir()
    return root, Repository(storage)

def test_roundtrip_expiry_preserves_new_recovery(setup):
    root, run = setup
    first = offdevice.maintain(root, run)
    old = run.storage / first['snapshot_id'] / 'backup.json'
    record = json.loads(old.read_text()); record['created_on'] = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    old.write_text(json.dumps(record))
    result = offdevice.maintain(root, run)
    assert result['remote_deleted'] == [first['snapshot_id']]
    assert [s['id'] for s in run.snapshots] == [result['snapshot_id']]
    assert result['downloaded_restore_verified']
    assert any(c[0] == 'prune' for c in run.calls)

@pytest.mark.parametrize('failure', ['check', 'restore', 'corrupt'])
def test_failed_verification_never_expires(setup, failure):
    root, run = setup
    offdevice.maintain(root, run); run.calls.clear(); run.fail = failure
    with pytest.raises((RuntimeError, ValueError)): offdevice.maintain(root, run)
    assert not any(c[0] in ('forget', 'prune') for c in run.calls)
    assert len(run.snapshots) == 2

def test_unknown_snapshot_refuses_upload(setup):
    root, run = setup; run.snapshots = [{'id': 'a' * 64, 'tags': ['unrelated']}]
    with pytest.raises(ValueError): offdevice.maintain(root, run)
    assert not any(c[0] == 'backup' for c in run.calls)

def test_erasure_overrides_age_and_future_refused():
    now = datetime.now(timezone.utc); record = {'created_on': now.isoformat()}
    assert offdevice.expired(record, (set(), set()), (set(), {('account', 'id')}), now, 30)
    assert not offdevice.expired(record, (set(), set()), (set(), set()), now, 30)
    with pytest.raises(ValueError):
        offdevice.expired({'created_on': (now + timedelta(days=1)).isoformat()}, (set(), set()), (set(), set()), now, 30)

def test_secret_output_is_not_forwarded(tmp_path, monkeypatch):
    from types import SimpleNamespace
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'repository': offdevice.REPOSITORY, 'key_id': 'fixture', 'application_key': 'fixture', 'password': 'fixture'})); config.chmod(0o600)
    monkeypatch.setattr(offdevice.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=12, stdout='secret', stderr='secret'))
    with pytest.raises(RuntimeError, match='exit 12') as error: offdevice.Restic(config)(['snapshots'])
    assert 'secret' not in str(error.value)


def test_repository_scope_and_executable(tmp_path, monkeypatch):
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'repository': offdevice.PRODUCTION_REPOSITORY,
        'key_id': 'fixture', 'application_key': 'fixture', 'password': 'fixture'}))
    config.chmod(0o600)
    monkeypatch.setattr(offdevice.shutil, 'which', lambda name: '/usr/bin/restic')
    with pytest.raises(ValueError, match='Unexpected repository'):
        offdevice.Restic(config)
    production = offdevice.Restic(config, repository=offdevice.PRODUCTION_REPOSITORY)
    assert production.executable == '/usr/bin/restic'
    assert production.env['RESTIC_REPOSITORY'] == offdevice.PRODUCTION_REPOSITORY
    with pytest.raises(ValueError, match='Unexpected repository'):
        offdevice.Restic(config, repository='unapproved')


def test_cli_rejects_wrong_catalog_before_remote_call(tmp_path, monkeypatch, capsys):
    import sys
    monkeypatch.setattr(sys, 'argv', ['offdevice', '--root', str(tmp_path)])
    monkeypatch.setenv('ANCIENTLENS_CATALOG_PATH', str(tmp_path / 'elsewhere.sqlite3'))
    monkeypatch.setattr(offdevice, 'Restic', lambda *a, **k: pytest.fail('must not contact remote'))
    with pytest.raises(SystemExit):
        offdevice.main()
    assert json.loads(capsys.readouterr().out)['status'] == 'failed'


def test_only_new_snapshot_downloads_full_corpus(setup):
    root, run = setup
    first = offdevice.maintain(root, run)
    run.calls.clear()
    second = offdevice.maintain(root, run)
    restores = [c for c in run.calls if c[0] == 'restore']
    assert len(restores) == 2
    assert '--include' not in next(c for c in restores if c[1] == second['snapshot_id'])
    old = next(c for c in restores if c[1] == first['snapshot_id'])
    assert old.count('--include') == 2
    assert '**/catalog.sqlite3' in old and '**/backup.json' in old
    assert not any('--read-data' in c for c in run.calls)
    assert second['downloaded_restore_verified']


def test_corrupt_old_catalog_refuses_expiry(setup):
    root, run = setup
    first = offdevice.maintain(root, run)
    (run.storage / first['snapshot_id'] / 'catalog.sqlite3').write_bytes(b'corrupt')
    run.calls.clear()
    with pytest.raises(ValueError, match='checksum'):
        offdevice.maintain(root, run)
    assert not any(c[0] in ('forget', 'prune') for c in run.calls)


def test_real_restic_retention_download_excludes_corpus(tmp_path):
    """Exercise actual include matching and two complete maintenance runs offline."""
    import os
    import subprocess
    executable = shutil.which('restic')
    if not executable:
        pytest.skip('restic executable not installed')
    root = tmp_path / 'project'
    (root / '.local').mkdir(parents=True)
    initialize(root / '.local/language-catalog.sqlite3')
    (root / 'corpus/nested').mkdir(parents=True)
    (root / 'corpus/nested/fixture.bin').write_bytes(os.urandom(128 * 1024))
    env = {k: v for k, v in os.environ.items() if not k.startswith(('RESTIC_', 'AWS_'))}
    env.update(RESTIC_REPOSITORY=str(tmp_path / 'repository'),
               RESTIC_PASSWORD='disposable-local-test-only')
    def run(args, cwd=None):
        return subprocess.run([executable, '--no-cache', *args], cwd=cwd, env=env,
                              capture_output=True, text=True, check=True, timeout=120).stdout
    run(['init'])
    first = offdevice.maintain(root, run)
    destination = tmp_path / 'metadata'
    bundle, manifest = offdevice.download_retention_metadata(run, first['snapshot_id'], destination)
    assert {p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()} == {'backup.json', 'catalog.sqlite3'}
    assert manifest['format'] == 1
    second = offdevice.maintain(root, run)
    assert second['downloaded_restore_verified']
    assert second['remote_deleted'] == []
    assert len(offdevice.inventory(run)) == 2
