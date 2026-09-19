"""Private local catalog/corpus backups and non-overwriting restore drills."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def relative_file(root,name):
    if not isinstance(name, str):
        raise ValueError('Unsafe backup path')
    part = PurePosixPath(name)
    if part.is_absolute() or '..' in part.parts or not part.parts or part.as_posix() != name:
        raise ValueError('Unsafe backup path')
    candidate = root
    for piece in part.parts:
        candidate = candidate / piece
        if candidate.is_symlink():
            raise ValueError('Symlinks are not backup files')
    if not candidate.is_file(): raise ValueError('Backup file missing')
    return candidate


def sqlite_version(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        return db.execute('SELECT version FROM catalog_version').fetchone()[0]


def inspect_database(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]: raise ValueError('Database integrity failure')
        if db.execute('PRAGMA foreign_key_check').fetchall(): raise ValueError('Foreign key failure')
        version=db.execute('SELECT version FROM catalog_version').fetchall()
        if version not in ([(5,)], [(6,)], [(7,)], [(8,)], [(9,)]): raise ValueError('Backup tool expects catalog version 5, 6, 7, 8 or 9')
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t:db.execute('SELECT count(*) FROM "'+t.replace('"','""')+'"').fetchone()[0] for t in tables}


def validate_media(database,corpus):
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as db:
        for row in db.execute('SELECT original_path,original_sha256,normalized_path,normalized_sha256 FROM media_records'):
            for name,sha in ((row[0],row[1]),(row[2],row[3])):
                if digest(relative_file(corpus,name))!=sha: raise ValueError('Catalog media checksum mismatch')
    manifest=corpus/'manifest.json'
    if manifest.exists():
        for sample in json.loads(manifest.read_text())['samples']:
            for path_key,sha_key in [('image_path','sha256'),('original_path','original_sha256')]:
                if digest(relative_file(corpus,sample[path_key]))!=sample[sha_key]: raise ValueError('Corpus manifest checksum mismatch')


def private_copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with source.open('rb') as src, target.open('xb') as dst:
        os.chmod(target,0o600)
        shutil.copyfileobj(src,dst)


def verify(bundle):
    bundle=Path(bundle).resolve()
    record=json.loads(relative_file(bundle,'backup.json').read_text())
    if record.get('format')!=1 or not isinstance(record.get('files'),dict): raise ValueError('Unsupported backup manifest')
    if 'catalog.sqlite3' not in record['files']: raise ValueError('Catalog missing from manifest')
    for name,item in record['files'].items():
        file=relative_file(bundle,name)
        if file.stat().st_size!=item['bytes'] or digest(file)!=item['sha256']: raise ValueError('Backup checksum mismatch')
    actual={p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}
    if actual!=set(record['files'])|{'backup.json'}: raise ValueError('Unexpected backup contents')
    if any(p.is_symlink() for p in bundle.rglob('*')): raise ValueError('Symlinks are not backup files')
    counts=inspect_database(bundle/'catalog.sqlite3')
    if counts!=record['table_counts']: raise ValueError('Backup row counts disagree')
    validate_media(bundle/'catalog.sqlite3',bundle/'corpus')
    return record


def create(database,corpus,destination):
    database=Path(database).resolve();corpus=Path(corpus).resolve();destination=Path(destination).absolute()
    if not database.is_file() or not corpus.is_dir(): raise ValueError('Database and corpus must exist')
    if destination.resolve()==corpus or corpus in destination.resolve().parents: raise ValueError('Backup cannot be inside corpus')
    destination.mkdir(parents=True,exist_ok=False,mode=0o700)
    try:
        snapshot=destination/'catalog.sqlite3'
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as src, closing(sqlite3.connect(snapshot)) as dst: src.backup(dst)
        os.chmod(snapshot,0o600)
        for source in sorted(corpus.rglob('*')):
            if source.is_symlink(): raise ValueError('Corpus symlinks are not allowed')
            if source.is_file(): private_copy(source,destination/'corpus'/source.relative_to(corpus))
        counts=inspect_database(snapshot.resolve())
        validate_media(snapshot.resolve(),destination/'corpus')
        files={p.relative_to(destination).as_posix():{'sha256':digest(p),'bytes':p.stat().st_size} for p in destination.rglob('*') if p.is_file()}
        record={'format':1,'created_on':datetime.now(timezone.utc).isoformat(),'private':True,'catalog_version':sqlite_version(snapshot),'table_counts':counts,'files':files}
        manifest=destination/'backup.json'
        with manifest.open('x') as f:
            os.chmod(manifest,0o600);json.dump(record,f,indent=2);f.write('\n')
        verify(destination)
        return {'status':'verified','files':len(files),'bytes':sum(i['bytes'] for i in files.values())}
    except Exception:
        shutil.rmtree(destination)
        raise


def restore(bundle,destination,removals_from=None):
    bundle=Path(bundle).resolve();destination=Path(destination).absolute()
    record=verify(bundle)
    if destination.resolve()==bundle or bundle in destination.resolve().parents: raise ValueError('Restore cannot be inside backup')
    destination.mkdir(parents=True,exist_ok=False,mode=0o700)
    try:
        for name,item in record['files'].items():
            private_copy(relative_file(bundle,name),destination/name)
            if digest(destination/name)!=item['sha256']: raise ValueError('Restore copy checksum mismatch')
        db_path=(destination/'catalog.sqlite3').resolve()
        # Never reactivate authentication sessions from a historical snapshot.
        with closing(sqlite3.connect(db_path)) as db, db:
            sessions=db.execute('SELECT count(*) FROM sessions').fetchone()[0]
            db.execute('DELETE FROM sessions')
        counts=inspect_database(db_path)
        expected={**record['table_counts'],'sessions':0}
        if counts!=expected: raise ValueError('Restore row count mismatch')
        validate_media(db_path,destination/'corpus')
        reconciled=None
        if removals_from is not None:
            from app.data.catalog import initialize
            from app.data.removals import reconcile
            initialize(db_path)
            reconciled=reconcile(Path(removals_from).resolve(),db_path)
            counts=inspect_database(db_path)
        result={'removal_requests_reconciled':reconciled,'requires_removal_reconciliation':removals_from is None,'status':'restore_verified','files':len(record['files']),'sessions_revoked':sessions,'table_counts':counts}
        receipt=destination/'restore-check.json'
        with receipt.open('x') as f:
            os.chmod(receipt,0o600);json.dump(result,f,indent=2);f.write('\n')
        return result
    except Exception:
        shutil.rmtree(destination)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    backup=commands.add_parser('create');backup.add_argument('--database',type=Path,required=True);backup.add_argument('--corpus',type=Path,required=True);backup.add_argument('--destination',type=Path,required=True)
    check=commands.add_parser('verify');check.add_argument('--bundle',type=Path,required=True)
    recover=commands.add_parser('restore');recover.add_argument('--bundle',type=Path,required=True);recover.add_argument('--destination',type=Path,required=True)
    recover.add_argument('--removals-from',type=Path,help='Trusted current v7/v8 catalog with later withdrawal/closure requests')
    args=parser.parse_args()
    if args.command=='create': result=create(args.database,args.corpus,args.destination)
    elif args.command=='restore': result=restore(args.bundle,args.destination,args.removals_from)
    else:
        record=verify(args.bundle);result={'status':'verified','files':len(record['files'])}
    print(json.dumps(result,indent=2))
