ALTER TABLE contribution_revisions ADD COLUMN terms_version TEXT;
ALTER TABLE contribution_revisions ADD COLUMN accepted_on TEXT;
ALTER TABLE contribution_revisions ADD COLUMN accepted_by TEXT REFERENCES accounts(id);
DROP TABLE catalog_version;
CREATE TABLE catalog_version (version INTEGER PRIMARY KEY CHECK(version IN (1,2,3,4,5,6)));
INSERT INTO catalog_version VALUES(6);
