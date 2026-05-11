#!/usr/bin/env bash
# End-to-end APWorld index request: audit -> smoke fuzz -> production fuzz -> open PR.
#
# Usage: process-request.sh <url> <apworld_name> <version> [multiplier] [--dry-run]
#   url           HTTPS URL to the .apworld
#   apworld_name  TOML basename in the index (e.g. Schedule_I, x2wotc)
#   version       Version string to add (e.g. 3.6.0)
#   multiplier    Production fuzz multiplier (default 1.0). Use 0.01 for a manual smoke test.
#   --dry-run     Run gates, skip PR open. Exit 0 if all gates pass.
#
# Environment:
#   SMOKE_MULT    Smoke-pass multiplier (default 0.05). Runs BEFORE the production
#                 fuzz; if it fails, we skip the expensive 1.0x run and exit early.
#                 Set to "0" to disable the smoke pass entirely (matches pre-2026-05-11
#                 behavior). Smoke is a pre-filter only; it never replaces the
#                 production gate per the briefing rule.
#
# All gates must pass before a PR is opened. Reports are kept under
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
SMOKE_MULT="${SMOKE_MULT:-0.05}"
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

# Vault archive helper: writes a markdown-wrapped copy of an audit or fuzz
# log into the AP-Pie Audits dir of the local Obsidian vault, which
# bidirectional `ob sync` (Obsidian Sync) then propagates to the maintainer's
# workstation automatically. Silent no-op if the vault path doesn't exist
# (e.g. running on a host without sync configured).
VAULT_AUDITS_DIR="$HOME/vaults/stefappelhof/11-Dev/AP-Pie/Audits"

archive_to_vault() {
  # Usage: archive_to_vault <kind> <log_path> <verdict>
  #   kind     - "audit" or "fuzz"
  #   log_path - source log to embed
  #   verdict  - PASS / FAIL / NEEDS_REVIEW / etc.
  #
  # Layout:  <vault>/Audits/<apworld>/<version> — <Audit|Fuzz>.md
  # One file per kind per version. Re-running the chain on the same
  # version overwrites (git/obsidian history is the audit trail).
  local kind="$1"
  local log_path="$2"
  local verdict="$3"

  [ -d "$VAULT_AUDITS_DIR" ] || return 0
  [ -f "$log_path" ] || return 0

  local date_today
  date_today=$(date +%Y-%m-%d)
  local kind_cap sibling_kind sibling_kind_cap
  if [ "$kind" = "audit" ]; then
    kind_cap="Audit"
    sibling_kind="fuzz"
    sibling_kind_cap="Fuzz"
  else
    kind_cap="Fuzz"
    sibling_kind="audit"
    sibling_kind_cap="Audit"
  fi
  local apworld_dir="${VAULT_AUDITS_DIR}/${APWORLD_NAME}"
  mkdir -p "$apworld_dir"
  local target="${apworld_dir}/${VERSION} — ${kind_cap}.md"
  # Vault-relative wikilink to the sibling report (Obsidian resolves the
  # full path even when names alone would collide across apworlds).
  local sibling_link="[[11-Dev/AP-Pie/Audits/${APWORLD_NAME}/${VERSION} — ${sibling_kind_cap}|${sibling_kind_cap} report]]"

  {
    echo "---"
    echo "type: audit-report"
    echo "kind: $kind"
    echo "date: \"$date_today\""
    echo "apworld: $APWORLD_NAME"
    echo "version: \"$VERSION\""
    echo "verdict: ${verdict:-UNKNOWN}"
    echo "source_url: $URL"
    echo "project: AP-Pie"
    echo "tags: [ap-pie, audit-report, $kind]"
    echo "---"
    echo ""
    echo "# ${kind_cap} — $APWORLD_NAME $VERSION"
    echo ""
    echo "- **Source URL:** $URL"
    echo "- **Verdict:** **${verdict:-UNKNOWN}**"
    echo "- **Sibling:** $sibling_link"
    echo "- **Generated:** $(date -u +%Y-%m-%dT%H:%M:%SZ) by automated worker chain"
    echo ""
    echo "## Full log"
    echo ""
    echo '```'
    cat "$log_path"
    echo '```'
  } > "$target"
  echo "Vault archive: $target"
}

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

# Archive audit to vault regardless of verdict — NEEDS_REVIEW and FAIL
# are exactly the cases worth eyeballing.
archive_to_vault audit "$RUN_DIR/audit.log" "${AUDIT_VERDICT:-UNKNOWN}"

# ── Phase 2a: Smoke fuzz (pre-filter) ──
# Cheap-but-real pass at SMOKE_MULT to catch obviously-broken APWorlds
# before we commit ~30-60 min of CPU to the 1.0x production run. NOT a
# production gate per the briefing rule; the 1.0x run below still has to
# pass before we open a PR.
if [ "$SMOKE_MULT" != "0" ] && [ "$SMOKE_MULT" != "" ]; then
  echo ">>> Phase 2a/4: Smoke fuzz at ${SMOKE_MULT}x (pre-filter)"
  SMOKE_LOG="$RUN_DIR/fuzz-smoke.log"
  set +e
  "$HOME/apworld-fuzzer/run-fuzz.sh" "$URL" "$APWORLD_NAME" "$SMOKE_MULT" 2>&1 | tee "$SMOKE_LOG"
  set -e
  SMOKE_VERDICT=$(grep -E '^RESULT:' "$SMOKE_LOG" | tail -1 | awk '{print $2}' || true)
  echo ""
  echo "Smoke verdict: ${SMOKE_VERDICT:-UNKNOWN}"
  echo ""
  if [ "$SMOKE_VERDICT" != "PASS" ]; then
    # Archive the smoke fuzz log to vault BEFORE exiting — failures are
    # exactly what we want to see in the vault.
    archive_to_vault fuzz "$SMOKE_LOG" "${SMOKE_VERDICT:-UNKNOWN}"
    echo "=================================="
    echo ">>> GATE FAILED (at smoke pre-filter)"
    echo "  audit: ${AUDIT_VERDICT:-UNKNOWN}"
    echo "  smoke: ${SMOKE_VERDICT:-UNKNOWN} (multiplier=$SMOKE_MULT)"
    echo "Skipping the ${MULT}x production fuzz to save CPU."
    echo "Reports: $RUN_DIR"
    echo "Will NOT open a PR."
    echo "=================================="
    exit 1
  fi
fi

# ── Phase 2b: Production fuzz ──
echo ">>> Phase 2b/4: Bananium fuzz suite (multiplier=$MULT)"
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

# Archive production fuzz to vault (overwrites the smoke archive — production
# is the canonical reference).
archive_to_vault fuzz "$FUZZ_LOG" "${FUZZ_VERDICT:-UNKNOWN}"

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
  echo ">>> All gates PASSED (--dry-run, skipping PR open)"
  echo "Reports: $RUN_DIR"
  echo "=================================="
  exit 0
fi

# ── Phase 3: Open PR ──
echo ">>> Phase 3/4: Opening PR on dowlle/Archipelago-index"
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
