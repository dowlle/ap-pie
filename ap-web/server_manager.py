"""Manages multiple Archipelago server processes."""

from __future__ import annotations

import json
import logging
import os
import pty
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class ServerInstance:
    seed: str
    port: int
    zip_path: str
    players: list[str]
    started_at: str  # ISO format
    pid: int | None = None
    status: str = "starting"  # starting, running, stopped, crashed
    _process: subprocess.Popen | None = field(default=None, repr=False)
    _log_lines: list[str] = field(default_factory=list, repr=False)
    _stdin_fd: int | None = field(default=None, repr=False)

    def to_dict(self, host: str = "localhost") -> dict:
        return {
            "seed": self.seed,
            "port": self.port,
            "zip_path": self.zip_path,
            "players": self.players,
            "started_at": self.started_at,
            "pid": self.pid,
            "status": self.status,
            "connection_url": f"{host}:{self.port}",
            "uptime_seconds": self._uptime_seconds(),
            "recent_log": self._log_lines[-50:],
        }

    def _uptime_seconds(self) -> float:
        try:
            start = datetime.fromisoformat(self.started_at)
            return (datetime.now(timezone.utc) - start).total_seconds()
        except (ValueError, TypeError):
            return 0.0


class ServerManager:
    """Thread-safe manager for Archipelago server processes."""

    def __init__(
        self,
        server_exe: str,
        host: str = "localhost",
        port_start: int = 38281,
        port_end: int = 38380,
        state_file: str | None = None,
        on_server_stopped: Callable[[str], None] | None = None,
    ):
        self._server_exe = server_exe
        self._host = host
        self._port_start = port_start
        self._port_end = port_end
        self._state_file = Path(state_file) if state_file else None
        self._servers: dict[str, ServerInstance] = {}
        self._lock = threading.Lock()
        self._monitor_thread: threading.Thread | None = None
        self._running = False
        self._on_server_stopped = on_server_stopped

        self._restore_state()
        self._start_monitor()

    # ── Public API ───────────────────────────────────────────────

    def start(self, seed: str, zip_path: str, players: list[str]) -> ServerInstance:
        with self._lock:
            if seed in self._servers and self._servers[seed].status == "running":
                return self._servers[seed]

            # Reuse previous port if this seed was launched before
            prev = self._servers.get(seed)
            port = prev.port if prev else self._allocate_port()
            if port is None:
                raise RuntimeError("No available ports in configured range")

            exe = self._server_exe
            cmd = [exe, str(zip_path), "--port", str(port)]

            # Use a pty for stdin so the AP server enables its console input handler
            master_fd, slave_fd = pty.openpty()

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=slave_fd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except FileNotFoundError:
                os.close(master_fd)
                raise RuntimeError(f"Server executable not found: {exe}")
            finally:
                os.close(slave_fd)  # parent doesn't need the slave side

            instance = ServerInstance(
                seed=seed,
                port=port,
                zip_path=zip_path,
                players=players,
                started_at=datetime.now(timezone.utc).isoformat(),
                pid=proc.pid,
                status="running",
                _process=proc,
                _stdin_fd=master_fd,
            )
            self._servers[seed] = instance
            self._save_state()

            # Start log reader thread
            threading.Thread(
                target=self._read_output,
                args=(instance,),
                daemon=True,
            ).start()

            logger.info(f"Started server for seed {seed} on port {port} (PID {proc.pid})")
            return instance

    def stop(self, seed: str) -> bool:
        with self._lock:
            instance = self._servers.get(seed)
            if not instance:
                return False

            if instance._process and instance._process.poll() is None:
                instance._process.terminate()
                try:
                    instance._process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    instance._process.kill()

            instance.status = "stopped"
            self._close_stdin(instance)
            self._save_state()
            logger.info(f"Stopped server for seed {seed}")
        self._fire_stopped(seed)
        return True

    def send_command(self, seed: str, command: str) -> bool:
        """Send a command string to a running server's stdin via pty."""
        with self._lock:
            instance = self._servers.get(seed)
            if not instance or instance.status != "running":
                return False
            if instance._stdin_fd is None:
                return False
            proc = instance._process
            if not proc or proc.poll() is not None:
                return False
            try:
                os.write(instance._stdin_fd, (command + "\n").encode())
            except OSError:
                return False
        return True

    def remove(self, seed: str) -> bool:
        """Stop and remove a server from tracking."""
        self.stop(seed)
        with self._lock:
            if seed in self._servers:
                del self._servers[seed]
                self._save_state()
                return True
            return False

    def status(self, seed: str) -> ServerInstance | None:
        with self._lock:
            return self._servers.get(seed)

    def list_all(self) -> list[dict]:
        with self._lock:
            return [s.to_dict(self._host) for s in self._servers.values()]

    def shutdown(self) -> None:
        """Stop all servers and the monitor thread."""
        self._running = False
        with self._lock:
            for seed in list(self._servers.keys()):
                instance = self._servers[seed]
                if instance._process and instance._process.poll() is None:
                    instance._process.terminate()
                self._close_stdin(instance)

    # ── Internal ─────────────────────────────────────────────────

    @staticmethod
    def _close_stdin(instance: ServerInstance) -> None:
        if instance._stdin_fd is not None:
            try:
                os.close(instance._stdin_fd)
            except OSError:
                pass
            instance._stdin_fd = None

    def _fire_stopped(self, seed: str) -> None:
        """Call the on_server_stopped callback if set."""
        if self._on_server_stopped:
            try:
                self._on_server_stopped(seed)
            except Exception as e:
                logger.error(f"on_server_stopped callback failed for {seed}: {e}")

    def _allocate_port(self) -> int | None:
        used_ports = {s.port for s in self._servers.values() if s.status == "running"}
        for port in range(self._port_start, self._port_end + 1):
            if port not in used_ports:
                return port
        return None

    def _read_output(self, instance: ServerInstance) -> None:
        """Read stdout/stderr from a server process (runs in a daemon thread)."""
        proc = instance._process
        if not proc or not proc.stdout:
            return
        try:
            for line in proc.stdout:
                line = line.rstrip("\n")
                instance._log_lines.append(line)
                # Keep max 500 lines
                if len(instance._log_lines) > 500:
                    instance._log_lines = instance._log_lines[-250:]
        except (ValueError, OSError):
            pass

    def _start_monitor(self) -> None:
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        """Periodically check if server processes are still alive."""
        while self._running:
            time.sleep(5)
            stopped_seeds = []
            with self._lock:
                changed = False
                for instance in self._servers.values():
                    if instance.status != "running":
                        continue
                    if instance._process and instance._process.poll() is not None:
                        exit_code = instance._process.returncode
                        instance.status = "crashed" if exit_code != 0 else "stopped"
                        self._close_stdin(instance)
                        logger.warning(
                            f"Server {instance.seed} exited with code {exit_code}"
                        )
                        stopped_seeds.append(instance.seed)
                        changed = True
                if changed:
                    self._save_state()
            # Fire callbacks outside the lock
            for seed in stopped_seeds:
                self._fire_stopped(seed)

    def _save_state(self) -> None:
        if not self._state_file:
            return
        try:
            data = {}
            for seed, inst in self._servers.items():
                data[seed] = {
                    "seed": inst.seed,
                    "port": inst.port,
                    "zip_path": inst.zip_path,
                    "players": inst.players,
                    "started_at": inst.started_at,
                    "pid": inst.pid,
                    "status": inst.status,
                }
            self._state_file.write_text(json.dumps(data, indent=2))
        except OSError as e:
            logger.error(f"Failed to save server state: {e}")

    def _restore_state(self) -> None:
        """Restore tracked servers from state file; check if PIDs are still alive."""
        if not self._state_file or not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text())
        except (json.JSONDecodeError, OSError):
            return

        changed = False
        stopped_seeds = []

        with self._lock:
            for seed, info in data.items():
                # Don't overwrite a server we're actively managing with a process handle
                if seed in self._servers and self._servers[seed]._process is not None:
                    continue

                pid = info.get("pid")
                was_running = info.get("status") == "running"

                # Check if process is still alive
                still_alive = False
                if was_running and pid:
                    try:
                        os.kill(pid, 0)
                        still_alive = True
                    except (OSError, ProcessLookupError):
                        pass

                actual_status = "running" if still_alive else (
                    "stopped" if was_running else info.get("status", "stopped")
                )
                if was_running and not still_alive:
                    changed = True
                    stopped_seeds.append(seed)

                self._servers[seed] = ServerInstance(
                    seed=info["seed"],
                    port=info["port"],
                    zip_path=info["zip_path"],
                    players=info.get("players", []),
                    started_at=info["started_at"],
                    pid=pid,
                    status=actual_status,
                )

            if changed:
                self._save_state()

        # Fire callbacks outside the lock
        for seed in stopped_seeds:
            self._fire_stopped(seed)
