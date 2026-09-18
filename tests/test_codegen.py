from __future__ import annotations

import subprocess

import pytest

from oeisbot import attempt, config, db, sandbox
from oeisbot.config import Budgets
from oeisbot.ingest import bfile, oeisdata
from oeisbot.ingest.seqfile import parse
from oeisbot.model import ModelUnavailable
from oeisbot.sandbox import RunResult, Status
from oeisbot.strategies import codegen
from oeisbot.terms import KnownTerms, Program
from oeisbot.verify import AttemptResult, Stop

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

    def chat(self, messages, *, temperature=0.2, max_tokens=2048):
        self.calls.append([dict(m) for m in messages])
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
