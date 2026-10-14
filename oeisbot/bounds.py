"""Searched bounds published in an entry's `%C` comments.

Many `more` entries carry a human claim that some range was examined and holds no further term:
`No more terms <= 2 * 10^38` (A194099), `a(29) > 10^13`, `Any subsequent terms are > 10^12`. The pipeline
parses those lines already (`ingest/seqfile.py` keeps them as `Entry.comments`) and used to ignore them.

**A bound here is an unverified human claim.** It may bound what is worth spending time on; it must never
become evidence that a term is correct, and nothing in this module is allowed to decide a term's value or
index. Its only consumer is the check at the verify/extend boundary (`verify.Harness`), which can decline
to spend time and nothing else.

The pattern set is evidence, not guesswork: it was chosen by hand-reading all 241 pool candidates whose
bound is beyond a real run's reach (session 9, `data/session9/resultsS9.md`). Two forms that a crude
reading would include are deliberately absent -- see `_UNINDEXED` -- and two guards reject shapes that
produced measured false positives.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# A069575 publishes `No more terms through 10^5000`, and CPython refuses to render an int that long
# under its default 4300-digit limit. verify.py sets this too; bounds.py is importable on its own
# (tests, scripts), so it must not rely on that having happened first.
sys.set_int_max_str_digits(0)

MAX_EXPONENT = 10_000          # beyond this nobody means a bound, and the int would be pointless to build


@dataclass(frozen=True)
class Bound:
    """A searched-range claim read out of one `%C` line."""
    value: int
    quote: str                 # the comment line it came from, so a reviewer can judge it
    index: int | None          # the index the claim names, or None when it speaks of all further terms


# ------------------------------------------------------------------ numbers in prose

# '2 * 10^38', '10^13', '1.5*10^6', '2^63', '3^500'. The base is captured: A053706 says
# `no other terms < 2^63` and A119909 `No more terms < 3^20`, and a base-10-only reader turned those
# into 2 and 3 -- discarding a 9.2e18 bound and a 3.5e9 one.
_POWER = re.compile(r"(?:(\d[\d,]*(?:\.\d+)?)\s*[*x]\s*)?(\d+)\s*\^\s*(\d+)", re.I)
_PLAIN = re.compile(r"\d[\d,]*(?:\.\d+)?")
# 'No additional terms up to 10 billion' (A175492) parses as 10 without this
_WORD_SCALE = re.compile(r"\A\s*(million|billion|trillion)\b", re.I)
_SCALES = {"million": 10**6, "billion": 10**9, "trillion": 10**12}


def _exact(mantissa: str | None, power: int) -> int | None:
    """`mantissa * power`, exactly.

    `Decimal ** int` is NOT exact: the default context rounds to 28 significant digits, so
    `int(Decimal(2) ** 200)` ends in 92 zeros where `2 ** 200` ends in ...301376. Only base 10 with a
    coefficient of 1 survives that, which is why an earlier version's `2^63` test passed while every
    larger power was wrong. So: integer exponentiation for the power, and an exact integer ratio for a
    decimal mantissa. Flooring a non-integral product is the conservative direction for a bound -- it can
    only make the check fire less often."""
    if mantissa is None:
        return power
    try:
        num, den = Decimal(mantissa.replace(",", "")).as_integer_ratio()
    except (ValueError, InvalidOperation, ArithmeticError):
        return None
    return (power * num) // den


def parse_number(text: str) -> int | None:
    """The first numeric literal in `text`, understanding OEIS's power and word notation."""
    p, q = _POWER.search(text), _PLAIN.search(text)
    if p is not None and (q is None or p.start() <= q.start()):
        try:
            exp = int(p.group(3))
            if exp > MAX_EXPONENT:
                return None
            power = int(p.group(2)) ** exp        # exact integer arithmetic, never Decimal ** int
        except (ValueError, OverflowError):
            return None
        return _exact(p.group(1), power)
    if q is None:
        return None
    scale = _WORD_SCALE.match(text[q.end():])
    return _exact(q.group(0), _SCALES[scale.group(1).lower()] if scale else 1)


# ------------------------------------------------------------------ bound claims

# The bare `>` must not be the one inside an arrow. A337671's `a(17)? -> 2^9216 - 9216^2 = ...` otherwise
# parses as a 2,775-digit bound on a(17): `_INDEXED` takes `a(17)`, the interjection `"? -"`, then the
# arrow's `>`. `_bridges` does not save it, because `"? -"` holds no `a(`, `=` or digit. The `=>` spelling
# was already rejected (it contains `=`), which is exactly why this looked covered.
_COMPARE = r"(?:>=|(?<![-=<>])>|greater\s+than|larger\s+than|bigger\s+than|exceeds|at\s+least)"
_CONNECT = r"(?:<=|<|below|less\s+than|up\s+to|under|through)"
_HEAD = r"no\s+(?:(?:more|further|other|additional)\s+terms?|others?)"

# Each pattern captures (interjection, tail). `_UNINDEXED` and `_INDEXED` are the strict forms only.
#
# Deliberately ABSENT: `searched to X` and `search extended to X`. Those produced A088783's false
# positive, where `searched to (2^24-1)/3` is a per-candidate *exponent* limit inside a table of search
# limits, not a bound on the next term -- while the same entry says its next term may be 185. Measured
# over the 172 deployable pool candidates, *none* loses its bound when they are dropped, so they cost
# nothing and remove a whole failure class.
_UNINDEXED = [
    re.compile(rf"\b{_HEAD}\b([^.;]{{0,40}}?){_CONNECT}\s*(.{{0,48}})", re.I),
    # 'Next term if it exists is greater than X' (A039774) puts four words inside the interjection
    re.compile(rf"\bnext\s+terms?\b([^.;]{{0,30}}?){_COMPARE}\s*(.{{0,48}})", re.I),
    # 'Any subsequent terms are > X' carries no search word at all and was invisible to earlier patterns
    re.compile(rf"\bany\s+subsequent\s+terms?\b([^.;]{{0,30}}?){_COMPARE}\s*(.{{0,48}})", re.I),
]
# 'a(10) (if it exists) is > 10^300', 'a(6), if it exists, is greater than 4*10^8' -- the commonest
# missed form by a wide margin, so the interjection is allowed but tightly policed by `_bridges`
_INDEXED = re.compile(rf"\ba\((\d+)\)([^.;]{{0,30}}?){_COMPARE}\s*(.{{0,48}})", re.I)

# A qualifier between the head and the comparator narrows the claim to a subset of terms, so it is not a
# statement about the next term at all: A146566's `No other term multiple of 12 below 10^9` is true and
# useless. Measured over the whole corpus this rejects 55 of 2,393 matches and costs 0 of the deployable
# bounds, because A146566's *other* comment states the unqualified 10^7 bound.
_QUALIFIER = re.compile(r"multiple\s+of|of\s+the\s+form|congruent\s+to|divisible\s+by|\bwith\b|\bwhose\b", re.I)
# An interjection that contains another index, an equals sign or a bare number is not an interjection:
# it has bridged two clauses, and `a(7) = 12345, and the search for a(8) went past 10^9` would otherwise
# attribute 10^9 to k = 7
_BRIDGE = re.compile(r"a\s*\(|=|\d")
_ANUMBER = re.compile(r"A\d{6}")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def _bridges(interjection: str) -> bool:
    return bool(_BRIDGE.search(interjection))


def _sentence_around(line: str, position: int) -> str:
    """The sentence of `line` containing `position`.

    Split on end punctuation followed by whitespace and a capital, so `4.97*10^17` and a trailing
    `A001220.` are not cut mid-token the way a naive split on '.' would."""
    start = 0
    for m in _SENTENCE.finditer(line):
        if m.end() > position:
            break
        start = m.end()
    end = len(line)
    for m in _SENTENCE.finditer(line):
        if m.start() > position:
            end = m.start()
            break
    return line[start:end]


def _borrowed(line: str, position: int, a_number: str) -> bool:
    """Whether the claim at `position` cites another entry's bound rather than making its own.

    A274994 says `No more terms up to 2000000, because ... A001220 has no other terms below 4.97*10^17`.
    Reading 4.97e17 as this sequence's bound is the one wrong skip in the measured census, and it is the
    failure mode that matters because a wrong skip is irreversible within a session. The guard is not
    free: it also drops bounds whose *justification* merely cites another entry (A087485, A127441,
    A238739 among the deployable ones), about 1.8% of the set. That trade is deliberate -- a missed skip
    only costs time."""
    sentence = _sentence_around(line, position)
    return any(m.group(0).upper() != a_number.upper() for m in _ANUMBER.finditer(sentence))


def bounds_in(comments: list[str], a_number: str) -> list[Bound]:
    """Every searched-bound claim in an entry's `%C` lines, matched one line at a time."""
    found: list[Bound] = []
    for line in comments:
        for pattern in _UNINDEXED:
            for m in pattern.finditer(line):
                if _QUALIFIER.search(m.group(1)) or _borrowed(line, m.start(), a_number):
                    continue
                value = parse_number(m.group(2))
                if value is not None:
                    found.append(Bound(value, line, None))
        for m in _INDEXED.finditer(line):
            if _bridges(m.group(2)) or _borrowed(line, m.start(), a_number):
                continue
            value = parse_number(m.group(3))
            if value is not None:
                found.append(Bound(value, line, int(m.group(1))))
    return found


def applicable(comments: list[str], a_number: str, last_value: int, next_unknown: int) -> Bound | None:
    """The strongest published bound that constrains the next unknown term, or None.

    An unindexed claim qualifies only when it exceeds the last known value: `No more terms < 10^7` says
    nothing once a(4) = 58,088,321 is known (A029495), and treating such a claim as live would skip runs
    on a bound that has already been overtaken. An indexed claim qualifies only when it names exactly the
    next unknown index -- an earlier index is superseded, a later one (A138598's sole comment is
    `a(14) > 10^5` with a(13) unknown) constrains a term the pipeline is not about to compute. The
    `> last_value` test is applied to both: an indexed claim can be stale too."""
    live = [b for b in bounds_in(comments, a_number)
            if b.value > last_value and (b.index is None or b.index == next_unknown)]
    return max(live, key=lambda b: b.value, default=None)
