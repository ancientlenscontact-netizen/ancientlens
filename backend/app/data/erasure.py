"""Preview-first operator catalog purge. No HTTP deletion endpoint or backup deletion."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from app.data.catalog import connect

TRIGGERS = ('revisions_no_update','revisions_no_delete','moderation_no_update','moderation_no_delete',
            'reports_no_update','reports_no_delete','resolutions_no_update','resolutions_no_delete')
TABLES = ('accounts','contributions','contribution_revisions','moderation_events','reports',
          'report_resolutions','removal_requests','erasure_events')


def plan(db, request_id):
    row=db.execute('SELECT kind,target_id FROM removal_requests WHERE id=?',(request_id,)).fetchone()
    if not row: raise ValueError('Removal request not found')
    kind,target=row
    completed=bool(db.execute('SELECT 1 FROM erasure_events WHERE request_id=?',(request_id,)).fetchone())
    ids=[r[0] for r in db.execute('SELECT id FROM contributions WHERE '+('owner_id=?' if kind=='account' else 'id=?'),(target,))]
    counts={'contributions':len(ids),'revisions':0,'reports':0,'moderation_events':0}
    for id in ids:
        for table,key in [('contribution_revisions','revisions'),('reports','reports'),('moderation_events','moderation_events')]:
            counts[key]+=db.execute(f'SELECT count(*) FROM {table} WHERE contribution_id=?',(id,)).fetchone()[0]
    if kind=='account':
        for table,column,key in [('reports','reporter_id','authored_reports'),('moderation_events','actor_id','authored_moderation_notes'),('report_resolutions','actor_id','authored_resolution_notes')]:
            counts[key]=db.execute(f'SELECT count(*) FROM {table} WHERE {column}=?',(target,)).fetchone()[0]
    result={'request_id':request_id,'kind':kind,'target_id':target,'already_purged':completed,'scope':'catalog_only','counts':counts}
    # Hash values as well as counts so changes since preview invalidate approval.
    h=hashlib.sha256(json.dumps(result,sort_keys=True).encode())
    for table in TABLES:
        h.update(table.encode())
        for row in db.execute(f'SELECT * FROM {table} ORDER BY rowid'):
            h.update(json.dumps(tuple(row),ensure_ascii=True).encode());h.update(b'\n')
    result['plan_hash']=h.hexdigest()
    return result


def purge_in_transaction(db,request_id):
    """Caller holds a transaction. Trigger changes, deletion and audit are atomic."""
    info=plan(db,request_id)
    if info['already_purged']: return info
    kind,target=info['kind'],info['target_id']
    ids=[r[0] for r in db.execute('SELECT id FROM contributions WHERE '+('owner_id=?' if kind=='account' else 'id=?'),(target,))]
    triggers=[]
    for name in TRIGGERS:
        row=db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()
        if not row: raise ValueError('Required immutability trigger missing')
        triggers.append((name,row[0]))
    for name,_ in triggers: db.execute('DROP TRIGGER '+name)
    for id in ids:
        db.execute('DELETE FROM report_resolutions WHERE report_id IN (SELECT id FROM reports WHERE contribution_id=?)',(id,))
        for table in ('reports','moderation_events','contribution_revisions'):
            db.execute(f'DELETE FROM {table} WHERE contribution_id=?',(id,))
        db.execute('DELETE FROM contributions WHERE id=?',(id,))
    now=datetime.now(timezone.utc).isoformat()
    if kind=='account':
        db.execute('DELETE FROM report_resolutions WHERE report_id IN (SELECT id FROM reports WHERE reporter_id=?)',(target,))
        db.execute('DELETE FROM reports WHERE reporter_id=?',(target,))
        # Keep decisions on other authors intact; redact free-text notes by this account.
        db.execute("UPDATE moderation_events SET reason='[Removed during account erasure]' WHERE actor_id=?",(target,))
        db.execute("UPDATE report_resolutions SET reason='[Removed during account erasure]' WHERE actor_id=?",(target,))
        for table in ('sessions','recovery_codes','write_quotas','saved_artifacts'):
            if db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(table,)).fetchone():
                db.execute(f'DELETE FROM {table} WHERE account_id=?',(target,))
        row=db.execute('SELECT username FROM accounts WHERE id=?',(target,)).fetchone()
        if row:
            bucket=hashlib.sha256(('account:'+row[0]).encode()).hexdigest()
            db.execute('DELETE FROM auth_attempts WHERE bucket=?',(bucket,))
        # Closed UUID skeleton is retained for FK integrity and anti-resurrection audit.
        db.execute("UPDATE accounts SET username=?,password_hash='',role='contributor',created_on=?,closed_on=? WHERE id=?",
                   ('removed:'+target,now,now,target))
    for _,sql in triggers: db.execute(sql)
    db.execute("INSERT INTO erasure_events VALUES (?,?,'catalog_only')",(request_id,now))
    if db.execute('PRAGMA foreign_key_check').fetchall(): raise ValueError('Erasure foreign key check failed')
    return {**info,'catalog_purged':True,'backups_erased':False}


def run(path,request_id,expected_hash=None):
    if not Path(path).is_file(): raise ValueError('Database not found')
    with closing(connect(path)) as db,db:
        db.execute('PRAGMA secure_delete=ON')
        db.execute('BEGIN IMMEDIATE')
        info=plan(db,request_id)
        if expected_hash is None: return info
        if expected_hash!=info['plan_hash']: raise ValueError('Plan changed; preview again before applying')
        return purge_in_transaction(db,request_id)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--request-id',type=int,required=True)
    parser.add_argument('--apply-plan',help='Exact plan_hash from a reviewed preview; omit for preview only')
    args=parser.parse_args()
    print(json.dumps(run(args.database,args.request_id,args.apply_plan),indent=2))
