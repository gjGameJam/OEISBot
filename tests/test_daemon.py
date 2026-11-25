"""`oeisbot daemon` (item 58), driven in memory: a fake clock, a fake machine and a scripted `run_session`.

`tests/test_attempt.py` ends with two tests that run the real session loop through the sandbox, to pin the
wiring the fakes here stand in for. Nothing in this file contacts oeis.org, runs git, or opens the real
database: `tests/conftest.py` makes each of those raise, and `tests/test_isolation.py` checks that it does.
"""
from __future__ import annotations

import builtins
import json
import os
import signal
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from oeisbot import config, daemon, db, lock, select
from oeisbot.config import GiB
from oeisbot.daemon import Cooldown, Daemon, Tier, Window

BASE, V600, LONG = (t.budgets for t in daemon.TIERS)
NOW = datetime(2026, 11, 22, 22, 0, tzinfo=timezone.utc)


def at(text: str) -> datetime:
    return datetime.fromisoformat(text)


# ------------------------------------------------------------------ the window

@pytest.mark.parametrize("text, start, end", [("22:00-08:00", 1320, 480), ("09:30-17:05", 570, 1025),
                                              (" 0:00 - 24:00 ", 0, 0), ("always", 0, 0), (" ALWAYS ", 0, 0)])
def test_a_window_is_read_as_local_hours(text, start, end):
    w = Window.parse(text)
    assert (w.start_min, w.end_min) == (start, end)


@pytest.mark.parametrize("text", ["", "22-8", "22:00", "25:00-08:00", "24:00-08:00", "22:60-08:00", "22:00-08:60",
                                  "22:00-24:01", "a:b-c:d", "22:00-08:00-09:00", "-1:00-08:00", "22:00-22:00"])
def test_a_window_that_cannot_be_read_says_what_was_expected(text):
    with pytest.raises(ValueError, match="expected HH:MM-HH:MM in local time with two different times"):
        Window.parse(text)


def test_a_window_prints_as_it_was_written():
    assert str(Window.parse("22:00-08:00")) == "22:00-08:00" and str(Window.parse("9:05-17:00")) == "09:05-17:00"
    assert str(Window.parse("always")) == "always" and Window.parse("always").always
    assert Window.parse("00:00-24:00").always and not Window.parse("22:00-08:00").always


def test_a_window_over_midnight_closes_the_next_morning():
    w = Window.parse("22:00-08:00")
    assert w.ends_at(at("2026-11-22 22:00:00")) == at("2026-11-23 08:00")       # the opening minute is inside
    assert w.ends_at(at("2026-11-22 23:59:59.750000")) == at("2026-11-23 08:00")    # a whole minute, whatever the tick
    assert w.ends_at(at("2026-11-23 00:00:00")) == at("2026-11-23 08:00")       # after midnight: this morning
    assert w.ends_at(at("2026-11-23 07:59:59")) == at("2026-11-23 08:00")
    assert w.ends_at(at("2026-11-23 08:00:00")) is None                         # the closing minute is outside
    assert w.ends_at(at("2026-11-22 21:59:59")) is None
    assert w.ends_at(at("2026-11-22 12:00:00")) is None


def test_a_window_inside_one_day_closes_the_same_day():
    w = Window.parse("09:00-17:00")
    assert w.ends_at(at("2026-11-22 09:00:00")) == at("2026-11-22 17:00")
    assert w.ends_at(at("2026-11-22 16:59:59")) == at("2026-11-22 17:00")
    assert w.ends_at(at("2026-11-22 17:00:00")) is None and w.ends_at(at("2026-11-22 08:59:59")) is None
    assert w.ends_at(at("2026-11-22 23:00:00")) is None
    assert Window.parse("always").ends_at(at("2026-11-22 03:00:00")) is None    # no closing time to give


def test_seconds_until_is_real_elapsed_time():
    assert daemon.seconds_until(at("2026-11-23 08:00"), at("2026-11-22 22:00")) == 10 * 3600
    assert daemon.seconds_until(at("2026-11-22 22:00"), at("2026-11-22 22:30")) == -1800


def test_a_night_with_a_clock_change_is_measured_in_real_seconds():
    """Ten wall-clock hours are nine real ones on the night the clocks go forward, eleven on the night
    they go back. Skipped where the machine's zone has no daylight saving."""
    w = Window.parse("22:00-08:00")
    spring = daemon.seconds_until(w.ends_at(at("2027-03-13 22:00")), at("2027-03-13 22:00"))
    autumn = daemon.seconds_until(w.ends_at(at("2027-11-06 22:00")), at("2027-11-06 22:00"))
    if spring == autumn == 36000:
        pytest.skip("this machine's time zone has no clock change on those nights")
    assert {spring, autumn} == {9 * 3600, 11 * 3600}


def test_a_pick_is_started_while_there_is_time_to_verify_it():
    from oeisbot.attempt import MAX_PROGRAMS_PER_SEQUENCE
    assert (BASE.verify_wall_s, BASE.extend_wall_s) == (60, 1800)
    assert daemon.start_gate_s(BASE) == MAX_PROGRAMS_PER_SEQUENCE * 60 + daemon.PICK_SLACK_S == 480
    assert daemon.start_gate_s(V600) == daemon.start_gate_s(LONG) == 3 * 600 + 300     # the extension is not counted


def test_a_tier_changes_only_the_two_times():
    """Never a new `Budgets` field: `attempt._checked` compares the field set of a saved win both ways."""
    import dataclasses
    for tier in daemon.TIERS:
        b, d = dataclasses.asdict(tier.budgets), dataclasses.asdict(config.DEFAULT_BUDGETS)
        assert set(b) == set(d)
        assert {k for k in b if b[k] != d[k]} <= {"verify_wall_s", "extend_wall_s"}
    assert [(t.name, t.verify_s, t.extend_s) for t in daemon.TIERS] == [
        ("base", 60, 1800), ("verify600", 600, 1800), ("long", 600, 10800)]


# ------------------------------------------------------------------ fixtures

@pytest.fixture
def home(tmp_path, monkeypatch):
    """A data directory, scratch directory, mirror and database of the test's own."""
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(config, "SCRATCH", tmp_path / "data" / "scratch")
    monkeypatch.setattr(config, "OEISDATA", tmp_path / "data" / "oeisdata")
    monkeypatch.setattr(lock, "ACQUIRE_PAUSE_S", 0.0)
    monkeypatch.setattr(lock, "PROBE_PAUSE_S", 0.0)
    conn = db.connect(tmp_path / "t.sqlite3")
    daemon.arm()                                     # as the user must, once, before any night runs
    yield conn, tmp_path
    conn.close()


def cand(a: str) -> select.Candidate:
    return select.Candidate(a, f"seq {a}", 1.0, 1.0, "pari")


def add_attempt(conn, a, *, when: datetime, mode="searched_bound", outcome="verified", sha="s1", known=10,
                call="c1", session=None, verified=1, budgets=BASE, extra=None, wall=60.0, cpu=59.0) -> int:
    """A run row as `attempt._Attempter.run` writes it: the budgets it ran under are in `extra`."""
    body = {"verify_wall_s": budgets.verify_wall_s, "extend_wall_s": budgets.extend_wall_s,
            "mem_bytes": budgets.mem_bytes, "mem_cap_bytes": budgets.mem_bytes} if budgets is not None else {}
    body.update(extra or {})
    if call is not None:
        body["attempt_call"] = call
    with conn:
        return conn.execute(
            """INSERT INTO attempts(session_id, a_number, strategy, program_sha, started_at, finished_at, verified,
                                    known_terms, new_terms, runtime_s, cpu_s, outcome, failure_mode, extra)
               VALUES (?, ?, 'pari:a(n)', ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)""",
            (session, a, sha, stamp(when), stamp(when), verified, known, wall, cpu, outcome, mode,
             json.dumps(body))).lastrowid


def stamp(when: datetime) -> str:
    return when.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")


def add_skip(conn, a, reason, *, when: datetime) -> int:
    rid = db.record_skip(conn, a, "pari", reason, "detail")
    with conn:
        conn.execute("UPDATE attempts SET started_at = ?, finished_at = ? WHERE id = ?", (stamp(when), stamp(when), rid))
    return rid


def fresh_sync(conn, when=NOW):
    db.set_meta(conn, "synced_at", stamp(when))


# ------------------------------------------------------------------ the cooldown

def cool(conn, known=lambda a: 10, budgets=BASE, **kw) -> Cooldown:
    return Cooldown(conn, budgets, NOW, known_count=known, **kw)


def test_a_sequence_never_attempted_is_not_cooled(home):
    conn, _ = home
    c = cool(conn)
    assert c(cand("A000001")) and (c.asked, c.held) == (1, 0)


def test_an_attempt_that_retired_nothing_cools_its_sequence_for_fourteen_days(home):
    """`searched_bound` is deliberately not a dead end: the sequence stays in the pool exactly as it was.
    A weekly session never met it twice running; a nightly loop would."""
    conn, _ = home
    assert daemon.COOLDOWN_DAYS == 14
    add_attempt(conn, "A000001", when=NOW - timedelta(days=1), mode="searched_bound")
    add_attempt(conn, "A000002", when=NOW - timedelta(days=14), mode="over_prediction")           # the last day counts
    add_attempt(conn, "A000003", when=NOW - timedelta(days=14, seconds=1), mode="searched_bound")  # too old
    c = cool(conn)                                               # the default period, not one the test chose
    assert [c(cand(a)) for a in ("A000001", "A000002", "A000003")] == [False, False, True]
    assert (c.asked, c.held) == (3, 2)
    assert cool(conn, days=0.5)(cand("A000001"))                 # and the period is the one asked for


def test_an_attempt_that_retired_a_program_does_not_cool(home):
    """If the sequence is still in the pool after that, its next program is what runs: progress."""
    conn, _ = home
    add_attempt(conn, "A000001", when=NOW - timedelta(days=1), mode="wrong_term", outcome="failed", verified=0)
    # one attempt, two programs: the first ended on a bound, the second failed for good
    add_attempt(conn, "A000002", when=NOW - timedelta(days=1), mode="searched_bound", sha="p1", call="x")
    add_attempt(conn, "A000002", when=NOW - timedelta(days=1), mode="wrong_term", outcome="failed", verified=0,
                sha="p2", call="x")
    add_attempt(conn, "A000003", when=NOW - timedelta(days=1), mode="extend_budget", wall=1900.0, cpu=1890.0)
    c = cool(conn)
    assert [c(cand(a)) for a in ("A000001", "A000002", "A000003")] == [True, True, True] and c.held == 0


def test_a_run_at_smaller_budgets_does_not_cool_at_a_higher_tier(home):
    """The finding that reshaped this class. A sequence that timed out at 60 s is what the 600 s tier is
    *for*; judging its base run at the new tier's budgets called it "no progress" and held back 128 of
    131 recently attempted candidates at `verify600`, so the ladder climbed into an empty pool."""
    conn, _ = home
    add_attempt(conn, "A000001", when=NOW - timedelta(days=1), mode="verify_timeout", outcome="failed", verified=0)
    add_attempt(conn, "A000002", when=NOW - timedelta(days=1), mode="searched_bound")            # ran at base
    add_attempt(conn, "A000003", when=NOW - timedelta(days=1), mode="searched_bound", budgets=V600)
    add_attempt(conn, "A000004", when=NOW - timedelta(days=1), mode="searched_bound", budgets=LONG)
    names = ("A000001", "A000002", "A000003", "A000004")

    def kept(budgets):
        c = cool(conn, budgets=budgets)
        return [c(cand(a)) for a in names]

    assert kept(BASE) == [True, False, False, False]     # 1: its timeout retired the program at 60 s
    assert kept(V600) == [True, True, False, False]      # 2 ran at 60 s: says nothing about 600 s
    assert kept(LONG) == [True, True, True, False]       # 3 ran a 30-minute extension, not a 3-hour one


def test_a_row_that_records_no_budget_is_taken_as_having_had_it(home):
    conn, _ = home
    add_attempt(conn, "A000001", when=NOW - timedelta(days=1), mode="searched_bound", budgets=None)   # before item 58
    assert not cool(conn, budgets=LONG)(cand("A000001"))


def test_only_the_most_recent_attempt_decides(home):
    conn, _ = home
    add_attempt(conn, "A000001", when=NOW - timedelta(days=5), mode="wrong_term", outcome="failed", verified=0,
                sha="p1", call="old")
    add_attempt(conn, "A000001", when=NOW - timedelta(days=1), mode="searched_bound", sha="p2", call="new")
    add_attempt(conn, "A000002", when=NOW - timedelta(days=5), mode="searched_bound", sha="p2", call="old")
    add_attempt(conn, "A000002", when=NOW - timedelta(days=1), mode="wrong_term", outcome="failed", verified=0,
                sha="p1", call="new")
    # rows written before `attempt_call` existed each stand alone: the newer one decides
    add_attempt(conn, "A000003", when=NOW - timedelta(days=5), mode="wrong_term", outcome="failed", verified=0,
                sha="p1", call=None)
    add_attempt(conn, "A000003", when=NOW - timedelta(days=1), mode="searched_bound", sha="p2", call=None)
    c = cool(conn)
    assert [c(cand("A000001")), c(cand("A000002")), c(cand("A000003"))] == [False, True, False]


def test_a_changed_entry_is_not_cooled(home, monkeypatch):
    conn, _ = home
    add_attempt(conn, "A000001", when=NOW - timedelta(days=1), known=10)
    assert not cool(conn, known=lambda a: 10)(cand("A000001"))
    assert cool(conn, known=lambda a: 12)(cand("A000001"))          # a sync brought terms: try it now
    assert cool(conn, known=lambda a: 0)(cand("A000001"))           # zero is a count, not "unknown"
    assert not cool(conn, known=lambda a: None)(cand("A000001"))    # cannot tell offline: stays cooled
    # left to itself it asks what selection asks
    monkeypatch.setattr(daemon, "current_known_count", lambda a: 12)
    assert Cooldown(conn, BASE, NOW)(cand("A000001"))


def test_the_known_count_is_the_one_an_attempt_would_see(home, monkeypatch):
    from oeisbot import attempt
    from oeisbot.terms import KnownTerms
    monkeypatch.setattr(attempt, "offline_known_terms",
                        lambda a: (None, KnownTerms(a, 1, {1: 2, 2: 3, 3: 5}, "data")) if a == "A000001" else None)
    assert daemon.current_known_count("A000001") == 3 and daemon.current_known_count("A000002") is None


def test_an_attempt_that_was_cut_short_is_not_cooled(home):
    conn, _ = home
    add_attempt(conn, "A000001", when=NOW - timedelta(days=1), mode="interrupted", call="i")
    # its first program ended on a bound and the stop came during its second, which never finished
    add_attempt(conn, "A000002", when=NOW - timedelta(days=1), mode="searched_bound", sha="p1", call="i")
    add_attempt(conn, "A000002", when=NOW - timedelta(days=1), mode="interrupted", sha="p2", call="i")
    # interrupted last night; the attempt before it is no longer the most recent, and does not decide
    add_attempt(conn, "A000003", when=NOW - timedelta(days=3), mode="searched_bound", call="b")
    add_attempt(conn, "A000003", when=NOW - timedelta(days=1), mode="interrupted", call="i")
    c = cool(conn)
    assert [c(cand(a)) for a in ("A000001", "A000002", "A000003")] == [True, True, True]


def test_a_skip_cools_until_the_mirror_has_synced_again(home):
    """A b-file that could not be fetched, terms that disagreed: the network or the data of that day."""
    conn, _ = home
    add_skip(conn, "A000001", "bfile_error", when=NOW - timedelta(days=1))
    no_count = lambda a: pytest.fail("a skip row has no known-term count to compare")      # noqa: E731
    assert not cool(conn, known=no_count)(cand("A000001"))          # never synced: still cooled
    fresh_sync(conn, NOW - timedelta(days=2))
    assert not cool(conn, known=no_count)(cand("A000001"))          # the sync was before the skip
    fresh_sync(conn, NOW - timedelta(hours=1))
    assert cool(conn, known=no_count)(cand("A000001"))              # synced since: try it again


def test_a_sequence_that_crashed_a_session_is_cooled_whatever_syncs(home):
    conn, _ = home
    add_skip(conn, "A000001", daemon.DAEMON_ERROR, when=NOW - timedelta(days=1))
    fresh_sync(conn, NOW)
    assert not cool(conn)(cand("A000001"))
    add_skip(conn, "A000002", daemon.DAEMON_ERROR, when=NOW - timedelta(days=15))
    assert cool(conn)(cand("A000002"))                              # and no longer than the period


def test_rows_of_any_shape_do_not_break_the_cooldown(home):
    conn, _ = home
    first = add_attempt(conn, "A000001", when=NOW - timedelta(days=2), mode="wrong_term", outcome="failed",
                        verified=0, sha="p1")
    second = add_attempt(conn, "A000001", when=NOW - timedelta(days=1), mode="searched_bound", sha="p2")
    blank = add_attempt(conn, "A000002", when=NOW - timedelta(days=1), mode="searched_bound")
    with conn:
        conn.execute("UPDATE attempts SET extra = 'not json' WHERE id IN (?, ?)", (first, second))
        conn.execute("UPDATE attempts SET failure_mode = NULL WHERE id = ?", (blank,))
    c = cool(conn)
    assert not c(cand("A000001"))                    # two attempts, not one: the newer one retired nothing
    assert not c(cand("A000002"))                    # a row with no stop recorded is still a recent attempt


# ------------------------------------------------------------------ a scripted night

class Night(Daemon):
    """A daemon whose clock, machine, pool and sessions are the test's. `run_session` does what a session
    does to the things the daemon looks at: a session row, the callbacks in the real order, attempt rows
    carrying the budgets they ran under, the clock."""

    def __init__(self, conn, *, window="22:00-08:00", start="2026-11-22 22:00:00", pools=None, pick_min=20.0,
                 picks_per_session=3, rows_per_pick=1, **kw):
        self.lines: list[str] = []
        super().__init__(conn, Window.parse(window), log=self.lines.append, **kw)
        self.clock = at(start)
        self.disk, self.ram = 100 * GiB, 16 * GiB
        self.pools = pools if pools is not None else {"base": [cand(f"A{n:06d}") for n in range(1, 200)]}
        self.pick_min, self.picks_per_session, self.rows_per_pick = pick_min, picks_per_session, rows_per_pick
        self.sessions: list[dict] = []
        self.pools_built: list[str] = []
        self.slept: list[float] = []
        self.synced = 0
        self.sync_error: Exception | None = None
        self.mode = lambda a: "wrong_term"
        self.on_sleep = lambda: None
        self.during_pick = lambda a: None
        self.before_session = lambda tier: None
        self.beats: list[dict] = []

    def tier_of(self, budgets) -> str:
        return next(t.name for t in self.tiers if t.budgets == budgets)

    def now(self):
        return self.clock

    def now_utc(self):
        return self.clock.replace(tzinfo=timezone.utc)

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.clock += timedelta(seconds=seconds)
        self.on_sleep()

    def free_disk(self):
        return self.disk

    def free_ram(self):
        return self.ram

    def _watch(self):
        pass                                        # the loop polls for itself; the real watcher has its own tests

    def beat(self, **changes):
        super().beat(**changes)
        self.beats.append(json.loads(json.dumps(self.state)))

    def sync_mirror(self):
        self.synced += 1
        if self.sync_error is not None:
            raise self.sync_error
        db.set_meta_many(self.conn, {"synced_at": stamp(self.clock), "pulled_at": stamp(self.clock)})

    def pool(self, budgets):
        self.pools_built.append(self.tier_of(budgets))
        return list(self.pools.get(self.tier_of(budgets), []))

    def drain(self, a):
        """What a real pool does when a pick retires its sequence's last program."""
        for tier, members in self.pools.items():
            self.pools[tier] = [c for c in members if c.a_number != a]

    def run_session(self, budgets, **kw):
        tier = self.tier_of(budgets)
        self.before_session(tier)
        sid = db.start_session(self.conn, note=kw["note"])
        drawable = [c for c in self.pools.get(tier, []) if kw["keep"](c)]
        started = []
        for c in drawable[:self.picks_per_session]:
            if kw["should_stop"]() or not kw["may_start"]():        # the order attempt.run_session asks in
                break
            kw["before_attempt"](c.a_number)
            started.append(c.a_number)
            self.during_pick(c.a_number)
            call = f"s{sid}-{c.a_number}"
            if kw["should_stop"]():
                add_attempt(self.conn, c.a_number, when=self.clock, mode="interrupted", outcome="failed", verified=0,
                            session=sid, call=call, budgets=budgets)
                break
            for n in range(self.rows_per_pick):
                add_attempt(self.conn, c.a_number, when=self.clock, mode=self.mode(c.a_number), outcome="failed",
                            verified=0, session=sid, sha=f"sha-{c.a_number}-{n}", call=call, budgets=budgets)
            self.clock += timedelta(minutes=self.pick_min)
        db.finish_session(self.conn, sid)
        self.sessions.append({"id": sid, "tier": tier, "budgets": budgets, "snapshot": kw["snapshot"],
                              "started": started, "note": kw["note"]})
        return sid


def session_rows(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]


def test_outside_the_window_nothing_starts(home):
    conn, _ = home
    orphan = db.start_session(conn, note="left open")
    night = Night(conn, start="2026-11-22 12:00:00")
    last_night = {"state": "stopped", "detail": "the window 22:00-08:00 closed", "warnings": ["A000001: 3 new term(s) ..."]}
    daemon.heartbeat_path().write_text(json.dumps(last_night))
    assert night.run() == "outside the window 22:00-08:00; nothing started"
    assert night.sessions == [] and night.synced == 0 and night.pools_built == []
    # not even recovery: outside its hours the daemon changes nothing
    assert conn.execute("SELECT finished_at FROM sessions WHERE id = ?", (orphan,)).fetchone()[0] is None
    # ... and that includes last night's result and its warnings: a start by day (the machine was off at
    # the opening and the task caught up) said "nothing started" over them
    assert daemon.read_heartbeat() == last_night
    assert night.lines == ["daemon: outside the window 22:00-08:00; nothing started"]


def test_a_night_syncs_once_then_runs_sessions_until_the_window_closes(home):
    conn, _ = home
    night = Night(conn)
    why = night.run()
    assert night.synced == 1
    # ten hours of twenty-minute picks: the last starts with twenty minutes left, and a base pick needs eight
    assert sum(len(s["started"]) for s in night.sessions) == 30
    assert why == "the window 22:00-08:00 closed"
    assert {s["tier"] for s in night.sessions} == {"base"}
    assert all(s["note"] == "daemon=1 tier=base" for s in night.sessions)
    assert all((s["budgets"].verify_wall_s, s["budgets"].extend_wall_s) == (60, 1800) for s in night.sessions)
    # the Pick map's snapshot: the first session of the night, and no other
    assert [s["snapshot"] for s in night.sessions] == [True] + [False] * (len(night.sessions) - 1)
    assert conn.execute("SELECT COUNT(*) FROM sessions WHERE finished_at IS NULL").fetchone()[0] == 0
    assert night.lines[-1] == f"daemon: finished: {why}"
    assert any(line.startswith("daemon: started, window 22:00-08:00 (closes 2026-11-23 08:00), tiers base, verify600, long")
               for line in night.lines)
    assert daemon.read_heartbeat()["state"] == "stopped"


def test_a_pick_is_not_started_without_time_to_verify_it(home):
    conn, _ = home
    # nine minutes before closing: one base pick may start (it needs eight); two minutes later, none
    night = Night(conn, start="2026-11-23 07:51:00", pick_min=2.0, sync=False)
    why = night.run()
    assert [s["started"] for s in night.sessions] == [["A000001"]]
    assert why == "7 min left in the window 22:00-08:00, and a pick at tier base needs 8 to be verified"
    edge = Night(conn, start="2026-11-23 07:52:00", pick_min=2.0, sync=False)          # exactly eight is enough
    edge.run()
    assert [len(s["started"]) for s in edge.sessions] == [1]
    late = Night(conn, start="2026-11-23 07:53:00", sync=False)
    assert late.run().startswith("7 min left") and late.sessions == [] and late.pools_built == []
    # the gate is the tier's own: 35 minutes at verify600
    fresh_sync(conn, at("2026-11-23 07:00:00"))
    upper = Night(conn, start="2026-11-23 07:30:00", sync=False, pools={"base": [], "verify600": [cand("A000001")]})
    assert upper.run() == "30 min left in the window 22:00-08:00, and a pick at tier verify600 needs 35 to be verified"


def test_a_failed_sync_is_a_warning_and_the_night_goes_on(home):
    conn, _ = home
    fresh_sync(conn, NOW - timedelta(days=2))
    night = Night(conn)
    night.sync_error = RuntimeError("git fetch failed")
    night.run()
    assert night.synced == 1 and night.sessions
    (warning,) = daemon.read_heartbeat()["warnings"]
    assert warning.startswith("sync failed (RuntimeError: git fetch failed); going on with the mirror as it is")
    assert "last pulled 2026-11-20" in warning and any(warning in line for line in night.lines)
    assert [b["state"] for b in night.beats][:2] == ["starting", "sync"]
    quiet = Night(conn, sync=False)
    quiet.run()
    assert quiet.synced == 0 and quiet.sessions and daemon.read_heartbeat()["warnings"] == []


def test_a_stop_request_ends_the_run_in_hand_and_the_night(home):
    conn, _ = home
    night = Night(conn)

    def during(a):
        if a == "A000002":
            daemon.request_stop()
            night.poll()                            # what the watcher thread does, once a second

    night.during_pick = during
    why = night.run()
    assert why == "stop requested (`oeisbot daemon --stop`)"
    assert [s["started"] for s in night.sessions] == [["A000001", "A000002"]]
    rows = [tuple(r) for r in conn.execute("SELECT a_number, failure_mode FROM attempts ORDER BY id")]
    assert rows == [("A000001", "wrong_term"), ("A000002", "interrupted")]
    assert not daemon.stop_path().exists()          # honoured, so used up
    beat = daemon.read_heartbeat()
    assert beat["stop_reason"] == why and beat["stopping_for_s"] is not None
    # and the interrupted pick is drawn again the next night, not cooled
    again = Night(conn, sync=False)
    again.run()
    assert "A000002" in again.sessions[0]["started"]


def test_a_stop_given_once_is_not_overwritten_by_a_later_one(home):
    conn, _ = home
    night = Night(conn)
    night.stop("the first reason")
    night.stop("a second")
    assert night.stop_reason == "the first reason" and night.stopping.is_set()
    assert night.run() == "the first reason" and night.synced == 0       # nor does a stopping daemon sync


def test_a_stop_request_left_by_an_earlier_night_is_dropped_and_a_new_one_honoured(home):
    conn, _ = home
    daemon.request_stop()
    old = time.time() - 3600
    os.utime(daemon.stop_path(), (old, old))
    night = Night(conn, sync=False)                 # started now: the request is an hour older than it
    assert night.run() == "the window 22:00-08:00 closed" and night.sessions
    assert not daemon.stop_path().exists()
    # one that arrives after the daemon has taken the lock, before it has even recovered, is for this daemon
    night = Night(conn, sync=False, started=time.time() - 5)
    daemon.request_stop()
    assert night.run() == "stop requested (`oeisbot daemon --stop`)" and night.sessions == []


def test_the_window_closing_during_a_pick_stops_it(home):
    conn, _ = home
    night = Night(conn, start="2026-11-23 07:00:00")

    def overrun(a):
        night.clock = at("2026-11-23 08:00:00")     # an extension still running at the close
        night.poll()

    night.during_pick = overrun
    assert night.run() == "the window 22:00-08:00 closed"
    assert [tuple(r) for r in conn.execute("SELECT a_number, failure_mode FROM attempts")] == [("A000001", "interrupted")]


def test_a_window_without_a_closing_time_runs_until_the_work_is_gone(home):
    conn, _ = home
    fresh_sync(conn)
    night = Night(conn, window="always", start="2026-11-22 12:00:00", sync=False,
                  pools={"base": [cand("A000001"), cand("A000002")]})
    night.during_pick = night.drain
    assert night.run() == "nothing left to draw at any tier"
    assert night.window_end is None and night.remaining_s() == float("inf")
    assert [(s["tier"], s["started"]) for s in night.sessions] == [("base", ["A000001", "A000002"])]
    assert daemon.read_heartbeat()["window_ends"] is None
    assert any("no closing time" in line for line in night.lines)


def test_an_exhausted_tier_costs_a_look_and_no_session_row(home):
    """The first version learnt that a tier was empty by running a session there: three empty rows a
    night, about a thousand a year, and the dashboard's session table would have been mostly those."""
    conn, _ = home
    fresh_sync(conn)
    pools = {"base": [], "verify600": [cand("A000001")], "long": [cand("A000009")]}
    night = Night(conn, sync=False, pools=pools)
    night.during_pick = night.drain
    assert night.run() == "nothing left to draw at any tier"
    assert [(s["tier"], s["started"]) for s in night.sessions] == [("verify600", ["A000001"]), ("long", ["A000009"])]
    assert session_rows(conn) == 2
    assert night.pools_built == ["base", "verify600", "verify600", "long", "long"]
    assert [(s["budgets"].verify_wall_s, s["budgets"].extend_wall_s) for s in night.sessions] == [(600, 1800), (600, 10800)]
    assert [s["snapshot"] for s in night.sessions] == [False, False]     # the Pick map: the lowest tier only
    assert any("tier base: pool 0, 0 cooling down, nothing to draw" in l for l in night.lines)
    assert any(l == "daemon: moving to tier verify600" for l in night.lines)


def test_no_climbing_on_a_stale_mirror(home):
    conn, _ = home
    fresh_sync(conn, NOW - timedelta(days=daemon.STALE_SYNC_DAYS, seconds=1))
    night = Night(conn, sync=False, pools={"base": [], "verify600": [cand("A000001")]})
    assert night.run() == ("nothing left to draw at tier base, and the mirror has not synced for over 7 days: "
                           "not climbing to longer budgets on stale data")
    assert night.sessions == [] and night.pools_built == ["base"]
    fresh_sync(conn, NOW - timedelta(days=daemon.STALE_SYNC_DAYS))       # exactly seven days is not over seven
    ok = Night(conn, sync=False, pools={"base": [], "verify600": []})
    assert ok.run() == "nothing left to draw at any tier"
    with conn:                                                           # never synced at all is stale
        conn.execute("DELETE FROM meta WHERE key = 'synced_at'")
    assert "stale data" in Night(conn, sync=False, pools={"base": []}).run()
    assert Night(conn, sync=True, pools={"base": []}).run() == "nothing left to draw at any tier"   # tonight's sync counts


def test_rebuilding_the_table_from_an_old_mirror_does_not_make_the_mirror_new(home):
    """`oeisbot sync --no-pull` moves `synced_at` too. The daemon asks when the mirror was last *pulled*:
    after two weeks of failed pulls, a `--no-pull` by hand must not send it up to 3-hour budgets, nor
    release yesterday's skips as if the data had changed."""
    conn, _ = home
    db.set_meta_many(conn, {"pulled_at": stamp(NOW - timedelta(days=20)), "synced_at": stamp(NOW)})
    night = Night(conn, sync=False, pools={"base": [], "verify600": [cand("A000001")]})
    assert "stale data" in night.run() and night.sessions == []
    add_skip(conn, "A000002", "bfile_error", when=NOW - timedelta(days=1))
    assert not cool(conn)(cand("A000002"))           # no pull since the skip, whatever `synced_at` says
    db.set_meta(conn, "pulled_at", stamp(NOW - timedelta(hours=1)))
    assert cool(conn)(cand("A000002"))
    assert daemon.pulled_at(conn) == stamp(NOW - timedelta(hours=1))
    with conn:                                       # a database from before the key existed: the sync time is all there is
        conn.execute("DELETE FROM meta WHERE key = 'pulled_at'")
    assert daemon.pulled_at(conn) == stamp(NOW)


def test_the_night_says_how_many_reviews_are_waiting(home):
    conn, _ = home
    fresh_sync(conn)
    for n, status in enumerate(("new", "reviewing", "submitted", "rejected")):
        win = add_attempt(conn, f"A00000{n}", when=NOW - timedelta(days=30), mode="max_new_terms", outcome="extended")
        db.set_review_status(conn, db.add_review(conn, f"A00000{n}", win, "artifacts/x", 2, 3), status)
    night = Night(conn, sync=False, pools={"base": []}, tiers=daemon.TIERS[:1])
    night.run()
    assert "daemon: 2 review(s) waiting for a person (`oeisbot review list`)" in night.lines
    assert daemon.read_heartbeat()["reviews_waiting"] == 2
    with conn:
        conn.execute("DELETE FROM reviews")
    quiet = Night(conn, sync=False, pools={"base": []}, tiers=daemon.TIERS[:1])
    quiet.run()
    assert not any("waiting for a person" in l for l in quiet.lines) and daemon.read_heartbeat()["reviews_waiting"] == 0


def test_what_retired_nothing_last_night_is_not_drawn_tonight(home):
    """The cooldown, through the loop, with the budgets the sessions really ran at."""
    conn, _ = home
    fresh_sync(conn)
    pool = [cand("A000001"), cand("A000002"), cand("A000003")]
    night = Night(conn, sync=False, pools={"base": list(pool)}, tiers=daemon.TIERS[:1])
    night.mode = lambda a: "searched_bound" if a != "A000002" else "wrong_term"
    night.during_pick = lambda a: night.drain(a) if a == "A000002" else None     # its one program is retired
    assert night.run() == "nothing left to draw at any tier"
    assert [s["started"] for s in night.sessions] == [["A000001", "A000002", "A000003"]]
    assert any("tier base: pool 2, 2 cooling down, nothing to draw" in line for line in night.lines)
    # a higher tier is not held back by what ran at base
    fresh_sync(conn, at("2026-11-23 21:00:00"))
    later = Night(conn, sync=False, start="2026-11-23 22:00:00", pools={"base": [], "verify600": list(pool)})
    later.during_pick = later.drain
    later.run()
    assert later.sessions[0]["tier"] == "verify600" and len(later.sessions[0]["started"]) == 3


def test_the_pool_and_the_cooldown_are_built_for_the_tier_being_run(home):
    conn, _ = home
    fresh_sync(conn)
    seen: list = []
    real = daemon.Cooldown

    class Spy(real):
        def __init__(self, conn_, budgets, now_utc, **kw):
            seen.append((budgets.verify_wall_s, budgets.extend_wall_s))
            super().__init__(conn_, budgets, now_utc, **kw)

    import oeisbot.daemon as module
    module.Cooldown = Spy
    try:
        night = Night(conn, sync=False, pools={"base": [], "verify600": [], "long": []})
        night.run()
    finally:
        module.Cooldown = real
    assert seen == [(60, 1800), (600, 1800), (600, 10800)]
    assert night.pools_built == ["base", "verify600", "long"]


def test_a_full_disk_pauses_the_night_instead_of_failing_every_pick(home):
    conn, _ = home
    night = Night(conn, sync=False)
    night.disk = config.DEFAULT_BUDGETS.reserve_disk_bytes + daemon.DISK_MARGIN_BYTES - 1

    def freed():
        if len(night.slept) == 3:
            night.disk = 100 * GiB

    night.on_sleep = freed
    night.run()
    assert night.slept[:3] == [daemon.PAUSE_S] * 3 and night.sessions
    assert sum("daemon: paused (10.0 GiB free on the data drive; a run needs 10 GiB)" in l for l in night.lines) == 1
    assert len([b for b in night.beats if b["state"] == "paused_disk"]) == 3
    assert conn.execute("SELECT COUNT(*) FROM attempts WHERE failure_mode = 'disk_cap'").fetchone()[0] == 0
    ok = Night(conn, sync=False)                    # exactly at the threshold is enough
    ok.disk = config.DEFAULT_BUDGETS.reserve_disk_bytes + daemon.DISK_MARGIN_BYTES
    ok.run()
    assert ok.slept == []


def test_low_ram_pauses_too_and_a_machine_that_never_recovers_waits_out_the_window(home):
    conn, _ = home
    assert daemon.RAM_MARGIN_BYTES == GiB and daemon.DISK_MARGIN_BYTES == 2 * GiB
    night = Night(conn, sync=False, start="2026-11-23 07:00:00")
    night.ram = config.DEFAULT_BUDGETS.reserve_phys_bytes + daemon.RAM_MARGIN_BYTES - 1
    assert night.run() == "the window 22:00-08:00 closed"                # the wait looks at the clock by itself
    assert night.sessions == [] and len(night.slept) == 6
    assert {b["state"] for b in night.beats} >= {"paused_ram", "stopped"}
    assert any("4.0 GiB of RAM free; a run needs 4 GiB" in line for line in night.lines)
    ok = Night(conn, sync=False, start="2026-11-23 07:00:00")
    ok.ram = config.DEFAULT_BUDGETS.reserve_phys_bytes + daemon.RAM_MARGIN_BYTES         # exactly enough
    ok.run()
    assert ok.slept == [] and ok.sessions


def test_a_machine_that_goes_short_mid_session_is_given_one_pause_even_if_it_looks_fine_again(home):
    """Memory hovering at the threshold: fine when the loop looks, short when the first pick is about to
    start. Without a pause that is a session row, a pool build and nothing run, as fast as it can loop
    (4,818 empty sessions in one simulated night)."""
    conn, _ = home
    night = Night(conn, sync=False, start="2026-11-23 06:00:00")
    night.before_session = lambda tier: setattr(night, "ram", 1 * GiB)   # short by the time a pick would start
    night.on_sleep = lambda: setattr(night, "ram", 16 * GiB)             # ... and fine again after the pause

    def top_of_loop_sees_it_fine():
        night.ram = 16 * GiB

    real_wait = night.wait_for_the_machine
    night.wait_for_the_machine = lambda at_least_once=False: (top_of_loop_sees_it_fine(), real_wait(at_least_once))[1]
    assert night.run() == "the window 22:00-08:00 closed"
    assert all(s["started"] == [] for s in night.sessions)
    assert night.slept and set(night.slept) == {daemon.PAUSE_S}
    assert len(night.sessions) == len(night.slept) <= 12                 # one per pause, not thousands
    assert any(b["state"] == "paused_machine" for b in night.beats)


def test_five_picks_in_a_row_lost_to_the_machine_end_the_night(home):
    """`launch_error`, `disk_cap`, `harness_error` and `bfile_error` are not the program's doing. Each is
    a row that doubles a failure penalty and retires nothing, so a loop that kept going would spend the
    pool on a fault and mark every sequence it touched."""
    conn, _ = home
    assert (daemon.BREAKER_RUN, daemon.MACHINE_FAILURES) == (5, ("launch_error", "disk_cap", "harness_error", "bfile_error"))
    night = Night(conn, sync=False, picks_per_session=25, pick_min=0.1, rows_per_pick=3)
    night.mode = lambda a: "launch_error"
    why = night.run()
    assert why.startswith("5 picks in a row ended as launch_error / disk_cap / harness_error / bfile_error")
    # picks, not rows: each pick wrote three rows, and it still took five of them
    assert [len(s["started"]) for s in night.sessions] == [5]
    assert conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 15


def test_a_streak_of_machine_failures_is_counted_across_sessions_and_only_since_this_start(home):
    conn, _ = home
    for n in range(5):                              # five from an earlier night: not this daemon's streak
        add_attempt(conn, f"A9{n:05d}", when=NOW - timedelta(days=20), mode="launch_error", outcome="failed",
                    verified=0, call=f"old{n}")
    night = Night(conn, sync=False, picks_per_session=2, pick_min=0.1)
    night.mode = lambda a: "bfile_error"
    assert night.run().startswith("5 picks in a row")
    assert [len(s["started"]) for s in night.sessions] == [2, 2, 1]       # two sessions and a pick, not one session


def test_an_ordinary_failure_breaks_the_streak(home):
    conn, _ = home
    fresh_sync(conn)
    night = Night(conn, sync=False, picks_per_session=25, pick_min=0.1, tiers=daemon.TIERS[:1],
                  pools={"base": [cand(f"A{n:06d}") for n in range(1, 11)]})
    night.mode = lambda a: "wrong_term" if a.endswith("5") or a.endswith("0") else "harness_error"
    night.during_pick = night.drain
    assert night.run() == "nothing left to draw at any tier"
    assert len(night.sessions[0]["started"]) == 10 and night.machine_failures_in_a_row() == 0


def test_a_session_that_raises_costs_one_sequence_not_the_night(home):
    """An entry that crashes the plan, a locked database: a run is recorded only after it ends, so the
    pick in hand had no row, was drawn again in the next session, and ended every night at the same
    place -- with the traceback on a console no scheduled task has."""
    conn, _ = home
    fresh_sync(conn)
    pool = [cand("A000001"), cand("A000002"), cand("A000003")]
    night = Night(conn, sync=False, pools={"base": list(pool)}, tiers=daemon.TIERS[:1])
    real = night.during_pick

    def crash_on_two(a):
        if a == "A000002":
            raise ZeroDivisionError("the plan could not read this entry")
        night.drain(a)

    night.during_pick = crash_on_two
    assert night.run() == "nothing left to draw at any tier"
    rows = [tuple(r) for r in conn.execute("SELECT a_number, outcome, failure_mode, strategy FROM attempts ORDER BY id")]
    assert ("A000002", "skipped", "daemon_error", "daemon") in rows
    assert {r[0] for r in rows if r[2] == "wrong_term"} == {"A000001", "A000003"}      # the others still ran
    assert any("raised ZeroDivisionError: the plan could not read this entry (while on A000002)" in l
               and "Traceback (most recent call last)" in l for l in night.lines)
    (warning,) = daemon.read_heartbeat()["warnings"]
    assert warning.startswith("A000002 raised ZeroDivisionError outside the sandbox and is held back for 14 days")
    assert real is not None


def test_a_fault_between_picks_is_charged_to_no_sequence(home):
    """Found by the re-check, and it failed then. The sequence to charge was read back from the
    heartbeat, which still named the pick that had just *finished*: a fault while the session asked
    about the next pick wrote a `daemon_error` row for a sequence that had done nothing wrong -- and that
    row, being its newest, hid the program it had just retired and held it back for 14 days."""
    conn, _ = home
    fresh_sync(conn)
    night = Night(conn, sync=False, start="2026-11-23 06:00:00", pools={"base": [cand("A000001"), cand("A000002")]})
    asked = {"n": 0}

    def disk():
        asked["n"] += 1
        if asked["n"] == 3:                          # the loop's own look, pick 1's, then before pick 2
            raise OSError("disk_usage failed for a moment")
        return 100 * GiB

    night.free_disk = disk
    night.during_pick = night.drain
    night.run()
    rows = [tuple(r) for r in conn.execute("SELECT a_number, failure_mode FROM attempts ORDER BY id")]
    assert ("A000001", "wrong_term") in rows and not any(mode == daemon.DAEMON_ERROR for _, mode in rows), rows
    assert any("raised OSError: disk_usage failed for a moment\n" in l for l in night.lines)     # no "(while on ...)"
    assert daemon.read_heartbeat()["warnings"] == []
    assert ("A000002", "wrong_term") in rows         # and the night went on to the pick that was waiting


def test_a_win_cut_short_by_the_window_is_said_where_the_user_will_see_it(home):
    """The one cost of letting the window interrupt an extension: a run that had already found terms
    opens its review with those only, and the sequence is out of the draw until the user decides."""
    conn, _ = home
    fresh_sync(conn)
    night = Night(conn, sync=False, start="2026-11-23 07:00:00", pools={"base": [cand("A000001")]}, tiers=daemon.TIERS[:1])
    real = night.run_session

    def session(budgets, **kw):
        sid = real(budgets, **kw)
        with conn:                                   # what the real session records for such a run
            conn.execute("UPDATE attempts SET outcome = 'extended', failure_mode = 'interrupted', new_terms = 3 "
                         "WHERE session_id = ?", (sid,))
        return sid

    night.run_session = session
    night.during_pick = night.drain
    night.run()
    assert daemon.read_heartbeat()["warnings"] == [
        "A000001: 3 new term(s) found before the run was stopped; it did not use its whole extension, so a "
        "longer run might find more"]


def test_a_mirror_left_unusable_by_the_sync_means_no_sessions(home):
    from oeisbot.ingest.oeisdata import MirrorUnusable
    conn, _ = home
    night = Night(conn)
    night.sync_error = MirrorUnusable("the reset failed (GitTimeout) and so did putting the mirror back (OSError)")
    assert night.run() == "the mirror could not be used after a failed sync"
    assert night.sessions == [] and night.pools_built == []
    (warning,) = daemon.read_heartbeat()["warnings"]
    assert warning.startswith("sync failed and left the mirror unusable") and "Run `oeisbot sync` by hand" in warning


def test_two_sessions_raising_in_a_row_end_the_night(home):
    conn, _ = home
    fresh_sync(conn)
    night = Night(conn, sync=False)
    night.before_session = lambda tier: (_ for _ in ()).throw(db.sqlite3.OperationalError("database is locked"))
    why = night.run()
    assert why == ("2 sessions in a row raised (OperationalError: database is locked); stopped rather than go on. "
                   "The traceback is in the daemon's log")
    assert session_rows(conn) == 0 and conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 0
    assert daemon.read_heartbeat()["state"] == "stopped"
    # a fault while looking at the pool counts the same way, and names no sequence
    night = Night(conn, sync=False)
    night.pool = lambda budgets: (_ for _ in ()).throw(RuntimeError("mirror unreadable"))
    assert night.run().startswith("2 sessions in a row raised (RuntimeError: mirror unreadable)")
    # a fault followed by a session that works is forgotten: two faults with a good session between them
    # are not "two in a row"
    night = Night(conn, sync=False, start="2026-11-23 06:00:00")
    asked = {"n": 0}

    def first_and_third(tier):
        asked["n"] += 1
        if asked["n"] in (1, 3):
            raise RuntimeError(f"fault at session {asked['n']}")

    night.before_session = first_and_third
    assert night.run() == "the window 22:00-08:00 closed"
    assert asked["n"] > 3 and len(night.sessions) == asked["n"] - 2
    assert sum("raised RuntimeError: fault at session" in l for l in night.lines) == 2


def test_a_session_that_starts_nothing_for_no_reason_ends_the_night_rather_than_spin(home):
    conn, _ = home
    night = Night(conn, sync=False, picks_per_session=0)
    assert "had 199 candidate(s) to draw and started none; stopping rather than loop" in night.run()
    assert len(night.sessions) == 1


def test_a_pick_is_not_started_once_a_stop_has_been_seen(home):
    """`may_start` looks at the clock; if that look is what notices the window has closed, the answer is
    no -- not "yes" followed by a run that is interrupted on its first tick."""
    conn, _ = home
    night = Night(conn, sync=False, start="2026-11-23 07:00:00")
    night.during_pick = lambda a: setattr(night, "clock", at("2026-11-23 08:00:05")) if a == "A000001" else None
    assert night.run() == "the window 22:00-08:00 closed"
    assert [s["started"] for s in night.sessions] == [["A000001"]]
    assert conn.execute("SELECT COUNT(*) FROM attempts WHERE failure_mode = 'interrupted'").fetchone()[0] == 0


def test_a_stop_request_seen_before_a_pick_keeps_that_pick_from_starting(home):
    """The same for `--stop`, where the window gives no second reason to say no: the request arrives
    during one pick, nothing polls until the session asks whether it may start the next, and that
    question is what finds it. The next pick is not started -- neither run to the end unnoticed, nor
    started only to be interrupted."""
    conn, _ = home
    night = Night(conn, sync=False)
    night.during_pick = lambda a: daemon.request_stop() if a == "A000001" else None      # and nobody polls
    assert night.run() == "stop requested (`oeisbot daemon --stop`)"
    assert [s["started"] for s in night.sessions] == [["A000001"]]
    assert [tuple(r) for r in conn.execute("SELECT a_number, failure_mode FROM attempts")] == [("A000001", "wrong_term")]


# ------------------------------------------------------------------ recovery

def test_recovery_closes_orphan_sessions_at_the_time_of_their_last_row(home):
    conn, _ = home
    orphan = db.start_session(conn, note="count=25 daemon=1 tier=base")
    add_attempt(conn, "A000001", when=NOW - timedelta(days=3), session=orphan, wall=12.0)
    bare = db.start_session(conn)                    # killed before its first row, and with no note at all
    with conn:
        conn.execute("UPDATE sessions SET note = NULL, started_at = ? WHERE id = ?", (stamp(NOW - timedelta(days=2)), bare))
    done = db.start_session(conn, note="finished")
    db.finish_session(conn, done)
    night = Night(conn, sync=False, pools={"base": []}, tiers=daemon.TIERS[:1])
    fresh_sync(conn)
    night.run()
    row = conn.execute("SELECT finished_at, attempts, machine_s, note FROM sessions WHERE id = ?", (orphan,)).fetchone()
    assert row["finished_at"] == stamp(NOW - timedelta(days=3))          # when it really ended, not tonight
    assert (row["attempts"], row["machine_s"]) == (1, 12.0)
    assert row["note"] == "count=25 daemon=1 tier=base (closed by recovery: its process ended mid-session)"
    row = conn.execute("SELECT finished_at, note FROM sessions WHERE id = ?", (bare,)).fetchone()
    assert row["finished_at"] == stamp(NOW - timedelta(days=2))
    assert row["note"] == " (closed by recovery: its process ended mid-session)"
    assert conn.execute("SELECT note FROM sessions WHERE id = ?", (done,)).fetchone()["note"] == "finished"
    assert sum("left open by a process that ended mid-session" in l for l in night.lines) == 2


def test_recovery_sweeps_only_old_run_directories(home):
    conn, tmp = home
    scratch = config.SCRATCH
    scratch.mkdir(parents=True)
    old = time.time() - daemon.SCRATCH_ORPHAN_AGE_S - 600
    young = time.time() - daemon.SCRATCH_ORPHAN_AGE_S + 600
    assert daemon.SCRATCH_ORPHAN_AGE_S == 6 * 3600
    names = {"A123456-gp-0a1b2c3d": old,            # a killed run's directory: goes
             "A123456-python-ffffffff": old,        # likewise
             "A654321-gp-00000000": young,          # just under six hours: could still be a live run
             "A654321-gp-11111111": time.time(),    # the test suite uses this directory too
             "smoke-0ccdc28f": old,                 # not a run's name: someone else's, left alone
             "A123456-gp-0a1b2c3": old,             # seven hex digits: not the harness's pattern
             "A12345-gp-0a1b2c3d": old,             # five digits
             "A123456-gp2-0a1b2c3d": old,           # a digit in the language
             "A123456-gp-0a1b2c3d-kept": old,       # a longer name that only starts like one
             "xA123456-gp-0a1b2c3d": old}
    for name, mtime in names.items():
        (scratch / name).mkdir()
        (scratch / name / "program.gp").write_text("a(n)=n")
        os.utime(scratch / name, (mtime, mtime))
    (scratch / "A111111-gp-aaaaaaaa").write_text("a file, not a directory")
    os.utime(scratch / "A111111-gp-aaaaaaaa", (old, old))
    night = Night(conn, sync=False, pools={"base": []}, tiers=daemon.TIERS[:1])
    fresh_sync(conn)
    night.run()
    assert sorted(p.name for p in scratch.iterdir()) == sorted(set(names) - {"A123456-gp-0a1b2c3d", "A123456-python-ffffffff"}
                                                               | {"A111111-gp-aaaaaaaa"})
    assert any("removed 2 leftover run directories" in line for line in night.lines)
    again = Night(conn, sync=False, pools={"base": []}, tiers=daemon.TIERS[:1])
    again.run()
    assert not any("leftover" in line for line in again.lines)


def test_recovery_survives_a_scratch_directory_it_cannot_read(home, monkeypatch):
    conn, _ = home
    config.SCRATCH.mkdir(parents=True)
    (config.SCRATCH / "A123456-gp-0a1b2c3d").mkdir()
    real_stat = type(config.SCRATCH).stat
    monkeypatch.setattr(type(config.SCRATCH), "stat",
                        lambda self, **kw: (_ for _ in ()).throw(PermissionError("locked")) if self.name.startswith("A1")
                        else real_stat(self, **kw))
    fresh_sync(conn)
    night = Night(conn, sync=False, pools={"base": []}, tiers=daemon.TIERS[:1])
    assert night.run() == "nothing left to draw at any tier"


def test_recovery_warns_of_a_pending_win_whose_saved_result_is_gone(home):
    conn, _ = home
    from oeisbot import attempt
    lost = add_attempt(conn, "A000001", when=NOW, mode="max_new_terms", outcome="recheck_pending")
    kept = add_attempt(conn, "A000002", when=NOW, mode="max_new_terms", outcome="recheck_pending")
    attempt.pending_path(kept).parent.mkdir(parents=True)
    attempt.pending_path(kept).write_text("{}")
    night = Night(conn, sync=False, pools={"base": []}, tiers=daemon.TIERS[:1])
    fresh_sync(conn)
    night.run()
    (warning,) = daemon.read_heartbeat()["warnings"]                     # where the dashboard will show it
    assert f"attempt #{lost} (A000001) waits for a re-check but its saved result is missing" in warning
    assert f"oeisbot recheck --release {lost}" in warning
    assert conn.execute("SELECT outcome FROM attempts WHERE id = ?", (lost,)).fetchone()[0] == "recheck_pending"


# ------------------------------------------------------------------ heartbeat, status, the watcher

def test_the_heartbeat_says_what_the_daemon_is_doing(home):
    conn, _ = home
    fresh_sync(conn)
    night = Night(conn, sync=False, start="2026-11-23 07:00:00", pools={"base": [cand("A000001")]})
    seen: list[dict] = []
    night.during_pick = lambda a: (seen.append(daemon.read_heartbeat()), night.drain(a))
    night.run()
    (beat,) = seen
    assert (beat["state"], beat["a_number"], beat["tier"], beat["detail"]) == ("running", "A000001", "base", None)
    assert beat["pid"] == os.getpid() and beat["window"] == "22:00-08:00"
    assert beat["window_ends"] == "2026-11-23T08:00" and beat["synced_at"].startswith("2026-11-22T22:00")
    assert beat["at"] == beat["progress_at"] == "2026-11-23T07:00:00+00:00"
    assert beat["stop_reason"] is None and beat["stopping_for_s"] is None and beat["warnings"] == []
    assert night.beats[0]["state"] == "starting" and night.beats[0]["reviews_waiting"] == 0
    assert {"state": "running", "detail": "building the pool"}.items() <= night.beats[1].items()
    final = daemon.read_heartbeat()
    assert final["state"] == "stopped" and final["a_number"] is None and final["detail"] == "nothing left to draw at any tier"


def test_only_the_main_loop_moves_the_progress_stamp(home, monkeypatch):
    """`at` is the watcher's proof that the process is alive; `progress_at` is the loop's proof that it
    is getting somewhere. A daemon hung in one call keeps the first moving and not the second."""
    conn, _ = home
    night = Night(conn, sync=False)
    night.beat(state="running")
    first = daemon.read_heartbeat()
    night.clock += timedelta(minutes=45)
    monkeypatch.setattr(daemon, "HEARTBEAT_S", 0.0)
    night.poll()                                    # the watcher's beat
    later = daemon.read_heartbeat()
    assert later["progress_at"] == first["progress_at"] and later["at"] != first["at"]
    monkeypatch.setattr(daemon, "HEARTBEAT_S", 3600.0)
    night.clock += timedelta(minutes=1)
    night.poll()                                    # not due: nothing written
    assert daemon.read_heartbeat()["at"] == later["at"]


def test_a_heartbeat_that_cannot_be_written_costs_nothing_and_is_said_once_per_streak(home, monkeypatch):
    conn, tmp = home
    night = Night(conn, sync=False)
    real_replace = type(tmp).replace
    failing = {"on": True, "calls": 0}

    def replace(self, target):
        failing["calls"] += 1
        if failing["on"]:
            raise PermissionError("another process has the file open")
        return real_replace(self, target)

    monkeypatch.setattr(type(tmp), "replace", replace)
    monkeypatch.setattr(daemon.time, "sleep", lambda s: None)
    night.beat(state="running")
    night.beat(state="running")
    assert failing["calls"] == 10                    # five tries each, not one
    assert sum("could not write" in l and "going on without it" in l for l in night.lines) == 1
    failing["on"] = False
    night.beat(state="running", detail="back")
    assert daemon.read_heartbeat()["detail"] == "back"
    failing["on"] = True
    night.beat(state="running")
    assert sum("could not write" in l for l in night.lines) == 2          # a new streak is said again


def test_the_heartbeat_file_is_written_by_one_thread_at_a_time(home, monkeypatch):
    """The deterministic half of the next test: the watcher and the main loop share one temporary file,
    so the write and the replace happen under a lock. Each write here is slowed down and counted."""
    conn, tmp = home
    night = Night(conn, sync=False)
    inside = {"now": 0, "most": 0}
    guard = threading.Lock()
    real_write = type(tmp).write_text

    def slow_write(self, *args, **kwargs):
        if self.suffix != ".part":
            return real_write(self, *args, **kwargs)
        with guard:
            inside["now"] += 1
            inside["most"] = max(inside["most"], inside["now"])
        time.sleep(0.002)
        try:
            return real_write(self, *args, **kwargs)
        finally:
            with guard:
                inside["now"] -= 1

    monkeypatch.setattr(type(tmp), "write_text", slow_write)
    threads = [threading.Thread(target=lambda: [Daemon.beat(night, state="running") for _ in range(40)])
               for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert inside["most"] == 1


def test_two_threads_beating_never_leave_a_broken_heartbeat(home):
    """The watcher and the main loop share one temporary file. Unserialised, a short body written over a
    longer one was installed as the heartbeat: 4,060 unreadable reads in a stress run."""
    conn, _ = home
    night = Night(conn, sync=False)
    night.beat(state="running")
    stop = threading.Event()
    broken: list[str] = []

    def reader():
        while not stop.is_set():
            try:
                text = daemon.heartbeat_path().read_text(encoding="utf-8")
            except OSError:
                continue                             # between the two halves of a replace: not a broken file
            try:
                json.loads(text)
            except ValueError:
                broken.append(text)

    def writer(detail):
        for _ in range(150):
            Daemon.beat(night, state="running", detail=detail)

    threads = [threading.Thread(target=reader), threading.Thread(target=writer, args=("x",)),
               threading.Thread(target=writer, args=("y" * 4000,))]
    for t in threads:
        t.start()
    for t in threads[1:]:
        t.join()
    stop.set()
    threads[0].join()
    assert broken == []


def test_status_asks_the_lock_not_the_heartbeat(home):
    conn, tmp = home
    assert daemon.status() == {"running": False, "other_command": None, "heartbeat": None, "armed": True}
    daemon.heartbeat_path().write_text(json.dumps({"state": "running", "a_number": "A000001"}))
    assert daemon.status()["running"] is False       # a killed daemon leaves a fresh-looking file
    with lock.writer("daemon"):
        assert daemon.status()["running"] is True and daemon.status()["other_command"] is None
    # a description left by a daemon that was killed says "daemon", and the lock says nobody is there
    lock.lock_path().write_text(json.dumps({"pid": 1, "command": "daemon", "started_at": "then"}))
    assert daemon.status()["running"] is False
    with lock.writer("run"):
        report = daemon.status()
        assert (report["running"], report["other_command"]) == (False, "run")
    daemon.heartbeat_path().write_text("[1, 2]")
    assert daemon.read_heartbeat() is None
    daemon.heartbeat_path().write_text("not json")
    assert daemon.read_heartbeat() is None


def test_a_daemon_whose_lock_description_is_unreadable_can_still_be_stopped(home, capsys):
    """The description is a courtesy and can fail to be written. `--stop` must not answer "no daemon is
    running" to a daemon that is: a held lock beside a heartbeat that has not stopped is the daemon."""
    conn, tmp = home
    daemon.heartbeat_path().write_text(json.dumps({"state": "running"}))
    with lock.writer("daemon"):
        lock.lock_path().write_text("")
        assert daemon.status()["running"] is True
        daemon.command(Args(stop=True))
        assert "stop requested" in capsys.readouterr().out and daemon.stop_path().exists()
        daemon.heartbeat_path().write_text(json.dumps({"state": "stopped"}))
        assert daemon.status()["running"] is False


def test_describe_reads_as_a_sentence_in_each_state():
    beat = {"state": "running", "a_number": "A000045", "tier": "base", "pid": 7, "window": "22:00-08:00",
            "window_ends": "2026-11-23T08:00", "synced_at": "2026-11-22T22:01:00+00:00", "at": "2026-11-23T01:00:30+00:00",
            "progress_at": "2026-11-23T01:00:00+00:00", "detail": None, "warnings": [], "stopping_for_s": None}
    text = daemon.describe({"running": True, "other_command": None, "heartbeat": beat})
    assert text == ("daemon is running (pid 7): running A000045 at tier base\n"
                    "window 22:00-08:00, closes 2026-11-23T08:00 local time; mirror last synced 2026-11-22T22:01:00+00:00\n"
                    "last step 2026-11-23T01:00:00+00:00 UTC; heartbeat 2026-11-23T01:00:30+00:00 UTC")
    between = daemon.describe({"running": True, "other_command": None, "heartbeat": {**beat, "a_number": None}})
    assert "running (between picks) at tier base" in between
    paused = daemon.describe({"running": True, "other_command": None,
                              "heartbeat": {**beat, "state": "paused_disk", "detail": "7.0 GiB free",
                                            "warnings": ["sync failed"]}})
    assert "paused_disk (7.0 GiB free)" in paused and paused.endswith("\nwarning: sync failed")
    syncing = daemon.describe({"running": True, "other_command": None,
                               "heartbeat": {**beat, "state": "sync", "stopping_for_s": 90, "stop_reason": "the window closed"}})
    assert "syncing the mirror\nstop asked for 90 s ago (the window closed); still finishing" in syncing
    assert daemon.describe({"running": False, "other_command": None, "heartbeat": None, "armed": True}) == \
        "daemon is not running\nno daemon has run here yet"
    # not armed is said, and an answer that does not say is read as not armed, never as armed
    for report in ({"running": False, "other_command": None, "heartbeat": None, "armed": False},
                   {"running": False, "other_command": None, "heartbeat": None}):
        assert daemon.describe(report) == (
            "daemon is not running\nnot armed: a start will do nothing until you run `oeisbot daemon --arm` "
            "(that is how a night is allowed to run here)\nno daemon has run here yet")
    stopped = daemon.describe({"running": False, "armed": True, "other_command": "sync",
                               "heartbeat": {"state": "stopped", "at": "T", "detail": "the window closed"}})
    assert stopped == ("daemon is not running; `oeisbot sync` holds the writers' lock\n"
                       "last daemon: stopped at T UTC (the window closed)")
    killed = daemon.describe({"running": False, "armed": True, "other_command": None,
                              "heartbeat": {"state": "running", "at": "T"}})
    assert "did not finish; it was running at T UTC when its process ended" in killed


class Busy(Night):
    """A night whose session is a run in hand: it only ever reads the stop flag, as a real run does."""
    _watch = Daemon._watch
    obeys = True

    def run_session(self, budgets, **kw):
        sid = db.start_session(self.conn, note=kw["note"])
        self.in_session()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not (self.obeys and kw["should_stop"]()) and not self.finished.is_set():
            time.sleep(0.01)
        db.finish_session(self.conn, sid)
        return sid

    def in_session(self):
        daemon.request_stop()


def test_the_watcher_thread_sees_a_stop_request_by_itself(home, monkeypatch):
    """No pick ever calls `poll`, so only the watcher can notice a request while a session is busy."""
    conn, _ = home
    fresh_sync(conn)
    monkeypatch.setattr(daemon, "POLL_S", 0.01)
    night = Busy(conn, sync=False)
    began = time.monotonic()
    assert night.run() == "stop requested (`oeisbot daemon --stop`)"
    assert time.monotonic() - began < 10 and night.finished.is_set()


def test_the_watcher_keeps_the_heartbeat_moving_through_a_long_run(home, monkeypatch):
    conn, _ = home
    fresh_sync(conn)
    monkeypatch.setattr(daemon, "POLL_S", 0.01)
    monkeypatch.setattr(daemon, "HEARTBEAT_S", 0.0)
    stamps: set = set()

    class Long(Busy):
        def in_session(self):
            for _ in range(30):                      # the main thread is "in a run": it writes nothing
                self.clock += timedelta(seconds=1)
                time.sleep(0.02)
                stamps.add((daemon.read_heartbeat() or {}).get("at"))
            daemon.request_stop()

    Long(conn, sync=False).run()
    assert len(stamps - {None}) > 3


def test_a_stop_that_is_not_obeyed_ends_the_process(home, monkeypatch):
    """The last resort. A call that never returns (a stalled fetch, a hung write) would hold the writers'
    lock past the window and refuse every command the next day; after `STOP_GRACE_S` the watcher ends the
    process, which frees the lock and the sandbox's job with it."""
    conn, _ = home
    fresh_sync(conn)
    monkeypatch.setattr(daemon, "POLL_S", 0.01)
    monkeypatch.setattr(daemon, "STOP_GRACE_S", 0.2)
    said: list[str] = []

    class Hung(Busy):
        obeys = False

        def hard_exit(self, why):
            said.append(why)
            self.finished.set()                      # stands in for os._exit: lets the stuck "call" return

    night = Hung(conn, sync=False)
    night.run()
    assert len(said) == 1 and "and the main thread has not come back" in said[0]
    assert "stop requested" in said[0]
    assert daemon.STOP_GRACE_S == 0.2 and Daemon.hard_exit is not Hung.hard_exit


def test_the_watcher_outlives_a_fault(home, monkeypatch):
    conn, _ = home
    fresh_sync(conn)
    monkeypatch.setattr(daemon, "POLL_S", 0.01)
    faults = {"n": 0}
    real_poll = Daemon.poll

    class Faulty(Busy):
        def poll(self):
            if threading.current_thread().name == "daemon-watch" and faults["n"] < 3:
                faults["n"] += 1
                raise OSError("the disk hiccuped")
            real_poll(self)

    night = Faulty(conn, sync=False)
    assert night.run() == "stop requested (`oeisbot daemon --stop`)"
    assert faults["n"] == 3 and sum("watcher fault (OSError: the disk hiccuped)" in l for l in night.lines) == 3


def test_a_real_sleep_ends_when_a_stop_is_asked(home):
    conn, _ = home
    d = Daemon(conn, Window.parse("always"), log=lambda m: None, sync=False)
    threading.Timer(0.2, d.stop, args=("enough",)).start()
    began = time.monotonic()
    d.sleep(600)
    assert time.monotonic() - began < 10
    began = time.monotonic()
    fresh = Daemon(conn, Window.parse("always"), log=lambda m: None, sync=False)
    fresh.sleep(0.3)                                 # and with no stop it lasts as long as asked
    assert 0.25 <= time.monotonic() - began < 10


def test_the_real_machine_checks_answer(home):
    conn, tmp = home
    d = Daemon(conn, Window.parse("always"), log=lambda m: None, sync=False)
    assert d.free_disk() > 0 and (tmp / "data").is_dir()                 # the data directory is made to be measured
    assert d.free_ram() > 0
    assert d.now().tzinfo is None and d.now_utc().tzinfo is timezone.utc


def test_the_real_sync_pulls_with_a_timeout_and_stores_a_snapshot(home, monkeypatch):
    from oeisbot import attempt
    from oeisbot.ingest import oeisdata
    conn, _ = home
    calls: list = []
    monkeypatch.setattr(oeisdata, "sync", lambda c, log, **kw: calls.append(("sync", kw)))
    monkeypatch.setattr(attempt, "snapshot_after_sync", lambda c, log: calls.append(("snapshot", None)))
    Daemon(conn, Window.parse("always"), log=lambda m: None).sync_mirror()
    assert calls == [("sync", {"pull": True, "timeout": daemon.SYNC_TIMEOUT_S}), ("snapshot", None)]
    # one git command is given less time than a stop is given to be obeyed, or a stop during a sync
    # would always end in the hard exit
    assert daemon.SYNC_TIMEOUT_S == 600 < daemon.STOP_GRACE_S == 1200


# ------------------------------------------------------------------ the command

class Args:
    def __init__(self, **kw):
        self.window, self.no_sync, self.stop, self.status = "22:00-08:00", False, False, False
        self.__dict__.update(kw)


@pytest.fixture
def no_real_night(monkeypatch):
    """The command tests below may reach `Daemon.run`. It never runs for real from a test: the suite's
    walls would stop it, but a test that depends on them is a test that passes by accident."""
    monkeypatch.setattr(daemon, "keep_awake", lambda on: None)
    monkeypatch.setattr(Daemon, "run", lambda self: pytest.fail("a real night was started from a test"))


def test_stop_and_status_only_ask(home, no_real_night, capsys):
    conn, tmp = home
    assert daemon.command(Args(status=True)) == 0
    assert "daemon is not running" in capsys.readouterr().out
    assert daemon.command(Args(stop=True)) == 0
    assert "no daemon is running; nothing to stop" in capsys.readouterr().out
    assert not daemon.stop_path().exists()           # no request left lying for the next night to trip on
    with lock.writer("daemon"):                      # one is running: the request is left, the lock untouched
        assert daemon.command(Args(stop=True)) == 0
        assert "stop requested" in capsys.readouterr().out and daemon.stop_path().exists()
        assert daemon.command(Args(status=True)) == 0
        assert "daemon is running" in capsys.readouterr().out
    daemon.stop_path().unlink()
    with lock.writer("run"):                         # a session is not a daemon: nothing to stop
        daemon.command(Args(stop=True))
        assert "no daemon is running" in capsys.readouterr().out and not daemon.stop_path().exists()


def test_the_command_runs_one_window_under_the_writers_lock(home, monkeypatch, capsys):
    conn, tmp = home
    opened: list = []
    monkeypatch.setattr(db, "connect", lambda *a, **k: opened.append(db.sqlite3.connect(":memory:")) or opened[-1])
    seen: dict = {}
    awake: list = []
    monkeypatch.setattr(daemon, "keep_awake", lambda on: awake.append((on, lock.held())))
    before = {name: signal.getsignal(getattr(signal, name)) for name in ("SIGINT", "SIGBREAK", "SIGTERM")
              if hasattr(signal, name)}

    def run(self):
        seen.update(held=lock.held(), owner=lock.read_owner()["command"], window=str(self.window), sync=self.do_sync,
                    started=self.started, handlers={n: signal.getsignal(getattr(signal, n)) for n in before})
        self.log("daemon: a line for the log")
        return "done"

    monkeypatch.setattr(Daemon, "run", run)
    began = time.time()
    assert daemon.command(Args(window="always", no_sync=True)) == 0
    assert (seen["held"], seen["owner"], seen["window"], seen["sync"]) == (True, "daemon", "always", False)
    assert began <= seen["started"] <= time.time()
    assert awake == [(True, True), (False, True)] and not lock.held()    # asked for under the lock, and given back
    # its handlers were in place for the night and are gone after it: all three, SIGBREAK included
    assert all(seen["handlers"][n] is not before[n] for n in before)
    assert {n: signal.getsignal(getattr(signal, n)) for n in before} == before
    with pytest.raises(db.sqlite3.ProgrammingError):
        opened[0].execute("SELECT 1")                # the connection was closed
    (log,) = list((tmp / "data" / "daemon").glob("daemon-*.log"))
    line = log.read_text(encoding="utf-8").rstrip()
    assert line.endswith("daemon: a line for the log") and line[2] == line[5] == ":"     # HH:MM:SS first
    assert "daemon: a line for the log" in capsys.readouterr().out


def test_ctrl_c_asks_once_and_ends_at_once_the_second_time(home, monkeypatch):
    conn, tmp = home
    monkeypatch.setattr(db, "connect", lambda *a, **k: db.sqlite3.connect(":memory:"))
    monkeypatch.setattr(daemon, "keep_awake", lambda on: None)
    seen: dict = {}

    def run(self):
        press = signal.getsignal(signal.SIGINT)
        press(signal.SIGINT, None)                   # the first press: a request, and the night goes on to obey it
        seen.update(stopping=self.stopping.is_set(), reason=self.stop_reason)
        press(signal.SIGINT, None)                   # the second is not asked to wait
        pytest.fail("the second press did not end the run")

    monkeypatch.setattr(Daemon, "run", run)
    assert daemon.command(Args(window="always")) == 130
    assert seen == {"stopping": True, "reason": "interrupted from the console"}
    assert not lock.held()
    beat = daemon.read_heartbeat()
    assert (beat["state"], beat["detail"]) == ("stopped", "ended at once from the console")
    (log,) = list((tmp / "data" / "daemon").glob("daemon-*.log"))
    text = log.read_text(encoding="utf-8")
    assert "press Ctrl-C again to end at once" in text and "ended at once from the console" in text


def test_a_fault_that_ends_the_night_is_in_the_log_and_the_exit_code(home, monkeypatch, capsys):
    """A scheduled task has no console: a traceback that only went to stderr was never seen, and the
    heartbeat went on saying "running"."""
    from oeisbot import cli
    conn, tmp = home
    monkeypatch.setattr(db, "connect", lambda *a, **k: db.sqlite3.connect(":memory:"))
    monkeypatch.setattr(daemon, "keep_awake", lambda on: None)
    monkeypatch.setattr(Daemon, "run", lambda self: (_ for _ in ()).throw(RuntimeError("recovery could not read the database")))
    assert cli.main(["daemon", "--window", "always"]) == 1           # and the code reaches the process
    assert not lock.held()
    beat = daemon.read_heartbeat()
    assert (beat["state"], beat["detail"]) == ("stopped", "ended by a fault: RuntimeError: recovery could not read the database")
    text = next((tmp / "data" / "daemon").glob("daemon-*.log")).read_text(encoding="utf-8")
    assert "ended by a fault (RuntimeError: recovery could not read the database)" in text
    assert "Traceback (most recent call last)" in text
    # the second Ctrl-C's code leaves the process too
    monkeypatch.setattr(Daemon, "run", lambda self: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert cli.main(["daemon", "--window", "always"]) == 130
    # and the ordinary end is still zero
    monkeypatch.setattr(Daemon, "run", lambda self: "done")
    assert cli.main(["daemon", "--window", "always"]) == 0


def test_the_last_resort_ends_git_before_the_process(home, monkeypatch):
    from oeisbot.ingest import oeisdata
    conn, _ = home
    order: list[str] = []
    monkeypatch.setattr(oeisdata, "end_running_git", lambda: order.append("git"))
    monkeypatch.setattr(daemon.os, "_exit", lambda code: order.append(f"exit {code}"))
    lines: list[str] = []
    Daemon(conn, Window.parse("always"), log=lines.append).hard_exit("asked to stop 20 min ago")
    assert order == ["git", "exit 3"] and lines == ["daemon: asked to stop 20 min ago; ending the process"]
    # even if ending git raises, the process still ends
    order.clear()
    monkeypatch.setattr(oeisdata, "end_running_git", lambda: (_ for _ in ()).throw(OSError("taskkill is missing")))
    with pytest.raises(OSError):
        Daemon(conn, Window.parse("always"), log=lambda m: None).hard_exit("x")
    assert order == ["exit 3"]


def test_the_command_refuses_a_bad_window(home, no_real_night, monkeypatch):
    awake: list = []
    monkeypatch.setattr(daemon, "keep_awake", awake.append)
    with pytest.raises(SystemExit, match="expected HH:MM-HH:MM"):
        daemon.command(Args(window="tonight"))
    assert awake == [] and not lock.held()


def _daemon_log(tmp) -> str:
    return "".join(p.read_text(encoding="utf-8") for p in (tmp / "data" / "daemon").glob("daemon-*.log"))


def test_a_start_that_finds_the_lock_held_waits_while_the_window_is_open(home, monkeypatch):
    """The scheduled task fires once a day. An `oeisbot attempt` started by hand at 21:30 and still
    running at 22:00 used to cost the whole night, and say so only on a console the task does not have."""
    conn, tmp = home
    monkeypatch.setattr(db, "connect", lambda *a, **k: db.sqlite3.connect(":memory:"))
    monkeypatch.setattr(daemon, "keep_awake", lambda on: None)
    monkeypatch.setattr(daemon, "_now", lambda: at("2026-11-22 22:00:00"))
    ran: list = []
    monkeypatch.setattr(Daemon, "run", lambda self: ran.append((lock.read_owner()["command"], self.started)) or "done")
    other = lock.writer("attempt")
    other.__enter__()
    slept: list = []

    def sleep(seconds):                              # the other command finishes during the third wait
        if seconds != daemon.LOCK_RETRY_S:
            return                                   # the lock's own short pauses between its tries
        slept.append(seconds)
        if len(slept) == 3:
            other.__exit__(None, None, None)

    monkeypatch.setattr(daemon.time, "sleep", sleep)
    began = time.time()
    assert daemon.command(Args()) == 0
    assert slept == [daemon.LOCK_RETRY_S] * 3 == [60.0] * 3
    assert ran[0][0] == "daemon" and ran[0][1] >= began      # `started` is when it got the lock, not when it first asked
    text = _daemon_log(tmp)
    assert text.count("`oeisbot daemon` not started: `oeisbot attempt` (pid") == 1           # said once, not every minute
    assert "Trying again every 60 s while the window is open" in text


def test_a_start_that_cannot_get_the_lock_says_so_in_the_log(home, no_real_night, monkeypatch):
    conn, tmp = home
    monkeypatch.setattr(daemon.time, "sleep", lambda s: pytest.fail("it waited") if s == daemon.LOCK_RETRY_S else None)
    with lock.writer("run"):
        # no window to wait in: once, and no
        assert daemon.command(Args(window="always")) == 1
        assert _daemon_log(tmp).rstrip().endswith("daemon: not started: the writers' lock is held")
        # started by day (a caught-up task, or by hand): the window is not open, so there is nothing to wait for
        monkeypatch.setattr(daemon, "_now", lambda: at("2026-11-22 12:00:00"))
        assert daemon.command(Args()) == 1
        assert _daemon_log(tmp).rstrip().endswith("daemon: not started: the writers' lock is held and the window is not open")
        # held until the window closed: it gives up when the clock says so
        clock = {"now": at("2026-11-23 07:59:30")}
        monkeypatch.setattr(daemon, "_now", lambda: clock["now"])
        monkeypatch.setattr(daemon.time, "sleep", lambda s: clock.update(now=clock["now"] + timedelta(seconds=s))
                            if s == daemon.LOCK_RETRY_S else None)
        assert daemon.command(Args()) == 1
        assert _daemon_log(tmp).rstrip().endswith("daemon: not started: the writers' lock is held and the window has closed")
    assert daemon.read_heartbeat() is None           # it never ran: it has nothing to say about a night


def test_a_database_that_cannot_be_opened_is_said_in_the_log(home, monkeypatch):
    conn, tmp = home
    monkeypatch.setattr(daemon, "keep_awake", lambda on: pytest.fail("it asked the machine to stay awake"))
    monkeypatch.setattr(db, "connect", lambda *a, **k: (_ for _ in ()).throw(db.sqlite3.OperationalError("unable to open database file")))
    assert daemon.command(Args(window="always")) == 1
    assert "not started: the database could not be opened (OperationalError: unable to open database file)" in _daemon_log(tmp)
    assert not lock.held()


def test_a_log_line_the_console_cannot_show_does_not_stop_anything(home, monkeypatch):
    """Under Task Scheduler stdout is a file in a legacy code page, and OEIS names are not ASCII. `print`
    raised on the first such line and ended the night there, every night."""
    conn, tmp = home

    def cp1252_print(*args, **kwargs):
        "".join(map(str, args)).encode("cp1252")
    monkeypatch.setattr(builtins, "print", cp1252_print)
    log = daemon.log_to(tmp / "logs")
    log("daemon: A000796 Decimal expansion of π")
    log("daemon: still here")
    lines = next((tmp / "logs").glob("daemon-*.log")).read_text(encoding="utf-8").splitlines()
    assert [l[9:] for l in lines] == ["daemon: A000796 Decimal expansion of π", "daemon: still here"]
    # and a log directory that cannot be written still leaves the console
    monkeypatch.undo()
    (tmp / "blocked").write_text("a file where the directory should be")
    shown: list[str] = []
    monkeypatch.setattr(builtins, "print", lambda *a, **k: shown.append(a[0]))
    daemon.log_to(tmp / "blocked")("daemon: said anyway")
    assert shown == ["daemon: said anyway"]


def test_the_cli_knows_the_daemon_and_does_not_lock_around_it(home, no_real_night, capsys):
    from oeisbot import cli
    assert "daemon" not in cli.LOCKED
    assert cli.main(["daemon", "--status"]) == 0
    assert "daemon is not running" in capsys.readouterr().out
    with lock.writer("daemon"):                      # --stop and --status must work while it is held
        assert cli.main(["daemon", "--stop"]) == 0 and cli.main(["daemon", "--status"]) == 0
    with pytest.raises(SystemExit, match="expected HH:MM-HH:MM"):
        cli.main(["daemon", "--window", "22:00-22:00"])


def test_keep_awake_asks_windows_for_the_system_only(monkeypatch):
    import ctypes
    import sys
    if sys.platform != "win32":
        pytest.skip("Windows only")
    asked: list[int] = []

    class Kernel:
        @staticmethod
        def SetThreadExecutionState(flags):
            asked.append(flags)

    monkeypatch.setattr(ctypes, "windll", type("W", (), {"kernel32": Kernel})())
    daemon.keep_awake(True)
    daemon.keep_awake(False)
    assert asked == [0x80000001, 0x80000000]         # continuous + system required; then continuous alone


# ------------------------------------------------------------------ arming

def test_an_unarmed_start_does_nothing_at_all(home, monkeypatch, capsys):
    """The safeguard added after 2026-11-22. Being started proves nothing about being meant: a scheduled
    task imported and forgotten, a script, an agent, a test falling through its stubs all start the
    daemon the same way. So a start does nothing until a person has armed it, and an unarmed start
    touches neither the lock, nor the database, nor the heartbeat: only its log."""
    conn, tmp = home
    assert daemon.disarm() is True and not daemon.is_armed()
    monkeypatch.setattr(db, "connect", lambda *a, **k: pytest.fail("the database was opened"))
    monkeypatch.setattr(lock, "writer", lambda *a, **k: pytest.fail("the writers' lock was taken"))
    monkeypatch.setattr(daemon, "keep_awake", lambda on: pytest.fail("the machine was asked to stay awake"))
    monkeypatch.setattr(Daemon, "run", lambda self: pytest.fail("a night was started"))
    assert daemon.command(Args(window="always")) == 2
    assert daemon.command(Args()) == 2
    text = _daemon_log(tmp)
    assert text.count("daemon: not started: not armed. A night runs here only after `oeisbot daemon --arm`") == 2
    assert daemon.read_heartbeat() is None and not lock.lock_path().exists()
    assert "not started: not armed" in capsys.readouterr().out
    # --status, --stop and --task-xml need no arming: they start nothing
    monkeypatch.undo()
    monkeypatch.setattr(Daemon, "run", lambda self: pytest.fail("a night was started"))
    assert daemon.command(Args(status=True)) == 0
    assert "not armed: a start will do nothing until you run `oeisbot daemon --arm`" in capsys.readouterr().out
    assert daemon.command(Args(stop=True)) == 0


def test_arming_is_one_deliberate_command_and_can_be_taken_back(home, monkeypatch, capsys):
    from oeisbot import cli
    conn, tmp = home
    daemon.disarm()
    monkeypatch.setattr(db, "connect", lambda *a, **k: db.sqlite3.connect(":memory:"))
    monkeypatch.setattr(daemon, "keep_awake", lambda on: None)
    ran: list = []
    monkeypatch.setattr(Daemon, "run", lambda self: ran.append(1) or "done")
    assert cli.main(["daemon", "--window", "always"]) == 2 and ran == []
    assert cli.main(["daemon", "--arm"]) == 0 and ran == []      # arming starts nothing by itself
    said = capsys.readouterr().out
    assert "armed (" in said and "oeisbot daemon --disarm" in said
    assert daemon.is_armed() and daemon.status()["armed"] is True
    assert "local time" in daemon.armed_path().read_text()
    assert cli.main(["daemon", "--window", "always"]) == 0 and ran == [1]
    assert cli.main(["daemon", "--disarm"]) == 0
    assert "disarmed: a start will now do nothing" in capsys.readouterr().out and not daemon.is_armed()
    assert cli.main(["daemon", "--window", "always"]) == 2 and ran == [1]
    assert cli.main(["daemon", "--disarm"]) == 0
    assert "(it was not armed)" in capsys.readouterr().out
    # disarming does not stop a daemon that is running, and says so
    with lock.writer("daemon"):
        cli.main(["daemon", "--disarm"])
        assert "is not stopped by this: use `oeisbot daemon --stop`" in capsys.readouterr().out


def test_arming_survives_a_night_and_a_kill(home):
    """It is the user's standing permission, not a one-night token: nothing the daemon does removes it."""
    conn, _ = home
    fresh_sync(conn)
    Night(conn, sync=False, pools={"base": []}, tiers=daemon.TIERS[:1]).run()
    assert daemon.is_armed()
    Night(conn, sync=False, pools={"base": []}, tiers=daemon.TIERS[:1]).recover()
    assert daemon.is_armed()


def test_a_mutant_left_in_the_code_stops_the_daemon_from_doing_anything(home, monkeypatch, capsys):
    """`data/item58/mutate.py` changes a source file, runs tests, and puts it back. Killed in between, it
    leaves the change -- which may be the removal of a safeguard -- and a sentinel at the root saying so.
    While that file is there the daemon starts nothing and arms nothing. (The harness's own test runs
    carry `OEISBOT_MUTATING=1`, and for them its own sentinel is not an alarm.)"""
    conn, tmp = home
    monkeypatch.setattr(config, "ROOT", tmp)
    monkeypatch.setattr(Daemon, "run", lambda self: pytest.fail("a night was started"))
    monkeypatch.delenv("OEISBOT_MUTATING", raising=False)
    daemon.disarm()
    (tmp / daemon.MUTANT_SENTINEL).write_text('{"file": "oeisbot/guard.py", "mutant": "nothing is ever under test"}')
    assert daemon.MUTANT_SENTINEL == "MUTANT_IN_TREE.json"
    for args in (Args(window="always"), Args(arm=True), Args(disarm=True)):
        with pytest.raises(SystemExit, match="a mutation run was interrupted and left a changed file in the code"):
            daemon.command(args)
    assert not daemon.is_armed()
    assert daemon.command(Args(status=True)) == 0        # looking is still allowed
    monkeypatch.setenv("OEISBOT_MUTATING", "1")          # the harness's own run: not an alarm
    assert daemon.command(Args(arm=True)) == 0 and daemon.is_armed()
    monkeypatch.delenv("OEISBOT_MUTATING")
    (tmp / daemon.MUTANT_SENTINEL).unlink()
    assert daemon.command(Args(disarm=True)) == 0


def test_a_refusal_at_the_last_moment_is_a_refusal_not_a_fault(home, monkeypatch):
    """Disarmed between the command's check and the night (or refused by the guard): nothing ran, so it
    is reported as an unarmed start is -- logged, exit 2, no heartbeat -- not as a night that failed."""
    conn, tmp = home
    monkeypatch.setattr(db, "connect", lambda *a, **k: db.sqlite3.connect(":memory:"))
    monkeypatch.setattr(daemon, "keep_awake", lambda on: None)
    real_run = Daemon.run

    def disarmed_meanwhile(self):
        daemon.disarm()
        return real_run(self)                        # the night's own check, not the command's

    monkeypatch.setattr(Daemon, "run", disarmed_meanwhile)
    assert daemon.command(Args(window="always", no_sync=True)) == 2
    text = _daemon_log(tmp)
    assert "daemon: not started: the daemon is not armed: a night runs here only after `oeisbot daemon --arm`" in text
    assert "ended by a fault" not in text and daemon.read_heartbeat() is None and not lock.held()
    from oeisbot.guard import RealProjectRefused
    daemon.arm()
    monkeypatch.setattr(Daemon, "run", lambda self: (_ for _ in ()).throw(RealProjectRefused("refused under a test: x")))
    assert daemon.command(Args(window="always", no_sync=True)) == 2
    assert "daemon: not started: refused under a test: x" in _daemon_log(tmp)
