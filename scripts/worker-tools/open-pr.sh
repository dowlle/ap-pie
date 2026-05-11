#!/usr/bin/env bash
# Edits dowlle/Archipelago-index to add a new APWorld version,
# pushes a branch, and opens a PR with audit + fuzz reports in the body.
#
# Usage: open-pr.sh <apworld_name> <version> <url> <sha256> <audit_log> <fuzz_log>
#
# Idempotent: if version is already in the TOML/lock, no-ops the edit
# (but still tries to open a PR; you'll get a no-diff error from gh).
set -euo pipefail

if [ $# -lt 6 ]; then
  echo "Usage: $0 <apworld_name> <version> <url> <sha256> <audit_log> <fuzz_log>" >&2
  exit 2
fi

APWORLD_NAME="$1"
VERSION="$2"
URL="$3"
SHA="$4"
AUDIT_LOG="$5"
FUZZ_LOG="$6"

INDEX_DIR="$HOME/Archipelago-index"
TOML_PATH="$INDEX_DIR/index/${APWORLD_NAME}.toml"

if [ ! -d "$INDEX_DIR" ]; then
  echo "ERROR: $INDEX_DIR not present. Run 'gh repo clone dowlle/Archipelago-index ~/Archipelago-index' first." >&2
  exit 3
fi
if [ ! -f "$TOML_PATH" ]; then
  echo "ERROR: $TOML_PATH not in index. This script handles add-version-to-existing-TOML; brand-new-game flow is separate." >&2
  exit 3
fi
for p in "$AUDIT_LOG" "$FUZZ_LOG"; do
  if [ ! -f "$p" ]; then
    echo "ERROR: log not found: $p" >&2
    exit 3
  fi
done

cd "$INDEX_DIR"
echo ">>> Syncing with origin"
git fetch origin --quiet
git checkout main --quiet
git pull origin main --quiet --ff-only

BRANCH="add-${APWORLD_NAME}-${VERSION}"
git branch -D "$BRANCH" 2>/dev/null || true
git checkout -b "$BRANCH" --quiet

# Edit TOML: append "VERSION" = {} under [versions]
python3 - "$TOML_PATH" "$VERSION" <<'PYEOF'
import re, sys
toml_path, version = sys.argv[1], sys.argv[2]
with open(toml_path) as f:
    text = f.read()
new_line = f'"{version}" = {{}}'
if f'"{version}"' in text:
    print(f"TOML: version {version} already present, no-op")
    sys.exit(0)
m = re.search(r'(\[versions\]\n(?:.*\n)*?)(?=\n\[|\Z)', text)
if m:
    block = m.group(1)
    text = text.replace(block, block.rstrip('\n') + '\n' + new_line + '\n', 1)
else:
    text = text.rstrip() + '\n\n[versions]\n' + new_line + '\n'
with open(toml_path, 'w') as f:
    f.write(text)
print(f"TOML: appended {new_line}")
PYEOF

# Edit index.lock: append "VERSION" = "SHA" under [APWORLD_NAME]
python3 - "$INDEX_DIR/index.lock" "$APWORLD_NAME" "$VERSION" "$SHA" <<'PYEOF'
import re, sys
lock_path, apworld, version, sha = sys.argv[1:]
with open(lock_path) as f:
    text = f.read()
new_line = f'"{version}" = "{sha}"'
patterns = [
    (rf'^(\[{re.escape(apworld)}\]\n(?:.*\n)*?)(?=\n\[|\Z)', f'[{apworld}]'),
    (rf'^(\["{re.escape(apworld)}"\]\n(?:.*\n)*?)(?=\n\[|\Z)', f'["{apworld}"]'),
]
done = False
for pat, header in patterns:
    m = re.search(pat, text, re.MULTILINE)
    if not m:
        continue
    block = m.group(1)
    if f'"{version}"' in block:
        print(f"LOCK: version {version} already in {header}, no-op")
        done = True
        break
    new_block = block.rstrip('\n') + '\n' + new_line + '\n'
    text = text.replace(block, new_block, 1)
    print(f"LOCK: appended {new_line} to {header}")
    done = True
    break
if not done:
    text = text.rstrip() + f'\n\n[{apworld}]\n{new_line}\n'
    print(f"LOCK: created [{apworld}] section")
with open(lock_path, 'w') as f:
    f.write(text)
PYEOF

echo ""
echo ">>> Diff:"
git --no-pager diff

if [ -z "$(git status --porcelain)" ]; then
  echo ""
  echo ">>> No changes to commit (version already in index?). Aborting."
  exit 4
fi

echo ""
echo ">>> Committing + pushing branch $BRANCH"
git add "$TOML_PATH" index.lock
git commit -m "Add ${APWORLD_NAME} ${VERSION}" --quiet
git push -u origin "$BRANCH" --quiet --force-with-lease

# Extract slim sections from audit log (NEVER embed the full report in the PR
# body — it leaks both the auditor's catalog of patterns checked and any
# absolute paths the log captured). Full report stays on the worker host for
# private review. Public PR shows only Verdict + Summary + Verdict rationale.
AUDIT_VERDICT_LINE=$(grep -E '^### Verdict:' "$AUDIT_LOG" | head -1 | sed 's/### Verdict: */**/' | sed 's/ *$/**/')
AUDIT_SUMMARY=$(awk '/^### Summary$/{flag=1;next} /^### /{flag=0} flag' "$AUDIT_LOG" | sed '/^[[:space:]]*$/d')
AUDIT_RATIONALE=$(awk '/^### Verdict rationale$/{flag=1;next} /^### /{flag=0} flag' "$AUDIT_LOG" | sed '/^[[:space:]]*$/d' | head -10)

# Extract slim fuzz verdict (just counts + multiplier — no paths, no per-check
# breakdown, no worker-host details).
FUZZ_VERDICT_LINE=$(grep -E '^RESULT:' "$FUZZ_LOG" | tail -1 | awk '{print $2}')
FUZZ_PASSED=$(grep -E '^CHECKS_PASSED:' "$FUZZ_LOG" | tail -1 | awk '{print $2}')
FUZZ_TOTAL=$(grep -E '^CHECKS_TOTAL:' "$FUZZ_LOG" | tail -1 | awk '{print $2}')
FUZZ_MULT=$(grep -E '^MULTIPLIER:' "$FUZZ_LOG" | tail -1 | awk '{print $2}')

# Build PR body
PR_BODY_FILE="$(mktemp)"
{
  echo "## Add ${APWORLD_NAME} ${VERSION}"
  echo ""
  echo "- **Source URL:** ${URL}"
  echo "- **SHA-256:** \`${SHA}\`"
  echo ""
  echo "### Security audit"
  echo ""
  echo "${AUDIT_VERDICT_LINE:-**Verdict: UNKNOWN**}"
  echo ""
  if [ -n "$AUDIT_SUMMARY" ]; then
    echo "$AUDIT_SUMMARY"
    echo ""
  fi
  if [ -n "$AUDIT_RATIONALE" ]; then
    echo "$AUDIT_RATIONALE"
    echo ""
  fi
  echo "### Runtime fuzz"
  echo ""
  echo "**Verdict: ${FUZZ_VERDICT_LINE:-UNKNOWN}** -- ${FUZZ_PASSED:-?}/${FUZZ_TOTAL:-?} checks passed at ${FUZZ_MULT:-?}x multiplier."
  echo ""
  echo "---"
  echo "*Audit + fuzz logs are kept privately; this body intentionally omits the audit catalog and per-check breakdowns. Reach the maintainer for the full reports.*"
} > "$PR_BODY_FILE"

PR_URL=$(gh pr create \
  --repo dowlle/Archipelago-index \
  --base main \
  --head "$BRANCH" \
  --title "Add ${APWORLD_NAME} ${VERSION}" \
  --body-file "$PR_BODY_FILE")

rm -f "$PR_BODY_FILE"

echo ""
echo "=== PR OPENED ==="
echo "PR_URL: $PR_URL"
echo "BRANCH: $BRANCH"
