"""Immediate withdrawal/closure with durable pending erasure requests, not completed deletion."""
from contextlib import closing
from datetime import datetime, timezone
import secrets
import sqlite3
from app.data.catalog import connect
from app.data.accounts import password_hash


def close_account(db, account_id, now):
    # Keep identity/history for the pending erasure review; destroy live credentials.
    db.execute("UPDATE accounts SET closed_on=COALESCE(closed_on,?),password_hash=?,role='contributor' WHERE id=?",
               (now,password_hash(secrets.token_urlsafe(48)),account_id))
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='saved_artifacts'").fetchone():
        db.execute('DELETE FROM saved_artifacts WHERE account_id=?',(account_id,))
    db.execute('DELETE FROM sessions WHERE account_id=?',(account_id,))
    db.execute('DELETE FROM recovery_codes WHERE account_id=?',(account_id,))
    db.execute('DELETE FROM write_quotas WHERE account_id=?',(account_id,))


class Removals:
    def __init__(self,path): self.path=path

    def request(self,user,contribution_id=None,credential_version=None):
        now=datetime.now(timezone.utc).isoformat()
        with closing(connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            account=db.execute('SELECT password_hash,closed_on FROM accounts WHERE id=?',(user['id'],)).fetchone()
            if not account or account[1]: raise PermissionError('Account is closed')
            if contribution_id is not None:
                owner=db.execute('SELECT owner_id FROM contributions WHERE id=?',(contribution_id,)).fetchone()
                if not owner or owner[0]!=user['id']: raise PermissionError('Only the owner can withdraw this contribution')
                kind,target='contribution',contribution_id
            else:
                if not credential_version or credential_version!=account[0]: raise PermissionError('Password changed; sign in again')
                kind,target='account',user['id']
            db.execute('INSERT OR IGNORE INTO removal_requests(kind,target_id,requested_by,created_on) VALUES (?,?,?,?)',(kind,target,user['id'],now))
            if kind=='account': close_account(db,target,now)
            return {'status':'removal_requested','kind':kind,'public_visibility':'withdrawn','erasure_complete':False}

    def list(self,user,after=0):
        if user['role']!='moderator': raise PermissionError('Moderator access required')
        with closing(connect(self.path)) as db:
            db.row_factory=sqlite3.Row
            return [dict(row) for row in db.execute('SELECT r.id,r.kind,r.target_id,r.created_on,e.catalog_purged_on FROM removal_requests r LEFT JOIN erasure_events e ON e.request_id=r.id WHERE r.id>? ORDER BY r.id LIMIT 20',(after,))]


def reconcile(source, destination):
    """Apply a trusted, newer catalog's withdrawal ledger to an isolated v7 restore."""
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src:
        src.execute('BEGIN')
        rows=src.execute('SELECT kind,target_id,requested_by,created_on FROM removal_requests ORDER BY id').fetchall()
        has_erasure=src.execute("SELECT 1 FROM sqlite_master WHERE name='erasure_events'").fetchone()
        erased=set(src.execute('SELECT r.kind,r.target_id FROM removal_requests r JOIN erasure_events e ON e.request_id=r.id')) if has_erasure else set()
        has_library=src.execute("SELECT 1 FROM sqlite_master WHERE name='library_deletions'").fetchone()
        library_rows=src.execute('SELECT account_id,artifact_id,removed_on FROM library_deletions').fetchall() if has_library else []
    applied=0
    with closing(connect(destination)) as db, db:
        db.execute('PRAGMA secure_delete=ON')
        db.execute('BEGIN IMMEDIATE')
        for kind,target,actor,created in rows:
            if not db.execute('SELECT 1 FROM accounts WHERE id=?',(actor,)).fetchone(): continue
            db.execute('INSERT OR IGNORE INTO removal_requests(kind,target_id,requested_by,created_on) VALUES (?,?,?,?)',(kind,target,actor,created))
            if kind=='account': close_account(db,target,created)
            if (kind,target) in erased:
                from app.data.erasure import purge_in_transaction
                request_id=db.execute('SELECT id FROM removal_requests WHERE kind=? AND target_id=?',(kind,target)).fetchone()[0]
                # Already-purged snapshots must not retain a newly generated credential hash.
                if kind=='account': db.execute("UPDATE accounts SET password_hash='' WHERE id=?",(target,))
                purge_in_transaction(db,request_id)
            applied+=1
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='saved_artifacts'").fetchone():
            for account,artifact,removed in library_rows:
                if not db.execute('SELECT 1 FROM accounts WHERE id=?',(account,)).fetchone():continue
                db.execute("UPDATE saved_artifacts SET notes='',deleted=1,version=version+1 WHERE account_id=? AND artifact_id=? AND updated_on<=?",(account,artifact,removed))
                db.execute('INSERT INTO library_deletions VALUES (?,?,?) ON CONFLICT(account_id,artifact_id) DO UPDATE SET removed_on=max(removed_on,excluded.removed_on)',(account,artifact,removed))
    return applied
