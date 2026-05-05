#!/usr/bin/env bash
# End-to-end APWorld index request: audit -> fuzz -> open PR.
#
# Usage: process-request.sh <url> <apworld_name> <version> [multiplier] [--dry-run]
#   url           HTTPS URL to the .apworld
#   apworld_name  TOML basename in the index (e.g. Schedule_I, x2wotc)
#   version       Version string to add (e.g. 3.6.0)
#   multiplier    Fuzz multiplier (default 1.0). Use 0.01 for a smoke test.
#   --dry-run     Run audit + fuzz, skip PR open. Exit 0 on both passing.
#
# Both gates must pass before a PR is opened. If either fails, the
# script exits non-zero with the failing verdict. Reports are kept under
# ~/apworld-tools/runs/<TS>-<APWORLD>-<VERSION>/.
set -o pipefail

if [ $# -lt 3 ]; then
  echo "Usage: $0 <url> <apworld_name> <version> [multiplier] [--dry-run]" >&2
  exit 2
fi

URL="$1"
APWORLD_NAME="$2"
VERSION="$3"
MULT="1.0"
DRY_RUN=false
shift 3
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ]; then
    DRY_RUN=true
  else
    MULT="$arg"
  fi
done

TOOLS_DIR="$HOME/apworld-tools"
TS="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$TOOLS_DIR/runs/${TS}-${APWORLD_NAME}-${VERSION}"
mkdir -p "$RUN_DIR"
echo "Run dir: $RUN_DIR"
echo ""

# ── Phase 1: Audit ──
echo ">>> Phase 1/3: Security audit"
"$TOOLS_DIR/audit.sh" "$URL" "$RUN_DIR"
AUDIT_VERDICT=$(grep -E '^AUDIT_VERDICT:' "$RUN_DIR/audit.log" 2>/dev/null | tail -1 | awk '{print $2}' || true)
# Fallback: the audit report itself emits "### Verdict: PASS"
if [ -z "$AUDIT_VERDICT" ]; then
  AUDIT_VERDICT=$(grep -E '^### Verdict:' "$RUN_DIR/audit.log" | head -1 | awk '{print $3}' || true)
fi
echo ""
echo "Audit verdict: ${AUDIT_VERDICT:-UNKNOWN}"
echo ""

# ── Phase 2: Fuzz ──
echo ">>> Phase 2/3: Bananium fuzz suite (multiplier=$MULT)"
FUZZ_LOG="$RUN_DIR/fuzz.log"
set +e
"$HOME/apworld-fuzzer/run-fuzz.sh" "$URL" "$APWORLD_NAME" "$MULT" 2>&1 | tee "$FUZZ_LOG"
set -e
FUZZ_VERDICT=$(grep -E '^RESULT:' "$FUZZ_LOG" | tail -1 | awk '{print $2}' || true)
SHA=$(grep -E '^SOURCE_SHA256:' "$FUZZ_LOG" | tail -1 | awk '{print $2}' || true)
echo ""
echo "Fuzz verdict: ${FUZZ_VERDICT:-UNKNOWN}"
echo "SHA-256: ${SHA:-UNKNOWN}"
echo ""

# ── Gate ──
if [ "$AUDIT_VERDICT" != "PASS" ] || [ "$FUZZ_VERDICT" != "PASS" ]; then
  echo "=================================="
  echo ">>> GATE FAILED"
  echo "  audit: ${AUDIT_VERDICT:-UNKNOWN}"
  echo "  fuzz:  ${FUZZ_VERDICT:-UNKNOWN}"
  echo "Reports: $RUN_DIR"
  echo "Will NOT open a PR."
  echo "=================================="
  exit 1
fi

if $DRY_RUN; then
  echo ""
  echo "=================================="
  echo ">>> Both gates PASSED (--dry-run, skipping PR open)"
  echo "Reports: $RUN_DIR"
  echo "=================================="
  exit 0
fi

# ── Phase 3: Open PR ──
echo ">>> Phase 3/3: Opening PR on dowlle/Archipelago-index"
echo ""
"$TOOLS_DIR/open-pr.sh" "$APWORLD_NAME" "$VERSION" "$URL" "$SHA" \
  "$RUN_DIR/audit.log" "$FUZZ_LOG" 2>&1 | tee "$RUN_DIR/pr.log"

PR_URL=$(grep -E '^PR_URL:' "$RUN_DIR/pr.log" | tail -1 | awk '{print $2}' || true)
echo "$PR_URL" > "$RUN_DIR/pr-url.txt"

echo ""
echo "=================================="
echo ">>> DONE"
echo "  audit:    PASS"
echo "  fuzz:     PASS ($MULT x)"
echo "  PR:       $PR_URL"
echo "  reports:  $RUN_DIR"
echo "=================================="
