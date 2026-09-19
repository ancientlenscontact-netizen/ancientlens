# Public source release boundary

Public releases use scripts/build_source_release.py to copy an explicit allowlist into a clean snapshot. They do not publish the operator Git history or internal deployment/context documents. This prevents private operational material from being inherited by an otherwise public code release.

Included: application source, dependencies/lockfiles, isolated tests and their public Unas reference fixture (no photograph), public CC0 assets, dataset/release scripts, licenses and user/developer documentation. Excluded: credentials, environment files, SQLite/catalog data, backups, runtime caches, original research corpus and internal operational history. Inspect release file inventory and run tests from the staged source before publishing. Generated source archives exclude themselves and dataset ZIPs to avoid recursion.

A downloadable source release is open-source distribution. It is not a substitute for a publicly hosted Git repository and issue workflow; link that repository once authentication and publication are complete.
