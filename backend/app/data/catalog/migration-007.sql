ALTER TABLE accounts ADD COLUMN closed_on TEXT;
CREATE TABLE removal_requests (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 kind TEXT NOT NULL CHECK(kind IN ('account','contribution')),
 target_id TEXT NOT NULL,
 requested_by TEXT NOT NULL REFERENCES accounts(id),
 created_on TEXT NOT NULL,
 UNIQUE(kind,target_id)
);
CREATE TRIGGER removals_no_update BEFORE UPDATE ON removal_requests BEGIN SELECT RAISE(ABORT,'Removal requests are immutable'); END;
CREATE TRIGGER removals_no_delete BEFORE DELETE ON removal_requests BEGIN SELECT RAISE(ABORT,'Removal requests are immutable'); END;
DROP TABLE catalog_version;
CREATE TABLE catalog_version (version INTEGER PRIMARY KEY CHECK(version IN (1,2,3,4,5,6,7)));
INSERT INTO catalog_version VALUES(7);
