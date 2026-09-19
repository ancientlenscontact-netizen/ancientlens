CREATE TABLE monuments (id TEXT PRIMARY KEY, name TEXT NOT NULL, site TEXT NOT NULL, country TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(id));
CREATE TABLE passage_records (
 id TEXT PRIMARY KEY, monument_id TEXT NOT NULL REFERENCES monuments(id), designation TEXT NOT NULL, locator TEXT NOT NULL,
 source_id TEXT NOT NULL REFERENCES sources(id), candidate_writing_system_id TEXT REFERENCES writing_systems(id),
 classification_source_id TEXT REFERENCES sources(id), review_status TEXT NOT NULL CHECK(review_status='unreviewed'),
 note TEXT NOT NULL
);
CREATE TABLE passage_references (
 passage_id TEXT NOT NULL REFERENCES passage_records(id), source_id TEXT NOT NULL REFERENCES sources(id),
 role TEXT NOT NULL CHECK(role IN ('reference','edition','translation')), reuse_status TEXT NOT NULL CHECK(reuse_status IN ('unknown','licensed','public_domain')),
 note TEXT NOT NULL, PRIMARY KEY(passage_id,source_id,role)
);
CREATE TABLE media_records (
 id TEXT PRIMARY KEY, monument_id TEXT NOT NULL REFERENCES monuments(id), source_id TEXT NOT NULL REFERENCES sources(id),
 author TEXT NOT NULL, license TEXT NOT NULL, license_url TEXT NOT NULL, attribution TEXT NOT NULL,
 original_path TEXT NOT NULL, normalized_path TEXT NOT NULL, original_sha256 TEXT NOT NULL, normalized_sha256 TEXT NOT NULL,
 width INTEGER NOT NULL CHECK(width>0), height INTEGER NOT NULL CHECK(height>0),
 review_status TEXT NOT NULL CHECK(review_status='unreviewed'), triage TEXT NOT NULL,
 CHECK(length(original_sha256)=64), CHECK(length(normalized_sha256)=64)
);
CREATE TABLE text_unit_media (text_unit_id TEXT PRIMARY KEY REFERENCES text_units(id), media_id TEXT NOT NULL REFERENCES media_records(id));
CREATE TABLE passage_image_links (
 passage_id TEXT NOT NULL REFERENCES passage_records(id), text_unit_id TEXT NOT NULL REFERENCES text_units(id),
 status TEXT NOT NULL CHECK(status IN ('unreviewed','reviewed','rejected')), evidence TEXT NOT NULL,
 reviewer TEXT, reviewed_on TEXT, PRIMARY KEY(passage_id,text_unit_id),
 CHECK(status='unreviewed' OR (reviewer IS NOT NULL AND length(trim(reviewer))>0 AND reviewed_on IS NOT NULL)),
 CHECK(length(trim(evidence))>0)
);
CREATE TABLE public_record_imports (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL CHECK(length(sha256)=64));
-- Replace the v1-only CHECK without touching existing catalog or review rows.
DROP TABLE catalog_version;
CREATE TABLE catalog_version (version INTEGER PRIMARY KEY CHECK(version IN (1,2)));
INSERT INTO catalog_version VALUES(2);
