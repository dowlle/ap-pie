"""Recoverable account deletion and durable post-backup erasure replay.

The seven-day grace state lives in Postgres. The append-only receipt ledger
does not: it lives in the mounted application state volume so restoring an old
database dump cannot resurrect an account whose deletion already completed.
Receipts contain only the internal user id, owned seed ids and timestamps.
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config

_thread_lock = threading.Lock()


def _ledger_path() -> Path:
    return Path(config.ACCOUNT_ERASURE_LEDGER)


def _read_receipts_unlocked(path: Path) -> list[dict]:
    if not path.exists():
        return []
    receipts: list[dict] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            receipt = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid erasure receipt at line {line_no}") from exc
        if not isinstance(receipt, dict) or not isinstance(receipt.get("user_id"), int):
            raise RuntimeError(f"Invalid erasure receipt shape at line {line_no}")
        receipts.append(receipt)
    return receipts


def _with_file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = (path.parent / f".{path.name}.lock").open("a+", encoding="utf-8")
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    return lock_handle


def ensure_receipt(user_id: int, seeds: list[str]) -> dict:
    """Persist and fsync a receipt before the destructive DB transaction."""
    path = _ledger_path()
    with _thread_lock:
        lock_handle = _with_file_lock(path)
        try:
            existing = _read_receipts_unlocked(path)
            for receipt in existing:
                if receipt["user_id"] == user_id:
                    return receipt
            receipt = {
                "receipt_id": uuid.uuid4().hex,
                "user_id": user_id,
                "seeds": sorted({str(seed) for seed in seeds if seed}),
                "erased_at": datetime.now(timezone.utc).isoformat(),
            }
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(receipt, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return receipt
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()


def list_receipts() -> list[dict]:
    path = _ledger_path()
    with _thread_lock:
        lock_handle = _with_file_lock(path)
        try:
            return _read_receipts_unlocked(path)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()


def _artifact_paths(seed: str) -> list[Path]:
    if not seed or Path(seed).name != seed or any(ch in seed for ch in ("/", "\\", "\x00")):
        raise ValueError("Unsafe seed id in erasure receipt")
    output = Path(config.OUTPUT_DIR).resolve()
    return [
        (output / f"AP_{seed}.zip").resolve(),
        (output / f"AP_{seed}.apsave").resolve(),
        (output / f"AP_{seed}.versions.json").resolve(),
    ]


def delete_seed_artifacts(seeds: list[str], manager=None) -> None:
    output = Path(config.OUTPUT_DIR).resolve()
    for seed in seeds:
        if manager is not None:
            try:
                manager.stop(seed)
            except Exception:
                # A missing/non-running server is the normal case. File checks
                # below are authoritative and remain retryable from the ledger.
                pass
        for path in _artifact_paths(seed):
            try:
                path.relative_to(output)
            except ValueError as exc:
                raise RuntimeError("Artifact path escaped AP_OUTPUT_DIR") from exc
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def _receipt_resolved(receipt: dict) -> bool:
    from db import get_user

    if get_user(receipt["user_id"]):
        return False
    return not any(path.exists() for seed in receipt.get("seeds", []) for path in _artifact_paths(seed))


def compact_resolved_receipts() -> None:
    """Drop resolved receipts after backup rotation; retain failures indefinitely."""
    path = _ledger_path()
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.ACCOUNT_ERASURE_RECEIPT_DAYS)
    with _thread_lock:
        lock_handle = _with_file_lock(path)
        try:
            receipts = _read_receipts_unlocked(path)
            keep: list[dict] = []
            for receipt in receipts:
                erased_at = datetime.fromisoformat(receipt["erased_at"])
                if erased_at.tzinfo is None:
                    erased_at = erased_at.replace(tzinfo=timezone.utc)
                if erased_at >= cutoff or not _receipt_resolved(receipt):
                    keep.append(receipt)
            temp = path.with_suffix(path.suffix + ".tmp")
            with temp.open("w", encoding="utf-8") as handle:
                for receipt in keep:
                    handle.write(json.dumps(receipt, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()


def process_due_account(user_id: int, manager=None) -> dict:
    """Purge one account only after its grace deadline has passed."""
    from db import (
        get_account_erasure_targets,
        permanently_delete_account,
    )

    targets = get_account_erasure_targets(user_id)
    if not targets:
        return {}
    receipt = ensure_receipt(targets["user_id"], targets["seeds"])
    result = permanently_delete_account(targets["user_id"])
    delete_seed_artifacts(receipt.get("seeds", []), manager=manager)
    return result


def process_due_accounts(manager=None, logger=None) -> list[dict]:
    """Purge expired grace periods, then replay all retained receipts."""
    from db import (
        list_due_account_deletions,
        permanently_delete_account,
        prune_expired_room_creation_blocks,
    )

    prune_expired_room_creation_blocks()
    results: list[dict] = []
    for due in list_due_account_deletions():
        result = process_due_account(due["id"], manager=manager)
        if result:
            results.append(result)

    # Replay is deliberately unconditional and idempotent. This is the path
    # that makes a restored database dump respect deletions completed later.
    for receipt in list_receipts():
        try:
            permanently_delete_account(receipt["user_id"], receipt_replay=True)
            delete_seed_artifacts(receipt.get("seeds", []), manager=manager)
        except Exception as exc:
            if logger is not None:
                logger.error(
                    "account erasure replay failed for receipt %s: %s",
                    receipt.get("receipt_id"), exc,
                )
    compact_resolved_receipts()
    return results
