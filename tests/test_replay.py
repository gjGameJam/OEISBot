"""`scripts/replay_predictions.py`: the backfill, and the guards that make its summary evidence.

This script is unusual in the repo: a committed helper whose *output* is the justification for a change
already made to the database. It said "40 of 40 rows reproduce exactly", and the docs quote that. Two
audit rounds found two different ways it could say so about rows it had never looked at -- first a row
whose log was missing, then one whose log had been truncated past the term the projection was made from
-- and in both cases it exited 0 and `--write` would have proceeded. The defect was never in the
arithmetic; it was in the bookkeeping around it. So what is tested here is the bookkeeping: that a row
which cannot be replayed is never counted among the rows that reproduced, that every way that can happen
is reported and blocks the write, and that the write itself is atomic and idempotent.

The fixtures are synthetic: a database built from `db.SCHEMA` minus the fit columns, so the script's own
`ALTER TABLE` runs, and a term log written by hand. Nothing here touches the real database.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from oeisbot import db, estimate
from oeisbot.config import Budgets

ROOT = Path(__file__).resolve().parent.parent


def load_script():
    """Import the script by path: `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location("replay_predictions", ROOT / "scripts" / "replay_predictions.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rp = load_script()

SEQUENCE_NAME = "A plain sequence of numbers"
# a doubling cost, every term above the work floor, so `estimate.project` fits it and every fit column
# comes out non-NULL -- a row the backfill must actually write
TERMS = [{"n": n, "value": str(2 ** n), "t": 0.5 * (n - 1), "cpu_s": 0.0, "work": 100 * (2 ** n),
          "mem": 8_000_000, "dt": 0.5, "dcpu": 0.4, "dwork": 100 * (2 ** n), "kind": "known" if n <= 8 else "new"}
         for n in range(1, 12)]


def write_log(path: Path, terms=None) -> Path:
    path.write_text("\n".join(json.dumps(t) for t in (TERMS if terms is None else terms)) + "\n",
                    encoding="utf-8")
    return path


# `predictions` as it stood before 2026-09-21. Spelled out rather than produced by dropping columns from
# `db.SCHEMA`: SQLite's DROP COLUMN re-parses the stored CREATE statement and chokes on its comments, and
# this is in any case the exact shape the script has to find in a database it has not seen before.
LEGACY_PREDICTIONS = """
DROP TABLE predictions;
CREATE TABLE predictions (
    id               INTEGER PRIMARY KEY,
    attempt_id       INTEGER NOT NULL REFERENCES attempts(id),
    n                INTEGER NOT NULL,
    cost_unit        TEXT NOT NULL,
    predicted_s      REAL,
    predicted_s_low  REAL,
    predicted_s_high REAL,
    predicted_mem    REAL,
    model            TEXT,
    trustworthy      INTEGER NOT NULL,
    feasible         INTEGER NOT NULL,
    value_dependent  INTEGER NOT NULL,
    actual_s         REAL,
    actual_mem       REAL,
    censored_s       REAL
);
"""


@pytest.fixture
def db_path(tmp_path):
    """A database whose `predictions` table predates the fit columns, and one attempt with a term log."""
    log = write_log(tmp_path / "A000001-20260101-000000-abcdef12.jsonl")
    path = tmp_path / "t.sqlite3"
    conn = db.connect(path)
    with conn:
        conn.executescript(LEGACY_PREDICTIONS)
    with conn:
        conn.execute("INSERT INTO sequences(a_number, name, offset, keywords, data_terms, program_langs,"
                     " more_credits, value_dependent, synced_at) VALUES"
                     " ('A000001', ?, 1, 'nonn,more', 8, 'pari', 0, 0, ?)", (SEQUENCE_NAME, db.now()))
        conn.execute("INSERT INTO attempts(id, a_number, strategy, program_sha, started_at, verified,"
                     " known_terms, new_terms, runtime_s, cost_unit, outcome, failure_mode, extra)"
                     " VALUES (1, 'A000001', 'pari:a(n)', 'abcdef12ff', ?, 1, 8, 2, 10.0, 'work',"
                     " 'extended', 'max_new_terms', ?)",
                     (db.now(), json.dumps({"log": str(log), "extend_wall_s": 600.0, "mem_cap_bytes": 2 << 30})))
    conn.close()
    return path, log


def seed_prediction(path: Path, n: int = 11) -> None:
    """Record the prediction this log would really have produced.

    Derived here from `estimate.assess` directly rather than by calling the script: a fixture built with
    the code under test would agree with it no matter what either of them did. This mirrors
    `verify.Harness.points` and `_project_next` the long way round, so the replay has something
    independently arrived at to reproduce."""
    records = [json.loads(line) for line in (Path(json.loads(
        sqlite3.connect(path).execute("SELECT extra FROM attempts WHERE id = 1").fetchone()[0])["log"]))
        .read_text(encoding="utf-8").splitlines()]
    points = [estimate.Point(r["n"], float(r["dwork"]), r["dt"], float(r["mem"]), int(r["value"]))
              for r in records[1:] if r["n"] < n]
    trigger = next(r for r in records if r["n"] == n - 1)
    verified_at = [r for r in records if r["kind"] == "known"][-1]["t"]
    a = estimate.assess(points, n, unit="work", time_budget_s=600.0 - (trigger["t"] - verified_at),
                        mem_budget=float(2 << 30), name=SEQUENCE_NAME)
    conn = sqlite3.connect(path)
    with conn:
        conn.execute("INSERT INTO predictions(attempt_id, n, cost_unit, predicted_s, predicted_s_low,"
                     " predicted_s_high, predicted_mem, model, trustworthy, feasible, value_dependent)"
                     " VALUES (1, ?, 'work', ?, ?, ?, ?, ?, ?, ?, ?)",
                     (n, a.seconds, a.seconds_low, a.seconds_high, a.mem_high,
                      a.cost.model if a.cost else None,
                      int(a.trusted(Budgets.over_prediction_factor)), int(a.feasible), int(a.value_dependent)))
    conn.close()


def run(path: Path, *args: str) -> tuple[int, str]:
    argv = sys.argv
    sys.argv = ["replay_predictions.py", "--db", str(path), *args]
    try:
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = rp.main()
        return code, buf.getvalue()
    finally:
        sys.argv = argv


def fit_columns_present(path: Path) -> bool:
    conn = sqlite3.connect(path)
    try:
        return "fit_npoints" in {r[1] for r in conn.execute("PRAGMA table_info(predictions)")}
    finally:
        conn.close()


def filled_rows(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM predictions WHERE fit_npoints IS NOT NULL").fetchone()[0]
    finally:
        conn.close()


def test_a_clean_replay_reports_and_backfills(db_path):
    path, _log = db_path
    seed_prediction(path)
    code, out = run(path)
    assert code == 0 and "1 replayed" in out and "COULD NOT BE REPLAYED" not in out
    assert "reproduces the stored values for 1 of 1 replayed rows (1 stored)" in out

    code, out = run(path, "--write")
    assert code == 0 and filled_rows(path) == 1 and fit_columns_present(path)
    assert "backfilled 1 rows" in out


def seed_unfitted_prediction(path: Path, n: int = 3) -> None:
    """A prediction from too few points to fit: every fit column is legitimately NULL. 22 of the real
    database's 40 rows look like this, and they are the ones idempotence turns on."""
    conn = sqlite3.connect(path)
    with conn:
        conn.execute("INSERT INTO predictions(attempt_id, n, cost_unit, model, trustworthy, feasible,"
                     " value_dependent, predicted_mem) VALUES (1, ?, 'work', NULL, 0, 1, 0, 10000000.0)", (n,))
    conn.close()


def test_the_write_is_idempotent(db_path):
    """A second run must change nothing and say so.

    The row that decides this is one with *no* cost fit, where all-NULL is the correct final state and
    so is indistinguishable from never-written. The first version of the script rewrote those on every
    run and reported them as backfilled, so a clean database still claimed work had been done."""
    path, _log = db_path
    seed_prediction(path)
    seed_unfitted_prediction(path)
    code, out = run(path, "--write")
    assert code == 0 and "backfilled 1 rows" in out, "only the fitted row has anything to write"
    before = sqlite3.connect(path).execute("SELECT * FROM predictions").fetchall()
    code, out = run(path, "--write")
    assert code == 0 and "backfilled 0 rows" in out and "none (already present)" in out
    assert sqlite3.connect(path).execute("SELECT * FROM predictions").fetchall() == before


@pytest.mark.parametrize("break_it, expected", [
    (lambda p, log, conn: conn.execute(
        "UPDATE attempts SET extra = json_set(extra, '$.log', 'C:\\gone\\missing.jsonl')"),
     "term log missing"),
    (lambda p, log, conn: conn.execute("UPDATE attempts SET extra = 'not json at all'"),
     "JSONDecodeError"),
    (lambda p, log, conn: conn.execute("UPDATE attempts SET extra = '[1, 2]'"),
     "not an object"),
    (lambda p, log, conn: conn.execute("DELETE FROM sequences"),
     "has no `sequences` row"),
    (lambda p, log, conn: conn.execute("UPDATE attempts SET program_sha = 'ffffffffff'"),
     "does not carry this attempt's program sha"),
    (lambda p, log, conn: conn.execute("UPDATE attempts SET known_terms = 3"),
     "known terms, the attempt recorded"),
    # the log no longer holds the term the projection was made from
    (lambda p, log, conn: write_log(log, TERMS[:-2]),
     "the one this projection was made from"),
    # one run per file, so two attempts naming one file means at least one names someone else's
    (lambda p, log, conn: conn.execute(
        "INSERT INTO attempts(id, a_number, strategy, started_at, outcome, failure_mode, extra)"
        " VALUES (2, 'A000001', 'pari:a(n)', '2026-01-01', 'verified', 'extend_budget', ?)",
        (json.dumps({"log": str(log)}),)),
     "is also named by attempt"),
])
def test_a_row_that_cannot_be_replayed_is_never_counted_as_reproduced(db_path, break_it, expected):
    """Each of these once had, or could have had, the same failure: counted among the rows with no cost
    fit, counted again among the rows that reproduced, exit 0, and `--write` proceeding regardless."""
    path, log = db_path
    seed_prediction(path)
    conn = sqlite3.connect(path)
    with conn:
        break_it(path, log, conn)
    conn.close()

    code, out = run(path)
    assert code == 1, out
    assert "0 replayed" in out and "1 COULD NOT BE REPLAYED" in out
    assert "NOT REPLAYED" in out and expected in out
    assert "reproduces the stored values for 0 of 0 replayed rows (1 stored)" in out

    code, out = run(path, "--write")
    assert code == 1 and "refusing to write" in out
    assert not fit_columns_present(path), "a refused write must not leave the schema half-changed"


def test_a_disagreement_blocks_the_write(db_path):
    """The other half of the guarantee: the row replays, but to something else. Nothing may be written,
    because the replay is the only evidence that the backfilled numbers are the run's own."""
    path, _log = db_path
    seed_prediction(path)
    conn = sqlite3.connect(path)
    with conn:
        conn.execute("UPDATE predictions SET model = 'ratio'")
    conn.close()
    code, out = run(path, "--write")
    assert code == 1 and "DISAGREES" in out and "model" in out
    assert "refusing to write" in out and not fit_columns_present(path)


def test_the_write_is_all_or_nothing(db_path, monkeypatch):
    """`ALTER TABLE` is transactional in SQLite, so a failure part way must take the columns with it."""
    path, _log = db_path
    seed_prediction(path)
    real = rp.add_columns

    def explode(conn):
        real(conn)
        raise RuntimeError("injected, after the ALTER")

    monkeypatch.setattr(rp, "add_columns", explode)
    with pytest.raises(RuntimeError):
        run(path, "--write")
    assert not fit_columns_present(path), "a failed write must take the ALTER with it"
