"""Daemon lifecycle management for the dispatcher process.

Public API:
    ensure_dispatcher()      — Start the dispatcher if not running. Blocks until ready.
    stop_dispatcher()        — Send SIGTERM and wait for exit.
    dispatcher_is_running()  — Check if the daemon is alive and ready.
"""

import errno
import fcntl
import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from sabbatical.core.config import SABBATICAL_DIR

logger = logging.getLogger(__name__)

DISPATCHER_PID_PATH = SABBATICAL_DIR / "dispatcher.pid"
DISPATCHER_READY_PATH = SABBATICAL_DIR / "dispatcher.ready"
DISPATCHER_LOG_PATH = SABBATICAL_DIR / "dispatcher.log"

_READY_TIMEOUT = 30.0  # pg0 first-run extracts PG binaries + initializes DB
_READY_POLL_INTERVAL = 0.25  # seconds
_STOP_TIMEOUT = 10.0  # seconds
_LOG_TRUNCATE_LINES = 1000


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        if e.errno == errno.ESRCH:
            return False
        # EPERM means process exists but we don't have permission (shouldn't happen for our own daemon)
        return True


def _truncate_log():
    """Truncate dispatcher.log to the last N lines to bound growth."""
    if not DISPATCHER_LOG_PATH.exists():
        return
    try:
        lines = DISPATCHER_LOG_PATH.read_text().splitlines()
        if len(lines) > _LOG_TRUNCATE_LINES:
            DISPATCHER_LOG_PATH.write_text(
                "\n".join(lines[-_LOG_TRUNCATE_LINES:]) + "\n"
            )
    except OSError:
        pass


def _read_pid_file() -> int | None:
    """Read and return the PID from the PID file, or None if invalid/missing."""
    try:
        text = DISPATCHER_PID_PATH.read_text().strip()
        return int(text) if text else None
    except (OSError, ValueError):
        return None


def ensure_dispatcher() -> None:
    """Start the dispatcher daemon if it's not already running. Idempotent.

    Blocks until the daemon signals readiness (ready marker file) or times out.
    Uses fcntl.flock on the PID file to prevent simultaneous-start races.
    """
    SABBATICAL_DIR.mkdir(parents=True, exist_ok=True)

    fd = os.open(str(DISPATCHER_PID_PATH), os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)

        # Check if already running
        pid = _read_pid_file()
        if pid is not None and _pid_is_alive(pid):
            # Process is alive — check if ready
            if DISPATCHER_READY_PATH.exists():
                return  # Already running and ready
            # Process alive but not ready yet — wait for it below
            _wait_for_ready(pid)
            return

        # Dead or no PID — clean up stale files
        DISPATCHER_READY_PATH.unlink(missing_ok=True)

        # Resolve the dispatcher binary
        binary = shutil.which("sabbatical-dispatcher")
        if binary is None:
            raise RuntimeError(
                "sabbatical-dispatcher binary not found on PATH. "
                "Ensure the sabbatical package is installed (pip install -e .)."
            )

        # Truncate log to bound growth
        _truncate_log()

        # Fork the daemon process
        log_file = open(DISPATCHER_LOG_PATH, "a")
        proc = subprocess.Popen(
            [binary],
            start_new_session=True,
            stdout=log_file,
            stderr=log_file,
        )
        log_file.close()

        # Write new PID
        DISPATCHER_PID_PATH.write_text(str(proc.pid))

        logger.info("dispatcher daemon started pid=%d", proc.pid)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    # Wait for readiness (outside the lock so other callers can check PID)
    _wait_for_ready(proc.pid)


def _wait_for_ready(pid: int) -> None:
    """Poll until the ready marker appears or timeout."""
    deadline = time.monotonic() + _READY_TIMEOUT
    while time.monotonic() < deadline:
        if DISPATCHER_READY_PATH.exists():
            return
        if not _pid_is_alive(pid):
            # Process died before becoming ready
            tail = ""
            if DISPATCHER_LOG_PATH.exists():
                try:
                    lines = DISPATCHER_LOG_PATH.read_text().splitlines()
                    tail = "\n".join(lines[-20:])
                except OSError:
                    pass
            raise RuntimeError(
                f"Dispatcher daemon (PID {pid}) exited before becoming ready.\n"
                f"Last log lines:\n{tail}"
            )
        time.sleep(_READY_POLL_INTERVAL)

    raise RuntimeError(
        f"Dispatcher daemon (PID {pid}) did not become ready within {_READY_TIMEOUT}s. "
        "It may be stuck running migrations. Check ~/.sabbatical/dispatcher.log"
    )


def stop_dispatcher() -> None:
    """Send SIGTERM to the dispatcher daemon and wait for it to exit."""
    pid = _read_pid_file()
    if pid is None:
        return

    if not _pid_is_alive(pid):
        # Stale PID file — clean up
        DISPATCHER_PID_PATH.unlink(missing_ok=True)
        DISPATCHER_READY_PATH.unlink(missing_ok=True)
        return

    # Send SIGTERM
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        DISPATCHER_PID_PATH.unlink(missing_ok=True)
        DISPATCHER_READY_PATH.unlink(missing_ok=True)
        return

    # Wait for exit (poll with signal 0 — cannot use waitpid since it's not our child)
    deadline = time.monotonic() + _STOP_TIMEOUT
    while time.monotonic() < deadline:
        if not _pid_is_alive(pid):
            break
        time.sleep(_READY_POLL_INTERVAL)
    else:
        # Timeout — force kill
        logger.warning("dispatcher daemon did not exit in time, sending SIGKILL pid=%d", pid)
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    # Clean up
    DISPATCHER_PID_PATH.unlink(missing_ok=True)
    DISPATCHER_READY_PATH.unlink(missing_ok=True)
    logger.info("dispatcher daemon stopped pid=%d", pid)


def dispatcher_is_running() -> bool:
    """Check if the dispatcher daemon process is alive and ready."""
    pid = _read_pid_file()
    if pid is None:
        return False
    return _pid_is_alive(pid) and DISPATCHER_READY_PATH.exists()


_last_check: float = 0.0
_CHECK_INTERVAL = 120.0  # seconds


def ensure_dispatcher_if_needed() -> None:
    """Lightweight cached check — calls ensure_dispatcher() at most once per _CHECK_INTERVAL.

    The check itself (dispatcher_is_running) is two filesystem stats — essentially free.
    Only pays the full startup cost if the dispatcher actually died.
    """
    global _last_check
    now = time.monotonic()
    if now - _last_check < _CHECK_INTERVAL:
        return
    _last_check = now
    if not dispatcher_is_running():
        ensure_dispatcher()
