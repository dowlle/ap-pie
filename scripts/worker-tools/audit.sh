#!/usr/bin/env bash
# Wraps the FEAT-19 auditor for a URL. Prints structured tail block:
#   AUDIT_VERDICT: PASS|NEEDS_REVIEW|FAIL
#   AUDIT_LOG: <path>
# Exits non-zero only on auditor crash, not on FAIL verdict.
set -o pipefail
if [ $# -lt 1 ]; then
  echo "Usage: $0 <url> [out_dir]" >&2
  exit 2
fi
URL="$1"
OUT_DIR="${2:-$HOME/apworld-tools/runs/audit-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT_DIR"
LOG="$OUT_DIR/audit.log"
cd ~/apworld-auditor
python3 audit.py url "$URL" 2>&1 | tee "$LOG"
VERDICT=$(grep -E '^### Verdict:' "$LOG" | head -1 | awk '{print $3}')
echo ""
echo "=== AUDIT TAIL ==="
echo "AUDIT_VERDICT: ${VERDICT:-UNKNOWN}"
echo "AUDIT_LOG: $LOG"
