# Pilot follow-up fixes — 2026-09-19

Implemented after the sequential simulated pilot. This is product validation, not human research or scholarly validation.

- Entering My Library resets discovery query, culture, topic, type, date wording, period and location. Its result count shows matching versus total saved objects.
- Library search includes the authenticated user's already-loaded private notes. Public Explore and Map do not receive note text. No new API or public indexing.
- Download lesson sheet now creates an offline HTML document with an embedded museum image, exact source passages, citation, rights and unreviewed/alignment caveats. Teaching prompts remain separate. Private notes are excluded. Source strings are escaped; the document has no scripts and restricts resources with CSP. Image failure produces a retry message rather than a silently incomplete handout. Open the HTML in a browser to print/save as PDF.
- Empty related-object sections are hidden. Compare and remove controls identify title and accession for accessibility.

Validation: TypeScript/Vite build passed; 15 library/contribution/pilot tests passed; source checker confirms 50 distinct objects and 57 exact source entries with provenance/image hashes. Focused frontend regression checks cover private/public search, all passage exports, escaping and exclusion of a private-note field. Browser: nonmatching 1–600 CE filter then Library shows 2/2; essay note search shows 1/2; Explore essay search shows zero; singleton Assyrian related heading absent. Actual downloaded HTML inspected and rendered at desktop/390px with embedded photograph, all passages, caveats and no QA private note. Live HTTPS bundle hash matches local; live lesson download reports success. Full printer/PDF pagination and a complete assistive-technology audit remain unverified.

Frontend-only deployment. No production account writes, new collection, backend migration, purchases or backup attempts.

## Repeat focused frontend checks

From the repository root, compile into a temporary directory and run:

```sh
frontend/node_modules/.bin/tsc frontend/src/Discovery.ts frontend/src/LessonSheet.ts --outDir /tmp/ancientlens-research-tests --module commonjs --target es2022 --skipLibCheck
node frontend/tests/research-tools.cjs /tmp/ancientlens-research-tests
```
