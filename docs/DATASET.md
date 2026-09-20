# AncientLens curated dataset — 2026-09-20.1

51 distinct Cleveland Museum of Art objects;58 English source translation entries. Sources are museum-designated CC0 records/images. This is a curated source collection, not community usage, a complete translation of every photographed surface, or scholarly ground truth. All AncientLens reviews are unreviewed. Some entries are short names or coin legends. No accounts, credentials, private notes, reports or community submissions are included.

## Contents

- collection.json: complete array of51 artifact objects
- schema.json: JSON Schema2020-12 for that array
- curated/cma-ID.jpg: original museum web JPEG
- curated/cma-ID.json: individual object record
- curated/sources/cma-ID.json: pinned museum metadata evidence
- manifest.json: version, counts, byte lengths and SHA256 checksums
- LICENSES.md: scope of code, museum and community licenses

Paths beginning /curated are relative to the website origin; in this ZIP remove the leading slash to resolve a file locally. source_url and metadata_url point to the museum. Decode JSON as UTF-8. Source typos, gaps, uncertainty and wording remain verbatim.

## Field contract

id is the stable cma-{museum ID} artifact identifier. accession is the museum accession, not another artifact. title and date reproduce the museum fields. culture preserves source labels; collection/source_language are editorial classifications, including explicit unknown classifications. language is the translation language. review describes AncientLens scholarly review, always unreviewed in this release.

passages contains id, field, text, source_text and remark. Passage IDs use cma-{museum ID}-{original inscription index}; indices may have gaps because untranslated entries are excluded. field identifies the exact source array field. text is the English museum translation; source_text is the museum transcription where supplied. Never infer photograph alignment from those fields alone.

institution, source_url, metadata_url, retrieved_at and metadata_sha256 preserve provenance. text_license/image_license and their rights URLs record CC0 evidence. image/image_url/image_sha256 identify and verify the photograph. image_changes/text_changes disclose transformations. source_snapshot and record_url identify local evidence. note contains important editorial scope caveats; retain it alongside text. description contains museum alternative wording where included.

## Reuse and updates

Cleveland source text, metadata and images retain CC0. Credit/provenance are requested for traceability; do not imply museum endorsement. AncientLens-authored documentation/software uses MIT, not a blanket claim of ownership over the collection. Community CC BY-SA translations are a separate scope and excluded here.

Version2026-09-19.1 is the initial downloadable release. Future releases preserve object/passage identities and publish a new immutable version; corrections do not silently replace historical ZIPs. Check the adjacent .sha256 file after downloading. Rebuild with python3 scripts/build_dataset_release.py; validate source fidelity with python3 scripts/check_collection.py.

Version2026-09-20.1 adds one Maya panel with a short sculptor-name source entry; it does not add30 full translations. Prior ZIP2026-09-19.1 remains immutable.
