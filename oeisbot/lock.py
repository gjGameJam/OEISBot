"""One lock for every command that runs programs, rewrites the mirror, or talks to oeis.org (item 58).

Before `oeisbot daemon` there was one writer at a time because there was one person at one console. An
unattended loop ends that, and three things break when two such processes overlap:

* the 1 request/second limit on oeis.org is a module global (`ingest.bfile._throttle`), so two processes
  each keep to it and together do not (invariant 1);
* `oeisbot recheck` and a session's own retry of pending re-checks would resolve the same win twice
  (`artifact.write` refuses an existing folder, `reviews.attempt_id` is unique);
* `oeisbot sync` rewrites the mirror's entries (`git reset --hard`) under a session that is reading them,
  and `oeisbot setup` rewrites the runtimes and grants under a sandbox that is using them.

So the daemon **and** the commands in `cli.LOCKED` take this lock, and whichever comes second is refused
with a message naming the first. Reading commands (`queue`, `pick`, `attempts`, `stats`, `review`, the
dashboard) do not: SQLite in WAL mode already serves them.

The lock is an operating-system lock on `data/writer.lock`, held for as long as the file is open. That is
the point of using one: a process that is killed, however it is killed, releases it, so there is no stale
lock to clean up and no pid to guess about (measured on this machine: free within 10 ms of `taskkill /F`,
of the venv launcher being killed, of `os._exit`). On Windows it is a lock on one byte **far past the end
of the file** (`LOCK_OFFSET`): a locked range cannot be read or written by another handle, and locking
past the end leaves the file itself -- empty, or holding the description below -- readable by anyone,
including a backup of `data/`. Nothing is ever written at that offset.

The holder writes who it is into the same file. That is only a description: it can be stale (left by a
killed process) or empty (a holder between taking the lock and writing), and nothing decides anything
from it. `held()` asks the lock.

Two limits, both recorded in docs/known-limitations.md. The lock is taken by the commands, not by the
library: a script that calls `attempt.run_session`, `run_attempt` or `bfile.fetch` directly must take
`lock.writer` itself. And it covers this process, not its children: a `git` started by a `sync` that is
then killed can outlive it for a moment while the next command starts.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from . import config, guard

# How often `writer` tries before it gives up, and `held` before it says yes. Not there to wait for a real
# holder -- a session runs for hours -- but because `held()` takes the lock for an instant to see whether
# it can, so a command (or another probe) arriving in that instant must look again before believing it.
# Measured with eight processes probing in tight loops: 12,859 acquisitions, none refused, at most 3 tries.
ACQUIRE_TRIES = 5
ACQUIRE_PAUSE_S = 0.05
PROBE_TRIES = 3
PROBE_PAUSE_S = 0.02
LOCK_OFFSET = 1 << 30           # the byte that is locked on Windows: far past anything the file will hold

_probe = threading.Lock()       # the lock is per handle, so two probes in one process would refuse each other


def directory() -> Path:
    """Where the lock lives. A function, read at every call, for two reasons: a test that points
    `config.DATA` elsewhere gets its own lock, and `tests/conftest.py` replaces this for every test that
    does not, so that no test ever takes -- or is refused by -- the lock of the real data directory."""
    return config.DATA


def lock_path() -> Path:
    return directory() / "writer.lock"


class Held(RuntimeError):
    """Another process holds the writers' lock. `owner` is what the file says about it, or None when
    that is missing or unreadable (the lock is held all the same)."""

    def __init__(self, command: str, owner: dict | None):
        self.owner = owner
        if owner:
            who = (f"`oeisbot {owner.get('command', '?')}` (pid {owner.get('pid', '?')}, started "
                   f"{owner.get('started_at', '?')} local time, by the lock file's account)")
        else:
            who = "another oeisbot command"
        stop = " (`oeisbot daemon --stop` for the daemon)" if not owner or owner.get("command") == "daemon" else ""
        super().__init__(f"`oeisbot {command}` not started: {who} is running, and only one command that runs "
                         f"programs, syncs or contacts oeis.org may run at a time. Wait for it, or stop it{stop}")


def _try_lock(fd: int) -> bool:
    """Take an exclusive, non-blocking lock. False when someone else has it."""
    try:
        if sys.platform == "win32":
            import msvcrt
            os.lseek(fd, LOCK_OFFSET, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(fd: int) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt
            os.lseek(fd, LOCK_OFFSET, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass        # closing the descriptor releases it anyway


def _describe(fd: int, owner: dict | None) -> None:
    """Replace the file's contents with `owner` (or nothing). The holder only; never raises. The old
    description is cut off first, so a failed write leaves an empty file, not someone else's name."""
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        if owner is not None:
            os.write(fd, json.dumps(owner).encode("utf-8"))
    except OSError:
        pass        # the description is a courtesy; the lock is what matters


def read_owner() -> dict | None:
    """What the file says about its last holder, or None. **Not** evidence that the lock is held."""
    try:
        owner = json.loads(lock_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return owner if isinstance(owner, dict) else None


def held() -> bool:
    """Whether some process holds the writers' lock right now. Asks the lock, never the description:
    takes it for an instant when it is free and gives it straight back. Creates nothing -- the dashboard
    calls this, and the dashboard only reads -- so no lock file means nobody has ever held it.

    A probe can meet another probe (two browser tabs, two dashboards) in that instant, so "held" is
    believed only after `PROBE_TRIES` looks a few milliseconds apart; a real holder is there every time."""
    with _probe:
        for attempt in range(PROBE_TRIES):
            try:
                fd = os.open(lock_path(), os.O_RDWR)
            except OSError:
                return False        # no lock file, or no data directory: nothing here holds anything
            try:
                if _try_lock(fd):
                    _unlock(fd)
                    return False
            finally:
                os.close(fd)
            if attempt + 1 < PROBE_TRIES:
                time.sleep(PROBE_PAUSE_S)
        return True


@contextmanager
def writer(command: str) -> Iterator[None]:
    """Hold the writers' lock for the body. Raises `Held` at once (within `ACQUIRE_TRIES` short tries) when
    another process has it; never waits for a holder to finish. An `OSError` means the lock file itself
    could not be opened (no data directory that can be created), which `cli.main` reports as such."""
    path = lock_path()
    guard.refuse_if_real(path, "taking the writers' lock")      # never from a test (oeisbot.guard)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    try:
        for attempt in range(ACQUIRE_TRIES):
            if _try_lock(fd):
                break
            if attempt + 1 < ACQUIRE_TRIES:
                time.sleep(ACQUIRE_PAUSE_S)
        else:
            raise Held(command, read_owner())
    except BaseException:
        os.close(fd)
        raise
    try:
        _describe(fd, {"pid": os.getpid(), "command": command,
                       "started_at": datetime.now().isoformat(sep=" ", timespec="seconds")})
        yield
    finally:
        _describe(fd, None)
        _unlock(fd)
        os.close(fd)
