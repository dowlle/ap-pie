#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

remote="${AP_PIE_BACKUP_REMOTE:-stef@178.104.97.246:/home/stef/backups/ap-pie/}"
backup_root="${AP_PIE_BACKUP_OFFSITE_DIR:-/home/stef/backups/ap-pie-database}"
gpg_home="${AP_PIE_BACKUP_PRIVATE_GPG_HOME:-/home/stef/.local/share/ap-pie-backup-gnupg-private}"
lock_file="${AP_PIE_BACKUP_PULL_LOCK_FILE:-/home/stef/.cache/ap-pie-backup-pull.lock}"

exec 9>"$lock_file"
flock -n 9 || exit 0
mkdir -p "$backup_root"

rsync -a --delete-delay "$remote" "$backup_root/"

for stack in prod beta; do
    newest="$(find "$backup_root/$stack" -maxdepth 1 -type f -name '*.dump.gpg' -printf '%T@ %p\n' \
        | sort -n | tail -1 | cut -d' ' -f2-)"
    [[ -n "$newest" ]] || { echo "No $stack backup found" >&2; exit 1; }
    (cd "$(dirname "$newest")" && sha256sum --check "$(basename "$newest").sha256")

    container="ap-pie-restore-test-$stack"
    docker rm -f "$container" >/dev/null 2>&1 || true
    docker run -d --name "$container" \
        -e POSTGRES_PASSWORD=restore-test-only \
        postgres:17-alpine >/dev/null
    cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
    trap cleanup EXIT

    ready=0
    for _ in $(seq 1 30); do
        if docker exec "$container" pg_isready -U postgres >/dev/null 2>&1; then
            ready=1
            break
        fi
        sleep 1
    done
    [[ "$ready" = 1 ]] || { echo "Restore-test PostgreSQL did not start" >&2; exit 1; }

    gpg --homedir "$gpg_home" --batch --quiet --decrypt "$newest" \
      | docker exec -i "$container" pg_restore \
            --username postgres --dbname postgres --no-owner --no-acl --exit-on-error
    docker exec "$container" psql -U postgres -d postgres -Atc \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" \
      | awk '$1 >= 10 { ok=1 } END { exit !ok }'
    cleanup
    trap - EXIT
done

printf 'verified_at=%s\n' "$(date -u +%Y%m%dT%H%M%SZ)" > "$backup_root/last-restore-test"
