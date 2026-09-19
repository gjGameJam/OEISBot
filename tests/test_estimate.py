import math

import pytest

from oeisbot import estimate, sandbox
from oeisbot.config import Budgets
from oeisbot.estimate import Point, assess, project
from oeisbot.terms import KnownTerms, Program
from oeisbot.verify import Harness, Prediction


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


def test_kill_threshold_needs_a_trustworthy_projection():
    steady = pts_from(lambda n: 1000 * 2.0 ** n, range(5, 20), secs_per_unit=1e-9)   # a(20) about 1 s
    a = assess(steady, 20, unit="work", time_budget_s=10_000, mem_budget=4e9)
    assert a.cost.trustworthy and 2 * a.seconds_high < estimate.MIN_GRACE_S < 100 * a.seconds_high
    assert a.rate_drift == pytest.approx(1.0) and a.trusted(2.0)     # a constant rate leaves the kill in place
    assert a.kill_after_s(2.0) == estimate.MIN_GRACE_S
    assert a.kill_after_s(100.0) == pytest.approx(100 * a.seconds_high)
    stored = Prediction.from_assessment(a, 2.0)
    assert stored.trustworthy and stored.reasons == a.reasons
    # climbing (so risky) but trustworthy: still killed, from the high estimate rather than the point one
    climbing = pts_from(lambda n: float(math.factorial(n)), range(5, 16), secs_per_unit=1e-12)   # a(16) about 20 s
    d = assess(climbing, 16, unit="work", time_budget_s=10_000, mem_budget=4e9)
    assert d.risky and d.cost.climbing and d.cost.trustworthy and d.seconds < d.seconds_high
    assert d.kill_after_s(2.0) == pytest.approx(2 * d.seconds_high) and d.kill_after_s(2.0) > estimate.MIN_GRACE_S
    # the newest term jumped: fits with and without it disagree
    jump = pts_from(lambda n: 1000 * 2.0 ** n * (50 if n == 19 else 1), range(5, 20))
    b = assess(jump, 20, unit="work", time_budget_s=10_000, mem_budget=4e9)
    assert b.cost.disagreement > estimate.TRUST_DISAGREEMENT and b.seconds_high is not None
    assert b.kill_after_s(2.0) is None
    stored = Prediction.from_assessment(b, 2.0)
    assert not stored.trustworthy and stored.reasons == b.reasons    # the drift note is only for a trusted fit
    # three points agree perfectly, but three are too few to trust
    few = pts_from(lambda n: 1000 * 2.0 ** n, range(17, 20))
    c = assess(few, 20, unit="work", time_budget_s=10_000, mem_budget=4e9)
    assert c.cost.npoints == 3 and c.cost.disagreement == pytest.approx(1.0) and c.seconds_high is not None
    assert c.kill_after_s(2.0) is None


# The points each run's harness had when verification completed in session 5 (2026-09-18), from its term
# log as Point(n, cost, wall_s, mem, value); the first term is left out, as in Harness.points(). Both runs
# were killed for over-prediction, 23.6 s and 10.3 s into the term (at 2x the high estimate for A277532, at
# the 10 s floor for A390295).
A277532_NAME = ("Position of first occurrence of at least n consecutive equal digits in the decimal expansion "
                "of the Euler-Mascheroni constant, starting after the decimal point.")
A277532_POINTS = [  # cpu seconds
    Point(2, 0.0, 0.00044239999260753393, 8004024, 1),
    Point(3, 0.0, 0.00025020004250109196, 8004232, 72),
    Point(4, 0.75, 1.19768149999436, 8007064, 2346),
    Point(5, 1.7029999999999998, 2.03794830001425, 8008408, 3422),
    Point(6, 1.125, 1.5325282999547198, 8008984, 3892),
]
A390295_NAME = "Average k of twin prime pairs such that gcd(d^2 - 4, k) = 1 for only one divisor d of k."
A390295_POINTS = [  # work units
    Point(2, 2, 0.00043479999294504523, 8001528, 6),
    Point(3, 6, 0.00019510003039613366, 8001528, 12),
    Point(4, 18, 0.00017799995839595795, 8001528, 30),
    Point(5, 30, 0.0003389000194147229, 8001528, 60),
    Point(6, 132, 0.00019180000526830554, 8001528, 192),
    Point(7, 48, 0.00017850002041086555, 8001528, 240),
    Point(8, 15120, 0.0033303999807685614, 8001528, 15360),
    Point(9, 771072, 0.23285799997393042, 8001528, 786432),
]


@pytest.mark.parametrize("points, unit, name, recorded_high", [
    (A277532_POINTS, "cpu", A277532_NAME, 11.70123571181761),
    (A390295_POINTS, "work", A390295_NAME, 2.4808095622155784),
], ids=["A277532", "A390295"])
def test_session5_untrustworthy_projections_do_not_kill(points, unit, name, recorded_high):
    a = assess(points, points[-1].n + 1, unit=unit, time_budget_s=1800, mem_budget=6 * 2 ** 30, name=name)
    assert a.seconds_high == pytest.approx(recorded_high, rel=1e-9)   # the replay matches predictions.predicted_s_high
    assert a.feasible and not a.value_dependent and not a.cost.trustworthy
    assert a.kill_after_s(2.0) is None


# A377248's points when a(7) was projected, replayed from its term log (database session 4, 2026-09-17). That run
# never verified (it timed out at a(8)), so no prediction was stored: the high estimate below is pinned from the
# replay, not from the database. a(7) took 78.5 s.
A377248_NAME = "Numbers k such that 8191 * 2^k + 1 is prime."
A377248_POINTS = [  # work units: candidates k tested
    Point(2, 8.0, 0.0005184000183362514, 8000744, 20),
    Point(3, 392.0, 0.0021754999761469662, 8000744, 412),
    Point(4, 300.0, 0.009475500002736226, 8000744, 712),
    Point(5, 1380.0, 0.3256310000142548, 8000744, 2092),
    Point(6, 2612.0, 5.009506300004432, 8000744, 4704),
]


def test_climbing_seconds_per_unit_withdraws_trust():
    # the cost fit alone is trustworthy, but each candidate took about 7x longer than those of the term before:
    # the rate projects to 11x the one the seconds were converted with, and the rule before offer A would have
    # killed a(7) at 11.2 s
    a = assess(A377248_POINTS, 7, unit="work", time_budget_s=1800, mem_budget=6 * 2 ** 30, name=A377248_NAME)
    assert a.cost.trustworthy and a.cost.npoints == 4 and a.cost.disagreement == pytest.approx(1.36, abs=0.01)
    assert a.seconds_high == pytest.approx(5.594300422463781, rel=1e-9)
    assert a.rate_drift == pytest.approx(10.955506786398118, rel=1e-9)
    assert a.feasible and not a.value_dependent             # the number and the feasibility check are unchanged
    assert not a.trusted(2.0) and a.kill_after_s(2.0) is None
    assert a.trusted(11.0) and a.kill_after_s(11.0) == pytest.approx(11.0 * a.seconds_high)
    stored = Prediction.from_assessment(a, 2.0)
    assert not stored.trustworthy
    assert stored.reasons[:-1] == a.reasons and "at 11x the rate used, over the 2x kill factor" in stored.reasons[-1]


def steady_work(rate, ns=range(5, 20)):
    """Work doubling per term, a trustworthy cost fit; wall seconds per work unit given by rate(n)."""
    return [Point(n, 1000 * 2.0 ** n, 1000 * 2.0 ** n * rate(n), 50e6, 2 ** n) for n in ns]


def test_rate_drift_is_the_projected_rate_over_the_rate_used():
    pts = steady_work(lambda n: 1e-9 * 1.5 ** n)               # each unit costs 1.5x more per term
    a = assess(pts, 20, unit="work", time_budget_s=1e9, mem_budget=4e9)
    recent = pts[-5:]                                          # the seconds are converted with these five
    used = sum(p.wall_s for p in recent) / sum(p.cost for p in recent)
    assert a.cost.trustworthy
    assert a.rate_drift == pytest.approx(1e-9 * 1.5 ** 20 / used, rel=1e-9)
    assert a.rate_drift == pytest.approx(1.9455, rel=1e-4)
    # a drift equal to the factor is still trusted, one just past it is not
    d = a.rate_drift
    assert a.trusted(d) and a.kill_after_s(d) == pytest.approx(d * a.seconds_high)
    assert not a.trusted(d * (1 - 1e-9)) and a.kill_after_s(d * (1 - 1e-9)) is None
    assert a.trusted(2.0)
    # 1.8x per term drifts 2.5x by the next term: past the default factor
    b = assess(steady_work(lambda n: 1e-9 * 1.8 ** n), 20, unit="work", time_budget_s=1e9, mem_budget=4e9)
    assert b.cost.trustworthy and b.rate_drift == pytest.approx(2.5229, rel=1e-4)
    assert not b.trusted(2.0) and b.kill_after_s(2.0) is None


def test_rate_drift_fits_exactly_the_last_five_fitted_points():
    # irregular rates, so that fitting four, five or six points gives three different answers
    mult = [3.0, 0.5, 2.0, 1.0, 4.0, 0.7, 2.5, 1.2, 6.0, 0.9, 3.5, 1.1, 8.0, 2.0, 5.0]
    pts = steady_work(lambda n: 1e-9 * mult[n - 5])
    a = assess(pts, 20, unit="work", time_budget_s=1e12, mem_budget=4e9)

    def drift(k):
        last = pts[-k:]
        xs, ys = [p.n for p in last], [math.log(p.wall_s / p.cost) for p in last]
        mx, my = sum(xs) / k, sum(ys) / k
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
        recent = pts[-5:]
        return math.exp(my + slope * (20 - mx)) / (sum(p.wall_s for p in recent) / sum(p.cost for p in recent))

    assert a.cost.trustworthy and a.rate_drift == pytest.approx(drift(5), rel=1e-9)
    assert min(abs(drift(k) / drift(5) - 1) for k in (4, 6)) > 0.05


def test_harness_uses_its_own_kill_factor_for_trust_and_kill(monkeypatch):
    # the harness driven in memory, without the sandbox: equal work per term, but from n = 14 each term takes
    # 3x longer than the one before, so a(19)'s rate drift is about 10
    monkeypatch.setattr(sandbox, "avail_phys_bytes", lambda: 64 * 2 ** 30)   # the memory cap must not depend on free RAM
    known = KnownTerms("A000079", 0, {n: 2 ** n for n in range(19)}, "bfile")
    prog = Program("python", "", origin="test", strategy="python:test")
    for factor in (2.0, 100.0):
        h = Harness(prog, known, Budgets(verify_wall_s=60, extend_wall_s=1000, over_prediction_factor=factor))
        t = 0.0
        for n in range(19):
            t += 0.001 if n < 14 else 0.01 * 3 ** (n - 14)
            assert h.on_line(f"@T {n} {2 ** n} {int(t * 1e6)} {1000 * (n + 1)} 8000000", t) is None
        [p] = h.predictions
        assert p.n == 19 and h.verified_at == t
        # the stored flag and the kill agree, both at the budget's factor
        assert p.trustworthy == (h.kill_after is not None) == (factor == 100.0)
    assert 100.0 * p.seconds_high > estimate.MIN_GRACE_S and h.kill_after == pytest.approx(100.0 * p.seconds_high)


def test_rate_drift_uses_only_the_points_the_rate_is_converted_from():
    # the earlier terms got cheaper per unit and the last five dearer: over all the points the trend even falls
    pts = steady_work(lambda n: 1e-6 * 0.3 ** (n - 5) if n <= 14 else 1e-6 * 0.3 ** 9 * 3 ** (n - 14))
    a = assess(pts, 20, unit="work", time_budget_s=1e9, mem_budget=4e9)
    assert a.cost.trustworthy and a.rate_drift == pytest.approx(4.8444, rel=1e-4) and not a.trusted(2.0)


def test_rate_drift_applies_to_the_cpu_unit_too():
    def pts(wall_per_cpu):
        return [Point(n, 0.1 * 1.5 ** n, 0.1 * 1.5 ** n * wall_per_cpu(n), 50e6, n) for n in range(5, 20)]
    # wall seconds per CPU second are steady on real runs: no drift
    steady = assess(pts(lambda n: 1.05), 20, unit="cpu", time_budget_s=1e12, mem_budget=4e9)
    assert steady.cost.trustworthy and steady.rate_drift == pytest.approx(1.0) and steady.trusted(2.0)
    # a job ever more starved of CPU is no ground to kill a term either
    starved = assess(pts(lambda n: 1.05 * 3 ** max(0, n - 14)), 20, unit="cpu", time_budget_s=1e12, mem_budget=4e9)
    assert starved.cost.trustworthy and starved.rate_drift > 2 and not starved.trusted(2.0)
    assert starved.kill_after_s(2.0) is None


# Projections from the offer-F replay (2026-09-19): a term log replayed, the next term projected from the points
# before it as if it were the first new term; Point(n, cost, wall_s, mem, value), the first term left out as in
# Harness.points(). The rule before offer F stopped a(16), a(14) and a(15) below as infeasible at budgets up to
# 1800 s, though they took 5.87 s, 0.325 s and 8.01 s; A265383's a(8) was still running 83 s later.
A274508_NAME = "a(n) is the only number m such that 3^(2^m) + 1 is divisible by A273945(n)."
A274508_POINTS = [  # cpu seconds, a(2)..a(16); a(15) is an outlier
    Point(2, 0.0, 0.0004899000050500035, 8002032, 3),
    Point(3, 0.0, 0.00020000000949949026, 8002032, 2),
    Point(4, 0.0, 0.00017809995915740728, 8002032, 3),
    Point(5, 0.0, 0.003543300030287355, 8002032, 7),
    Point(6, 0.0, 0.00019320001592859626, 8002032, 8),
    Point(7, 0.0, 0.006174899986945093, 8002032, 10),
    Point(8, 0.0, 0.0011018000077456236, 8002032, 15),
    Point(9, 0.031, 0.03852589998859912, 8002032, 7),
    Point(10, 0.09400000000000001, 0.09464769996702671, 8002032, 15),
    Point(11, 0.0, 0.0007291000219993293, 8002032, 11),
    Point(12, 2.1559999999999997, 2.1678249000106007, 8002032, 8),
    Point(13, 1.2350000000000003, 1.2589617000194266, 8002032, 19),
    Point(14, 2.14, 2.1855613999650814, 8002032, 4),
    Point(15, 31.563000000000002, 32.375720000010915, 8002032, 9),
    Point(16, 5.75, 5.870602699986193, 8002032, 21),
]
A350878_NAME = ("Integers m that divide the sum of values d*p < m, where d is a divisor of m, p is a prime, and d*p "
                "does not divide m.")
A350878_POINTS = [  # work units, a(2)..a(14)
    Point(2, 1.0, 0.0004905000096186996, 8002088, 2),
    Point(3, 3.0, 0.0002046999870799482, 8002088, 5),
    Point(4, 5.0, 0.00019990000873804092, 8002088, 10),
    Point(5, 8.0, 0.0034888999653048813, 8002088, 18),
    Point(6, 6.0, 0.0001879000337794423, 8002088, 24),
    Point(7, 8.0, 0.00018779997481033206, 8002088, 32),
    Point(8, 28.0, 0.0001849000109359622, 8002088, 60),
    Point(9, 11.0, 0.00016639998648315668, 8002088, 71),
    Point(10, 29.0, 0.00018090003868564963, 8002088, 100),
    Point(11, 412.0, 0.03903469996294007, 8002088, 512),
    Point(12, 2478.0, 1.281009600032121, 8002088, 2990),
    Point(13, 6920.0, 12.231953500013333, 8002088, 9910),
    Point(14, 121.0, 0.32493149995571, 8002088, 10031),
]
A265383_NAME = "Numbers k such that 10^k * (10^k - 1) - 1 is prime."
A265383_POINTS = [  # cpu seconds, a(2)..a(7)
    Point(2, 0.0, 0.0004501999937929213, 8001856, 6),
    Point(3, 0.0, 0.00020370000856928527, 8001856, 9),
    Point(4, 0.0, 0.0157329999783542, 8001856, 154),
    Point(5, 0.094, 0.09467690001474693, 8001856, 253),
    Point(6, 17.875, 18.03893369997968, 8001856, 1114),
    Point(7, 18.766, 18.90705040001194, 8001856, 1390),
]
UNTRUSTED_NOTE = "untrustworthy: not judged infeasible on time"


@pytest.mark.parametrize("points, n, unit, name, npoints, high", [
    (A274508_POINTS[:-1], 16, "cpu", A274508_NAME, 5, 204.16380150197566),     # disagreement 441, after the outlier
    (A350878_POINTS[:-1], 14, "work", A350878_NAME, 3, 123.83510854540107),    # disagreement 2.8, but only 3 points
    (A350878_POINTS, 15, "work", A350878_NAME, 4, 122.24842038073419),         # disagreement 151
    (A265383_POINTS, 8, "cpu", A265383_NAME, 3, 651750.132623167),             # disagreement 1025
], ids=["A274508 a(16)", "A350878 a(14)", "A350878 a(15)", "A265383 a(8)"])
def test_an_untrustworthy_projection_never_stops_a_run_on_time(points, n, unit, name, npoints, high):
    for budget in (1, 60, 120, 300, 1800, 10_800):
        a = assess(points, n, unit=unit, time_budget_s=budget, mem_budget=6 * 2 ** 30, name=name)
        assert a.seconds_high == pytest.approx(high, rel=1e-9) and a.cost.npoints == npoints   # the replay's numbers
        assert not a.cost.trustworthy and not a.value_dependent
        assert a.feasible and a.kill_after_s(2.0) is None
        # the reviewer is told why a projection over the budget did not stop the run
        assert sum(UNTRUSTED_NOTE in r for r in a.reasons) == (high > budget)
    # memory is still checked, whatever the trust in the time projection (these project about 10 MB)
    m = assess(points, n, unit=unit, time_budget_s=1, mem_budget=1e6, name=name)
    assert not m.feasible and any("exceeds cap" in r for r in m.reasons)
    # a search is not judged on time at all, so it carries no such note
    s = assess(points, n, unit=unit, time_budget_s=1, mem_budget=6 * 2 ** 30, name="Least k such that k*2^n+1 is prime")
    assert s.value_dependent and s.feasible and not any(UNTRUSTED_NOTE in r for r in s.reasons)


def test_a_trustworthy_projection_still_stops_a_run_on_its_high_end():
    # A274508's a(17), projected after a(16): trustworthy (6 points, disagreement 2.3), low 26.9 s, high 61.4 s
    a = assess(A274508_POINTS, 17, unit="cpu", time_budget_s=60, mem_budget=6 * 2 ** 30, name=A274508_NAME)
    assert a.cost.trustworthy and a.cost.npoints == 6 and a.seconds_low < 60 < a.seconds_high
    assert a.seconds_high == pytest.approx(61.42768786509824, rel=1e-9)
    assert not a.feasible and any("exceeds remaining budget 60 s" in r for r in a.reasons)
    assert not any(UNTRUSTED_NOTE in r for r in a.reasons)
    # a budget equal to the high estimate is enough
    assert assess(A274508_POINTS, 17, unit="cpu", time_budget_s=a.seconds_high, mem_budget=6 * 2 ** 30,
                  name=A274508_NAME).feasible
    # a fit trustworthy in itself whose rate drifts past the kill factor is not trusted to kill, but it is still
    # judged on its high end: the drift only means the seconds are lower still than they should be
    c = assess(A377248_POINTS, 7, unit="work", time_budget_s=5, mem_budget=6 * 2 ** 30, name=A377248_NAME)
    assert c.cost.trustworthy and not c.trusted(2.0) and c.seconds_low < 5 < c.seconds_high
    assert not c.feasible


def test_harness_runs_on_past_an_untrustworthy_projection_over_the_budget(monkeypatch):
    # the harness driven in memory: work doubles per term until the last known term, which costs 30x that, so
    # the fits with and without it disagree and the first new term's high estimate is over the 1 s extension.
    # The rule before offer F stopped the run there as infeasible
    monkeypatch.setattr(sandbox, "avail_phys_bytes", lambda: 64 * 2 ** 30)   # the memory cap must not depend on free RAM
    known = KnownTerms("A000079", 0, {n: 2 ** n for n in range(19)}, "bfile")
    prog = Program("python", "", origin="test", strategy="python:test")
    h = Harness(prog, known, Budgets(verify_wall_s=60, extend_wall_s=1.0))
    t = work = 0.0
    for n in range(19):
        dwork = 1000 * 2 ** n * (30 if n == 18 else 1)
        work += dwork
        t += dwork * 1e-9
        assert h.on_line(f"@T {n} {2 ** n} {int(t * 1e6)} {int(work)} 8000000", t) is None, h.detail
    [p] = h.predictions
    assert p.n == 19 and not p.trustworthy and p.feasible and p.seconds_high > 1.0
    assert any(UNTRUSTED_NOTE in r for r in p.reasons) and h.kill_after is None
    assert h.on_tick(t + 0.9) is None                          # no kill, and the extension is not used up yet
    # a(19) arrives within the extension and is kept as a new term
    t += 0.95
    h.on_line(f"@T 19 {2 ** 19} {int(t * 1e6)} {int(work + 1000 * 2 ** 19)} 8000000", t)
    assert [(r.n, r.kind) for r in h.records[-2:]] == [(18, "known"), (19, "new")]
    assert h.predictions[0].actual_s == pytest.approx(h.records[-1].dt)


def test_next_term_bit_bound_flags_int64_overflow():
    pts = pts_from(lambda n: 1000.0, range(40, 60), value=lambda n: 2 ** n)
    a = assess(pts, 62, unit="work", time_budget_s=1e9, mem_budget=4e9)
    assert a.next_bits_high >= 63 and a.exceeds_int64


def test_cheap_sequences_are_feasible_but_marked_risky():
    pts = [Point(n, 1.0, 1e-4, 1e7, n) for n in range(1, 10)]
    a = assess(pts, 10, unit="work", time_budget_s=100, mem_budget=4e9)
    assert a.feasible and a.risky and a.cost is None
