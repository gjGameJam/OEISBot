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
    assert "oeisbot_base = 1" in cs[0].program.executed


def test_predicate_requires_increasing_terms():
    cs, rej = cands("isok(k) = isprime(k)", data="3,2,5")
    assert not cs and "not strictly increasing" in rej[0].reason


def test_search_start_is_where_the_driver_starts():
    """out_of_reach counts calls from search_start, so it must be the k the driver's loop begins at."""
    for data, start in [("2,3,5,7", 1), ("-3,0,4", -3), ("0,1,4,9", 0)]:
        c = cands("isok(k) = 1", data=data)[0][0]
        assert c.search_start == start and f"oeisbot_base = {start}" in c.program.executed
    assert cands("a(n) = prime(n)")[0][0].search_start is None
    assert cands("for(n=1, 10^4, if(isprime(n), print1(n, \", \")))")[0][0].search_start is None


def test_out_of_reach_bounds_predicate_searches_only():
    budget = 60
    limit = int(pari.PREDICATE_MAX_RATE * budget)          # calls one budget allows at most
    fits, too_far = f"2,3,{limit}", f"2,3,{limit + 1}"     # search from k = 1: calls = last term
    for data, reachable in [(fits, True), (too_far, False)]:        # exactly at the limit still fits
        e = entry(["isok(k) = 1"], data=data)
        c = pari.build_candidates(e, known(e))[0][0]
        why = pari.out_of_reach(c, known(e), budget)
        assert (why is None) == reachable, why
    assert "predicate calls" in why and "a(3)" in why
    # the same huge last term does not bound an a(n) program or a print loop
    for prog in ("a(n) = n", "for(n=1, 10^4, if(isprime(n), print1(n, \", \")))"):
        e = entry([prog], data=too_far)
        c = pari.build_candidates(e, known(e))[0][0]
        assert pari.out_of_reach(c, known(e), budget) is None
    # a last term far beyond a float's range is still described without an overflow
    e = entry(["isok(k) = 1"], data="2,3," + "9" * 400)
    assert "about 10^399" in pari.out_of_reach(pari.build_candidates(e, known(e))[0][0], known(e), budget)


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


def test_a_print_loop_starting_off_the_offset_or_above_the_first_term_is_refused():
    """Item 53 (next step vii, the user's choice on 2026-09-30). An INDEX loop -- one that prints on every
    iteration -- must start at the offset, or the emitter numbers every term from the wrong index and a
    correct program fails `wrong_term` (A290024, session 11; 26 such loops in the pool). A FILTER loop
    that prints its own variable must start at or below the first known term, or it skips it (A215906,
    session 12; 20 in the pool). Everything else is left to the gate. The fixture's data starts a(1) = 2
    at offset 1."""
    cs, rej = cands("for(n=2, 500, print1(prime(n), \", \"))")           # index loop starting at 2, offset 1
    assert not cs and "starts at n = 2 while the offset is 1" in rej[0].reason
    cs, rej = cands("for(n=1, 500, print1(prime(n), \", \"))")           # at the offset: kept
    assert [c.form for c in cs] == ["print-loop"] and not rej
    cs, rej = cands("for(n=3, 500, if(isprime(n), print1(n, \", \")))")  # filter loop printing n, above a(1) = 2
    assert not cs and "would never reach the first known term a(1) = 2" in rej[0].reason
    cs, rej = cands("for(n=2, 500, if(isprime(n), print1(n, \", \")))")  # at the first value: kept
    assert [c.form for c in cs] == ["print-loop"] and not rej
    assert [c.form for c in cands("for(n=1, 500, if(isprime(n), print1(n, \", \")))")[0]] == ["print-loop"]
    assert [c.form for c in cands("for(n=5, 500, isprime(n) && print1(n, \", \"))")[0]] == []      # a && guard is a filter too
    # an inner loop that only computes the value, followed by a top-level print, is still an index loop
    cs, rej = cands("for(n=2, 500, s=0; for(k=1, n, s+=k); print1(s, \", \"))")
    assert not cs and "starts at n = 2 while the offset is 1" in rej[0].reason
    assert [c.form for c in cands("for(n=1, 500, s=0; for(k=1, n, s+=k); print1(s, \", \"))")[0]] == ["print-loop"]
    assert [c.form for c in cands("for(n=5, 500, if(isprime(n), print1(2*n, \", \")))")[0]] == ["print-loop"]  # prints an expression: not judged
    assert [c.form for c in cands("forprime(p=3, 500, print1(p, \", \"))")[0]] == ["print-loop"]   # not a plain for: not an index loop
    assert [c.form for c in cands("n0=2; for(n=n0, 500, print1(prime(n), \", \"))")[0]] == ["print-loop"]  # non-literal start
    # A290024 exactly: offset 0, loop from 1, printing once per iteration
    cs, rej = cands("for(n=1, 7, print1(n^2, \", \"))", data="0,1,4,9,16,25,36", offset=0)
    assert not cs and "starts at n = 1 while the offset is 0" in rej[0].reason
    # the refusal does not touch a def in the same block: the block still yields the def, and reports nothing
    cs, rej = cands("a(n) = prime(n)\nfor(n=2, 500, print1(a(n), \", \"))")
    assert [c.form for c in cs] == ["a(n)"] and not rej


def test_a_def_whose_only_parameter_has_a_default_is_a_bulk_printer():
    """Item 53 (next step 7's shape, the user's choice on 2026-09-30): `a373945(upto=10^8)` and
    `a368129(rmax=235)` take a search bound, not an index; called with an index they run the search up
    to it and print a list, and the run is a plain timeout with nothing in the row to say why. Measured
    2026-09-30: all 4 such defs in the corpus are bulk printers. A default on a LATER parameter is the
    ordinary drivable shape and stays."""
    cs, rej = cands("a999999(upto=10^8) = {my(s=-1); forprime(p=3, upto, s+=p; print1(s, \", \")); s}")
    assert not cs and "bulk printer" in rej[0].reason and "a999999" in rej[0].reason
    cs, rej = cands("is(n=10^6) = isprime(n)")
    assert not cs and "bulk printer" in rej[0].reason
    assert [c.form for c in cands("a(n, upto=10^8) = n")[0]] == ["a(n)"]
    assert [c.form for c in cands("is(k, b=2) = (k % b) == 0")[0]] == ["predicate"]


def test_a_def_needing_a_second_argument_is_not_driven():
    """gp does not refuse a call that omits an argument -- it binds the parameter to 0 and runs on, so
    the driver would silently compute something else (A366832: `isok(k, b)`, its own loop supplying
    b = 9, reached `digits(k, 0)`). A parameter with a default is fine: gp uses the default."""
    assert not cands("isok(k, b) = (k % b) == 0")[0]
    assert [c.form for c in cands("isok(k, b=2) = (k % b) == 0")[0]] == ["predicate"]
    assert [c.form for c in cands("a(n, k) = prime(n)")[0]] == []
    assert [c.form for c in cands("a(n, k=1) = prime(n)")[0]] == ["a(n)"]
    # every parameter after the first, not a count of those without defaults: gp fills omitted
    # arguments from the left, so `a(n=1, k)` still leaves k at 0 (gp 2.17.4: f(a=1,b)=[a,b]; f(7)
    # gives [7, 0]). Counting would call this one drivable, because only k lacks a default.
    assert [c.form for c in cands("a(n=1, k) = prime(n)")[0]] == []
    # and the other half of the same rule: a def with no parameter at all has nowhere to put the index,
    # and gp refuses the extra argument the drivers would pass
    assert not cands("a() = 5")[0]


def test_parameter_defaults_are_split_at_the_top_level_only():
    """`v=[1, 2]` is one parameter with a default, not two, one of which lacks one."""
    stmt = [s for s in pari.split_statements("a(n, v=[1, 2]) = prime(n)") if s.kind == "def"][0]
    assert stmt.params == ["n", "v"] and stmt.defaults == [False, True]
    assert [c.form for c in cands("a(n, v=[1, 2]) = prime(n)")[0]] == ["a(n)"]


def test_a_block_offers_both_its_def_and_its_own_loop():
    """The generic drivers scan every index from the start and emit the bare value, so a loop that
    restricts the domain or transforms what it prints computes a different sequence. Which one is
    right is not decidable from the text, so both are offered, the def form first, and the gate
    decides -- a def form that fails to verify leaves the loop form its turn in the same attempt."""
    cs, rej = cands("isok(k) = isprime(k)\nforprime(p=2, 10^6, if(isok(p), print1(p, \", \")))")
    assert [c.form for c in cs] == ["predicate", "print-loop"] and not rej
    assert "forprime(p=2, +oo" in cs[1].program.executed
    # the loop keeps its own domain; the predicate driver has none
    assert "forprime" not in cs[0].program.executed


def test_a_block_with_only_one_usable_form_still_offers_only_that_one():
    assert [c.form for c in cands("a(n) = prime(n)")[0]] == ["a(n)"]
    assert [c.form for c in cands("for(n=1, 500, if(isprime(n), print1(n, \",\")))")[0]] == ["print-loop"]


def test_a_block_that_yields_nothing_still_reports_why():
    """The complement of `test_a_call_in_a_dropped_driver_statement_does_not_reject_the_block`, which
    now passes because a form that cannot be built is reported only when the whole block came to
    nothing. That suppression must not swallow the reason when the block really did yield nothing."""
    cs, rej = cands("for(n=1, 10, print(A007947(n)))")
    assert not cs and "A007947" in rej[0].reason
    # nor when a predicate is refused for non-increasing terms and there is no loop to fall back to
    cs2, rej2 = cands("isok(k) = isprime(k)", data="5,3,7")
    # exactly one: the block must not also report "no a(n), predicate, or single print loop" after it
    assert not cs2 and len(rej2) == 1 and "not strictly increasing" in rej2[0].reason


def test_unsupported_shapes_rejected():
    assert not cands("lista(nn) = for(n=1, nn, if(isprime(n), print1(n, \", \")))")[0]
    assert not cands("N=10^4; for(n=1, N, if(isprime(n), print1(n, \", \")))")[0]      # variable outer bound
    assert not cands("for(n=1, 99, print1(n, \", \")); print(\"done\")")[0]              # two prints
    assert "list-printing" in cands("lista(nn) = for(n=1, nn, print1(n))")[1][0].reason


def test_undefined_a_numbers_finds_calls_and_indexes():
    """A call or an index on an unknown name always errors in gp; a bare mention does not -- it stays a
    polynomial variable, so `n + A007947` prints the expression unevaluated and `#A007947` is 2."""
    assert pari.undefined_a_numbers("a(n) = A007947(n)") == ["A007947"]
    assert pari.undefined_a_numbers("a(n) = my(m = a147798[n]); m") == ["a147798"]
    assert pari.undefined_a_numbers("a(n) = A007947(n) + A007947(n+1)") == ["A007947"]   # named once
    assert pari.undefined_a_numbers("a(n) = A1969[n]") == ["A1969"]                      # an abbreviation
    assert pari.undefined_a_numbers("a(n) = n + A007947") == []
    assert pari.undefined_a_numbers("a(n) = #A007947") == []
    assert pari.undefined_a_numbers("a(n) = prime(n)") == []
    assert pari.undefined_a_numbers("a(n) = A007947(n) == 3") == ["A007947"]      # `==` is not a definition


def test_undefined_a_numbers_counts_every_way_a_name_is_defined():
    """Read generously: a name wrongly called undefined would throw away a program that runs."""
    assert pari.undefined_a_numbers("A007947(n) = n; a(n) = A007947(n)") == []
    assert pari.undefined_a_numbers("A007947 = [1, 2]; a(n) = A007947[n]") == []
    assert pari.undefined_a_numbers("A007947 = (n) -> n; a(n) = A007947(n)") == []
    assert pari.undefined_a_numbers("a(n) = my(A007947 = [1]); A007947[n]") == []
    assert pari.undefined_a_numbers("a(n, A007947) = A007947(n)") == []
    assert pari.undefined_a_numbers("a(n, &A007947) = A007947[n]") == []          # by reference
    assert pari.undefined_a_numbers("g = (A007947) -> A007947[1]; a(n) = g([n])") == []   # a closure's
    # a `my(x)` with no value is not a definition: gp errors on calling or indexing x just the same
    assert pari.undefined_a_numbers("a(n) = {my(A007947); A007947(n)}") == ["A007947"]
    # several definitions in one statement, the shape A087636 uses
    assert pari.undefined_a_numbers("A87636 = []; A087636(n) = {A87636[n] = A087636(n-1)}") == []
    # a default value *uses* a name, it does not define it: A242998 reads A000043[n] that way
    assert pari.undefined_a_numbers("a(n, p = A000043[n]) = p") == ["A000043"]
    assert pari.undefined_a_numbers("a(n) = my(m = A034386(n)); m") == ["A034386"]


def test_a_def_with_a_call_inside_a_default_is_a_def():
    """Item 51 (the `_DEF`/`_DEFINES` fix item 46 deferred): `A122172_row(n, p=part(n))={...}` has a call
    inside a default, which the `[^()]*` regexes could not cross -- the statement was classified as a
    call and dropped, the block yielded nothing, and the helper check reported the block's own function
    as undefined."""
    stmt = pari._classify("A122172_row(n, p=part(n)) = vector(n, i, p*i)")
    assert (stmt.kind, stmt.name, stmt.params, stmt.defaults) == ("def", "A122172_row", ["n", "p"], [False, True])
    closure = pari._classify("f = (n, p=part(n)) -> p*n")
    assert (closure.kind, closure.name, closure.params, closure.defaults) == ("def", "f", ["n", "p"], [False, True])
    assert pari._classify("f(n) == 3").kind == "call"                    # a comparison is not a definition
    assert pari._classify("for(n=1, f(n), print(n))").kind == "call"
    assert pari.undefined_a_numbers("A122172_row(n, p=part(n)) = {p*n}; a(n) = A122172_row(n)") == []
    assert pari.undefined_a_numbers("a(n) = my(v = apply((k, q=f(k)) -> A000043[q], [1])); v") == ["A000043"]


def test_helper_names_that_embed_an_a_number_are_checked_whole():
    """Item 51 (next step 5, both halves). The check captures the whole identifier and compares that
    against the block's definitions: `is_A178751` (the prefix form, A274003 in session 11) and
    `a375301_row` (the suffix form, A375302 in session 7) are helpers from other entries; `is_A034293`,
    defined in its own block, is not flagged for the A-number inside it -- the trap item 50 named."""
    assert pari.undefined_a_numbers("is_A274003(n) = is_A178751(n) && n % 2") == ["is_A178751"]
    assert pari.undefined_a_numbers("a(n) = a375301_row(n)[1]") == ["a375301_row"]
    assert pari.undefined_a_numbers("is_A034293(n) = n > 3; a(n) = is_A034293(n)") == []
    assert pari.undefined_a_numbers("a(n) = next_A003309(n)") == ["next_A003309"]
    assert pari.undefined_a_numbers("A076467_vec = [1, 2]; a(n) = A076467_vec[n]") == []
    assert pari.undefined_a_numbers("A076467_vec(n) = [1, 2]; a(n) = A076467_vec(n)[1]") == []


def test_undefined_a_numbers_ignores_strings_and_comments():
    assert pari.undefined_a_numbers('a(n) = print("A007947(n)")') == []
    assert pari.undefined_a_numbers("a(n) = n  \\\\ see A007947(n)") == []
    assert pari.undefined_a_numbers("a(n) = n  /* A007947[n] */") == []


def test_a_block_calling_another_entrys_helper_is_rejected():
    cs, rej = cands("a(n) = A007947(n)")
    assert not cs and "A007947" in rej[0].reason and "another OEIS entry" in rej[0].reason
    cs, rej = cands("isok(k) = A007947(k) == k")          # the predicate form too
    assert not cs and "A007947" in rej[0].reason
    # and the print-loop form, which reaches the check through a different branch (A101759, A287915)
    cs, rej = cands("for(n=1, 999, if(A007947(n) == n, print1(n, \", \")))")
    assert not cs and "A007947" in rej[0].reason


def test_a_helper_the_block_defines_itself_is_not_rejected():
    cs, rej = cands("A007947(n) = factorback(factor(n)[, 1])\na(n) = A007947(n)")
    assert [c.form for c in cs] == ["a(n)"] and not rej
    assert "A007947(n) = factorback" in cs[0].program.executed


def test_a_call_in_a_dropped_driver_statement_does_not_reject_the_block():
    """Only the text that runs is checked: top-level driver statements are dropped for the function
    forms, so a helper named in one is never called."""
    cs, rej = cands("a(n) = prime(n)\nfor(n=1, 10, print(A007947(n)))")
    assert [c.form for c in cs] == ["a(n)"] and not rej
    assert "A007947" not in cs[0].program.executed


def test_one_rejected_block_leaves_the_entrys_other_block_runnable():
    cs, rej = cands("a(n) = A007947(n)", "a(n) = prime(n)")
    assert [c.form for c in cs] == ["a(n)"] and "A007947" not in cs[0].program.executed
    assert len(rej) == 1 and rej[0].block == 1


# ---------------------------------------------------------------- conjectural programs (history item 47)
# A program whose author calls it conjectural reproduces every known term by construction, so the
# verification gate learns nothing from it and the run emits values until max_new_terms stops it.
# Session 10 produced 200 such values twice. The measured class is 7 of 5,781 PARI parts; the words are
# deliberately narrow and test_a_bound_or_assumption_still_builds pins that.

def test_a_conjectural_trailing_comment_rejects_the_whole_part():
    """A162763's shape: a working closed form with the author's disclaimer after it."""
    cs, rej = cands("a(n) = 2*n-2 \\\\ Proved to be an upper bound, conjectured to be exact")
    assert not cs
    assert len(rej) == 1 and "conjectured" in rej[0].reason


def test_the_same_program_without_the_disclaimer_still_builds():
    """A162761's shape -- the one sibling of four whose closed form is PROVED. This is the test that
    pins the pipeline being able to tell them apart at all; before item 47 it could not."""
    cs, rej = cands("a(n) = 2*n-2 \\\\ Proved to be exact, cf. comments")
    assert [c.form for c in cs] == ["a(n)"] and not rej


def test_a_heuristic_comment_line_rejects_the_part():
    """A349899's shape: a standalone comment line above the program."""
    cs, rej = cands("\\\\ This program is heuristic and fails if a(n) is divisible by a large prime\na(n) = prime(n)")
    assert not cs
    assert len(rej) == 1 and "heuristic" in rej[0].reason


def test_a_conjectured_sequence_warning_rejects_the_part():
    """A107263's shape."""
    cs, rej = cands("\\\\ Warning: conjectured sequence.\na(n) = prime(n)")
    assert not cs and "conjectured" in rej[0].reason


def test_a_conjectural_part_does_not_condemn_a_clean_part_beside_it():
    """Per signed part, not per entry. No real entry is this shape, so only a test holds the line."""
    cs, rej = cands("a(n) = 2*n \\\\ conjectured to be exact\n\\\\ _A. Author_, Jan 1 2020\na(n) = prime(n)")
    assert [c.form for c in cs] == ["a(n)"]
    assert "prime(n)" in cs[0].program.executed
    # the reason can only name the BLOCK: Rejected carries no part number, though `label` computes one
    assert len(rej) == 1 and rej[0].block == 1 and "conjectured" in rej[0].reason


def test_a_disclaimer_on_the_entrys_own_loop_rejects_the_part():
    """The check reads the raw part text, not a candidate's script. A top-level driver statement is
    dropped for the function forms and its comments go with it, so a script-based check would miss
    exactly this block. Contrast test_a_call_in_a_dropped_driver_statement_does_not_reject_the_block
    above, which asserts the apparent opposite for a different reason: there the question is what gp
    will execute, here it is what the author said about the arithmetic."""
    cs, rej = cands("for(n=1, 10^6, if(isprime(n), print1(n, \", \"))) \\\\ conjectured to be exact")
    assert not cs and "conjectured" in rej[0].reason


def test_the_word_in_live_code_still_builds():
    """Matched in comments and strings, never in live code: a GP identifier named `heuristic` is a
    false positive a future `sync` could introduce. Two lines on purpose -- `split_statements` breaks
    on newlines, not `;`, so the one-line form is a single `assign` that defines nothing and would be
    rejected with no check present at all."""
    cs, rej = cands("heuristic = 5\na(n) = heuristic*prime(n)")
    assert [c.form for c in cs] == ["a(n)"] and not rej


def test_a_bound_or_assumption_still_builds():
    """The scope fence. `upper bound`, `lower bound` and `assuming` were measured over the whole corpus
    and are dominated by false positives -- optional parameters literally named that, and the
    "assuming the vector A002975 holds enough terms" shape. Widening the word list breaks this."""
    for comment in ("\\\\ Gives an upper bound for a(n)",
                    "\\\\ assuming the vector A000040 holds enough terms",
                    "\\\\ a(n) is probably prime for all n"):
        cs, rej = cands(f"a(n) = prime(n) {comment}")
        assert [c.form for c in cs] == ["a(n)"], comment
        assert not rej, comment


@pytest.mark.parametrize("program, bucket", [
    ("a(n) = prime(n)", "a(n)"),
    ("isok(k) = isprime(k)", "predicate"),
    ("for(n=1, 10^4, if(isprime(n), print1(n, \", \")))", "print-loop"),
    ('lista(nn) = for(n=1, nn, if(isprime(n), print1(n, ", ")))', "list printer only (unsupported)"),
    ("a(n) = A007947(n)", "calls another entry's helper (unrunnable)"),
    # the row item 47 added: "no usable function" would be false -- this defines a perfectly good a(n)
    ("a(n) = prime(n) \\\\ conjectured to be exact", "author calls it conjectural (refused)"),
    ("a(n, k) = prime(n)", "no usable function (unsupported)"),
])
def test_stats_form_buckets(program, bucket):
    """`oeisbot stats --forms` has mis-filed a bucket twice -- item 33's critic and item 47's auditor --
    because it had no test and a wrong row looks exactly like a real measurement. This is that test."""
    from oeisbot.cli import form_bucket
    assert form_bucket(*cands(program)) == bucket


def test_the_conjectural_marker_matches_the_reason_it_is_meant_to():
    """The marker and the reason are separate strings that must stay in sync: the wording was changed
    once and two call sites went on matching the old text. Anything keying on the class uses
    `rejected_as_conjectural`, never a literal."""
    cs, rej = cands("a(n) = prime(n) \\\\ conjectured to be exact")
    assert not cs and pari.rejected_as_conjectural(rej)
    assert rej[0].reason.startswith(pari.CONJECTURAL_REASON)
    # and it must not claim every rejection is conjectural
    assert not pari.rejected_as_conjectural(cands("a(n) = A007947(n)")[1])
    assert not pari.rejected_as_conjectural([])


def test_the_rejection_reason_carries_no_value_from_the_comment():
    """The reason names the matched word and never the surrounding line, so it can never carry a term
    value out of a comment. It reaches `say()` and `db.record_skip`'s detail.

    The digit-glued cases are the ones that matter: the pattern used `\\w*` tails until an audit showed
    `conjectured86` being reported whole, and 86 is a real known term of A162762. `[a-z]*` makes a digit
    in the reason impossible by construction rather than by luck, so any tail that admits `\\w` again
    fails here."""
    cs, rej = cands("a(n) = 2*n \\\\ conjectured that a(20) = 123456789 exactly")
    assert not cs and len(rej) == 1
    assert "conjectured" in rej[0].reason
    assert "123456789" not in rej[0].reason and "20" not in rej[0].reason

    for comment in ("\\\\ conjectured86: a(17) = 86 exactly",
                    "/* conjectured123456789012345678901234567890 */",
                    "\\\\ heuristic_86_beyond_a16"):
        cs, rej = cands(f"a(n) = 2*n {comment}")
        assert not cs and len(rej) == 1, comment
        assert not any(ch.isdigit() for ch in rej[0].reason), (comment, rej[0].reason)
        assert "_" not in rej[0].reason, (comment, rej[0].reason)


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
def test_predicate_driver_stays_below_the_rate_bound():
    """out_of_reach is only sound while no predicate can be tested faster than PREDICATE_MAX_RATE. Time the
    real driver on the cheapest predicate there is, a single comparison: false for every k below L, so the
    first term arrives after exactly L calls."""
    big = 2 * 10**7
    e = entry([f"isok(k) = k >= {big}"], data=f"{big},{big + 1},{big + 2}")
    c = pari.build_candidates(e, known(e))[0][0]
    r = run_attempt(c.program, known(e), Budgets(verify_wall_s=30, extend_wall_s=0), extend=False)
    assert r.verified, (r.stop, r.detail)
    first = r.records[0]                       # includes gp's start-up, a few percent of the total
    rate = (first.value - c.search_start + 1) / first.t
    assert rate * 1.5 < pari.PREDICATE_MAX_RATE, f"{rate:.3g} predicate calls/s: raise PREDICATE_MAX_RATE"


@runtime
@pytest.mark.sandbox
def test_gp_syntax_error_is_a_crash_not_a_hang():
    cs, _ = cands("a(n) = prime(n")   # unbalanced
    e = entry(["a(n) = prime(n"])
    if not cs:
        return
    r = run_attempt(cs[0].program, known(e), FAST)
    assert not r.verified and r.stop in (Stop.CRASH, Stop.INCOMPLETE)
