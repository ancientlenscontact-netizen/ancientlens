ALTER TABLE sessions ADD COLUMN credential_version TEXT;
UPDATE sessions SET credential_version=(SELECT password_hash FROM accounts WHERE id=sessions.account_id);
CREATE TABLE write_quotas (account_id TEXT NOT NULL REFERENCES accounts(id), kind TEXT NOT NULL, window INTEGER NOT NULL, used INTEGER NOT NULL, PRIMARY KEY(account_id,kind,window));
CREATE TABLE recovery_codes (account_id TEXT PRIMARY KEY REFERENCES accounts(id), code_hash TEXT NOT NULL);
CREATE TABLE reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT, contribution_id TEXT NOT NULL, revision INTEGER NOT NULL,
 reporter_id TEXT NOT NULL REFERENCES accounts(id), reason TEXT NOT NULL CHECK(length(trim(reason))>0), created_on TEXT NOT NULL,
 UNIQUE(contribution_id,revision,reporter_id), FOREIGN KEY(contribution_id,revision) REFERENCES contribution_revisions(contribution_id,revision)
);
CREATE TABLE report_resolutions (report_id INTEGER PRIMARY KEY REFERENCES reports(id), actor_id TEXT NOT NULL REFERENCES accounts(id), outcome TEXT NOT NULL CHECK(outcome IN ('action_taken','dismissed')), reason TEXT NOT NULL CHECK(length(trim(reason))>0), created_on TEXT NOT NULL);
CREATE TRIGGER reports_no_update BEFORE UPDATE ON reports BEGIN SELECT RAISE(ABORT,'Report history is immutable'); END;
CREATE TRIGGER reports_no_delete BEFORE DELETE ON reports BEGIN SELECT RAISE(ABORT,'Report history is immutable'); END;
CREATE TRIGGER resolutions_no_update BEFORE UPDATE ON report_resolutions BEGIN SELECT RAISE(ABORT,'Report history is immutable'); END;
CREATE TRIGGER resolutions_no_delete BEFORE DELETE ON report_resolutions BEGIN SELECT RAISE(ABORT,'Report history is immutable'); END;
CREATE INDEX contributions_passage ON contributions(passage_id,created_on,id);
DROP TABLE catalog_version;
CREATE TABLE catalog_version (version INTEGER PRIMARY KEY CHECK(version IN (1,2,3,4,5)));
INSERT INTO catalog_version VALUES(5);
