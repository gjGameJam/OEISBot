"""`oeisbot daemon`: sessions back to back, unattended, inside a nightly window (item 58).

What it adds to `attempt.run_session` is everything a person at the console used to supply: when to
start and stop, which budgets to run at, not picking the same undecided sequence night after night,
syncing the mirror, noticing a full disk, and cleaning up after a process that was killed. It adds no
selection rule and no verification rule: every pick still goes through `attempt_sequence`, and nothing
here submits anything or contacts oeis.org except through the calls a session already makes.

One night, in order:

1. Take the writers' lock (`oeisbot.lock`) as `daemon`. If a command holds it, say so in the log and try
   again every minute while the window is open (`_take_the_lock`); the task that starts this fires once
   a day, so giving up at once would lose the night.
2. **Recover** from a killed predecessor: close session rows left open, remove run directories it left
   in `data/scratch`, drop a stop request older than this start. A scheduled task is usually ended by
   being killed (only `--stop`, the window's end and Ctrl-C reach this code), so this is the normal path.
3. **Sync** the mirror once (`oeisdata.sync`, each git command under `SYNC_TIMEOUT_S`), so new and
   changed entries are in the pool. A failed pull is logged, shown in the heartbeat, and the night goes
   on with the data it has.
4. **Sessions** at the lowest tier of the ladder (`TIERS`) that has something to draw. A pick is started
   while there is time left to *verify* it (`start_gate_s`); the window closing interrupts an extension
   in hand, which costs nothing (`verify.Stop.INTERRUPTED` retires nothing and adds no penalty).
   Sequences whose last attempt changed nothing are held back for `COOLDOWN_DAYS` (`Cooldown`).
5. Stop when the window ends, on `oeisbot daemon --stop`, on Ctrl-C, or when nothing is left to run.

Everything that touches the clock, the disk or the machine is a method of `Daemon` that a test replaces;
the loop itself is driven in memory in `tests/test_daemon.py`.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
import traceback
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from . import config, db, guard, lock, sandbox, select
from .config import Budgets, GiB


@dataclass(frozen=True)
class Tier:
    name: str
    verify_s: float
    extend_s: float

    @property
    def budgets(self) -> Budgets:
        """The defaults with this tier's two times. Never a new `Budgets` field: `attempt._checked`
        compares the field set of a saved win both ways, so one more field would strand every win
        waiting in `data/pending/`."""
        return replace(config.DEFAULT_BUDGETS, verify_wall_s=self.verify_s, extend_wall_s=self.extend_s)


# The ladder, lowest first. `base` is the setting sessions 8 to 12 actually ran at: a 60 s verification
# and a 30-minute extension, not the 3-hour default (every row of sessions 7 to 12 records the 1800 s;
# session 7 alone verified at 600 s). So the pool it starts from and the time a pass takes are the ones
# those sessions measured. `verify600` is session 7's longer first pass;
# `long` adds the default extension. A sequence leaves a tier when its programs are dead ends at that
# tier's budgets (`db.is_dead_end`), which is what makes the next tier's pool different.
TIERS = (Tier("base", 60, 1800), Tier("verify600", 600, 1800), Tier("long", 600, 3 * 3600))

DEFAULT_WINDOW = "22:00-08:00"
# written at the root by data/item58/mutate.py while a mutant is in the working tree, removed when the
# file is restored. If it is there when nothing is running, the harness was killed and the code is not
# the code: the daemon refuses to do anything, and tests/conftest.py refuses to run
MUTANT_SENTINEL = "MUTANT_IN_TREE.json"
ALWAYS = "always"

COOLDOWN_DAYS = 14
# The mirror older than this: no climbing past the lowest tier. A higher tier spends hours per pick, and
# spending them on terms that may have been extended since is the waste a sync exists to prevent.
STALE_SYNC_DAYS = 7
SESSION_PICKS = config.DEFAULT_BUDGETS.session_attempt_cap
# kept free beyond the sandbox's own reserves before a pick is started: at the reserve itself the
# sandbox stops the run as `disk_cap` / refuses to launch, and every such pick doubles a failure penalty
DISK_MARGIN_BYTES = 2 * GiB
RAM_MARGIN_BYTES = 1 * GiB
PAUSE_S = 600.0                 # between looks at a machine that is short of disk or RAM
# stops that are the machine's or the network's doing; this many picks in a row end the night rather
# than burn through the pool (each is a `failed` row or a skip, and none of them retires anything)
MACHINE_FAILURES = ("launch_error", "disk_cap", "harness_error", "bfile_error")
BREAKER_RUN = 5
# a session that raises is the daemon's own fault or one entry's; this many in a row end the night
ERROR_RUN = 2
DAEMON_ERROR = "daemon_error"   # the skip reason recorded for the pick in hand when a session raised
POLL_S = 1.0                    # how often the stop request and the window are looked at
HEARTBEAT_S = 30.0
# seconds a pick can take beyond its verify budgets before it is in its extension: sandbox start-up and
# wind-down for each program, a b-file download, the pool build before the first pick
PICK_SLACK_S = 300.0
# each git command of the nightly sync. A normal fetch-and-reset is about a minute; the first one after
# months rewrites most of 676,000 files and is still a matter of minutes
SYNC_TIMEOUT_S = 600.0
# After a stop is asked for, the main thread has this long to come back. It normally takes under a
# second. The honest long waits are a win's re-check in network trouble (about nine minutes) and a sync
# in hand, which does not look at the stop: one git command up to `SYNC_TIMEOUT_S`, then reading the
# mirror. Past this the process ends itself, ending git first (`oeisdata.end_running_git`): the
# writers' lock must not be held into the day by a hung call, and the lock and the sandbox's job object
# both let go when the process does (recovery tidies the rest).
STOP_GRACE_S = 1200.0
# a run directory in data/scratch last changed this long ago belongs to no live run: the longest pick at
# the top tier is under four hours
SCRATCH_ORPHAN_AGE_S = 6 * 3600.0
_RUN_DIR = re.compile(r"A\d{6}-[a-z]+-[0-9a-f]{8}")     # sandbox.new_scratch_dir(f"{a_number}-{language}")


def start_gate_s(budgets: Budgets) -> float:
    """How much of the window must be left to start a pick: time for every program of the entry to use
    its whole verify budget (`MAX_PROGRAMS_PER_SEQUENCE`), so the pick at least reaches a verdict on
    each. The extension is not counted: if the window closes during it the run is interrupted, which
    retires nothing, adds no penalty and is not cooled. (The first design counted the extension too and
    left a third of every night at the top tier unused.)

    What that costs: about one pick a night is cut short in its extension (measured mix of sessions 9 to
    12), its minutes of searching thrown away -- fewer than the gate used to leave idle. And the rare one
    that had already found new terms opens its review with those terms only; the sequence is then out of
    the draw until the user decides, though a full extension might have found more
    (`Daemon._note_wins_cut_short` says so in the heartbeat)."""
    from .attempt import MAX_PROGRAMS_PER_SEQUENCE
    return MAX_PROGRAMS_PER_SEQUENCE * budgets.verify_wall_s + PICK_SLACK_S


# ------------------------------------------------------------------ the window

@dataclass(frozen=True)
class Window:
    """Local wall-clock hours the daemon may run in, e.g. 22:00 to 08:00. `always` has no closing time."""
    start_min: int
    end_min: int

    @classmethod
    def parse(cls, text: str) -> "Window":
        if text.strip().lower() == ALWAYS:
            return cls(0, 0)
        try:
            a, b = text.split("-")
            (ah, am), (bh, bm) = (tuple(int(x) for x in t.strip().split(":")) for t in (a, b))
            if not (0 <= ah <= 23 and 0 <= bh <= 24 and 0 <= am <= 59 and 0 <= bm <= 59 and bh * 60 + bm <= 1440):
                raise ValueError
            if ah * 60 + am == bh * 60 + bm:    # 22:00-22:00: a whole day, or nothing? Say which
                raise ValueError
            start, end = ah * 60 + am, (bh * 60 + bm) % 1440       # 00:00-24:00 is the whole day: `always`
        except ValueError:
            raise ValueError(f"window {text!r}: expected HH:MM-HH:MM in local time with two different times "
                             f"(e.g. {DEFAULT_WINDOW}), or `{ALWAYS}`") from None
        return cls(start, end)

    @property
    def always(self) -> bool:
        return self.start_min == self.end_min

    def __str__(self) -> str:
        if self.always:
            return ALWAYS
        return "-".join(f"{m // 60:02d}:{m % 60:02d}" for m in (self.start_min, self.end_min))

    def ends_at(self, now: datetime) -> datetime | None:
        """When the window that contains `now` (naive local time) closes, or None when `now` is outside
        it. Not meaningful for `always`, which has no closing time (the caller asks `always` first).

        The answer is a wall-clock time, and the caller turns the gap into seconds with `seconds_until`,
        which goes through real timestamps -- so a night with a clock change in it is an hour shorter or
        longer in seconds, as it is on the machine. A window whose end falls inside the hour the clocks
        skip or repeat ends an hour off by the wall clock on that one night; the default does not."""
        if self.always:
            return None
        minute = now.hour * 60 + now.minute + now.second / 60
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_today = midnight + timedelta(minutes=self.end_min)
        if self.start_min < self.end_min:                       # inside one day
            return end_today if self.start_min <= minute < self.end_min else None
        if minute >= self.start_min:                            # over midnight: the evening half
            return end_today + timedelta(days=1)
        return end_today if minute < self.end_min else None     # ... and the morning half


def seconds_until(then: datetime, now: datetime) -> float:
    """Elapsed seconds between two naive local times, through the operating system's idea of local
    time, so daylight-saving changes are counted."""
    return then.timestamp() - now.timestamp()


# ------------------------------------------------------------------ the cooldown

class Cooldown:
    """Which pool members not to draw now: those whose most recent attempt, in the last `days`, changed
    nothing about what the next attempt *at these budgets* would do.

    Most attempts end with a program retired (a deterministic failure, a used-up budget), and then the
    sequence either leaves the pool or its next program runs: there is nothing to cool. But some stops
    retire nothing on purpose -- a published bound out of reach (`searched_bound`), a term killed for
    running past its projection, the machine short of memory, a b-file that could not be fetched -- and a
    sequence that ends that way stays in the pool exactly as it was. A person running a session a week
    never met the same one twice in a row; a loop meets it every night once the pool has thinned.

    A recent attempt cools its sequence unless one of these is true:

    * it was cut short: one of its rows is `interrupted` (the daemon's own stop), so a program of it may
      never have run;
    * it ran under smaller budgets than the ones asked about now. A run that timed out at 60 s says
      nothing about 600 s -- that sequence is exactly what the next tier is for, and holding it back
      would empty every tier above the first (the first version did: 128 of 131 at `verify600`);
    * one of its runs is a dead end at these budgets (`db.is_dead_end`): it made progress, and the next
      attempt runs something else;
    * the sequence has a different number of known terms now than that attempt saw: a sync changed it;
    * it recorded only a skip (a b-file that could not be fetched, inconsistent terms) and the mirror has
      synced since: the cause was the network or the data of that day. A skip the daemon itself wrote
      for a session that raised (`DAEMON_ERROR`) cools for the whole period, so one crashing entry does
      not end every night.

    Built once per look at a pool and asked once per candidate. `held` counts what it kept back."""

    def __init__(self, conn: sqlite3.Connection, budgets: Budgets, now_utc: datetime, days: float = COOLDOWN_DAYS,
                 known_count: Callable[[str], int | None] | None = None):
        self.conn, self.budgets = conn, budgets
        self.known_count = known_count or current_known_count
        self.held = 0
        self.asked = 0
        self.synced_at = pulled_at(conn) or ""
        since = (now_utc - timedelta(days=days)).isoformat(timespec="seconds")
        # the rows of each sequence's most recent attempt in the period. The rows of one `attempt_sequence`
        # call share extra.attempt_call; a row without it (a skip, or one written before the key existed)
        # stands alone
        self.recent: dict[str, list[sqlite3.Row]] = {}
        calls: dict[str, str] = {}
        for row in conn.execute("""
                SELECT id, a_number, program_sha, known_terms, failure_mode, started_at,
                       CASE WHEN json_valid(extra) THEN json_extract(extra, '$.verify_wall_s') END AS verify_s,
                       CASE WHEN json_valid(extra) THEN json_extract(extra, '$.extend_wall_s') END AS extend_s,
                       CASE WHEN json_valid(extra) THEN COALESCE(json_extract(extra, '$.attempt_call'), 'row:' || id)
                            ELSE 'row:' || id END AS call
                FROM attempts WHERE started_at >= ? ORDER BY id""", (since,)):
            a = row["a_number"]
            if calls.get(a) != row["call"]:
                calls[a], self.recent[a] = row["call"], []
            self.recent[a].append(row)

    def _ran_at_these_budgets(self, row: sqlite3.Row) -> bool:
        """False when the row records a smaller verify or extension budget than is asked about now. A
        row that does not record one (written before item 58) is taken as having had it."""
        return ((row["verify_s"] is None or row["verify_s"] >= self.budgets.verify_wall_s)
                and (row["extend_s"] is None or row["extend_s"] >= self.budgets.extend_wall_s))

    def __call__(self, cand: select.Candidate) -> bool:
        self.asked += 1
        if self._keep(cand.a_number):
            return True
        self.held += 1
        return False

    def _keep(self, a_number: str) -> bool:
        rows = self.recent.get(a_number)
        if not rows:
            return True
        if any(row["failure_mode"] == db.INTERRUPTED for row in rows):
            return True                                         # cut short: try it again
        runs = [row for row in rows if row["program_sha"]]
        if not runs:                                            # only a skip was recorded
            if any(row["failure_mode"] == DAEMON_ERROR for row in rows):
                return False
            return self.synced_at > max(row["started_at"] for row in rows)
        runs = [row for row in runs if self._ran_at_these_budgets(row)]
        if not runs:
            return True                                         # it has not been tried at these budgets
        for row in runs:
            if row["known_terms"] is not None and db.is_dead_end(
                    self.conn, a_number, row["program_sha"], row["known_terms"], self.budgets) is not None:
                return True                                     # progress: something was retired
        seen = {row["known_terms"] for row in runs if row["known_terms"] is not None}
        if seen:
            now = self.known_count(a_number)
            if now is not None and now not in seen:
                return True                                     # the entry has changed since
        return False


def pulled_at(conn: sqlite3.Connection) -> str | None:
    """When the mirror was last pulled (`meta.pulled_at`, written by a sync that pulled). A database
    whose last sync predates that key has only `synced_at`, which every sync until then wrote after a
    pull or after `--no-pull` alike; it is taken as the pull time, being the best there is."""
    return db.get_meta(conn, "pulled_at") or db.get_meta(conn, "synced_at")


def current_known_count(a_number: str) -> int | None:
    """How many known terms an attempt would see now, decided offline as selection does
    (`attempt.offline_known_terms`), or None where only an attempt could tell."""
    from .attempt import offline_known_terms
    gated = offline_known_terms(a_number)
    return gated[1].count if gated is not None else None


# ------------------------------------------------------------------ files the daemon leaves

def daemon_dir() -> Path:
    return config.DATA / "daemon"


def stop_path() -> Path:
    return daemon_dir() / "stop"


def heartbeat_path() -> Path:
    return daemon_dir() / "heartbeat.json"


def armed_path() -> Path:
    return daemon_dir() / "armed"


def is_armed() -> bool:
    """Whether the user has said the daemon may run nights here (`oeisbot daemon --arm`)."""
    try:
        return armed_path().exists()
    except OSError:
        return False


def arm() -> Path:
    """`oeisbot daemon --arm`. A real night runs only where this has been done, once, by a person.

    The daemon is the one command in this project that works for hours with nobody watching, and
    nothing about being *started* shows that anyone meant it: a scheduled task imported and forgotten, a
    script, an agent, a test that falls through its stubs (2026-11-22) all start it the same way. So
    starting is not enough. Arming is a separate, deliberate act that only `--arm` performs; an unarmed
    start logs why it did nothing and exits. `--disarm` takes it back, and is the way to make sure a
    scheduled task does nothing without removing the task."""
    path = armed_path()
    guard.refuse_if_real(path, "arming the daemon")             # never from a test (oeisbot.guard)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(datetime.now().isoformat(sep=" ", timespec="seconds") + " (local time)\n", encoding="utf-8")
    return path


def disarm() -> bool:
    """`oeisbot daemon --disarm`. True when it had been armed. A daemon already running is not stopped
    by this (`--stop` does that); it is the *next* start that will do nothing."""
    path = armed_path()
    guard.refuse_if_real(path, "disarming the daemon")
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def request_stop() -> Path:
    """`oeisbot daemon --stop`: leave the request where the running daemon looks for it."""
    path = stop_path()
    guard.refuse_if_real(path, "leaving a stop request for the daemon")     # never from a test (oeisbot.guard)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(datetime.now(timezone.utc).isoformat(timespec="seconds"), encoding="utf-8")
    return path


def read_heartbeat() -> dict | None:
    """The last state a daemon wrote, or None. Says nothing about whether one is running: `status()` does."""
    try:
        beat = json.loads(heartbeat_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return beat if isinstance(beat, dict) else None


def status() -> dict:
    """What the dashboard and `oeisbot daemon --status` show. `running` comes from the lock, never from
    the heartbeat's age: a daemon mid-pick can be quiet for an hour, and a killed one leaves a fresh file.
    The lock says *that* a command is running; which one comes from its description, and when that
    cannot be read, a held lock beside a heartbeat that has not stopped is taken as the daemon."""
    held = lock.held()
    owner = lock.read_owner() if held else None
    beat = read_heartbeat()
    if owner:
        running = owner.get("command") == "daemon"
    else:
        running = held and bool(beat) and beat.get("state") != "stopped"
    return {"running": running, "other_command": owner.get("command") if owner and not running else None,
            "heartbeat": beat, "armed": is_armed()}


# ------------------------------------------------------------------ the daemon

class NotArmed(RuntimeError):
    """`Daemon.run` was called where `oeisbot daemon --arm` has not been run."""


class Daemon:
    def __init__(self, conn: sqlite3.Connection, window: Window, *, log: Callable[[str], None] = print,
                 sync: bool = True, tiers: tuple[Tier, ...] = TIERS, started: float | None = None):
        self.conn, self.window, self.log, self.do_sync, self.tiers = conn, window, log, sync, tiers
        # wall time just before the writers' lock was taken: a stop request older than this is a leftover
        self.started = time.time() if started is None else started
        self.stopping = threading.Event()       # asked 4 times a second from inside a run: only ever a flag
        self.stop_reason: str | None = None
        self.stopping_since: float | None = None
        self.finished = threading.Event()       # `run` has returned: the watcher may go
        self.state: dict = {"state": "starting", "warnings": []}
        self.window_end: datetime | None = None
        self.first_row = 0
        # the sequence a session is on right now, or None between picks. Its own variable, not read back
        # from the heartbeat: it must be exact, because a session that raises charges this sequence
        self.in_hand: str | None = None
        self._beat_at = 0.0
        self._beat_failed = False
        self._state_lock = threading.Lock()     # the state, and the one temporary file two threads write

    # ---- the outside world, each replaced by a test -------------------------------------------------

    def now(self) -> datetime:
        return datetime.now()

    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def sleep(self, seconds: float) -> None:
        """Wait, in one-second slices: a stop ends it at once, and on Windows a single long wait would
        also keep Ctrl-C from being seen until it was over."""
        end = time.monotonic() + seconds
        while not self.stopping.is_set():
            left = end - time.monotonic()
            if left <= 0:
                return
            self.stopping.wait(min(1.0, left))

    def free_disk(self) -> int:
        config.DATA.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(config.DATA).free

    def free_ram(self) -> int:
        return sandbox.avail_phys_bytes()

    def pool(self, budgets: Budgets) -> list[select.Candidate]:
        """The pool a session at these budgets would draw from (`attempt.session_pool`)."""
        from .attempt import session_pool
        return session_pool(self.conn, budgets, model=False)[0]

    def run_session(self, budgets: Budgets, **kwargs) -> int:
        from .attempt import run_session
        return run_session(self.conn, SESSION_PICKS, budgets, log=self.log, **kwargs)

    def sync_mirror(self) -> None:
        from .attempt import snapshot_after_sync
        from .ingest import oeisdata
        oeisdata.sync(self.conn, self.log, pull=True, timeout=SYNC_TIMEOUT_S)
        snapshot_after_sync(self.conn, self.log)

    def hard_exit(self, why: str) -> None:
        """The last resort after `STOP_GRACE_S`: end the process from the watcher thread. A git command
        of the sync is ended first -- it is this process's child but in no job, and would otherwise go
        on rewriting the mirror after the lock that protects it had been let go."""
        self.log(f"daemon: {why}; ending the process")
        try:
            from .ingest import oeisdata
            oeisdata.end_running_git()
        finally:
            os._exit(3)

    # ---- stopping -----------------------------------------------------------------------------------

    def stop(self, reason: str) -> None:
        """Ask the loop, and the run in hand, to stop. The first reason given is the one reported."""
        if not self.stopping.is_set():
            self.stop_reason = reason
            self.stopping_since = time.monotonic()
            self.stopping.set()

    def poll(self) -> None:
        """Look at the stop request and the clock, and refresh the heartbeat when it is due. Called every
        `POLL_S` by the watcher thread while the night runs, and by the loop itself between steps; never
        from inside a run (the run only reads `stopping`)."""
        try:
            if stop_path().exists():
                self.stop("stop requested (`oeisbot daemon --stop`)")
        except OSError:
            pass
        if self.window_end is not None and seconds_until(self.window_end, self.now()) <= 0:
            self.stop(f"the window {self.window} closed")
        if time.monotonic() - self._beat_at >= HEARTBEAT_S:
            self._write_beat()

    def remaining_s(self) -> float:
        """Seconds until the window closes; without a closing time (`always`), no limit."""
        return seconds_until(self.window_end, self.now()) if self.window_end is not None else float("inf")

    # ---- the heartbeat ------------------------------------------------------------------------------

    def beat(self, **changes) -> None:
        """Record what the daemon is doing, from the main loop. `progress_at` moves only here, so a
        reader can tell a daemon that is working from one whose watcher is still ticking over a hung
        call (`at` moves either way)."""
        with self._state_lock:
            self.state.update(changes)
            self.state["progress_at"] = self.now_utc().isoformat(timespec="seconds")
        self._write_beat()

    def warn(self, text: str) -> None:
        """Something the user should see without reading the log: kept in the heartbeat for the night."""
        self.log(f"daemon: {text}")
        with self._state_lock:
            if text not in self.state["warnings"]:
                self.state["warnings"].append(text)

    def _write_beat(self) -> None:
        """Write the heartbeat, in a file: `meta` would be the obvious place, but every write there moves
        the stamp that throws away the dashboard's cached Pick-map pool. Never raises -- a full disk, or
        a scanner holding the file open at that instant, must not stop a night. The whole write is under
        one lock: the watcher and the main loop share the temporary file."""
        guard.refuse_if_real(heartbeat_path(), "writing the daemon's heartbeat")     # never from a test
        with self._state_lock:
            self.state.update(
                pid=os.getpid(), window=str(self.window), at=self.now_utc().isoformat(timespec="seconds"),
                window_ends=self.window_end.isoformat(timespec="minutes") if self.window_end else None,
                stop_reason=self.stop_reason,
                stopping_for_s=round(time.monotonic() - self.stopping_since) if self.stopping_since else None)
            body = json.dumps(self.state, indent=1)
            self._beat_at = time.monotonic()
            path = heartbeat_path()
            error: OSError | None = None
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".part")
                tmp.write_text(body, encoding="utf-8")
                for attempt in range(5):        # Windows: replace fails while another handle has the file open
                    try:
                        tmp.replace(path)
                        error = None
                        break
                    except OSError as e:
                        error = e
                        time.sleep(0.05)
            except OSError as e:
                error = e
            failed, self._beat_failed = self._beat_failed, error is not None
        if error is not None and not failed:    # said once per streak, outside the lock
            self.log(f"daemon: could not write {path} ({type(error).__name__}: {error}); going on without it")

    # ---- recovery -----------------------------------------------------------------------------------

    def recover(self) -> None:
        """Tidy up after a daemon (or a session) that was killed. Safe because this process holds the
        writers' lock: no other session is running, so every open session row is an orphan."""
        try:
            # a request left by an earlier night, or every later night would stop as it started. One made
            # since this daemon took the lock is for this daemon, and is left for `poll` to honour
            if stop_path().exists() and stop_path().stat().st_mtime < self.started:
                stop_path().unlink()
        except OSError as e:
            self.log(f"daemon: could not remove the old stop request {stop_path()} ({e})")
        for row in self.conn.execute("SELECT id FROM sessions WHERE finished_at IS NULL ORDER BY id").fetchall():
            db.finish_session(self.conn, row["id"])
            with self.conn:
                # it ended when its last row was written, not now: a session killed days ago must not
                # read as days long
                self.conn.execute("""
                    UPDATE sessions SET finished_at = COALESCE(
                               (SELECT MAX(COALESCE(finished_at, started_at)) FROM attempts WHERE session_id = ?1), started_at),
                           note = COALESCE(note, '') || ' (closed by recovery: its process ended mid-session)'
                    WHERE id = ?1""", (row["id"],))
            self.log(f"daemon: closed session {row['id']}, left open by a process that ended mid-session; "
                     "the run it was on, if any, was not recorded")
        swept = self.sweep_scratch()
        if swept:
            self.log(f"daemon: removed {swept} leftover run director{'y' if swept == 1 else 'ies'} from {config.SCRATCH}")
        from .attempt import pending_path
        for row in db.pending_rechecks(self.conn):
            if not pending_path(row["id"]).exists():
                self.warn(f"attempt #{row['id']} ({row['a_number']}) waits for a re-check but its saved result "
                          f"is missing; its sequence stays blocked until `oeisbot recheck --release {row['id']}`")

    def sweep_scratch(self) -> int:
        """Remove run directories a killed process left in `data/scratch` (a run deletes its own in a
        `finally`, which a kill skips). Deliberately narrow, because the lock does not cover everything
        that uses that directory -- the test suite runs real sandboxed programs there, and may be running
        now: only names the harness gives a run (`A123456-gp-1a2b3c4d`), and only ones last changed more
        than `SCRATCH_ORPHAN_AGE_S` ago, longer than any run can last. Anything else is left alone."""
        if not config.SCRATCH.is_dir():
            return 0
        guard.refuse_if_real(config.SCRATCH, "sweeping old run directories")    # never from a test (oeisbot.guard)
        swept = 0
        cutoff = time.time() - SCRATCH_ORPHAN_AGE_S
        for child in config.SCRATCH.iterdir():
            try:
                if child.is_dir() and _RUN_DIR.fullmatch(child.name) and child.stat().st_mtime < cutoff:
                    shutil.rmtree(child, ignore_errors=True)
                    swept += not child.exists()
            except OSError:
                pass
        return swept

    # ---- the machine --------------------------------------------------------------------------------

    def machine_problem(self) -> tuple[str, str] | None:
        """(state, what is short) when a pick should not be started now, else None."""
        b = config.DEFAULT_BUDGETS
        disk = self.free_disk()
        if disk < b.reserve_disk_bytes + DISK_MARGIN_BYTES:
            return "paused_disk", (f"{disk / GiB:.1f} GiB free on the data drive; a run needs "
                                   f"{(b.reserve_disk_bytes + DISK_MARGIN_BYTES) / GiB:.0f} GiB")
        ram = self.free_ram()
        if ram < b.reserve_phys_bytes + RAM_MARGIN_BYTES:
            return "paused_ram", (f"{ram / GiB:.1f} GiB of RAM free; a run needs "
                                  f"{(b.reserve_phys_bytes + RAM_MARGIN_BYTES) / GiB:.0f} GiB")
        return None

    def wait_for_the_machine(self, at_least_once: bool = False) -> None:
        """Hold here while the machine is short of disk or RAM, looking again every `PAUSE_S`. With
        `at_least_once`, after a session was cut short for that reason, one pause is taken even if the
        machine looks fine at this instant: memory hovering at the threshold would otherwise start a
        session, fail its first pick's check and start another, for as long as it hovered."""
        said = None
        while not self.stopping.is_set():
            problem = self.machine_problem()
            if problem is None and not at_least_once:
                return
            state, why = problem or ("paused_machine", "the machine was short a moment ago; waiting once "
                                                       "before looking again")
            at_least_once = False
            if why != said:
                said = why
                self.log(f"daemon: paused ({why}); looking again every {PAUSE_S / 60:g} min")
            self.beat(state=state, detail=why, a_number=None)
            self.sleep(PAUSE_S)
            self.poll()

    def machine_failures_in_a_row(self) -> int:
        """How many of the newest *picks* since this daemon started ended in a stop that is the machine's
        doing (an earlier program of the same pick may have failed for its own reasons). Picks, not rows
        -- one pick can write a row per program -- and counted across sessions, so a streak is not
        forgotten at a session's end."""
        calls: list[str] = []
        for row in self.conn.execute("""
                SELECT failure_mode,
                       CASE WHEN json_valid(extra) THEN COALESCE(json_extract(extra, '$.attempt_call'), 'row:' || id)
                            ELSE 'row:' || id END AS call
                FROM attempts WHERE id > ? ORDER BY id DESC LIMIT ?""", (self.first_row, BREAKER_RUN * 4)):
            if row["failure_mode"] not in MACHINE_FAILURES:
                break
            if row["call"] not in calls:
                calls.append(row["call"])
        return len(calls)

    # ---- one night ----------------------------------------------------------------------------------

    def sync_is_stale(self) -> bool:
        synced = pulled_at(self.conn)
        try:
            age = self.now_utc() - datetime.fromisoformat(synced)
        except (TypeError, ValueError):
            return True
        return age > timedelta(days=STALE_SYNC_DAYS)

    def run(self) -> str:
        """One window's work. Returns why it ended (also logged, and left in the heartbeat).

        Refuses unless armed, here as well as in `command`: a script or a test that builds a `Daemon`
        itself and calls this is as much a start as the command is, and holds no lock while it does.
        And never from a test against the real project (oeisbot.guard): this one call covers recovery,
        the heartbeat and everything else a night writes under `data/daemon/`."""
        guard.refuse_if_real(daemon_dir(), "running a daemon night")
        if not is_armed():
            raise NotArmed("the daemon is not armed: a night runs here only after `oeisbot daemon --arm`")
        if self.window.always:
            self.window_end = None              # no closing time: runs until stopped or out of work
        else:
            self.window_end = self.window.ends_at(self.now())
            if self.window_end is None:
                # Said in the log and nowhere else. The heartbeat still holds last night's result and
                # its warnings, and a start by day (the machine was off at the opening and the task
                # caught up, or someone pressed Run) must not replace them with "nothing started"
                why = f"outside the window {self.window}; nothing started"
                self.log(f"daemon: {why}")
                return why
        watcher = threading.Thread(target=self._watch, name="daemon-watch", daemon=True)
        watcher.start()
        try:
            self.recover()
            self.first_row = self.conn.execute("SELECT COALESCE(MAX(id), 0) FROM attempts").fetchone()[0]
            closes = f"closes {self.window_end:%Y-%m-%d %H:%M}" if self.window_end else "no closing time"
            self.log(f"daemon: started, window {self.window} ({closes}), tiers {', '.join(t.name for t in self.tiers)}")
            waiting = self.conn.execute("SELECT COUNT(*) FROM reviews WHERE status IN ('new', 'reviewing')").fetchone()[0]
            if waiting:
                # each one keeps its sequence out of the draw until the user decides; nobody reads a log
                # every morning, so it is said every night
                self.log(f"daemon: {waiting} review(s) waiting for a person (`oeisbot review list`)")
            self.beat(reviews_waiting=waiting)
            self.poll()
            if self.do_sync and not self.stopping.is_set():
                self.beat(state="sync", a_number=None, detail=None)
                from .ingest.oeisdata import MirrorUnusable
                try:
                    self.sync_mirror()
                except MirrorUnusable as e:
                    # half rewritten, and it could not be put back: an entry read now may be cut off in
                    # the middle of a term, and a correct program would be retired for a wrong one
                    self.warn(f"sync failed and left the mirror unusable ({e}); no sessions tonight. "
                              "Run `oeisbot sync` by hand")
                    return self._finish("the mirror could not be used after a failed sync")
                except Exception as e:          # noqa: BLE001 -- a night is not lost to a network fault
                    self.warn(f"sync failed ({type(e).__name__}: {e}); going on with the mirror as it is "
                              f"(last pulled {pulled_at(self.conn) or 'never'})")
            return self._finish(self._sessions())
        finally:
            self.finished.set()                 # ends the watcher
            watcher.join(timeout=5 * POLL_S)

    def _watch(self) -> None:
        """The second thread: sees a stop request or the window closing while the main thread is inside
        a run, keeps the heartbeat's `at` moving, and ends the process if a stop is not obeyed."""
        while not self.finished.wait(POLL_S):
            try:
                self.poll()
                if self.stopping_since is not None and time.monotonic() - self.stopping_since > STOP_GRACE_S:
                    self.hard_exit(f"asked to stop {STOP_GRACE_S / 60:g} min ago ({self.stop_reason}) and the "
                                   "main thread has not come back")
            except Exception as e:              # noqa: BLE001 -- the watcher must outlive any one fault
                try:
                    self.log(f"daemon: watcher fault ({type(e).__name__}: {e})")
                except Exception:               # noqa: BLE001 -- even a log that cannot be written
                    pass

    def _finish(self, why: str) -> str:
        self.log(f"daemon: finished: {why}")
        try:
            # a request that was honoured is used up. (One that arrives after this is removed at the
            # next start, being older than it.)
            if self.stop_reason and "stop requested" in self.stop_reason:
                stop_path().unlink(missing_ok=True)
        except OSError:
            pass
        self.beat(state="stopped", detail=why, a_number=None, session=None)
        return why

    def _sessions(self) -> str:
        level = 0
        errors = 0
        stored_tonight = False
        pause_once = False
        while True:
            self.poll()
            self.wait_for_the_machine(at_least_once=pause_once)
            pause_once = False
            if self.stopping.is_set():
                return self.stop_reason or "stopped"
            tier = self.tiers[level]
            budgets = tier.budgets
            need = start_gate_s(budgets)
            if self.remaining_s() < need:
                return (f"{max(self.remaining_s(), 0) / 60:.0f} min left in the window {self.window}, and a pick at "
                        f"tier {tier.name} needs {need / 60:.0f} to be verified")
            why_not: dict = {}
            sid = None
            try:
                # Look before starting a session: an exhausted tier then costs a few seconds and no row.
                # (The first version learnt it from an empty session, three of them a night for ever.)
                self.beat(state="running", a_number=None, tier=tier.name, detail="building the pool", session=None)
                cool = Cooldown(self.conn, budgets, self.now_utc())
                drawable = {c.a_number for c in self.pool(budgets) if cool(c)}
                if not drawable:
                    self.log(f"daemon: tier {tier.name}: pool {cool.asked}, {cool.held} cooling down, nothing to draw")
                    if level + 1 == len(self.tiers):
                        return "nothing left to draw at any tier"
                    if self.sync_is_stale():
                        return (f"nothing left to draw at tier {tier.name}, and the mirror has not synced for "
                                f"over {STALE_SYNC_DAYS} days: not climbing to longer budgets on stale data")
                    level += 1
                    self.log(f"daemon: moving to tier {self.tiers[level].name}")
                    continue

                def may_start() -> bool:
                    self.in_hand = None             # the pick before this one is over, whatever happens next
                    self.poll()
                    if self.stopping.is_set():
                        return False                # the session asks `should_stop` first and says so
                    if self.remaining_s() < need:
                        why_not["why"] = "window"
                    elif self.machine_problem() is not None:
                        why_not["why"] = "machine"
                    elif self.machine_failures_in_a_row() >= BREAKER_RUN:
                        why_not["why"] = "breaker"
                    return "why" not in why_not

                def before_attempt(a_number: str) -> None:
                    self.in_hand = a_number         # first, before anything here that could raise
                    self.beat(state="running", a_number=a_number, tier=tier.name, detail=None,
                              synced_at=pulled_at(self.conn))

                # The Pick map's snapshot: once a night, at the lowest tier. The dashboard builds its live
                # pool under the newest snapshot's budgets, and one per session would leave it comparing
                # with the pool of an hour ago
                self.in_hand = None
                sid = self.run_session(budgets, note=f"daemon=1 tier={tier.name}",
                                       keep=lambda c: c.a_number in drawable,
                                       before_attempt=before_attempt, may_start=may_start,
                                       should_stop=self.stopping.is_set,
                                       snapshot=level == 0 and not stored_tonight)
                stored_tonight = stored_tonight or level == 0
                errors = 0
                self.in_hand = None
                self._note_wins_cut_short(sid)
            except Exception as e:                  # noqa: BLE001 -- see `_session_raised`
                errors += 1
                self._session_raised(e, tier)
                self.in_hand = None
                if errors >= ERROR_RUN:
                    return (f"{errors} sessions in a row raised ({type(e).__name__}: {e}); stopped rather than "
                            "go on. The traceback is in the daemon's log")
                continue
            ran = self.conn.execute("SELECT COUNT(*) FROM attempts WHERE session_id = ?", (sid,)).fetchone()[0]
            self.log(f"daemon: session {sid} at tier {tier.name}: {ran} attempt row(s); pool {cool.asked}, "
                     f"{cool.held} cooling down")
            if self.stopping.is_set():
                return self.stop_reason or "stopped"
            why = why_not.get("why")
            if why == "breaker":
                return (f"{BREAKER_RUN} picks in a row ended as {' / '.join(MACHINE_FAILURES)}: the machine or "
                        "the network, not the programs. Stopped rather than spend the pool on it")
            if why == "machine":
                pause_once = True                   # wait before trying again, even if it looks fine now
                continue
            if why == "window":
                continue                            # the top of the loop ends the night, and says why
            if ran == 0:
                return (f"session {sid} had {len(drawable)} candidate(s) to draw and started none; stopping "
                        "rather than loop")

    def _note_wins_cut_short(self, sid: int) -> None:
        """A run stopped by the window (or a stop request) after it had found new terms is still a win:
        it is re-checked and opens a review like any other, and its sequence then leaves the draw until
        the user decides. But it stopped early, and a full extension might have found more. That is the
        one cost of letting the window interrupt an extension, and it is said where the user will see it."""
        for row in self.conn.execute("""SELECT a_number, new_terms FROM attempts WHERE session_id = ? AND failure_mode = ?
                                        AND outcome IN ('extended', 'recheck_pending') ORDER BY id""",
                                     (sid, db.INTERRUPTED)):
            self.warn(f"{row['a_number']}: {row['new_terms']} new term(s) found before the run was stopped; it did "
                      "not use its whole extension, so a longer run might find more")

    def _session_raised(self, e: Exception, tier: Tier) -> None:
        """A session raised: the daemon's own fault, the database's, or one entry's (a program the plan
        cannot read, a b-file that breaks the parser). If a pick was in hand (`in_hand`: set as the pick
        starts, cleared when the session asks about the next one) it may have no row yet -- a run is
        recorded after it ends -- so it would be drawn again in the next session and end the next night
        at the same place. It gets a skip row of its own here, which cools it for the whole period.
        Between picks nothing is charged to anyone. The traceback goes to the log: a scheduled task has
        no console for it to go to."""
        a = self.in_hand
        self.log(f"daemon: a session at tier {tier.name} raised {type(e).__name__}: {e}"
                 + (f" (while on {a})" if a else "") + "\n" + "".join(traceback.format_exception(e)).rstrip())
        if a:
            try:
                db.record_skip(self.conn, a, "daemon", DAEMON_ERROR, f"{type(e).__name__}: {e}"[:500])
                self.warn(f"{a} raised {type(e).__name__} outside the sandbox and is held back for "
                          f"{COOLDOWN_DAYS} days; see the daemon's log")
            except Exception as again:              # noqa: BLE001 -- the database may be what is wrong
                self.log(f"daemon: could not record that ({type(again).__name__}: {again})")


def keep_awake(on: bool) -> None:
    """Ask Windows not to sleep while the daemon works. It stops *idle* sleep only -- a closed lid, the
    power button and a scheduled hibernate still win -- which is why a slept-through verification is
    handled where it is judged (`db.is_dead_end`'s CPU condition), not assumed away here. The request
    belongs to the calling thread and ends with it, so a killed daemon leaves nothing set."""
    if sys.platform != "win32":
        return
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


# ------------------------------------------------------------------ the command

def log_to(directory: Path) -> Callable[[str], None]:
    """Append to `daemon-YYYYMMDD.log` in `directory` with the time, then print. Never raises: the file
    is written first and as UTF-8, and a console or a redirected stdout that cannot show a character (an
    OEIS name with a letter outside the code page, under Task Scheduler) must not end a night.
    (What it refuses, loudly and once, is being pointed at the real `data/daemon/` from a test.)"""
    guard.refuse_if_real(directory, "writing the daemon's log")

    def log(message: str) -> None:
        stamp = datetime.now()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with open(directory / f"daemon-{stamp:%Y%m%d}.log", "a", encoding="utf-8") as f:
                f.write(f"{stamp:%H:%M:%S} {message}\n")
        except OSError:
            pass
        try:
            print(message, flush=True)
        except (UnicodeError, OSError, ValueError):
            pass
    return log


def describe(report: dict) -> str:
    """`oeisbot daemon --status`, as text."""
    beat = report["heartbeat"] or {}
    warnings = "".join(f"\nwarning: {w}" for w in beat.get("warnings") or [])
    if report["running"]:
        doing = {"running": f"running {beat.get('a_number') or '(between picks)'} at tier {beat.get('tier')}",
                 "sync": "syncing the mirror"}.get(beat.get("state"), beat.get("state") or "starting")
        detail = f" ({beat['detail']})" if beat.get("detail") else ""
        stopping = (f"\nstop asked for {beat['stopping_for_s']} s ago ({beat.get('stop_reason')}); still finishing"
                    if beat.get("stopping_for_s") is not None else "")
        return (f"daemon is running (pid {beat.get('pid', '?')}): {doing}{detail}{stopping}\n"
                f"window {beat.get('window', '?')}, closes {beat.get('window_ends') or 'never'} local time; "
                f"mirror last synced {beat.get('synced_at') or 'unknown'}\n"
                f"last step {beat.get('progress_at', '?')} UTC; heartbeat {beat.get('at', '?')} UTC{warnings}")
    other = f"; `oeisbot {report['other_command']}` holds the writers' lock" if report["other_command"] else ""
    if not report.get("armed", False):
        other += ("\nnot armed: a start will do nothing until you run `oeisbot daemon --arm`"
                  " (that is how a night is allowed to run here)")
    if not beat:
        return f"daemon is not running{other}\nno daemon has run here yet"
    if beat.get("state") != "stopped":
        last = (f"\nlast daemon: did not finish; it was {beat.get('state')} at {beat.get('at')} UTC when its "
                "process ended. The next start tidies up after it")
    else:
        last = f"\nlast daemon: stopped at {beat.get('at')} UTC ({beat.get('detail')})"
    return f"daemon is not running{other}{last}{warnings}"


def _mutant_left_in_tree() -> bool:
    """The harness's sentinel is there, and this process is not one of the harness's own test runs (which
    it starts with `OEISBOT_MUTATING=1` while the sentinel it wrote is, rightly, in place)."""
    return (config.ROOT / MUTANT_SENTINEL).exists() and os.environ.get("OEISBOT_MUTATING") != "1"


def command(args) -> int:
    """`oeisbot daemon`. `--stop` and `--status` only leave a request or read; running takes the writers'
    lock for the whole window, so every other command that runs, syncs or fetches is refused meanwhile."""
    if args.status:
        print(describe(status()))
        return 0
    if _mutant_left_in_tree():
        # `data/item58/mutate.py` was killed with a mutant still in the code: what would run is not the
        # program. It may be a mutant that removes a safeguard, so nothing is started, armed or stopped
        raise SystemExit(f"`oeisbot daemon` refused: {config.ROOT / MUTANT_SENTINEL} says a mutation run was "
                         "interrupted and left a changed file in the code. Restore it as that file says, then "
                         "delete it")
    if getattr(args, "arm", False):
        print(f"armed ({arm()}): `oeisbot daemon` will now run a night when it is started inside its window.\n"
              "Take it back with `oeisbot daemon --disarm`.")
        return 0
    if getattr(args, "disarm", False):
        print("disarmed: a start will now do nothing" + ("" if disarm() else " (it was not armed)")
              + (". A daemon is running now and is not stopped by this: use `oeisbot daemon --stop`"
                 if status()["running"] else ""))
        return 0
    if args.stop:
        if not status()["running"]:
            print("no daemon is running; nothing to stop")
            return 0
        print(f"stop requested ({request_stop()}): the daemon interrupts the run in hand, retiring nothing, "
              "and exits -- usually within seconds, longer if it is syncing or that run had just found new terms")
        return 0
    try:
        window = Window.parse(args.window)
        target = getattr(args, "task_xml", None)
        if target:                                  # writes or prints a definition; registers and starts nothing
            from .schedule import task_xml, write_task
            if target == "-":
                print(task_xml(window), end="")
            else:
                print(f"wrote {write_task(Path(target), window)}; import it with\n"
                      f'  schtasks /create /tn "OEISBot daemon" /xml "{target}"')
            return 0
    except ValueError as e:
        raise SystemExit(str(e))
    import signal
    for stream in (sys.stdout, sys.stderr):     # a redirected stream in a legacy code page: escape, never raise
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="backslashreplace")
            except (OSError, ValueError):
                pass
    log = log_to(daemon_dir())
    if not is_armed():
        # Before the lock, the database and everything else: an unarmed start touches nothing but its log
        log("daemon: not started: not armed. A night runs here only after `oeisbot daemon --arm` (see "
            "`docs/daemon.md`); this start did nothing")
        return 2
    try:
        with contextlib.ExitStack() as held:
            started = _take_the_lock(held, window, log)
            if started is None:
                return 1
            try:
                conn = db.connect()
            except Exception as e:      # noqa: BLE001 -- a scheduled task has no console to say this on
                log(f"daemon: not started: the database could not be opened ({type(e).__name__}: {e})")
                return 1
            daemon = Daemon(conn, window, log=log, sync=not args.no_sync, started=started)

            def on_signal(signum, frame):
                if daemon.stopping.is_set():
                    raise KeyboardInterrupt     # the second press is not asked to wait
                daemon.stop("interrupted from the console")
                try:
                    log("daemon: stopping after the run in hand; press Ctrl-C again to end at once")
                except RuntimeError:            # the main thread was inside `print` when the signal came
                    pass

            # Ctrl-C and Ctrl-Break in a console. Closing the window, logging off, Task Scheduler's "End"
            # and `taskkill` do not come through here on Windows: they end the process, and the next
            # start's recovery is what handles them
            old = {name: signal.signal(getattr(signal, name), on_signal)
                   for name in ("SIGINT", "SIGBREAK", "SIGTERM") if hasattr(signal, name)}
            try:
                keep_awake(True)
                daemon.run()
            except KeyboardInterrupt:
                log("daemon: ended at once from the console; the run in hand, if any, was not recorded")
                daemon.beat(state="stopped", detail="ended at once from the console", a_number=None)
                return 130
            except (guard.RealProjectRefused, NotArmed) as e:
                # A refusal, not a fault: disarmed between the check above and the night, or the guard is
                # on in this process. Nothing ran. The same code as an unarmed start, and no heartbeat:
                # there is no night to describe
                log(f"daemon: not started: {e}")
                return 2
            except Exception as e:      # noqa: BLE001 -- a scheduled task has no console for a traceback
                log(f"daemon: ended by a fault ({type(e).__name__}: {e})\n"
                    + "".join(traceback.format_exception(e)).rstrip())
                daemon.beat(state="stopped", detail=f"ended by a fault: {type(e).__name__}: {e}", a_number=None)
                return 1
            finally:
                keep_awake(False)
                for name, handler in old.items():
                    signal.signal(getattr(signal, name), handler)
                conn.close()
    except OSError as e:
        log(f"daemon: not started: {type(e).__name__}: {e}")
        raise SystemExit(f"`oeisbot daemon` not started: {type(e).__name__}: {e}")
    except (guard.RealProjectRefused, NotArmed) as e:
        # the guard is on in this process (a test's environment reached a real start), or the arming was
        # taken away between the check above and the night: said, not left as a traceback nobody sees
        log(f"daemon: not started: {e}")
        return 2
    return 0


LOCK_RETRY_S = 60.0


def _take_the_lock(held: contextlib.ExitStack, window: Window, log: Callable[[str], None]) -> float | None:
    """Take the writers' lock for the daemon, waiting while another command holds it and the window is
    open. Returns the time just before it was taken, or None when the window closed first (or, outside
    any window, at the first refusal).

    The scheduled task fires once a day. The first version gave up at the first refusal, so an
    `oeisbot attempt` started by hand at 21:30 and still running at 22:00 cost the whole night -- and
    said so only on a console the task does not have. Now it is logged, and tried again every minute."""
    said = False
    while True:
        started = time.time()
        try:
            held.enter_context(lock.writer("daemon"))
            return started
        except lock.Held as e:
            waits = not window.always and window.ends_at(_now()) is not None
            if not said:
                log(f"daemon: {e}" + (f". Trying again every {LOCK_RETRY_S:g} s while the window is open" if waits else ""))
            if not waits:
                log("daemon: not started: the writers' lock is held"
                    + (" and the window has closed" if said else "" if window.always else " and the window is not open"))
                return None
            said = True
            time.sleep(LOCK_RETRY_S)


def _now() -> datetime:
    return datetime.now()
