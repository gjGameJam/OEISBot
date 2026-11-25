"""The Pick map: the pure comparison (`oeisbot.pickmap`), the snapshot tables (`db.record_pick_snapshot`) and
`/api/pickmap`. The hooks that store a snapshot (`run_session`, `oeisbot snapshot`) are tested beside the
session tests in `test_attempt.py`, which has the fixtures for them."""
from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from oeisbot import attempt, config, db, pickmap
from oeisbot.select import Candidate

# ------------------------------------------------------------------ the pure comparison


def test_a_difficulty_on_an_edge_belongs_to_the_band_above():
    assert [pickmap.band_of(d) for d in (0.3, 0.4999, 0.5, 0.7499, 0.75, 0.9999, 1.0, 15.9999, 16.0, 1e6)] \
        == [0, 0, 1, 1, 2, 2, 3, 7, 8, 8]
    assert len(pickmap.BAND_LABELS) == len(pickmap.BAND_EDGES) + 1
    assert list(pickmap.BAND_EDGES) == sorted(set(pickmap.BAND_EDGES))


def test_chances_are_first_draw_shares_that_add_up_to_one():
    p = pickmap.chances({"A1": 1.0, "A2": 2.0, "A3": 4.0}, 1.0)
    assert math.isclose(sum(p.values()), 1.0)
    assert math.isclose(p["A1"] / p["A2"], 2.0) and math.isclose(p["A2"] / p["A3"], 2.0)
    flat = pickmap.chances({"A1": 1.0, "A2": 2.0, "A3": 4.0}, 0.0)
    assert all(math.isclose(v, 1 / 3) for v in flat.values())
    steep = pickmap.chances({"A1": 1.0, "A2": 2.0}, 2.0)           # weights 1 and 1/4
    assert math.isclose(steep["A1"], 0.8)


def test_chances_of_nothing_are_nothing_and_never_raise():
    assert pickmap.chances({}, 1.0) == {}
    assert pickmap.chances({"A1": float("nan"), "A2": 1.0}, 1.0) == {"A1": 0.0, "A2": 0.0}
    huge = pickmap.chances({"A1": 1e-154, "A2": 1e-154}, 2.0)           # two weights of 1e308 add up to infinity
    assert huge == {"A1": 0.0, "A2": 0.0}


def test_chances_agree_with_what_the_session_draws_with():
    """The map must show the weights `select.pick` uses, not a copy of the formula."""
    from oeisbot import select
    d = {"A1": 0.35, "A2": 1.7, "A3": 12.0}
    p = pickmap.chances(d, 1.3)
    total = sum(select.weight(x, 1.3) for x in d.values())
    for a, x in d.items():
        assert math.isclose(p[a], select.weight(x, 1.3) / total)


def hdr(id_, digest, taken="2026-09-30T00:00:00+00:00"):
    return {"id": id_, "digest": digest, "taken_at": taken}


def test_the_baseline_is_the_newest_snapshot_that_is_not_the_live_pool():
    newest_first = [hdr(3, "same"), hdr(2, "same"), hdr(1, "old")]
    assert pickmap.baseline(newest_first, "same")["id"] == 1            # two equal to the live pool are skipped
    assert pickmap.baseline(newest_first, "other")["id"] == 3           # none equal: simply the newest
    assert pickmap.baseline([hdr(1, "same")], "same") is None           # nothing different to compare with
    assert pickmap.baseline([], "same") is None


def test_with_nothing_to_compare_with_no_tile_has_a_ratio_and_none_is_new():
    out = pickmap.compare({"A1": 1.0, "A2": 3.0}, None, 1.0)
    assert out["gone"] == [] and out["entered"] == {"n": 0, "share": 0.0}
    assert [(r["a"], r["ratio"], r["p0"], r["new"]) for r in out["rows"]] == [("A1", None, None, False), ("A2", None, None, False)]
    assert math.isclose(sum(r["p"] for r in out["rows"]), 1.0)


def test_a_pool_that_did_not_change_has_every_ratio_at_one():
    pool = {f"A{i}": 0.5 + i / 7 for i in range(1, 30)}
    out = pickmap.compare(pool, dict(pool), 1.0)
    assert out["gone"] == [] and out["entered"]["n"] == 0
    assert all(math.isclose(r["ratio"], 1.0) and math.isclose(r["p"], r["p0"]) for r in out["rows"])


def test_sequences_leaving_the_pool_do_not_move_the_ones_that_stayed():
    """The reason for the intersection ratio (measured from the pool before session 12 to the live one on
    2026-10-13: 55 sequences holding 1.9% of the picks left, and a plain p / p_then painted all 3,355
    unchanged survivors "up 2%")."""
    base = {f"A{i}": 1.0 for i in range(100, 0, -1)}                    # reverse insertion order: ties sort by name
    live = {a: d for a, d in base.items() if int(a[1:]) <= 80}          # twenty left, no survivor changed
    out = pickmap.compare(live, base, 1.0)
    assert all(math.isclose(r["ratio"], 1.0) for r in out["rows"])
    plain = [r["p"] / (1 / 100) for r in out["rows"]]
    assert all(math.isclose(x, 1.25) for x in plain)                    # what the naive ratio would have said
    assert out["entered"] == {"n": 0, "share": 0.0}
    assert len(out["gone"]) == 20 and math.isclose(sum(p for _, p in out["gone"]), 0.2)
    assert [a for a, _ in out["gone"]] == sorted(f"A{i}" for i in range(81, 101))   # equal chances: by name


def test_one_failed_attempt_shows_as_about_half_and_everyone_else_as_about_one():
    base = {f"A{i}": 1.0 for i in range(1, 201)}
    live = {**base, "A7": 2.0}                                          # one failure doubles a difficulty
    rows = {r["a"]: r for r in pickmap.compare(live, base, 1.0)["rows"]}
    assert 0.50 < rows["A7"]["ratio"] < 0.51
    assert all(0.99 < r["ratio"] < 1.01 for a, r in rows.items() if a != "A7")
    assert math.isclose(rows["A7"]["p"] / rows["A7"]["p0"], rows["A7"]["ratio"])


def test_p_then_is_rescaled_so_that_p_over_p0_is_the_ratio_and_the_chances_still_add_up():
    base = {"A1": 1.0, "A2": 1.0, "A3": 1.0, "A4": 1.0, "A5": 1.0, "A6": 1.0}
    live = {"A1": 1.0, "A2": 2.0, "A3": 1.0, "A4": 1.0}                 # A5, A6 gone, A2 failed
    out = pickmap.compare(live, base, 1.0)
    rows = {r["a"]: r for r in out["rows"]}
    assert math.isclose(rows["A2"]["ratio"], (0.5 / 3.5) / 0.25)
    assert math.isclose(rows["A1"]["ratio"], (1 / 3.5) / 0.25)
    for r in rows.values():
        assert math.isclose(r["p"] / r["p0"], r["ratio"])
    assert math.isclose(sum(r["p0"] for r in rows.values()), 1.0)        # the survivors' shares, renormalised
    assert [(a, round(p, 6)) for a, p in out["gone"]] == [("A5", round(1 / 6, 6)), ("A6", round(1 / 6, 6))]


def test_a_candidate_in_only_the_live_pool_is_new_and_has_no_ratio():
    base = {"A1": 1.0, "A2": 1.0}
    live = {"A1": 1.0, "A2": 1.0, "A9": 0.5}
    out = pickmap.compare(live, base, 1.0)
    new = [r for r in out["rows"] if r["new"]]
    assert [(r["a"], r["ratio"], r["p0"]) for r in new] == [("A9", None, None)]
    assert out["entered"]["n"] == 1 and math.isclose(out["entered"]["share"], new[0]["p"])
    old = [r for r in out["rows"] if not r["new"]]
    assert all(r["ratio"] is not None and r["p0"] is not None for r in old)


def test_a_newcomer_takes_its_share_from_everyone_and_does_not_move_the_survivors_against_each_other():
    """The survivors are normalised among themselves, so a newcomer holding half the picks leaves the two that
    were already there at 1.0 and gives them the rescaled earlier share they now really hold (0.25 each)."""
    out = pickmap.compare({"A1": 1.0, "A2": 1.0, "A9": 0.5}, {"A1": 1.0, "A2": 1.0}, 1.0)
    rows = {r["a"]: r for r in out["rows"]}
    assert math.isclose(rows["A9"]["p"], 0.5) and math.isclose(out["entered"]["share"], 0.5)
    for a in ("A1", "A2"):
        assert math.isclose(rows[a]["ratio"], 1.0) and math.isclose(rows[a]["p0"], 0.25) and math.isclose(rows[a]["p"], 0.25)


def test_the_ratio_of_an_unchanged_sequence_does_not_depend_on_the_order_the_pool_was_listed_in():
    """`common` is a set, so its iteration order follows the string hash seed; summing in that order moved
    unchanged sequences' ratios by up to 4e-15 between runs. `fsum` makes the sums exact."""
    import random
    rng = random.Random(7)
    base = {f"A{i:06d}": 0.3 + rng.random() * 9 for i in range(1, 400)}
    live = {a: d for a, d in base.items() if rng.random() > 0.05}
    live.update({f"A9{i:05d}": 0.3 + rng.random() * 3 for i in range(8)})
    live["A000002"] = base["A000002"] * 2
    keys = list(live)
    results = []
    for _ in range(6):
        rng.shuffle(keys)
        shuffled = {a: live[a] for a in keys}
        results.append({r["a"]: (r["ratio"], r["p0"]) for r in pickmap.compare(shuffled, base, 1.0)["rows"]})
    assert all(r == results[0] for r in results[1:])


@pytest.mark.parametrize("spiky", ["live", "base"])
def test_the_two_masses_are_summed_exactly_wherever_the_common_set_puts_the_big_share(monkeypatch, spiky):
    """One share of a half and a hundred of 6e-17: a plain sum rounds each small one up by a whole ulp when it
    comes after the big one and keeps it when it comes before, so only a pool whose big share happens to be
    last gets the exact mass. Which end of the set that is follows the string hash seed, so five unrelated
    sets of names are tried (a plain sum matches on one position in 101). `chances` is replaced by the identity
    so the shares are exactly those written here."""
    monkeypatch.setattr(pickmap, "chances", lambda difficulties, alpha: difficulties)
    for round_ in range(5):
        names = [f"X{round_}_{i}" for i in range(101)]
        big = {names[0]: 0.5, **{a: 6e-17 for a in names[1:]}}
        flat = {a: 1 / 101 for a in names}
        live, base = (big, flat) if spiky == "live" else (flat, big)
        scale = math.fsum(live.values()) / math.fsum(base.values())
        out = pickmap.compare(live, base, 1.0)
        assert len(out["rows"]) == 101 and all(r["p0"] == base[r["a"]] * scale for r in out["rows"])


def test_a_row_is_in_the_band_of_its_difficulty_now_not_the_one_it_had():
    """A failed attempt multiplies a difficulty up and can carry the sequence over a band edge (0.9 -> 1.8)."""
    out = pickmap.compare({"A1": 1.8, "A2": 1.0}, {"A1": 0.9, "A2": 1.0}, 1.0)
    assert pickmap.band_of(0.9) != pickmap.band_of(1.8)
    assert {r["a"]: (r["d"], r["band"]) for r in out["rows"]} == {"A1": (1.8, pickmap.band_of(1.8)),
                                                                  "A2": (1.0, pickmap.band_of(1.0))}


def test_disjoint_pools_have_nothing_in_common_and_do_not_divide_by_zero():
    out = pickmap.compare({"A1": 1.0, "A2": 2.0}, {"A8": 1.0, "A9": 1.0}, 1.0)
    assert all(r["new"] and r["ratio"] is None for r in out["rows"])
    assert out["entered"]["n"] == 2 and math.isclose(out["entered"]["share"], 1.0)
    assert [a for a, _ in out["gone"]] == ["A8", "A9"]


def test_those_who_left_are_listed_heaviest_first_and_by_name_among_equals():
    base = {"A1": 1.0, "A2": 1.0, "A3": 2.0, "A4": 0.5, "A5": 2.0}                  # weights 1, 1, 1/2, 2, 1/2
    out = pickmap.compare({"A1": 1.0, "A2": 1.0}, base, 1.0)
    assert [a for a, _ in out["gone"]] == ["A4", "A3", "A5"]
    chances = [p for _, p in out["gone"]]
    assert chances == sorted(chances, reverse=True)


def test_a_chance_that_underflows_to_nothing_gives_no_ratio_instead_of_dividing_by_zero():
    both = {"A1": 1e100, "A2": 1e100}                                       # (1e100) ** -6 is 0.0, so nothing adds up
    out = pickmap.compare(both, both, 6.0)
    assert all(r["p"] == 0.0 and r["p0"] == 0.0 and r["ratio"] is None and not r["new"] for r in out["rows"])
    mixed = {"A1": 1.0, "A2": 1e100}                                        # only the second one has no earlier chance
    rows = {r["a"]: r for r in pickmap.compare(mixed, mixed, 6.0)["rows"]}
    assert rows["A2"]["ratio"] is None and math.isclose(rows["A1"]["ratio"], 1.0)


def test_the_ratio_depends_on_alpha_and_at_alpha_zero_ignores_difficulty():
    base = {f"A{i}": 1.0 for i in range(1, 11)}
    live = {**base, "A1": 4.0}
    at0 = pickmap.compare(live, base, 0.0)["rows"]
    assert all(math.isclose(r["ratio"], 1.0) for r in at0)             # alpha 0 is uniform: nothing moved
    at2 = {r["a"]: r["ratio"] for r in pickmap.compare(live, base, 2.0)["rows"]}
    assert at2["A1"] < 0.1


def test_band_summary_lists_only_bands_with_members_and_their_share():
    rows = pickmap.compare({"A1": 0.3, "A2": 0.4, "A3": 3.0}, None, 1.0)["rows"]
    out = pickmap.band_summary(rows)
    assert [(b["band"], b["label"], b["n"]) for b in out] == [(0, "under 0.5", 2), (5, "2 to 4", 1)]
    assert math.isclose(sum(b["share"] for b in out), 1.0)
    assert pickmap.band_summary([]) == []


@pytest.mark.parametrize("kw, expected", [
    (dict(attempt=None, review="new", in_more=True, rules_changed=True, budgets_changed=True), "review new"),
    (dict(attempt=("failed", "verify_timeout"), review="new", in_more=False, rules_changed=True, budgets_changed=True),
     "review new"),
    (dict(attempt=("recheck_pending", None), review="approved", in_more=True, rules_changed=False, budgets_changed=False),
     "review approved"),
    (dict(attempt=("recheck_pending", None), review=None, in_more=True, rules_changed=False, budgets_changed=False),
     "win waiting for its re-check"),
    (dict(attempt=("failed", "verify_timeout"), review=None, in_more=False, rules_changed=True, budgets_changed=True),
     "attempted: failed (verify_timeout)"),
    (dict(attempt=("extended", None), review=None, in_more=True, rules_changed=False, budgets_changed=False),
     "attempted: extended"),
    (dict(attempt=None, review=None, in_more=False, rules_changed=True, budgets_changed=True), "left the 'more' list"),
    (dict(attempt=None, review=None, in_more=True, rules_changed=True, budgets_changed=True), "selection rules changed"),
    (dict(attempt=None, review=None, in_more=True, rules_changed=False, budgets_changed=True), "budgets differ"),
    (dict(attempt=None, review=None, in_more=True, rules_changed=False, budgets_changed=False), "unexplained"),
])
def test_a_departure_is_explained_by_the_strongest_thing_the_database_recorded(kw, expected):
    assert pickmap.departure_reason(**kw) == expected


# ------------------------------------------------------------------ the snapshot tables


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.sqlite3")
    yield c
    c.close()


def pairs(n, d=1.0):
    return [(f"A{i:06d}", d) for i in range(1, n + 1)]


def test_a_snapshot_is_stored_with_its_rows_and_what_built_it(conn):
    sid = db.record_pick_snapshot(conn, "pari", [("A2", 2.0), ("A1", 0.5)], session_id=None, budgets="B", rules="R")
    (h,) = db.pick_snapshot_headers(conn, "pari")
    assert (h["id"], h["n"], h["budgets"], h["rules"], h["session_id"]) == (sid, 2, "B", "R", None)
    assert h["digest"] == db.pick_digest([("A1", 0.5), ("A2", 2.0)]) and h["taken_at"].endswith("+00:00")
    assert db.pick_snapshot_difficulties(conn, sid) == {"A1": 0.5, "A2": 2.0}


def test_a_snapshot_remembers_the_session_that_took_it(conn):
    session = db.start_session(conn, note="x")
    sid = db.record_pick_snapshot(conn, "pari", pairs(2), session_id=session)
    assert db.pick_snapshot_headers(conn, "pari")[0]["session_id"] == session and sid is not None


def test_the_digest_ignores_order_and_sees_the_last_bit_of_a_difficulty():
    a = db.pick_digest([("A1", 1.0), ("A2", 2.0)])
    assert a == db.pick_digest([("A2", 2.0), ("A1", 1.0)])
    assert a != db.pick_digest([("A1", 1.0), ("A2", math.nextafter(2.0, 3.0))])
    assert a != db.pick_digest([("A1", 1.0)])
    assert a != db.pick_digest([("A1", 1.0), ("A3", 2.0)])
    assert db.pick_digest([("A1", 11.0)]) != db.pick_digest([("A11", 1.0)])      # where one pair ends matters


def test_a_pool_equal_to_the_newest_snapshot_stores_nothing_but_one_equal_to_an_older_one_does(conn):
    first = db.record_pick_snapshot(conn, "pari", pairs(3))
    assert db.record_pick_snapshot(conn, "pari", list(reversed(pairs(3)))) is None
    second = db.record_pick_snapshot(conn, "pari", pairs(4))
    third = db.record_pick_snapshot(conn, "pari", pairs(3))              # back to the first: the NEWEST differs
    assert None not in (first, second, third) and len({first, second, third}) == 3
    assert [h["id"] for h in db.pick_snapshot_headers(conn, "pari")] == [third, second, first]


def test_each_pool_keeps_its_own_newest_snapshots(conn):
    for n in range(1, 6):
        db.record_pick_snapshot(conn, "pari", pairs(n), keep=3)
    db.record_pick_snapshot(conn, "model", pairs(2), keep=3)
    assert [h["n"] for h in db.pick_snapshot_headers(conn, "pari")] == [5, 4, 3]
    assert [h["n"] for h in db.pick_snapshot_headers(conn, "model")] == [2]
    survivors = {r[0] for r in conn.execute("SELECT DISTINCT snapshot_id FROM pick_snapshot_rows")}
    assert survivors == {h["id"] for pool in ("pari", "model") for h in db.pick_snapshot_headers(conn, pool)}


def test_the_default_number_kept_is_per_pool_from_the_config(conn, monkeypatch):
    monkeypatch.setattr(config, "PICK_SNAPSHOTS_KEPT", {"pari": 2, "model": 1})
    for n in range(1, 5):
        db.record_pick_snapshot(conn, "pari", pairs(n))
        db.record_pick_snapshot(conn, "model", pairs(n))
    assert len(db.pick_snapshot_headers(conn, "pari")) == 2 and len(db.pick_snapshot_headers(conn, "model")) == 1


def test_every_pool_the_database_accepts_has_a_retention_in_the_config():
    assert set(config.PICK_SNAPSHOTS_KEPT) == set(db.POOLS)
    assert all(isinstance(n, int) and n >= 1 for n in config.PICK_SNAPSHOTS_KEPT.values())


def test_an_unknown_pool_or_a_keep_that_would_delete_the_new_snapshot_is_refused(conn):
    with pytest.raises(ValueError, match="unknown pool"):
        db.record_pick_snapshot(conn, "wolfram", pairs(1))
    for bad in (0, -1):
        with pytest.raises(ValueError, match="keep must be at least 1"):
            db.record_pick_snapshot(conn, "pari", pairs(1), keep=bad)
    assert conn.execute("SELECT COUNT(*) FROM pick_snapshots").fetchone()[0] == 0


def test_a_failed_write_leaves_the_old_state_not_a_header_without_rows(conn):
    first = db.record_pick_snapshot(conn, "pari", pairs(3), keep=1)
    with pytest.raises(sqlite3.IntegrityError):
        db.record_pick_snapshot(conn, "pari", pairs(2) + pairs(2), keep=1)        # a duplicate A-number
    assert [h["id"] for h in db.pick_snapshot_headers(conn, "pari")] == [first]
    assert len(db.pick_snapshot_difficulties(conn, first)) == 3                    # not pruned, not touched
    assert conn.execute("SELECT COUNT(*) FROM pick_snapshot_rows").fetchone()[0] == 3
    assert not conn.in_transaction


def test_the_write_lock_is_taken_before_the_pool_is_compared(conn):
    """Two writers that both read "the newest differs" would both insert; BEGIN IMMEDIATE makes the second
    wait and then see the first one's snapshot."""
    seen: list[str] = []
    conn.set_trace_callback(seen.append)
    db.record_pick_snapshot(conn, "pari", pairs(2))
    conn.set_trace_callback(None)
    first_select = next(i for i, s in enumerate(seen) if s.startswith("SELECT id, digest FROM pick_snapshots"))
    assert "BEGIN IMMEDIATE" in seen[:first_select]


def test_a_writer_that_cannot_get_the_write_lock_raises_and_stores_nothing(tmp_path):
    path = tmp_path / "t.sqlite3"
    one, two = db.connect(path), db.connect(path)
    two.execute("PRAGMA busy_timeout=50")
    try:
        one.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            db.record_pick_snapshot(two, "pari", pairs(2))
        one.rollback()
        assert db.pick_snapshot_headers(two, "pari") == [] and not two.in_transaction
        assert db.record_pick_snapshot(two, "pari", pairs(2)) is not None
    finally:
        one.close()
        two.close()


def test_writers_racing_with_the_same_pool_store_it_once(tmp_path):
    path = tmp_path / "t.sqlite3"
    db.connect(path).close()
    start, results, errors = threading.Barrier(6), [], []

    def write():
        c = db.connect(path)
        try:
            start.wait(10)
            results.append(db.record_pick_snapshot(c, "pari", pairs(300)))
        except Exception as e:      # noqa: BLE001 -- the assertion below reports it
            errors.append(e)
        finally:
            c.close()

    threads = [threading.Thread(target=write) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert errors == [] and len(results) == 6 and sum(r is not None for r in results) == 1
    check = db.connect(path)
    assert len(db.pick_snapshot_headers(check, "pari")) == 1
    check.close()


def test_a_connection_with_a_transaction_open_is_refused_and_its_pending_write_is_left_alone(conn):
    conn.execute("INSERT INTO meta(key, value) VALUES ('pending', 'yes')")
    assert conn.in_transaction
    with pytest.raises(RuntimeError, match="cannot run inside a transaction"):
        db.record_pick_snapshot(conn, "pari", pairs(2))
    assert conn.in_transaction                                                    # neither committed nor rolled back
    assert conn.execute("SELECT value FROM meta WHERE key = 'pending'").fetchone()[0] == "yes"
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM meta WHERE key = 'pending'").fetchone()[0] == 0
    assert db.pick_snapshot_headers(conn, "pari") == []


def test_an_unchanged_pool_refreshes_what_built_it_and_stores_no_new_snapshot(conn):
    first = db.record_pick_snapshot(conn, "pari", pairs(3), budgets="B1", rules="R1")
    assert db.record_pick_snapshot(conn, "pari", pairs(3), budgets="B2", rules="R2") is None
    (h,) = db.pick_snapshot_headers(conn, "pari")
    assert (h["id"], h["budgets"], h["rules"]) == (first, "B2", "R2")
    assert not conn.in_transaction


def test_refreshing_the_newest_snapshots_stamp_leaves_the_older_ones_alone(conn):
    older = db.record_pick_snapshot(conn, "pari", pairs(2), budgets="B1", rules="R1")
    newer = db.record_pick_snapshot(conn, "pari", pairs(3), budgets="B2", rules="R2")
    other = db.record_pick_snapshot(conn, "model", pairs(3), budgets="M1", rules="M2")
    assert db.record_pick_snapshot(conn, "pari", pairs(3), budgets="B3", rules="R3") is None
    stamps = {h["id"]: (h["budgets"], h["rules"]) for p in ("pari", "model") for h in db.pick_snapshot_headers(conn, p)}
    assert stamps == {older: ("B1", "R1"), newer: ("B3", "R3"), other: ("M1", "M2")}


def test_an_unchanged_pool_with_no_stamp_keeps_the_stamp_it_has(conn):
    db.record_pick_snapshot(conn, "pari", pairs(3), budgets="B1", rules="R1")
    assert db.record_pick_snapshot(conn, "pari", pairs(3)) is None
    (h,) = db.pick_snapshot_headers(conn, "pari")
    assert (h["budgets"], h["rules"]) == ("B1", "R1")


def test_a_database_made_before_the_snapshot_tables_gets_them_the_next_time_it_is_opened_for_writing(tmp_path):
    path = tmp_path / "old.sqlite3"
    db.connect(path).close()
    raw = sqlite3.connect(path)
    raw.executescript("DROP TABLE pick_snapshot_rows; DROP TABLE pick_snapshots;")
    raw.close()
    reader = db.connect(path, readonly=True)
    assert db.has_pick_snapshots(reader) is False
    reader.close()
    writer = db.connect(path)
    assert db.has_pick_snapshots(writer) is True and db.record_pick_snapshot(writer, "pari", pairs(2)) is not None
    writer.close()


def test_the_snapshot_tables_may_be_missing_and_a_reader_says_so(tmp_path):
    bare = sqlite3.connect(tmp_path / "bare.sqlite3")
    assert db.has_pick_snapshots(bare) is False
    bare.execute("CREATE TABLE pick_snapshots(id INTEGER)")
    assert db.has_pick_snapshots(bare) is False                                   # both tables or neither
    bare.close()
    made = db.connect(tmp_path / "made.sqlite3")
    assert db.has_pick_snapshots(made) is True
    made.close()


def test_deleting_a_snapshot_deletes_its_rows(conn):
    sid = db.record_pick_snapshot(conn, "pari", pairs(5))
    with conn:
        conn.execute("DELETE FROM pick_snapshots WHERE id = ?", (sid,))
    assert conn.execute("SELECT COUNT(*) FROM pick_snapshot_rows").fetchone()[0] == 0


def test_budgets_json_is_equal_for_equal_budgets_and_differs_when_one_field_does():
    a = attempt.budgets_json(config.DEFAULT_BUDGETS)
    assert a == attempt.budgets_json(replace(config.DEFAULT_BUDGETS))
    assert a != attempt.budgets_json(replace(config.DEFAULT_BUDGETS, verify_wall_s=config.DEFAULT_BUDGETS.verify_wall_s + 1))
    parsed = json.loads(a)
    assert list(parsed) == sorted(parsed) and config.Budgets(**parsed) == config.DEFAULT_BUDGETS


@pytest.mark.parametrize("error", [OSError("no source"), TypeError("built-in")])
def test_the_rules_fingerprint_is_stable_and_says_unknown_rather_than_raising(monkeypatch, error):
    import inspect
    fp = attempt.rules_fingerprint()
    assert fp == attempt.rules_fingerprint() and len(fp) == 12 and int(fp, 16) >= 0

    def refuse(obj):
        raise error
    monkeypatch.setattr(inspect, "getsource", refuse)
    assert attempt.rules_fingerprint() == "unknown"


FINGERPRINT_SOURCES = [attempt.Runnable, attempt.PariPlan, attempt.pari_plan, db.is_dead_end,
                       attempt.oeisdata.load_entry, attempt.bfile.cached, attempt.bfile.known_terms]
FINGERPRINT_MODULES = [attempt.select, attempt.pari, attempt.seqfile]
FINGERPRINT_CONSTANTS = [(db, "DETERMINISTIC_FAILURES", ("made_up",)), (db, "OPEN_REVIEW_STATUSES", ("made_up",)),
                         (db, "EXTEND_DEAD_END_MIN_CPU_SHARE", 0.5), (config, "CODEGEN_MIN_KNOWN_TERMS", 99)]


@pytest.mark.parametrize("target", FINGERPRINT_SOURCES, ids=lambda t: t.__qualname__)
def test_the_rules_fingerprint_moves_with_the_source_of_each_function_and_class_it_is_made_from(monkeypatch, target):
    import inspect
    real = inspect.getsource
    base = attempt.rules_fingerprint()
    monkeypatch.setattr(inspect, "getsource", lambda obj: real(obj) + ("\n# edited\n" if obj is target else ""))
    assert attempt.rules_fingerprint() != base


@pytest.mark.parametrize("mod", FINGERPRINT_MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_the_rules_fingerprint_moves_with_the_text_of_each_module_it_is_made_from(monkeypatch, tmp_path, mod):
    from pathlib import Path
    base = attempt.rules_fingerprint()
    edited = tmp_path / "edited.py"
    edited.write_bytes(Path(mod.__file__).read_bytes() + b"\n# edited\n")
    monkeypatch.setattr(mod, "__file__", str(edited))
    assert attempt.rules_fingerprint() != base


@pytest.mark.parametrize("owner, name, value", FINGERPRINT_CONSTANTS,
                         ids=[n for _, n, _ in FINGERPRINT_CONSTANTS])
def test_the_rules_fingerprint_moves_with_each_constant_that_retires_a_program_or_gates_the_model(
        monkeypatch, owner, name, value):
    base = attempt.rules_fingerprint()
    monkeypatch.setattr(owner, name, value)
    assert attempt.rules_fingerprint() != base


def test_the_rules_fingerprint_does_not_change_when_a_checkout_converts_the_line_endings(monkeypatch, tmp_path):
    from pathlib import Path
    base = attempt.rules_fingerprint()
    for mod in FINGERPRINT_MODULES:
        raw = Path(mod.__file__).read_bytes().replace(b"\r\n", b"\n")
        crlf = tmp_path / (mod.__name__.rsplit(".", 1)[-1] + ".py")
        crlf.write_bytes(raw.replace(b"\n", b"\r\n"))
        monkeypatch.setattr(mod, "__file__", str(crlf))
    assert attempt.rules_fingerprint() == base


# ------------------------------------------------------------------ /api/pickmap

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from oeisbot.dashboard import app as dashboard  # noqa: E402


class _Keep:
    def summary(self) -> str:
        return "left out 2 that could only be skipped (2 no_supported_program)"


def cands(d: dict[str, float], name: str | None = None) -> list[Candidate]:
    return [Candidate(a, name or f"name of {a}", x, 1 / x, "pari") for a, x in d.items()]


@pytest.fixture
def pm(tmp_path, monkeypatch):
    """A dashboard over a temporary database whose live pool is whatever `state[pool]` says (a dict of
    A-number -> difficulty), standing in for `attempt.session_pool`. `state['calls']` lists (model, budgets)."""
    path = tmp_path / "t.sqlite3"
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path / "artifacts")
    dashboard._live.clear()
    monkeypatch.setattr(dashboard, "_rules", None)
    state = {"pari": {}, "model": {}, "calls": []}

    def fake_session_pool(conn, budgets, *, model, alpha=1.0):
        state["calls"].append((model, budgets))
        return cands(state["model" if model else "pari"], state.get("name")), _Keep()

    monkeypatch.setattr(attempt, "session_pool", fake_session_pool)
    conn = db.connect(path)
    yield TestClient(dashboard.app), conn, state
    conn.close()
    dashboard._live.clear()


def get(client, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = client.get("/api/pickmap" + (f"?{q}" if q else ""))
    assert r.status_code == 200, r.text
    return r.json()


def test_the_map_lists_every_candidate_with_its_chance_largest_first(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0, "A000002": 0.5, "A000003": 4.0}
    out = get(client)
    assert (out["pool"], out["alpha"], out["n"], out["snapshots"], out["baseline"]) == ("pari", 1.0, 3, 0, None)
    assert [r["a"] for r in out["rows"]] == ["A000002", "A000001", "A000003"]
    assert math.isclose(sum(r["p"] for r in out["rows"]), 1.0)
    assert all(r["ratio"] is None and r["p0"] is None and r["new"] is False for r in out["rows"])
    assert out["rows"][0]["name"] == "name of A000002"
    assert [(b["band"], b["label"], b["n"]) for b in out["bands"]] == [(1, "0.5 to 0.75", 1), (3, "1 to 1.5", 1), (6, "4 to 8", 1)]
    assert math.isclose(sum(b["share"] for b in out["bands"]), 1.0)
    assert out["note"].startswith("left out 2 that could only be skipped")
    assert out["gone"] == {"n": 0, "share": 0.0, "reasons": [], "top": []} and out["entered"] == {"n": 0, "share": 0.0}


def test_alpha_changes_the_chances_and_is_validated(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0, "A000002": 2.0}
    flat = get(client, alpha=0)
    assert [round(r["p"], 6) for r in flat["rows"]] == [0.5, 0.5]
    steep = get(client, alpha=2)
    assert math.isclose(steep["rows"][0]["p"], 0.8) and steep["alpha"] == 2.0
    for bad in ("alpha=-0.1", f"alpha={pickmap.MAX_ALPHA + 0.1}", "alpha=nan", "pool=wolfram", "alpha=abc"):
        assert client.get(f"/api/pickmap?{bad}").status_code == 422, bad
    assert client.get(f"/api/pickmap?alpha={pickmap.MAX_ALPHA}").status_code == 200


def test_the_frontend_limit_on_alpha_is_the_servers():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "dashboard" / "src" / "treemap.ts").read_text(encoding="utf-8")
    assert f"export const MAX_ALPHA = {pickmap.MAX_ALPHA:g};" in src


def test_the_pools_are_separate(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    state["model"] = {"A000001": 1.0, "A000002": 2.0, "A000003": 2.0}
    assert get(client, pool="pari")["n"] == 1
    assert get(client, pool="model")["n"] == 3
    assert [m for m, _ in state["calls"]] == [False, True]


def test_the_map_without_the_snapshot_tables_still_answers_and_does_not_make_them(pm):
    client, conn, state = pm
    with conn:
        conn.execute("DROP TABLE pick_snapshot_rows")
        conn.execute("DROP TABLE pick_snapshots")
    state["pari"] = {"A000001": 1.0, "A000002": 1.0}
    out = get(client)
    assert out["snapshots"] == 0 and out["baseline"] is None and out["n"] == 2
    assert not db.has_pick_snapshots(conn)                                         # a reader cannot create them


def test_the_baseline_is_the_newest_snapshot_that_differs_from_the_live_pool(pm):
    client, conn, state = pm
    old = db.record_pick_snapshot(conn, "pari", [("A000001", 1.0), ("A000002", 1.0), ("A000003", 1.0)])
    live = {"A000001": 1.0, "A000002": 1.0, "A000003": 2.0}
    same = db.record_pick_snapshot(conn, "pari", list(live.items()))
    assert old and same
    state["pari"] = dict(live)
    out = get(client)
    assert out["snapshots"] == 2 and out["baseline"]["id"] == old                  # the one equal to live is skipped
    assert out["baseline"]["n"] == 3 and out["baseline"]["session_id"] is None
    ratios = {r["a"]: r["ratio"] for r in out["rows"]}
    assert ratios["A000003"] < 0.7 < 1.0 < ratios["A000001"]


def test_when_every_snapshot_equals_the_live_pool_there_is_nothing_to_compare_with(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0, "A000002": 3.0}
    db.record_pick_snapshot(conn, "pari", list(state["pari"].items()))
    out = get(client)
    assert out["snapshots"] == 1 and out["baseline"] is None
    assert all(r["ratio"] is None for r in out["rows"])


def test_a_snapshot_of_the_other_pool_is_not_a_baseline(pm):
    client, conn, state = pm
    db.record_pick_snapshot(conn, "model", [("A000001", 1.0), ("A000002", 1.0)])
    state["pari"] = {"A000001": 1.0}
    out = get(client)
    assert out["snapshots"] == 0 and out["baseline"] is None
    db.record_pick_snapshot(conn, "pari", [("A000001", 2.0)])                      # now each pool has one of its own
    state["model"] = {"A000001": 1.0, "A000002": 1.0, "A000003": 1.0}
    model, pari = get(client, pool="model"), get(client)
    assert (model["snapshots"], model["baseline"]["n"]) == (1, 2) and (pari["snapshots"], pari["baseline"]["n"]) == (1, 1)


def test_new_candidates_and_departures_are_reported_with_the_reason_the_database_gives(pm):
    client, conn, state = pm
    db.upsert_sequences(conn, [db.SequenceRow(a, f"seq {a}", 0, "nonn,more", 20, 3, "pari", 0, False)
                               for a in ("A000001", "A000002", "A000003", "A000004", "A000005", "A000006")])
    base = {"A000001": 1.0, "A000002": 1.0, "A000003": 1.0, "A000004": 1.0, "A000005": 1.0, "A000006": 1.0}
    db.record_pick_snapshot(conn, "pari", list(base.items()))
    # after the snapshot: A000003 was attempted and failed, A000004 won (an open review), A000005 left the
    # 'more' list, A000006 has no explanation
    db.record_skip(conn, "A000003", "pari:x", "verify_timeout", outcome="failed")
    win = db.record_skip(conn, "A000004", "pari:x", "max_new_terms", outcome="extended")
    db.add_review(conn, "A000004", win, "artifacts/A000004/attempt-1", 2, 3)
    with conn:
        conn.execute("UPDATE sequences SET in_more = 0 WHERE a_number = 'A000005'")
    state["pari"] = {"A000001": 1.0, "A000002": 1.0, "A000009": 0.5}
    out = get(client)
    assert out["baseline"]["budgets_differ"] is False and out["baseline"]["rules_differ"] is None
    assert out["entered"]["n"] == 1
    new = [r for r in out["rows"] if r["new"]]
    assert [r["a"] for r in new] == ["A000009"] and new[0]["ratio"] is None
    gone = out["gone"]
    assert gone["n"] == 4 and math.isclose(gone["share"], 4 / 6)
    assert {r["reason"]: r["n"] for r in gone["reasons"]} == {
        "attempted: failed (verify_timeout)": 1, "review new": 1, "left the 'more' list": 1, "unexplained": 1}
    assert [t["a"] for t in gone["top"]] == ["A000003", "A000004", "A000005", "A000006"]
    assert gone["top"][0]["name"] == "seq A000003" and gone["top"][0]["reason"] == "attempted: failed (verify_timeout)"
    assert math.isclose(sum(r["share"] for r in gone["reasons"]), gone["share"])


def test_the_reasons_are_listed_largest_share_first(pm):
    client, conn, state = pm
    db.upsert_sequences(conn, [db.SequenceRow(a, f"seq {a}", 0, "nonn,more", 20, 3, "pari", 0, False)
                               for a in ("A000001", "A000002")])
    db.record_pick_snapshot(conn, "pari", [("A000001", 2.0), ("A000002", 0.5), ("A000099", 1.0)])
    with conn:
        conn.execute("UPDATE sequences SET in_more = 0 WHERE a_number = 'A000001'")
    state["pari"] = {"A000099": 1.0}
    reasons = get(client)["gone"]["reasons"]
    assert [r["reason"] for r in reasons] == ["unexplained", "left the 'more' list"]       # not alphabetical
    assert reasons[0]["share"] > reasons[1]["share"]


def test_a_review_that_keeps_a_sequence_out_explains_its_departure(pm):
    """An open review always did. Since item 58 a rejected one does too (select.candidates no longer
    draws such a sequence), so it is the reason whatever an attempt recorded afterwards -- until then
    this test pinned the opposite, because a rejected sequence went back to the draw."""
    client, conn, state = pm
    names = ("A000001", "A000002", "A000003", "A000004")
    db.upsert_sequences(conn, [db.SequenceRow(a, f"seq {a}", 0, "nonn,more", 20, 3, "pari", 0, False) for a in names])
    db.record_pick_snapshot(conn, "pari", [*((a, 1.0) for a in names), ("A000099", 1.0)])
    for a, status in (("A000001", "rejected"), ("A000002", "submitted"), ("A000003", "reviewing")):
        win = db.record_skip(conn, a, "pari:x", "max_new_terms", outcome="extended")
        db.set_review_status(conn, db.add_review(conn, a, win, f"artifacts/{a}/attempt-1", 2, 3), status)
    db.record_skip(conn, "A000001", "pari:x", "verify_timeout", outcome="failed")
    state["pari"] = {"A000099": 1.0}
    why = {t["a"]: t["reason"] for t in get(client)["gone"]["top"]}
    assert why == {"A000001": "review rejected", "A000002": "review submitted",
                   "A000003": "review reviewing", "A000004": "unexplained"}


def test_an_interrupted_run_is_never_named_as_why_a_sequence_left(pm):
    """Item 58. A run its caller stopped takes nothing out of the pool, and the daemon records such rows
    every night; the newest attempt would otherwise be blamed for whatever happened next."""
    client, conn, state = pm
    names = ("A000001", "A000002", "A000003")
    db.upsert_sequences(conn, [db.SequenceRow(a, f"seq {a}", 0, "nonn,more", 20, 3, "pari", 0, False) for a in names])
    db.record_pick_snapshot(conn, "pari", [*((a, 1.0) for a in names), ("A000099", 1.0)])
    db.record_skip(conn, "A000001", "pari:x", "interrupted", outcome="failed")          # then it left `more`
    db.record_skip(conn, "A000002", "pari:x", "wrong_term", outcome="failed")           # a real reason ...
    db.record_skip(conn, "A000002", "pari:x", "interrupted", outcome="failed")          # ... not hidden by a later stop
    db.record_skip(conn, "A000003", "pari:x", "interrupted", outcome="verified")        # and nothing else known
    with conn:
        conn.execute("UPDATE sequences SET in_more = 0 WHERE a_number = 'A000001'")
    state["pari"] = {"A000099": 1.0}
    why = {t["a"]: t["reason"] for t in get(client)["gone"]["top"]}
    assert why == {"A000001": "left the 'more' list", "A000002": "attempted: failed (wrong_term)",
                   "A000003": "unexplained"}


def test_an_interrupted_run_that_found_terms_is_still_the_reason(pm):
    """The other half: a run stopped after it had found new terms is a win, pending or recorded, and
    that does take its sequence out of the pool. Only the fruitless interrupted run is passed over."""
    client, conn, state = pm
    names = ("A000001", "A000002")
    db.upsert_sequences(conn, [db.SequenceRow(a, f"seq {a}", 0, "nonn,more", 20, 3, "pari", 0, False) for a in names])
    db.record_pick_snapshot(conn, "pari", [*((a, 1.0) for a in names), ("A000099", 1.0)])
    db.record_skip(conn, "A000001", "pari:x", "wrong_term", outcome="failed")           # older, and not the reason
    db.record_skip(conn, "A000001", "pari:x", "interrupted", outcome="recheck_pending")
    db.record_skip(conn, "A000002", "pari:x", "interrupted", outcome="extended")        # a win no review was opened for
    state["pari"] = {"A000099": 1.0}
    why = {t["a"]: t["reason"] for t in get(client)["gone"]["top"]}
    assert why == {"A000001": "win waiting for its re-check", "A000002": "attempted: extended (interrupted)"}


def test_an_attempt_made_before_the_snapshot_does_not_explain_a_later_departure(pm):
    client, conn, state = pm
    db.upsert_sequences(conn, [db.SequenceRow("A000001", "x", 0, "nonn,more", 20, 3, "pari", 0, False)])
    db.record_skip(conn, "A000001", "pari:x", "verify_timeout", outcome="failed")
    with conn:
        conn.execute("UPDATE attempts SET started_at = '2020-01-01T00:00:00+00:00'")
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0), ("A000002", 1.0)])
    state["pari"] = {"A000002": 1.0}
    out = get(client)
    assert [t["reason"] for t in out["gone"]["top"]] == ["unexplained"]


def test_only_the_ten_largest_departures_are_listed(pm):
    client, conn, state = pm
    gone = {f"A{i:06d}": 2.0 - i / 100 for i in range(1, 13)}                 # twelve leave; A000012 holds the most
    db.record_pick_snapshot(conn, "pari", [*gone.items(), ("A000099", 1.0)])
    state["pari"] = {"A000099": 1.0}
    out = get(client)["gone"]
    assert out["n"] == 12 and sum(r["n"] for r in out["reasons"]) == 12
    assert [t["a"] for t in out["top"]] == [f"A{i:06d}" for i in range(12, 2, -1)]      # lowest difficulty = most chance
    assert out["top"][-1]["a"] == "A000003" and len(out["top"]) == 10


def test_a_long_name_is_cut_and_marked_as_cut_in_the_rows_and_the_departures(pm):
    client, conn, state = pm
    db.upsert_sequences(conn, [db.SequenceRow("A000002", "y" * 300, 0, "nonn,more", 20, 3, "pari", 0, False)])
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0), ("A000002", 1.0)])
    state["pari"] = {"A000001": 1.0}
    state["name"] = "n" * 300
    out = get(client)
    # ninety characters and an ellipsis: a cut name must never read as a whole one
    assert out["rows"][0]["name"] == "n" * 90 + "…" and out["gone"]["top"][0]["name"] == "y" * 90 + "…"


def test_a_name_is_cut_between_words_and_a_short_one_is_left_alone():
    # A102997's name, which the map used to end at "(A00227"
    name = ("Numbers n such that 4*10^n + 8*R_n - 7 is prime, where R_n = 11...1 is the repunit "
            "(A002275) of length n.")
    assert len(name) > 90
    cut = dashboard.short_name(name)
    assert cut == "Numbers n such that 4*10^n + 8*R_n - 7 is prime, where R_n = 11...1 is the repunit…"
    assert name.startswith(cut[:-1]) and name[len(cut) - 1] == " "      # it stops where a word stops
    assert dashboard.short_name("x" * 90) == "x" * 90                   # exactly at the limit: whole, unmarked
    assert dashboard.short_name("short name") == "short name"
    assert dashboard.short_name(None) == ""
    # one early space is no reason to throw most of the name away
    assert dashboard.short_name("ab " + "c" * 200) == "ab " + "c" * 87 + "…"


def test_a_departure_with_no_sequence_row_is_not_blamed_on_the_more_list(pm):
    client, conn, state = pm
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0), ("A000002", 1.0)])
    state["pari"] = {"A000001": 1.0}
    assert [t["reason"] for t in get(client)["gone"]["top"]] == ["unexplained"]       # rows are never deleted: unknown


def test_the_page_says_when_the_pool_was_built_under_other_budgets_or_rules(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0, "A000002": 1.0}
    other = replace(config.DEFAULT_BUDGETS, verify_wall_s=config.DEFAULT_BUDGETS.verify_wall_s + 5)
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0)], budgets=attempt.budgets_json(other), rules="stale")
    out = get(client)
    # the live pool is built under the snapshot's own budgets, so the budgets do NOT differ ...
    assert out["baseline"]["budgets_differ"] is False
    assert state["calls"][-1][1] == other
    # ... but the code that decides membership has changed since
    assert out["baseline"]["rules_differ"] is True


def test_a_snapshot_without_budgets_is_compared_under_the_defaults_and_without_a_banner(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0, "A000002": 1.0}
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0)])                       # taken with no budgets, no rules
    out = get(client)
    assert state["calls"][-1][1] == config.DEFAULT_BUDGETS
    assert out["baseline"]["budgets_differ"] is False and out["baseline"]["rules_differ"] is None


def test_a_snapshot_with_unreadable_budgets_falls_back_to_the_defaults(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0, "A000002": 1.0}
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0)], budgets="{not json")
    out = get(client)
    assert state["calls"][-1][1] == config.DEFAULT_BUDGETS
    assert out["baseline"]["budgets_differ"] is True                                # what was stored is not what ran


def test_departures_after_a_change_of_rules_say_so_instead_of_unexplained(pm):
    client, conn, state = pm
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0), ("A000002", 1.0)], budgets=attempt.budgets_json(
        config.DEFAULT_BUDGETS), rules="stale")
    state["pari"] = {"A000001": 1.0}
    out = get(client)
    assert [t["reason"] for t in out["gone"]["top"]] == ["selection rules changed"]


def test_an_unfinished_session_is_reported_unless_it_is_a_day_old(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    assert get(client)["running_session"] is None
    sid = db.start_session(conn, note="x")
    out = get(client)
    assert out["running_session"]["id"] == sid
    with conn:
        conn.execute("UPDATE sessions SET started_at = '2020-01-01T00:00:00+00:00' WHERE id = ?", (sid,))
    assert get(client)["running_session"] is None                                   # crashed long ago
    sid2 = db.start_session(conn, note="y")
    db.finish_session(conn, sid2)
    assert get(client)["running_session"] is None


def test_the_live_pool_is_built_once_until_the_database_changes_or_a_rebuild_is_asked_for(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    get(client)
    get(client, alpha=2)                                                            # alpha is applied afterwards
    assert len(state["calls"]) == 1
    state["pari"] = {"A000001": 1.0, "A000002": 1.0}
    assert get(client)["n"] == 1 and len(state["calls"]) == 1                       # nothing changed: the cache serves
    assert get(client, refresh="true")["n"] == 2 and len(state["calls"]) == 2       # a rebuild on request
    state["pari"] = {"A000001": 1.0, "A000002": 1.0, "A000003": 1.0}
    db.set_meta_many(conn, {"k": "v"})                                              # any commit invalidates it
    assert get(client)["n"] == 3 and len(state["calls"]) == 3


def test_the_live_pool_is_rebuilt_when_the_budgets_it_is_asked_under_change(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0, "A000002": 1.0}
    get(client)
    other = replace(config.DEFAULT_BUDGETS, extend_wall_s=config.DEFAULT_BUDGETS.extend_wall_s + 1)
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0)], budgets=attempt.budgets_json(other))
    get(client)
    assert [b for _, b in state["calls"]] == [config.DEFAULT_BUDGETS, other]


def test_the_live_pool_expires_after_its_time_to_live(pm, monkeypatch):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    get(client)
    built = dashboard._live["pari"]
    monkeypatch.setattr(dashboard, "_live", {"pari": built._replace(built=built.built - dashboard.POOL_TTL_S - 1)})
    state["pari"] = {"A000001": 1.0, "A000002": 1.0}
    assert get(client)["n"] == 2


def test_warming_the_pool_builds_it_under_the_budgets_the_page_will_ask_for(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    other = replace(config.DEFAULT_BUDGETS, verify_wall_s=17)
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0), ("A000002", 1.0)], budgets=attempt.budgets_json(other))
    dashboard.warm_live_pool()
    assert [b for _, b in state["calls"]] == [other]
    get(client)
    assert len(state["calls"]) == 1                                                  # the visit found it built


def test_a_session_that_was_killed_does_not_hide_behind_a_newer_one_that_finished(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    killed = db.start_session(conn, note="killed")                                  # recent, never finished
    db.finish_session(conn, db.start_session(conn, note="newer"))
    assert get(client)["running_session"] is None                                   # only the newest one can be running
    assert killed


def test_the_time_a_pool_was_built_is_when_it_was_built(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    before = db.now()
    out = get(client)
    assert before <= out["built_at"] <= db.now()


class _Gate:
    """A stand-in for `attempt.session_pool` that counts its builds and holds each until `release` is set."""

    def __init__(self, state, hold: bool = False):
        self.state, self.hold = state, hold
        self.started, self.release = threading.Event(), threading.Event()
        self.builds = 0
        self.lock = threading.Lock()
        if not hold:
            self.release.set()

    def __call__(self, conn, budgets, *, model, alpha=1.0):
        with self.lock:
            self.builds += 1
        self.started.set()
        assert self.release.wait(10)
        return cands(self.state["model" if model else "pari"]), _Keep()


def test_requests_that_arrive_together_wait_for_one_build_and_share_it(pm, monkeypatch):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    gate = _Gate(state, hold=True)
    monkeypatch.setattr(attempt, "session_pool", gate)
    got = []
    threads = [threading.Thread(target=lambda: got.append(dashboard.live_pool("pari", config.DEFAULT_BUDGETS)))
               for _ in range(4)]
    for t in threads:
        t.start()
    assert gate.started.wait(10)
    gate.release.set()
    for t in threads:
        t.join(10)
    assert gate.builds == 1 and len(got) == 4 and all(g is got[0] for g in got)


def test_a_request_that_waited_for_a_build_takes_it_even_though_the_database_moved_meanwhile(pm, monkeypatch):
    """While a session runs the database moves all the time; if the stamp alone decided, every waiter would
    build again as soon as the first build finished."""
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    gate = _Gate(state, hold=True)
    monkeypatch.setattr(attempt, "session_pool", gate)
    got = []
    first = threading.Thread(target=lambda: got.append(dashboard.live_pool("pari", config.DEFAULT_BUDGETS)))
    first.start()
    assert gate.started.wait(10)
    second = threading.Thread(target=lambda: got.append(dashboard.live_pool("pari", config.DEFAULT_BUDGETS)))
    second.start()
    time.sleep(0.3)                                                                  # let it reach the lock
    db.set_meta_many(conn, {"k": "written while the pool was being built"})
    gate.release.set()
    first.join(10)
    second.join(10)
    assert gate.builds == 1 and got[0] is got[1]
    dashboard.live_pool("pari", config.DEFAULT_BUDGETS)                              # asked afterwards: the database moved
    assert gate.builds == 2


def test_a_pool_that_is_cached_is_served_while_another_pool_is_being_built(pm, monkeypatch):
    client, conn, state = pm
    state["pari"], state["model"] = {"A000001": 1.0}, {"A000001": 1.0, "A000002": 1.0}
    dashboard.live_pool("pari", config.DEFAULT_BUDGETS)
    gate = _Gate(state, hold=True)
    monkeypatch.setattr(attempt, "session_pool", gate)
    slow = threading.Thread(target=lambda: dashboard.live_pool("model", config.DEFAULT_BUDGETS))
    slow.start()
    try:
        assert gate.started.wait(10)
        done = []
        fast = threading.Thread(target=lambda: done.append(dashboard.live_pool("pari", config.DEFAULT_BUDGETS)))
        fast.start()
        fast.join(5)
        assert done and not gate.release.is_set()                                     # served before the build finished
    finally:
        gate.release.set()
        slow.join(10)
    assert gate.builds == 1                                                           # the pari lookup built nothing


def test_the_same_pool_under_other_budgets_is_built_again_and_replaces_the_cached_one(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    other = replace(config.DEFAULT_BUDGETS, extend_wall_s=config.DEFAULT_BUDGETS.extend_wall_s + 1)
    dashboard.live_pool("pari", config.DEFAULT_BUDGETS)
    dashboard.live_pool("pari", other)
    assert [b for _, b in state["calls"]] == [config.DEFAULT_BUDGETS, other]
    dashboard.live_pool("pari", other)
    assert len(state["calls"]) == 2                                                   # one entry per pool: the last wins


def broken(message="oeisdata unreadable"):
    def build(conn, budgets, *, model, alpha=1.0):
        raise RuntimeError(message)
    return build


def test_a_pool_that_cannot_be_built_is_a_503_naming_the_reason_not_a_stale_map(pm, monkeypatch, caplog):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    old = dashboard.live_pool("pari", config.DEFAULT_BUDGETS)                  # a build that worked, to be asked again
    real = attempt.session_pool
    monkeypatch.setattr(attempt, "session_pool", broken())
    with caplog.at_level(logging.ERROR, logger="oeisbot.dashboard"):
        r = client.get("/api/pickmap?refresh=true")
    assert r.status_code == 503
    assert r.json() == {"error": "pool_build_failed", "reason": "RuntimeError: oeisdata unreadable"}
    (record,) = [x for x in caplog.records if x.name == "oeisbot.dashboard"]
    assert record.exc_info and "oeisdata unreadable" in caplog.text and "Traceback" in caplog.text
    assert "Traceback" not in r.text                                            # the log has the traceback, the page the reason
    assert dashboard._live["pari"] is old                                       # neither replaced by the failure nor served for it
    monkeypatch.setattr(attempt, "session_pool", real)
    assert get(client, refresh="true")["n"] == 1                                # and the next request builds again


def test_a_failed_build_is_not_cached_so_the_next_request_tries_again(pm, monkeypatch):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    real = attempt.session_pool
    monkeypatch.setattr(attempt, "session_pool", broken())
    for _ in range(2):                                                          # twice: nothing remembers the first failure
        assert client.get("/api/pickmap").status_code == 503
    assert dashboard._live == {}
    monkeypatch.setattr(attempt, "session_pool", real)
    assert get(client)["n"] == 1 and len(state["calls"]) == 1


def test_the_reason_is_one_short_line_whatever_the_error_said(pm, monkeypatch):
    client, conn, state = pm
    monkeypatch.setattr(attempt, "session_pool", broken("line one\n\tline two  " + "x" * 500))
    reason = client.get("/api/pickmap").json()["reason"]
    assert reason.startswith("RuntimeError: line one line two xxx") and len(reason) == 200
    assert "\n" not in reason and "\t" not in reason and "  " not in reason


@pytest.mark.parametrize("error, text", [
    (OSError("b-file cache unreadable"), "OSError: b-file cache unreadable"),
    (sqlite3.OperationalError("database is locked"), "OperationalError: database is locked"),
    (KeyError("A000001"), "KeyError: 'A000001'"),
    (ValueError("bad %S line"), "ValueError: bad %S line"),
])
def test_whatever_the_pool_build_raises_is_a_503_naming_it(pm, monkeypatch, error, text):
    """Not only a RuntimeError: an unreadable cache, a locked database and a malformed entry are the real causes."""
    client, conn, state = pm

    def build(conn, budgets, *, model, alpha=1.0):
        raise error

    monkeypatch.setattr(attempt, "session_pool", build)
    r = client.get("/api/pickmap")
    assert r.status_code == 503 and r.json() == {"error": "pool_build_failed", "reason": text}


def test_a_model_pool_that_cannot_be_built_leaves_the_pari_map_alone(pm, monkeypatch):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    assert get(client)["n"] == 1
    real = attempt.session_pool

    def only_the_model_breaks(conn_, budgets, *, model, alpha=1.0):
        if model:
            raise RuntimeError("no model pool today")
        return real(conn_, budgets, model=model, alpha=alpha)

    monkeypatch.setattr(attempt, "session_pool", only_the_model_breaks)
    assert client.get("/api/pickmap?pool=model").json() == {"error": "pool_build_failed",
                                                            "reason": "RuntimeError: no model pool today"}
    assert get(client)["n"] == 1


def test_a_missing_database_is_still_fastapis_own_503_and_not_a_pool_failure(pm, tmp_path, monkeypatch):
    client, conn, state = pm
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "nowhere.sqlite3")
    r = client.get("/api/pickmap")
    assert r.status_code == 503 and "no database at" in r.json()["detail"] and "error" not in r.json()
    # ... also when it is the build that finds it gone, after the route's own first look
    def vanished(*a, **k):
        raise dashboard.HTTPException(503, "no database at gone")

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite3")
    monkeypatch.setattr(dashboard, "live_pool", vanished)
    r = client.get("/api/pickmap")
    assert r.status_code == 503 and r.json() == {"detail": "no database at gone"}


def test_only_the_pool_build_is_turned_into_a_503_the_rest_of_the_route_still_fails_loudly(pm, monkeypatch):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}

    def compare_breaks(*a, **k):
        raise ValueError("a bug in the comparison")

    monkeypatch.setattr(pickmap, "compare", compare_breaks)
    r = TestClient(dashboard.app, raise_server_exceptions=False).get("/api/pickmap")
    assert r.status_code == 500 and "pool_build_failed" not in r.text


def test_each_pool_keeps_its_own_cached_build(pm):
    client, conn, state = pm
    state["pari"], state["model"] = {"A000001": 1.0}, {"A000001": 1.0, "A000002": 2.0}
    pari = dashboard.live_pool("pari", config.DEFAULT_BUDGETS)
    model = dashboard.live_pool("model", config.DEFAULT_BUDGETS)
    assert (len(pari.rows), len(model.rows)) == (1, 2)
    assert dashboard.live_pool("pari", config.DEFAULT_BUDGETS) is pari       # building the model pool left it alone
    assert dashboard.live_pool("model", config.DEFAULT_BUDGETS) is model
    assert len(state["calls"]) == 2


def test_a_pool_built_after_waiting_for_the_lock_is_stamped_with_what_it_read(pm, monkeypatch):
    """The stamp is taken once the lock is held. Taken before, a build that waited behind another pool's would
    carry the database's state from before the wait, and the next lookup would rebuild for nothing."""
    client, conn, state = pm
    state["pari"], state["model"] = {"A000001": 1.0}, {"A000001": 1.0, "A000002": 2.0}
    gate = _Gate(state, hold=True)
    monkeypatch.setattr(attempt, "session_pool", gate)
    slow = threading.Thread(target=lambda: dashboard.live_pool("model", config.DEFAULT_BUDGETS))
    slow.start()
    assert gate.started.wait(10)
    waiter = threading.Thread(target=lambda: dashboard.live_pool("pari", config.DEFAULT_BUDGETS))
    waiter.start()
    time.sleep(0.3)                                                                  # let it reach the lock
    db.set_meta_many(conn, {"k": "written while the other pool was being built"})
    gate.release.set()
    slow.join(10)
    waiter.join(10)
    assert gate.builds == 2
    dashboard.live_pool("pari", config.DEFAULT_BUDGETS)
    assert gate.builds == 2                                                          # nothing moved since it read


def test_the_database_stamp_moves_with_the_path_either_file_and_both_its_mtime_and_its_size(tmp_path, monkeypatch):
    path = tmp_path / "s.db"
    monkeypatch.setattr(config, "DB_PATH", path)
    assert dashboard._db_stamp() == (str(path), None, None)                          # nothing there: no error

    def put(p, size, mtime_ns):
        p.write_bytes(b"x" * size)
        os.utime(p, ns=(mtime_ns, mtime_ns))

    put(path, 10, 10**18)
    base = dashboard._db_stamp()
    assert base == (str(path), (10**18, 10), None)
    put(path, 10, 10**18 + 10**9)
    assert dashboard._db_stamp() != base                                             # the mtime alone
    put(path, 11, 10**18)
    assert dashboard._db_stamp() != base                                             # the size alone
    put(path, 10, 10**18)
    assert dashboard._db_stamp() == base                                             # and it is only those
    (tmp_path / "s.db-wal").write_bytes(b"w")
    assert dashboard._db_stamp() != base                                             # the WAL file counts
    (tmp_path / "s.db-wal").unlink()
    other = tmp_path / "t.db"
    put(other, 10, 10**18)
    monkeypatch.setattr(config, "DB_PATH", other)
    assert dashboard._db_stamp()[1:] == base[1:] and dashboard._db_stamp() != base   # same file stats, other database


def test_the_rules_of_the_loaded_code_are_read_once(pm, monkeypatch):
    client, conn, state = pm
    calls = []

    def fingerprint():
        calls.append(1)
        return f"fp{len(calls)}"

    monkeypatch.setattr(attempt, "rules_fingerprint", fingerprint)
    assert dashboard.rules_loaded() == "fp1" and dashboard.rules_loaded() == "fp1" and len(calls) == 1


def test_warming_the_pool_also_reads_the_rules_so_the_first_visit_does_not(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    assert dashboard._rules is None
    dashboard.warm_live_pool()
    assert dashboard._rules == attempt.rules_fingerprint()


def test_warming_the_pool_works_before_the_snapshot_tables_exist(pm):
    client, conn, state = pm
    with conn:
        conn.execute("DROP TABLE pick_snapshot_rows")
        conn.execute("DROP TABLE pick_snapshots")
    state["pari"] = {"A000001": 1.0}
    dashboard.warm_live_pool()
    assert [b for _, b in state["calls"]] == [config.DEFAULT_BUDGETS]


def test_the_live_pool_is_built_under_the_budgets_of_the_newest_snapshot_not_an_older_one(pm):
    client, conn, state = pm
    older = replace(config.DEFAULT_BUDGETS, verify_wall_s=config.DEFAULT_BUDGETS.verify_wall_s + 3)
    newer = replace(config.DEFAULT_BUDGETS, verify_wall_s=config.DEFAULT_BUDGETS.verify_wall_s + 9)
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0)], budgets=attempt.budgets_json(older))
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0), ("A000002", 1.0)], budgets=attempt.budgets_json(newer))
    state["pari"] = {"A000001": 1.0, "A000002": 1.0, "A000003": 1.0}
    get(client)
    assert state["calls"][-1][1] == newer
    dashboard._live.clear()
    dashboard.warm_live_pool()                                                       # the warm-up asks the same way
    assert state["calls"][-1][1] == newer and len(state["calls"]) == 2


@pytest.mark.parametrize("taken, loaded", [("unknown", "abc123"), ("abc123", "unknown"), (None, "abc123")])
def test_a_fingerprint_that_could_not_be_taken_on_either_side_means_we_cannot_tell(pm, monkeypatch, taken, loaded):
    client, conn, state = pm
    monkeypatch.setattr(dashboard, "_rules", loaded)
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0), ("A000002", 1.0)], rules=taken)
    state["pari"] = {"A000001": 1.0}
    out = get(client)
    assert out["baseline"]["rules_differ"] is None
    assert [t["reason"] for t in out["gone"]["top"]] == ["unexplained"]              # not "selection rules changed"


def test_the_rules_compared_are_the_baselines_not_the_newest_snapshots(pm, monkeypatch):
    client, conn, state = pm
    monkeypatch.setattr(dashboard, "_rules", "now")
    live = {"A000001": 1.0, "A000002": 1.0}
    db.record_pick_snapshot(conn, "pari", [*live.items(), ("A000003", 1.0)], rules="then")
    db.record_pick_snapshot(conn, "pari", list(live.items()), rules="now")           # equals the live pool: no baseline
    state["pari"] = dict(live)
    out = get(client)
    assert out["baseline"]["n"] == 3 and out["baseline"]["rules_differ"] is True
    assert [t["reason"] for t in out["gone"]["top"]] == ["selection rules changed"]


def test_an_unfinished_session_counts_as_running_for_a_day_and_not_beyond(pm):
    client, conn, state = pm
    state["pari"] = {"A000001": 1.0}
    sid = db.start_session(conn, note="x")
    for hours, running in ((23, True), (25, False), (24 * 7, False)):
        started = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
        with conn:
            conn.execute("UPDATE sessions SET started_at = ? WHERE id = ?", (started, sid))
        assert (get(client)["running_session"] is not None) is running, hours


def test_the_reasons_are_ordered_by_the_chance_they_hold_not_by_how_many_sequences_they_cover(pm):
    client, conn, state = pm
    db.upsert_sequences(conn, [db.SequenceRow(a, f"seq {a}", 0, "nonn,more", 20, 3, "pari", 0, False)
                               for a in ("A000002", "A000003")])
    db.record_pick_snapshot(conn, "pari", [("A000001", 0.5), ("A000002", 4.0), ("A000003", 4.0), ("A000099", 1.0)])
    with conn:
        conn.execute("UPDATE sequences SET in_more = 0")
    state["pari"] = {"A000099": 1.0}
    reasons = get(client)["gone"]["reasons"]
    assert [(r["reason"], r["n"]) for r in reasons] == [("unexplained", 1), ("left the 'more' list", 2)]


def test_the_newest_open_review_is_the_one_that_explains_a_departure(pm):
    client, conn, state = pm
    db.upsert_sequences(conn, [db.SequenceRow("A000001", "x", 0, "nonn,more", 20, 3, "pari", 0, False)])
    db.record_pick_snapshot(conn, "pari", [("A000001", 1.0), ("A000099", 1.0)])
    first = db.add_review(conn, "A000001", db.record_skip(conn, "A000001", "pari:x", "max_new_terms", outcome="extended"),
                          "artifacts/A000001/attempt-1", 2, 3)
    db.set_review_status(conn, first, "reviewing")
    db.add_review(conn, "A000001", db.record_skip(conn, "A000001", "pari:x", "max_new_terms", outcome="extended"),
                  "artifacts/A000001/attempt-2", 2, 3)
    state["pari"] = {"A000099": 1.0}
    assert [t["reason"] for t in get(client)["gone"]["top"]] == ["review new"]


def test_departures_are_looked_up_in_chunks_of_five_hundred_and_none_is_missed(pm):
    client, conn, state = pm
    assert [len(c) for c in dashboard._chunks(list(range(1201)))] == [500, 500, 201]
    assert list(dashboard._chunks([])) == []
    gone = {f"A{i:06d}": 1.0 for i in range(1, 1202)}
    db.record_pick_snapshot(conn, "pari", [*gone.items(), ("A999999", 1.0)])
    state["pari"] = {"A999999": 1.0}
    out = get(client)["gone"]
    assert out["n"] == 1201 and [(r["reason"], r["n"]) for r in out["reasons"]] == [("unexplained", 1201)]


def test_the_pool_must_be_exactly_pari_or_model(pm):
    client, conn, state = pm
    for bad in ("pariX", "xpari", "modelmodel", "Pari", ""):
        assert client.get(f"/api/pickmap?pool={bad}").status_code == 422, bad


def test_over_the_real_session_pool(tmp_path, monkeypatch):
    """No stand-in for `attempt.session_pool`: the route builds the pool a session would draw from, from a
    database row and an entry, under the budgets it is given."""
    from oeisbot.ingest import bfile, oeisdata

    from .test_attempt import make_entry
    path = tmp_path / "t.sqlite3"
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path / "artifacts")
    monkeypatch.setattr(bfile, "cached", lambda a: (True, None))
    monkeypatch.setattr(oeisdata, "load_entry", lambda a: make_entry("a(n) = prime(n)", a_number=a))
    dashboard._live.clear()
    monkeypatch.setattr(dashboard, "_rules", None)
    conn = db.connect(path)
    db.upsert_sequences(conn, [db.SequenceRow("A999999", "The primes.", 1, "nonn,more", 15, 2, "pari", 0, False),
                               db.SequenceRow("A999998", "No program.", 1, "nonn,more", 15, 2, "", 0, False)])
    for a in ("A999999", "A999998"):
        db.update_bfile_info(conn, a, "absent")
    conn.close()
    try:
        client = TestClient(dashboard.app)
        pari = get(client)
        assert [r["a"] for r in pari["rows"]] == ["A999999"] and math.isclose(pari["rows"][0]["p"], 1.0)
        assert pari["rows"][0]["d"] == pytest.approx(0.3 * (1 + math.log10(1 + 15 / 50)))
        assert get(client, pool="model")["n"] == 2
    finally:
        dashboard._live.clear()
