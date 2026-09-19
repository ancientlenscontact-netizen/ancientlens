CREATE TABLE curated_artifacts (id TEXT PRIMARY KEY REFERENCES monuments(id), title TEXT NOT NULL);
CREATE TABLE saved_artifacts (
 account_id TEXT NOT NULL REFERENCES accounts(id), artifact_id TEXT NOT NULL REFERENCES curated_artifacts(id),
 notes TEXT NOT NULL DEFAULT '' CHECK(length(notes)<=4000), version INTEGER NOT NULL CHECK(version>0),
 updated_on TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0 CHECK(deleted IN (0,1)),
 PRIMARY KEY(account_id,artifact_id)
);
CREATE TABLE library_deletions (
 account_id TEXT NOT NULL REFERENCES accounts(id), artifact_id TEXT NOT NULL REFERENCES curated_artifacts(id),
 removed_on TEXT NOT NULL, PRIMARY KEY(account_id,artifact_id)
);
DROP TABLE catalog_version;
CREATE TABLE catalog_version (version INTEGER PRIMARY KEY CHECK(version BETWEEN 1 AND 9));
INSERT INTO catalog_version VALUES(9);
