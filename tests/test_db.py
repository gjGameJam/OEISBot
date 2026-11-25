from __future__ import annotations

import dataclasses
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


def test_set_meta_many_writes_all_the_keys_or_none(conn):
    """`meta` keys that describe one moment -- the runtime versions (history item 43) -- must not be
    able to land half-written, leaving a fresh gp version beside a stale Python one. `set_meta` opens a
    transaction per call and cannot promise that; this is why `set_meta_many` exists.

    Note the *caller* choosing `set_meta` in a loop instead is deliberately not detectable from outside:
    the end state is identical and only a crash between the two writes tells them apart. That mutation
    is recorded as uncatchable in the item's mutation harness rather than papered over with a test that
    asserts which function was called."""
    db.set_meta_many(conn, {"gp_version": "one", "sandbox_python_version": "two"})
    assert (db.get_meta(conn, "gp_version"), db.get_meta(conn, "sandbox_python_version")) == ("one", "two")

    # The bad binding must come SECOND, or nothing is ever applied and the assertions below hold without
    # any rollback: `set_meta_many` sorts its items, so `gp_version` is written before
    # `sandbox_python_version` fails. Reversing these two names hollows this test out silently.
    with pytest.raises(sqlite3.Error):      # a value SQLite cannot bind, part way through
        db.set_meta_many(conn, {"gp_version": "three", "sandbox_python_version": ["not a string"]})
    # the first key of the failed batch must not have survived it
    assert db.get_meta(conn, "gp_version") == "one"
    assert db.get_meta(conn, "sandbox_python_version") == "two"


def test_attempt_and_predictions_recorded(conn):
    aid = db.record_attempt(conn, make_result(), started_at=db.now())
    rows = conn.execute("SELECT n, predicted_s, actual_s FROM predictions WHERE attempt_id = ? ORDER BY n", (aid,)).fetchall()
    assert [tuple(r) for r in rows] == [(2, 1.0, 1.2), (3, 1.0, 1.2)]


def test_the_cost_fits_statistics_are_stored_and_stay_null_without_a_fit(conn):
    """A row must be able to say "the fit was sound, the drift withdrew it" (trustworthy 0,
    fit_trustworthy 1) and "there was no fit at all" (every fit column NULL) -- and never confuse the
    two. `int(None)` would raise; a bool written as 0 would read as "the fit said no"."""
    result = make_result(new=2)
    result.predictions[0] = Prediction(2, "work", 1.0, 0.5, 2.0, 1e6, "exp", False, True, True, False, 10, [],
                                       actual_s=1.2, fit_trustworthy=True, fit_npoints=5, fit_disagreement=1.75,
                                       fit_climbing=False, rate_drift=7.794)
    result.predictions[1] = Prediction(3, "work", None, None, None, 1e6, None, False, True, True, False, 10, [],
                                       actual_s=1.2)
    aid = db.record_attempt(conn, result, started_at=db.now())
    rows = conn.execute("""SELECT n, trustworthy, fit_trustworthy, fit_npoints, fit_disagreement, fit_climbing,
                           rate_drift FROM predictions WHERE attempt_id = ? ORDER BY n""", (aid,)).fetchall()
    assert [tuple(r) for r in rows] == [(2, 0, 1, 5, 1.75, 0, 7.794), (3, 0, None, None, None, None, None)]


# Every `verify.Prediction` field, and the `predictions` column it is stored in -- None for the ones
# deliberately not stored. Item 36 added five fields, and the ways that can go wrong are all silent: a
# field added to the dataclass but not to `db.SCHEMA`, or to the SCHEMA but not the INSERT, or to the
# INSERT in the wrong position. Pinning the whole mapping makes each of those a failure here, and forces
# a decision to be recorded rather than defaulted when a field is added later.
PREDICTION_COLUMNS = {
    "n": "n", "unit": "cost_unit", "seconds": "predicted_s", "seconds_low": "predicted_s_low",
    "seconds_high": "predicted_s_high", "mem_high": "predicted_mem", "model": "model",
    "trustworthy": "trustworthy", "feasible": "feasible", "value_dependent": "value_dependent",
    "actual_s": "actual_s", "actual_mem": "actual_mem", "censored_s": "censored_s",
    "fit_trustworthy": "fit_trustworthy", "fit_npoints": "fit_npoints",
    "fit_disagreement": "fit_disagreement", "fit_climbing": "fit_climbing", "rate_drift": "rate_drift",
    # not stored, each for a reason documented in docs/data-and-schema.md
    "risky": None,             # derivable: model IS NULL OR value_dependent OR NOT fit_trustworthy OR fit_climbing
    "next_bits_high": None,    # about the next term's size, not about the cost fit
    "reasons": None,           # free text; survives in artifacts/*/predictions.csv
    "actual_cost": None,       # the cost unit's own figure; actual_s is what the estimator is judged on
}


def test_every_prediction_field_is_stored_or_knowingly_not(conn):
    """The dataclass and the table must not drift apart silently."""
    fields = {f.name for f in dataclasses.fields(Prediction)}
    assert fields == set(PREDICTION_COLUMNS), (
        "verify.Prediction changed: add each new field to PREDICTION_COLUMNS with its column, or None "
        f"if it is deliberately not stored. Added {fields - set(PREDICTION_COLUMNS)}, "
        f"removed {set(PREDICTION_COLUMNS) - fields}")
    table = {r["name"] for r in conn.execute("PRAGMA table_info(predictions)")}
    mapped = {c for c in PREDICTION_COLUMNS.values() if c}
    assert mapped <= table, f"mapped to columns that do not exist: {mapped - table}"
    assert table - mapped == {"id", "attempt_id"}, (
        f"columns nothing maps to (added to db.SCHEMA but never written?): {table - mapped - {'id', 'attempt_id'}}")


def test_every_stored_prediction_field_survives_a_round_trip(conn):
    """Distinct values in every field, so a column written from the wrong one cannot look right. This is
    what catches an INSERT whose column list and value tuple have drifted out of step."""
    values = {
        "n": 7, "unit": "cpu", "seconds": 1.5, "seconds_low": 0.25, "seconds_high": 3.5,
        "mem_high": 1234.0, "model": "poly", "trustworthy": False, "feasible": True,
        "value_dependent": True, "actual_s": 2.25, "actual_mem": 4321.0, "censored_s": 8.75,
        "fit_trustworthy": True, "fit_npoints": 6, "fit_disagreement": 2.75, "fit_climbing": False,
        "rate_drift": 9.5,
    }
    result = make_result(new=1)
    result.predictions[:] = [Prediction(**values, next_bits_high=11, reasons=["why"], risky=True,
                                        actual_cost=99.0)]
    aid = db.record_attempt(conn, result, started_at=db.now())
    row = conn.execute("SELECT * FROM predictions WHERE attempt_id = ?", (aid,)).fetchone()
    stored = {field: row[PREDICTION_COLUMNS[field]] for field in values}
    # SQLite has no bool: the two flags come back as 0/1, and that is what `_opt_int` is for
    assert stored == {k: (int(v) if isinstance(v, bool) else v) for k, v in values.items()}


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
    db.record_attempt(conn, stuck, started_at=db.now(),
                      extra={"extend_wall_s": 600, "mem_bytes": 2 * GiB, "mem_cap_bytes": 2 * GiB})
    sha = stuck.program.sha
    assert db.is_dead_end(conn, "A000001", sha, 2, budgets)
    assert db.is_dead_end(conn, "A000001", sha, 2, replace(budgets, extend_wall_s=300, mem_bytes=GiB))
    assert not db.is_dead_end(conn, "A000001", sha, 2, replace(budgets, extend_wall_s=3600))   # more time
    assert not db.is_dead_end(conn, "A000001", sha, 2, replace(budgets, mem_bytes=4 * GiB))    # more memory
    unknown = make_result(stop=Stop.INFEASIBLE, verified=True, new=0, sha_source="recorded before budgets")
    db.record_attempt(conn, unknown, started_at=db.now())
    assert not db.is_dead_end(conn, "A000001", unknown.program.sha, 2, budgets)


def test_an_infeasible_verdict_is_keyed_on_the_budget_it_ran_out_of(conn):
    """Item 51. `extra.infeasible_on` says which budget the projection exceeded, and the dead-end rule
    asks about that one alone: a verdict on time holds under any memory cap and one on memory under any
    extension time. Rows without the key (every row before 2026-09-30) keep needing both, as before."""
    budgets = Budgets(extend_wall_s=600, mem_bytes=2 * GiB)

    def row(tag, on):
        r = make_result(stop=Stop.INFEASIBLE, verified=True, new=0, sha_source=tag)
        db.record_attempt(conn, r, started_at=db.now(), extra={"extend_wall_s": 600, "mem_bytes": 2 * GiB,
                                                               "mem_cap_bytes": 2 * GiB, "infeasible_on": on})
        return r.program.sha

    time_only = row("time", "time")
    assert db.is_dead_end(conn, "A000001", time_only, 2, budgets)
    assert db.is_dead_end(conn, "A000001", time_only, 2, replace(budgets, mem_bytes=8 * GiB))       # memory was not the reason
    assert not db.is_dead_end(conn, "A000001", time_only, 2, replace(budgets, extend_wall_s=3600))  # more time: try again
    mem_only = row("memory", "memory")
    assert db.is_dead_end(conn, "A000001", mem_only, 2, replace(budgets, extend_wall_s=36000))      # time was not the reason
    assert not db.is_dead_end(conn, "A000001", mem_only, 2, replace(budgets, mem_bytes=8 * GiB))
    both = row("both", "time+memory")
    assert db.is_dead_end(conn, "A000001", both, 2, budgets)
    assert not db.is_dead_end(conn, "A000001", both, 2, replace(budgets, mem_bytes=8 * GiB))
    assert not db.is_dead_end(conn, "A000001", both, 2, replace(budgets, extend_wall_s=3600))


def test_a_harness_error_is_never_a_dead_end(conn):
    """Item 51: `harness_error` is our own callback raising inside the sandbox, not the program failing.
    It sits outside DETERMINISTIC_FAILURES and matches no dead-end clause, so the program runs again."""
    assert Stop.HARNESS_ERROR.value not in db.DETERMINISTIC_FAILURES
    r = make_result(stop=Stop.HARNESS_ERROR, verified=False, new=0, sha_source="bug")
    db.record_attempt(conn, r, started_at=db.now(), extra={"extend_wall_s": 600, "mem_cap_bytes": GiB})
    row = conn.execute("SELECT failure_mode FROM attempts ORDER BY id DESC LIMIT 1").fetchone()
    assert row["failure_mode"] == "harness_error"
    assert not db.is_dead_end(conn, "A000001", r.program.sha, 2, Budgets(verify_wall_s=1, extend_wall_s=1, mem_bytes=1))


def test_a_run_squeezed_for_memory_is_not_retired(conn):
    """The infeasible clause keys on the cap the run actually got, not the one it asked for: a busy
    machine pushes the harness below the budget (`min(mem_bytes, free RAM - reserve)`), and the verdict
    was reached under that smaller cap. Such a run must be tried again once the RAM is back."""
    budgets = Budgets(extend_wall_s=600, mem_bytes=2 * GiB)
    starved = make_result(stop=Stop.INFEASIBLE, verified=True, new=0, sha_source="starved")
    db.record_attempt(conn, starved, started_at=db.now(),
                      extra={"extend_wall_s": 600, "mem_bytes": 2 * GiB, "mem_cap_bytes": GiB})
    sha = starved.program.sha
    assert not db.is_dead_end(conn, "A000001", sha, 2, budgets)                        # it never got 2 GiB
    assert db.is_dead_end(conn, "A000001", sha, 2, replace(budgets, mem_bytes=GiB))    # but it did get 1

    # the shape of every row recorded before 2026-09-20: the budgets, but no effective cap. It never
    # counts, rather than falling back to the configured budget it asked for
    legacy = make_result(stop=Stop.INFEASIBLE, verified=True, new=0, sha_source="recorded before the cap")
    db.record_attempt(conn, legacy, started_at=db.now(), extra={"extend_wall_s": 600, "mem_bytes": 2 * GiB})
    assert not db.is_dead_end(conn, "A000001", legacy.program.sha, 2, budgets)


def test_refresh_difficulty_rescores_every_row(conn):
    """Including rows that have left `more`: the column is meant to equal `select.difficulty` for every
    row in the table, not only the ones a session could pick."""
    db.upsert_sequences(conn, [db.SequenceRow("A000001", "Things", 1, "nonn,more", 5, 2, "pari", 0, False),
                               db.SequenceRow("A000002", "Things", 1, "nonn,more", 5, 2, "pari", 0, False)])
    db.mark_not_in_more(conn, {"A000001"})                       # A000002 is retired
    with conn:
        conn.execute("UPDATE sequences SET difficulty = 0")
    assert db.refresh_difficulty(conn, select.difficulty) == 2
    rows = conn.execute("SELECT * FROM sequences ORDER BY a_number").fetchall()
    assert [r["in_more"] for r in rows] == [1, 0]
    for r in rows:                                               # the retired row is scored, and correctly
        assert r["difficulty"] > 0
        assert r["difficulty"] == pytest.approx(select.difficulty(r))


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
    # the run spent 60.3 s without reproducing the known terms, nearly all of it on the CPU
    slow.run = replace(slow.run, wall_s=60.3, cpu_s=59.0)
    db.record_attempt(conn, slow, started_at=db.now())
    sha = slow.program.sha
    assert db.is_dead_end(conn, "A000001", sha, 2, Budgets(verify_wall_s=60))
    assert db.is_dead_end(conn, "A000001", sha, 2, Budgets(verify_wall_s=30))
    assert not db.is_dead_end(conn, "A000001", sha, 2, Budgets(verify_wall_s=600))   # a longer pass revisits it
    assert not db.is_dead_end(conn, "A000001", sha, 3, Budgets(verify_wall_s=60))    # more known terms to check
    exact = make_result(stop=Stop.VERIFY_TIMEOUT, verified=False, new=0, sha_source="stopped right at the budget")
    exact.run = replace(exact.run, wall_s=60.0, cpu_s=60.0)
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


def test_a_rejected_review_refuses_a_new_one_but_keeps_the_win(conn):
    """Item 51. A `rejected` review does not gate the run (item 48's deliberate asymmetry), so it gates
    the *output*: a later win of the same sequence keeps its `extended` row and its artifact path but
    opens no review, and the refusal is recorded on the attempt rather than raised out of the
    transaction -- raised, the rollback would leave it `recheck_pending`, to be retried and refused
    every session for ever."""
    a1 = db.record_attempt(conn, make_result(sha_source="a"), started_at=db.now())
    r1 = db.add_review(conn, "A000001", a1, "artifacts/x", 2, 3)
    db.set_review_status(conn, r1, "rejected", "conjectural: the program's own comment says so")
    a2 = db.record_attempt(conn, make_result(sha_source="b"), started_at=db.now(), outcome="recheck_pending",
                           extra={"recheck": "not done yet"})
    with pytest.raises(db.ReviewRefused) as e:
        db.add_review(conn, "A000001", a2, "artifacts/y", 2, 3)
    assert e.value.prior_id == r1 and f"#{r1}" in str(e.value) and "conjectural" in str(e.value)
    assert db.record_win(conn, a2, "A000001", "artifacts/y", 2, 3, "still new") is None
    row = conn.execute("SELECT outcome, artifact_path, extra FROM attempts WHERE id = ?", (a2,)).fetchone()
    assert (row["outcome"], row["artifact_path"]) == ("extended", "artifacts/y")
    extra = json.loads(row["extra"])
    assert extra["review_refused"]["prior_review"] == r1 and extra["recheck"] == "still new"
    assert conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 1
    assert db.open_review(conn, "A000001") is None
    # reopening the old row lifts the refusal: a human decides the new result is different, never the pipeline
    db.set_review_status(conn, r1, "reviewing")
    a3 = db.record_attempt(conn, make_result(sha_source="c"), started_at=db.now())
    assert db.add_review(conn, "A000001", a3, "artifacts/z", 2, 3) > r1


def test_review_rows_carry_the_identity_block_and_the_cli_prints_it(conn):
    """Item 51: `oeisbot review list` and the dashboard inbox identify a review by the same facts in the
    same order -- the sequence and its name, the addition and where it came from, then the bookkeeping."""
    from oeisbot import cli
    db.upsert_sequences(conn, [db.SequenceRow("A000001", "Things that are things", 1, "nonn,more", 5, 2, "pari", 0, False)])
    aid = db.record_attempt(conn, make_result(), started_at=db.now())
    rid = db.add_review(conn, "A000001", aid, "artifacts/x", 2, 3)
    (r,) = db.review_rows(conn)
    assert (r["id"], r["a_number"], r["name"], r["new_terms"], r["attempt_id"]) == (rid, "A000001", "Things that are things", 2, aid)
    assert r["program_origin"] and r["strategy"]
    lines = cli.review_block(r).splitlines()
    assert lines[0].startswith(f"#{rid}") and "A000001" in lines[0] and " new " in lines[0] and lines[0].endswith("Things that are things")
    assert lines[1].strip() == f"2 new terms, a(2)..a(3), from {r['program_origin']}, attempt #{aid}"
    assert lines[2].strip() == "artifacts/x"
    db.set_review_status(conn, rid, "rejected", "not it")
    (r,) = db.review_rows(conn)
    assert cli.review_block(r).splitlines()[2].strip() == "artifacts/x  not it"


def test_session_rollup(conn):
    sid = db.start_session(conn)
    db.record_attempt(conn, make_result(), started_at=db.now(), session_id=sid)
    db.record_skip(conn, "A000002", "pari", "no_program", session_id=sid)
    db.finish_session(conn, sid)
    row = conn.execute("SELECT attempts, wins, machine_s FROM sessions WHERE id = ?", (sid,)).fetchone()
    assert tuple(row) == (2, 1, 3.0)


def test_a_verify_timeout_starved_of_cpu_is_not_a_dead_end(conn):
    """Item 58. The verify budget is wall time, so a machine that slept or was busy through a verification
    used to retire the program at that budget for ever, though it never had its minute. The extension
    rule has always asked for a CPU share (EXTEND_DEAD_END_MIN_CPU_SHARE); verification now asks the same."""
    share = db.EXTEND_DEAD_END_MIN_CPU_SHARE

    def timed_out(source, wall, cpu):
        r = make_result(stop=Stop.VERIFY_TIMEOUT, verified=False, new=0, sha_source=source)
        r.run = replace(r.run, wall_s=wall, cpu_s=cpu)
        db.record_attempt(conn, r, started_at=db.now())
        return r.program.sha

    budgets = Budgets(verify_wall_s=60)
    # the machine slept: ten minutes on the wall, twenty seconds of work
    assert not db.is_dead_end(conn, "A000001", timed_out("slept", 600.0, 20.0), 2, budgets)
    assert not db.is_dead_end(conn, "A000001", timed_out("just under", 60.0, 60.0 * share - 0.1), 2, budgets)
    assert db.is_dead_end(conn, "A000001", timed_out("exactly", 60.0, 60.0 * share), 2, budgets)
    assert db.is_dead_end(conn, "A000001", timed_out("just over", 60.0, 60.0 * share + 0.1), 2, budgets)
    # What counts is the CPU the run got against the budget asked NOW, not its share of its own wall
    # time. Ten minutes at half speed is 300 s of work: more than a 60 s budget could ever give, so the
    # program is retired there, and less than 0.8 of a 600 s budget, so it is not retired there. (The
    # first version of this rule compared with the run's own wall time and brought A272621 and A101722
    # back to the 60 s pool after 288 s and 474 s of CPU had already failed them.)
    half_speed = timed_out("ten minutes at half speed", 600.0, 300.0)
    assert db.is_dead_end(conn, "A000001", half_speed, 2, budgets)
    assert not db.is_dead_end(conn, "A000001", half_speed, 2, Budgets(verify_wall_s=600))
    assert db.is_dead_end(conn, "A000001", half_speed, 2, Budgets(verify_wall_s=300 / share))     # exactly enough
    assert not db.is_dead_end(conn, "A000001", half_speed, 2, Budgets(verify_wall_s=300 / share + 1))
    # a row with no CPU figure cannot show it had the time, so it does not count
    sha = timed_out("no cpu figure", 60.0, 59.0)
    with conn:
        conn.execute("UPDATE attempts SET cpu_s = NULL WHERE program_sha = ?", (sha,))
    assert not db.is_dead_end(conn, "A000001", sha, 2, budgets)


def test_an_interrupted_run_is_never_a_dead_end(conn):
    """Item 58: `interrupted` is the caller stopping the run (the daemon's stop, the end of its window).
    Whatever state the run was in, it says nothing about the program, at any budget."""
    assert db.INTERRUPTED == Stop.INTERRUPTED.value
    assert db.INTERRUPTED not in db.DETERMINISTIC_FAILURES
    tiny = Budgets(verify_wall_s=1, extend_wall_s=1, mem_bytes=1)
    for verified, source in ((False, "stopped while verifying"), (True, "stopped while extending")):
        r = make_result(stop=Stop.INTERRUPTED, verified=verified, new=0, sha_source=source)
        r.run = replace(r.run, wall_s=5000.0, cpu_s=5000.0)       # long, and all of it on the CPU
        db.record_attempt(conn, r, started_at=db.now(),
                          extra={"extend_wall_s": 99999, "mem_bytes": 2 * GiB, "mem_cap_bytes": 2 * GiB})
        row = conn.execute("SELECT failure_mode, outcome FROM attempts ORDER BY id DESC LIMIT 1").fetchone()
        assert tuple(row) == ("interrupted", "verified" if verified else "failed")
        assert not db.is_dead_end(conn, "A000001", r.program.sha, 2, tiny)
        assert not db.is_dead_end(conn, "A000001", r.program.sha, 2, Budgets())


def test_an_interrupted_run_adds_no_failure_penalty(conn):
    """A stop lands on whatever sequence happened to be running. Counting it would make that sequence
    twice as hard to pick for something that was never about it."""
    db.upsert_sequences(conn, [db.SequenceRow("A000001", "x", 0, "nonn,more", 10, 1, "pari", 0, False)])
    base = select.difficulty(conn.execute("SELECT * FROM sequences").fetchone())

    def penalty():
        [c] = select.candidates(conn)
        return c.difficulty / base

    def run(stop, verified, call):
        r = make_result(stop=stop, verified=verified, new=0)
        return db.record_attempt(conn, r, started_at=db.now(), extra={"attempt_call": call})

    run(Stop.INTERRUPTED, False, "a")                    # outcome `failed`, and not counted
    run(Stop.INTERRUPTED, True, "b")                     # outcome `verified`, and not counted
    assert penalty() == 1
    run(Stop.WRONG_TERM, False, "c")                     # an attempt whose first program really failed ...
    run(Stop.INTERRUPTED, False, "c")                    # ... and whose second was interrupted: counted once
    assert penalty() == 2
    skipped = db.record_skip(conn, "A000001", "pari", "no_supported_program")
    with conn:                                           # made into a failed row with no failure_mode at all
        conn.execute("UPDATE attempts SET outcome = 'failed', failure_mode = NULL WHERE id = ?", (skipped,))
    assert penalty() == 4                                # NULL is not `interrupted`: it still counts


def test_a_sequence_with_a_rejected_review_is_not_drawn(conn):
    """Item 58. A win for a sequence whose review was rejected is refused a new review
    (test_a_rejected_review_refuses_a_new_one_but_keeps_the_win), so drawing it can only spend the run
    and write a folder nobody is shown. An attended session met that once in a while; a loop would meet
    it every time the draw landed there."""
    db.upsert_sequences(conn, [db.SequenceRow(a, "x", 0, "nonn,more", 10, 1, "pari", 0, False)
                               for a in ("A000001", "A000002", "A000003")])

    def drawn():
        return sorted(c.a_number for c in select.candidates(conn))

    assert drawn() == ["A000001", "A000002", "A000003"]
    first = db.record_attempt(conn, make_result(sha_source="a"), started_at=db.now())
    review = db.add_review(conn, "A000001", first, "artifacts/x", 2, 3)
    assert drawn() == ["A000002", "A000003"]             # open: a human is deciding (as before)
    db.set_review_status(conn, review, "rejected", "conjectural program")
    assert drawn() == ["A000002", "A000003"]             # rejected: still out, which is the change
    with conn:                                           # the row is a person's to remove; then it is back
        conn.execute("DELETE FROM reviews WHERE id = ?", (review,))
    assert drawn() == ["A000001", "A000002", "A000003"]
