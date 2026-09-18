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
