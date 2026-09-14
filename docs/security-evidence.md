# Catalog evidence

Security review and generation results are separate and belong to a module,
version and full archive SHA-256. A missing match stays pending. Built-in
worlds without a separate archive display Review not applicable.

`ap-web/security-evidence.json` reserves the public metadata schema and is
empty in the source tree. Worker-generated evidence is delivered directly
to the beta runtime, rather than published in the application repository. The
source report is private; its fingerprint identifies it without exposing
its contents. Public immutable records are served at
`/api/apworlds/security-reviews/<record-digest>`. Source-audit dates are UTC.
Holds augment the underlying source review; the audit date is not a claim
about when the maintainer placed the hold. A routine automated PASS cannot
erase an earlier recorded concern or hold. Clearing it requires an explicit
checksum-bound maintainer decision. Published records are retained.

`ap-web/fuzz-evidence.json` backfills Actions provenance only when the source
commit's archive checksum and all recorded fuzz fields match. The modal
links to that test run and separately to the immutable index result.
Absent original provenance is stated explicitly. An Actions conclusion
does not replace or reinterpret the saved fuzz result.

Runtime overlays live beside the persistent index in `.state/`. The web
application detects atomic file replacements and updates its cached catalog.
Malformed review overlays retain the previous valid dispositions; malformed
fuzz provenance cannot invent a link or change a result. No application or
GitHub write token is used by this feed.

Run `scripts/export_security_evidence.py` beside the audit worker with a
read-only audit database and the target index lock. Optional reviewed
summaries and maintainer holds augment its metadata. Run
`scripts/export_fuzz_provenance.py` with the existing badge producer, target
catalog, lock and a local cache for public GitHub metadata. Neither exporter
changes the audit database or the index.

`scripts/publish_beta_evidence.py` coordinates these exports and publishes
validated public metadata through an existing SSH connection. It refuses
production website/container targets. Run it from a restricted maintenance
account or timer; keep its audit inputs and GitHub cache outside the web tier.
It does not run audits, merge PRs, refresh the index, send notifications or
enable generation. Before promotion, deploy and verify the corresponding
production evidence feed separately.

Regression checks: `scripts/test_security_evidence.py`,
`scripts/test_fuzz_evidence.py` and frontend Playwright catalog/security tests.
ALL-games discovery and isolated Builder derivation remain separate work.
