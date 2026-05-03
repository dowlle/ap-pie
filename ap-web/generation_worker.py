"""Background worker that drains the generation_jobs queue.

A single daemon thread polls Postgres every couple of seconds for queued jobs,
runs the AP generator subprocess, and writes the result back to the row. The
HTTP request that enqueues the job returns immediately (HTTP 202) instead of
blocking gunicorn's single worker for the 30-300 seconds an AP generation
takes.

The worker is started lazily on the first enqueue rather than at app boot,
because gunicorn with `preload_app = True` forks workers from a master that
already loaded the app - any thread started inside `create_app()` would die
during the fork. Starting on enqueue dodges that and also avoids holding a
DB connection in a never-used worker.

Concurrency model: one job at a time, in order. We use SELECT ... FOR UPDATE
SKIP LOCKED in `claim_pending_job` so this is already safe if gunicorn ever
scales past one worker, but the AP generator itself has cwd-shared state
(custom_worlds symlinks) so running two generations in parallel would race.
Serial is fine.
"""

from __future__ import annotations

import json
import logging
import threading

import config

logger = logging.getLogger(__name__)

_worker_thread: "threading.Thread | None" = None
_worker_lock = threading.Lock()
_shutdown_event = threading.Event()
_POLL_INTERVAL_SECONDS = 2.0


def ensure_worker_running() -> None:
    """Start the worker thread if it isn't alive. Safe to call repeatedly."""
    global _worker_thread
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _shutdown_event.clear()
        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="ap-generation-worker",
            daemon=True,
        )
        _worker_thread.start()
        logger.info("Started generation worker thread")


def shutdown_worker(timeout: float = 5.0) -> None:
    """Signal the worker to stop and wait briefly. Daemon thread anyway."""
    _shutdown_event.set()
    if _worker_thread is not None and _worker_thread.is_alive():
        _worker_thread.join(timeout=timeout)


def _worker_loop() -> None:
    from db import claim_pending_job, reset_orphaned_running_jobs

    try:
        recovered = reset_orphaned_running_jobs()
        if recovered:
            logger.warning("Recovered %d orphaned running jobs", recovered)
    except Exception:
        logger.exception("Failed to reset orphaned jobs at startup")

    while not _shutdown_event.is_set():
        try:
            job = claim_pending_job()
            if not job:
                _shutdown_event.wait(_POLL_INTERVAL_SECONDS)
                continue
            _run_job(job)
        except Exception:
            logger.exception("Worker loop error; pausing before retry")
            _shutdown_event.wait(5.0)


def _run_job(job: dict) -> None:
    from db import (
        add_activity,
        get_room,
        get_yamls,
        mark_job_failed,
        mark_job_succeeded,
        update_room,
    )
    from generation import generate_game

    job_id = job["id"]
    room_id = job["room_id"]

    room = get_room(room_id)
    if not room:
        mark_job_failed(job_id, error=f"Room {room_id} disappeared", log="")
        return

    yamls = get_yamls(room_id)
    if not yamls:
        mark_job_failed(job_id, error="No YAMLs uploaded", log="")
        update_room(room_id, status="closed")
        return

    yaml_pairs = [(y["filename"], y["yaml_content"]) for y in yamls]

    logger.info("Running generation job %d for room %s (%d yamls)", job_id, room_id, len(yamls))

    result = generate_game(
        yamls=yaml_pairs,
        output_dir=config.OUTPUT_DIR,
        generator_exe=config.GENERATOR_EXE,
        spoiler_level=room.get("spoiler_level", 3),
        race_mode=room.get("race_mode", False),
        timeout=config.GENERATION_TIMEOUT,
        custom_worlds_dir=config.WORLDS_DIR,
    )

    if result.success:
        update_room(
            room_id,
            status="generated",
            seed=result.seed,
            generation_log=result.log,
        )
        mark_job_succeeded(job_id, seed=result.seed or "", log=result.log)
        add_activity(room_id, "generation", f"Generation succeeded: seed {result.seed}")

        # Refresh the in-memory game records cache so the new game shows up
        # in /api/games and friends without waiting for the file-count poll.
        try:
            from app import _refresh_records

            _refresh_records()
        except Exception:
            logger.exception("Failed to refresh records cache after generation")

        # Persist game versions sidecar so the UI can show what apworld
        # versions were used to generate this seed.
        try:
            if result.zip_path:
                from ap_lib.parsing import parse_generation_log

                game_versions = parse_generation_log(result.log)
                if game_versions:
                    versions_file = result.zip_path.with_suffix(".versions.json")
                    versions_file.write_text(json.dumps(game_versions, indent=2))
        except Exception:
            logger.exception("Failed to persist game versions sidecar")
    else:
        update_room(room_id, status="closed", generation_log=result.log)
        mark_job_failed(
            job_id,
            error=result.error or "Unknown error",
            log=result.log,
        )
        add_activity(room_id, "generation", f"Generation failed: {result.error}")
