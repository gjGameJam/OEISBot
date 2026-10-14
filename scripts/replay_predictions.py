"""Replay every stored prediction from its attempt's term log, and optionally backfill the cost fit's
statistics onto rows that predate them.

Why this exists. `predictions` stores what the estimator *decided* (`trustworthy`, `feasible`, the
seconds) but, before 2026-09-21, not what it decided *from*. `Projection.npoints` and
`Assessment.rate_drift` are recoverable from nothing else, so a question as basic as "has a trustworthy
cost fit ever happened, and on how many points?" could only be answered by replaying a term log by hand
-- which is how session 7's audit found A229209's 5-point fit, and how it missed it for so long.

What makes the replay trustworthy is that it re-derives values that *are* stored, and compares them.
`estimate.project` and its fitting primitives, and `verify.Harness.points`, have not changed since the
first attempt in this database, so a replay reproduces `model`, `predicted_s`, `predicted_s_low`,
`predicted_s_high`, `predicted_mem`, `value_dependent` and `trustworthy` exactly -- 40 of 40 rows when
this was written. The five unstored values come out of the same `estimate.assess` call that reproduces
those seven, so a clean comparison is the evidence that the backfilled numbers are the ones the run
itself computed. `trustworthy` earns its place in that list: it is
`fit_trustworthy and rate_drift <= over_prediction_factor`, so it is the only stored column that
constrains a replayed `rate_drift` at all.

`feasible` is reproduced only for attempts that recorded both budgets it depends on
(`extra.extend_wall_s`, added 2026-09-18, and `extra.mem_cap_bytes`, added 2026-09-20); elsewhere it is
reported as unchecked rather than compared against a guess. `reasons` is not stored at all.

A row that cannot be replayed at all is counted and reported separately, never as a row that
reproduced: no term log, a log pruned or truncated past the term the projection was made from, a log
holding two runs, a log that belongs to a *different* run (wrong program sha, wrong known-term count, or
named by two attempts at once), a sequence no longer in `sequences`, an unreadable `extra`. `data/runs/` is gitignored local state that nothing cleans up but nothing protects either,
and this script's summary is the evidence for the backfill, so it must not be able to say "40 of 40"
about rows it never looked at.

Read-only unless `--write`. `--write` fills only rows where every fit column is still NULL, so it can
never overwrite a value the run itself recorded with a replayed one -- the two can differ, for instance
if `oeisbot sync` has changed a sequence's name since the run (the name feeds `value_dependent`).

    .venv\\Scripts\\python scripts\\replay_predictions.py           # check every row, write nothing
    .venv\\Scripts\\python scripts\\replay_predictions.py --write   # add the columns and backfill
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from oeisbot import config, db, estimate                                      # noqa: E402

# the columns this script fills, in the order `predictions` declares them
FIT_COLUMNS = ("fit_trustworthy", "fit_npoints", "fit_disagreement", "fit_climbing", "rate_drift")
REL_TOLERANCE = 1e-9


@dataclass
class Replayed:
    row: sqlite3.Row
    values: dict[str, object] = field(default_factory=dict)      # the five fit columns
    checks: list[tuple[str, object, object]] = field(default_factory=list)   # field, stored, replayed
    problems: list[str] = field(default_factory=list)            # could not be replayed at all
    notes: list[str] = field(default_factory=list)               # replayed, but something was left unchecked

    @property
    def replayed(self) -> bool:
        """Whether anything was actually compared. A row that could not be replayed has no checks, so it
        must never be counted among the rows that reproduced -- nor among those with no cost fit."""
        return bool(self.checks)

    @property
    def disagreements(self) -> list[tuple[str, object, object]]:
        return [(f, s, r) for f, s, r in self.checks if not _same(s, r)]


def _same(stored, replayed) -> bool:
    if stored is None or replayed is None:
        return stored is None and replayed is None
    if isinstance(stored, str) or isinstance(replayed, str):
        return stored == replayed
    if isinstance(stored, (int, float)) and isinstance(replayed, (int, float)):
        return abs(stored - replayed) <= REL_TOLERANCE * max(1.0, abs(stored), abs(replayed))
    return stored == replayed


def load_log(path: Path) -> list[dict]:
    """A term log, checked. `Harness._log` opens the file with "a" and the name carries a whole-second
    timestamp, so two runs of the same program on the same sequence within one second would append into
    one file. That has never happened, but a file holding two runs would silently replay as one, so the
    indices are checked to be strictly consecutive before anything is fitted."""
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise ValueError(f"{path.name}: no term records")
    ns = [r["n"] for r in records]
    if ns != list(range(ns[0], ns[0] + len(ns))):
        raise ValueError(f"{path.name}: indices are not strictly consecutive (two runs in one file?)")
    return records


def check_log_belongs(row: sqlite3.Row, path: Path, records: list[dict]) -> None:
    """That the log is the *right* file, not merely a well-formed one.

    `load_log` already refuses a file holding two runs, so one run in the wrong file should not pass
    either. `extra.log` is machine-written and correct today; these guard a later hand-edit. The run log
    is named `<A-number>-<local timestamp>-<program sha8>`, and the attempt records both its
    `program_sha` and how many known terms it reproduced.

    Two runs of the *same* program on the *same* sequence share both of those, and differ only in the
    log's timestamp. Rather than read a local time back against a UTC `started_at` -- wrong the first
    time the machine's offset changes, and a false positive here blocks `--write` -- `shared_logs`
    catches that case from the other side: one run per file means one file per attempt."""
    sha = row["program_sha"]
    if sha and not path.stem.endswith(f"-{sha[:8]}"):
        raise ValueError(f"log {path.name} does not carry this attempt's program sha {sha[:8]}")
    if row["known_terms"] is not None:
        known = sum(1 for r in records if r["kind"] == "known")
        if known != row["known_terms"]:
            raise ValueError(f"log {path.name} has {known} known terms, the attempt recorded "
                             f"{row['known_terms']}: a different run?")


def shared_logs(conn: sqlite3.Connection) -> dict[str, list[int]]:
    """Log paths named by more than one attempt, against every attempt in the database, not only those
    with predictions. `Harness._log` writes one file per run, so two attempts naming one file means at
    least one of them names a file that is not its own -- the one wrong-file case the per-row checks
    cannot see, since a re-run of the same program on the same sequence matches on every other field."""
    used: dict[str, list[int]] = {}
    for row in conn.execute("SELECT id, json_extract(extra, '$.log') AS log FROM attempts "
                            "WHERE json_valid(extra) AND json_extract(extra, '$.log') IS NOT NULL"):
        used.setdefault(row["log"], []).append(row["id"])
    return {log: ids for log, ids in used.items() if len(ids) > 1}


def replay_row(row: sqlite3.Row, records: list[dict], name: str) -> Replayed:
    """Re-derive one stored prediction from the terms that preceded it.

    The point set is `Harness.points()`: every record after the first (the first carries interpreter
    start-up cost), with no regard to `kind`, up to the term that triggered the projection. `kind` is
    read only to find the last *known* term, which is safe -- the only relabelling that happens after a
    record is logged is `new` -> `void` (`verify.on_line`), so a logged `known` stays `known`."""
    out = Replayed(row)
    unit = row["cost_unit"]
    before = [r for r in records[1:] if r["n"] < row["n"]]
    points = [estimate.Point(r["n"], float(r["dwork"] if unit == "work" else r["dcpu"]), r["dt"],
                             float(r["mem"]), int(r["value"])) for r in before]

    # A projection is made the instant term n-1 arrives, and only after the known terms have been
    # reproduced, so both of these are in every intact log. Their absence means the log no longer holds
    # the run this row came from -- a truncated or pruned file -- which is a reason not to trust the
    # point set either, not merely a missing budget. Raising makes the row `unreplayed`; calling it a
    # note would leave it counted among the rows that reproduced, under a message naming the wrong cause
    known = [r for r in records if r["kind"] == "known"]
    trigger = next((r for r in records if r["n"] == row["n"] - 1), None)
    if trigger is None:
        raise ValueError(f"the log has no term a({row['n'] - 1}), the one this projection was made from: "
                         "truncated?")
    if not known:
        raise ValueError("the log has no known terms, so it cannot say when verification completed")

    # the budgets `Harness._project_next` used, when the attempt recorded them; otherwise the feasibility
    # verdict is not reproducible and is left out of the comparison rather than guessed at
    extra = json.loads(row["extra"] or "{}")
    extend_s, mem_cap = extra.get("extend_wall_s"), extra.get("mem_cap_bytes")
    if extend_s is not None and mem_cap is not None:
        time_budget, mem_budget = extend_s - (trigger["t"] - known[-1]["t"]), float(mem_cap)
    else:
        time_budget, mem_budget = math.inf, math.inf
        missing = [k for k, v in (("extend_wall_s", extend_s), ("mem_cap_bytes", mem_cap)) if v is None]
        out.notes.append(f"feasible not checked: the attempt recorded no {' or '.join(missing)}")

    a = estimate.assess(points, row["n"], unit=unit, time_budget_s=time_budget, mem_budget=mem_budget,
                        name=name)
    cost = a.cost
    out.values = {
        "fit_trustworthy": None if cost is None else int(cost.trustworthy),
        "fit_npoints": None if cost is None else cost.npoints,
        "fit_disagreement": None if cost is None else cost.disagreement,
        "fit_climbing": None if cost is None else int(cost.climbing),
        "rate_drift": a.rate_drift,
    }
    out.checks = [
        ("model", row["model"], cost.model if cost else None),
        ("predicted_s", row["predicted_s"], a.seconds),
        ("predicted_s_low", row["predicted_s_low"], a.seconds_low),
        ("predicted_s_high", row["predicted_s_high"], a.seconds_high),
        ("predicted_mem", row["predicted_mem"], a.mem_high),
        ("value_dependent", row["value_dependent"], int(a.value_dependent)),
        # the only stored column that constrains `rate_drift`. The kill factor is not recorded per run,
        # but it has only ever had its default value and no command exposes it (`config.Budgets`)
        ("trustworthy", row["trustworthy"], int(a.trusted(config.Budgets.over_prediction_factor))),
    ]
    if math.isfinite(time_budget):
        out.checks.append(("feasible", row["feasible"], int(a.feasible)))
    return out


def replay_all(conn: sqlite3.Connection) -> list[Replayed]:
    rows = conn.execute("""
        SELECT p.*, a.a_number, a.extra, a.program_sha, a.known_terms,
               (SELECT s.name FROM sequences s WHERE s.a_number = a.a_number) AS name
        FROM predictions p JOIN attempts a ON a.id = p.attempt_id ORDER BY p.id""").fetchall()
    duplicated = shared_logs(conn)
    done = []
    for row in rows:
        out = Replayed(row)
        try:
            # `extra` is hand-editable JSON, so a malformed one is a problem with that row, not a reason
            # to abandon the other 39
            extra = json.loads(row["extra"] or "{}")
            log = extra.get("log") if isinstance(extra, dict) else None
            if not isinstance(extra, dict):
                out.problems.append(f"`extra` is {type(extra).__name__}, not an object")
            elif row["name"] is None:
                # the name feeds `name_suggests_search` -> `value_dependent`; replaying with "" would
                # quietly change the verdict rather than fail
                out.problems.append(f"{row['a_number']} has no `sequences` row, so its name is unknown")
            elif not log:
                out.problems.append("the attempt names no term log")
            elif not Path(log).exists():
                out.problems.append(f"term log missing: {log}")
            elif log in duplicated:
                others = [i for i in duplicated[log] if i != row["attempt_id"]]
                out.problems.append(f"term log is also named by attempt(s) {others}, so at least one of "
                                    f"them is not its own run: {log}")
            else:
                records = load_log(Path(log))
                check_log_belongs(row, Path(log), records)
                out = replay_row(row, records, row["name"])
        except (ValueError, KeyError, TypeError, OSError) as e:
            out = Replayed(row, problems=[f"{type(e).__name__}: {e}"])
        done.append(out)
    return done


def add_columns(conn: sqlite3.Connection) -> list[str]:
    """`ALTER TABLE ADD COLUMN` for whichever fit columns are missing. This project has no migration
    framework (see CLAUDE.md); `db.connect` runs `CREATE TABLE IF NOT EXISTS`, which leaves an existing
    table alone, so an established database gets these columns here or not at all. The types match
    `db.SCHEMA`, which lists them last for exactly this reason: ADD COLUMN can only append."""
    have = {r["name"] for r in conn.execute("PRAGMA table_info(predictions)")}
    types = {"fit_trustworthy": "INTEGER", "fit_npoints": "INTEGER", "fit_disagreement": "REAL",
             "fit_climbing": "INTEGER", "rate_drift": "REAL"}
    added = [c for c in FIT_COLUMNS if c not in have]
    for column in added:
        conn.execute(f"ALTER TABLE predictions ADD COLUMN {column} {types[column]}")
    return added


def write_backfill(conn: sqlite3.Connection, done: list[Replayed]) -> tuple[int, list[str]]:
    """Add the columns and fill them, in one transaction that either lands whole or not at all.

    `sqlite3` auto-BEGINs before the first statement that changes the database, so a hand-written
    `BEGIN IMMEDIATE` needs `isolation_level = None` first; nothing in `oeisbot.db` may be called here,
    because those helpers commit with `with conn:`."""
    conn.isolation_level = None
    conn.execute("BEGIN IMMEDIATE")
    try:
        added = add_columns(conn)
        written = 0
        for out in done:
            if not out.values or out.disagreements:
                continue
            if all(v is None for v in out.values.values()):
                # the run fitted nothing, so NULL is already the right answer and there is no way to tell
                # such a row from an unfilled one. Writing NULLs over NULLs would make every later run
                # report rows it had not changed
                continue
            # only ever fill a row that has nothing: a value the run recorded itself is never replaced by
            # a replayed one, so running this twice cannot rewrite history
            current = conn.execute(f"SELECT {', '.join(FIT_COLUMNS)} FROM predictions WHERE id = ?",
                                   (out.row["id"],)).fetchone()
            if any(v is not None for v in current):
                continue
            conn.execute(f"UPDATE predictions SET {', '.join(c + ' = ?' for c in FIT_COLUMNS)} WHERE id = ?",
                         (*[out.values[c] for c in FIT_COLUMNS], out.row["id"]))
            written += 1
        conn.execute("INSERT INTO meta(key, value) VALUES ('schema_version', ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (str(db.SCHEMA_VERSION),))
        conn.execute("COMMIT")
        return written, added
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=config.DB_PATH, help="database to read (default: the project's)")
    ap.add_argument("--write", action="store_true", help="add the fit columns and backfill rows that have none")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    done = replay_all(conn)

    replayed = [d for d in done if d.replayed]
    unreplayed = [d for d in done if not d.replayed]
    fitted = [d for d in replayed if d.values.get("fit_npoints") is not None]
    trusted = [d for d in fitted if d.values["fit_trustworthy"] == 1]
    bad = [d for d in done if d.disagreements]
    print(f"{len(done)} stored predictions; {len(replayed)} replayed "
          f"({len(replayed) - len(fitted)} with no cost fit, {len(fitted)} with one, "
          f"{len(trusted)} of those trustworthy)"
          + (f"; {len(unreplayed)} COULD NOT BE REPLAYED" if unreplayed else ""))
    for d in trusted:
        v = d.values
        print(f"  trustworthy fit: prediction #{d.row['id']} attempt #{d.row['attempt_id']} {d.row['a_number']} "
              f"n={d.row['n']} model={d.row['model']} npoints={v['fit_npoints']} "
              f"disagreement={v['fit_disagreement']:.4g} rate_drift={v['rate_drift']:.4g} "
              f"(stored trustworthy={d.row['trustworthy']})")
    # notes are the ordinary state of the older rows, so they are summarised rather than repeated: a run
    # that printed 17 identical lines would be the last place a real diagnostic got read
    grouped: dict[str, list[int]] = {}
    for d in done:
        for note in d.notes:
            grouped.setdefault(note, []).append(d.row["id"])
    for note, ids in grouped.items():
        shown = ", ".join(f"#{i}" for i in ids[:6]) + (f" and {len(ids) - 6} more" if len(ids) > 6 else "")
        print(f"  note: {len(ids)} row{'s' if len(ids) != 1 else ''} ({shown}): {note}")
    for d in unreplayed:
        for problem in d.problems:
            print(f"  NOT REPLAYED: prediction #{d.row['id']} (attempt #{d.row['attempt_id']} "
                  f"{d.row['a_number']}): {problem}")
    for d in bad:
        for f, stored, got in d.disagreements:
            print(f"  DISAGREES: prediction #{d.row['id']} {f}: stored {stored!r}, replayed {got!r}")
    print(f"replay reproduces the stored values for {len(replayed) - len(bad)} of {len(replayed)} "
          f"replayed rows ({len(done)} stored)")

    try:
        if args.write:
            if bad or unreplayed:
                print("refusing to write: the replay must reproduce every stored row first "
                      f"({len(bad)} disagreeing, {len(unreplayed)} not replayed)")
                return 1
            written, added = write_backfill(conn, done)
            print(f"added columns: {', '.join(added) or 'none (already present)'}; backfilled {written} rows")
    finally:
        conn.close()
    return 1 if bad or unreplayed else 0


if __name__ == "__main__":
    raise SystemExit(main())
