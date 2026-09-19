"""Verified encrypted backup maintenance for the dedicated AncientLens repository."""
import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from uuid import uuid4
from app.data import backup, retention
from app.data.catalog import connect
from app.data.configure_offdevice import REPOSITORY

TAG = 'ancientlens-catalog-corpus'
PRODUCTION_REPOSITORY = REPOSITORY + '-production'


class Restic:
    def __init__(self, config, executable=None, repository=REPOSITORY):
        path = Path(config)
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Unsafe credential path')
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise ValueError('Credential file must have mode 600')
        data = json.loads(path.read_text())
        if repository not in (REPOSITORY, PRODUCTION_REPOSITORY) or data.get('repository') != repository:
            raise ValueError('Unexpected repository; refusing remote maintenance')
        if not all(isinstance(data.get(k), str) and data[k] for k in ('key_id', 'application_key', 'password')):
            raise ValueError('Incomplete private configuration')
        self.executable = executable or shutil.which('restic')
        if not self.executable:
            raise ValueError('Restic executable unavailable')
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('RESTIC_', 'AWS_'))}
        self.env.update(RESTIC_REPOSITORY=data['repository'], AWS_ACCESS_KEY_ID=data['key_id'],
                        AWS_SECRET_ACCESS_KEY=data['application_key'], RESTIC_PASSWORD=data['password'])

    def __call__(self, args, cwd=None):
        result = subprocess.run([self.executable, *args], cwd=cwd, env=self.env,
                                capture_output=True, text=True, timeout=1800)
        if result.returncode:
            # Provider output can contain authentication material; never forward it.
            raise RuntimeError('Restic %s failed (exit %s)' % (args[0], result.returncode))
        return result.stdout


def inventory(run):
    snapshots = json.loads(run(['snapshots', '--json'])) or []
    for entry in snapshots:
        if not re.fullmatch('[0-9a-f]{64}', entry.get('id', '')) or entry.get('tags') != [TAG]:
            raise ValueError('Unexpected snapshot in dedicated repository; refusing expiry')
    if len({s['id'] for s in snapshots}) != len(snapshots):
        raise ValueError('Duplicate snapshot identifiers')
    return snapshots


def download(run, snapshot, destination):
    run(['restore', snapshot, '--target', str(destination), '--verify'])
    manifests = list(destination.rglob('backup.json'))
    if len(manifests) != 1:
        raise ValueError('Expected exactly one backup manifest')
    bundle = manifests[0].parent
    record = backup.verify(bundle)
    return bundle, record


def download_retention_metadata(run, snapshot, destination):
    """Download only old manifest/catalog for retention, never old corpus media."""
    run(['restore', snapshot, '--target', str(destination), '--verify',
         '--include', '**/backup.json', '--include', '**/catalog.sqlite3'])
    manifests = list(destination.rglob('backup.json'))
    if len(manifests) != 1:
        raise ValueError('Expected exactly one retention manifest')
    bundle = manifests[0].parent
    record = json.loads(manifests[0].read_text())
    if record.get('format') != 1:
        raise ValueError('Unsupported retention manifest')
    catalog = backup.relative_file(bundle, 'catalog.sqlite3')
    expected = record['files']['catalog.sqlite3']
    if catalog.stat().st_size != expected['bytes'] or backup.digest(catalog) != expected['sha256']:
        raise ValueError('Retention catalog checksum mismatch')
    return bundle, record


def expired(record, saved_ledger, current_ledger, now, days):
    created = datetime.fromisoformat(record['created_on'])
    if created.tzinfo is None or created > now:
        raise ValueError('Invalid backup timestamp')
    return created <= now - timedelta(days=days) or not current_ledger[1] <= saved_ledger[1]


def maintain(root, run, days=30):
    if type(days) is not int or days < 1:
        raise ValueError('Retention days must be positive')
    root = Path(root).resolve()
    private = root / '.local/offdevice'
    if private.is_symlink():
        raise ValueError('Unsafe maintenance directory')
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(private, 0o700)
    lock_path = private / 'maintenance.lock'
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _maintain(root, private, run, days)


def _maintain(root, private, run, days):
    inventory(run)  # Reject unknown scope before any upload or expiry.
    current = root / '.local/language-catalog.sqlite3'
    bundle = root / '.local/backups' / ('offdevice-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8])
    created = backup.create(current, root / 'corpus', bundle)
    messages = [json.loads(line) for line in run(['backup', '--json', '--tag', TAG, '.'], cwd=bundle).splitlines()]
    summaries = [m for m in messages if m.get('message_type') == 'summary']
    if len(summaries) != 1:
        raise ValueError('Missing unique upload summary')
    snapshot = summaries[0].get('snapshot_id', '')
    if not re.fullmatch('[0-9a-f]{64}', snapshot):
        raise ValueError('Invalid uploaded snapshot ID')
    run(['check'])  # New full restore below verifies protected file data.
    before = inventory(run)
    if snapshot not in {s['id'] for s in before}:
        raise ValueError('Uploaded snapshot missing')
    wanted = retention.ledger(current)
    removed = []
    with tempfile.TemporaryDirectory(prefix='ancientlens-remote-') as temporary:
        temp = Path(temporary)
        restored, record = download(run, snapshot, temp / 'protected')
        if record != backup.verify(bundle):
            raise ValueError('Downloaded manifest differs from source')
        saved = retention.ledger(restored / 'catalog.sqlite3')
        if not all(a <= b for a, b in zip(wanted, saved)):
            raise ValueError('New backup lacks current removal ledger; retry maintenance')
        backup.restore(restored, temp / 'drill', removals_from=current)
        now = datetime.now(timezone.utc)
        for entry in before:
            if entry['id'] == snapshot:
                continue
            old, old_record = download_retention_metadata(run, entry['id'], temp / 'old')
            if expired(old_record, retention.ledger(old / 'catalog.sqlite3'), wanted, now, days):
                removed.append(entry['id'])
            shutil.rmtree(temp / 'old')
        # Freeze removal writes while confirming coverage and deleting old snapshots.
        with closing(connect(current)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if retention.ledger(current) != wanted:
                raise ValueError('Removal ledger changed; no remote expiry performed')
            if inventory(run) != before:
                raise ValueError('Remote inventory changed; no remote expiry performed')
            for target in removed:
                run(['forget', target])
            run(['prune'])  # Also retries reclamation after an interrupted previous run.
            run(['check'])
            remaining = {s['id'] for s in inventory(run)}
            if snapshot not in remaining or remaining.intersection(removed):
                raise ValueError('Unexpected inventory after remote expiry')
    preview = retention.plan(root / '.local/backups', current, days)
    local = retention.apply(root / '.local/backups', current, preview['plan_hash'], days)
    result = {'status': 'verified', 'verified_at': datetime.now(timezone.utc).isoformat(),
              'snapshot_id': snapshot, 'bundle': created, 'downloaded_restore_verified': True,
              'remote_deleted': removed, 'retention_days': days, 'local_retention': local,
              'verification_policy': 'full-new-restore; metadata-only-old-retention; repository-structure-check',
              'provider_version_expiry': 'Backblaze lifecycle is asynchronous; not all-copy erasure proof'}
    receipt = private / ('maintenance-' + uuid4().hex + '.json')
    with os.fdopen(os.open(receipt, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as output:
        json.dump(result, output, indent=2)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3],
                        help='Persistent data root containing .local/language-catalog.sqlite3 and corpus')
    parser.add_argument('--restic', help='Restic executable (otherwise resolved on PATH)')
    parser.add_argument('--production', action='store_true', help='Require the separate production repository')
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        current = root / '.local/language-catalog.sqlite3'
        configured = os.environ.get('ANCIENTLENS_CATALOG_PATH')
        if configured and Path(configured).resolve() != current:
            raise ValueError('Backup root does not match the configured service catalog')
        if not current.is_file() or not (root / 'corpus').is_dir():
            raise ValueError('Existing catalog and corpus required')
        repository = PRODUCTION_REPOSITORY if args.production else REPOSITORY
        result = maintain(root, Restic(root / '.local/offdevice/credentials.json',
                                      args.restic, repository=repository), args.days)
    except Exception as error:
        # Never expose unexpected exception text, provider output or secret-bearing values.
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__,
                          'action': 'Inspect backup configuration, connectivity and verified receipts; do not delete snapshots manually.'}))
        raise SystemExit(1)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
