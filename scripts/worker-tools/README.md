# Worker tools

Scripts for the off-server worker that processes APWorld index requests
captured by AP-Pie's Phase 0a admin queue (FEAT-30). The worker runs
both gates (Claude security audit + Eijebong runtime fuzzer) on an
isolated host with no inbound surface, then opens a PR on
`dowlle/Archipelago-index` with the verdicts in the body.

These scripts are deployed manually to the worker host's
`~/apworld-tools/` directory. They expect:

- `~/apworld-auditor/` -- the FEAT-19 auditor checkout (`audit.py`)
- `~/apworld-fuzzer/` -- AP-from-source + `fuzz.py` + the bananium hooks
  (see `~/apworld-fuzzer/run-fuzz.sh`)
- `~/Archipelago-index/` -- a clone of `dowlle/Archipelago-index`
- `gh` CLI authed for `dowlle` with `repo` scope

## Scripts

### `audit.sh <url> [out_dir]`

Wraps the FEAT-19 auditor for a URL. Tees the auditor's output to
`<out_dir>/audit.log`, then prints a structured tail block:

```
AUDIT_VERDICT: PASS|NEEDS_REVIEW|FAIL
AUDIT_LOG: <path>
```

Exits non-zero only on auditor crash, not on a FAIL verdict.

### `open-pr.sh <apworld_name> <version> <url> <sha256> <audit_log> <fuzz_log>`

Edits `~/Archipelago-index/index/<apworld_name>.toml` to add the new
version row, edits `index.lock` to add the SHA, commits + pushes a
branch (`add-<apworld_name>-<version>`), and opens a PR on
`dowlle/Archipelago-index` with both reports embedded in the PR body
(in `<details>` blocks). Idempotent on the file edits; refuses to
push if there's no diff.

### `process-request.sh <url> <apworld_name> <version> [multiplier] [--dry-run]`

The end-to-end orchestrator. Runs `audit.sh`, runs the fuzz suite
(`~/apworld-fuzzer/run-fuzz.sh` at the given multiplier; default 1.0),
gates on both passing, and on success calls `open-pr.sh`. Bails before
PR open if either gate fails. With `--dry-run`, runs both gates and
prints verdicts but does not open a PR.

Per-request artifacts land under `~/apworld-tools/runs/<TS>-<APWORLD>-<VERSION>/`.

## Phase 1 plans

These are designed to be reused by the polling worker. The polling
loop will:

1. `GET` pending+approved requests from ap-pie via outbound HTTPS
2. For each one, invoke `process-request.sh`
3. `PATCH` the verdicts + PR URL back to ap-pie

No `gh` credentials live on the AP-Pie web tier. All write capability
stays on the worker host.
