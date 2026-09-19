"""Local draft storage. No account identity, rights approval or scholarly review is inferred."""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, StringConstraints, Field, model_validator
from app.data.catalog import connect, initialize
from app.data.quotas import consume

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Evidence = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]

class Draft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    author: ShortText
    translation_language: ShortText
    translation: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]
    source: Evidence
    reuse_terms: Evidence
    rights_basis: Literal['original_work', 'permission_supported']
    rights_evidence: Evidence
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] = ''
    ai_assisted: bool
    terms_version: Literal['2026-09-16.1']
    terms_accepted: bool = Field(strict=True)

    @model_validator(mode='after')
    def acceptance(self):
        if not self.terms_accepted:
            raise ValueError('Accept contributor terms for this revision')
        if self.rights_basis == 'original_work' and self.reuse_terms != 'CC BY-SA 4.0':
            raise ValueError('Original contributions require CC BY-SA 4.0')
        return self


class NewDraft(Draft):
    passage_id: ShortText

class Revision(Draft):
    base_revision: int = Field(ge=1, strict=True)

class Conflict(Exception):
    pass

class Contributions:
    def __init__(self, path):
        self.path = path
        initialize(path)

    def connection(self):
        db = connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def passages(self):
        with closing(self.connection()) as db:
            rows = db.execute("""SELECT p.id, p.designation, p.locator, p.review_status, p.note,
                m.name AS monument, m.site, m.country, s.title AS source_title, s.url AS source_url,
                (SELECT count(*) FROM passage_image_links l WHERE l.passage_id=p.id AND l.status='reviewed') AS reviewed_image_links
                FROM passage_records p JOIN monuments m ON p.monument_id=m.id
                JOIN sources s ON p.source_id=s.id ORDER BY m.name, p.designation LIMIT 200""").fetchall()
            return [dict(row) for row in rows]

    def list(self, passage_id, user=None, limit=10, offset=0):
        with closing(self.connection()) as db:
            db.execute('BEGIN')  # One read snapshot for visibility, revisions and audit history.
            # Filter visibility before paging identities; each page includes bounded history.
            ids=[row[0] for row in db.execute("""SELECT c.id FROM contributions c
                JOIN contribution_revisions r ON r.contribution_id=c.id
                AND r.revision=(SELECT max(revision) FROM contribution_revisions WHERE contribution_id=c.id)
                WHERE c.passage_id=? AND (? OR c.owner_id=? OR (NOT EXISTS(SELECT 1 FROM removal_requests w WHERE (w.kind='contribution' AND w.target_id=c.id) OR (w.kind='account' AND w.target_id=c.owner_id)) AND r.terms_version='2026-09-16.1' AND r.rights_basis='original_work' AND r.reuse_terms='CC BY-SA 4.0' AND
                  (SELECT action FROM moderation_events e WHERE e.contribution_id=c.id AND e.revision=r.revision ORDER BY e.id DESC LIMIT 1)='allowed'))
                ORDER BY c.created_on,c.id LIMIT ? OFFSET ?""",
                (passage_id,bool(user and user['role']=='moderator'),user['id'] if user else None,limit,offset))]
            if not ids: return []
            placeholders=','.join('?' for _ in ids)
            rows = db.execute(f"""SELECT c.id, c.passage_id, c.owner_id, NOT (NOT EXISTS(SELECT 1 FROM removal_requests w WHERE (w.kind='contribution' AND w.target_id=c.id) OR (w.kind='account' AND w.target_id=c.owner_id))) AS withdrawn, r.*,
                COALESCE((SELECT action FROM moderation_events e WHERE e.contribution_id=c.id AND e.revision=r.revision ORDER BY e.id DESC LIMIT 1),'pending') AS effective_status
                FROM contributions c JOIN contribution_revisions r ON r.contribution_id=c.id
                WHERE c.id IN ({placeholders}) AND r.revision>(SELECT max(revision)-10 FROM contribution_revisions WHERE contribution_id=c.id)
                ORDER BY c.created_on,c.id,r.revision""",ids).fetchall()
            latest = {row['id']:row for row in rows}
            result=[]
            for row in rows:
                owner=bool(user and user['id']==row['owner_id'])
                moderator=bool(user and user['role']=='moderator')
                if not (owner or moderator) and not (latest[row['id']]['effective_status']=='allowed' and row['effective_status']=='allowed' and row['terms_version']=='2026-09-16.1' and row['rights_basis']=='original_work' and row['reuse_terms']=='CC BY-SA 4.0'):
                    continue
                item=dict(row)
                item['moderation_status']=item.pop('effective_status')
                item.pop('owner_id')
                item.pop('accepted_by')
                item['can_edit']=owner and not row['withdrawn']
                item['can_moderate']=moderator
                item['moderation_events']=[dict(e) for e in db.execute(
                    'SELECT e.id,e.action,e.reason,e.created_on,a.username AS moderator FROM moderation_events e JOIN accounts a ON a.id=e.actor_id WHERE e.contribution_id=? AND e.revision=? ORDER BY e.id DESC LIMIT 10',
                    (row['id'],row['revision']))] if owner or moderator else []
                item['moderation_events'].reverse()
                item['history_may_be_truncated']=row['revision']>10 or len(item['moderation_events'])==10
                result.append(item)
            return result

    def moderate(self, contribution_id, revision, action, reason, user, base_event):
        if user['role']!='moderator': raise PermissionError('Moderator access required')
        with closing(self.connection()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT max(revision) FROM contribution_revisions WHERE contribution_id=?',(contribution_id,)).fetchone()[0]
            if current is None: raise KeyError('Contribution not found')
            if current!=revision: raise Conflict('This contribution has a newer revision. Reload before moderating.')
            last=db.execute('SELECT COALESCE(max(id),0) FROM moderation_events WHERE contribution_id=? AND revision=?',(contribution_id,revision)).fetchone()[0]
            if last!=base_event: raise Conflict('A newer moderation decision exists. Reload before moderating.')
            if action == 'allowed':
                if db.execute("SELECT 1 FROM contributions c WHERE c.id=? AND NOT (NOT EXISTS(SELECT 1 FROM removal_requests w WHERE (w.kind='contribution' AND w.target_id=c.id) OR (w.kind='account' AND w.target_id=c.owner_id)))",(contribution_id,)).fetchone():
                    raise Conflict('Withdrawn contributions cannot be made public')
                rights=db.execute('SELECT terms_version,rights_basis,reuse_terms FROM contribution_revisions WHERE contribution_id=? AND revision=?',(contribution_id,revision)).fetchone()
                if tuple(rights)!=('2026-09-16.1','original_work','CC BY-SA 4.0'):
                    raise Conflict('Visibility requires current acceptance for original CC BY-SA 4.0 work. Permission-supported and legacy text need separate rights clearance.')
            consume(db,user['id'],'moderation decisions',100)
            db.execute('INSERT INTO moderation_events(contribution_id,revision,actor_id,action,reason,created_on) VALUES (?,?,?,?,?,?)',
                (contribution_id,revision,user['id'],action,reason,datetime.now(timezone.utc).isoformat()))
            return {'moderation_status':action,'review_status':'unreviewed'}

    def save(self, draft, contribution_id=None, user=None):
        if not user: raise PermissionError('Sign in to contribute')
        with closing(self.connection()) as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                now = datetime.now(timezone.utc).isoformat()
                if contribution_id is None:
                    if not db.execute('SELECT 1 FROM passage_records WHERE id=?', (draft.passage_id,)).fetchone():
                        raise KeyError('Passage not found')
                    contribution_id = str(uuid4())
                    db.execute('INSERT INTO contributions(id,passage_id,created_on,owner_id) VALUES (?,?,?,?)', (contribution_id, draft.passage_id, now,user['id']))
                    revision = 1
                else:
                    owner = db.execute('SELECT owner_id FROM contributions WHERE id=?',(contribution_id,)).fetchone()
                    if owner is None: raise KeyError('Contribution not found')
                    if owner[0]!=user['id']: raise PermissionError('Only the contributor can revise this draft')
                    if db.execute("SELECT 1 FROM contributions c WHERE c.id=? AND NOT (NOT EXISTS(SELECT 1 FROM removal_requests w WHERE (w.kind='contribution' AND w.target_id=c.id) OR (w.kind='account' AND w.target_id=c.owner_id)))",(contribution_id,)).fetchone():
                        raise Conflict('Withdrawn contributions cannot be revised')
                    current = db.execute('SELECT max(revision) FROM contribution_revisions WHERE contribution_id=?', (contribution_id,)).fetchone()[0]
                    if current is None:
                        raise KeyError('Contribution not found')
                    if draft.base_revision != current:
                        raise Conflict('This draft has a newer revision. Reload before saving.')
                    revision = current + 1
                if revision>50: raise Conflict('This pilot limits a contribution to 50 revisions. Contact the project maintainer.')
                consume(db,user['id'],'draft saves',20)
                values = draft.model_dump(exclude={'passage_id', 'base_revision', 'terms_accepted'})
                values.update(accepted_on=now, accepted_by=user['id'])
                columns = list(values)
                db.execute(f"INSERT INTO contribution_revisions (contribution_id,revision,{','.join(columns)},created_on) VALUES ({','.join('?' for _ in range(len(columns)+3))})",
                           [contribution_id, revision, *values.values(), now])
                db.commit()
                return {'id': contribution_id, 'revision': revision, 'review_status': 'unreviewed', 'moderation_status': 'pending'}
            except Exception:
                db.rollback()
                raise
