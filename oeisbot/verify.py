"""Verification harness (build step 2), with online feasibility checks (step 3).

Runs a program in the sandbox and checks every term as it streams out, as (index, value) pairs:

  * the first index must be the first known index (the offset), then strictly consecutive
  * every known term must match; the first mismatch kills the run
  * only after *all* known terms are reproduced is anything beyond them recorded as new
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

from . import config, estimate, sandbox
from .config import Budgets
from .sandbox import Limits, RunResult, Status
from .terms import KnownTerms, Program

sys.set_int_max_str_digits(0)

WEAK_VERIFICATION_TERMS = 10   # fewer known terms than this: reproducing them is weak evidence
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
    # extension-phase stops
    VERIFIED_ONLY = "verified_only"      # extension not requested
    INFEASIBLE = "infeasible"
    OVER_PREDICTION = "over_prediction"
    EXTEND_BUDGET = "extend_budget"
    MAX_NEW_TERMS = "max_new_terms"
    FINISHED = "finished"                # program ended by itself after verification


_STATUS_TO_STOP = {
    Status.TIMEOUT: Stop.TIMEOUT, Status.MEMORY_CAP: Stop.MEMORY_CAP, Status.CPU_CAP: Stop.CPU_CAP,
    Status.DISK_CAP: Stop.DISK_CAP, Status.OUTPUT_CAP: Stop.OUTPUT_CAP, Status.LAUNCH_ERROR: Stop.LAUNCH_ERROR,
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

    @classmethod
    def from_assessment(cls, a: estimate.Assessment, kill_factor: float) -> "Prediction":
        """`trustworthy` is whether the over-prediction kill at `kill_factor` may act on the projection."""
        note = a.drift_note(kill_factor)
        return cls(a.n, a.unit, a.seconds, a.seconds_low, a.seconds_high, a.mem_high,
                   a.cost.model if a.cost else None, a.trusted(kill_factor),
                   a.feasible, a.risky, a.value_dependent, a.next_bits_high, list(a.reasons) + ([note] if note else []))


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


def brief_detail(detail: str) -> str:
    """A detail cut to one session-log line. A gp error runs to about 180 characters -- the call it could
    not make, the reason, and the file it gave up on -- and is worth carrying whole."""
    return detail if len(detail) <= CONSOLE_DETAIL_CHARS else detail[:CONSOLE_DETAIL_CHARS - 3] + "..."


class Harness:
    def __init__(self, program: Program, known: KnownTerms, budgets: Budgets, *, name: str = "",
                 extend: bool = True, log_path: Path | None = None):
        self.program, self.known, self.budgets, self.name = program, known, budgets, name
        self.extend = extend
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
        self.mem_cap = min(budgets.mem_bytes, sandbox.avail_phys_bytes() - budgets.reserve_phys_bytes)

    # -------------------------------------------------------------- callbacks (serialized by the sandbox)

    def _halt(self, stop: Stop, detail: str) -> str:
        if self.stop is None:
            self.stop, self.detail = stop, detail
        return f"{stop.value}: {detail}"

    def on_line(self, line: str, t: float) -> str | None:
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
        if not line.startswith("@T "):
            return None
        parts = line.split()
        try:
            if len(parts) != 6:
                raise ValueError
            n, value, cpu_us, work, mem = (int(p) for p in parts[1:])
        except ValueError:
            return self._halt(Stop.PROTOCOL, f"malformed term line: {line[:200]!r}")

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
        cpu_s = cpu_us / 1e6
        rec = TermRecord(n, value, t, cpu_s, work, mem,
                         dt=t - (prev.t if prev else 0.0), dcpu=cpu_s - (prev.cpu_s if prev else 0.0),
                         dwork=work - (prev.work if prev else 0), kind=kind)
        self.records.append(rec)
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
            if self.reproduced != self.known.count:
                return self._halt(Stop.INCOMPLETE, f"reproduced {self.reproduced} of {self.known.count} known terms")
            self.verified_at = t
            if not self.extend:
                return self._halt(Stop.VERIFIED_ONLY, self.known.describe())
            return self._project_next(t)
        return None

    def on_tick(self, t: float) -> str | None:
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
        a = estimate.assess(pts, n_next, unit=unit, time_budget_s=remaining, mem_budget=self.mem_cap, name=self.name)
        self.predictions.append(Prediction.from_assessment(a, self.budgets.over_prediction_factor))
        self.term_started_at = t
        self.kill_after = a.kill_after_s(self.budgets.over_prediction_factor)
        if not a.feasible:
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
            parisizemax = int(max(self.mem_cap, 1 << 28) * 0.8)
            return [str(config.GP), "-q", "-f", "-D", f"parisizemax={parisizemax}", "program.gp"]
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
        return AttemptResult(self.program, self.known, outcome, stop, detail, verified, self.reproduced,
                             self.records, self.predictions, res, self.verified_at, scratch)


def run_attempt(program: Program, known: KnownTerms, budgets: Budgets = config.DEFAULT_BUDGETS, *,
                name: str = "", extend: bool = True, log_path: Path | None = None) -> AttemptResult:
    return Harness(program, known, budgets, name=name, extend=extend, log_path=log_path).run()
