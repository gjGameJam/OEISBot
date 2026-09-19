from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

from oeisbot import attempt, config, db, sandbox
from oeisbot.config import Budgets
from oeisbot.ingest import bfile, oeisdata
from oeisbot.ingest.seqfile import parse
from oeisbot.model import ModelUnavailable
from oeisbot.sandbox import RunResult, Status
from oeisbot.strategies import codegen
from oeisbot.terms import KnownTerms, Program
from oeisbot.verify import CONTRACT_ERROR, AttemptResult, Stop, _short, run_attempt

PLAN = '{"approach": "brute_force", "reason": "simple recurrence", "plan": "iterate the recurrence"}'

WRONG_OFFSET = """```python
def terms(work):
    a, b, n = 0, 1, 1
    while True:
        yield n, a
        work(1)
        a, b, n = b, a + b, n + 1
```"""

CORRECT = """Here you go:
```python
def terms(work):
    a, b, n = 0, 1, 0
    while True:
        yield n, a
        work(1)
        a, b, n = b, a + b, n + 1
```"""


class FakeModel:
    name = "fake-coder"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[list[dict]] = []
        self.temperatures: list[float] = []

    def chat(self, messages, *, temperature=0.2, max_tokens=2048):
        self.calls.append([dict(m) for m in messages])
        self.temperatures.append(temperature)
        return self.replies.pop(0)


def test_extract_code_and_plan():
    assert codegen.extract_code(CORRECT).startswith("def terms(work):")
    assert codegen.extract_code("no code here") is None
    assert codegen.parse_plan("sure: " + PLAN).approach == "brute_force"
    assert codegen.parse_plan("garbage").approach == "brute_force"
    assert codegen.parse_plan('{"approach": "skip", "reason": "hopeless"}').approach == "skip"


@pytest.mark.parametrize("code, problem", [
    ("import os\ndef terms(work):\n    yield 0, 0\n", "import not allowed: os"),
    ("from subprocess import run\ndef terms(work):\n    yield 0, 0\n", "import not allowed: subprocess"),
    ("def terms(work):\n    open('x')\n    yield 0, 0\n", "use of `open`"),
    ("def terms(work):\n    yield ().__class__.__bases__\n", "dunder attribute"),
    ("def terms():\n    yield 0, 0\n", "exactly one argument"),
    ("def f(work):\n    yield 0, 0\n", "no top-level function"),
    ("def terms(work:\n", "SyntaxError"),
])
def test_static_check_rejects(code, problem):
    assert problem in codegen.static_check(code)


def test_static_check_accepts_allowed_imports():
    assert codegen.static_check("import math, gmpy2\nfrom sympy import isprime\ndef terms(work):\n    yield 0, 0\n") is None


def fib_known(n_terms=40) -> KnownTerms:
    fib = [0, 1]
    while len(fib) < n_terms:
        fib.append(fib[-1] + fib[-2])
    return KnownTerms("A999998", 0, dict(enumerate(fib)), "bfile")


def test_prompt_holds_out_known_terms():
    known = fib_known(40)
    shown = codegen.shown_indices(known)
    assert len(shown) == 24 and shown[-1] == 23
    entry = parse("%S A999998 0,1,1,2\n%N A999998 Test.\n%O A999998 0,1\n%K A999998 nonn,more\n")
    text = codegen._context(entry, known)
    assert f"a(23) = {known.values[23]}" in text and "a(24) = " not in text
    assert "including 16 you cannot see" in text


@pytest.mark.parametrize("count, shown", [(3, 1), (4, 2), (5, 3), (6, 3), (7, 4), (10, 6), (40, 24), (60, 30)])
def test_at_least_two_known_terms_are_always_held_out(count, shown):
    assert len(codegen.shown_indices(fib_known(count))) == shown


def test_copied_terms_rejected_but_small_constants_allowed():
    known = fib_known(40)
    listed = ", ".join(str(known.values[n]) for n in range(10, 30))
    copied = f"KNOWN = [{listed}]\ndef terms(work):\n    yield from enumerate(KNOWN)\n"
    assert "known term values as literals" in codegen.static_check(copied, known.values.values())
    as_string = f'S = "{listed}"\ndef terms(work):\n    yield 0, 0\n'
    assert "known term values as literals" in codegen.static_check(as_string, known.values.values())
    wheel = "W = [2, 3, 5, 7, 11, 13]\ndef terms(work):\n    yield 0, 0\n"
    assert codegen.static_check(wheel, [2, 3, 5, 7, 11, 13, 17, 19]) is None


def test_fixed_bounds_flagged():
    code = "from sympy import primerange\nlimit = 1000\ndef terms(work):\n    ps = list(primerange(2, 50000))\n    yield 0, 0\n"
    assert codegen.fixed_bounds(code) == ["limit = 1000", "primerange(..., 50000)"]
    assert codegen.fixed_bounds("def terms(work):\n    for i in range(10):\n        yield i, i\n") == []


def test_held_out_values_are_not_revealed_in_retries():
    known = fib_known(40)
    run = RunResult(Status.STOPPED, 1, 1.0, 1.0, 0, 0)
    prog = Program("python", "", "test", "python:model")
    hidden = AttemptResult(prog, known, "failed", Stop.WRONG_TERM, f"a(30) = 5, known value {known.values[30]}",
                           False, 30, [], [], run)
    text = codegen.describe_failure(hidden, shown_last_index=23)
    assert str(known.values[30]) not in text and "not shown" in text
    visible = AttemptResult(prog, known, "failed", Stop.WRONG_TERM, f"a(20) = 5, known value {known.values[20]}",
                            False, 20, [], [], run)
    assert str(known.values[20]) in codegen.describe_failure(visible, shown_last_index=23)


def test_retry_guidance_depends_on_the_failure():
    """A crash is an error in the code, not a misreading of the definition; steering the model at the
    definition is what let one sequence fail three generations with the same missing-API error."""
    crash = codegen.retry_guidance(Stop.CRASH)
    assert "primerange" in crash and "no gmpy2.prime_range" in crash
    assert codegen.DEFINITION_GUIDANCE not in crash
    for stop in (Stop.BAD_INDEX, Stop.PROTOCOL):
        assert "protocol" in codegen.retry_guidance(stop)
        assert codegen.DEFINITION_GUIDANCE not in codegen.retry_guidance(stop)
    for stop in (Stop.VERIFY_TIMEOUT, Stop.TIMEOUT, Stop.CPU_CAP):
        assert "too slow, not wrong" in codegen.retry_guidance(stop)
    assert "memory" in codegen.retry_guidance(Stop.MEMORY_CAP)
    assert "keep yielding" in codegen.retry_guidance(Stop.INCOMPLETE)
    # a wrong value really is a misreading: keep the old wording
    assert codegen.retry_guidance(Stop.WRONG_TERM) == codegen.DEFINITION_GUIDANCE
    assert codegen.retry_guidance(None) == "Fix that and send the program again."


def test_host_conditions_are_not_blamed_on_the_program():
    """launch_error and disk_cap can be the machine, not the program (no free RAM, full disk). Telling the
    model to re-read the definition then burns a generation on something it cannot fix."""
    launch = codegen.retry_guidance(Stop.LAUNCH_ERROR)
    assert "rather than in your program" in launch
    for stop in (Stop.LAUNCH_ERROR, Stop.DISK_CAP, Stop.OUTPUT_CAP):
        assert codegen.DEFINITION_GUIDANCE not in codegen.retry_guidance(stop)


def test_every_stop_that_can_retry_is_classified():
    """The fall-through exists, but nothing reaching a retry today should be landing in it: a new Stop
    should be classified deliberately rather than inheriting definition advice."""
    # stops that imply the program verified; generate_and_verify breaks before retrying on these
    after_verification = {Stop.VERIFIED_ONLY, Stop.INFEASIBLE, Stop.OVER_PREDICTION, Stop.EXTEND_BUDGET,
                          Stop.MAX_NEW_TERMS, Stop.FINISHED}
    unclassified = [s for s in Stop if s not in after_verification
                    and s is not Stop.WRONG_TERM                      # the one intended fall-through
                    and codegen.retry_guidance(s) == codegen.DEFINITION_GUIDANCE]
    assert unclassified == [], f"these stops silently inherit definition advice: {unclassified}"


@pytest.mark.sandbox
@pytest.mark.skipif(bool(sandbox.runtime_problems()), reason="sandbox runtime missing")
def test_api_hints_name_only_functions_that_exist():
    """A hint list that invents a name is the bug it exists to fix, so check every name against the
    interpreter that will actually run the generated program (gmpy2/sympy are not in the venv)."""
    probe = ("import importlib\n"
             "missing = [f'{m}.{n}' for m, ns in %r.items() for n in ns\n"
             "           if not hasattr(importlib.import_module(m), n)]\n"
             "import gmpy2\n"
             "missing += ['gmpy2.prime_range exists after all'] if hasattr(gmpy2, 'prime_range') else []\n"
             "print('|'.join(missing))" % codegen.API_NAMES)
    out = subprocess.run([str(config.SANDBOX_PYTHON), "-c", probe], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "", f"bad names in API_HINTS: {out.stdout.strip()}"


FIB = ",".join(str(x) for x in [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181])
FAST = Budgets(verify_wall_s=30, extend_wall_s=3, max_new_terms=3)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path / "artifacts")
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(bfile, "fetch", lambda a, refresh=False: None)
    monkeypatch.setattr(oeisdata, "load_entry", lambda a: parse(
        f"%S A999998 {FIB}\n%N A999998 Fibonacci-like test sequence.\n%O A999998 0,4\n%K A999998 nonn,more\n"
        "%t A999998 Table[Fibonacci[n], {n, 0, 20}]\n"))
    monkeypatch.setattr(attempt, "recheck", lambda known, first, new: (True, "test"))
    conn = db.connect(tmp_path / "t.sqlite3")
    yield conn, tmp_path
    conn.close()


@pytest.mark.sandbox
@pytest.mark.skipif(bool(sandbox.runtime_problems()), reason="sandbox runtime missing")
def test_retry_with_real_error_then_success(env):
    conn, tmp = env
    model = FakeModel([PLAN, WRONG_OFFSET, CORRECT])
    rep = attempt.attempt_sequence(conn, "A999998", FAST, log=lambda m: None, model=model)
    assert rep.artifact, rep.lines
    retry_prompt = model.calls[2][-1]["content"]
    assert "bad_index" in retry_prompt and "n = 0" in retry_prompt
    # the stop-specific guidance must actually reach the model, not just exist in retry_guidance
    assert "output-protocol error" in retry_prompt
    assert codegen.DEFINITION_GUIDANCE not in retry_prompt
    assert len(model.calls[2]) == 4          # system, task, latest reply, failure: no older history
    rows = conn.execute("SELECT strategy, outcome, failure_mode FROM attempts ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [("python:model", "failed", "bad_index"),
                                        ("python:model", "extended", "max_new_terms")]
    readme = (tmp / "artifacts" / "A999998" / f"attempt-{rep.attempt_ids[-1]}" / "README.md").read_text()
    assert "AI-generated" in readme


@pytest.mark.sandbox
@pytest.mark.skipif(bool(sandbox.runtime_problems()), reason="sandbox runtime missing")
def test_generation_cap_and_static_rejections(env):
    conn, _ = env
    bad = "```python\nimport os\ndef terms(work):\n    yield 0, 0\n```"
    model = FakeModel([PLAN, bad, bad, WRONG_OFFSET])
    rep = attempt.attempt_sequence(conn, "A999998", FAST, log=lambda m: None, model=model)
    assert rep.artifact is None
    assert len(model.calls) == 1 + config.CODEGEN_ATTEMPTS
    assert "import not allowed: os" in model.calls[2][-1]["content"]


def test_too_few_known_terms_never_reach_the_model(env, monkeypatch):
    conn, _ = env
    entry = parse("%S A999998 0,1\n%N A999998 Too short.\n%O A999998 0,2\n%K A999998 nonn,more\n")
    monkeypatch.setattr(oeisdata, "load_entry", lambda a: entry)
    model = FakeModel([])
    rep = attempt.attempt_sequence(conn, "A999998", FAST, log=lambda m: None, model=model)
    assert rep.skipped == "too_few_known_terms" and model.calls == []
    with pytest.raises(ValueError, match="at least 3"):
        codegen.generate_and_verify(entry, fib_known(2), model, lambda prog: None)
    assert model.calls == []


def test_no_runnable_code_is_recorded(env):
    conn, _ = env
    bad = "```python\nimport os\ndef terms(work):\n    yield 0, 0\n```"
    model = FakeModel([PLAN, bad, bad, bad])
    rep = attempt.attempt_sequence(conn, "A999998", FAST, log=lambda m: None, model=model)
    assert rep.skipped == "model_no_runnable_code"
    row = conn.execute("SELECT strategy, failure_mode, detail FROM attempts").fetchone()
    assert (row["strategy"], row["failure_mode"]) == ("python:model", "model_no_runnable_code")
    assert row["detail"].count("import not allowed: os") == config.CODEGEN_ATTEMPTS


def test_an_unreachable_model_ends_the_sequence_without_a_run(env):
    conn, _ = env

    class Unreachable:
        name = "unreachable"

        def chat(self, messages, **kwargs):
            raise ModelUnavailable("http://127.0.0.1:11434/api/chat: connection refused")

    rep = attempt.attempt_sequence(conn, "A999998", FAST, log=lambda m: None, model=Unreachable())
    assert rep.skipped == "no_supported_program"      # the entry has no PARI program either
    assert any("model unavailable" in line for line in rep.lines)


def test_model_skip_is_recorded(env):
    conn, _ = env
    model = FakeModel(['{"approach": "skip", "reason": "needs a supercomputer"}'])
    rep = attempt.attempt_sequence(conn, "A999998", FAST, log=lambda m: None, model=model)
    assert rep.skipped == "model_skip"
    assert conn.execute("SELECT failure_mode FROM attempts").fetchone()[0] == "model_skip"


# ------------------------------------------------------------------ lists: members(work); repeated programs

LIST_ENTRY = ("%S A999997 2,3,5,7,11,13,17,19,23,29,31,37,41,43,47\n%N A999997 Numbers k such that k is prime.\n"
              "%O A999997 1,1\n%K A999997 nonn,more\n")
LIST_HELD = [29, 31, 37, 41, 43, 47]          # a(10)..a(15): 15 known terms, 9 shown
FORM_LIST = '{"form": "list", "reason": "the numbers k with a property"}'
FORM_FUNCTION = '{"form": "function", "reason": "a(n) is computed from n"}'
MEMBERS_PRIMES = """```python
def members(work):
    k = 1
    while True:
        k += 1
        work(1)
        if all(k % d for d in range(2, int(k ** 0.5) + 1)):
            yield k
```"""
MEMBERS_COMMENTED = MEMBERS_PRIMES.replace("    k = 1\n", "    k = 1          # below the first prime\n\n")
MEMBERS_OTHER = MEMBERS_PRIMES.replace("    k = 1\n", "    k = 0\n")
RUN = RunResult(Status.STOPPED, 1, 1.0, 1.0, 0, 0)


def list_known() -> KnownTerms:
    return bfile.known_terms(parse(LIST_ENTRY), None)


def scripted_runner(known, stops):
    """Runs nothing: answers each program with the next (stop, detail[, reproduced]), verified when the stop
    is `finished`. A failure reproduces 0 known terms unless the step says otherwise."""
    ran: list[Program] = []

    def run(prog):
        ran.append(prog)
        stop, detail, *reproduced = stops.pop(0)
        ok = stop is Stop.FINISHED
        return AttemptResult(prog, known, "verified" if ok else "failed", stop, detail, ok,
                             known.count if ok else reproduced[0] if reproduced else 0, [], [], RUN)
    return run, ran


def user_text(call) -> str:
    return "\n".join(m["content"] for m in call if m["role"] == "user")


def test_form_defaults_to_function():
    assert codegen.parse_form(FORM_LIST) == "list" and codegen.parse_form(FORM_FUNCTION) == "function"
    assert codegen.parse_form('sure: {"form": " LIST "}') == "list"
    assert codegen.parse_form('{"form": "sequence"}') == "function"
    assert codegen.parse_form("not json at all") == "function" and codegen.parse_form("[1, 2]") == "function"
    assert codegen.parse_plan(PLAN).form == "function"          # the plan itself never sets it


def test_members_contract_only_for_a_list_whose_terms_increase():
    assert codegen.contract_for("list", list_known()) is codegen.MEMBERS
    assert codegen.contract_for("function", list_known()) is codegen.TERMS
    assert codegen.contract_for("list", fib_known(20)) is codegen.TERMS         # 0, 1, 1, 2, ...: not strictly
    assert codegen.contract_for("list", KnownTerms("A999997", 1, {1: 5, 2: 5, 3: 6}, "data")) is codegen.TERMS


def test_static_check_and_extraction_follow_the_contract():
    members = "def members(work):\n    yield 2\n"
    assert codegen.static_check(members, function="members") is None
    assert "no top-level function `terms`" in codegen.static_check(members)
    assert "no top-level function `members`" in codegen.static_check("def terms(work):\n    yield 1, 2\n",
                                                                       function="members")
    assert "exactly one argument" in codegen.static_check("def members():\n    yield 2\n", function="members")
    both = members + "def terms(work):\n    yield 1, 2\n"
    assert "the runner supplies `terms`" in codegen.static_check(both, function="members")
    assert codegen.extract_code("def members(work):\n    yield 2", "members").startswith("def members")
    assert codegen.extract_code("def members(work):\n    yield 2") is None


def test_fixed_bounds_include_constant_expressions():
    code = ("LIMIT = 10**7\nsize = 2 * 10**6\ncap = 10**4 - 1\n"
            "def members(work):\n    for k in range(2, 1 << 20):\n        yield k\n")
    assert codegen.fixed_bounds(code) == ["LIMIT = 10000000", "cap = 9999", "range(..., 1048576)", "size = 2000000"]
    assert codegen.fixed_bounds("N_MAX = 10**100000\n") == []        # not evaluated: too big to build


def test_a_list_gets_the_members_contract_and_the_driver():
    entry, known = parse(LIST_ENTRY), list_known()
    model = FakeModel([PLAN, FORM_LIST, MEMBERS_PRIMES])
    runner, ran = scripted_runner(known, [(Stop.FINISHED, "program ended after verification")])
    out = codegen.generate_and_verify(entry, known, model, runner, log=lambda m: None)
    assert out.success is not None and out.plan.form == "list"
    assert user_text(model.calls[0]) == codegen.CLASSIFY.format(context=codegen._context(entry, known),
                                                                approaches=list(codegen.APPROACHES))
    assert user_text(model.calls[1]) == codegen.FORM.format(context=codegen._context(entry, known))
    assert model.temperatures[1] == 0.2
    generate = user_text(model.calls[2])
    assert "def members(work):" in generate and "def terms(work)" not in generate
    assert "your first value becomes a(1), the second a(2)" in generate
    [prog] = ran
    code = codegen.extract_code(MEMBERS_PRIMES, "members")
    assert prog.source == code and prog.script == code + codegen.MEMBERS_DRIVER.format(first=1)
    assert prog.executed.endswith(codegen.MEMBERS_DRIVER.format(first=1))
    assert prog.strategy == "python:model" and "members(work), numbered by the runner" in prog.origin
    assert any(n.startswith(codegen.MEMBERS_NOTE) for n in prog.notes)


def test_a_function_keeps_the_terms_contract():
    entry = parse(f"%S A999998 {FIB}\n%N A999998 Fibonacci-like test sequence.\n%O A999998 0,4\n%K A999998 nonn,more\n")
    # known terms that do not strictly increase: the form is not even asked
    model = FakeModel([PLAN, CORRECT])
    runner, ran = scripted_runner(fib_known(20), [(Stop.FINISHED, "program ended after verification")])
    codegen.generate_and_verify(entry, fib_known(20), model, runner, log=lambda m: None)
    assert len(model.calls) == 2
    # increasing known terms, but the model says function
    model2 = FakeModel([PLAN, FORM_FUNCTION, CORRECT])
    runner2, ran2 = scripted_runner(list_known(), [(Stop.FINISHED, "program ended after verification")])
    codegen.generate_and_verify(parse(LIST_ENTRY), list_known(), model2, runner2, log=lambda m: None)
    for m, prog in ((model, ran[0]), (model2, ran2[0])):
        generate = user_text(m.calls[-1])
        assert "def terms(work):" in generate and "members" not in generate
        assert prog.script is None and prog.executed == codegen.extract_code(CORRECT)
        assert not any(n.startswith(codegen.MEMBERS_NOTE) for n in prog.notes)


def test_list_retries_reveal_no_held_out_value():
    entry, known = parse(LIST_ENTRY), list_known()
    wrong = AttemptResult(Program("python", "", "test", "python:model"), known, "failed", Stop.WRONG_TERM,
                          "a(11) = 37, known value 31", False, 10, [], [], RUN)
    text = codegen.describe_failure(wrong, shown_last_index=9, contract=codegen.MEMBERS)
    assert "a(11) is wrong" in text and "37" not in text and "31" not in text
    # terms(work) shows a wrong program value, but not this one: 37 is the held-out a(12) (offer G)
    assert "37" not in codegen.describe_failure(wrong, shown_last_index=9)
    # a shown index, but the program's value (the held-out a(10)) lies past the last term shown
    skipped = AttemptResult(Program("python", "", "test", "python:model"), known, "failed", Stop.WRONG_TERM,
                            "a(9) = 29, known value 23", False, 8, [], [], RUN)
    text = codegen.describe_failure(skipped, shown_last_index=9, contract=codegen.MEMBERS)
    assert "29" not in text and "a(9) is wrong: it is 23" in text
    early = AttemptResult(Program("python", "", "test", "python:model"), known, "failed", Stop.WRONG_TERM,
                          "a(5) = 13, known value 11", False, 4, [], [], RUN)
    assert "a(5) = 13" in codegen.describe_failure(early, shown_last_index=9, contract=codegen.MEMBERS)
    # a value too long to print in full cannot be compared, so it is not shown either
    long = AttemptResult(Program("python", "", "test", "python:model"), known, "failed", Stop.WRONG_TERM,
                         "a(9) = 1234567890123456789012345...5432109876543210987654321 (70 digits), known value 23",
                         False, 8, [], [], RUN)
    text = codegen.describe_failure(long, shown_last_index=9, contract=codegen.MEMBERS)
    assert "12345678901" not in text and "a(9) is wrong: it is 23" in text
    # through the loop: both kinds, then a repeat
    model = FakeModel([PLAN, FORM_LIST, MEMBERS_PRIMES, MEMBERS_OTHER, MEMBERS_COMMENTED])
    runner, _ = scripted_runner(known, [(Stop.WRONG_TERM, "a(9) = 29, known value 23"),
                                        (Stop.WRONG_TERM, "a(11) = 37, known value 31")])
    codegen.generate_and_verify(entry, known, model, runner, log=lambda m: None)
    for call in model.calls:
        assert not [v for v in LIST_HELD if re.search(rf"\b{v}\b", user_text(call))]
    # and through the repeat message, which describes the earlier failure again
    model = FakeModel([PLAN, FORM_LIST, MEMBERS_PRIMES, MEMBERS_COMMENTED, MEMBERS_OTHER])
    runner, _ = scripted_runner(known, [(Stop.WRONG_TERM, "a(9) = 29, known value 23"),
                                        (Stop.WRONG_TERM, "a(2) = 4, known value 3")])
    codegen.generate_and_verify(entry, known, model, runner, log=lambda m: None)
    assert "the same program as the one you sent in generation 1" in model.calls[4][-1]["content"]
    for call in model.calls:
        assert not [v for v in LIST_HELD if re.search(rf"\b{v}\b", user_text(call))]


# the deterministic failures, and a verify_timeout: every generation of a stage has the same verify budget
@pytest.mark.parametrize("stop", [Stop.WRONG_TERM, Stop.BAD_INDEX, Stop.PROTOCOL, Stop.CRASH, Stop.INCOMPLETE,
                                  Stop.VERIFY_TIMEOUT])
def test_a_program_that_would_fail_again_is_not_run_again(stop):
    entry, known = parse(LIST_ENTRY), list_known()
    # generation 2 is generation 1 with a comment and a blank line; generation 3 differs. Each failure
    # reproduced 2 known terms first, as 15 of the 16 real model timeouts had reproduced some
    model = FakeModel([PLAN, FORM_LIST, MEMBERS_PRIMES, MEMBERS_COMMENTED, MEMBERS_OTHER])
    runner, ran = scripted_runner(known, [(stop, "detail one", 2), (stop, "detail two", 2)])
    out = codegen.generate_and_verify(entry, known, model, runner, log=lambda m: None)
    assert [p.origin.split(",")[1].strip()[:12] for p in ran] == ["generation 1", "generation 3"]
    assert out.rejected == [f"the same program as generation 1, which failed with {stop.value}"]
    assert len(model.calls) == 2 + config.CODEGEN_ATTEMPTS       # the repeat used up a generation
    retry = model.calls[4][-1]["content"]
    assert "the same program as the one you sent in generation 1" in retry
    assert codegen.REPEAT_GUIDANCE in retry and "detail one" in retry and codegen.retry_guidance(stop) in retry
    assert "Keep the same contract (def members(work) yielding the members themselves" in retry
    # ...and a repeat of an earlier, not the latest, program is caught as well
    model = FakeModel([PLAN, FORM_LIST, MEMBERS_PRIMES, MEMBERS_OTHER, MEMBERS_COMMENTED])
    runner, ran = scripted_runner(known, [(stop, "detail one", 2), (stop, "detail two", 2)])
    out = codegen.generate_and_verify(entry, known, model, runner, log=lambda m: None)
    assert len(ran) == 2 and out.rejected == [f"the same program as generation 1, which failed with {stop.value}"]
    # ...and so is a program that first failed in generation 2, the commonest real case (A320768, A396894)
    model = FakeModel([PLAN, FORM_LIST, MEMBERS_OTHER, MEMBERS_PRIMES, MEMBERS_COMMENTED])
    runner, ran = scripted_runner(known, [(stop, "detail one", 2), (stop, "detail two", 2)])
    out = codegen.generate_and_verify(entry, known, model, runner, log=lambda m: None)
    assert len(ran) == 2 and out.rejected == [f"the same program as generation 2, which failed with {stop.value}"]


@pytest.mark.parametrize("stop", [Stop.TIMEOUT, Stop.MEMORY_CAP, Stop.CPU_CAP, Stop.LAUNCH_ERROR, Stop.DISK_CAP,
                                  Stop.OUTPUT_CAP])
def test_a_program_is_run_again_after_a_failure_that_may_not_repeat(stop):
    entry, known = parse(LIST_ENTRY), list_known()
    model = FakeModel([PLAN, FORM_LIST, MEMBERS_PRIMES, MEMBERS_PRIMES, MEMBERS_PRIMES])
    runner, ran = scripted_runner(known, [(stop, "d")] * 3)
    out = codegen.generate_and_verify(entry, known, model, runner, log=lambda m: None)
    assert len(ran) == 3 and out.rejected == []


@pytest.mark.sandbox
@pytest.mark.skipif(bool(sandbox.runtime_problems()), reason="sandbox runtime missing")
@pytest.mark.parametrize("first", [-2, 0, 1, 5])
def test_the_driver_numbers_the_members_from_the_offset(first):
    code = "def members(work):\n    k = 0\n    while True:\n        work(1)\n        yield k * k\n        k += 1\n"
    known = KnownTerms("A999997", first, {first + i: i * i for i in range(12)}, "data")
    prog = Program("python", code, "test", "python:model", script=code + codegen.MEMBERS_DRIVER.format(first=first))
    r = run_attempt(prog, known, FAST)
    assert r.verified and r.reproduced == 12, (r.stop, r.detail)
    assert [(t.n, t.value) for t in r.new_terms] == [(first + 12, 144), (first + 13, 169), (first + 14, 196)]


@pytest.mark.sandbox
@pytest.mark.skipif(bool(sandbox.runtime_problems()), reason="sandbox runtime missing")
@pytest.mark.parametrize("yields, message", [
    ("1, 4, 9, 4", "members() must yield increasing values: the value after a(3) was not larger than it"),
    ("1, 4, 4", "members() must yield increasing values: the value after a(2) was not larger than it"),
    ("(1, 1), (2, 4)", "members() must yield the members themselves, not (index, value) pairs"),
])
def test_the_driver_rejects_what_is_not_a_list(yields, message):
    code = f"def members(work):\n    yield from [{yields}]\n"
    known = KnownTerms("A999997", 1, {1: 1, 2: 4, 3: 9, 4: 16}, "data")
    prog = Program("python", code, "test", "python:model", script=code + codegen.MEMBERS_DRIVER.format(first=1))
    r = run_attempt(prog, known, FAST)
    assert r.stop is Stop.PROTOCOL and r.detail == f"{CONTRACT_ERROR}: {message}" and not r.verified
    assert not re.search(r"\d", r.detail.replace(message, ""))     # positions only: no value is named
    assert f"class {CONTRACT_ERROR}(Exception):" in codegen.MEMBERS_DRIVER     # the name the harness knows


@pytest.mark.sandbox
@pytest.mark.skipif(bool(sandbox.runtime_problems()), reason="sandbox runtime missing")
def test_a_members_program_wins_and_is_reviewed_as_ai_generated(env, monkeypatch):
    conn, tmp = env
    monkeypatch.setattr(oeisdata, "load_entry", lambda a: parse(LIST_ENTRY))
    model = FakeModel([PLAN, FORM_LIST, MEMBERS_PRIMES])
    rep = attempt.attempt_sequence(conn, "A999997", FAST, log=lambda m: None, model=model)
    assert rep.artifact, rep.lines
    row = conn.execute("SELECT strategy, program_origin, program_sha, extra FROM attempts").fetchone()
    assert row["strategy"] == "python:model" and "members(work), numbered by the runner" in row["program_origin"]
    folder = tmp / "artifacts" / "A999997" / f"attempt-{rep.attempt_ids[-1]}"
    code = codegen.extract_code(MEMBERS_PRIMES, "members")
    executed = code + codegen.MEMBERS_DRIVER.format(first=1)
    assert (folder / "program.py").read_text() == code + "\n"
    assert (folder / "executed.py").read_text() == executed
    readme = (folder / "README.md").read_text()
    assert "AI-generated program" in readme and "Numbered by the runner" in readme and "executed.py" in readme
    assert (folder / "b999997.txt").read_text().splitlines()[15:] == ["16 53", "17 59", "18 61"]
    # the kept program is what ran, and its hash is the recorded one
    kept = Path(json.loads(row["extra"])["log"]).with_suffix(".py").read_bytes()
    assert kept == executed.encode() and hashlib.sha256(kept).hexdigest()[:16] == row["program_sha"]


ORIGINAL_GENERATE = """CONTEXT

Approach: search. PLAN

Write Python 3.11 code defining exactly this generator:

def terms(work):
    # yields (n, a(n)) for n = 1, 1+1, 1+2, ... in order, forever

Rules:
- Yield tuples (n, value) where value is a Python int or gmpy2.mpz. Start at n = 1. Never skip an index.
- Do not stop after the known terms; keep yielding until the process is killed.
- Call work(k) to report k units of real work (candidates tested, nodes visited, states expanded),
  batched, e.g. work(1000) once per 1000 inner-loop steps.
- Compute every term. Never copy known terms into the program.
- No fixed search limits (like limit = 1000): grow any sieve or search range as n increases.
- Reuse work between terms where possible instead of recomputing each a(n) from scratch.
- Prefer memory-lean methods: generators, DFS/backtracking rather than BFS, no huge lists.
- Allowed imports: math. No file, network or subprocess access. Do not print anything.
Output a single ```python code block and nothing else."""
ORIGINAL_CLASSIFY = """CONTEXT

Decide how to compute further terms of this sequence on a single desktop computer.
Answer with one JSON object and nothing else:
{"approach": one of ['a', 'b'], "reason": "<one sentence>", "plan": "<two or three sentences on the algorithm>"}
Use "skip" when further terms clearly need a research breakthrough or huge computation."""
ORIGINAL_RETRY = """Your last program did not get through verification:

FAILURE

GUIDANCE

Keep the same contract (def terms(work) yielding (n, a(n)) from n = 1).
Output a single ```python code block and nothing else."""


def test_prompts_for_a_function_are_word_for_word_the_old_ones():
    """The list contract must leave everything a function-style sequence sees as it was before it."""
    assert codegen.GENERATE.format(context="CONTEXT", approach="search", plan="PLAN", imports="math",
                                   contract=codegen.TERMS.spec.format(first=1, second=2)) == ORIGINAL_GENERATE
    assert codegen.CLASSIFY.format(context="CONTEXT", approaches=["a", "b"]) == ORIGINAL_CLASSIFY
    assert codegen.RETRY.format(failure="FAILURE", guidance="GUIDANCE",
                                keep=codegen.TERMS.keep.format(first=1)) == ORIGINAL_RETRY


@pytest.mark.parametrize("extra", [
    "terms = []\n", "class terms:\n    pass\n", "terms = members\n", "from math import sqrt as terms\n",
    "for terms in range(3):\n    pass\n", "if True:\n    terms = 1\n",
    "def helper():\n    global terms\n    terms = 1\n", "del terms\n", "import terms.x\n",
    "try:\n    pass\nexcept Exception as terms:\n    pass\n", "match 1:\n    case terms:\n        pass\n",
    "def helper(x=(terms := 1)):\n    return x\n", "class C((terms := object)):\n    pass\n",
])
def test_the_name_terms_is_refused_beside_members(extra):
    code = "def members(work):\n    yield 2\n" + extra
    assert "do not use the name `terms`" in codegen.static_check(code, function="members")


# ------------------------------------------------------------------ offer G: a program value that is a held-out term

def failed(known, detail, stop=Stop.WRONG_TERM):
    return AttemptResult(Program("python", "", "test", "python:model"), known, "failed", stop, detail, False, 0,
                         [], [], RUN)


def test_a_program_value_that_is_a_held_out_term_is_never_shown():
    known = list_known()                     # a(1)..a(9) = 2..23 shown; 29, 31, 37, 41, 43, 47 held out

    def said(detail, stop=Stop.WRONG_TERM):
        return codegen.describe_failure(failed(known, detail, stop), shown_last_index=9)
    # an off-by-one terms(work) program, at a shown index and at a held-out one
    assert said("a(9) = 29, known value 23") == "wrong_term: a(9) is wrong: it is 23 (your value is not shown)"
    assert said("a(11) = 37, known value 31").startswith("wrong_term: a(11) is wrong (neither your value")
    # a value that is no term is still shown, as before
    assert said("a(9) = 30, known value 23") == "wrong_term: a(9) = 30, known value 23"
    assert "a(11) = 38 is wrong" in said("a(11) = 38, known value 31")
    # a bad index that is really a held-out term (either sign), and one that is not
    assert "41" not in said("program emitted n=41, expected n=1 (offset is 1)", Stop.BAD_INDEX)
    assert "41" not in said("program emitted n=-41, expected n=1 (offset is 1)", Stop.BAD_INDEX)
    assert "program emitted n=40, expected n=1" in said("program emitted n=40, expected n=1 (offset is 1)", Stop.BAD_INDEX)


@pytest.mark.parametrize("contract", [codegen.TERMS, codegen.MEMBERS])
def test_a_held_out_term_with_its_sign_flipped_is_not_shown(contract):
    # attempt #105 (A345338): the retry said "a(1) = -10031, known value 1", and 10031 is the held-out a(4)
    known = KnownTerms("A345338", 1, {1: 1, 2: 5, 3: 181, 4: 10031, 5: 1001320}, "data")
    text = codegen.describe_failure(failed(known, "a(1) = -10031, known value 1"), shown_last_index=3,
                                    contract=contract)
    assert "10031" not in text and "a(1) is wrong: it is 1" in text


def test_long_held_out_values_are_matched_as_the_harness_prints_them():
    h = 10**70 + 12345                       # 71 digits: printed abbreviated, and -h with one digit more
    known = KnownTerms("A999996", 1, {1: 1, 2: 2, 3: 3, 4: h, 5: h + 1}, "data")      # a(1)..a(3) shown
    for value in (h, -h, h + 10**40):        # the last differs from h but prints the same: hidden too
        text = codegen.describe_failure(failed(known, f"a(2) = {_short(value)}, known value 2"), shown_last_index=3)
        assert _short(value) not in text and "a(2) is wrong: it is 2" in text
    text = codegen.describe_failure(failed(known, f"a(2) = {_short(h + 2)}, known value 2"), shown_last_index=3)
    assert f"a(2) = {_short(h + 2)}" in text                           # not a held-out term: shown
    # a bad index is printed in full, not abbreviated
    for n in (h, -h):
        text = codegen.describe_failure(failed(known, f"program emitted n={n}, expected n=1 (offset is 1)",
                                               Stop.BAD_INDEX), shown_last_index=3)
        assert str(h) not in text and "program emitted a wrong index (not shown)" in text


def test_a_value_that_is_also_shown_stays_shown():
    # 4 is held out (a(5)) but also shown (a(1), a(3)): repeating it reveals nothing; 7 is only held out
    known = KnownTerms("A999996", 1, {1: 4, 2: 5, 3: 4, 4: 7, 5: 4}, "data")
    assert "a(2) = 4, known value 5" in codegen.describe_failure(failed(known, "a(2) = 4, known value 5"), 3)
    assert "7" not in codegen.describe_failure(failed(known, "a(2) = 7, known value 5"), 3)


def test_terms_retries_carry_no_held_out_value():
    entry, known = parse(LIST_ENTRY), list_known()
    commented = CORRECT.replace("a, b, n = 0, 1, 0", "a, b, n = 0, 1, 0   # from the start")
    # the known terms increase, but the model says function: terms(work), whose retries show program values
    for replies, stops in (
            ([PLAN, FORM_FUNCTION, CORRECT, WRONG_OFFSET, commented],
             [(Stop.WRONG_TERM, "a(9) = 29, known value 23"), (Stop.WRONG_TERM, "a(11) = 37, known value 31")]),
            ([PLAN, FORM_FUNCTION, CORRECT, commented, WRONG_OFFSET],      # the repeat message goes out
             [(Stop.WRONG_TERM, "a(11) = 37, known value 31"), (Stop.WRONG_TERM, "x")]),
            ([PLAN, FORM_FUNCTION, CORRECT, commented, WRONG_OFFSET],
             [(Stop.BAD_INDEX, "program emitted n=41, expected n=1 (offset is 1)"), (Stop.WRONG_TERM, "x")])):
        model = FakeModel(replies)
        runner, ran = scripted_runner(known, stops)
        codegen.generate_and_verify(entry, known, model, runner, log=lambda m: None)
        assert all(p.script is None for p in ran)                       # terms(work) indeed
        assert len(model.calls) == 5
        for call in model.calls:
            assert not [v for v in LIST_HELD if re.search(rf"\b{v}\b", user_text(call))]


def test_code_that_cannot_be_parsed_is_rejected_not_raised():
    too_deep = "LIMIT = " + "+".join(["1"] * 5000) + "\ndef members(work):\n    yield 2\n"   # ast.parse recurses
    assert "cannot be parsed (RecursionError)" in codegen.static_check(too_deep, function="members")


def test_a_local_named_terms_is_allowed_beside_members():
    code = "def members(work):\n    terms = []\n    for k in range(2, 9):\n        terms.append(k)\n        yield k\n"
    assert codegen.static_check(code, function="members") is None


def test_an_unfenced_members_program_is_still_extracted():
    model = FakeModel([PLAN, FORM_LIST, "def members(work):\n    yield 2\n"])
    runner, ran = scripted_runner(list_known(), [(Stop.FINISHED, "program ended after verification")])
    out = codegen.generate_and_verify(parse(LIST_ENTRY), list_known(), model, runner, log=lambda m: None)
    assert len(ran) == 1 and out.rejected == []


def test_a_deeply_nested_expression_cannot_crash_the_stage():
    deep = ("LIMIT = " + "+".join(["1"] * 1000) + "\n"
            "def members(work):\n    k = 1\n    while True:\n        k += 1\n        yield k\n")
    with pytest.raises(RecursionError):          # the premise: it parses, but ast.dump cannot print it
        ast.dump(ast.parse(deep))
    assert codegen.static_check(deep, function="members") is None and codegen.fixed_bounds(deep) == []
    reply = "```python\n" + deep + "```"
    model = FakeModel([PLAN, FORM_LIST, reply, reply, MEMBERS_OTHER])
    runner, ran = scripted_runner(list_known(), [(Stop.WRONG_TERM, "a(2) = 4, known value 3"),
                                                 (Stop.WRONG_TERM, "a(2) = 4, known value 3")])
    out = codegen.generate_and_verify(parse(LIST_ENTRY), list_known(), model, runner, log=lambda m: None)
    assert len(ran) == 2 and out.rejected == ["the same program as generation 1, which failed with wrong_term"]


@pytest.mark.sandbox
@pytest.mark.skipif(bool(sandbox.runtime_problems()), reason="sandbox runtime missing")
def test_members_out_of_order_after_verification_void_the_new_terms():
    # 17 and 19 come before 13: a(6), a(7) would be recorded as 17, 19, and once 13 arrives, none stands
    known = KnownTerms("A999997", 1, {1: 2, 2: 3, 3: 5, 4: 7, 5: 11}, "data")
    code = "def members(work):\n    yield from [2, 3, 5, 7, 11, 17, 19, 13]\n"
    r = run_attempt(Program("python", code, "test", "python:model",
                            script=code + codegen.MEMBERS_DRIVER.format(first=1)), known, FAST)
    assert r.verified and r.stop is Stop.PROTOCOL and r.outcome == "verified" and r.new_terms == []
    assert [rec.kind for rec in r.records] == ["known"] * 5 + ["void", "void"]
    # any other error after verification still leaves the new terms standing, as for terms(work)
    code = "def members(work):\n    yield from [2, 3, 5, 7, 11, 13, 17]\n    raise RuntimeError('out of ideas')\n"
    r = run_attempt(Program("python", code, "test", "python:model",
                            script=code + codegen.MEMBERS_DRIVER.format(first=1)), known, FAST)
    assert r.stop is Stop.FINISHED and [(t.n, t.value) for t in r.new_terms] == [(6, 13), (7, 17)]
