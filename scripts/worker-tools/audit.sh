#!/usr/bin/env bash
# Wraps the FEAT-19 auditor for a URL. Prints structured tail block:
#   AUDIT_VERDICT: PASS|NEEDS_REVIEW|FAIL
#   AUDIT_LOG: <path>
# Exits non-zero only on auditor crash, not on FAIL verdict.
set -o pipefail

# audit.py shells out to the `claude` CLI which on the worker host lives at
# ~/.local/bin/claude (Atlas convention). Under `ssh host '<cmd>'` (non-login
# shell) ~/.local/bin is not on PATH and audit.py crashes with
# FileNotFoundError('claude'). Explicitly extend PATH so audit.sh works in
# both interactive and command-mode SSH without needing `bash -lc` wrapping.
export PATH="$HOME/.local/bin:$PATH"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <url> [out_dir]" >&2
  exit 2
fi
URL="$1"
OUT_DIR="${2:-$HOME/apworld-tools/runs/audit-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT_DIR"
LOG="$OUT_DIR/audit.log"
cd ~/apworld-auditor

# Important: DO NOT pipe audit.py through `| tee`. Empirically (Atlas
# 2026-05-11, claude 2.1.129) the piped-stdout context propagates through
# `subprocess.run(capture_output=True)` inside audit.py and trips Claude
# Code to exit 1 with empty stderr, even though audit.py's internal pipes
# look identical either way. `>` redirect avoids the issue. We lose the
# live console mirror, but process-request.sh echoes the tail block below
# and the full log is preserved at $LOG for the PR body.
python3 audit.py url "$URL" > "$LOG" 2>&1

VERDICT=$(grep -E '^### Verdict:' "$LOG" | head -1 | awk '{print $3}')
echo ""
echo "=== AUDIT TAIL ==="
echo "AUDIT_VERDICT: ${VERDICT:-UNKNOWN}"
echo "AUDIT_LOG: $LOG"
