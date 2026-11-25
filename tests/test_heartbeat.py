"""Progress heartbeats: what the predicate driver reports, and what the harness will believe.

The frontier exists so that a later run can be told a range was already scanned. That makes a wrong
frontier worse than no frontier -- it would skip the range permanently, and the run would honestly
report finding nothing -- so most of this file is about the lines the harness refuses.
"""
from __future__ import annotations

import pytest

from oeisbot import sandbox
from oeisbot.config import Budgets
from oeisbot.ingest.seqfile import parse
from oeisbot.strategies import pari
from oeisbot.terms import KnownTerms, Program
from oeisbot.verify import MAX_HEARTBEAT_CHARS, Harness, ScanTracking, TermRecord, run_attempt

KNOWN = KnownTerms("A999999", 1, {1: 10, 2: 20, 3: 30}, "data")
FAST = Budgets(verify_wall_s=20, extend_wall_s=5)
MAX_RATE = 2e7


def harness(scan: ScanTracking | None = ScanTracking(1, MAX_RATE)) -> Harness:
    return Harness(Program("gp", "x", origin="test", strategy="pari:predicate"), KNOWN, FAST, scan=scan)


def beat(k: int, tested: int | None = None, cpu_us: int = 1000) -> str:
    """The driver tests every k from `start` = 1, so `tested` defaults to the value that keeps the
    position and the work count consistent -- the identity the harness checks."""
    return f"@P {k} {k if tested is None else tested} {cpu_us}"


# ------------------------------------------------------------------ the accepted path

def test_a_heartbeat_moves_the_frontier():
    h = harness()
    assert h.on_line(beat(10_000), 1.0) is None       # never halts, never returns a stop
    assert h.scan_reached == 10_000 and h.heartbeats == 1 and h.heartbeats_ignored == 0


def test_the_frontier_is_the_latest_accepted_position():
    h = harness()
    for k in (10_000, 30_000, 70_000):
        h.on_line(beat(k), 1.0)
    assert h.scan_reached == 70_000 and h.heartbeats == 3


# ------------------------------------------------------------------ the refusals

@pytest.mark.parametrize("line", [
    "@P ",                         # the prefix and nothing else
    "@P 10000",                    # too few
    "@P 10000 10000 1000 extra",   # too many
    "@P ten 10000 1000",           # not a number
    "@P 10000 10000 1e6",          # not an integer literal
])
def test_a_malformed_heartbeat_is_dropped_not_fatal(line):
    """A heartbeat can never make a term, so a cosmetic defect in one must not kill a sound run."""
    h = harness()
    assert h.on_line(line, 1.0) is None
    assert h.stop is None and h.scan_reached is None and h.heartbeats_ignored == 1


def test_without_the_caller_gate_no_heartbeat_counts():
    """The mechanical half of the two-gate pattern: only the predicate driver is built to emit these,
    so a model-written program printing `@P` must move nothing."""
    h = harness(scan=None)
    h.on_line(beat(10_000), 1.0)
    assert h.scan_reached is None and h.heartbeats == 0 and h.heartbeats_ignored == 1


def test_the_work_identity_is_required():
    """`k - start + 1 == tested`: for this driver the position and the work are one fact, so a frontier
    that does not match the work claimed for it did not come from the driver we built."""
    h = harness()
    h.on_line(beat(10_000, tested=9_999), 1.0)
    assert h.scan_reached is None and h.heartbeats_ignored == 1


def test_a_frontier_that_claims_no_work_is_rejected():
    h = harness()
    h.on_line(beat(0, tested=0), 1.0)          # identity holds (0 - 1 + 1 == 0) but nothing was scanned
    assert h.scan_reached is None and h.heartbeats_ignored == 1


@pytest.mark.parametrize("second", [5_000, 10_000])
def test_the_frontier_only_moves_forward(second):
    h = harness()
    h.on_line(beat(10_000), 1.0)
    h.on_line(beat(second), 2.0)
    assert h.scan_reached == 10_000 and h.heartbeats == 1 and h.heartbeats_ignored == 1


def test_a_frontier_behind_an_emitted_term_is_rejected():
    """A term at k proves the driver tested k; a later heartbeat below it contradicts the run itself."""
    h = harness()
    h.records.append(TermRecord(n=1, value=50_000, t=1.0, cpu_s=1.0, work=50_000, mem=0,
                                dt=1.0, dcpu=1.0, dwork=50_000, kind="known"))
    h.on_line(beat(40_000), 2.0)
    assert h.scan_reached is None and h.heartbeats_ignored == 1


def test_a_frontier_faster_than_any_predicate_is_rejected():
    """The ceiling `pari.out_of_reach` is built on, so a bogus jump cannot buy a skip that no machine
    could have earned. gp's start-up is granted because the harness clock counts it and the scan does not."""
    h = harness()
    h.on_line(beat(2 * 10**7), 0.0)            # 2e7 calls claimed before the clock has moved
    assert h.scan_reached is None and h.heartbeats_ignored == 1
    h.on_line(beat(2 * 10**7), 10.0)           # the same claim, with time enough to have made it
    assert h.scan_reached == 2 * 10**7


def test_an_over_long_heartbeat_is_dropped_before_parsing():
    """`int()` is quadratic and this runs in the sandbox's reader thread, which holds the same lock as
    the harness's own clock: a program spraying huge numbers would stall the timers that kill it.

    The line below is one the harness would otherwise ACCEPT -- valid fields, honest arithmetic, padded
    only with spaces -- so it isolates the length cap. A line of huge *numbers* is refused by the rate
    ceiling as well, and so proves nothing about the cap on its own."""
    h = harness()
    padded = "@P 10000 " + " " * (MAX_HEARTBEAT_CHARS * 2) + " 10000 1000"
    h.on_line(padded, 1.0)
    assert h.scan_reached is None and h.heartbeats_ignored == 1
    assert len(h.first_bad_heartbeat) <= MAX_HEARTBEAT_CHARS
    # the same content inside the cap is accepted, so the length is doing the work and nothing else
    h2 = harness()
    h2.on_line("@P 10000  10000 1000", 1.0)
    assert h2.scan_reached == 10_000


def test_the_first_bad_line_is_kept_and_counted():
    """A driver bug that mangles every line would otherwise be silence: the frontier just never moves."""
    h = harness()
    h.on_line("@P bad first", 1.0)
    h.on_line("@P bad second", 2.0)
    assert h.heartbeats_ignored == 2 and h.first_bad_heartbeat == "@P bad first"


# ------------------------------------------------------------------ the same identity on a term line

def term(n: int, value: int, work: int | None = None, start: int = 1) -> str:
    """A predicate driver's term line: the term is the k just tested and `work` counts every k from
    `start`, so `work` defaults to the count that agrees with the value."""
    return f"@T {n} {value} 1000 {value - start + 1 if work is None else work} 8000000"


def test_a_term_line_that_keeps_the_identity_is_a_term():
    h = harness()
    assert h.on_line(term(1, 10), 1.0) is None
    assert h.stop is None and h.reproduced == 1 and h.records[0].work == 10


@pytest.mark.parametrize("work", [9, 11, 0])
def test_a_term_line_that_breaks_the_identity_is_not_ours(work):
    """The value is right and the index is right, so nothing else would refuse this line: only the work
    count says the driver we built did not print it. It is a protocol stop, and the detail carries no
    digit at all: nothing shows it to the model today, and it is kept that way because a forged line's
    value could be a held-out term."""
    h = harness()
    said = h.on_line(term(1, 10, work=work), 1.0)
    assert h.stop is not None and h.stop.value == "protocol" and said.startswith("protocol: ")
    assert h.records == [] and h.reproduced == 0
    assert not any(ch.isdigit() for ch in h.detail)


def test_the_term_identity_is_measured_from_the_scan_start():
    """`start` is not always 1: a sequence whose first term is 0 is scanned from 0."""
    h = harness(ScanTracking(0, MAX_RATE))
    assert h.on_line(term(1, 10, start=0), 1.0) is None and h.reproduced == 1      # work 11
    h2 = harness(ScanTracking(0, MAX_RATE))
    h2.on_line(term(1, 10), 1.0)                                                    # work 10: start 1's count
    assert h2.stop is not None and h2.stop.value == "protocol"


def test_the_term_identity_is_broken_before_the_value_is_compared():
    """A forged line is refused as forged, not as a wrong term: nothing in it is worth comparing, and a
    `wrong_term` detail would print the value it carries."""
    h = harness()
    h.on_line(term(1, 11, work=3), 1.0)        # the wrong value AND the wrong count
    assert h.stop.value == "protocol"


def test_without_the_caller_gate_a_term_line_is_not_checked():
    """The a(n) and print-loop drivers hard-code `work` to 0 and a Python program counts its own work,
    so the identity means nothing there and must not be applied."""
    h = harness(scan=None)
    assert h.on_line("@T 1 10 1000 0 8000000", 1.0) is None
    assert h.stop is None and h.reproduced == 1


# ------------------------------------------------------------------ the real driver

pytestmark_sandbox = pytest.mark.skipif(bool(sandbox.runtime_problems()),
                                        reason="; ".join(sandbox.runtime_problems()))


def _candidate(src: str, data: str):
    lines = [f"%S A999999 {data}", "%N A999999 Test.", "%O A999999 1,1", "%K A999999 nonn,more",
             f"%o A999999 (PARI) {src}"]
    e = parse("\n".join(lines) + "\n")
    kn = KnownTerms(e.a_number, e.offset, e.data_values, "data")
    return pari.build_candidates(e, kn)[0][0], kn


@pytest.mark.sandbox
@pytestmark_sandbox
def test_the_driver_reports_a_frontier_and_the_block_grows():
    """The heartbeat cadence is in time, not in k, so the block must actually adapt -- a block fixed in
    k would go hours without a report on an expensive predicate."""
    big = 3 * 10**7
    cand, kn = _candidate(f"isok(k) = k >= {big}", f"{big},{big + 1},{big + 2}")
    r = run_attempt(cand.program, kn, Budgets(verify_wall_s=180, extend_wall_s=0), extend=False,
                    scan=ScanTracking(cand.search_start, pari.PREDICATE_MAX_RATE))
    assert r.verified, (r.stop, r.detail)
    assert r.heartbeats > 5 and r.heartbeats_ignored == 0
    assert r.scan_reached is not None and r.scan_reached > pari.HEARTBEAT_BLOCK0 * 4


@pytest.mark.sandbox
@pytestmark_sandbox
def test_terms_are_unchanged_across_block_seams(monkeypatch):
    """The block boundary is the one place the rewrite could duplicate or skip a k. A duplicate emits one
    value under two indices and a skip loses a term, and above the known terms neither is visible -- so
    force a tiny block and check the terms against a predicate whose answers are known by hand."""
    monkeypatch.setattr(pari, "HEARTBEAT_BLOCK0", 10)
    values = [3 * i for i in range(1, 11)]                   # 3, 6, ... 30, crossing several seams
    cand, kn = _candidate("isok(k) = k % 3 == 0", ",".join(str(v) for v in values))
    assert "oeisbot_blk = 10" in cand.program.executed       # the small block really reached the driver
    r = run_attempt(cand.program, kn, Budgets(verify_wall_s=60, extend_wall_s=0), extend=False,
                    scan=ScanTracking(cand.search_start, pari.PREDICATE_MAX_RATE))
    assert r.verified and r.reproduced == len(values), (r.stop, r.detail)
    assert [rec.value for rec in r.records] == values
    assert r.heartbeats_ignored == 0


@pytest.mark.sandbox
@pytestmark_sandbox
def test_the_block_shrinks_when_a_predicate_turns_expensive(monkeypatch):
    """Growth alone is not enough. Predicate cost climbs with k -- this project has measured a per-term
    cost swinging from under a millisecond to 153 s inside one sequence -- so a block calibrated while
    calls were cheap can swallow hours once they are not, losing exactly the progress the heartbeat
    exists to keep. The block must come back down."""
    monkeypatch.setattr(pari, "HEARTBEAT_BLOCK0", 100)
    monkeypatch.setattr(pari, "HEARTBEAT_TARGET_MS", 20)
    # cheap until k = 60000, then ~1000x dearer per call, so the block overruns the target and must halve
    src = "isok(k) = if(k >= 60000, for(i = 1, 2000, 1)); k % 100000 == 0"
    cand, kn = _candidate(src, "100000,200000")
    seen = []
    h = Harness(cand.program, kn, Budgets(verify_wall_s=120, extend_wall_s=0), extend=False,
                scan=ScanTracking(cand.search_start, pari.PREDICATE_MAX_RATE))
    inner = h._on_heartbeat

    def spy(line, t):
        inner(line, t)
        if h.scan_reached is not None and (not seen or seen[-1] != h.scan_reached):
            seen.append(h.scan_reached)

    h._on_heartbeat = spy
    r = h.run()
    assert r.heartbeats_ignored == 0, r.first_bad_heartbeat
    blocks = [b - a for a, b in zip(seen, seen[1:])]
    assert blocks, "no heartbeats to measure"
    # an actual decrease, not just min < max: a block that only ever grew would satisfy that too
    assert any(b < a for a, b in zip(blocks, blocks[1:])), f"the block never came back down: {blocks}"


@pytest.mark.sandbox
@pytestmark_sandbox
def test_a_frontier_never_names_a_k_the_driver_has_not_tested():
    """The heartbeat prints after its block, so the frontier lags the true position by up to one block
    and can never lead it. Understating is the safe direction: it can only cost a later run time."""
    cand, kn = _candidate("isok(k) = k % 1000 == 0", "1000,2000,3000,4000,5000")
    r = run_attempt(cand.program, kn, Budgets(verify_wall_s=60, extend_wall_s=0), extend=False,
                    scan=ScanTracking(cand.search_start, pari.PREDICATE_MAX_RATE))
    assert r.verified, (r.stop, r.detail)
    assert r.scan_reached is None or r.scan_reached <= max(rec.value for rec in r.records) + pari.HEARTBEAT_BLOCK0
