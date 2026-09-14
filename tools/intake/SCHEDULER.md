# Beta intake scheduler

Installed on Atlas on 2026-09-14 with tooling checkout
`/home/stef/projects/ap-pie-intake` at `0784c87`.

Dedicated persistent state:
`/home/stef/projects/ap-pie-support/artifacts/automatic-intake-beta`.
The initial SQLite database was copied with SQLite's backup API.

User units are `ap-pie-beta-intake.service` and `ap-pie-beta-intake.timer`.
The timer runs at minutes 05 and 35 of each hour, with missed-run persistence.
Each cycle verifies at most 100 artifacts using four isolated workers. The cycle lock
prevents concurrent coordinator runs. Download, schema and guide workers have
isolated mounts and cleared environments. Fresh fuzzing is not performed on
Atlas; recorded Actions evidence is reused.

Inspect with `systemctl --user status ap-pie-beta-intake.timer` and
`journalctl --user-unit ap-pie-beta-intake.service`.
Pause future publication with
`systemctl --user disable --now ap-pie-beta-intake.timer`.
This does not terminate an already-running service or remove published data.

The first timer-triggered receipt was `c0fd6178eb1542c1952f356c0d63a3c7`:
595 sources scanned without errors, three artifacts verified, discovery
published before evidence, then schemas and existing guide checks processed.
Beta served nine discovery versions and retained 172 guides afterward.

The original activation-relative timer retriggered during daemon reloads.
It was replaced on 2026-09-14 with the fixed wall-clock schedule above.
Installed configuration also refreshes the canonical index and all live open
PR heads before scanning, and reuses exact-checksum audit-cache/QA evidence.

The initial pilot receipt alone did not prove source coverage, uncached
security review handling or rollback. Subsequent cohort checks and real worker,
rollback and unattended receipts provide that evidence.
Production publication is unavailable through these fixed-container tools.

Uncached reviews use the existing trusted extractor/prompt and an outer bwrap
worker that cannot see application files, inherited environment, normal home
or Docker socket. Only provider login, source and private outputs are mounted.
Configure `--review-runner`, `--review-runtime`, `--review-auth`, and retain
`--review-limit 1` for bounded recurring model spend. Cache-only imports leave
missing results for that independent worker. Full reports stay private;
public evidence contains only exact archive identity, disposition and report
hash. Weak PASS coverage is downgraded. Existing holds are never cleared.

After the successful 100-candidate bulk receipt
`3d17c9f8e5d1477c98e2117f9db8cf9b`, recurring throughput is configured for
100 candidates and four isolated download workers. Selection spreads work
across modules and skips equivalent observations. The optional trusted
generation emitter collects already completed Actions runs for relevant PRs;
it never starts tests. Run `coverage.py --db STATE --prs QUEUED_PRS --out REPORT`
to see all source, PR-origin, hold and independent evidence gaps.

Index-stored artifacts are now queued using the canonical repository's full
commit SHA and `apworlds/` path. They require the same isolated archive and
checksum verification as release assets. Retired entries remain registered
without creating new downloads. Scanner classifications distinguish built-in,
retired and index-stored sources from missing mappings. The 2026-09-14 source
dry run found 103 stored-file version observations across 77 sources; a real
Twilight Princess 0.3.0 archive passed verification without package execution.
