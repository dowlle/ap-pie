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

## Full completion requirements

The following remain required before calling this pipeline complete:

1. Publish validated discovery snapshots to beta through a bounded loader that
   preserves accepted records and the existing guide batch.
2. Import exact-hash cached review/test evidence and preserve policy holds;
   never turn an unrelated successful check into security clearance.
3. Implement credential-free archive processing and generation workers, plus
   a broker for the established source-review provider. New packages must not
   reach the current web-request schema derivation path.
4. Implement independent guide finding and restricted schema derivation, with
   validated cached output served by the application.
5. Provide queue visibility and a source-submission path, reconcile deleted
   assets, handle changed bytes under the same version, and prioritize newest
   releases and queued updates over historical artifacts.
6. Install the guarded beta-only scheduled publisher and verify a scheduled
   cycle end to end, including retries, deduplication and rollback.

Production publication is a separate operation. No component here merges index
PRs or modifies production databases.

Run deterministic checks with:

```sh
python3 -m unittest discover -s tools/intake -p 'test_*.py' -v
```
