CREATE TABLE accounts (
 id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT 'contributor' CHECK(role IN ('contributor','moderator')), created_on TEXT NOT NULL
);
CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id), expires_at INTEGER NOT NULL);
CREATE TABLE auth_attempts (bucket TEXT PRIMARY KEY, started_at INTEGER NOT NULL, attempts INTEGER NOT NULL);
ALTER TABLE contributions ADD COLUMN owner_id TEXT REFERENCES accounts(id);
CREATE TABLE moderation_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, contribution_id TEXT NOT NULL, revision INTEGER NOT NULL,
 actor_id TEXT NOT NULL REFERENCES accounts(id), action TEXT NOT NULL CHECK(action IN ('allowed','changes_requested','hidden')),
 reason TEXT NOT NULL CHECK(length(trim(reason))>0), created_on TEXT NOT NULL,
 FOREIGN KEY(contribution_id,revision) REFERENCES contribution_revisions(contribution_id,revision)
);
CREATE TRIGGER moderation_no_update BEFORE UPDATE ON moderation_events BEGIN SELECT RAISE(ABORT,'Moderation history is immutable'); END;
CREATE TRIGGER moderation_no_delete BEFORE DELETE ON moderation_events BEGIN SELECT RAISE(ABORT,'Moderation history is immutable'); END;
CREATE INDEX moderation_revision ON moderation_events(contribution_id,revision,id);
DROP TABLE catalog_version;
CREATE TABLE catalog_version (version INTEGER PRIMARY KEY CHECK(version IN (1,2,3,4)));
INSERT INTO catalog_version VALUES(4);
