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
    local postgres_container="$2"
    local web_container="$3"
    local target="$backup_root/$stack/$stamp.dump.gpg"
    local temporary="$target.partial"
    local ledger_target="$backup_root/$stack/$stamp.erasure.jsonl.gpg"
    local ledger_temporary="$ledger_target.partial"

    docker inspect "$postgres_container" "$web_container" >/dev/null
    docker exec "$postgres_container" pg_dump \
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

    # The ledger is intentionally outside PostgreSQL: it prevents a dump
    # restored from before a completed account deletion from resurrecting the
    # account. Capture it after pg_dump so any receipt written during the dump
    # is included in the same backup set. A missing ledger is a valid empty
    # ledger for stacks that have not deployed the account feature yet.
    docker exec --user 1000:1000 "$web_container" python -c '
import fcntl
import pathlib
import sys

path = pathlib.Path("/app/.state/account-erasure-receipts.jsonl")
path.parent.mkdir(parents=True, exist_ok=True)
with (path.parent / f".{path.name}.lock").open("a+") as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    if path.exists():
        sys.stdout.buffer.write(path.read_bytes())
' \
      | gpg --homedir "$gpg_home" --batch --yes --trust-model always \
            --encrypt --recipient "$recipient" --output "$ledger_temporary"

    [[ -s "$ledger_temporary" ]]
    mv "$ledger_temporary" "$ledger_target"
    (cd "$(dirname "$ledger_target")" && sha256sum "$(basename "$ledger_target")" > "$(basename "$ledger_target").sha256")
}

trap 'find "$backup_root" -type f -name "*.partial" -delete' EXIT
dump_stack prod ap-pie-postgres-1 ap-pie-ap-web-1
dump_stack beta ap-pie-beta-postgres-1 ap-pie-beta-ap-web-1

find "$backup_root/prod" "$backup_root/beta" -type f \
    \( -name '*.dump.gpg' -o -name '*.dump.gpg.sha256' \
       -o -name '*.erasure.jsonl.gpg' -o -name '*.erasure.jsonl.gpg.sha256' \) \
    -mtime "+$retention_days" -delete

printf 'completed_at=%s\n' "$stamp" > "$backup_root/last-success"
