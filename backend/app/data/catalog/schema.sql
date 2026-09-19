CREATE TABLE catalog_version (version INTEGER PRIMARY KEY CHECK(version=1));
CREATE TABLE sources (id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL, accessed_on TEXT NOT NULL, note TEXT NOT NULL);
CREATE TABLE languages (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(id));
CREATE TABLE varieties (
 id TEXT PRIMARY KEY, language_id TEXT NOT NULL REFERENCES languages(id), name TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('historical_stage','dialect','register','unspecified')),
 parent_id TEXT, source_id TEXT NOT NULL REFERENCES sources(id), note TEXT NOT NULL,
 UNIQUE(id,language_id), FOREIGN KEY(parent_id,language_id) REFERENCES varieties(id,language_id), CHECK(parent_id IS NULL OR parent_id<>id)
);
CREATE TABLE scripts (id TEXT PRIMARY KEY, name TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(id), note TEXT NOT NULL);
CREATE TABLE writing_systems (
 id TEXT PRIMARY KEY, language_id TEXT NOT NULL REFERENCES languages(id), variety_id TEXT,
 script_id TEXT NOT NULL REFERENCES scripts(id), source_id TEXT NOT NULL REFERENCES sources(id), note TEXT NOT NULL,
 FOREIGN KEY(variety_id,language_id) REFERENCES varieties(id,language_id)
);
CREATE TABLE research_priorities (
 writing_system_id TEXT PRIMARY KEY REFERENCES writing_systems(id), priority TEXT NOT NULL CHECK(priority IN ('initial','secondary','future')),
 reason TEXT NOT NULL
);
CREATE TABLE capabilities (
 writing_system_id TEXT NOT NULL REFERENCES writing_systems(id), task TEXT NOT NULL CHECK(task IN ('localization','recognition','reading_order','transliteration','translation','known_inscription_retrieval')),
 status TEXT NOT NULL DEFAULT 'unavailable' CHECK(status IN ('unavailable','experimental','validated')),
 evidence TEXT, PRIMARY KEY(writing_system_id,task), CHECK(status='unavailable' OR (evidence IS NOT NULL AND length(trim(evidence))>0))
);
-- One inscription may contain several languages/scripts; alternatives are separate assertions.
CREATE TABLE text_units (id TEXT PRIMARY KEY, corpus_object_id TEXT NOT NULL, corpus_sample_id TEXT NOT NULL, normalized_sha256 TEXT NOT NULL CHECK(length(normalized_sha256)=64), region_ref TEXT, note TEXT NOT NULL);
CREATE TABLE classification_assertions (
 id TEXT PRIMARY KEY, text_unit_id TEXT NOT NULL REFERENCES text_units(id), writing_system_id TEXT NOT NULL REFERENCES writing_systems(id),
 status TEXT NOT NULL DEFAULT 'unreviewed' CHECK(status IN ('unreviewed','reviewed','rejected')),
 author TEXT NOT NULL, evidence TEXT, reviewer TEXT, reviewed_on TEXT,
 CHECK(status='unreviewed' OR (reviewer IS NOT NULL AND length(trim(reviewer))>0 AND evidence IS NOT NULL AND length(trim(evidence))>0 AND reviewed_on IS NOT NULL))
);
INSERT INTO catalog_version VALUES(1);
