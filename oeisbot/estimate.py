"""Feasibility estimation (build step 3).

Inputs are per-term records: the cost of computing term n alone, in instrumented work units
when the program reports them (hardware-independent, smooth) or CPU seconds otherwise.
Cost is converted to seconds with a measured rate, and memory is extrapolated the same way.

Rules implemented here, from the design:
  * fit log(cost) against n; compare exponential, polynomial and ratio-extrapolation models
  * inspect ratios c(n+1)/c(n): a climbing ratio means super-exponential growth, which an
    exponential fit badly underestimates -> use the ratio model
  * odd and even n fitted separately when their costs alternate
  * report a range: the same model fitted with and without the newest point; large
    disagreement -> risky (or skip)
  * flag value-dependent cost ("smallest k such that ...") -> a budgeted open search
  * bound the bit size of the next term before running
"""
from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass, field

WINDOW = 12                  # fit on the most recent points only
MIN_POINTS = 3
TRUST_DISAGREEMENT = 3.0     # with/without newest point may differ by this factor and still be trusted
SKIP_DISAGREEMENT = 10.0
WORK_FLOOR = 50              # below these the per-term cost is dominated by overhead and noise
CPU_FLOOR_S = 0.05
MIN_GRACE_S = 10.0


@dataclass(frozen=True)
class Point:
    n: int
    cost: float      # cost of this term alone, in `unit`
    wall_s: float    # wall seconds for this term alone
    mem: float       # bytes: peak memory while computing this term
    value: int


@dataclass
class Projection:
    n: int
    point: float
    low: float
    high: float
    model: str                 # exp | poly | ratio | flat
    disagreement: float        # high / low
    climbing: bool
    parity_split: bool
    npoints: int
    notes: list[str] = field(default_factory=list)

    @property
    def trustworthy(self) -> bool:
        return self.disagreement <= TRUST_DISAGREEMENT and self.npoints >= 4


@dataclass
class Assessment:
    n: int
    unit: str
    cost: Projection | None
    seconds: float | None          # point estimate for term n
    seconds_low: float | None
    seconds_high: float | None
    mem_high: float | None
    feasible: bool
    risky: bool
    value_dependent: bool
    next_bits_high: int | None
    reasons: list[str] = field(default_factory=list)

    @property
    def exceeds_int64(self) -> bool:
        return self.next_bits_high is not None and self.next_bits_high >= 63

    def kill_after_s(self, factor: float) -> float | None:
        """How long term n may run before it counts as 'way over prediction'. None: budget only."""
        if self.value_dependent or self.seconds_high is None:
            return None
        return max(MIN_GRACE_S, factor * self.seconds_high)


# ------------------------------------------------------------------ fitting primitives

def _ols(xs: list[float], ys: list[float]) -> tuple[float, float]:
    m = len(xs)
    mx, my = sum(xs) / m, sum(ys) / m
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return my, 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, b


def _r2(xs: list[float], ys: list[float]) -> float:
    a, b = _ols(xs, ys)
    my = sum(ys) / len(ys)
    ss_tot = sum((y - my) ** 2 for y in ys)
    if ss_tot == 0:
        return 1.0
    return 1 - sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys)) / ss_tot


def _log_growth(series: list[tuple[int, float]]) -> list[tuple[float, float]]:
    """(midpoint n, d ln cost / dn) between consecutive points."""
    return [((x0 + x1) / 2, (y1 - y0) / (x1 - x0)) for (x0, y0), (x1, y1) in zip(series, series[1:])]


def _predict(model: str, series: list[tuple[int, float]], n: int) -> float:
    """Predicted ln(cost) at n from (n, ln cost) pairs."""
    xs = [x for x, _ in series]
    ys = [y for _, y in series]
    if model == "exp":
        a, b = _ols(xs, ys)
        return a + b * n
    if model == "poly":
        shift = 1 - min(xs) if min(xs) <= 0 else 0
        a, b = _ols([math.log(x + shift) for x in xs], ys)
        return a + b * math.log(max(n + shift, 1))
    if model == "ratio":
        g = _log_growth(series)
        if len(g) >= 2:
            a, b = _ols([m for m, _ in g], [v for _, v in g])
        else:
            a, b = g[0][1], 0.0
        x_last, y_last = series[-1]
        # integrate the fitted growth rate a + b*m from x_last to n
        return y_last + a * (n - x_last) + b * (n * n - x_last * x_last) / 2
    raise ValueError(model)


def _is_climbing(series: list[tuple[int, float]]) -> bool:
    g = _log_growth(series)
    if len(g) < 3:
        return False
    a, b = _ols([m for m, _ in g], [v for _, v in g])
    span = g[-1][0] - g[0][0]
    rises = sum(1 for (_, v0), (_, v1) in zip(g, g[1:]) if v1 > v0)
    return b > 0 and b * span > 0.15 and rises >= 0.6 * (len(g) - 1)


def _parity_series(series: list[tuple[int, float]], n_next: int) -> tuple[list[tuple[int, float]], bool]:
    same = [(x, y) for x, y in series if (x - n_next) % 2 == 0]
    other = [(x, y) for x, y in series if (x - n_next) % 2 != 0]
    if len(same) < MIN_POINTS or len(other) < MIN_POINTS:
        return series, False
    a, b = _ols([x for x, _ in series], [y for _, y in series])
    # medians, so a single outlier (e.g. a jump at the newest term) does not fake an alternation
    r_same = statistics.median(y - (a + b * x) for x, y in same)
    r_other = statistics.median(y - (a + b * x) for x, y in other)
    if abs(r_same - r_other) > math.log(1.5):
        return same, True
    return series, False


def project(points: list[tuple[int, float]], n_next: int) -> Projection | None:
    """Project a positive cost series to n_next. Returns None with fewer than MIN_POINTS points."""
    pts = sorted((n, c) for n, c in points if c > 0)[-WINDOW * 2:]
    if len(pts) < MIN_POINTS:
        return None
    logs = [(n, math.log(c)) for n, c in pts]
    series, parity = _parity_series(logs, n_next)
    series = series[-WINDOW:]
    notes = []
    if parity:
        notes.append("odd/even costs alternate; fitted same-parity terms only")

    climbing = _is_climbing(series)
    if climbing:
        model = "ratio"
        notes.append("growth ratio is climbing (super-exponential); exponential fit would underestimate")
    elif len(series) >= 4:
        # choose by how well each model, fitted without the newest point, predicts it
        x_last, y_last = series[-1]
        errors = {m: abs(_predict(m, series[:-1], x_last) - y_last) for m in ("exp", "poly")}
        model = min(errors, key=errors.get)
    else:
        model = "exp"

    full = _predict(model, series, n_next)
    drop_series = series[:-1]
    drop_model = model if len(drop_series) >= (3 if model == "ratio" else 2) else "exp"
    dropped = _predict(drop_model, drop_series, n_next) if len(drop_series) >= 2 else full
    # disagreement from the raw fits; the reported range never goes below the newest observed
    # cost when costs have been growing
    disagreement = math.exp(min(abs(full - dropped), 700))
    floor = series[-1][1] if series[-1][1] >= series[0][1] else -math.inf
    lo, hi = sorted((max(full, floor), max(dropped, floor)))
    return Projection(
        n=n_next, point=math.exp(min(max(full, floor), 700)), low=math.exp(min(lo, 700)),
        high=math.exp(min(hi, 700)), model=model, disagreement=disagreement, climbing=climbing,
        parity_split=parity, npoints=len(series), notes=notes)


# ------------------------------------------------------------------ assessment

_VALUE_DEPENDENT = re.compile(
    r"\b(smallest|least|minimal|minimum|lowest|first|largest|greatest)\b[^.;]*?"
    r"\b(such that|for which|with|where|whose|that|having|so that)\b", re.IGNORECASE)


def name_suggests_search(name: str) -> bool:
    return bool(_VALUE_DEPENDENT.search(name or ""))


def _value_dependent_by_data(pts: list[Point]) -> bool:
    if len(pts) < 6:
        return False
    y = [math.log(p.cost) for p in pts]
    r2_n = _r2([float(p.n) for p in pts], y)
    r2_v = _r2([math.log(abs(p.value) + 2) for p in pts], y)
    return r2_n < 0.8 and r2_v > r2_n + 0.15


def _bits_bound(points: list[Point], n_next: int) -> int | None:
    recent = points[-8:]
    if not recent:
        return None
    bits = [(p.n, abs(p.value).bit_length()) for p in recent]
    n_last, b_last = bits[-1]
    if len(bits) < 2:
        return b_last * 2 + 1
    incs = [(b1 - b0) / (n1 - n0) for (n0, b0), (n1, b1) in zip(bits, bits[1:]) if n1 != n0]
    step = max(incs[-3:]) if incs else 0.0
    return int(b_last + (n_next - n_last) * max(step, 0.0) * 1.5 + 1)


def cost_floor(unit: str) -> float:
    return WORK_FLOOR if unit == "work" else CPU_FLOOR_S


def assess(points: list[Point], n_next: int, *, unit: str, time_budget_s: float, mem_budget: float,
           name: str = "") -> Assessment:
    """Can term n_next be computed within the time and memory budgets?"""
    reasons: list[str] = []
    fit = [p for p in points if p.cost >= cost_floor(unit) and p.wall_s > 0][-WINDOW * 2:]
    value_dep = name_suggests_search(name) or _value_dependent_by_data(fit)
    bits = _bits_bound(points, n_next)
    if value_dep:
        reasons.append("cost depends on the unknown value (search): n-based extrapolation misleads; budgeted open search")

    # memory: baseline plus projected growth
    mem_high = None
    if points:
        baseline = min(p.mem for p in points)
        growth = [(p.n, p.mem - baseline) for p in points if p.mem - baseline > (1 << 20)]
        mproj = project(growth, n_next)
        mem_high = baseline + mproj.high if mproj else max(p.mem for p in points) * 1.25

    proj = project([(p.n, p.cost) for p in fit], n_next)
    if proj is None:
        cheap = sum(p.wall_s for p in points) < 1.0
        reasons.append(f"only {len(fit)} terms above the noise floor; "
                       + ("all terms so far are cheap" if cheap else "cannot extrapolate"))
        feasible = mem_high is None or mem_high <= mem_budget
        return Assessment(n_next, unit, None, None, None, None, mem_high, feasible, True, value_dep, bits, reasons)

    recent = fit[-5:]
    rate = sum(p.wall_s for p in recent) / sum(p.cost for p in recent)   # wall seconds per cost unit
    s_point, s_low, s_high = proj.point * rate, proj.low * rate, proj.high * rate
    reasons += proj.notes
    risky = value_dep or not proj.trustworthy or proj.climbing
    feasible = True
    if proj.disagreement > TRUST_DISAGREEMENT:
        reasons.append(f"fits with/without newest point disagree {proj.disagreement:.1f}x")
    if not value_dep:
        if s_high > time_budget_s:
            feasible = False
            reasons.append(f"projected {s_high:.3g} s exceeds remaining budget {time_budget_s:.3g} s")
        elif proj.disagreement > SKIP_DISAGREEMENT and s_high > 0.1 * time_budget_s:
            feasible = False
            reasons.append("projection untrustworthy and not negligible against the budget")
    if mem_high is not None and mem_high > mem_budget:
        feasible = False
        reasons.append(f"projected memory {mem_high / 2**30:.2f} GiB exceeds cap {mem_budget / 2**30:.2f} GiB")
    return Assessment(n_next, unit, proj, s_point, s_low, s_high, mem_high, feasible, risky, value_dep, bits, reasons)
