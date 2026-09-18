"""The orchestration path end to end, with oeisdata, b-files and the oeis.org re-check stubbed out."""
from __future__ import annotations

import json
import shutil
import sqlite3
import urllib.error
from dataclasses import replace

import pytest

from oeisbot import attempt, config, db, sandbox, select
from oeisbot.config import Budgets
from oeisbot.ingest import bfile, oeisdata
from oeisbot.ingest.seqfile import parse
from oeisbot.strategies import pari

pytestmark = [
    pytest.mark.sandbox,
    pytest.mark.skipif(bool(sandbox.runtime_problems()), reason="sandbox runtime missing"),
]

PRIMES = "2,3,5,7,11,13,17,19,23,29,31,37,41,43,47"
FAST = Budgets(verify_wall_s=30, extend_wall_s=5, max_new_terms=5)


def make_entry(program: str, data: str = PRIMES, keywords: str = "nonn,more"):
    return parse(f"%S A999999 {data}\n%N A999999 The primes.\n%O A999999 1,1\n%K A999999 {keywords}\n"
                 f"%o A999999 (PARI) {program}\n")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path / "artifacts")
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(bfile, "fetch", lambda a, refresh=False: None)
    monkeypatch.setattr(attempt, "RECHECK_RETRY_WAITS_S", (0.0, 0.0))
    state = {"program": "a(n) = prime(n)", "data": PRIMES, "keywords": "nonn,more",
             "recheck": (True, "live entry ends at a(15)"), "recheck_calls": 0}

    def fake_recheck(known, first, new):
        state["recheck_calls"] += 1
        if isinstance(state["recheck"], BaseException):
            raise state["recheck"]
        return state["recheck"]

    monkeypatch.setattr(oeisdata, "load_entry",
                        lambda a: make_entry(state["program"], state["data"], state["keywords"]))
    monkeypatch.setattr(attempt, "recheck", fake_recheck)
    conn = db.connect(tmp_path / "t.sqlite3")
    yield conn, state, tmp_path
    conn.close()


def test_success_writes_artifact_and_review(env):
    conn, _, tmp = env
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert rep.artifact, rep.lines
    extra = json.loads(conn.execute("SELECT extra FROM attempts WHERE id = ?", (rep.attempt_ids[-1],)).fetchone()[0])
    assert (extra["extend_wall_s"], extra["mem_bytes"]) == (FAST.extend_wall_s, FAST.mem_bytes)
    assert extra["recheck"] == "live entry ends at a(15)" and not attempt.pending_path(rep.attempt_ids[-1]).exists()
    folder = tmp / "artifacts" / "A999999" / f"attempt-{rep.attempt_ids[-1]}"
    bf = (folder / "b999999.txt").read_text().splitlines()
    assert bf[0] == "1 2" and bf[14] == "15 47" and bf[15:] == ["16 53", "17 59", "18 61", "19 67", "20 71"]
    readme = (folder / "README.md").read_text()
    assert "a(16)..a(20)" in readme and "Weak verification" not in readme
    assert {p.name for p in folder.iterdir()} >= {"README.md", "program.gp", "executed.gp", "verification.md",
                                                  "timing.csv", "predictions.csv", "run.json"}
    review = db.open_review(conn, "A999999")
    assert review["status"] == "new" and (review["first_new_index"], review["last_new_index"]) == (16, 20)

    again = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert again.skipped == "open_review"


def test_superseded_run_records_no_artifact(env):
    conn, state, _ = env
    state["recheck"] = (False, "live entry already has 5 of the new terms")
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert rep.artifact is None
    row = conn.execute("SELECT outcome FROM attempts WHERE id = ?", (rep.attempt_ids[-1],)).fetchone()
    assert row["outcome"] == "superseded"
    assert db.open_review(conn, "A999999") is None


def test_deterministic_failure_is_not_repeated(env):
    conn, state, _ = env
    state["program"] = "a(n) = prime(n) + (n == 7)"
    first = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    row = conn.execute("SELECT failure_mode FROM attempts WHERE id = ?", (first.attempt_ids[-1],)).fetchone()
    assert row["failure_mode"] == "wrong_term"
    second = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert second.skipped == "all_programs_dead_ends"


def missing_entry(monkeypatch, state):
    monkeypatch.setattr(oeisdata, "load_entry", lambda a: None)


def no_more_keyword(monkeypatch, state):
    state["keywords"] = "nonn,easy"


def bfile_lookup_fails(monkeypatch, state):
    def boom(a, refresh=False):
        raise urllib.error.HTTPError("url", 500, "server error", {}, None)
    monkeypatch.setattr(bfile, "fetch", boom)


def bfile_disagrees_with_data(monkeypatch, state):
    monkeypatch.setattr(bfile, "fetch", lambda a, refresh=False: bfile.BFile(a, {1: 2, 2: 4}))   # a(2) is 3


@pytest.mark.parametrize("break_it, reason", [(missing_entry, "not_in_oeisdata"),
                                              (no_more_keyword, "no_more_keyword"),
                                              (bfile_lookup_fails, "bfile_error"),
                                              (bfile_disagrees_with_data, "inconsistent_known_terms")])
def test_gates_record_a_skip_and_run_nothing(env, monkeypatch, break_it, reason):
    conn, state, _ = env
    break_it(monkeypatch, state)
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert rep.skipped == reason and rep.artifact is None
    rows = conn.execute("SELECT outcome, failure_mode, program_sha FROM attempts").fetchall()
    assert [tuple(r) for r in rows] == [("skipped", reason, None)]


def test_infeasible_dead_end_runs_again_with_a_bigger_budget(env):
    conn, state, _ = env
    entry = make_entry(state["program"])
    known = bfile.known_terms(entry, None)
    candidates, _ = pari.build_candidates(entry, known)
    program = candidates[0].program
    with conn:      # an earlier run that verified every known term and judged the next one infeasible
        conn.execute("""INSERT INTO attempts(a_number, strategy, program_sha, started_at, verified, known_terms,
                            new_terms, outcome, failure_mode, extra)
                        VALUES ('A999999', ?, ?, ?, 1, ?, 0, 'verified', 'infeasible', ?)""",
                     (program.strategy, program.sha, db.now(), known.count,
                      json.dumps({"extend_wall_s": FAST.extend_wall_s, "mem_bytes": FAST.mem_bytes})))

    assert attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None).skipped == "all_programs_dead_ends"
    bigger = replace(FAST, extend_wall_s=FAST.extend_wall_s * 2)
    rep = attempt.attempt_sequence(conn, "A999999", bigger, log=lambda m: None)
    assert rep.skipped is None and rep.artifact, rep.lines
    ran = conn.execute("SELECT COUNT(*) FROM attempts WHERE program_sha = ? AND outcome = 'extended'",
                       (program.sha,)).fetchone()[0]
    assert ran == 1


def test_too_few_known_terms_is_recorded_after_the_pari_stage(env):
    conn, state, _ = env
    state["data"], state["program"] = "5,6", "a(n) = n"       # 2 known terms, and a program that gets them wrong
    model = object()                                          # never used: calling it would raise AttributeError
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None, model=model)
    assert rep.skipped == "too_few_known_terms"
    rows = conn.execute("SELECT strategy, outcome, failure_mode FROM attempts ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [("pari:a(n)", "failed", "wrong_term"),
                                        ("python:model", "skipped", "too_few_known_terms")]


def test_a_win_survives_a_failed_save(env, monkeypatch):
    conn, state, _ = env

    def no_disk(*args, **kwargs):
        raise OSError("No space left on device")

    monkeypatch.setattr(attempt, "_save_pending", no_disk)
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert rep.artifact and any("could not save the result" in line for line in rep.lines)
    assert conn.execute("SELECT outcome FROM attempts WHERE id = ?", (rep.attempt_ids[-1],)).fetchone()[0] == "extended"


def test_recheck_error_is_retried_in_place(env, monkeypatch):
    conn, state, _ = env

    def flaky(known, first, new):
        state["recheck_calls"] += 1
        if state["recheck_calls"] == 1:
            raise urllib.error.URLError("connection reset")
        return True, "live entry ends at a(15)"

    monkeypatch.setattr(attempt, "recheck", flaky)
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert rep.artifact and state["recheck_calls"] == 2
    assert any("trying again" in line for line in rep.lines)


@pytest.mark.parametrize("verdict, outcome", [((True, "live entry ends at a(15)"), "extended"),
                                              ((False, "live entry already has 5 of the new terms"), "superseded")])
def test_unreachable_recheck_keeps_the_win_pending(env, verdict, outcome):
    conn, state, tmp = env
    state["recheck"] = urllib.error.URLError("no route to host")
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    attempt_id = rep.attempt_ids[-1]
    assert rep.artifact is None and state["recheck_calls"] == 1 + len(attempt.RECHECK_RETRY_WAITS_S)
    row = conn.execute("SELECT outcome, new_terms, extra FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    assert (row["outcome"], row["new_terms"]) == ("recheck_pending", 5)
    assert json.loads(row["extra"])["recheck"].startswith("not done: URLError")
    assert attempt.pending_path(attempt_id).is_file() and db.open_review(conn, "A999999") is None

    # while pending, the sequence is neither attempted again nor picked
    assert attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None).skipped == "recheck_pending"
    db.upsert_sequences(conn, [db.SequenceRow("A999999", "The primes.", 1, "nonn,more", 15, 2, "pari", 0, False)])
    assert [c.a_number for c in select.candidates(conn)] == []

    # still unreachable: stays pending
    assert attempt.retry_pending_rechecks(conn, log=lambda m: None) == 1

    state["recheck"] = verdict
    assert attempt.retry_pending_rechecks(conn, log=lambda m: None) == 0
    row = conn.execute("SELECT outcome, artifact_path, extra FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    assert row["outcome"] == outcome and json.loads(row["extra"])["recheck"] == verdict[1]
    assert not attempt.pending_path(attempt_id).exists() and db.pending_rechecks(conn) == []
    review = db.open_review(conn, "A999999")
    if outcome == "extended":
        folder = tmp / "artifacts" / "A999999" / f"attempt-{attempt_id}"
        assert row["artifact_path"] and verdict[1] in (folder / "verification.md").read_text()
        assert (review["attempt_id"], review["first_new_index"], review["last_new_index"]) == (attempt_id, 16, 20)
    else:
        assert row["artifact_path"] is None and review is None
        assert [c.a_number for c in select.candidates(conn)] == ["A999999"]


def pending_win(conn, state) -> int:
    state["recheck"] = urllib.error.URLError("no route to host")
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert conn.execute("SELECT outcome FROM attempts WHERE id = ?", (rep.attempt_ids[-1],)).fetchone()[0] == "recheck_pending"
    return rep.attempt_ids[-1]


def test_interrupted_recheck_is_kept_and_resolved_later(env):
    conn, state, tmp = env
    state["recheck"] = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    (attempt_id, outcome, extra), = conn.execute("SELECT id, outcome, extra FROM attempts").fetchall()
    assert outcome == "recheck_pending" and json.loads(extra)["recheck"] == "not done yet"
    assert attempt.pending_path(attempt_id).is_file()

    state["recheck"] = (True, "live entry ends at a(15)")
    assert attempt.retry_pending_rechecks(conn, log=lambda m: None) == 0
    assert db.open_review(conn, "A999999")["attempt_id"] == attempt_id


def test_non_network_recheck_error_is_not_retried(env):
    conn, state, _ = env
    state["recheck"] = ValueError("max() arg is an empty sequence")
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert state["recheck_calls"] == 1 and rep.artifact is None
    extra = json.loads(conn.execute("SELECT extra FROM attempts WHERE id = ?", (rep.attempt_ids[-1],)).fetchone()[0])
    assert extra["recheck"] == "not done: ValueError: max() arg is an empty sequence"


def test_pending_retry_survives_broken_state_and_repeats_safely(env, monkeypatch):
    conn, state, tmp = env
    attempt_id = pending_win(conn, state)
    saved = attempt.pending_path(attempt_id).read_bytes()
    state["recheck"] = (True, "live entry ends at a(15)")
    folder = tmp / "artifacts" / "A999999" / f"attempt-{attempt_id}"
    lines: list[str] = []

    # an unloadable saved result: logged, still pending, and a session still runs
    attempt.pending_path(attempt_id).write_bytes(b"not a pickle")
    assert attempt.retry_pending_rechecks(conn, log=lines.append) == 1
    assert "UnpicklingError" in lines[-1]
    attempt.run_session(conn, 1, FAST, a_numbers=["A999999"], log=lambda m: None)
    assert db.pending_recheck(conn, "A999999")["id"] == attempt_id

    # a complete folder that is not this attempt's is never overwritten
    attempt.pending_path(attempt_id).write_bytes(saved)
    folder.mkdir(parents=True)
    (folder / "README.md").write_text("someone else's review")
    assert attempt.retry_pending_rechecks(conn, log=lines.append) == 1
    assert "FileExistsError" in lines[-1] and (folder / "README.md").read_text() == "someone else's review"

    # the database write fails after the folder was written: the folder keeps its marker...
    shutil.rmtree(folder)

    def locked(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    with monkeypatch.context() as m:
        m.setattr(db, "record_win", locked)
        assert attempt.retry_pending_rechecks(conn, log=lines.append) == 1
    assert "OperationalError" in lines[-1] and (folder / ".incomplete").exists()
    # ...so the next try replaces it
    assert attempt.retry_pending_rechecks(conn, log=lines.append) == 0
    assert not (folder / ".incomplete").exists() and "a(16)..a(20)" in (folder / "README.md").read_text()
    assert db.open_review(conn, "A999999")["attempt_id"] == attempt_id
