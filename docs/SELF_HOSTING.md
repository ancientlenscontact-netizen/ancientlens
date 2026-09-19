# Self-hosting the community pilot

Use README for a loopback demo. Production needs a separate persistent data directory and HTTPS reverse proxy. Use backend/app/community.py with ANCIENTLENS_SERVICE_MODE=community, ANCIENTLENS_SECURE_COOKIES=1, ANCIENTLENS_ALLOWED_ORIGINS=https://your-domain.example, ANCIENTLENS_CATALOG_PATH pointing to a private persistent SQLite file, and ANCIENTLENS_DATA_DIR outside the static document root. Initialize a new catalog using app.data.catalog.initialize before production startup. Never distribute a populated private catalog.

Build frontend with npm ci and npm run build. Serve frontend/dist and proxy /api to the loopback backend. Do not publish the backend development server or local research media. Do not cache private API responses. No automatic first-user moderator: assign an existing account with the Accounts operator API after verifying ownership.

Recovery codes are single-use and shown only to their owner. No email reset or account-identity override exists. Back up the catalog and required corpus through app.data.backup; verify an isolated restore and reconcile the latest removal ledger before activating restored data. Encrypted off-device maintenance is in app.data.offdevice; its repository constants/configuration must be set for your dedicated storage. Do not reuse the operator’s deployment details or credentials.

Monitor service reachability, backup success and missed runs. Keep external monitoring credentials outside static files and Git. The application is an early pilot, not a managed hosting service or a scholarly verification system.
