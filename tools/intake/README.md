# Automatic APWorld discovery intake

This implementation separates discovery from accepted-index merging. Verified
artifacts enter discovery before security and generation results are available.
Evidence and worker jobs belong to the exact module, version and SHA-256.

## Current components

- `reconcile.py` registers every index source, immutable queued PR heads and
  recorded non-passing audit artifacts. Existing guides and holds are retained.
- `scan_sources.py` scans registered GitHub repositories once per repository,
  accounts for unsupported sources and errors, paginates releases, matches
  assets to their game, and detects asset revisions. Missing accepted tags do
  not suppress discovery. Cached responses expire after thirty minutes.
- `artifact_worker.py` verifies bounded HTTPS downloads and archives without
  executing package code. Redirect hosts and resolved addresses are checked.
- `verify_queue.py` launches artifact verification in Bubblewrap with an empty
  environment, isolated namespaces and no application, home or credential
  mounts. Verified bytes are stored under their content hash.
- `ledger.py` retains source observations, immutable releases, independent
  security/generation/guide jobs, worker leases, backoff and permanent blocks.

## Operational components

Validated snapshots and hash-addressed archive downloads are published to beta
before evidence work. Invalid replacements retain the last valid feed; retained
checksum-addressed snapshots support rollback without clearing policy holds.

Independent jobs import exact-hash cached security and Actions test evidence,
perform bounded isolated source reviews, derive schemas statically, and verify
guide links. Generation execution remains on the existing separate Actions
workers. The intake collector never starts fresh fuzzing on Atlas. Missing test
results remain pending; a cached result from different bytes is never inherited.

The timer scans all registered sources at minutes 05/35, verifies at most 100
artifacts with four isolated workers, and runs at most one uncached review.
Generation collection rotates through five PR-head cache refreshes per cycle.
Discovery remains available while independent work retries or awaits capacity.

Failed historical artifacts are explicit unverified observations, with no
verified download. Unknown historical checksums remain unknown. Changed bytes
under a declared checksum are quarantined and held independently of reviews.

The catalog keeps operational queue details collapsed for admins. Visitors have
a source-submission link below the cards and per-release evidence/warnings.
Existing guide links are preserved; independently verified links fill gaps.

The 2026-09-14 unattended run `1939b5b532744fe2a5f2a8cf0f03e64f` verified 99
artifacts, published discovery first, then processed security, generation,
schemas and guides successfully. Full original source/PR/audit reconciliation,
cached hashes, policy joins and guide preservation were audited against beta.

Production publication is a separate operation. No component here merges index
PRs or modifies production databases.

Run deterministic checks with:

```sh
python3 -m unittest discover -s tools/intake -p 'test_*.py' -v
```
