from contextlib import closing
from datetime import datetime, timezone
import sqlite3
from app.data.catalog import connect
from app.data.contributions import Conflict
from app.data.quotas import consume

class Reports:
    def __init__(self,path): self.path=path

    def submit(self,id,revision,reason,user):
        with closing(connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("""SELECT c.owner_id,r.terms_version,r.rights_basis,r.reuse_terms,
                (SELECT action FROM moderation_events e WHERE e.contribution_id=c.id AND e.revision=r.revision ORDER BY e.id DESC LIMIT 1)
                FROM contributions c JOIN contribution_revisions r ON r.contribution_id=c.id
                WHERE c.id=? AND r.revision=? AND r.revision=(SELECT max(revision) FROM contribution_revisions WHERE contribution_id=c.id)""",(id,revision)).fetchone()
            if not row or not (row[0]==user['id'] or user['role']=='moderator' or (row[1]=='2026-09-16.1' and row[2]=='original_work' and row[3]=='CC BY-SA 4.0' and row[4]=='allowed' and not db.execute("SELECT 1 FROM removal_requests w JOIN contributions c ON c.id=? WHERE (w.kind='contribution' AND w.target_id=c.id) OR (w.kind='account' AND w.target_id=c.owner_id)",(id,)).fetchone())):
                raise KeyError('Visible current revision not found')
            consume(db,user['id'],'reports',10)
            try:
                cursor=db.execute('INSERT INTO reports(contribution_id,revision,reporter_id,reason,created_on) VALUES (?,?,?,?,?)',
                    (id,revision,user['id'],reason,datetime.now(timezone.utc).isoformat()))
            except sqlite3.IntegrityError: raise Conflict('You already reported this revision')
            return {'id':cursor.lastrowid,'status':'open'}

    def list(self,user,after=0):
        if user['role']!='moderator': raise PermissionError('Moderator access required')
        with closing(connect(self.path)) as db:
            db.row_factory=sqlite3.Row
            return [dict(row) for row in db.execute("""SELECT r.id,r.contribution_id,r.revision,r.reason,r.created_on,
                c.passage_id,p.designation,a.username AS reporter,t.translation,t.author
                FROM reports r JOIN contributions c ON c.id=r.contribution_id JOIN passage_records p ON p.id=c.passage_id
                JOIN accounts a ON a.id=r.reporter_id JOIN contribution_revisions t ON t.contribution_id=r.contribution_id AND t.revision=r.revision
                WHERE r.id>? AND NOT EXISTS(SELECT 1 FROM report_resolutions z WHERE z.report_id=r.id)
                ORDER BY r.id LIMIT 20""",(after,))]

    def resolve(self,id,outcome,reason,user):
        if user['role']!='moderator': raise PermissionError('Moderator access required')
        with closing(connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM reports WHERE id=?',(id,)).fetchone(): raise KeyError('Report not found')
            if db.execute('SELECT 1 FROM report_resolutions WHERE report_id=?',(id,)).fetchone(): raise Conflict('Report already resolved')
            consume(db,user['id'],'report resolutions',100)
            db.execute('INSERT INTO report_resolutions VALUES (?,?,?,?,?)',(id,user['id'],outcome,reason,datetime.now(timezone.utc).isoformat()))
            return {'status':'resolved','outcome':outcome}
