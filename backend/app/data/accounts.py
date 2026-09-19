"""Account/session persistence. Passwords and session tokens never leave this boundary."""
import argparse
import hashlib
import hmac
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from app.data.catalog import connect, initialize

ITERATIONS = 600_000
SESSION_SECONDS = 7 * 24 * 60 * 60

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f'{salt}${digest}'

class RateLimited(Exception):
    pass

class Accounts:
    def __init__(self, path):
        self.path = path

    def throttle(self, key, limit=20):
        now = int(time.time())
        # Do not retain raw client addresses; forwarded headers are deliberately ignored.
        bucket = hashlib.sha256(key.encode()).hexdigest()
        with closing(connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM auth_attempts WHERE started_at < ?', (now-900,))
            row = db.execute('SELECT attempts FROM auth_attempts WHERE bucket=?', (bucket,)).fetchone()
            if row and row[0] >= limit:
                raise RateLimited()
            db.execute('INSERT INTO auth_attempts VALUES (?,?,1) ON CONFLICT(bucket) DO UPDATE SET attempts=attempts+1', (bucket,now))

    def register(self, username, password):
        id = str(uuid4())
        encoded = password_hash(password)
        with closing(connect(self.path)) as db, db:
            try:
                db.execute('INSERT INTO accounts(id,username,password_hash,created_on) VALUES (?,?,?,?)',
                           (id,username,encoded,datetime.now(timezone.utc).isoformat()))
            except sqlite3.IntegrityError:
                raise ValueError('This username is unavailable')
        return {'id':id,'username':username,'role':'contributor'}

    def login(self, username, password):
        with closing(connect(self.path)) as db:
            row = db.execute('SELECT id,username,role,password_hash FROM accounts WHERE username=? AND closed_on IS NULL', (username,)).fetchone()
        stored = row[3] if row else '00'*16 + '$' + '00'*32
        candidate = password_hash(password,stored.split('$')[0])
        if not hmac.compare_digest(candidate,stored):
            return None
        return {'id':row[0],'username':row[1],'role':row[2],'credential_version':row[3]} if row else None

    def issue_recovery(self, account_id, credential_version=None):
        code=secrets.token_hex(32)
        with closing(connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM accounts WHERE id=? AND closed_on IS NULL',(account_id,)).fetchone():
                raise ValueError('Account is closed')
            if credential_version and not db.execute('SELECT 1 FROM accounts WHERE id=? AND password_hash=?',(account_id,credential_version)).fetchone():
                raise ValueError('Password changed; sign in again')
            db.execute('INSERT INTO recovery_codes VALUES (?,?) ON CONFLICT(account_id) DO UPDATE SET code_hash=excluded.code_hash',
                (account_id,hashlib.sha256(code.encode()).hexdigest()))
        return code

    def recover(self, username, code, password):
        # Fixed-cost password hashing also runs for invalid usernames/codes.
        encoded=password_hash(password)
        replacement=secrets.token_hex(32)
        with closing(connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT a.id,r.code_hash FROM accounts a JOIN recovery_codes r ON r.account_id=a.id WHERE a.username=? AND a.closed_on IS NULL',(username,)).fetchone()
            supplied=hashlib.sha256(code.encode()).hexdigest()
            if not hmac.compare_digest(supplied,row[1] if row else '0'*64): return None
            db.execute('UPDATE accounts SET password_hash=? WHERE id=?',(encoded,row[0]))
            db.execute('DELETE FROM sessions WHERE account_id=?',(row[0],))
            db.execute('UPDATE recovery_codes SET code_hash=? WHERE account_id=?',(hashlib.sha256(replacement.encode()).hexdigest(),row[0]))
        return replacement

    def session(self, account_id, credential_version=None):
        token = secrets.token_urlsafe(32)
        with closing(connect(self.path)) as db, db:
            if not db.execute('SELECT 1 FROM accounts WHERE id=? AND closed_on IS NULL',(account_id,)).fetchone():
                raise ValueError('Account is closed')
            db.execute('DELETE FROM sessions WHERE expires_at<=?', (int(time.time()),))
            stamp=credential_version or db.execute('SELECT password_hash FROM accounts WHERE id=?',(account_id,)).fetchone()[0]
            db.execute('INSERT INTO sessions VALUES (?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(),account_id,int(time.time())+SESSION_SECONDS,stamp))
        return token

    def user(self, token):
        if not token or len(token)>128:
            return None
        with closing(connect(self.path)) as db:
            row = db.execute('SELECT a.id,a.username,a.role FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE token_hash=? AND expires_at>? AND s.credential_version=a.password_hash AND a.closed_on IS NULL',
                             (hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
        return dict(zip(('id','username','role'),row)) if row else None

    def logout(self, token):
        if token:
            with closing(connect(self.path)) as db, db:
                db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='Assign an existing local account role; no password is accepted here.')
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--username',required=True)
    parser.add_argument('--role',choices=['contributor','moderator'],required=True)
    args=parser.parse_args()
    if not args.database.is_file(): parser.error('Database not found')
    initialize(args.database)
    with closing(connect(args.database)) as db, db:
        cursor=db.execute('UPDATE accounts SET role=? WHERE username=? AND closed_on IS NULL',(args.role,args.username.lower()))
        if cursor.rowcount != 1: parser.error('Account not found; register in the application first')
    print('Account role updated. Scholarly reviewer status is unchanged.')
