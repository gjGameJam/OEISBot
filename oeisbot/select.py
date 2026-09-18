"""Difficulty scoring and weighted selection (build step 5).

Difficulty d comes from cheap features; a candidate is picked with probability proportional to
1 / d^alpha. alpha = 0 is uniform; larger alpha favors easy targets more strongly. A sum tree keeps
sampling O(log n) while weights change during a session (after failures, or picks without replacement).
"""
from __future__ import annotations

import math
import random
import sqlite3
from dataclasses import dataclass

from . import config, db

# multiplicative difficulty factors; tune these against the attempts table
RUNNABLE_PROGRAM = {"pari": 0.3, "python": 0.45, "sage": 0.5}
OTHER_PROGRAM = {"mathematica": 0.6, "maple": 0.7}
HARD_KEYWORD = 6.0
PER_MORE_CREDIT = 0.75           # each "More terms from ..." credit: humans already pushed it
BIG_TERM_DIGITS = 20             # last terms beyond this many digits count as large
VALUE_DEPENDENT = 1.5
FAILURE_PENALTY = 2.0            # per earlier failed attempt, capped
MAX_FAILURE_PENALTY = 64.0


def difficulty(row) -> float:
    """row: db.SequenceRow or a sequences-table sqlite3.Row."""
    get = (lambda k: row[k]) if isinstance(row, sqlite3.Row) else (lambda k: getattr(row, k))
    langs = set(filter(None, (get("program_langs") or "").split(",")))
    kws = set(filter(None, (get("keywords") or "").split(",")))
    d = 1.0
    runnable = [f for lang, f in RUNNABLE_PROGRAM.items() if lang in langs]
    other = [f for lang, f in OTHER_PROGRAM.items() if lang in langs]
    if runnable:
        d *= min(runnable)
    elif other:
        d *= min(other)
    if "hard" in kws:
        d *= HARD_KEYWORD
    keys = row.keys() if isinstance(row, sqlite3.Row) else vars(row)
    bdig = get("bfile_last_digits") if "bfile_last_digits" in keys else None
    digits = max(bdig or 0, get("data_last_digits") or 0)
    d *= 1 + max(0, digits - BIG_TERM_DIGITS) / BIG_TERM_DIGITS
    d *= 1 + PER_MORE_CREDIT * (get("more_credits") or 0)
    if get("value_dependent"):
        d *= VALUE_DEPENDENT
    bterms = get("bfile_terms") if "bfile_terms" in keys else None
    d *= 1 + math.log10(1 + (bterms or get("data_terms") or 0) / 50)
    return d


def weight(d: float, alpha: float) -> float:
    return d ** -alpha


class SumTree:
    """Binary indexed sums over leaf weights: update and sample in O(log n)."""

    def __init__(self, weights: list[float]):
        self.size = 1
        while self.size < max(1, len(weights)):
            self.size *= 2
        self.tree = [0.0] * (2 * self.size)
        self.tree[self.size:self.size + len(weights)] = [max(0.0, w) for w in weights]
        for i in range(self.size - 1, 0, -1):
            self.tree[i] = self.tree[2 * i] + self.tree[2 * i + 1]

    @property
    def total(self) -> float:
        return self.tree[1]

    def get(self, i: int) -> float:
        return self.tree[self.size + i]

    def update(self, i: int, w: float) -> None:
        j = self.size + i
        self.tree[j] = max(0.0, w)
        j //= 2
        while j:
            self.tree[j] = self.tree[2 * j] + self.tree[2 * j + 1]
            j //= 2

    def find(self, u: float) -> int:
        """Leaf index whose cumulative weight interval contains u, 0 <= u < total."""
        j = 1
        while j < self.size:
            left = self.tree[2 * j]
            if u < left:
                j = 2 * j
            else:
                u -= left
                j = 2 * j + 1
        return j - self.size

    def sample(self, rng: random.Random) -> int | None:
        if self.total <= 0:
            return None
        i = self.find(rng.random() * self.total)
        # guard against landing on a zero leaf through floating-point rounding
        while self.get(i) <= 0:
            i = self.find(rng.random() * self.total)
        return i


@dataclass
class Candidate:
    a_number: str
    name: str
    difficulty: float
    weight: float
    program_langs: str


def _too_few_for_model(row: sqlite3.Row) -> bool:
    """Fewer known terms than model generation needs. Decided only once the b-file lookup has run, since a
    b-file can add terms beyond the DATA line."""
    if row["bfile_status"] not in ("present", "absent"):
        return False
    return max(row["bfile_terms"] or 0, row["data_terms"]) < config.CODEGEN_MIN_KNOWN_TERMS


def candidates(conn: sqlite3.Connection, *, alpha: float = 1.0, require_langs: set[str] | None = None) -> list[Candidate]:
    """Eligible 'more' sequences with effective difficulty (features x failure history)."""
    failures = {r["a_number"]: r["c"] for r in conn.execute(
        "SELECT a_number, COUNT(*) AS c FROM attempts WHERE outcome IN ('failed', 'verified') GROUP BY a_number")}
    blocked = {r["a_number"] for r in conn.execute(
        f"SELECT DISTINCT a_number FROM reviews WHERE status IN ({','.join('?' * len(db.OPEN_REVIEW_STATUSES))})",
        db.OPEN_REVIEW_STATUSES)}
    blocked |= {r["a_number"] for r in db.pending_rechecks(conn)}
    out = []
    for row in conn.execute("SELECT * FROM sequences WHERE in_more = 1"):
        a = row["a_number"]
        if a in blocked:
            continue
        langs = set(filter(None, row["program_langs"].split(",")))
        if require_langs is not None and not langs & require_langs:
            continue
        if "pari" not in langs and _too_few_for_model(row):
            continue     # no PARI program and the model would refuse it: it could only be skipped
        d = difficulty(row) * min(MAX_FAILURE_PENALTY, FAILURE_PENALTY ** failures.get(a, 0))
        out.append(Candidate(a, row["name"], d, weight(d, alpha), row["program_langs"]))
    return out


def pick(pool: list[Candidate], k: int, rng: random.Random) -> list[Candidate]:
    """k distinct candidates, each draw with probability proportional to weight."""
    tree = SumTree([c.weight for c in pool])
    chosen = []
    for _ in range(min(k, len(pool))):
        i = tree.sample(rng)
        if i is None:
            break
        chosen.append(pool[i])
        tree.update(i, 0.0)
    return chosen
