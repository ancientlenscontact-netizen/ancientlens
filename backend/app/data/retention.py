"""Preview-first expiry of verified managed backup bundles; never scans arbitrary directories."""
import argparse
from contextlib import closing
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from uuid import uuid4
from app.data.backup import verify,digest,restore,create
from app.data.catalog import connect


def ledger(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('BEGIN')
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        requests=set(db.execute('SELECT kind,target_id FROM removal_requests')) if 'removal_requests' in tables else set()
        erased=set(db.execute('SELECT r.kind,r.target_id FROM removal_requests r JOIN erasure_events e ON e.request_id=r.id')) if 'erasure_events' in tables else set()
        return requests,erased


def plan(root,current,days=30,now=None):
    root=Path(root);current=Path(current).resolve()
    if root.is_symlink() or not root.is_dir(): raise ValueError('Managed backup root must be an existing real directory')
    root=root.resolve()
    if root==current.parent or root in current.parents: raise ValueError('Live catalog must be outside the backup root')
    if not isinstance(days,int) or isinstance(days,bool) or days<1: raise ValueError('Retention days must be positive')
    now=now or datetime.now(timezone.utc)
    wanted,purged=ledger(current)
    entries=[]
    for folder in sorted(root.iterdir()):
        if folder.is_symlink() or not folder.is_dir(): raise ValueError('Unexpected item in managed backup root')
        record=verify(folder)
        created=datetime.fromisoformat(record['created_on'])
        if created.tzinfo is None or created>now: raise ValueError('Invalid/future backup timestamp')
        requests,erased=ledger(folder/'catalog.sqlite3')
        entries.append({'name':folder.name,'created_on':record['created_on'],'manifest_sha256':digest(folder/'backup.json'),
                        'bytes':sum(x['bytes'] for x in record['files'].values()),
                        'ledger_current':wanted<=requests and purged<=erased,
                        'predates_erasure':not purged<=erased})
    if not entries: raise ValueError('No verified backup to preserve')
    newest=max(entries,key=lambda x:(datetime.fromisoformat(x['created_on']),x['name']))
    if not newest['ledger_current']: raise ValueError('Create a fresh backup containing the current removal/erasure ledger first')
    cutoff=now-timedelta(days=days)
    if datetime.fromisoformat(newest['created_on'])<=cutoff: raise ValueError('Create a fresh recovery backup before expiring old copies')
    for entry in entries:
        expired=datetime.fromisoformat(entry['created_on'])<=cutoff
        entry['action']='delete' if entry is not newest and (expired or entry['predates_erasure']) else 'keep'
        entry['reason']='predates completed erasure' if entry['predates_erasure'] else 'age limit' if expired else 'within retention'
        if entry is newest: entry['reason']='protected newest recovery copy'
    result={'root':str(root),'current_catalog':str(current),'retention_days':days,'protected':newest['name'],'bundles':entries,
            'ledger_fingerprint':hashlib.sha256(json.dumps([sorted(wanted),sorted(purged)]).encode()).hexdigest()}
    result['plan_hash']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result


def apply(root,current,expected_hash,days=30,now=None):
    # Prevent concurrent removals/erasures while checking ledger coverage and expiring copies.
    with closing(connect(current)) as db,db:
        db.execute('BEGIN IMMEDIATE')
        preview=plan(root,current,days,now)
        if preview['plan_hash']!=expected_hash: raise ValueError('Retention plan changed; preview again')
        root=Path(preview['root'])
        # A checksum alone is insufficient: prove the protected copy can actually restore.
        with tempfile.TemporaryDirectory(prefix='ancientlens-retention-') as temporary:
            restore(root/preview['protected'],Path(temporary)/'restore',removals_from=current)
        removed=[]
        for item in preview['bundles']:
            if item['action']=='delete':
                folder=root/item['name']
                if folder.is_symlink() or folder.resolve().parent!=root: raise ValueError('Backup path changed')
                verify(folder)
                if digest(folder/'backup.json')!=item['manifest_sha256']: raise ValueError('Backup changed during expiry')
                shutil.rmtree(folder)
                removed.append(item['name'])
        return {'status':'managed_expiry_complete','deleted':removed,'protected':preview['protected'],
                'protected_restore_verified':True,'scope':str(root),'off_device_verified':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--current-catalog',type=Path,required=True)
    p.add_argument('--days',type=int,default=30);p.add_argument('--apply-plan')
    p.add_argument('--maintain',action='store_true',help='Create a fresh backup, verify restore, then apply retention')
    p.add_argument('--corpus',type=Path)
    args=p.parse_args()
    if args.maintain:
        if args.apply_plan or args.corpus is None: p.error('--maintain requires --corpus and cannot use --apply-plan')
        destination=args.root/('maintenance-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8])
        create(args.current_catalog,args.corpus,destination)
        preview=plan(args.root,args.current_catalog,args.days)
        result=apply(args.root,args.current_catalog,preview['plan_hash'],args.days)
    else:
        result=apply(args.root,args.current_catalog,args.apply_plan,args.days) if args.apply_plan else plan(args.root,args.current_catalog,args.days)
    print(json.dumps(result,indent=2))
