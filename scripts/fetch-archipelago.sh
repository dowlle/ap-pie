#!/usr/bin/env bash
# fetch-archipelago.sh - Install or upgrade the Archipelago binary that ap-web mounts
#
# Reads the target version from .ap-version (repo root) unless overridden.
# Downloads the Linux x86_64 tarball from GitHub Releases, verifies SHA256
# against the release manifest, and extracts it to $AP_INSTALL_PATH.
#
# Usage:
#   ./scripts/fetch-archipelago.sh                # install version from .ap-version
#   ./scripts/fetch-archipelago.sh 0.6.8          # override version
#   ./scripts/fetch-archipelago.sh --check        # print current vs target, no changes
#   ./scripts/fetch-archipelago.sh --no-backup    # skip backup of previous install
#   ./scripts/fetch-archipelago.sh --force        # reinstall even if versions match
#
# Environment:
#   AP_INSTALL_PATH  - install target (default: $HOME/archipelago-install/Archipelago)
#
# Exit codes:
#   0  success / already at target
#   1  fatal (download/verify/extract failure)
#   2  bad arguments

set -euo pipefail

# ── Config ───────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="$REPO_ROOT/.ap-version"
INSTALL_PATH="${AP_INSTALL_PATH:-$HOME/archipelago-install/Archipelago}"
GH_API="https://api.github.com/repos/ArchipelagoMW/Archipelago/releases/tags"
GH_DL="https://github.com/ArchipelagoMW/Archipelago/releases/download"
ASSET_TEMPLATE="Archipelago_%s_linux-x86_64.tar.gz"

# ── Helpers ──────────────────────────────────────────────────────
info()    { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
step()    { printf '  %s\n' "$*"; }
success() { printf '\033[1;32m✔\033[0m  %s\n' "$*"; }
warn()    { printf '\033[1;33m⚠\033[0m  %s\n' "$*" >&2; }
fatal()   { printf '\033[1;31m✖\033[0m  %s\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || fatal "Required command not found: $1"; }

# ── Parse args ───────────────────────────────────────────────────
CHECK_ONLY=false
NO_BACKUP=false
FORCE=false
OVERRIDE_VERSION=""

for arg in "$@"; do
  case "$arg" in
    --check)     CHECK_ONLY=true ;;
    --no-backup) NO_BACKUP=true ;;
    --force)     FORCE=true ;;
    --help|-h)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    -*)
      echo "Unknown flag: $arg" >&2; exit 2 ;;
    *)
      if [[ -n "$OVERRIDE_VERSION" ]]; then
        echo "Too many positional args" >&2; exit 2
      fi
      OVERRIDE_VERSION="$arg" ;;
  esac
done

# ── Resolve target version ───────────────────────────────────────
if [[ -n "$OVERRIDE_VERSION" ]]; then
  TARGET_VERSION="$OVERRIDE_VERSION"
elif [[ -f "$VERSION_FILE" ]]; then
  TARGET_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
else
  fatal "No .ap-version found at $VERSION_FILE and no version arg given"
fi

[[ "$TARGET_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-rc[0-9]+)?$ ]] \
  || fatal "Invalid version format: $TARGET_VERSION (expected X.Y.Z or X.Y.Z-rcN)"

# ── Detect current installed version ─────────────────────────────
# Tried in order:
#   1. .installed-ap-version marker (written by this script)
#   2. Utils.py __version__ (source installs)
#   3. Most recent Launcher log line "Archipelago (X.Y.Z) logging initialized"
current_installed_version() {
  if [[ -f "$INSTALL_PATH/.installed-ap-version" ]]; then
    tr -d '[:space:]' < "$INSTALL_PATH/.installed-ap-version"
    return
  fi
  if [[ -f "$INSTALL_PATH/Utils.py" ]]; then
    grep -E '^__version__' "$INSTALL_PATH/Utils.py" 2>/dev/null \
      | head -1 | sed -E 's/.*"([^"]+)".*/\1/'
    return
  fi
  local latest_log
  latest_log="$(ls -t "$INSTALL_PATH/logs/"Launcher_*.txt 2>/dev/null | head -1 || true)"
  if [[ -n "$latest_log" ]]; then
    grep -m1 -oE 'Archipelago \([0-9]+\.[0-9]+\.[0-9]+[^)]*\)' "$latest_log" 2>/dev/null \
      | head -1 | sed -E 's/.*\(([^)]+)\).*/\1/'
    return
  fi
  echo ""
}

CURRENT_VERSION="$(current_installed_version || true)"

# ── Check mode ───────────────────────────────────────────────────
if $CHECK_ONLY; then
  info "Archipelago version check"
  step "Install path:  $INSTALL_PATH"
  step "Installed:     ${CURRENT_VERSION:-(none)}"
  step "Target:        $TARGET_VERSION"
  if [[ "$CURRENT_VERSION" == "$TARGET_VERSION" ]]; then
    success "Up to date"
  else
    warn "Out of date - run without --check to upgrade"
  fi
  exit 0
fi

# ── Idempotence ──────────────────────────────────────────────────
if [[ "$CURRENT_VERSION" == "$TARGET_VERSION" ]] && ! $FORCE; then
  success "Already at $TARGET_VERSION (use --force to reinstall)"
  exit 0
fi

# ── Preflight ────────────────────────────────────────────────────
need curl
need tar
need sha256sum

info "Fetching Archipelago $TARGET_VERSION"
step "Install path:  $INSTALL_PATH"
step "Current:       ${CURRENT_VERSION:-(none)}"
step "Target:        $TARGET_VERSION"

ASSET_NAME="$(printf "$ASSET_TEMPLATE" "$TARGET_VERSION")"
DL_URL="$GH_DL/$TARGET_VERSION/$ASSET_NAME"
TMP="$(mktemp -d -t ap-fetch-XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

# ── Resolve SHA256 from GitHub API ───────────────────────────────
info "Looking up SHA256 from release manifest..."
MANIFEST="$TMP/release.json"
if ! curl -fsSL "$GH_API/$TARGET_VERSION" -o "$MANIFEST"; then
  fatal "Could not fetch release manifest for $TARGET_VERSION (is the tag published?)"
fi

# Extract digest for our asset (format: "sha256:<hex>")
EXPECTED_SHA=""
if command -v jq >/dev/null 2>&1; then
  EXPECTED_SHA="$(jq -r --arg name "$ASSET_NAME" \
    '.assets[] | select(.name == $name) | .digest' "$MANIFEST" \
    | sed 's/^sha256://')"
elif command -v python3 >/dev/null 2>&1; then
  # python3 fallback: parses JSON properly and filters by asset name, same
  # semantics as the jq path. Avoids the "first digest in manifest" bug the
  # previous grep fallback had, which silently picked the wrong asset's SHA
  # whenever a release shipped multi-platform tarballs.
  EXPECTED_SHA="$(MANIFEST_PATH="$MANIFEST" TARGET_ASSET="$ASSET_NAME" python3 - <<'PY'
import json, os, sys
with open(os.environ["MANIFEST_PATH"]) as f:
    data = json.load(f)
target = os.environ["TARGET_ASSET"]
for asset in data.get("assets", []):
    if asset.get("name") == target:
        digest = asset.get("digest", "")
        if digest.startswith("sha256:"):
            print(digest[7:])
        sys.exit(0)
PY
)"
else
  fatal "Neither jq nor python3 found on this host. Install one (e.g. apt install jq) so the SHA256 can be resolved unambiguously by asset name. Refusing to fall back to a grep-based heuristic that could pick the wrong asset's digest."
fi

[[ -n "$EXPECTED_SHA" && "$EXPECTED_SHA" =~ ^[a-f0-9]{64}$ ]] \
  || fatal "Could not resolve SHA256 for $ASSET_NAME from release manifest"

step "Expected SHA:  $EXPECTED_SHA"

# ── Download ─────────────────────────────────────────────────────
info "Downloading $ASSET_NAME..."
curl -fL --progress-bar -o "$TMP/$ASSET_NAME" "$DL_URL" \
  || fatal "Download failed from $DL_URL"

# ── Verify ───────────────────────────────────────────────────────
info "Verifying SHA256..."
ACTUAL_SHA="$(sha256sum "$TMP/$ASSET_NAME" | awk '{print $1}')"
if [[ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]]; then
  fatal "Checksum mismatch! expected=$EXPECTED_SHA actual=$ACTUAL_SHA"
fi
success "Checksum verified"

# ── Extract ──────────────────────────────────────────────────────
info "Extracting..."
EXTRACT_DIR="$TMP/extract"
mkdir -p "$EXTRACT_DIR"
tar -xzf "$TMP/$ASSET_NAME" -C "$EXTRACT_DIR"

# The tarball extracts to a directory like "Archipelago/" - find it
NEW_INSTALL="$(find "$EXTRACT_DIR" -maxdepth 2 -type d -name 'Archipelago' | head -1)"
[[ -n "$NEW_INSTALL" && -d "$NEW_INSTALL" ]] \
  || fatal "Could not locate 'Archipelago' directory inside extracted tarball"

# ── Swap in ──────────────────────────────────────────────────────
PARENT_DIR="$(dirname "$INSTALL_PATH")"
mkdir -p "$PARENT_DIR"

if [[ -d "$INSTALL_PATH" ]]; then
  if $NO_BACKUP; then
    info "Removing previous install (no backup)..."
    rm -rf "$INSTALL_PATH"
  else
    BACKUP="$INSTALL_PATH.bak-${CURRENT_VERSION:-prev}-$(date +%Y%m%d-%H%M%S)"
    info "Backing up previous install → $BACKUP"
    mv "$INSTALL_PATH" "$BACKUP"
  fi
fi

info "Installing to $INSTALL_PATH..."
mv "$NEW_INSTALL" "$INSTALL_PATH"

# Ensure executable bits on the binaries that ap-web calls
for bin in ArchipelagoServer ArchipelagoGenerate; do
  [[ -f "$INSTALL_PATH/$bin" ]] && chmod +x "$INSTALL_PATH/$bin" || true
done

# Drop version marker for future --check runs
echo "$TARGET_VERSION" > "$INSTALL_PATH/.installed-ap-version"

success "Archipelago $TARGET_VERSION installed at $INSTALL_PATH"
info "Next: restart ap-web so the container picks up the new binary"
step "  docker compose up --build -d"
