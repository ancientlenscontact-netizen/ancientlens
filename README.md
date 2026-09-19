# AncientLens

An open-source explorer for ancient inscriptions: browse real artifacts, read museum-sourced English translations, save private notes, and contribute original translations.

**Public pilot:** https://ancientlens.org/ · **Dataset and source releases:** https://ancientlens.org/data.html

The pilot contains 50 distinct Cleveland Museum of Art objects and 57 published translation entries across six editorial culture collections. Some entries are short names or coin legends. Every AncientLens scholarly review status is **unreviewed**. This is sourced retrieval, not automatic translation of arbitrary photographs. Museum content is not evidence of community activity.

## Run a local demo

Requires Python 3.9+ and Node 20.19+ (or22.12+). From a downloaded source release or clone:

```sh
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

In another terminal, from the project root:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The50 curated artifacts and57 passage references load without a corpus download or credentials. The hosted pilot additionally has7 Unas passage references; they are not part of the curated dataset release. Local accounts/data are created separately. Never copy the production SQLite file into a public release.

Try searching “Shemai”, opening its translation, registering a local account, saving a private note, and opening Contribute on an inscription. Save your recovery code: email password resets are not provided. Local mode also exposes experimental research tools; their proposed regions are not identified glyphs. Keep development servers on loopback.

## Test and build

```sh
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
python3 scripts/check_collection.py
python3 scripts/build_dataset_release.py
npm --prefix frontend run build
```

The optional real-Restic test skips if Restic is not installed. Tests use isolated temporary databases. The source archive excludes operator history, credentials, private databases, backups and acquired research originals. See [release scope](docs/PUBLIC_RELEASE.md).

## Data and licenses

[Versioned dataset](https://ancientlens.org/data.html): JSON records, JSON Schema, original museum metadata, images, checksums and provenance. Stable artifact IDs identify objects; passage IDs retain museum inscription indices. See [dataset documentation](docs/DATASET.md).

Project-owned software/documentation: [MIT](LICENSE). Cleveland source records/images: CC0. Original community translations: CC BY-SA4.0 with explicit acceptance; community submissions are not in this dataset release. These are separate grants; see [LICENSING.md](LICENSING.md). No museum endorsement or independent scholarly verification is implied.

## Participate

See [CONTRIBUTING.md](CONTRIBUTING.md) for code, original translations and source corrections. Security concerns: [SECURITY.md](SECURITY.md). Report ordinary bugs or source corrections to ancientlens.contact@gmail.com, with the artifact link and supporting evidence. Do not include passwords, recovery codes or private notes.

## Public hosting

The public community service excludes research image-upload routes. Self-hosting needs HTTPS, Secure cookies, explicit allowed origins, persistent SQLite, tested backups and moderator/operator controls. See [self-hosting](docs/SELF_HOSTING.md). Do not expose the local demo as a production service.

## Structure

- `frontend/src`: React interface and generated curated records
- `frontend/public/curated`: CC0 images and pinned source evidence
- `backend/app/api`: accounts, libraries, contributions and moderation
- `backend/app/data`: persistence, removal and backup tooling
- `backend/tests`: isolated regression tests
- `scripts`: deterministic dataset/source release tooling

Camera translation, scholarly accuracy evaluation and additional datasets remain future work. No accuracy score is claimed.
