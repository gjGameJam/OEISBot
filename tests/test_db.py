from __future__ import annotations

import json
import sqlite3
from dataclasses import replace

import pytest

from oeisbot import db, select
from oeisbot.config import GiB, Budgets
from oeisbot.sandbox import RunResult, Status
from oeisbot.terms import KnownTerms, Program
from oeisbot.verify import AttemptResult, Prediction, Stop, TermRecord


def make_result(stop=Stop.MAX_NEW_TERMS, verified=True, new=2, sha_source="x"):
    known = KnownTerms("A000001", 0, {0: 0, 1: 1}, "bfile")
    prog = Program("python", sha_source, origin="test", strategy="python:test")
    recs = [TermRecord(n, n, 0.1 * n, 0.1 * n, n, 1000, 0.1, 0.1, 1, "known" if n < 2 else "new") for n in range(2 + new)]
    preds = [Prediction(n, "work", 1.0, 0.5, 2.0, 1e6, "exp", True, True, False, False, 10, [], actual_s=1.2)
             for n in range(2, 2 + new)]
    run = RunResult(Status.STOPPED, 1, 3.0, 2.5, 50_000_000, 1 << 30, "stop")
    return AttemptResult(prog, known, "extended" if verified and new else "verified" if verified else "failed",
                         stop, "detail", verified, 2, recs, preds, run)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.sqlite3")
    yield c
    c.close()


def test_wal_mode_and_readonly_reader(tmp_path, conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    aid = db.record_attempt(conn, make_result(), started_at=db.now())
    ro = db.connect(tmp_path / "t.sqlite3", readonly=True)
    assert ro.execute("SELECT outcome, new_terms FROM attempts WHERE id = ?", (aid,)).fetchone()[:] == ("extended", 2)
    with pytest.raises(Exception):
        ro.execute("DELETE FROM attempts")
    ro.close()


def test_attempt_and_predictions_recorded(conn):
    aid = db.record_attempt(conn, make_result(), started_at=db.now())
    rows = conn.execute("SELECT n, predicted_s, actual_s FROM predictions WHERE attempt_id = ? ORDER BY n", (aid,)).fetchall()
    assert [tuple(r) for r in rows] == [(2, 1.0, 1.2), (3, 1.0, 1.2)]


def test_dead_end_detection(conn):
    budgets = Budgets()
    bad = make_result(stop=Stop.WRONG_TERM, verified=False, new=0, sha_source="buggy")
    db.record_attempt(conn, bad, started_at=db.now())
    assert db.is_dead_end(conn, "A000001", bad.program.sha, 2, budgets)
    assert not db.is_dead_end(conn, "A000001", bad.program.sha, 3, budgets)        # b-file grew: worth retrying
    timeout = make_result(stop=Stop.TIMEOUT, verified=False, new=0, sha_source="slow")
    db.record_attempt(conn, timeout, started_at=db.now())
    assert not db.is_dead_end(conn, "A000001", timeout.program.sha, 2, budgets)    # transient; budgets may change


def test_infeasible_is_a_dead_end_only_without_a_bigger_budget(conn):
    budgets = Budgets(extend_wall_s=600, mem_bytes=2 * GiB)
    stuck = make_result(stop=Stop.INFEASIBLE, verified=True, new=0, sha_source="stuck")
    db.record_attempt(conn, stuck, started_at=db.now(), extra={"extend_wall_s": 600, "mem_bytes": 2 * GiB})
    sha = stuck.program.sha
    assert db.is_dead_end(conn, "A000001", sha, 2, budgets)
    assert db.is_dead_end(conn, "A000001", sha, 2, replace(budgets, extend_wall_s=300, mem_bytes=GiB))
    assert not db.is_dead_end(conn, "A000001", sha, 2, replace(budgets, extend_wall_s=3600))   # more time
    assert not db.is_dead_end(conn, "A000001", sha, 2, replace(budgets, mem_bytes=4 * GiB))    # more memory
    unknown = make_result(stop=Stop.INFEASIBLE, verified=True, new=0, sha_source="recorded before budgets")
    db.record_attempt(conn, unknown, started_at=db.now())
    assert not db.is_dead_end(conn, "A000001", unknown.program.sha, 2, budgets)


def test_extension_used_up_is_a_dead_end_only_without_more_time(conn):
    budgets = Budgets(extend_wall_s=600, mem_bytes=2 * GiB)

    def used_up(source, cpu_share=0.95, new=0, stored=True):
        r = make_result(stop=Stop.EXTEND_BUDGET, verified=True, new=new, sha_source=source)
        r.run = replace(r.run, wall_s=610.0, cpu_s=610.0 * cpu_share)
        db.record_attempt(conn, r, started_at=db.now(),
                          extra={"extend_wall_s": 600, "mem_bytes": 2 * GiB} if stored else None)
        return r.program.sha

    sha = used_up("searched 600 s")
    assert db.is_dead_end(conn, "A000001", sha, 2, budgets)                                     # the same time
    assert db.is_dead_end(conn, "A000001", sha, 2, replace(budgets, extend_wall_s=300))
    assert db.is_dead_end(conn, "A000001", sha, 2, replace(budgets, mem_bytes=16 * GiB))      # memory never ends one
    assert not db.is_dead_end(conn, "A000001", sha, 2, replace(budgets, extend_wall_s=601))   # more time
    assert not db.is_dead_end(conn, "A000001", sha, 3, budgets)                               # more known terms
    assert not db.is_dead_end(conn, "A000001", used_up("found some", new=2), 2, budgets)
    assert not db.is_dead_end(conn, "A000001", used_up("recorded before budgets", stored=False), 2, budgets)
    # a busy machine: the run got too little CPU to count
    starved = db.EXTEND_DEAD_END_MIN_CPU_SHARE
    assert not db.is_dead_end(conn, "A000001", used_up("starved", cpu_share=starved - 0.01), 2, budgets)
    assert db.is_dead_end(conn, "A000001", used_up("just enough", cpu_share=starved + 0.01), 2, budgets)
    exact = make_result(stop=Stop.EXTEND_BUDGET, verified=True, new=0, sha_source="exactly the share")
    exact.run = replace(exact.run, wall_s=500.0, cpu_s=500.0 * starved)
    db.record_attempt(conn, exact, started_at=db.now(), extra={"extend_wall_s": 600, "mem_bytes": 2 * GiB})
    assert db.is_dead_end(conn, "A000001", exact.program.sha, 2, budgets)
    # a killed term is not a used-up extension: the kill does not depend on the budget
    killed = make_result(stop=Stop.OVER_PREDICTION, verified=True, new=0, sha_source="killed")
    killed.run = replace(killed.run, wall_s=610.0, cpu_s=600.0)
    db.record_attempt(conn, killed, started_at=db.now(), extra={"extend_wall_s": 600, "mem_bytes": 2 * GiB})
    assert not db.is_dead_end(conn, "A000001", killed.program.sha, 2, budgets)


def test_verify_timeout_is_a_dead_end_up_to_the_time_it_already_ran(conn):
    slow = make_result(stop=Stop.VERIFY_TIMEOUT, verified=False, new=0, sha_source="slow to verify")
    slow.run = replace(slow.run, wall_s=60.3)      # the run spent 60.3 s without reproducing the known terms
    db.record_attempt(conn, slow, started_at=db.now())
    sha = slow.program.sha
    assert db.is_dead_end(conn, "A000001", sha, 2, Budgets(verify_wall_s=60))
    assert db.is_dead_end(conn, "A000001", sha, 2, Budgets(verify_wall_s=30))
    assert not db.is_dead_end(conn, "A000001", sha, 2, Budgets(verify_wall_s=600))   # a longer pass revisits it
    assert not db.is_dead_end(conn, "A000001", sha, 3, Budgets(verify_wall_s=60))    # more known terms to check
    exact = make_result(stop=Stop.VERIFY_TIMEOUT, verified=False, new=0, sha_source="stopped right at the budget")
    exact.run = replace(exact.run, wall_s=60.0)
    db.record_attempt(conn, exact, started_at=db.now())
    assert db.is_dead_end(conn, "A000001", exact.program.sha, 2, Budgets(verify_wall_s=60))
    # the sandbox's own wall clock is not the verify budget: still not a dead end (test_dead_end_detection)
    timeout = make_result(stop=Stop.TIMEOUT, verified=False, new=0, sha_source="wall clock")
    timeout.run = replace(timeout.run, wall_s=5000.0)
    db.record_attempt(conn, timeout, started_at=db.now())
    assert not db.is_dead_end(conn, "A000001", timeout.program.sha, 2, Budgets(verify_wall_s=60))


def test_record_win_is_one_transaction(conn):
    aid = db.record_attempt(conn, make_result(), started_at=db.now(), outcome="recheck_pending",
                            extra={"recheck": "not done yet"})
    db.add_review(conn, "A000001", aid, "artifacts/x", 2, 3)       # makes the review insert fail (attempt_id is unique)
    with pytest.raises(sqlite3.IntegrityError):
        db.record_win(conn, aid, "A000001", "artifacts/y", 2, 3, "still new")
    row = conn.execute("SELECT outcome, artifact_path, extra FROM attempts WHERE id = ?", (aid,)).fetchone()
    assert (row["outcome"], row["artifact_path"], json.loads(row["extra"])) == ("recheck_pending", None, {"recheck": "not done yet"})


def test_pool_leaves_out_sequences_that_could_only_be_skipped(conn):
    rows = [db.SequenceRow(a, "x", 0, "nonn,more", terms, 1, langs, 0, False)
            for a, terms, langs in [("A000001", 2, "mathematica"), ("A000002", 2, "pari"),
                                    ("A000003", 2, "mathematica"), ("A000004", 3, "")]]
    db.upsert_sequences(conn, rows)
    for a in ("A000001", "A000002", "A000004"):
        db.update_bfile_info(conn, a, "absent")
    # A000001: 2 known terms, no PARI, b-file looked up: the model would refuse it
    # A000003: same, but the b-file has not been looked up yet and could add terms
    assert sorted(c.a_number for c in select.candidates(conn)) == ["A000002", "A000003", "A000004"]
    db.update_bfile_info(conn, "A000003", "present", 40, 39, 5)
    assert "A000003" in {c.a_number for c in select.candidates(conn)}


def test_failure_penalty_counts_attempts_not_rows(conn):
    # x2 per earlier attempt with a `failed` or `verified` row, capped at x64; the rows of one attempt share
    # extra.attempt_call, and a row without it counts on its own
    db.upsert_sequences(conn, [db.SequenceRow("A000001", "x", 0, "nonn,more", 10, 1, "pari", 0, False)])
    base = select.difficulty(conn.execute("SELECT * FROM sequences").fetchone())

    def penalty():
        [c] = select.candidates(conn)
        return c.difficulty / base

    def run(outcome, extra):
        r = make_result(stop=Stop.WRONG_TERM, verified=False, new=0) if outcome == "failed" else \
            make_result(stop=Stop.EXTEND_BUDGET, verified=True, new=0)
        return db.record_attempt(conn, r, started_at=db.now(), outcome=outcome, extra=extra)

    assert penalty() == 1
    for _ in range(3):                                   # one attempt: say a PARI run and two model generations
        run("failed", {"attempt_call": "a"})
    assert penalty() == 2
    run("verified", {"attempt_call": "b"})              # a verified run with nothing new counts too
    assert penalty() == 4
    run("failed", {"attempt_call": "b"})                 # ...once for its attempt
    assert penalty() == 4
    run("extended", {"attempt_call": "c"})               # an attempt with neither kind of row does not count
    run("superseded", {"attempt_call": "c"})
    db.record_skip(conn, "A000001", "pari", "no_supported_program")
    assert penalty() == 4
    run("failed", {"attempt_call": "d"})                 # one that also has such a row counts once
    run("extended", {"attempt_call": "d"})
    assert penalty() == 8
    run("failed", {})                                    # no key (a row written before keys existed)
    run("failed", {"log": "x"})
    assert penalty() == 32
    bad = run("failed", {"attempt_call": "e"})
    with conn:                                           # an unreadable extra counts on its own, and breaks nothing
        conn.execute("UPDATE attempts SET extra = 'not json' WHERE id = ?", (bad,))
    assert penalty() == 64
    run("failed", {"attempt_call": "f"})
    assert penalty() == 64                               # the cap


def test_review_cannot_be_submitted_twice(conn):
    a1 = db.record_attempt(conn, make_result(sha_source="a"), started_at=db.now())
    a2 = db.record_attempt(conn, make_result(sha_source="b"), started_at=db.now())
    r1 = db.add_review(conn, "A000001", a1, "artifacts/x", 2, 3)
    r2 = db.add_review(conn, "A000001", a2, "artifacts/y", 2, 3)
    assert db.open_review(conn, "A000001")["id"] == r2
    db.set_review_status(conn, r1, "submitted")
    with pytest.raises(ValueError):
        db.set_review_status(conn, r2, "submitted")
    with pytest.raises(Exception):
        db.set_review_status(conn, r2, "bogus")


def test_session_rollup(conn):
    sid = db.start_session(conn)
    db.record_attempt(conn, make_result(), started_at=db.now(), session_id=sid)
    db.record_skip(conn, "A000002", "pari", "no_program", session_id=sid)
    db.finish_session(conn, sid)
    row = conn.execute("SELECT attempts, wins, machine_s FROM sessions WHERE id = ?", (sid,)).fetchone()
    assert tuple(row) == (2, 1, 3.0)
