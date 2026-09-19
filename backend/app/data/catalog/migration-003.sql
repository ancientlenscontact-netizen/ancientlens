CREATE TABLE contributions (
 id TEXT PRIMARY KEY,
 passage_id TEXT NOT NULL REFERENCES passage_records(id),
 created_on TEXT NOT NULL
);
CREATE TABLE contribution_revisions (
 contribution_id TEXT NOT NULL REFERENCES contributions(id),
 revision INTEGER NOT NULL CHECK(revision > 0),
 author TEXT NOT NULL CHECK(length(trim(author))>0),
 translation_language TEXT NOT NULL CHECK(length(trim(translation_language))>0),
 translation TEXT NOT NULL CHECK(length(trim(translation))>0),
 source TEXT NOT NULL CHECK(length(trim(source))>0),
 reuse_terms TEXT NOT NULL CHECK(length(trim(reuse_terms))>0),
 rights_basis TEXT NOT NULL CHECK(rights_basis IN ('original_work','permission_supported')),
 rights_evidence TEXT NOT NULL CHECK(length(trim(rights_evidence))>0),
 notes TEXT NOT NULL,
 ai_assisted INTEGER NOT NULL CHECK(ai_assisted IN (0,1)),
 created_on TEXT NOT NULL,
 review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK(review_status='unreviewed'),
 moderation_status TEXT NOT NULL DEFAULT 'pending' CHECK(moderation_status='pending'),
 PRIMARY KEY(contribution_id, revision)
);
CREATE TRIGGER revisions_no_update BEFORE UPDATE ON contribution_revisions
 BEGIN SELECT RAISE(ABORT, 'Revisions are immutable'); END;
CREATE TRIGGER revisions_no_delete BEFORE DELETE ON contribution_revisions
 BEGIN SELECT RAISE(ABORT, 'Revisions are immutable'); END;
DROP TABLE catalog_version;
CREATE TABLE catalog_version (version INTEGER PRIMARY KEY CHECK(version IN (1,2,3)));
INSERT INTO catalog_version VALUES(3);
