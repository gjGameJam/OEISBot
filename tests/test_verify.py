"""The verification gate, end to end through the sandbox."""
from __future__ import annotations

import json
import textwrap
from dataclasses import replace

import pytest

from oeisbot import estimate, sandbox, verify
from oeisbot.config import Budgets
from oeisbot.sandbox import RunResult, Status
from oeisbot.terms import KnownTerms, Program
from oeisbot.verify import MAX_TERM_FIELD_DIGITS, Harness, Stop, run_attempt

pytestmark = [
    pytest.mark.sandbox,
    pytest.mark.skipif(bool(sandbox.runtime_problems()), reason="; ".join(sandbox.runtime_problems())),
]

FAST = Budgets(verify_wall_s=20, extend_wall_s=5, max_new_terms=5)


def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


FIB_KNOWN = KnownTerms("A000045", 0, {n: fib(n) for n in range(0, 31)}, "bfile")


def py(code: str) -> Program:
    return Program("python", textwrap.dedent(code), origin="test", strategy="python:test")


FIB_OK = py("""
    def terms(work):
        a, b, n = 0, 1, 0
        while True:
            yield n, a
            work(1)
            a, b, n = b, a + b, n + 1
""")


def test_correct_program_is_verified_and_extended(tmp_path):
    log = tmp_path / "terms.jsonl"
    r = run_attempt(FIB_OK, FIB_KNOWN, FAST, log_path=log)
    assert r.verified and r.outcome == "extended", (r.stop, r.detail)
    assert r.reproduced == 31
    assert r.stop is Stop.MAX_NEW_TERMS
    assert [(t.n, t.value) for t in r.new_terms] == [(n, fib(n)) for n in range(31, 36)]
    lines = [json.loads(l) for l in log.read_text().splitlines()]
    assert len(lines) == 36 and lines[-1]["value"] == str(fib(35))
    assert len(r.predictions) == 5   # one per new term; none for a term past max_new_terms


def test_verify_only_does_not_emit_new_terms():
    r = run_attempt(FIB_OK, FIB_KNOWN, FAST, extend=False)
    assert r.verified and r.outcome == "verified" and r.stop is Stop.VERIFIED_ONLY
    assert r.new_terms == []


def test_off_by_one_offset_is_caught():
    prog = py("""
        def terms(work):
            a, b, n = 1, 1, 1          # starts at F(1) labelled n=1: values right, offset wrong
            while True:
                yield n, a
                a, b, n = b, a + b, n + 1
    """)
    r = run_attempt(prog, FIB_KNOWN, FAST)
    assert not r.verified and r.stop is Stop.BAD_INDEX
    assert "expected n=0" in r.detail


def test_shifted_values_are_caught_as_wrong_terms():
    prog = py("""
        def terms(work):
            a, b, n = 1, 1, 0          # right indices, values shifted by one
            while True:
                yield n, a
                a, b, n = b, a + b, n + 1
    """)
    r = run_attempt(prog, FIB_KNOWN, FAST)
    assert r.stop is Stop.WRONG_TERM and r.detail.startswith("a(0) = 1, known value 0")


def test_wrong_late_term_is_caught_and_nothing_trusted():
    prog = py("""
        def terms(work):
            a, b, n = 0, 1, 0
            while True:
                yield n, (a if n != 29 else a + 1)
                a, b, n = b, a + b, n + 1
    """)
    r = run_attempt(prog, FIB_KNOWN, FAST)
    assert r.stop is Stop.WRONG_TERM and "a(29)" in r.detail
    assert r.outcome == "failed" and r.new_terms == []


def test_skipped_index_is_caught():
    prog = py("""
        def terms(work):
            a, b = 0, 1
            for n in range(100):
                if n != 7:
                    yield n, a
                a, b = b, a + b
    """)
    r = run_attempt(prog, FIB_KNOWN, FAST)
    assert r.stop is Stop.BAD_INDEX and "n=8, expected n=7" in r.detail


def test_crash_reports_the_error():
    prog = py("""
        def terms(work):
            yield 0, 0
            raise ZeroDivisionError("boom")
    """)
    r = run_attempt(prog, FIB_KNOWN, FAST)
    assert r.stop is Stop.CRASH and "ZeroDivisionError: boom" in r.detail


def test_non_integer_values_rejected():
    prog = py("""
        def terms(work):
            yield 0, 0.0
    """)
    r = run_attempt(prog, FIB_KNOWN, FAST)
    assert r.stop is Stop.CRASH and "TypeError" in r.detail


def test_program_that_ends_early_is_incomplete():
    prog = py("""
        def terms(work):
            a, b = 0, 1
            for n in range(10):
                yield n, a
                a, b = b, a + b
    """)
    r = run_attempt(prog, FIB_KNOWN, FAST)
    assert r.stop is Stop.INCOMPLETE and not r.verified
    assert r.detail == "program ended after 10 terms"      # it said nothing: there is nothing to add


def test_incomplete_keeps_what_the_program_said_on_stderr():
    prog = py("""
        import sys
        def terms(work):
            print("gave up: no way to compute this", file=sys.stderr)
            return
            yield
    """)
    r = run_attempt(prog, FIB_KNOWN, FAST)
    assert r.stop is Stop.INCOMPLETE and not r.verified
    assert r.detail.startswith("program ended after 0 terms: ")
    assert "gave up: no way to compute this" in r.detail


def test_the_last_known_term_cannot_verify_a_run_that_missed_one():
    """`on_line`'s guard at the last known index. Nothing can reach it: indices are consecutive and a
    value that differs halts before the term is appended, so every known index has matched by the time the
    last one arrives. The state is therefore built by hand. The guard is kept because without it such a
    run would set `verified_at`, spend its whole extension and end as `failed`."""
    known = KnownTerms("A000045", 0, {n: fib(n) for n in range(4)}, "data")
    h = Harness(py(""), known, FAST)
    for n in range(3):
        assert h.on_line(f"@T {n} {fib(n)} 0 0 0", 0.1 * n) is None
    h.reproduced = 0                       # the impossible state: known terms behind, none of them counted
    said = h.on_line(f"@T 3 {fib(3)} 0 0 0", 0.4)
    assert said == "incomplete: reproduced 1 of 4 known terms"
    assert h.stop is Stop.INCOMPLETE and h.verified_at is None


def test_an_over_long_counting_field_is_a_protocol_stop_not_a_crash():
    """`on_line` runs in the sandbox's stdout reader thread, which has no exception handler and holds the
    same lock as `on_tick`. An untrusted program can put anything in a term line -- py_runner hands the
    candidate module the same stdout, and verify.py:31 lifts Python's own digit limit -- so a field of a
    few hundred digits would raise OverflowError out of the float conversions a TermRecord needs, killing
    the drain thread, and one of a few hundred thousand would stall it in quadratic int(). Both are
    refused here, as a malformed line, before anything converts."""
    known = KnownTerms("A000045", 0, {n: fib(n) for n in range(4)}, "data")
    huge = "9" * 400
    for field, line in (("cpu_us", f"@T 0 {fib(0)} {huge} 0 0"),
                        ("work", f"@T 0 {fib(0)} 0 {huge} 0"),
                        ("mem", f"@T 0 {fib(0)} 0 0 {huge}"),
                        ("n", f"@T {huge} {fib(0)} 0 0 0")):
        h = Harness(py(""), known, FAST)
        said = h.on_line(line, 0.1)
        assert said is not None and said.startswith("protocol:"), field
        assert h.stop is Stop.PROTOCOL, field
        assert not h.records, field


def test_the_counting_field_cap_is_the_documented_one():
    """400 digits is over the float cliff at ~309, so the cases above would also be caught with no cap
    at all wherever a float conversion is reached. These two sit either side of MAX_TERM_FIELD_DIGITS
    and below that cliff, so only a real cap of exactly this size passes both."""
    known = KnownTerms("A000045", 0, {n: fib(n) for n in range(4)}, "data")
    over = "9" * (MAX_TERM_FIELD_DIGITS + 1)
    assert Harness(py(""), known, FAST).on_line(f"@T 0 {fib(0)} {over} 0 0", 0.1) == \
        f"protocol: malformed term line: {f'@T 0 {fib(0)} {over} 0 0'[:200]!r}"
    at = "9" * MAX_TERM_FIELD_DIGITS
    h = Harness(py(""), known, FAST)
    assert h.on_line(f"@T 0 {fib(0)} {at} 0 0", 0.1) is None
    assert h.reproduced == 1


def test_a_huge_term_value_is_still_a_term():
    """The cap is per field and deliberately exempts the value: OEIS terms are legitimately unbounded,
    which is the whole reason verify.py:31 lifts Python's limit. Capping it would refuse real sequences."""
    big = 10 ** 5000
    known = KnownTerms("A999999", 0, {0: big}, "data")
    h = Harness(py(""), known, FAST)
    assert h.on_line(f"@T 0 {big} 0 0 0", 0.1) is None
    assert h.reproduced == 1 and h.records[0].value == big


def test_a_gp_program_that_errors_but_exits_cleanly_says_why():
    """gp prints its error, skips the rest of the file and exits 0, so the run is `incomplete` rather than
    a crash and the stderr tail is the only thing that says why no term came out. The caret rule gp puts
    under the offending call is dropped, or it would push out the line naming the call."""
    prog = Program("gp", "print(oeisbot_nowhere(3))\n", origin="test", strategy="gp:test")
    r = run_attempt(prog, FIB_KNOWN, FAST)
    assert r.stop is Stop.INCOMPLETE and not r.verified and r.run.exit_code == 0
    assert "not a function" in r.detail and "oeisbot_nowhere" in r.detail


def ended(stderr: str, *, status: Status = Status.EXITED, exit_code: int = 0) -> RunResult:
    """A finished sandbox run, for driving Harness._result in memory."""
    return RunResult(status, exit_code=exit_code, wall_s=1.0, cpu_s=1.0, peak_mem_bytes=0, mem_cap_bytes=0,
                     stderr_tail=stderr)


def test_stderr_tail_keeps_the_last_three_lines_that_say_something():
    # gp's shape: the call, a caret rule under it, the reason, then the file it gave up on. Keeping the
    # rule would cost the line that names the call, which is the one worth reading
    res = ended("  ***   at top-level: print(A007947(3))\n"
                "  ***                       ^------------------\n"
                "  ***   not a function in function call\n"
                "\n"
                "... skipping file 'program.gp'\n")
    assert verify._stderr_tail(res) == ("***   at top-level: print(A007947(3)) | "
                                        "***   not a function in function call | "
                                        "... skipping file 'program.gp'")
    assert verify._stderr_tail(res, lines=1) == "... skipping file 'program.gp'"
    assert verify._stderr_tail(ended("\n  ^^^^\n  ----\n")) == ""     # nothing but rules: nothing to say


def test_a_stderr_line_is_capped():
    """A program can write 64 KiB of stderr without a single line break; a detail is not the place for it."""
    r = Harness(FIB_OK, FIB_KNOWN, FAST)._result(ended("x" * 70_000), None)
    assert r.detail == "program ended after 0 terms: " + "x" * verify.STDERR_LINE_CHARS


def test_brief_detail_cuts_a_long_detail_to_one_line():
    assert verify.brief_detail("a" * verify.CONSOLE_DETAIL_CHARS) == "a" * verify.CONSOLE_DETAIL_CHARS
    cut = verify.brief_detail("a" * (verify.CONSOLE_DETAIL_CHARS + 1))
    assert len(cut) == verify.CONSOLE_DETAIL_CHARS and cut.endswith("...")


def test_a_non_zero_exit_is_a_crash_carrying_the_stderr_tail():
    """The `crash` detail keeps the shape it has always had, including the bare `: ` when a program that
    failed said nothing at all."""
    h = Harness(FIB_OK, FIB_KNOWN, FAST)
    r = h._result(ended("Traceback (most recent call last):\n  File x, line 1\n    ^^^^\nBoom: 3\n",
                        exit_code=1), None)
    assert r.stop is Stop.CRASH
    assert r.detail == "exit code 1: Traceback (most recent call last): | File x, line 1 | Boom: 3"
    assert Harness(FIB_OK, FIB_KNOWN, FAST)._result(ended("", exit_code=2), None).detail == "exit code 2: "


def test_a_stop_without_a_single_term_keeps_the_stderr_tail():
    h = Harness(FIB_OK, FIB_KNOWN, FAST)
    h._halt(Stop.VERIFY_TIMEOUT, f"reproduced 0 of {FIB_KNOWN.count} known terms within 20 s")
    r = h._result(ended("*** the PARI stack overflows !\n"), None)
    assert r.stop is Stop.VERIFY_TIMEOUT
    assert r.detail == (f"reproduced 0 of {FIB_KNOWN.count} known terms within 20 s: "
                        "*** the PARI stack overflows !")


def test_stderr_is_not_added_to_a_run_that_produced_terms():
    """After a term has arrived the terms are the evidence, whether or not the stop is in _TAIL_STOPS:
    a stop outside the list never collects a tail, and one inside it collects a tail only with no terms."""
    h = Harness(FIB_OK, FIB_KNOWN, FAST, extend=False)
    for n in range(31):
        h.on_line(f"@T {n} {fib(n)} {n * 1000} {n} 8000000", n * 0.01)
    r = h._result(ended("*** noise the program wrote on its way out\n"), None)
    assert r.stop is Stop.VERIFIED_ONLY and r.verified and "noise" not in r.detail

    slow = Harness(FIB_OK, FIB_KNOWN, FAST)
    for n in range(5):
        slow.on_line(f"@T {n} {fib(n)} {n * 1000} {n} 8000000", n * 0.01)
    slow._halt(Stop.VERIFY_TIMEOUT, f"reproduced 5 of {FIB_KNOWN.count} known terms within 20 s")
    r = slow._result(ended("*** noise the program wrote while it ran\n"), None)
    assert r.stop is Stop.VERIFY_TIMEOUT and r.detail.endswith("within 20 s")


def test_slow_verification_times_out():
    prog = py("""
        import time
        def terms(work):
            a, b, n = 0, 1, 0
            while True:
                time.sleep(0.2)
                yield n, a
                a, b, n = b, a + b, n + 1
    """)
    r = run_attempt(prog, FIB_KNOWN, replace(FAST, verify_wall_s=2))
    assert r.stop is Stop.VERIFY_TIMEOUT and not r.verified


def test_gmpy2_values_accepted():
    prog = py("""
        import gmpy2
        def terms(work):
            n = 0
            while True:
                yield n, gmpy2.fib(n)
                n += 1
    """)
    r = run_attempt(prog, FIB_KNOWN, FAST)
    assert r.verified, (r.stop, r.detail)


# a sequence whose per-term work doubles: a(n) = number of subsets of {1..n} = 2^n, counted by brute force
DOUBLING = py("""
    def terms(work):
        n = 0
        while True:
            count = 0
            for _ in range(2 ** n):
                count += 1
            work(2 ** n)
            yield n, count
            n += 1
""")
POW2_KNOWN = KnownTerms("A000079", 0, {n: 2 ** n for n in range(0, 19)}, "bfile")


def test_infeasible_stop_ends_the_sandboxed_run():
    # the real program with no extension time: a(19)'s projection (about 17 ms here) is over the budget whatever the
    # timing, since every fitted term took some time, and the decision comes in the callback that verifies a(18), so
    # no tick comes between. The whole extension, stopping after new terms, is tested in memory with controlled times
    # (test_estimate.py::test_extension_stops_when_next_term_is_projected_infeasible): real millisecond timings stall
    # by up to 0.4 s on this machine, which made that test flaky when it ran here
    r = run_attempt(DOUBLING, POW2_KNOWN, Budgets(verify_wall_s=60, extend_wall_s=0, max_new_terms=50))
    assert r.verified and r.stop is Stop.INFEASIBLE, (r.stop, r.detail)
    assert "exceeds remaining budget 0 s" in r.detail
    # nothing past the known terms recorded, and the sandbox ended the run on the harness's stop (left alone, the
    # program never ends, and the harness's next tick would stop it as extend_budget). How soon the kill comes is
    # test_sandbox.py::test_on_tick_can_stop's to check
    assert r.records[-1].n == 18 and r.new_terms == [] and r.outcome == "verified"
    assert r.run.status is sandbox.Status.STOPPED and r.run.stop_reason.startswith("infeasible:")
    [p] = r.predictions
    assert p.n == 19 and not p.feasible and p.actual_s is None and p.censored_s is None


def test_term_far_over_prediction_is_killed(monkeypatch):
    monkeypatch.setattr(estimate, "MIN_GRACE_S", 1.0)
    prog = py("""
        import time
        def terms(work):
            n = 0
            while True:
                count = 0
                for _ in range(2 ** n):
                    count += 1
                work(2 ** n)
                if n == 19:
                    time.sleep(60)      # the new term suddenly costs far more than projected
                yield n, count
                n += 1
    """)
    r = run_attempt(prog, POW2_KNOWN, Budgets(verify_wall_s=60, extend_wall_s=120, max_new_terms=50))
    assert r.verified and r.stop is Stop.OVER_PREDICTION, (r.stop, r.detail)
    assert r.run.wall_s < 30
    assert r.predictions[-1].n == 19 and r.predictions[-1].censored_s >= 1.0
    assert r.predictions[-1].trustworthy       # only a trustworthy projection kills


def test_untrustworthy_projection_does_not_kill_the_term(monkeypatch):
    monkeypatch.setattr(estimate, "MIN_GRACE_S", 1.0)
    # only the last three known terms report enough work to be fitted, so the first new term's projection
    # rests on three points: never trustworthy, however well they agree
    prog = py("""
        import time
        def terms(work):
            n = 0
            while True:
                if n >= 16:
                    time.sleep(4 if n == 19 else 0.02)   # the first new term takes far longer than projected
                    work(100 * 2 ** (n - 16))
                yield n, 2 ** n
                n += 1
    """)
    r = run_attempt(prog, POW2_KNOWN, Budgets(verify_wall_s=60, extend_wall_s=30, max_new_terms=1))
    assert r.verified and r.stop is Stop.MAX_NEW_TERMS, (r.stop, r.detail)
    assert [(t.n, t.value) for t in r.new_terms] == [(19, 2 ** 19)]
    [p] = r.predictions
    assert p.n == 19 and p.unit == "work" and not p.trustworthy and p.feasible and not p.value_dependent
    # the rule before 2026-09-18 would have killed a(19) partway through
    assert p.seconds_high is not None and max(estimate.MIN_GRACE_S, 2 * p.seconds_high) < p.actual_s


def test_climbing_seconds_per_unit_does_not_kill_the_term(monkeypatch):
    monkeypatch.setattr(estimate, "MIN_GRACE_S", 1.0)
    # the same work every term, so the cost fit is flat and trustworthy, but from n = 14 each term takes 3x
    # longer than the one before (like a primality test on a growing number), and a(19) takes 4 s
    prog = py("""
        import time
        def terms(work):
            n = 0
            while True:
                if n >= 14:
                    time.sleep(4 if n == 19 else 0.01 * 3 ** (n - 14))
                work(1000)
                yield n, 2 ** n
                n += 1
    """)
    r = run_attempt(prog, POW2_KNOWN, Budgets(verify_wall_s=60, extend_wall_s=30, max_new_terms=1))
    assert r.verified and r.stop is Stop.MAX_NEW_TERMS, (r.stop, r.detail)
    assert [(t.n, t.value) for t in r.new_terms] == [(19, 2 ** 19)]
    [p] = r.predictions
    assert p.n == 19 and p.unit == "work" and not p.trustworthy and p.feasible and not p.value_dependent
    assert "not trusted to kill" in p.reasons[-1]           # so the cost fit itself was trustworthy
    # the rule before offer A would have killed a(19) partway through
    assert p.seconds_high is not None and max(estimate.MIN_GRACE_S, 2 * p.seconds_high) < p.actual_s


def test_gp_program_verified():
    script = textwrap.dedent("""
        a(n) = fibonacci(n);
        for(n = 0, +oo, my(v = a(n)); print("@T ", n, " ", v, " ", getabstime() * 1000, " 0 ", default(parisize)));
    """)
    prog = Program("gp", "a(n) = fibonacci(n)", origin="test", strategy="pari:a(n)", script=script)
    r = run_attempt(prog, FIB_KNOWN, FAST)
    assert r.verified and r.outcome == "extended", (r.stop, r.detail, r.run.stderr_tail)
    assert [(t.n, t.value) for t in r.new_terms] == [(n, fib(n)) for n in range(31, 36)]


def test_a_callback_error_is_its_own_stop_outside_every_dead_end_and_tail_rule():
    """Item 51: the sandbox reports our own `on_line`/`on_tick` raising as `Status.CALLBACK_ERROR`, and
    the harness records it as `harness_error` -- a stop that is not the program's failure, so it is not
    in `db.DETERMINISTIC_FAILURES`, and whose detail is the sandbox's reason (it names the exception),
    so no stderr tail is appended to it."""
    from oeisbot import db
    assert verify._STATUS_TO_STOP[Status.CALLBACK_ERROR] is Stop.HARNESS_ERROR
    assert Stop.HARNESS_ERROR not in verify._TAIL_STOPS
    assert Stop.HARNESS_ERROR.value not in db.DETERMINISTIC_FAILURES
    known = KnownTerms("A000045", 0, {n: fib(n) for n in range(4)}, "data")
    h = Harness(py(""), known, FAST)
    res = h._result(RunResult(Status.CALLBACK_ERROR, None, 1.0, 0.5, 0, 6 << 30,
                              "on_line raised ZeroDivisionError: harness bug", [], "stderr noise\n"), None)
    assert res.stop is Stop.HARNESS_ERROR and res.detail == "on_line raised ZeroDivisionError: harness bug"
    assert res.outcome == "failed" and not res.verified


def test_gp_memory_is_judged_against_the_stack_ceiling_not_the_job_cap(tmp_path):
    """Item 51 (next step 6). The gp driver reports `default(parisize) + heap`, a PARI stack figure, while
    the job cap is enforced on the job's commit -- quantities ~800x apart -- so no gp run could ever be
    judged infeasible on memory (A277041 reached the job cap reporting 8 MiB throughout). The harness now
    compares the stack figure with the ceiling it launches gp with (`parisizemax`, 0.8 x the cap); a
    Python run, whose figure is its own process memory, keeps the job cap. Same term lines, same
    growth: the gp harness must stop strictly earlier."""
    known = KnownTerms("A000045", 0, {n: fib(n) for n in range(4)}, "data")
    budgets = Budgets(verify_wall_s=60, extend_wall_s=600, mem_bytes=6 << 30)
    gp = Harness(Program("gp", "a(n)=fibonacci(n)", origin="test", strategy="pari:a(n)"), known, budgets)
    assert gp.stack_cap == int(max(gp.mem_cap, 1 << 28) * 0.8) and gp.stack_cap < gp.mem_cap
    assert f"parisizemax={gp.stack_cap}" in gp.argv(tmp_path)      # the same ceiling gp is launched with
    py_run = Harness(py(""), known, budgets)
    assert py_run.stack_cap is None

    def halted_at(h: Harness) -> int:
        mem, n = 8_000_000, 0
        while h.stop is None and n < 200:
            h.on_line(f"@T {n} {fib(n)} {n * 1000} 0 {int(mem)}", 0.1 * (n + 1))
            mem *= 1.15                                     # the stack figure grows 15% a term
            n += 1
        assert h.stop is Stop.INFEASIBLE and h.infeasible_on == ["memory"], (h.stop, h.detail)
        return n

    n_gp, n_py = halted_at(gp), halted_at(py_run)
    assert n_gp < n_py
    assert gp.predictions[-1].mem_high > gp.stack_cap


# ------------------------------------------------------------------ interrupted (item 58)

def _fed(h: Harness, upto: int) -> Harness:
    for n in range(upto):
        h.on_line(f"@T {n} {fib(n)} {n * 1000} {n} 8000000", n * 0.01)
    return h


def test_a_stop_request_ends_the_run_as_interrupted_in_either_phase():
    """Item 58, driven in memory: `should_stop` is asked on every tick. Before verification the run is a
    `failed` row, after it a `verified` one -- and in both the stop is `interrupted`, which no dead-end
    rule matches."""
    stop = {"now": False}
    h = _fed(Harness(FIB_OK, FIB_KNOWN, FAST, should_stop=lambda: stop["now"]), 5)
    assert h.on_tick(1.0) is None                                   # not asked to stop: nothing happens
    stop["now"] = True
    assert h.on_tick(2.0).startswith("interrupted: stopped on request 2.0 s into the run, during verification")
    r = h._result(RunResult(Status.STOPPED, 1, 2.1, 2.0, 0, 6 << 30, "stop", [], "noise on stderr\n"), None)
    assert (r.stop, r.outcome, r.verified) == (Stop.INTERRUPTED, "failed", False)
    assert "noise" not in r.detail and Stop.INTERRUPTED not in verify._TAIL_STOPS

    stop["now"] = False
    h = _fed(Harness(FIB_OK, FIB_KNOWN, replace(FAST, extend_wall_s=1000), should_stop=lambda: stop["now"]), 31)
    assert h.verified_at is not None and h.on_tick(1.0) is None
    stop["now"] = True
    assert "during the extension" in h.on_tick(3.0)
    r = h._result(RunResult(Status.STOPPED, 1, 3.1, 3.0, 0, 6 << 30, "stop"), None)
    assert (r.stop, r.outcome, r.verified, r.new_terms) == (Stop.INTERRUPTED, "verified", True, [])


def test_a_stop_request_wins_over_a_budget_that_ran_out_on_the_same_tick():
    """The order inside `on_tick` is the safety property. A run that is both interrupted and past a
    budget must be recorded as the stop that retires nothing: it may be past the budget only because
    the machine slept, which is exactly when a stop is asked for."""
    h = _fed(Harness(FIB_OK, FIB_KNOWN, FAST, should_stop=lambda: True), 5)
    assert h.on_tick(FAST.verify_wall_s + 100).startswith("interrupted")          # not verify_timeout
    assert h.stop is Stop.INTERRUPTED
    h = _fed(Harness(FIB_OK, FIB_KNOWN, replace(FAST, extend_wall_s=1000), should_stop=lambda: True), 31)
    assert h.on_tick(h.verified_at + 5000).startswith("interrupted")              # not extend_budget
    assert h.stop is Stop.INTERRUPTED
    # and without a request the budgets act exactly as before
    h = _fed(Harness(FIB_OK, FIB_KNOWN, FAST, should_stop=lambda: False), 5)
    assert h.on_tick(FAST.verify_wall_s + 100).startswith("verify_timeout")
    h = _fed(Harness(FIB_OK, FIB_KNOWN, FAST), 5)                                 # the default: no callback
    assert h.should_stop is None and h.on_tick(FAST.verify_wall_s + 100).startswith("verify_timeout")
    # any true answer is a request, not only the object True
    h = _fed(Harness(FIB_OK, FIB_KNOWN, FAST, should_stop=lambda: "the window closed"), 5)
    assert h.on_tick(1.0).startswith("interrupted") and h.stop is Stop.INTERRUPTED


def test_no_line_is_read_after_the_harness_has_halted():
    """The sandbox ends the job only after the halting callback has returned, so the reader thread can
    hand over one more line. Reading it let a run that was stopped during verification be recorded as
    verified -- its last known term arriving a moment after the halt -- with a detail saying otherwise."""
    h = _fed(Harness(FIB_OK, FIB_KNOWN, FAST, should_stop=lambda: True), 30)      # one known term short
    assert h.on_tick(1.0).startswith("interrupted")
    assert h.on_line(f"@T 30 {fib(30)} 30000 30 8000000", 1.01) is None           # the last known term, too late
    assert h.on_line(f"@T 31 {fib(31)} 31000 31 8000000", 1.02) is None
    r = h._result(RunResult(Status.STOPPED, 1, 1.1, 1.0, 0, 6 << 30, "stop"), None)
    assert (r.stop, r.outcome, r.verified, r.reproduced, len(r.records)) == (Stop.INTERRUPTED, "failed", False, 30, 30)
    assert h.verified_at is None and not h.predictions
    # the same for a budget stop: a late line cannot turn a verify_timeout into a verified row
    h = _fed(Harness(FIB_OK, FIB_KNOWN, FAST), 30)
    assert h.on_tick(FAST.verify_wall_s + 1).startswith("verify_timeout")
    h.on_line(f"@T 30 {fib(30)} 30000 30 8000000", FAST.verify_wall_s + 1.01)
    r = h._result(RunResult(Status.STOPPED, 1, 21.1, 21.0, 0, 6 << 30, "stop"), None)
    assert (r.stop, r.verified, r.reproduced) == (Stop.VERIFY_TIMEOUT, False, 30)
    # One line is still acted on after a halt: the driver's contract error, which can only take terms away
    h = _fed(Harness(FIB_OK, FIB_KNOWN, replace(FAST, extend_wall_s=1000)), 32)   # verified, one new term
    assert h.on_tick(h.verified_at + 2000).startswith("extend_budget")
    assert h.on_line("@ERR some other error", 9.0) is None and h.records[-1].kind == "new"
    assert h.on_line(f"@ERR {verify.CONTRACT_ERROR}: members out of order", 9.1) is None
    assert [r.kind for r in h.records[-2:]] == ["known", "void"]
    r = h._result(RunResult(Status.STOPPED, 1, 9.2, 9.0, 0, 6 << 30, "stop"), None)
    assert (r.stop, r.outcome, r.new_terms) == (Stop.EXTEND_BUDGET, "verified", [])   # the stop stands; no term does
    # and a wrong term is final too: nothing after it is counted
    h = _fed(Harness(FIB_OK, FIB_KNOWN, FAST), 5)
    assert h.on_line("@T 5 999 5000 5 8000000", 0.05).startswith("wrong_term")
    assert h.on_line(f"@T 5 {fib(5)} 5000 5 8000000", 0.06) is None and h.reproduced == 5


def test_a_first_stop_is_not_overwritten_by_a_later_request():
    """`_halt` keeps the first stop. A wrong term followed by a stop request is still a wrong term: the
    program's own failure was established before anyone asked, and it must retire the program."""
    stop = {"now": False}
    h = _fed(Harness(FIB_OK, FIB_KNOWN, FAST, should_stop=lambda: stop["now"]), 5)
    assert h.on_line("@T 5 999 5000 5 8000000", 0.05).startswith("wrong_term")
    stop["now"] = True
    h.on_tick(1.0)
    assert h.stop is Stop.WRONG_TERM


def test_a_real_run_is_interrupted_through_the_sandbox(monkeypatch):
    """End to end: the request reaches a running program through the sandbox's tick, the job is ended,
    and the terms that arrived first are kept as what they were."""
    prog = py("""
        import time
        def terms(work):
            a, b, n = 0, 1, 0
            while True:
                if n > 30:
                    time.sleep(60)          # verified, then nothing new for a long time
                yield n, a
                a, b, n = b, a + b, n + 1
    """)
    r = run_attempt(prog, FIB_KNOWN, replace(FAST, extend_wall_s=120), should_stop=_once_verified(monkeypatch))
    assert (r.stop, r.outcome, r.verified, r.reproduced) == (Stop.INTERRUPTED, "verified", True, 31)
    assert r.run.status is Status.STOPPED and r.run.wall_s < 60, r.run


def _once_verified(monkeypatch):
    """A `should_stop` that is true once the run in hand has reproduced every known term."""
    state = {"harness": None}
    real = Harness.on_line

    def spy(self, line, t):
        state["harness"] = self
        return real(self, line, t)

    monkeypatch.setattr(Harness, "on_line", spy)
    return lambda: state["harness"] is not None and state["harness"].verified_at is not None


def test_a_should_stop_that_raises_in_a_run_is_a_harness_error(monkeypatch):
    """The sandbox guards its callbacks: a raising `should_stop` ends the job and is recorded as our own
    fault, never the program's -- outside every dead-end rule. (It is still a `failed` row, so it does
    count in the failure penalty; `attempt_sequence` says so.)"""
    from oeisbot import db
    armed = _once_verified(monkeypatch)
    prog = py("""
        import time
        def terms(work):
            a, b, n = 0, 1, 0
            while True:
                if n > 30:
                    time.sleep(60)
                yield n, a
                a, b, n = b, a + b, n + 1
    """)

    def broken() -> bool:
        if armed():
            raise RuntimeError("clock fault")
        return False

    r = run_attempt(prog, FIB_KNOWN, replace(FAST, extend_wall_s=120), should_stop=broken)
    assert r.stop is Stop.HARNESS_ERROR and "on_tick raised RuntimeError: clock fault" in r.detail
    assert r.stop.value not in db.DETERMINISTIC_FAILURES and r.run.wall_s < 60
