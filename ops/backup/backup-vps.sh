#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

backup_root="${AP_PIE_BACKUP_DIR:-/home/stef/backups/ap-pie}"
gpg_home="${AP_PIE_BACKUP_GPG_HOME:-/home/stef/.local/share/ap-pie-backup-gnupg-public}"
recipient_file="${AP_PIE_BACKUP_RECIPIENT_FILE:-/home/stef/.config/ap-pie-backup/recipient}"
retention_days="${AP_PIE_BACKUP_RETENTION_DAYS:-14}"
lock_file="${AP_PIE_BACKUP_LOCK_FILE:-/home/stef/.cache/ap-pie-backup.lock}"

exec 9>"$lock_file"
flock -n 9 || exit 0

[[ -r "$recipient_file" ]] || { echo "Missing backup recipient file" >&2; exit 1; }
recipient="$(tr -d '[:space:]' < "$recipient_file")"
[[ -n "$recipient" ]] || { echo "Empty backup recipient" >&2; exit 1; }

mkdir -p "$backup_root/prod" "$backup_root/beta"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

dump_stack() {
    local stack="$1"
    local container="$2"
    local target="$backup_root/$stack/$stamp.dump.gpg"
    local temporary="$target.partial"

    docker inspect "$container" >/dev/null
    docker exec "$container" pg_dump \
        --username archipelago \
        --dbname archipelago \
        --format custom \
        --compress 9 \
        --no-owner \
        --no-acl \
      | gpg --homedir "$gpg_home" --batch --yes --trust-model always \
            --encrypt --recipient "$recipient" --output "$temporary"

    [[ -s "$temporary" ]]
    mv "$temporary" "$target"
    (cd "$(dirname "$target")" && sha256sum "$(basename "$target")" > "$(basename "$target").sha256")
}

trap 'find "$backup_root" -type f -name "*.partial" -delete' EXIT
dump_stack prod ap-pie-postgres-1
dump_stack beta ap-pie-beta-postgres-1

find "$backup_root/prod" "$backup_root/beta" -type f \
    \( -name '*.dump.gpg' -o -name '*.dump.gpg.sha256' \) \
    -mtime "+$retention_days" -delete

printf 'completed_at=%s\n' "$stamp" > "$backup_root/last-success"
