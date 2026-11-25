"""Verification harness (build step 2), with online feasibility checks (step 3).

Runs a program in the sandbox and checks every term as it streams out, as (index, value) pairs:

  * the first index must be the first known index (the offset), then strictly consecutive
  * every known term must match; the first mismatch kills the run
  * only after *all* known terms are reproduced is anything beyond them recorded as new
  * when verification completes, a searched bound the entry publishes is compared against the rate
    just measured; unreachable within the extension budget -> stop before spending any of it
  * when verification completes, and after each new term, the next term is projected;
    infeasible -> stop; a term running far past a trusted projection -> kill
  * every term is appended to a JSONL log outside the sandbox as it arrives, so a kill
    never loses finished work
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from importlib import resources
from pathlib import Path
from typing import Callable

from . import config, estimate, sandbox
from .config import Budgets
from .sandbox import Limits, RunResult, Status
from .terms import KnownTerms, Program

sys.set_int_max_str_digits(0)

WEAK_VERIFICATION_TERMS = 10   # fewer known terms than this: reproducing them is weak evidence
# A heartbeat line is advisory: it records how far a scan reached and can never make a term, so a
# malformed one is dropped rather than halted on -- killing a sound run over a cosmetic defect in a
# progress report would be a self-inflicted wound. These two bound what a *hostile* one can do.
MAX_HEARTBEAT_CHARS = 200      # `int()` is quadratic and runs in the reader thread under the sandbox's lock
HEARTBEAT_STARTUP_GRACE_S = 0.5   # gp's start-up, which the harness clock counts but the scan does not
# The same ceiling for a term line's *counting* fields -- index, microseconds, work units, bytes. A term's
# own value is deliberately exempt: it is legitimately unbounded, which is why line 31 lifts Python's limit.
# The largest honest quantity here is a byte or microsecond count, far below 10^40; a longer field is a
# forged or broken line. Capping it before `int()` closes the `OverflowError` the float conversions a
# TermRecord needs would otherwise raise in the sandbox's reader thread, which has no exception handler:
# the thread would die, the drain loop would stop, and the run would lose the reason it failed.
# It does NOT close the quadratic-`int()`/`str()` stall, because the value field is exempt and MAX_LINE
# is 1 MiB: measured on this machine, 10^6 digits costs 3.7 s to parse and 13.1 s to render, and the
# thread holds the same lock as `on_tick` throughout. That residue is in known-limitations.md.
MAX_TERM_FIELD_DIGITS = 40
# raised by a driver when the program breaks the contract the driver enforces (codegen.MEMBERS_DRIVER:
# members out of order). The order is then wrong somewhere, so no new term of that run can be trusted.
CONTRACT_ERROR = "OEISBotContractError"


class Stop(str, Enum):
    # program failures (nothing trusted)
    WRONG_TERM = "wrong_term"
    BAD_INDEX = "bad_index"
    PROTOCOL = "protocol"
    CRASH = "crash"
    INCOMPLETE = "incomplete"            # ended by itself before reproducing all known terms
    VERIFY_TIMEOUT = "verify_timeout"
    # resource stops (a failure before verification, an ordinary end after it)
    TIMEOUT = "timeout"
    MEMORY_CAP = "memory_cap"
    CPU_CAP = "cpu_cap"
    DISK_CAP = "disk_cap"
    OUTPUT_CAP = "output_cap"
    LAUNCH_ERROR = "launch_error"
    HARNESS_ERROR = "harness_error"      # our own callback raised (sandbox Status.CALLBACK_ERROR): never the program's fault
    # The caller asked the run in hand to stop (the daemon's stop request, or the end of its window; item
    # 58). It says nothing about the program: outside db.DETERMINISTIC_FAILURES and matched by no clause of
    # db.is_dead_end, so it retires nothing, and select.candidates leaves it out of the failure penalty
    INTERRUPTED = "interrupted"
    # extension-phase stops
    VERIFIED_ONLY = "verified_only"      # extension not requested
    SEARCHED_BOUND = "searched_bound"    # the entry publishes a bound the extension cannot reach
    INFEASIBLE = "infeasible"
    OVER_PREDICTION = "over_prediction"
    EXTEND_BUDGET = "extend_budget"
    MAX_NEW_TERMS = "max_new_terms"
    FINISHED = "finished"                # program ended by itself after verification


_STATUS_TO_STOP = {
    Status.TIMEOUT: Stop.TIMEOUT, Status.MEMORY_CAP: Stop.MEMORY_CAP, Status.CPU_CAP: Stop.CPU_CAP,
    Status.DISK_CAP: Stop.DISK_CAP, Status.OUTPUT_CAP: Stop.OUTPUT_CAP, Status.LAUNCH_ERROR: Stop.LAUNCH_ERROR,
    # a harness bug is recorded as its own stop, outside db.DETERMINISTIC_FAILURES, so it retires nothing
    # (item 51); the sandbox's reason already names the exception, so no stderr tail is appended
    Status.CALLBACK_ERROR: Stop.HARNESS_ERROR,
}
# stops that do not themselves say why the program produced what it did, so the stderr tail is kept
# (see Harness._result). A stop added to `Stop` belongs here only if that is true of it too. `launch_error`
# is deliberately absent: no process ran, so there is no stderr, and its detail names the reason already.
_TAIL_STOPS = frozenset({Stop.INCOMPLETE, Stop.VERIFY_TIMEOUT, Stop.TIMEOUT, Stop.MEMORY_CAP, Stop.CPU_CAP,
                         Stop.DISK_CAP, Stop.OUTPUT_CAP})


@dataclass
class TermRecord:
    n: int
    value: int
    t: float          # wall seconds since start, at arrival
    cpu_s: float      # cumulative, reported by the program's process
    work: int         # cumulative instrumented work
    mem: int          # bytes: peak since the previous term
    dt: float         # this term alone
    dcpu: float
    dwork: int
    kind: str         # 'known' | 'new' | 'unchecked' (gap in known terms) | 'void' (new, then disowned)


@dataclass(frozen=True)
class ScanTracking:
    """What the harness needs to believe a predicate driver's progress heartbeats.

    Supplied by the caller for the PARI predicate form only (`attempt._Attempter.run`), which is the same
    two-gate pattern the searched-bound check uses: a caller gate that knows the form, and a mechanical
    check here that does not take it on trust. `start` is the first k the driver tests, so for that driver
    the position and the count are the same fact twice -- `k - start + 1 == tested` -- and a heartbeat
    that fails the identity is not a heartbeat from the driver we built.

    Without this the frontier would be a bare program self-report. That matters more than it looks: the
    frontier's whole purpose is to let a later run skip a range, so a single bogus heartbeat would skip
    it permanently and invisibly, and the run would honestly report having found nothing."""
    start: int
    max_rate: float            # pari.PREDICATE_MAX_RATE, passed in so this module never imports pari


@dataclass
class Prediction:
    n: int
    unit: str
    seconds: float | None
    seconds_low: float | None
    seconds_high: float | None
    mem_high: float | None
    model: str | None
    trustworthy: bool
    feasible: bool
    risky: bool
    value_dependent: bool
    next_bits_high: int | None
    reasons: list[str]
    actual_s: float | None = None
    actual_cost: float | None = None
    actual_mem: float | None = None
    censored_s: float | None = None   # still running when stopped: actual cost is at least this
    # What the verdict above was made from: the cost fit's own statistics (`estimate.Projection`) and the
    # rate drift. All None together, exactly when nothing could be fitted (`Assessment.cost is None`), so
    # `trustworthy` can be told apart from `fit_trustworthy` -- a sound fit withdrawn from the kill by the
    # drift alone is `trustworthy = 0, fit_trustworthy = 1`. New fields go at the *end*: `Prediction` is
    # built positionally elsewhere, and one inserted mid-list would fill the wrong field silently
    fit_trustworthy: bool | None = None
    fit_npoints: int | None = None
    fit_disagreement: float | None = None
    fit_climbing: bool | None = None
    rate_drift: float | None = None

    @classmethod
    def from_assessment(cls, a: estimate.Assessment, kill_factor: float) -> "Prediction":
        """`trustworthy` is whether the over-prediction kill at `kill_factor` may act on the projection;
        the `fit_*` fields and `rate_drift` are the statistics that verdict was made from."""
        note = a.drift_note(kill_factor)
        c = a.cost
        return cls(a.n, a.unit, a.seconds, a.seconds_low, a.seconds_high, a.mem_high,
                   c.model if c else None, a.trusted(kill_factor),
                   a.feasible, a.risky, a.value_dependent, a.next_bits_high, list(a.reasons) + ([note] if note else []),
                   fit_trustworthy=c.trustworthy if c else None, fit_npoints=c.npoints if c else None,
                   fit_disagreement=c.disagreement if c else None, fit_climbing=c.climbing if c else None,
                   rate_drift=a.rate_drift)


@dataclass
class AttemptResult:
    program: Program
    known: KnownTerms
    outcome: str                   # 'extended' | 'verified' | 'failed'
    stop: Stop
    detail: str
    verified: bool
    reproduced: int
    records: list[TermRecord]
    predictions: list[Prediction]
    run: RunResult
    verified_at_s: float | None = None
    scratch: Path | None = None
    # the memory cap the feasibility check was judged against (`Harness.mem_cap`), which is the budget
    # lowered to the free physical RAM of the moment. `run.mem_cap_bytes` is the sandbox's own reading of
    # the same formula an instant later, so only this one belongs with an `infeasible` verdict
    mem_cap: int = 0
    # How far the predicate driver's scan actually reached, from its progress heartbeats, and what the
    # harness made of them. None when no heartbeat was accepted -- every non-predicate run, and any
    # predicate run killed before its first block finished. `heartbeats_ignored` and
    # `first_bad_heartbeat` exist so a driver bug that mangles every line shows up as a number rather
    # than as silence: without them the frontier would simply never advance and nothing would say why.
    # New fields go at the *end*: this class is built positionally below, and one inserted mid-list
    # would fill the wrong field silently (`Prediction` carries the same warning for the same reason)
    scan_reached: int | None = None
    heartbeats: int = 0
    heartbeats_ignored: int = 0
    first_bad_heartbeat: str | None = None
    # Which budget an `infeasible` stop was reached on ("time", "memory", or both), so the dead-end rule
    # can ask about that budget alone (item 51). Empty on every other stop.
    infeasible_on: list[str] = field(default_factory=list)
    # New terms that land at or below the entry's published searched bound -- a range a human said was
    # empty. `{"bound": str, "quote": str, "indices": [n, ...]}`, or None. Only ever casts doubt (either
    # the published search or this program is wrong); it can never confirm a term (invariant 10). Both
    # fields added 2026-09-30, which invalidated any pending win saved before then (none existed)
    below_bound: dict | None = None

    @property
    def new_terms(self) -> list[TermRecord]:
        return [r for r in self.records if r.kind == "new"] if self.verified else []

    @property
    def cost_unit(self) -> str:
        return "work" if self.records and self.records[-1].work > 0 else "cpu"

    @property
    def peak_mem_bytes(self) -> int:
        """gp commits its whole parisizemax up front on Windows, so the job's commit peak says nothing;
        use the stack high-water mark the driver reports instead."""
        if self.program.language == "gp":
            return max((r.mem for r in self.records), default=0)
        return self.run.peak_mem_bytes

    @property
    def weak_verification(self) -> bool:
        return self.known.count < WEAK_VERIFICATION_TERMS


def _short(v: int) -> str:
    s = str(v)
    return s if len(s) <= 60 else f"{s[:25]}...{s[-25:]} ({len(s)} digits)"


_RULE_CHARS = set("*^-_=~ ")
STDERR_LINE_CHARS = 400        # a program can write 64 KiB of stderr without a single line break
CONSOLE_DETAIL_CHARS = 300     # how much of a detail a session log line carries


def _stderr_tail(res: RunResult, lines: int = 3) -> str:
    """The last few stderr lines that say something, as one line, for a failure detail.

    Blank lines and rules are dropped: gp underlines the offending call with a caret rule on a line of
    its own, and keeping it would push the line that names the call out of a three-line tail. Each line
    is capped, as every other text a program writes into a detail is (`_short`, a malformed term line)."""
    said = [s[:STDERR_LINE_CHARS] for s in (l.strip() for l in res.stderr_tail.strip().splitlines())
            if set(s) - _RULE_CHARS]
    return " | ".join(said[-lines:])


def measured_rate(records: list[TermRecord]) -> tuple[float, float, int] | None:
    """(work per second, the window in seconds, the work done in it) over `records`, or None.

    Module level, not a Harness method, so `attempt` can record exactly the rate the decision was made
    with instead of recomputing it a second way and disagreeing.

    Dropping `records[0]` follows `points()`: the first term carries interpreter start-up, and for gp
    that is most of a short verification -- on the measured runs, about 25 ms of a 28 ms window.
    Including it *understates* the rate, and understating makes the searched-bound skip fire more often,
    which is the unsafe direction for a decision that cannot be undone within a session. Returning None
    when the window collapses is the safe answer for the same reason: gp's stdout is block-buffered, so
    several terms can arrive at nearly the same `t`, and no rate means no skip."""
    if len(records) < 2:
        return None
    first, last = records[0], records[-1]
    window, work = last.t - first.t, last.work - first.work
    if window <= 0 or work <= 0:
        return None
    return work / window, window, work


def brief_detail(detail: str) -> str:
    """A detail cut to one session-log line. A gp error runs to about 180 characters -- the call it could
    not make, the reason, and the file it gave up on -- and is worth carrying whole."""
    return detail if len(detail) <= CONSOLE_DETAIL_CHARS else detail[:CONSOLE_DETAIL_CHARS - 3] + "..."


class Harness:
    def __init__(self, program: Program, known: KnownTerms, budgets: Budgets, *, name: str = "",
                 extend: bool = True, log_path: Path | None = None, searched_bound: "Bound | None" = None,
                 scan: ScanTracking | None = None, should_stop: Callable[[], bool] | None = None):
        self.program, self.known, self.budgets, self.name = program, known, budgets, name
        self.extend = extend
        # asked on every tick; True ends the run as `interrupted` (see Stop.INTERRUPTED)
        self.should_stop = should_stop
        # the caller gate for progress heartbeats: predicate form only (see ScanTracking)
        self.scan = scan
        self.scan_reached: int | None = None
        self.heartbeats = 0
        self.heartbeats_ignored = 0
        self.first_bad_heartbeat: str | None = None
        # `bounds.Bound`, and only for the PARI predicate form (attempt._Attempter.run decides). Annotated
        # as a string so this module never imports bounds: nothing here needs more than .value and .quote
        self.searched_bound = searched_bound
        self.log_path = log_path
        self.records: list[TermRecord] = []
        self.predictions: list[Prediction] = []
        self.reproduced = 0
        self.stop: Stop | None = None
        self.detail = ""
        self.verified_at: float | None = None
        self.term_started_at = 0.0
        self.kill_after: float | None = None
        self.child_error: str | None = None
        self.done = False
        self.infeasible_on: list[str] = []
        self.below_bound: list[int] = []
        self.mem_cap = min(budgets.mem_bytes, sandbox.avail_phys_bytes() - budgets.reserve_phys_bytes)
        # What the memory projection is judged against. The job cap (`mem_cap`) is enforced on the job's
        # commit, but the gp driver reports `default(parisize) + heap` -- the PARI *stack*, which gp
        # commits up to `parisizemax` and errors past ("the PARI stack overflows", an `incomplete`). Those
        # are different quantities ~800x apart, so until 2026-09-30 no gp run could be judged infeasible
        # on memory at all (A277041 reached the job cap reporting 8 MiB throughout). A gp run is now judged
        # against the ceiling it is launched with (`argv`), item 51. Growth outside the stack -- GMP's own
        # allocations, which the job cap does see -- stays invisible to the projection: known-limitations.md
        self.stack_cap: int | None = int(max(self.mem_cap, 1 << 28) * 0.8) if program.language == "gp" else None

    # -------------------------------------------------------------- callbacks (serialized by the sandbox)

    def _halt(self, stop: Stop, detail: str) -> str:
        if self.stop is None:
            self.stop, self.detail = stop, detail
        return f"{stop.value}: {detail}"

    def _drop_heartbeat(self, line: str) -> None:
        self.heartbeats_ignored += 1
        if self.first_bad_heartbeat is None:
            self.first_bad_heartbeat = line[:MAX_HEARTBEAT_CHARS]

    def _on_heartbeat(self, line: str, t: float) -> None:
        """`@P <k reached> <predicate calls made> <cpu us>`: how far the scan has got.

        Never halts and never touches a term. Every rejection below is a case where accepting the line
        would let a later reader believe a range was scanned when it was not:

        * no `scan` -- the caller did not build a predicate driver, so nothing here emits `@P` by
          contract. The mechanical half of the two-gate pattern.
        * over-long -- `int()` is quadratic and this runs in the sandbox's reader thread, which holds the
          same lock as `on_tick`; a program spraying million-digit numbers would stall the harness's own
          clocks rather than its own.
        * identity `k - start + 1 != tested` -- the driver tests every k from `start`, so position and
          count are one fact. A frontier that does not match the work claimed for it is not ours.
        * not advancing, or behind a term already emitted -- the frontier only ever moves forward, and it
          cannot be behind a k the driver has demonstrably tested.
        * faster than any predicate can be tested -- the same ceiling `pari.out_of_reach` is built on,
          with gp's start-up granted because the harness clock includes it and the scan does not.
        """
        if self.scan is None or len(line) > MAX_HEARTBEAT_CHARS:
            self._drop_heartbeat(line)
            return
        parts = line.split()
        try:
            if len(parts) != 4:
                raise ValueError
            k, tested, _cpu_us = (int(p) for p in parts[1:])
        except ValueError:
            self._drop_heartbeat(line)
            return
        last_term = self.records[-1].value if self.records else None
        if (tested <= 0 or k - self.scan.start + 1 != tested
                or (self.scan_reached is not None and k <= self.scan_reached)
                or (last_term is not None and k < last_term)
                or tested > self.scan.max_rate * (max(t, 0.0) + HEARTBEAT_STARTUP_GRACE_S)):
            self._drop_heartbeat(line)
            return
        self.heartbeats += 1
        self.scan_reached = k

    def on_line(self, line: str, t: float) -> str | None:
        # Nothing after the first halt is read. The sandbox ends the job only after the callback that
        # halted has returned and let go of the lock, so the output reader can get more lines in before
        # it sees the stop -- and a run stopped "during verification" could then be recorded as
        # verified, its last known term having arrived a moment later (item 58's review; the same held
        # for a `verify_timeout`). The price is that a real new term arriving in that instant is not
        # counted, as one arriving an instant later never was.
        # One line is still acted on: the driver's contract error. It says the new terms may be
        # misplaced, and voiding them can only take a result away, never grant one
        if self.stop is not None:
            if line.startswith("@ERR") and line[4:].strip().startswith(CONTRACT_ERROR + ":"):
                for rec in self.records:
                    if rec.kind == "new":
                        rec.kind = "void"
            return None
        if not line.startswith("@"):
            return None
        if line.startswith("@DONE"):
            self.done = True
            return None
        if line.startswith("@ERR"):
            self.child_error = line[4:].strip()
            if self.child_error.startswith(CONTRACT_ERROR + ":"):
                # a value that should have come earlier arrived late: every new term may be misplaced
                for rec in self.records:
                    if rec.kind == "new":
                        rec.kind = "void"
                return self._halt(Stop.PROTOCOL, self.child_error)
            return None
        if line.startswith("@P "):
            self._on_heartbeat(line, t)
            return None
        if not line.startswith("@T "):
            return None
        parts = line.split()
        try:
            if len(parts) != 6:
                raise ValueError
            n_s, value_s, cpu_us_s, work_s, mem_s = parts[1:]
            # every field but the value is a count; see MAX_TERM_FIELD_DIGITS for why this is checked
            # here, before `int()`, rather than after
            if any(len(f.lstrip("-")) > MAX_TERM_FIELD_DIGITS for f in (n_s, cpu_us_s, work_s, mem_s)):
                raise ValueError
            n, value, cpu_us = int(n_s), int(value_s), int(cpu_us_s)
            work, mem = int(work_s), int(mem_s)
            cpu_s = cpu_us / 1e6
        # OverflowError is unreachable while the cap above is 40 digits and float() overflows at 309:
        # no mutation covers it, and it is kept deliberately, as `on_line`'s `incomplete` guard below
        # is. It is what stands between a raised cap -- or a sixth field added to the line and left out
        # of the tuple above -- and a dead reader thread, which is a silent failure rather than a loud one.
        except (ValueError, OverflowError):
            return self._halt(Stop.PROTOCOL, f"malformed term line: {line[:200]!r}")

        # The predicate driver's term line states one fact twice, as its heartbeats do (`ScanTracking`):
        # the term IS the k just tested, and `work` counts every k from `start`. A line that breaks the
        # identity was not printed by the driver we built -- the entry's own code wrote something that
        # looks like a term -- and its `work` would go on to set the rate the searched-bound check and
        # the cost fit reason with. Checked before the index and the value, because nothing in a line
        # that is not ours is worth comparing. The detail carries no number. Nothing shows it to the
        # model today (a PARI run reaches a prompt only once verified, through `slow_program_note`), and
        # it is kept value-free so that no later path can: the value on such a line could be a held-out
        # term.
        if self.scan is not None and value - self.scan.start + 1 != work:
            return self._halt(Stop.PROTOCOL, "a term line's work count does not match its value, which "
                                             "the predicate driver's own lines always do")

        prev = self.records[-1] if self.records else None
        expected = prev.n + 1 if prev else self.known.first_index
        if n != expected:
            hint = f" (offset is {self.known.offset})" if prev is None else ""
            return self._halt(Stop.BAD_INDEX, f"program emitted n={n}, expected n={expected}{hint}")

        if n in self.known.values:
            if value != self.known.values[n]:
                return self._halt(Stop.WRONG_TERM, f"a({n}) = {_short(value)}, known value {_short(self.known.values[n])}")
            kind = "known"
            self.reproduced += 1
        elif n < self.known.last_index:
            kind = "unchecked"
        else:
            kind = "new"
        rec = TermRecord(n, value, t, cpu_s, work, mem,
                         dt=t - (prev.t if prev else 0.0), dcpu=cpu_s - (prev.cpu_s if prev else 0.0),
                         dwork=work - (prev.work if prev else 0), kind=kind)
        self.records.append(rec)
        # A new term inside the range the entry's comment calls empty. Noted, never acted on: the term
        # stays a term and the run goes on, because the doubt cuts both ways -- the published search may
        # be the wrong one -- and a human decides which (the artifact README and the inbox say so)
        if kind == "new" and self.searched_bound is not None and value <= self.searched_bound.value:
            self.below_bound.append(n)
        self._log(rec)

        if kind == "new":
            pending = self.predictions[-1] if self.predictions else None
            if pending is not None and pending.n == n:
                pending.actual_s, pending.actual_mem = rec.dt, float(rec.mem)
                pending.actual_cost = float(rec.dwork if pending.unit == "work" else rec.dcpu)
            if len(self.records) - self._index_of_last_known() - 1 >= self.budgets.max_new_terms:
                return self._halt(Stop.MAX_NEW_TERMS, f"reached {self.budgets.max_new_terms} new terms")
            return self._project_next(t)
        if n == self.known.last_index:
            # Unreachable, and kept as a guard. Indices are forced consecutive from known.first_index
            # above, and a known index whose value differs halts before the term is appended, so by the
            # last known index every known index has been emitted and matched: reproduced == count. Were
            # this dropped, that state would set verified_at instead, and the run would go on to spend its
            # whole extension before ending as `failed` with a stop db.is_dead_end does not recognise.
            if self.reproduced != self.known.count:
                return self._halt(Stop.INCOMPLETE, f"reproduced {self.reproduced} of {self.known.count} known terms")
            self.verified_at = t
            if not self.extend:
                return self._halt(Stop.VERIFIED_ONLY, self.known.describe())
            if (why := self._bound_exhausted()) is not None:
                return self._halt(Stop.SEARCHED_BOUND, why)
            return self._project_next(t)
        return None

    # -------------------------------------------------------------- the searched-bound check

    def _bound_exhausted(self) -> str | None:
        """Why the extension cannot reach the bound the entry publishes, or None.

        Each guard is here because its absence caused a measured error (session 9):

        * `work <= 0` -- `work` is hard-coded to 0 for the `a(n)` and print-loop drivers
          (`pari.py` A_DRIVER, _EMIT), so a zero rate would make any bound look unreachable. The caller
          only supplies a bound for the predicate form; this is the mechanical backstop for that.
        * `extend_wall_s <= 0` -- a missing budget recorded as 0.0 made `gap > rate * 0` true for any
          bound while this was being measured, inventing 240.3 s of saving out of nothing.
        * `gap <= 0` -- `bounds.applicable` already filters stale claims, but this is the safety
          boundary, so it does not take that on trust. (Strictly redundant: the threshold on the right is
          always positive here, so a non-positive gap fails that test anyway. Kept as a statement of
          intent, not because it has ever caught anything.)

        The detail deliberately names only the bound and the budget. It reaches the model through
        `codegen.slow_program_note`, whose contract is timing and the stop reason but **never a term
        value**, and the last known term is always held out (`codegen.shown_indices`). Publishing the
        rate and the margin alongside the bound would let `last_value` be recovered exactly, so they go
        to the attempt row's `extra` instead.

        The quote is kept out for a narrower reason than it first appears: `codegen._context` already
        puts `entry.comments[:8]` in the prompt, so for almost every entry this can fire on the model
        sees that line anyway. What `extra` avoids is the *other* path -- a later session replaying this
        row's `detail` into `slow_program_note` through the dead-end branch of `attempt_sequence`, where
        no comments accompany it -- and comments past the eighth."""
        b = self.searched_bound
        if b is None or self.budgets.extend_wall_s <= 0:
            return None
        measured = measured_rate(self.records)
        if measured is None:
            return None
        calls_per_s, _window, _work = measured
        gap = b.value - self.known.values[self.known.last_index]
        if gap <= 0 or gap <= config.SEARCHED_BOUND_MARGIN * calls_per_s * self.budgets.extend_wall_s:
            return None
        return (f"the entry publishes a searched bound of {_short(b.value)}, beyond what the extension "
                f"can reach in {self.budgets.extend_wall_s:g} s at the rate measured while verifying")

    def on_tick(self, t: float) -> str | None:
        # Asked first, so a tick on which the run is both interrupted and out of a budget is recorded as
        # the stop that retires nothing: an interrupted run did not get the time its row would claim. If
        # `should_stop` itself raises, the sandbox reports a callback error (`harness_error`), which
        # retires nothing either
        if self.should_stop is not None and self.should_stop():
            phase = "verification" if self.verified_at is None else "the extension"
            return self._halt(Stop.INTERRUPTED, f"stopped on request {t:.1f} s into the run, during {phase}")
        if self.verified_at is None:
            if t > self.budgets.verify_wall_s:
                return self._halt(Stop.VERIFY_TIMEOUT, f"reproduced {self.reproduced} of {self.known.count} "
                                                       f"known terms within {self.budgets.verify_wall_s:g} s")
            return None
        if t - self.verified_at > self.budgets.extend_wall_s:
            return self._halt(Stop.EXTEND_BUDGET, f"extension budget {self.budgets.extend_wall_s:g} s used")
        if self.kill_after is not None and t - self.term_started_at > self.kill_after:
            p = self.predictions[-1]
            return self._halt(Stop.OVER_PREDICTION,
                              f"a({p.n}) running {t - self.term_started_at:.1f} s, over "
                              f"{self.budgets.over_prediction_factor:g}x the projected {p.seconds_high:.3g} s")
        return None

    # -------------------------------------------------------------- helpers

    def _index_of_last_known(self) -> int:
        return self.known.last_index - self.known.first_index

    def points(self) -> tuple[list[estimate.Point], str]:
        unit = "work" if self.records and self.records[-1].work > 0 else "cpu"
        pts = [estimate.Point(r.n, float(r.dwork if unit == "work" else r.dcpu), r.dt, float(r.mem), r.value)
               for r in self.records[1:]]      # the first term carries interpreter start-up cost
        return pts, unit

    def _project_next(self, t: float) -> str | None:
        n_next = self.records[-1].n + 1
        pts, unit = self.points()
        remaining = self.budgets.extend_wall_s - (t - self.verified_at)
        mem_budget = self.stack_cap if self.stack_cap is not None else self.mem_cap    # like with like, see __init__
        a = estimate.assess(pts, n_next, unit=unit, time_budget_s=remaining, mem_budget=mem_budget, name=self.name)
        self.predictions.append(Prediction.from_assessment(a, self.budgets.over_prediction_factor))
        self.term_started_at = t
        self.kill_after = a.kill_after_s(self.budgets.over_prediction_factor)
        if not a.feasible:
            self.infeasible_on = list(a.infeasible_on)
            return self._halt(Stop.INFEASIBLE, "; ".join(a.reasons))
        return None

    def _log(self, rec: TermRecord) -> None:
        if self.log_path is None:
            return
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({**asdict(rec), "value": str(rec.value)}) + "\n")

    # -------------------------------------------------------------- run

    def argv(self, scratch: Path) -> list[str]:
        if self.program.language == "python":
            (scratch / "candidate.py").write_text(self.program.executed, encoding="utf-8")
            runner = resources.files("oeisbot.runners").joinpath("py_runner.py")
            (scratch / "runner.py").write_text(runner.read_text(encoding="utf-8"), encoding="utf-8")
            return [str(config.SANDBOX_PYTHON), "-B", "-u", "-X", "utf8", "runner.py", "candidate.py"]
        if self.program.language == "gp":
            (scratch / "program.gp").write_text(self.program.executed, encoding="utf-8")
            return [str(config.GP), "-q", "-f", "-D", f"parisizemax={self.stack_cap}", "program.gp"]
        raise ValueError(f"unsupported language {self.program.language!r}")

    def run(self, keep_scratch: bool = False) -> AttemptResult:
        scratch = sandbox.new_scratch_dir(f"{self.known.a_number}-{self.program.language}")
        wall = self.budgets.verify_wall_s + (self.budgets.extend_wall_s if self.extend else 0) + 30
        limits = Limits(wall_s=wall, mem_bytes=self.budgets.mem_bytes, disk_bytes=self.budgets.disk_bytes,
                        reserve_phys_bytes=self.budgets.reserve_phys_bytes,
                        reserve_disk_bytes=self.budgets.reserve_disk_bytes)
        try:
            res = sandbox.run(self.argv(scratch), cwd=scratch, limits=limits, on_line=self.on_line, on_tick=self.on_tick)
        finally:
            if not keep_scratch:
                shutil.rmtree(scratch, ignore_errors=True)
        return self._result(res, scratch if keep_scratch else None)

    def _result(self, res: RunResult, scratch: Path | None) -> AttemptResult:
        stop, detail = self.stop, self.detail
        if stop is None:
            if res.status in _STATUS_TO_STOP:
                stop, detail = _STATUS_TO_STOP[res.status], res.stop_reason or res.status.value
            elif self.verified_at is not None:
                stop, detail = Stop.FINISHED, "program ended after verification"
            elif self.child_error or res.exit_code != 0:
                stop, detail = Stop.CRASH, self.child_error or f"exit code {res.exit_code}: {_stderr_tail(res)}"
            else:
                stop, detail = Stop.INCOMPLETE, f"program ended after {len(self.records)} terms"
        # A program can fail and still exit 0 -- gp prints its error, skips the rest of the file and leaves
        # with status 0 -- so an `incomplete` says why only on stderr. The same holds for a run killed at
        # the verify budget or by a sandbox cap before a single term: nothing else recorded says what it
        # was doing. Every other stop already carries its own cause (`crash` puts the tail in its detail;
        # `protocol`, `bad_index` and `wrong_term` name the line, index or value at fault), and after
        # verification the terms are the evidence, so none of them collects stderr.
        if stop in _TAIL_STOPS and (stop is Stop.INCOMPLETE or not self.records):
            tail = _stderr_tail(res)
            detail = f"{detail}: {tail}" if tail else detail
        verified = self.verified_at is not None and self.reproduced == self.known.count
        last = self.predictions[-1] if self.predictions else None
        # an infeasible projection stops the run before its term starts: there is no running time to censor
        if last is not None and last.actual_s is None and last.feasible and self.verified_at is not None:
            last.censored_s = res.wall_s - self.term_started_at
        new = sum(1 for r in self.records if r.kind == "new")
        outcome = "extended" if verified and new else "verified" if verified else "failed"
        below = None
        if self.below_bound and self.searched_bound is not None:
            below = {"bound": str(self.searched_bound.value), "quote": self.searched_bound.quote,
                     "indices": list(self.below_bound)}
        return AttemptResult(self.program, self.known, outcome, stop, detail, verified, self.reproduced,
                             self.records, self.predictions, res, self.verified_at, scratch, self.mem_cap,
                             self.scan_reached, self.heartbeats, self.heartbeats_ignored,
                             self.first_bad_heartbeat, self.infeasible_on, below)


def run_attempt(program: Program, known: KnownTerms, budgets: Budgets = config.DEFAULT_BUDGETS, *,
                name: str = "", extend: bool = True, log_path: Path | None = None,
                searched_bound: "Bound | None" = None, scan: ScanTracking | None = None,
                should_stop: Callable[[], bool] | None = None) -> AttemptResult:
    return Harness(program, known, budgets, name=name, extend=extend, log_path=log_path,
                   searched_bound=searched_bound, scan=scan, should_stop=should_stop).run()
