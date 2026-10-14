"""Searched bounds published in `%C` comments, and the check that skips an extension because of one.

Every test here attacks a failure that actually happened while the feature was being measured
(`data/session9/resultsS9.md`), not a hypothetical one. No sandbox: the harness is driven in memory with
controlled times, as CLAUDE.md requires, because real sub-second timings on this machine are noisy.
"""
from __future__ import annotations

import json
import re

from oeisbot import bounds, config, db, verify
from oeisbot.bounds import _INDEXED, Bound, applicable, bounds_in, parse_number
from oeisbot.config import Budgets
from oeisbot.sandbox import RunResult, Status
from oeisbot.terms import KnownTerms, Program
from oeisbot.verify import Harness, Stop

# three known terms, last a(3) = 30, so the next unknown index is 4
KNOWN = KnownTerms("A999999", 1, {1: 10, 2: 20, 3: 30}, "data")
PROG = Program("gp", "is(k)=1", origin="test", strategy="pari:predicate")


def drive(bound: Bound | None, *, extend_wall_s: float = 10.0, work=(100, 200, 300)) -> Harness:
    """Reproduce all three known terms at a controlled rate, then return the harness.

    With the default work counts the window is records[-1] - records[0] = 200 work in 2.0 s, so the
    measured rate is 100/s and a 10 s extension reaches 1,000 before the margin, 100 after it."""
    h = Harness(PROG, KNOWN, Budgets(verify_wall_s=60, extend_wall_s=extend_wall_s), searched_bound=bound)
    for i, (n, value) in enumerate(sorted(KNOWN.values.items())):
        h.on_line(f"@T {n} {value} 0 {work[i]} 8000000", float(i))
    return h


# ------------------------------------------------------------------ parsing

def test_parse_number_is_exact_for_every_base_not_only_ten():
    """`Decimal ** int` rounds to 28 significant digits, so an earlier version turned 2^200 into a number
    ending in 92 zeros. 2^63 passed anyway because it is only 19 digits -- which is why base 10 and small
    powers cannot be the whole test set."""
    assert parse_number("2^200") == 2 ** 200
    assert parse_number("3^100") == 3 ** 100
    assert parse_number("2^63") == 2 ** 63
    assert parse_number("10^37") == 10 ** 37
    assert parse_number("1.22*10^26") == 122 * 10 ** 24
    assert parse_number("3203982595205562774973") == 3203982595205562774973


def test_parse_number_reads_the_notations_oeis_actually_uses():
    assert parse_number("2 * 10^38") == 2 * 10 ** 38
    assert parse_number("1.5*10^6") == 1_500_000
    assert parse_number("4,292,000,000") == 4_292_000_000
    assert parse_number("74*10^7") == 740_000_000
    assert parse_number("2.5 * 10^7") == 25_000_000
    assert parse_number("10 billion") == 10 ** 10        # A175492 read as 10 before this
    assert parse_number("no digits here") is None


def test_an_absurd_exponent_is_refused_rather_than_built():
    assert parse_number("10^999999999") is None
    assert parse_number(f"10^{bounds.MAX_EXPONENT}") == 10 ** bounds.MAX_EXPONENT


# ------------------------------------------------------------------ which claims count

def test_an_unindexed_bound_below_the_last_known_term_is_stale():
    """A029495: `No more terms < 10^7` says nothing once a(4) = 58,088,321 is known. Acting on it would
    skip a run on a bound reality has already passed."""
    comments = ["No more terms < 10^7. - _Lars Blomberg_, Oct 01 2011",
                "a(4) found via a parallel GPU search. No other terms < 10^8. - _William Toner_"]
    assert applicable(comments, "A029495", 58_088_321, 5).value == 10 ** 8
    assert applicable(comments[:1], "A029495", 58_088_321, 5) is None


def test_an_indexed_bound_counts_only_for_the_next_unknown_index():
    """A111441 carries `a(16) > 10^14` from when a(16) was unknown, and `a(17) > 8*10^15` now that it is
    not. A bound for an index already computed constrains nothing."""
    comments = ["a(16) > 10^14 if it exists.", "a(17) > 8*10^15. - _Paul W. Dyson_"]
    assert applicable(comments, "A111441", 1_820_988_137_264_459, 17).value == 8 * 10 ** 15


def test_a_bound_for_an_index_beyond_the_next_unknown_is_not_used():
    """A138598's only comment is `a(14) > 10^5` while a(13) is the next unknown. True, current, and about
    a term the pipeline is not about to compute."""
    assert applicable(["a(14) > 10^5."], "A138598", 42703, 13) is None


def test_a_bound_borrowed_from_another_entry_is_rejected():
    """A274994 was the one wrong skip in the hand-checked census: it quotes A001220's 4.97*10^17 while
    its own claim is 2*10^6, which is inside reach."""
    line = ("No more terms up to 2000000, because A280300 has no more terms up to 2000000, "
            "and A001220 has no other terms below 4.97*10^17.")
    assert bounds_in([line], "A274994") == []
    # the entry's own A-number in the sentence must not trigger the guard
    assert bounds_in(["A274994 has no more terms below 10^9."], "A274994")[0].value == 10 ** 9


def test_a_qualified_claim_is_not_a_claim_about_the_next_term():
    """A146566: `No other term multiple of 12 below 10^9` is true and useless -- it says nothing about
    terms that are not multiples of 12. Its other, unqualified comment is the usable one."""
    assert bounds_in(["No other term multiple of 12 below 10^9."], "A146566") == []
    assert bounds_in(["No other term < 10000000."], "A146566")[0].value == 10_000_000


def test_the_phrasings_that_were_being_missed_now_parse():
    """Each of these was found by hand-reading entries the old patterns skipped; the interjection between
    `a(k)` and its comparator was a third of all misses."""
    assert bounds_in(["a(10) (if it exists) is > 10^300."], "A242945")[0].value == 10 ** 300
    assert bounds_in(["a(6), if it exists, is greater than 4*10^8."], "A374166")[0].value == 4 * 10 ** 8
    assert bounds_in(["a(28) if it exists exceeds 10^11."], "A385074")[0].value == 10 ** 11
    assert bounds_in(["Any subsequent terms are > 10^12."], "A077030")[0].value == 10 ** 12
    assert bounds_in(["Next term if it exists is greater than 100000."], "A039774")[0].value == 100_000
    assert bounds_in(["No additional terms up to 10 billion."], "A175492")[0].value == 10 ** 10


def test_an_interjection_may_not_bridge_two_clauses():
    """Widening `a(k) ... > X` is what makes the commonest form parse, so it has to be policed: an
    interjection holding another index, an equals sign or a bare number has run past the clause it
    started in, and would attribute the wrong bound to the wrong index -- here 10^9 to a(7).

    The fixture has to be one the pattern actually matches. An earlier version used `...went past 10^9`,
    which `_COMPARE` does not contain, so the regex found nothing and the guard was never consulted:
    the test passed with the guard removed entirely."""
    assert _INDEXED.search("a(7) = 12345 and a(8) > 10^9."), "the fixture must reach the guard"
    assert bounds_in(["a(7) = 12345 and a(8) > 10^9."], "A000001") == []


def test_the_loose_searched_to_pattern_is_not_used():
    """A088783's `searched to (2^24-1)/3` is a per-candidate *exponent* limit inside a table of search
    limits, while the entry says its next term may be 185. Measured over the deployable pool, no entry
    needs this phrasing, so it is not a pattern -- it only ever added false positives."""
    assert bounds_in(["1000 is corresponding to a number already searched to (2^24-1)/3."], "A088783") == []


# ------------------------------------------------------------------ the check at the boundary

def test_the_check_fires_when_the_bound_is_out_of_reach():
    h = drive(Bound(10 ** 9, "No more terms <= 10^9.", None))
    assert h.stop is Stop.SEARCHED_BOUND
    assert h.verified_at == 2.0                        # verification still succeeded
    assert verify.measured_rate(h.records) == (100.0, 2.0, 200)


def test_the_check_does_not_fire_on_a_bound_the_extension_could_reach():
    """rate 100/s x 10 s x the 10x margin = 10,000 above a(3) = 30, so 5,000 is inside reach and the run
    must go on to project the next term as usual."""
    h = drive(Bound(5_000, "No more terms <= 5000.", None))
    assert h.stop is None
    assert h.predictions, "the run should have gone on to project the next term"


def test_no_bound_means_no_check():
    assert drive(None).stop is None


def test_a_zero_work_count_can_never_fire_the_check():
    """`work` is hard-coded to 0 in the a(n) and print-loop drivers. Without this guard a zero rate makes
    `gap > margin * 0 * extend` true for every bound, which is how a missing budget invented 240 s of
    savings while this was being measured."""
    h = drive(Bound(10 ** 9, "No more terms <= 10^9.", None), work=(0, 0, 0))
    assert h.stop is None
    assert verify.measured_rate(h.records) is None


def test_a_new_term_below_the_published_bound_is_flagged_not_refused():
    """Item 51, the safe direction of invariant 10: a new term inside the range the entry's comment
    calls empty is still a term and the run goes on -- the published search may be the wrong one -- but
    the harness records which indices landed there, and the attempt carries bound, quote and indices
    so the README and the inbox can say the two disagree."""
    h = Harness(PROG, KNOWN, Budgets(verify_wall_s=60, extend_wall_s=10),
                searched_bound=Bound(5_000, "No more terms <= 5000.", None))
    for n, value in sorted(KNOWN.values.items()):
        assert h.on_line(f"@T {n} {value} 0 {n * 100} 8000000", float(n)) is None
    assert h.stop is None                                   # 5,000 is within reach: the check did not fire
    assert h.on_line("@T 4 4000 0 400 8000000", 4.0) is None    # inside the range reported empty
    assert h.on_line("@T 5 6000 0 500 8000000", 5.0) is None    # above it
    assert h.below_bound == [4]
    assert [r.kind for r in h.records[-2:]] == ["new", "new"]   # both still terms: only the doubt is recorded
    res = h._result(RunResult(Status.STOPPED, 0, 5.0, 4.0, 0, 6 << 30, "stop"), None)
    assert res.below_bound == {"bound": "5000", "quote": "No more terms <= 5000.", "indices": [4]}
    assert [t.n for t in res.new_terms] == [4, 5]

    plain = Harness(PROG, KNOWN, Budgets(verify_wall_s=60, extend_wall_s=10))     # no bound: nothing to flag
    for n, value in sorted(KNOWN.values.items()):
        plain.on_line(f"@T {n} {value} 0 {n * 100} 8000000", float(n))
    plain.on_line("@T 4 4000 0 400 8000000", 4.0)
    assert plain._result(RunResult(Status.STOPPED, 0, 5.0, 4.0, 0, 6 << 30, "stop"), None).below_bound is None


def test_a_zero_extension_budget_can_never_fire_the_check():
    assert drive(Bound(10 ** 9, "q", None), extend_wall_s=0).stop is None


def test_a_collapsed_measurement_window_can_never_fire_the_check():
    """gp's stdout is block-buffered, so several terms can arrive at nearly the same `t`. No usable
    rate means no skip, rather than a skip on a rate that is an artifact of buffering."""
    h = Harness(PROG, KNOWN, Budgets(verify_wall_s=60, extend_wall_s=10),
                searched_bound=Bound(10 ** 9, "q", None))
    for n, value in sorted(KNOWN.values.items()):
        h.on_line(f"@T {n} {value} 0 {n * 100} 8000000", 0.0)
    assert h.stop is None


def test_a_stale_bound_reaching_the_harness_still_cannot_fire_it():
    """`applicable` filters these out, but the harness is the safety boundary and does not take that on
    trust: a bound at or below the last known term is a negative gap."""
    assert drive(Bound(30, "q", None)).stop is None
    assert drive(Bound(1, "q", None)).stop is None


# ------------------------------------------------------------------ what the stop means downstream

def _result(h: Harness):
    return h._result(RunResult(Status.EXITED, exit_code=0, wall_s=2.0, cpu_s=2.0, peak_mem_bytes=0,
                               mem_cap_bytes=0, stderr_tail=""), None)


def test_a_searched_bound_stop_is_a_verified_run_with_no_new_terms():
    r = _result(drive(Bound(10 ** 9, "No more terms <= 10^9.", None)))
    assert r.verified is True and r.outcome == "verified" and r.new_terms == []
    assert r.stop is Stop.SEARCHED_BOUND


def test_a_searched_bound_stop_is_not_a_dead_end(tmp_path):
    """Nothing about the sequence has been disproved, so the program must stay runnable. The user asked
    for the stopping point to be recorded instead, so a later attempt can resume rather than start over."""
    conn = db.connect(tmp_path / "t.sqlite3")
    r = _result(drive(Bound(10 ** 9, "No more terms <= 10^9.", None)))
    budgets = Budgets(verify_wall_s=60, extend_wall_s=10)
    db.record_attempt(conn, r, started_at=db.now(),
                      extra={"extend_wall_s": 10.0, "mem_cap_bytes": 1 << 40,
                             "searched_bound": str(10 ** 9), "verified_scan_to": "30"})
    assert db.is_dead_end(conn, "A999999", r.program.sha, KNOWN.count, budgets) is None


def test_the_detail_never_carries_a_held_out_term_value():
    """The detail reaches the model through codegen.slow_program_note, whose contract is timing and the
    stop reason but never a term value -- and the last known term is always held out. Naming the bound is
    safe (it is public and larger than every known term); naming the rate or the margin beside it would
    let the last known term be recovered by arithmetic, and the quote is an entry comment that may list
    terms outright."""
    quote = "No more terms <= 10^9, and 30 is the largest known term."
    # a budget of 7 s so it cannot be confused with the 10x margin or the 100/s rate
    h = drive(Bound(10 ** 9, quote, None), extend_wall_s=7)
    detail = h.detail
    assert h.stop is Stop.SEARCHED_BOUND
    assert quote not in detail
    # The contract as a property rather than a substring hunt: every number the detail mentions must be
    # one of the two public ones -- the published bound and the budget. The measured rate (100/s), the
    # margin (10x) and the last known term (30) must all be absent; and with the rate absent, the last
    # known term cannot be recovered from `bound - margin * rate * extend` either.
    numbers = set(re.findall(r"\d+(?:\.\d+)?", detail))
    assert numbers <= {str(10 ** 9), "7"}, f"detail leaks a number: {detail}"
    assert str(10 ** 9) in detail


def test_a_huge_bound_survives_json_and_the_detail():
    """A069575 publishes `No more terms through 10^5000`. The value is stored as a string because SQLite
    integers stop at 2^63, and `str()` on it needs the interpreter's digit limit lifted."""
    big = 10 ** 5000
    assert len(str(big)) == 5001
    assert json.loads(json.dumps({"searched_bound": str(big)}))["searched_bound"] == str(big)
    h = drive(Bound(big, "No more terms through 10^5000.", None))
    assert h.stop is Stop.SEARCHED_BOUND
    assert len(h.detail) < 200, "a 5001-digit bound must be abbreviated, not printed in full"


def test_an_arrow_does_not_supply_the_comparator():
    """A337671 writes `a(17)? -> 2^9216 - 9216^2 = ...`. A bare `>` that is really the head of an arrow
    made that a 2,775-digit bound on a(17); the interjection `"? -"` holds no `a(`, `=` or digit, so the
    bridge guard did not save it. The `=>` spelling was rejected all along, which is why this looked
    covered."""
    assert bounds_in(["a(17)? -> 2^9216 - 9216^2 = (4^96 - 96^4) + 1"], "A337671") == []
    assert bounds_in(["a(5) => 10^9"], "A000001") == []
    assert bounds_in(["a(5) >= 10^9."], "A000001")[0].value == 10 ** 9   # still parses


def test_a_borrowed_bound_is_rejected_in_the_indexed_form_too():
    """The guard is applied at both call sites; disabling it in the indexed arm alone used to leave every
    test green."""
    assert bounds_in(["a(5) > 10^9, because A001220 has no more terms below that."], "A274994") == []
    assert bounds_in(["a(5) > 10^9."], "A274994")[0].value == 10 ** 9


def test_the_strongest_live_bound_wins():
    """`applicable` takes the max, so an entry that has tightened its bound over the years is read at its
    current strength. That choice also means one mis-parse outranks every correct claim in the same
    entry, which is why the parsing guards above matter as much as they do."""
    comments = ["a(9) > 10^7. - _Michel Marcus_", "a(9) > 10^12. - _Giovanni Resta_"]
    assert applicable(comments, "A000001", 1254, 9).value == 10 ** 12
    assert applicable(list(reversed(comments)), "A000001", 1254, 9).value == 10 ** 12


def test_only_the_predicate_form_is_offered_a_bound(tmp_path):
    """The semantic gate. For a(n) and print-loop the loop variable need not be the term value, and for a
    model program `work` is whatever that program counts -- so a bound must never reach any of them. The
    harness's `work > 0` test is a backstop for the two PARI drivers only; it cannot catch the model
    form, whose runner reports a positive work count of its own."""
    import pytest
    from oeisbot import attempt as attempt_mod
    from oeisbot.ingest import seqfile

    entry = seqfile.parse("\n".join([
        "%I A999999", "%S A999999 10,20,30", "%N A999999 Test sequence.",
        "%C A999999 No more terms <= 10^9.", "%K A999999 nonn,more", "%O A999999 1,1"]))
    seen = {}

    class Sentinel(Exception):
        pass

    def capture(prog, known, budgets, **kw):
        seen["bound"] = kw.get("searched_bound")
        raise Sentinel

    monkey = attempt_mod.run_attempt
    attempt_mod.run_attempt = capture
    try:
        conn = db.connect(tmp_path / "t.sqlite3")
        rep = attempt_mod.SequenceReport("A999999")
        a = attempt_mod._Attempter(conn, entry, KNOWN, Budgets(verify_wall_s=60, extend_wall_s=10),
                                   None, rep, lambda m: None, False)
        for form, expected in (("predicate", True), ("a(n)", False), ("print-loop", False), ("model", False)):
            seen.clear()
            with pytest.raises(Sentinel):
                a.run(PROG, form)
            assert (seen["bound"] is not None) is expected, f"form {form} got {seen['bound']!r}"
    finally:
        attempt_mod.run_attempt = monkey
