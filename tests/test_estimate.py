import math

import pytest

from oeisbot import estimate
from oeisbot.estimate import Point, assess, project


def series(f, ns):
    return [(n, f(n)) for n in ns]


def test_exponential_growth_is_projected_accurately():
    p = project(series(lambda n: 2.0 ** n, range(10, 26)), 26)
    assert p.model in ("exp", "ratio") and not p.climbing
    assert p.point == pytest.approx(2.0 ** 26, rel=0.05)
    assert p.trustworthy


def test_polynomial_growth_prefers_poly_model():
    p = project(series(lambda n: n ** 3, range(10, 41)), 41)
    assert p.model == "poly"
    assert p.point == pytest.approx(41 ** 3, rel=0.05)


def test_superexponential_growth_detected_and_not_underestimated():
    pts = series(lambda n: float(math.factorial(n)), range(5, 16))
    p = project(pts, 16)
    assert p.climbing and p.model == "ratio"
    assert p.high >= 0.5 * math.factorial(16)
    assert p.point == pytest.approx(math.factorial(16), rel=0.5)
    # the exponential fit this guards against is badly low
    exp_only = math.exp(estimate._predict("exp", [(n, math.log(c)) for n, c in pts], 16))
    assert exp_only < 0.4 * math.factorial(16)


def test_parity_alternation_fits_same_parity_terms():
    f = lambda n: 3.0 ** n * (20 if n % 2 else 1)
    p = project(series(f, range(10, 24)), 25)
    assert p.parity_split
    assert p.point == pytest.approx(f(25), rel=0.1)
    q = project(series(f, range(10, 24)), 24)
    assert q.point == pytest.approx(f(24), rel=0.1)


def test_disagreement_marks_untrustworthy():
    pts = series(lambda n: 2.0 ** n, range(10, 20)) + [(20, 2.0 ** 20 * 50)]
    p = project(pts, 21)
    assert p.disagreement > estimate.TRUST_DISAGREEMENT
    assert not p.trustworthy


def test_too_few_points():
    assert project([(1, 1.0), (2, 2.0)], 3) is None


def pts_from(f_cost, ns, secs_per_unit=1e-6, mem=lambda n: 50e6, value=lambda n: 2 ** n):
    return [Point(n, f_cost(n), f_cost(n) * secs_per_unit, mem(n), value(n)) for n in ns]


def test_assess_converts_work_to_seconds_and_checks_budget():
    pts = pts_from(lambda n: 1000 * 2.0 ** n, range(5, 20))
    a = assess(pts, 20, unit="work", time_budget_s=10_000, mem_budget=4e9)
    assert a.seconds == pytest.approx(1000 * 2 ** 20 * 1e-6, rel=0.05)
    assert a.feasible and not a.risky
    b = assess(pts, 20, unit="work", time_budget_s=100, mem_budget=4e9)
    assert not b.feasible and any("exceeds remaining budget" in r for r in b.reasons)


def test_assess_memory_projection_blocks_infeasible_jobs():
    pts = pts_from(lambda n: 1000 * 2.0 ** n, range(5, 20), mem=lambda n: 20e6 + 1e3 * 2.0 ** n)
    a = assess(pts, 20, unit="work", time_budget_s=1e9, mem_budget=4e9)
    assert a.mem_high == pytest.approx(20e6 + 1e3 * 2 ** 20, rel=0.2)
    assert a.feasible
    b = assess(pts, 20, unit="work", time_budget_s=1e9, mem_budget=5e8)
    assert not b.feasible


def test_value_dependent_names():
    assert estimate.name_suggests_search("Smallest prime p such that p + 2^n is also prime.")
    assert estimate.name_suggests_search("Least k > 0 for which k*2^n + 1 is prime.")
    assert not estimate.name_suggests_search("Number of Hamiltonian cycles in the n X n grid graph.")


def test_value_dependent_assessment_is_a_budgeted_search():
    pts = pts_from(lambda n: 1000 * 2.0 ** n, range(5, 20))
    a = assess(pts, 20, unit="work", time_budget_s=0.001, mem_budget=4e9, name="Least k such that k*2^n+1 is prime")
    assert a.value_dependent and a.risky
    assert a.feasible               # time projection not trusted; the budget caps it instead
    assert a.kill_after_s(2.0) is None


def test_next_term_bit_bound_flags_int64_overflow():
    pts = pts_from(lambda n: 1000.0, range(40, 60), value=lambda n: 2 ** n)
    a = assess(pts, 62, unit="work", time_budget_s=1e9, mem_budget=4e9)
    assert a.next_bits_high >= 63 and a.exceeds_int64


def test_cheap_sequences_are_feasible_but_marked_risky():
    pts = [Point(n, 1.0, 1e-4, 1e7, n) for n in range(1, 10)]
    a = assess(pts, 10, unit="work", time_budget_s=100, mem_budget=4e9)
    assert a.feasible and a.risky and a.cost is None
