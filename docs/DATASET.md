# AncientLens curated dataset — 2026-09-20.6

92 distinct objects/documents,100 English source entries:60 Cleveland objects/67entries,29 Maya research-source records/30entries, and3 Walters objects/3entries. All AncientLens scholarly reviews remain unreviewed. The30-record Maya collection includes the earlier Cleveland panel. Most new entries are names or short phrases; some are damaged dedicatory passages. One Dresden Codex record contains only a page18b deity-name excerpt. These are not30 fully translated documents. No fabricated activity, accounts, private notes or community submissions are included.

## Contents and identifiers

collection.json and schema.json describe all records. curated/{id}.json is the individual record; curated/sources/{id}.json is pinned source evidence. cma- IDs preserve the Cleveland accession association and original inscription index. maya- IDs identify distinct objects/documents; a stairway or codex is counted once. field locates the selected passage in its publication. Some source fields list parallel attestations: the record title identifies the one selected, not multiple imported objects. source_text preserves source transcription when included.

Cleveland records retain exact museum wording and CC0 photographs. New research text is excerpted from credited ClassicMayan research notes: HTML whitespace is collapsed, but wording, gaps, question marks and alternatives are preserved. Date not catalogued means no bounded date was imported; no date or findspot is inferred from royal names. Broad cultural labels are editorial.

## Rights and media

text_license and text_rights_url must be read per record. Cleveland materials are CC0; ClassicMayan excerpts are CC BY4.0 with required attribution to the authors/publication in institution and source_url. institution is source credit, not a universal holding-museum field. Preserve text_changes and coverage in note. See LICENSES.md. Do not label this mixed collection wholly CC0. No endorsement or independent scholarly review is implied.

Three Maya research records now include credited scholarly drawings;26 remain text-only. Copan Stela64 now includes both published front/reverse renderings with lacunae retained. The other two illustrated editions are CCIT Vaso8 and PNTF192. All three are fragmentary, not complete recovered ancient documents. curated/pilot-selection.json records this first source-coverage selection toward20perarea; it is not scholarly validation.

Empty image, image_url, image_sha256 and image_rights_url with image_license=Not included mean that no image is supplied or licensed by this release. The UI offers a textual preview, not a photograph. Do not treat it as archaeological imagery. For records with photographs, image_sha256 verifies the original bytes. metadata_sha256 verifies the local source_snapshot; research evidence additionally records the retrieved HTML hash and exact excerpt context. Source snapshots are evidence, not ancient documents.

Paths beginning /curated resolve relative to the website; remove the leading slash inside the ZIP. Decode UTF-8. manifest.json lists byte lengths and SHA256 checksums. Separate release .sha256 verifies the archive. Build with scripts/build_dataset_release.py; check fidelity with scripts/check_collection.py.

## Release history

2026-09-19.1:50 Cleveland objects/57entries. 2026-09-20.1:51/58, adding the Maya panel. 2026-09-20.2:80/87 with29 attributed research excerpts. Prior ZIPs remain immutable. Community CC BY-SA acceptance is a separate workflow and unchanged.

2026-09-20.3: three drawings, one additional published front passage,88entries. Previous ZIPs immutable.

2026-09-20.4: selection expands to9 existing records (5 China,1 SouthAsia,3 Mesoamerica); no artifact/translation/image changes. Selection evidence and image limitations included. The20-per-area target remains unfinished.

2026-09-20.5 adds2 CC0 Walters records with photographs and complete short published inscription renderings. Aurelia Artemis is an Egyptian-region object with Greek text. Pepi vessel alternative rendering is preserved in the passage remark, not a second inscription. Selection now11 (Egypt2,China5,SouthAsia1,Mesoamerica3); target20each remains unfinished.

2026-09-20.6 adds nine Chinese mirrors and a Mesopotamian foundation tablet, each with a reusable photograph and complete museum-published rendering. Two existing Chinese records also enter the illustrated selection:23 selected (China16,Egypt2,Mesoamerica3,SouthAsia1,Mesopotamia1). Target20each remains unfinished. The tablet photograph shows both inscribed faces; its language is not specified by the museum. All scholarly reviews unreviewed.
