CREATE TABLE erasure_events (
 request_id INTEGER PRIMARY KEY REFERENCES removal_requests(id),
 catalog_purged_on TEXT NOT NULL,
 scope TEXT NOT NULL CHECK(scope='catalog_only')
);
CREATE TRIGGER erasures_no_update BEFORE UPDATE ON erasure_events BEGIN SELECT RAISE(ABORT,'Erasure audit is immutable'); END;
CREATE TRIGGER erasures_no_delete BEFORE DELETE ON erasure_events BEGIN SELECT RAISE(ABORT,'Erasure audit is immutable'); END;
DROP TABLE catalog_version;
CREATE TABLE catalog_version (version INTEGER PRIMARY KEY CHECK(version IN (1,2,3,4,5,6,7,8)));
INSERT INTO catalog_version VALUES(8);
