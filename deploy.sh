#!/usr/bin/env bash
# deploy.sh - Deploy Archipelago Pie to a remote host
#
# Usage:
#   DEPLOY_SERVER=user@host bash deploy.sh              # git pull + docker compose up --build -d
#   DEPLOY_SERVER=user@host bash deploy.sh --no-pull    # skip git pull, just rebuild & restart
#   DEPLOY_SERVER=user@host bash deploy.sh --logs-only  # tail container logs (no deploy)
#
# Requirements: SSH key access to $DEPLOY_SERVER. Set DEPLOY_DIR if your
# checkout lives somewhere other than ~/ap-pie on the remote.

set -euo pipefail

: "${DEPLOY_SERVER:?Set DEPLOY_SERVER (e.g. user@host) - see comments at top of file}"
SERVER="$DEPLOY_SERVER"
REMOTE_DIR="${DEPLOY_DIR:-~/ap-pie}"
CONTAINER="${DEPLOY_CONTAINER:-ap-pie-ap-web-1}"
LOG_TAIL_SECONDS=20

# ── Parse flags ──────────────────────────────────────────────────
NO_PULL=false
LOGS_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --no-pull)   NO_PULL=true ;;
    --logs-only) LOGS_ONLY=true ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

# ── Helpers ──────────────────────────────────────────────────────
info()    { echo -e "\033[1;34m==>\033[0m $*"; }
success() { echo -e "\033[1;32m✔\033[0m  $*"; }
step()    { echo -e "\033[0;37m  $*\033[0m"; }

# ── Logs only ────────────────────────────────────────────────────
if $LOGS_ONLY; then
  info "Tailing logs on $SERVER..."
  ssh "$SERVER" "docker logs --tail 50 -f $CONTAINER"
  exit 0
fi

# ── Deploy ───────────────────────────────────────────────────────
info "Deploying Archipelago Pie → $SERVER:$REMOTE_DIR"
echo

# 1. Git pull
if $NO_PULL; then
  step "Skipping git pull (--no-pull)"
else
  info "Pulling latest code..."
  ssh "$SERVER" "cd $REMOTE_DIR && git pull --ff-only"
  success "Code up to date"
  echo
fi

# 2. Sync Archipelago binary to target version in .ap-version
if [[ -f "$(dirname "$0")/.ap-version" ]]; then
  TARGET_AP_VERSION="$(tr -d '[:space:]' < "$(dirname "$0")/.ap-version")"
  info "Checking Archipelago version on $SERVER (target: $TARGET_AP_VERSION)..."
  if ssh "$SERVER" "cd $REMOTE_DIR && bash scripts/fetch-archipelago.sh --check" | grep -q "Up to date"; then
    success "Archipelago $TARGET_AP_VERSION already installed"
  else
    info "Upgrading Archipelago to $TARGET_AP_VERSION..."
    ssh "$SERVER" "cd $REMOTE_DIR && bash scripts/fetch-archipelago.sh"
    success "Archipelago $TARGET_AP_VERSION installed"
  fi
  echo
fi

# 3. Docker build + restart
info "Building and restarting containers..."
ssh "$SERVER" "cd $REMOTE_DIR && docker compose up --build -d"
success "Containers restarted"
echo

# 4. Quick health check - wait for the app to respond
info "Waiting for app to come up..."
for i in $(seq 1 10); do
  if ssh "$SERVER" "curl -sf http://localhost:5001/api/health > /dev/null 2>&1"; then
    success "App is healthy (/api/health returned 200)"
    break
  fi
  if [ "$i" -eq 10 ]; then
    echo "  ⚠ App did not respond after 10s - check logs below"
  else
    step "  Attempt $i/10..."
    sleep 2
  fi
done
echo

# 5. Tail logs briefly
info "Recent container logs (last ${LOG_TAIL_SECONDS}s):"
echo "────────────────────────────────────────────────"
ssh "$SERVER" "docker logs --since ${LOG_TAIL_SECONDS}s $CONTAINER 2>&1 | tail -30"
echo "────────────────────────────────────────────────"
echo
success "Deploy complete!"
