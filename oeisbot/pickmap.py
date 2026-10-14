"""What the dashboard's Pick map shows: the pick chance of every candidate in the pool a session draws
from, and how each has moved since an earlier snapshot of that pool (`db.record_pick_snapshot`).

A pick chance is `weight / sum of weights`, with `weight = difficulty ** -alpha` (`select.weight`): the
chance of being the *first* draw of a session. Later draws are made without replacement, so a sequence's
chance of being in a session of k picks is larger; the map shows the first-draw share because it is the
one that adds up to 100% across the pool and so can be drawn as area.

Pure functions over {a_number: difficulty} mappings: no database, no clock, so tests can feed them
numbers.
"""
from __future__ import annotations

import bisect
import math
from collections.abc import Mapping

from . import select

# Difficulty bands, by the effective difficulty `select.candidates` computes (features times failure
# history). The edges follow where the real pool's mass sits: most of it is below 1, and a long thin tail
# runs past 16. A difficulty equal to an edge belongs to the band above it.
BAND_EDGES = (0.5, 0.75, 1.0, 1.5, 2.0, 4.0, 8.0, 16.0)
BAND_LABELS = ("under 0.5", "0.5 to 0.75", "0.75 to 1", "1 to 1.5", "1.5 to 2", "2 to 4", "4 to 8", "8 to 16", "16 and up")

# `alpha` beyond this is refused by the API: weights are `d ** -alpha`, and the map is only ever asked
# about the exponent the sessions use (1.0) or a reasonable sweep around it.
MAX_ALPHA = 6.0


def band_of(difficulty: float) -> int:
    return bisect.bisect_right(BAND_EDGES, difficulty)


def chances(difficulties: Mapping[str, float], alpha: float) -> dict[str, float]:
    """Every candidate's first-draw chance; they sum to 1 (to 0 for an empty pool, or when the weights do not
    add up to a positive number, e.g. a NaN difficulty at an alpha above 0 -- the map then draws nothing
    rather than raising, where `select.pick` would clamp the NaN weight to 0 and draw the rest; the pool
    never has a NaN, so the two cannot differ in practice. Weights that add up to infinity give every
    candidate 0 by the division itself). A difficulty of 0 or below is not handled: `select.weight`
    raises, and the pool never has one (the factors in `select.difficulty` bottom out at 0.3, and a
    failure only multiplies it up)."""
    weights = {a: select.weight(d, alpha) for a, d in difficulties.items()}
    total = sum(sorted(weights.values()))                # the same pool in any order gives the same chances
    if not total > 0:
        return {a: 0.0 for a in weights}
    return {a: w / total for a, w in weights.items()}


def baseline(headers, live_digest: str):
    """The snapshot to compare the live pool with: the newest one that is NOT the live pool. `headers` is
    `db.pick_snapshot_headers` (newest first). A snapshot equal to the live pool is skipped because the
    comparison would show nothing but "no change"; skipping it shows what changed *into* the live pool,
    which is the most recent change there is. None when every snapshot matches the live pool, or there
    are none."""
    return next((h for h in headers if h["digest"] != live_digest), None)


def compare(live: Mapping[str, float], base: Mapping[str, float] | None, alpha: float) -> dict:
    """Per-candidate chance now (`p`) and how it moved since `base`.

    `ratio` compares each candidate with the *others that were in both pools*: its share of the picks
    those candidates hold between them, now over then. That is the whole point of doing it this way. A
    plain `p / p_then` moves every tile by the same factor whenever sequences leave or enter the pool --
    from the pool before session 12 to the one on 2026-10-13, 55 sequences left holding 1.9% of the picks and
    a plain ratio painted the 3,355 survivors whose difficulty had not changed all "up 2%", which is true and
    tells you nothing about any of them. Here a sequence that failed (its difficulty doubles) shows as
    `2 ** -alpha` -- ~0.5 at the default alpha of 1 -- and everyone else as ~1.0. "~1.0" holds while the
    sequences that moved hold little of the picks: the others read `1 / (1 - f/2)` for movers holding a
    fraction f of the survivors' mass at alpha 1 (1.006 for f = 1.25%, 1.016 for one tile with 3.2%).

    `p0` is the share it had then, rescaled by the same factor, so `p / p0 == ratio` and a tooltip adds
    up. A candidate only in `live` is `new` (ratio and p0 None); one only in `base` is in `gone`, with
    the (unrescaled) chance it had. `entered` and `gone` say how much of the pick mass moved in and out.
    `base=None` means there is nothing to compare with: every ratio is None and nothing is new."""
    p = chances(live, alpha)
    rows = []
    if base is None:
        for a, d in live.items():
            rows.append({"a": a, "d": d, "band": band_of(d), "p": p[a], "p0": None, "ratio": None, "new": False})
        return {"rows": rows, "gone": [], "entered": {"n": 0, "share": 0.0}}
    q = chances(base, alpha)
    common = live.keys() & base.keys()
    now_mass = math.fsum(p[a] for a in common)           # `common` is a set: fsum makes the order irrelevant
    then_mass = math.fsum(q[a] for a in common)
    scale = now_mass / then_mass if then_mass > 0 else 0.0
    entered_n, entered_share = 0, 0.0
    for a, d in live.items():
        row = {"a": a, "d": d, "band": band_of(d), "p": p[a], "p0": None, "ratio": None, "new": a not in base}
        if row["new"]:
            entered_n += 1
            entered_share += p[a]
        else:
            then = q[a] * scale
            row["p0"] = then
            row["ratio"] = p[a] / then if then > 0 else None
        rows.append(row)
    gone = sorted(((a, q[a]) for a in base if a not in live), key=lambda t: (-t[1], t[0]))
    return {"rows": rows, "gone": gone, "entered": {"n": entered_n, "share": entered_share}}


def band_summary(rows: list[dict]) -> list[dict]:
    """One entry per band that has members: how many candidates, and what share of all picks they take."""
    out = []
    for i, label in enumerate(BAND_LABELS):
        members = [r for r in rows if r["band"] == i]
        if members:
            out.append({"band": i, "label": label, "n": len(members), "share": sum(r["p"] for r in members)})
    return out


def departure_reason(*, attempt: tuple[str, str | None] | None, review: str | None, in_more: bool | None,
                     rules_changed: bool, budgets_changed: bool) -> str:
    """Why a sequence in an earlier snapshot is not in the live pool, from what the database recorded since:
    an open review or a pending re-check (a win), the newest attempt's outcome, the sequence leaving the
    `more` list at a sync. When nothing explains it, the pool was built under other rules or budgets if
    the fingerprints say so, and is otherwise genuinely unexplained -- the label says which, because
    "unexplained" with changed rules would blame the data for what the code did."""
    if review:
        return f"review {review}"
    if attempt:
        outcome, mode = attempt
        if outcome == "recheck_pending":
            return "win waiting for its re-check"
        return f"attempted: {outcome}" + (f" ({mode})" if mode else "")
    if in_more is False:
        return "left the 'more' list"
    if rules_changed:
        return "selection rules changed"
    if budgets_changed:
        return "budgets differ"
    return "unexplained"
