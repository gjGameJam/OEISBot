"""The orchestration path end to end, with oeisdata, b-files and the oeis.org re-check stubbed out."""
from __future__ import annotations

import json
import re
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


def make_entry(program: str | list[str], data: str = PRIMES, keywords: str = "nonn,more", comments=(),
               a_number: str = "A999999"):
    """One %o (PARI) block per program, in entry order."""
    lines = [f"%S {a_number} {data}", f"%N {a_number} The primes.", f"%O {a_number} 1,1", f"%K {a_number} {keywords}"]
    lines += [f"%C {a_number} {c}" for c in comments]
    lines += [f"%o {a_number} (PARI) {p}" for p in ([program] if isinstance(program, str) else program)]
    return parse("\n".join(lines) + "\n")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path / "artifacts")
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(bfile, "fetch", lambda a, refresh=False: None)
    monkeypatch.setattr(bfile, "cached", lambda a: (True, None))
    monkeypatch.setattr(attempt, "RECHECK_RETRY_WAITS_S", (0.0, 0.0))
    state = {"program": "a(n) = prime(n)", "data": PRIMES, "keywords": "nonn,more", "comments": (),
             "recheck": (True, "live entry ends at a(15)"), "recheck_calls": 0}

    def fake_recheck(known, first, new):
        state["recheck_calls"] += 1
        if isinstance(state["recheck"], BaseException):
            raise state["recheck"]
        return state["recheck"]

    monkeypatch.setattr(oeisdata, "load_entry",
                        lambda a: make_entry(state["program"], state["data"], state["keywords"], state["comments"]))
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
    assert any("failed the same way before (attempt #1: wrong_term)" in line for line in second.lines)


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


# reproduces the 15 known primes, then searches without ever finding a(16)
SEARCHES_FOREVER = "a(n) = if(n <= 15, prime(n), my(s = 0); while(1, s++))"
SEARCH_BRIEFLY = replace(FAST, extend_wall_s=2)


def test_a_used_up_extension_is_not_repeated_without_more_time(env, monkeypatch):
    conn, state, _ = env
    state["program"] = SEARCHES_FOREVER
    # a 2 s run spends a noticeable share of its wall time starting up; the CPU guard has its own test (test_db)
    monkeypatch.setattr(db, "EXTEND_DEAD_END_MIN_CPU_SHARE", 0.0)
    first = attempt.attempt_sequence(conn, "A999999", SEARCH_BRIEFLY, log=lambda m: None)
    assert rows(conn) == [("pari:a(n)", "verified", "extend_budget")], first.lines
    row = conn.execute("SELECT id, new_terms, extra FROM attempts").fetchone()
    assert row["new_terms"] == 0 and json.loads(row["extra"])["extend_wall_s"] == SEARCH_BRIEFLY.extend_wall_s

    with monkeypatch.context() as m:
        m.setattr(attempt, "run_attempt", lambda *a, **k: pytest.fail("a used-up extension was run again"))
        again = attempt.attempt_sequence(conn, "A999999", SEARCH_BRIEFLY, log=lambda m: None)
        shorter = attempt.attempt_sequence(conn, "A999999", replace(SEARCH_BRIEFLY, extend_wall_s=1),
                                           log=lambda m: None)
    assert again.skipped == shorter.skipped == "all_programs_dead_ends"
    assert f"verified before and found nothing new in no less time (attempt #{row['id']}: extend_budget)" \
        in "\n".join(again.lines)
    # the selection check agrees: out of a PARI-only pool at that budget, back in with more time or the model
    add_row(conn)
    names, keep = pool(conn, budgets=SEARCH_BRIEFLY)
    assert names == [] and keep.left_out == {"all_programs_dead_ends": 1}
    assert pool(conn, budgets=replace(SEARCH_BRIEFLY, extend_wall_s=3))[0] == ["A999999"]
    assert pool(conn, model=True, budgets=SEARCH_BRIEFLY)[0] == ["A999999"]
    # more time runs it again
    longer = attempt.attempt_sequence(conn, "A999999", replace(SEARCH_BRIEFLY, extend_wall_s=3), log=lambda m: None)
    assert longer.skipped is None
    assert rows(conn)[-1] == ("pari:a(n)", "verified", "extend_budget")


def test_a_used_up_extension_lets_the_entrys_next_program_run(env, monkeypatch):
    conn, state, _ = env
    # block 2 runs first (later blocks first); block 1 would find new terms, but a verified run ends the stage
    state["program"] = ["a(n) = prime(n)", SEARCHES_FOREVER]
    monkeypatch.setattr(db, "EXTEND_DEAD_END_MIN_CPU_SHARE", 0.0)
    attempt.attempt_sequence(conn, "A999999", SEARCH_BRIEFLY, log=lambda m: None)
    assert rows(conn) == [("pari:a(n)", "verified", "extend_budget")]
    # block 1 has not had its turn, so the sequence stays in a PARI-only pool at that budget
    add_row(conn)
    names, keep = pool(conn, budgets=SEARCH_BRIEFLY)
    assert names == ["A999999"] and not keep.left_out
    # a later attempt at that budget skips the used-up program and runs the next one, which wins
    again = attempt.attempt_sequence(conn, "A999999", SEARCH_BRIEFLY, log=lambda m: None)
    lines = "\n".join(again.lines)
    assert "A999999 %o (PARI) block 2: verified before and found nothing new in no less time" in lines
    assert "running pari:a(n) from A999999 %o (PARI) block 1" in lines
    assert rows(conn) == [("pari:a(n)", "verified", "extend_budget"), ("pari:a(n)", "extended", "max_new_terms")]
    assert again.artifact, again.lines


@pytest.mark.parametrize("failure_mode", ["infeasible", "extend_budget"])
def test_a_budget_dead_end_does_not_hold_back_the_others(env, failure_mode):
    conn, state, _ = env
    # block 2 is wrong at a(7), so only block 1 can win: every sibling, not just the next, gets its turn
    state["program"] = ["a(n) = prime(n)", "a(n) = prime(n) + (n == 7)", SEARCHES_FOREVER]
    entry = make_entry(state["program"])
    known = bfile.known_terms(entry, None)
    dead = pari.build_candidates(entry, known)[0][0].program       # block 3, first in run order
    with conn:
        conn.execute("""INSERT INTO attempts(a_number, strategy, program_sha, started_at, verified, known_terms,
                            new_terms, runtime_s, cpu_s, outcome, failure_mode, detail, extra)
                        VALUES ('A999999', ?, ?, ?, 1, ?, 0, 5.5, 5.4, 'verified', ?, 'nothing new', ?)""",
                     (dead.strategy, dead.sha, db.now(), known.count, failure_mode,
                      json.dumps({"extend_wall_s": FAST.extend_wall_s, "mem_bytes": FAST.mem_bytes})))
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    # the others run in order after the dead end: block 2 fails, block 1 wins
    origins = [r[0] for r in conn.execute("SELECT program_origin FROM attempts WHERE id > 1 ORDER BY id")]
    assert [o[-7:] for o in origins] == ["block 2", "block 1"] and rep.artifact, rep.lines
    assert rows(conn)[1:] == [("pari:a(n)", "failed", "wrong_term"), ("pari:a(n)", "extended", "max_new_terms")]


def test_a_program_broken_after_verifying_does_not_hold_back_the_others(env):
    conn, state, _ = env
    state["program"] = ["a(n) = prime(n)", "a(n) = if(n <= 15, prime(n), 0)"]
    entry = make_entry(state["program"])
    known = bfile.known_terms(entry, None)
    broken = pari.build_candidates(entry, known)[0][0].program      # block 2, first in run order
    assert broken.origin.endswith("block 2")
    with conn:      # it verified, then emitted a bad index: a deterministic dead end, not a budget one
        conn.execute("""INSERT INTO attempts(a_number, strategy, program_sha, started_at, verified, known_terms,
                            new_terms, outcome, failure_mode, detail)
                        VALUES ('A999999', ?, ?, ?, 1, ?, 0, 'verified', 'bad_index', 'program emitted n=17')""",
                     (broken.strategy, broken.sha, db.now(), known.count))
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert "A999999 %o (PARI) block 2: failed the same way before (attempt #1: bad_index)" in rep.lines
    assert rep.artifact, rep.lines                                 # block 1 ran and won


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
    call = json.loads(extra)["attempt_call"]

    state["recheck"] = (True, "live entry ends at a(15)")
    assert attempt.retry_pending_rechecks(conn, log=lambda m: None) == 0
    assert db.open_review(conn, "A999999")["attempt_id"] == attempt_id
    extra = json.loads(conn.execute("SELECT extra FROM attempts WHERE id = ?", (attempt_id,)).fetchone()[0])
    assert extra["attempt_call"] == call and extra["recheck"] == "live entry ends at a(15)"   # the key survives


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


# ------------------------------------------------------------------ PARI plan, selection check, model after PARI

# verifies all 15 known terms, then errors on a(16): verified, no new terms (stop `finished`)
VERIFIES_ONLY = 'a(n) = if(n > 15, error("too slow"), prime(n))'
FAR_PREDICATE = "isok(k) = isprime(k)"
FAR_DATA = "2,3,1000000007"          # a predicate search to 1e9 cannot finish inside FAST's 30 s verify budget
PLAN = '{"approach": "brute_force", "reason": "trial division", "plan": "test each k"}'
PRIMES_PY = """```python
def terms(work):
    n, k = 1, 1
    while True:
        k += 1
        if all(k % d for d in range(2, int(k ** 0.5) + 1)):
            yield n, k
            n += 1
        work(1)
```"""


WRONG_START = PRIMES_PY.replace("n, k = 1, 1", "n, k = 0, 1")      # yields from n = 0: bad_index


class FakeModel:
    name = "fake-coder"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[list[dict]] = []

    def chat(self, messages, *, temperature=0.2, max_tokens=2048):
        self.calls.append([dict(m) for m in messages])
        return self.replies.pop(0)


class NoModel:
    """Fails the test if the model stage is reached."""
    name = "must-not-be-called"

    def chat(self, messages, **kwargs):
        raise AssertionError("the model stage ran")


def rows(conn):
    return [tuple(r) for r in conn.execute("SELECT strategy, outcome, failure_mode FROM attempts ORDER BY id")]


def test_out_of_reach_predicate_is_not_run(env, monkeypatch):
    conn, state, _ = env
    state["program"], state["data"] = FAR_PREDICATE, FAR_DATA
    monkeypatch.setattr(attempt, "run_attempt", lambda *a, **k: pytest.fail("an out-of-reach program was run"))
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert rep.skipped == "verify_out_of_reach"
    assert any(line.startswith("A999999 %o (PARI) block 1: not run: reaching a(3)") for line in rep.lines)
    assert rows(conn) == [("pari", "skipped", "verify_out_of_reach")]
    # the same program under a budget long enough for it is runnable again
    entry = make_entry(FAR_PREDICATE, FAR_DATA)
    plan = attempt.pari_plan(conn, entry, bfile.known_terms(entry, None), replace(FAST, verify_wall_s=1000))
    assert len(plan.runnable) == 1 and not plan.out_of_reach


def test_out_of_reach_predicate_still_goes_to_the_model(env):
    conn, state, _ = env
    state["program"], state["data"] = FAR_PREDICATE, FAR_DATA
    model = FakeModel(['{"approach": "skip", "reason": "needs a supercomputer"}'])
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None, model=model)
    assert len(model.calls) == 1 and rep.skipped == "model_skip"
    assert rows(conn) == [("python:model", "skipped", "model_skip")]


def test_a_verified_pari_program_stops_the_other_pari_programs(env):
    conn, state, _ = env
    # later blocks run first: block 2 verifies without new terms, so block 1 (which would win) must not run
    state["program"] = ["a(n) = prime(n)", VERIFIES_ONLY]
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert rows(conn) == [("pari:a(n)", "verified", "finished")] and rep.artifact is None


def test_model_tries_after_a_correct_but_unproductive_pari_program(env):
    conn, state, tmp = env
    # long comments push the context past its truncation limit: the note must survive it
    state["program"], state["comments"] = VERIFIES_ONLY, ["x" * 1300] * 8
    # the known terms (primes) strictly increase, so the model is also asked the form: it says function
    model = FakeModel([PLAN, '{"form": "function"}', WRONG_START, PRIMES_PY])   # the 2nd generation wins
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None, model=model)
    assert rep.artifact, rep.lines
    assert rows(conn) == [("pari:a(n)", "verified", "finished"), ("python:model", "failed", "bad_index"),
                          ("python:model", "extended", "max_new_terms")]
    pari_id = rep.attempt_ids[0]
    held = [29, 31, 37, 41, 43, 47]               # a(10)..a(15): held out from the model
    for call in model.calls:                      # classify, generate and the retry all carry the note
        prompt = "\n".join(m["content"] for m in call if m["role"] == "user")
        assert "[truncated]" in prompt and "already reproduces all 15 known terms" in prompt
        assert re.search(rf"block 1, in \d+\.\d s, attempt #{pari_id}\)", prompt)
        assert "It may only cover the known range" in prompt       # it ended by itself (`finished`)
        assert not [v for v in held if re.search(rf"\b{v}\b", prompt)]
    readme = (tmp / "artifacts" / "A999999" / f"attempt-{rep.attempt_ids[-1]}" / "README.md").read_text()
    assert "Compare with the entry's program:" in readme and f"attempt #{pari_id}" in readme
    # the three rows are one attempt (the win recorded first as recheck_pending), so they share one key
    calls = {json.loads(e)["attempt_call"] for (e,) in conn.execute("SELECT extra FROM attempts")}
    assert len(calls) == 1 and len(calls.pop()) == 32


def test_the_failure_penalty_counts_an_attempt_once_however_many_programs_it_ran(env):
    conn, state, _ = env
    state["program"] = "a(n) = prime(n) + 1"             # wrong from a(1)
    add_row(conn)
    base = select.difficulty(conn.execute("SELECT * FROM sequences").fetchone())

    def penalty():
        [c] = select.candidates(conn)
        return c.difficulty / base

    def model():            # its program starts at the wrong index; the same program sent again is not run
        return FakeModel([PLAN, '{"form": "function"}', WRONG_START, WRONG_START, WRONG_START])

    attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None, model=model())
    assert rows(conn) == [("pari:a(n)", "failed", "wrong_term"), ("python:model", "failed", "bad_index")]
    assert penalty() == 2                                # two rows, one attempt
    # a second attempt: the PARI program is a dead end now, and the model fails again
    attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None, model=model())
    assert rows(conn)[2:] == [("python:model", "failed", "bad_index")]
    calls = [json.loads(e)["attempt_call"] for (e,) in conn.execute("SELECT extra FROM attempts ORDER BY id")]
    assert calls[0] == calls[1] != calls[2]
    assert penalty() == 4                                # three rows would have made it 8


@pytest.mark.parametrize("failure_mode, detail, logged", [
    ("infeasible", "needs 9 days", "verified before and judged the next term infeasible with no less time and memory"),
    ("extend_budget", "extension budget 5 s used", "verified before and found nothing new in no less time"),
])
def test_model_is_told_about_a_verified_program_from_an_earlier_attempt(env, failure_mode, detail, logged):
    conn, state, _ = env
    entry = make_entry(state["program"])
    known = bfile.known_terms(entry, None)
    program = pari.build_candidates(entry, known)[0][0].program
    with conn:      # an earlier run verified every known term, then found nothing new: a dead end
        earlier = conn.execute("""INSERT INTO attempts(a_number, strategy, program_sha, started_at, verified,
                                      known_terms, new_terms, runtime_s, cpu_s, outcome, failure_mode, detail, extra)
                                  VALUES ('A999999', ?, ?, ?, 1, ?, 0, 5.5, 5.4, 'verified', ?, ?, ?)""",
                               (program.strategy, program.sha, db.now(), known.count, failure_mode, detail,
                                json.dumps({"extend_wall_s": FAST.extend_wall_s, "mem_bytes": FAST.mem_bytes}))).lastrowid
    model = FakeModel(['{"approach": "skip", "reason": "hopeless"}'])
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None, model=model)
    prompt = model.calls[0][-1]["content"]
    assert f"attempt #{earlier}) already reproduces all 15 known terms" in prompt
    assert f"{failure_mode}: {detail}" in prompt and "fundamentally faster" in prompt
    assert any(f"{logged} (attempt #{earlier}: {failure_mode})" in line for line in rep.lines)


@pytest.mark.parametrize("failure_mode, verified, new_terms, detail", [
    ("wrong_term", 0, 0, "a(12) = 38, known value 37"),            # a held-out value in the detail
    ("bad_index", 1, 2, "program emitted n=19, expected n=18"),    # verified, but it did find new terms
])
def test_only_a_verified_dead_end_without_new_terms_becomes_the_note(env, failure_mode, verified, new_terms, detail):
    conn, state, _ = env
    entry = make_entry(state["program"])
    known = bfile.known_terms(entry, None)
    program = pari.build_candidates(entry, known)[0][0].program
    with conn:
        conn.execute("""INSERT INTO attempts(a_number, strategy, program_sha, started_at, verified, known_terms,
                            new_terms, outcome, failure_mode, detail)
                        VALUES ('A999999', ?, ?, ?, ?, ?, ?, 'failed', ?, ?)""",
                     (program.strategy, program.sha, db.now(), verified, known.count, new_terms, failure_mode, detail))
    model = FakeModel(['{"approach": "skip", "reason": "hopeless"}'])
    attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None, model=model)
    prompt = model.calls[0][-1]["content"]
    assert "already reproduces" not in prompt and detail not in prompt and not re.search(r"\b37\b", prompt)


def test_an_empty_bfile_falls_back_to_data(env, monkeypatch):
    conn, state, _ = env
    monkeypatch.setattr(bfile, "fetch", lambda a, refresh=False: bfile.BFile(a, {}, malformed=["garbage"]))
    add_row(conn)
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert rep.artifact and "15 terms from data" in rep.lines[0]
    row = conn.execute("SELECT bfile_status, bfile_terms FROM sequences WHERE a_number = 'A999999'").fetchone()
    assert tuple(row) == ("present", 0)


def test_a_failed_pari_run_lets_the_next_one_run_and_is_not_called_verified(env):
    conn, state, _ = env
    state["program"] = ["a(n) = prime(n)", "a(n) = prime(n) + (n == 7)"]     # the wrong one runs first
    model = NoModel()                                                        # a win keeps the model away
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None, model=model)
    assert rows(conn) == [("pari:a(n)", "failed", "wrong_term"), ("pari:a(n)", "extended", "max_new_terms")]
    assert rep.artifact


def test_a_win_stops_the_other_pari_programs(env):
    conn, state, _ = env
    state["program"] = ["a(n) = prime(n)", "a(n) = 0 + prime(n)"]      # two different programs that both win
    attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)
    assert rows(conn) == [("pari:a(n)", "extended", "max_new_terms")]


def test_a_verified_pari_run_with_too_few_terms_for_the_model(env):
    conn, state, _ = env
    state["program"], state["data"] = 'a(n) = if(n > 2, error("too slow"), prime(n))', "2,3"
    model = FakeModel([])
    rep = attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None, model=model)
    assert model.calls == [] and rep.skipped == "too_few_known_terms"
    assert rows(conn) == [("pari:a(n)", "verified", "finished"), ("python:model", "skipped", "too_few_known_terms")]


@pytest.mark.parametrize("verdict", [(True, "live entry ends at a(15)"),
                                     (False, "live entry already has 5 of the new terms"),
                                     urllib.error.URLError("no route to host")])
def test_new_terms_from_pari_keep_the_model_away_whatever_the_recheck_says(env, verdict):
    conn, state, _ = env
    state["recheck"] = verdict
    attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None, model=NoModel())
    assert [r[0] for r in rows(conn)] == ["pari:a(n)"]


def test_plan_checks_dead_ends_first_and_names_the_reason(env):
    conn, _, _ = env
    entry = make_entry(FAR_PREDICATE, FAR_DATA)
    known = bfile.known_terms(entry, None)
    cand = pari.build_candidates(entry, known)[0][0]
    assert attempt.pari_plan(conn, entry, known, FAST).out_of_reach          # out of reach, no history yet
    with conn:      # the same program also crashed before: it is reported as the dead end it is
        conn.execute("""INSERT INTO attempts(a_number, strategy, program_sha, started_at, known_terms, outcome,
                            failure_mode) VALUES ('A999999', ?, ?, ?, ?, 'failed', 'crash')""",
                     (cand.program.strategy, cand.program.sha, db.now(), known.count))
    plan = attempt.pari_plan(conn, entry, known, FAST)
    assert len(plan.dead_ends) == 1 and not plan.out_of_reach and not plan.runnable
    plan_of = lambda dead, far: attempt.PariPlan([], [], [(cand, None)] * dead, [(cand, "far")] * far)
    assert plan_of(0, 0).nothing_to_run()[0] == "no_supported_program"
    assert plan_of(0, 1).nothing_to_run() == ("verify_out_of_reach", "far")
    assert plan_of(1, 0).nothing_to_run()[0] == "all_programs_dead_ends"
    reason, detail = plan_of(1, 1).nothing_to_run()
    assert reason == "all_programs_dead_ends" and "1 more out of reach" in detail


# ------------------------------------------------------------------ the selection check (attempt.Runnable)

def add_row(conn, a="A999999", langs="pari", terms=15):
    db.upsert_sequences(conn, [db.SequenceRow(a, "The primes.", 1, "nonn,more", terms, 2, langs, 0, False)])
    db.update_bfile_info(conn, a, "absent")


def pool(conn, model=False, budgets=FAST):
    keep = attempt.Runnable(conn, budgets, model)
    return [c.a_number for c in select.candidates(conn, require_langs=None if model else {"pari"}, keep=keep)], keep


@pytest.mark.parametrize("program, data, reason", [
    ('lista(nn) = for(n=1, nn, if(isprime(n), print1(n, ", ")))', PRIMES, "no_supported_program"),
    # a helper that lives in another OEIS entry: gp would run this, error and exit 0
    ("a(n) = A007947(n)", PRIMES, "no_supported_program"),
    (FAR_PREDICATE, FAR_DATA, "verify_out_of_reach"),
])
def test_selection_leaves_out_what_could_only_be_skipped(env, program, data, reason):
    conn, state, _ = env
    state["program"], state["data"] = program, data
    add_row(conn)
    names, keep = pool(conn)
    assert names == [] and keep.left_out == {reason: 1} and reason in keep.summary()
    # with the model on, the model can still take it (at least 3 known terms)
    assert pool(conn, model=True)[0] == ["A999999"]
    # and attempting it anyway records exactly the reason the check predicted
    assert attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None).skipped == reason


def test_selection_leaves_out_dead_ends_until_a_bigger_budget(env):
    conn, state, _ = env
    state["program"] = "a(n) = prime(n) + (n == 7)"
    add_row(conn)
    assert pool(conn)[0] == ["A999999"]
    attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None)       # wrong_term: a dead end
    names, keep = pool(conn)
    assert names == [] and keep.left_out == {"all_programs_dead_ends": 1}


def test_selection_check_uses_the_cached_bfile(env, monkeypatch):
    conn, state, _ = env
    state["program"], state["data"] = FAR_PREDICATE, "2,3,5"
    add_row(conn)
    assert pool(conn)[0] == ["A999999"]                                  # DATA alone: in reach
    far = {1: 2, 2: 3, 3: 5, 4: 1000000007}                              # the b-file goes much further
    monkeypatch.setattr(bfile, "cached", lambda a: (True, bfile.BFile(a, far)))
    names, keep = pool(conn)
    assert names == [] and keep.left_out == {"verify_out_of_reach": 1}


def broken_pointer(a):
    raise KeyError("oid")          # what a malformed LFS pointer file raises


@pytest.mark.parametrize("breakage, gate", [
    ("bfile not cached", None),                                # the attempt's lookup downloads it
    ("bfile check raises", "bfile_error"),
    ("entry missing", "not_in_oeisdata"),
    ("inconsistent terms", "inconsistent_known_terms"),
])
def test_selection_keeps_what_the_attempt_gates_decide(env, monkeypatch, breakage, gate):
    conn, state, _ = env
    state["program"] = "lista(nn) = 0"            # would be left out if the check could run
    add_row(conn)
    if breakage == "bfile not cached":
        monkeypatch.setattr(bfile, "cached", lambda a: (False, None))
    elif breakage == "bfile check raises":
        monkeypatch.setattr(bfile, "cached", broken_pointer)
        monkeypatch.setattr(bfile, "fetch", lambda a, refresh=False: broken_pointer(a))
    elif breakage == "entry missing":
        monkeypatch.setattr(oeisdata, "load_entry", lambda a: None)
    else:
        bad = bfile.BFile("A999999", {1: 2, 2: 4})                                   # a(2) is 3
        monkeypatch.setattr(bfile, "cached", lambda a: (True, bad))
        monkeypatch.setattr(bfile, "fetch", lambda a, refresh=False: bad)
    names, keep = pool(conn)
    assert names == ["A999999"] and keep.undecided == 1 and "only an attempt can check" in keep.summary()
    if gate:                                      # ...and the attempt does record it as a skip
        assert attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None).skipped == gate


def test_selection_leaves_out_and_reports_what_would_stop_a_session(env, monkeypatch):
    conn, state, _ = env
    add_row(conn)
    monkeypatch.setattr(oeisdata, "load_entry", lambda a: 1 / 0)     # an attempt has no gate for this
    names, keep = pool(conn)
    assert names == [] and keep.errors == ["A999999: ZeroDivisionError: division by zero"]
    assert "whose check failed (first: A999999: ZeroDivisionError" in keep.summary()


def test_selection_with_the_model_names_the_skip_the_model_stage_records(env):
    conn, state, _ = env
    state["program"], state["data"] = "lista(nn) = 0", "2,3"           # nothing to run, 2 known terms
    add_row(conn, terms=2)
    names, keep = pool(conn, model=True)
    assert names == [] and keep.left_out == {"too_few_known_terms": 1}
    assert attempt.attempt_sequence(conn, "A999999", FAST, log=lambda m: None,
                                    model=NoModel()).skipped == "too_few_known_terms"


def test_session_checks_the_pool_with_its_own_budgets(env, monkeypatch):
    conn, state, _ = env
    # 8e8 calls: out of reach within FAST's 30 s, but not within the default 60 s
    calls = 800000011
    assert pari.PREDICATE_MAX_RATE * FAST.verify_wall_s < calls <= pari.PREDICATE_MAX_RATE * config.DEFAULT_BUDGETS.verify_wall_s
    state["program"], state["data"] = FAR_PREDICATE, f"2,3,{calls}"
    add_row(conn)
    lines: list[str] = []
    attempt.run_session(conn, 1, FAST, seed=1, log=lines.append)
    assert rows(conn) == [] and "1 verify_out_of_reach" in lines[0]


def test_queue_and_pick_show_the_session_pool(env, monkeypatch, capsys):
    from oeisbot import cli
    conn, state, _ = env
    state["program"] = "lista(nn) = 0"
    add_row(conn)
    monkeypatch.setattr(db, "connect", lambda *a, **k: conn)
    cli.main(["queue"])
    assert "0 candidates" in capsys.readouterr().out.splitlines()[0]
    cli.main(["queue", "--all"])                                   # the --model pool: the model can take it
    out = capsys.readouterr().out
    assert "1 candidates" in out.splitlines()[0] and "A999999" in out
    cli.main(["pick", "-k", "1"])
    assert "A999999" not in capsys.readouterr().out


def test_session_picks_only_runnable_sequences(env, monkeypatch):
    conn, state, _ = env
    entries = {"A999999": make_entry("a(n) = prime(n)"),
               "A999997": make_entry("lista(nn) = 0", a_number="A999997")}
    monkeypatch.setattr(oeisdata, "load_entry", lambda a: entries[a])
    add_row(conn, "A999999")
    add_row(conn, "A999997")
    lines: list[str] = []
    attempt.run_session(conn, 2, FAST, seed=1, log=lines.append)
    assert {r["a_number"] for r in conn.execute("SELECT a_number FROM attempts")} == {"A999999"}
    assert "picked 1 of 1 candidates" in lines[0] and "1 no_supported_program" in lines[0]
