"""Account-private bookmarks/notes with optimistic writes and removal replay."""
from contextlib import closing
from datetime import datetime,timezone
import sqlite3
from app.data.catalog import connect
from app.data.contributions import Conflict
from app.data.quotas import consume

class Library:
    def __init__(self,path):self.path=path
    def connection(self):
        db=connect(self.path);db.row_factory=sqlite3.Row;return db
    def list(self,user):
        with closing(self.connection()) as db:
            return [dict(r) for r in db.execute('SELECT artifact_id,notes,version,updated_on FROM saved_artifacts WHERE account_id=? AND deleted=0 ORDER BY updated_on DESC LIMIT 100',(user['id'],))]
    def get(self,user,artifact):
        with closing(self.connection()) as db:
            if not db.execute('SELECT 1 FROM curated_artifacts WHERE id=?',(artifact,)).fetchone():raise KeyError('Artifact not found')
            row=db.execute('SELECT notes,version,updated_on,deleted FROM saved_artifacts WHERE account_id=? AND artifact_id=?',(user['id'],artifact)).fetchone()
            return {'artifact_id':artifact,'notes':row['notes'] if row else '', 'version':row['version'] if row else 0,'saved':bool(row and not row['deleted'])}
    def save(self,user,artifact,notes,version,remove=False):
        with closing(self.connection()) as db,db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM accounts WHERE id=? AND closed_on IS NULL',(user['id'],)).fetchone():raise PermissionError('Account is closed')
            if not db.execute('SELECT 1 FROM curated_artifacts WHERE id=?',(artifact,)).fetchone():raise KeyError('Artifact not found')
            row=db.execute('SELECT version FROM saved_artifacts WHERE account_id=? AND artifact_id=?',(user['id'],artifact)).fetchone()
            if version!=(row['version'] if row else 0):raise Conflict('A newer library change exists. Reload the saved record before editing.')
            if not row and db.execute('SELECT count(*) FROM saved_artifacts WHERE account_id=?',(user['id'],)).fetchone()[0]>=100:raise Conflict('Library limit: 100 artifacts')
            consume(db,user['id'],'library changes',100)
            now=datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO saved_artifacts VALUES (?,?,?,?,?,?) ON CONFLICT(account_id,artifact_id) DO UPDATE SET notes=excluded.notes,version=excluded.version,updated_on=excluded.updated_on,deleted=excluded.deleted',
                (user['id'],artifact,'' if remove else notes,version+1,now,int(remove)))
            if remove:db.execute('INSERT INTO library_deletions VALUES (?,?,?) ON CONFLICT(account_id,artifact_id) DO UPDATE SET removed_on=excluded.removed_on',(user['id'],artifact,now))
            return {'artifact_id':artifact,'notes':'' if remove else notes,'version':version+1,'saved':not remove}
