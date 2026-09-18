from __future__ import annotations

import pytest

from oeisbot import sandbox
from oeisbot.config import Budgets
from oeisbot.ingest.seqfile import parse
from oeisbot.strategies import pari
from oeisbot.terms import KnownTerms
from oeisbot.verify import Stop, run_attempt


def entry(programs: list[str], data="2,3,5,7,11,13,17,19,23,29,31,37,41,43,47", offset=1, name="Primes."):
    lines = [f"%S A999999 {data}", f"%N A999999 {name}", f"%O A999999 {offset},1", "%K A999999 nonn,more"]
    for prog in programs:
        first, *rest = prog.split("\n")
        lines.append(f"%o A999999 (PARI) {first}")
        lines += [f"%o A999999 {r}" for r in rest]
    return parse("\n".join(lines) + "\n")


def known(e):
    return KnownTerms(e.a_number, e.offset, e.data_values, "data")


def cands(*programs, **kw):
    e = entry(list(programs), **kw)
    return pari.build_candidates(e, known(e))


def test_statement_splitting():
    code = 'f(n) = {\n  my(s = "}{");\n  s\n}\nfor(n=1, 10,\n  print(f(n)))\nx = 3 \\\\ {comment'
    kinds = [(s.kind, s.name) for s in pari.split_statements(code)]
    assert kinds == [("def", "f"), ("call", None), ("assign", None)]


def test_a_of_n_form_drops_top_level_calls():
    cs, rej = cands("a(n) = prime(n)\nvector(20, n, a(n))")
    assert [c.form for c in cs] == ["a(n)"] and not rej
    script = cs[0].program.executed
    assert "vector(20" not in script and "for(oeisbot_n = 1, +oo" in script


def test_predicate_form():
    cs, _ = cands("isok(k) = isprime(k)")
    assert cs[0].form == "predicate"
    assert "for(oeisbot_k = 1, +oo" in cs[0].program.executed


def test_predicate_requires_increasing_terms():
    cs, rej = cands("isok(k) = isprime(k)", data="3,2,5")
    assert not cs and "not strictly increasing" in rej[0].reason


def test_print_loop_rewrite_lifts_bounds():
    cs, _ = cands("for(n=1, 10^4, if(isprime(n), print1(n, \", \")))")
    c = cs[0]
    assert c.form == "print-loop"
    assert "for(n=1, +oo, if(isprime(n), oeisbot_emit(n)))" in c.program.executed
    assert any("10^4 lifted" in n for n in c.program.notes)


def test_print_loop_inner_search_bound_lifted_but_not_small_bounds():
    prog = "for(n=1, 20, for(k=1, 100000, if(sum(i=1, 5, k%i)==n, print1(k, \", \"); break)); for(j=1, 9, 0))"
    c = cands(prog)[0][0]
    ex = c.program.executed
    assert "for(n=1, +oo" in ex and "for(k=1, +oo" in ex and "for(j=1, 9," in ex


def test_print_loop_with_leading_assignment():
    c = cands("a=1; for(n=1, 500, if(isprime(n), print1(n, \",\")); a++)")[0][0]
    assert "a=1;" in c.program.executed and "for(n=1, +oo" in c.program.executed


def test_unsupported_shapes_rejected():
    assert not cands("lista(nn) = for(n=1, nn, if(isprime(n), print1(n, \", \")))")[0]
    assert not cands("N=10^4; for(n=1, N, if(isprime(n), print1(n, \", \")))")[0]      # variable outer bound
    assert not cands("for(n=1, 99, print1(n, \", \")); print(\"done\")")[0]              # two prints
    assert "list-printing" in cands("lista(nn) = for(n=1, nn, print1(n))")[1][0].reason


runtime = pytest.mark.skipif(bool(sandbox.runtime_problems()), reason="sandbox runtime missing")
FAST = Budgets(verify_wall_s=30, extend_wall_s=5, max_new_terms=5)
PRIMES_AFTER_47 = [53, 59, 61, 67, 71]


@runtime
@pytest.mark.sandbox
@pytest.mark.parametrize("program", [
    "a(n) = prime(n)",
    "isok(k) = isprime(k)",
    "for(n=1, 100, if(isprime(n), print1(n, \", \")))",
])
def test_forms_verify_and_extend_in_sandbox(program):
    cs, _ = cands(program)
    e = entry([program])
    r = run_attempt(cs[0].program, known(e), FAST)
    assert r.verified and r.stop is Stop.MAX_NEW_TERMS, (r.stop, r.detail, r.run.stderr_tail)
    assert [(t.n, t.value) for t in r.new_terms] == list(zip(range(16, 21), PRIMES_AFTER_47))


@runtime
@pytest.mark.sandbox
def test_predicate_work_counts_reported():
    cs, _ = cands("isok(k) = isprime(k)")
    r = run_attempt(cs[0].program, known(entry(["isok(k) = isprime(k)"])), FAST)
    assert r.cost_unit == "work" and r.records[-1].work >= 71


@runtime
@pytest.mark.sandbox
def test_gp_syntax_error_is_a_crash_not_a_hang():
    cs, _ = cands("a(n) = prime(n")   # unbalanced
    e = entry(["a(n) = prime(n"])
    if not cs:
        return
    r = run_attempt(cs[0].program, known(e), FAST)
    assert not r.verified and r.stop in (Stop.CRASH, Stop.INCOMPLETE)
