"""Attempts database (build step 4). SQLite in WAL mode: the harness writes, the dashboard only reads.

One row per attempt; one row per projected term (predicted vs actual cost) so the estimator can be
checked; review rows track what a human has done with each success so nothing is submitted twice.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import config, guard

# 2 since 2026-09-21: `predictions` gained the cost fit's own statistics. Advisory only -- nothing reads
# it, and `connect` writes it with INSERT OR IGNORE, so an existing database keeps whatever it has unless
# a migration sets it (the one-off backfill did).
SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS sequences (
    a_number          TEXT PRIMARY KEY,        -- 'A123456'
    name              TEXT NOT NULL,
    offset            INTEGER NOT NULL,
    keywords          TEXT NOT NULL,           -- comma separated, as on the %K line
    data_terms        INTEGER NOT NULL,        -- terms on the DATA lines
    data_last_digits  INTEGER,
    program_langs     TEXT NOT NULL,           -- comma separated: pari, mathematica, maple, python, ...
    more_credits      INTEGER NOT NULL,        -- "More terms from ..." style %E credits
    value_dependent   INTEGER NOT NULL DEFAULT 0,
    bfile_status      TEXT,                    -- NULL not fetched | present | absent | error
    bfile_terms       INTEGER,
    bfile_last_index  INTEGER,
    bfile_last_digits INTEGER,
    difficulty        REAL,
    in_more           INTEGER NOT NULL DEFAULT 1,  -- still keyword 'more' at the last sync
    synced_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    attempts    INTEGER NOT NULL DEFAULT 0,
    wins        INTEGER NOT NULL DEFAULT 0,
    machine_s   REAL NOT NULL DEFAULT 0,
    note        TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
    id                    INTEGER PRIMARY KEY,
    session_id            INTEGER REFERENCES sessions(id),
    a_number              TEXT NOT NULL,
    strategy              TEXT NOT NULL,       -- e.g. 'pari:a(n)', 'python:model'
    program_origin        TEXT,
    program_sha           TEXT,
    started_at            TEXT NOT NULL,
    finished_at           TEXT,
    verified              INTEGER NOT NULL DEFAULT 0,
    known_terms           INTEGER,
    known_source          TEXT,
    reproduced            INTEGER,
    new_terms             INTEGER NOT NULL DEFAULT 0,
    runtime_s             REAL,
    cpu_s                 REAL,
    peak_mem_bytes        INTEGER,
    cost_unit             TEXT,
    projected_next_s_low  REAL,                -- the last projection made (for the term never reached)
    projected_next_s_high REAL,
    projected_next_mem    REAL,
    outcome               TEXT NOT NULL,       -- extended | verified | failed | skipped | superseded | recheck_pending
    failure_mode          TEXT,                -- why it stopped (verify.Stop value, or a skip reason)
    detail                TEXT,
    extra                 TEXT,                -- JSON
    artifact_path         TEXT
);
CREATE INDEX IF NOT EXISTS attempts_a ON attempts(a_number);
CREATE INDEX IF NOT EXISTS attempts_failure ON attempts(failure_mode);
CREATE INDEX IF NOT EXISTS attempts_started ON attempts(started_at);

CREATE TABLE IF NOT EXISTS predictions (
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
    actual_s         REAL,                     -- NULL if the term never finished
    actual_mem       REAL,
    censored_s       REAL,                     -- still running when stopped: at least this long
    -- The cost fit's own statistics (estimate.Projection) and the rate drift: what `trustworthy` above
    -- was decided from. All NULL together, exactly when nothing could be fitted -- so NULL means "no
    -- cost fit", never "the fit said no". `trustworthy` is the kill's permission (Assessment.trusted) =
    -- fit_trustworthy AND rate_drift <= the kill factor, so a sound fit withdrawn by the drift alone
    -- reads trustworthy = 0, fit_trustworthy = 1.
    -- Added 2026-09-21. Rows written before then were backfilled by replaying their term logs
    -- (scripts/replay_predictions.py), so the same rule holds for them; a row would be NULL for any
    -- other reason only if its log had been pruned, and none had.
    -- Listed last so that a database created from this schema matches one altered in place: ALTER TABLE
    -- ADD COLUMN can only append.
    fit_trustworthy  INTEGER,
    fit_npoints      INTEGER,
    fit_disagreement REAL,
    fit_climbing     INTEGER,
    rate_drift       REAL
);
CREATE INDEX IF NOT EXISTS predictions_attempt ON predictions(attempt_id);

CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY,
    a_number        TEXT NOT NULL,
    attempt_id      INTEGER NOT NULL UNIQUE REFERENCES attempts(id),
    artifact_path   TEXT NOT NULL,
    first_new_index INTEGER NOT NULL,
    last_new_index  INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'reviewing', 'submitted', 'rejected')),
    note            TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS reviews_a ON reviews(a_number);

-- The pool a session picks from, as it stood at some moment: one row per candidate with its effective
-- difficulty. A pick chance is derived (weight / sum of weights, for any alpha), so storing the difficulty
-- keeps every alpha answerable. `pool` is 'pari' for `oeisbot run`, 'model' for `run --model`: the two
-- pools differ in size and in what they exclude, so a snapshot is only ever compared with its own pool.
-- `digest` is a hash of the rows, so an unchanged pool is not stored twice. `budgets` (JSON) and `rules` (a
-- hash of the selection code) say what the pool was built under: membership depends on both (a dead end is
-- relative to a budget, and the gates are code), so the Pick map warns when the live pool is built under
-- others rather than reading every difference as something that happened to a sequence. `pool` is validated
-- in Python (POOLS), not here, so a third pool needs no schema change.
CREATE TABLE IF NOT EXISTS pick_snapshots (
    id         INTEGER PRIMARY KEY,
    pool       TEXT NOT NULL,
    taken_at   TEXT NOT NULL,
    session_id INTEGER REFERENCES sessions(id),
    n          INTEGER NOT NULL,
    digest     TEXT NOT NULL,
    budgets    TEXT,
    rules      TEXT
);
CREATE INDEX IF NOT EXISTS pick_snapshots_pool ON pick_snapshots(pool, id);
CREATE TABLE IF NOT EXISTS pick_snapshot_rows (
    snapshot_id INTEGER NOT NULL REFERENCES pick_snapshots(id) ON DELETE CASCADE,
    a_number    TEXT NOT NULL,
    difficulty  REAL NOT NULL,
    PRIMARY KEY (snapshot_id, a_number)
) WITHOUT ROWID;
"""

OPEN_REVIEW_STATUSES = ("new", "reviewing", "submitted")
# failures that will repeat identically if the same program is run again on the same known terms
DETERMINISTIC_FAILURES = ("wrong_term", "bad_index", "protocol", "crash", "incomplete")
# a verified run that used its whole extension without a new term is a dead end only if it had the CPU:
# a run starved by a busy machine did less work than its budget allows. Real runs had 0.93-0.99.
# Since item 58 a `verify_timeout` needs the same fraction of the verify budget on the CPU (see
# is_dead_end); the name is kept.
EXTEND_DEAD_END_MIN_CPU_SHARE = 0.8
# The stop a run is recorded under when its caller asked it to stop (verify.Stop.INTERRUPTED, spelled
# out here because this module cannot import verify). Never a dead end, and select.candidates leaves
# such rows out of the failure penalty: the run says nothing about its program or its sequence.
INTERRUPTED = "interrupted"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _opt_int(flag: bool | None) -> int | None:
    """A nullable flag as 0/1, keeping None as NULL: `int(None)` raises, and `None` must stay NULL to
    mean "no cost fit" rather than "the fit said no"."""
    return None if flag is None else int(flag)


def connect(path: Path = config.DB_PATH, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    else:
        guard.refuse_if_real(path, "opening the database for writing")     # never from a test (oeisbot.guard)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    if not readonly:
        with conn:
            conn.executescript(SCHEMA)
            conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
    return conn


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    with conn:
        conn.execute("INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (key, value))


def set_meta_many(conn: sqlite3.Connection, values: dict[str, str]) -> None:
    """Several `meta` keys in **one** transaction, so a crash cannot leave a fresh value beside a stale
    one. `set_meta` opens a transaction per call, which is fine for a lone key and wrong for a set that
    describes one moment -- the runtime versions being the case it was added for."""
    with conn:
        conn.executemany("INSERT INTO meta(key, value) VALUES (?, ?) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value", sorted(values.items()))


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


# ------------------------------------------------------------------ sessions

def start_session(conn: sqlite3.Connection, note: str = "") -> int:
    with conn:
        return conn.execute("INSERT INTO sessions(started_at, note) VALUES (?, ?)", (now(), note)).lastrowid


def finish_session(conn: sqlite3.Connection, session_id: int) -> None:
    with conn:
        conn.execute("""
            UPDATE sessions SET finished_at = ?,
                attempts = (SELECT COUNT(*) FROM attempts WHERE session_id = ?),
                wins = (SELECT COUNT(*) FROM attempts WHERE session_id = ? AND outcome = 'extended'),
                machine_s = (SELECT COALESCE(SUM(runtime_s), 0) FROM attempts WHERE session_id = ?)
            WHERE id = ?""", (now(), session_id, session_id, session_id, session_id))


# ------------------------------------------------------------------ attempts

def record_attempt(conn: sqlite3.Connection, result, *, started_at: str, session_id: int | None = None,
                   artifact_path: str | None = None, outcome: str | None = None, extra: dict | None = None) -> int:
    """Store a verify.AttemptResult and its predictions."""
    last = result.predictions[-1] if result.predictions else None
    with conn:
        attempt_id = conn.execute("""
            INSERT INTO attempts(session_id, a_number, strategy, program_origin, program_sha, started_at, finished_at,
                verified, known_terms, known_source, reproduced, new_terms, runtime_s, cpu_s, peak_mem_bytes, cost_unit,
                projected_next_s_low, projected_next_s_high, projected_next_mem, outcome, failure_mode, detail, extra,
                artifact_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
            session_id, result.known.a_number, result.program.strategy, result.program.origin, result.program.sha,
            started_at, now(), int(result.verified), result.known.count, result.known.source, result.reproduced,
            len(result.new_terms), result.run.wall_s, result.run.cpu_s, result.peak_mem_bytes, result.cost_unit,
            last.seconds_low if last else None, last.seconds_high if last else None, last.mem_high if last else None,
            outcome or result.outcome, result.stop.value, result.detail, json.dumps(extra or {}), artifact_path,
        )).lastrowid
        conn.executemany("""
            INSERT INTO predictions(attempt_id, n, cost_unit, predicted_s, predicted_s_low, predicted_s_high,
                predicted_mem, model, trustworthy, feasible, value_dependent, actual_s, actual_mem, censored_s,
                fit_trustworthy, fit_npoints, fit_disagreement, fit_climbing, rate_drift)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", [
            (attempt_id, p.n, p.unit, p.seconds, p.seconds_low, p.seconds_high, p.mem_high, p.model,
             int(p.trustworthy), int(p.feasible), int(p.value_dependent), p.actual_s, p.actual_mem, p.censored_s,
             _opt_int(p.fit_trustworthy), p.fit_npoints, p.fit_disagreement, _opt_int(p.fit_climbing), p.rate_drift)
            for p in result.predictions])
    return attempt_id


def record_skip(conn: sqlite3.Connection, a_number: str, strategy: str, reason: str, detail: str = "",
                session_id: int | None = None, outcome: str = "skipped") -> int:
    with conn:
        return conn.execute("""
            INSERT INTO attempts(session_id, a_number, strategy, started_at, finished_at, outcome, failure_mode, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, a_number, strategy, now(), now(), outcome, reason, detail)).lastrowid


_SET_RECHECK = """UPDATE attempts SET outcome = COALESCE(?, outcome), artifact_path = COALESCE(?, artifact_path),
                     extra = json_set(COALESCE(extra, '{}'), '$.recheck', ?) WHERE id = ?"""


def set_recheck_result(conn: sqlite3.Connection, attempt_id: int, note: str, outcome: str | None = None,
                       failures: int | None = None) -> None:
    """Store the re-check note in attempts.extra, and change the outcome if given. `failures`, when given,
    records how many times in a row this pending win has failed to resolve with that same note."""
    with conn:
        conn.execute(_SET_RECHECK, (outcome, None, note, attempt_id))
        if failures is not None:
            conn.execute("UPDATE attempts SET extra = json_set(COALESCE(extra, '{}'), '$.recheck_failures', ?) "
                         "WHERE id = ?", (failures, attempt_id))


def record_win(conn: sqlite3.Connection, attempt_id: int, a_number: str, artifact_path: str,
               first_new_index: int, last_new_index: int, recheck_note: str) -> int | None:
    """After a successful re-check: mark the attempt `extended` with its artifact and queue a review, in one
    transaction. Returns the review id -- or None when the review was **refused** because the sequence
    already has a `rejected` one (`ReviewRefused`, item 51). The attempt is still recorded `extended` with
    its artifact, so the terms are kept, and `extra.review_refused` names the prior review; nothing new
    appears in the inbox. The refusal is caught *inside* the transaction on purpose: raised out of it, the
    rollback would leave the attempt `recheck_pending` and `retry_pending_rechecks` would re-run the
    refusal every session, for ever."""
    with conn:
        conn.execute(_SET_RECHECK, ("extended", artifact_path, recheck_note, attempt_id))
        try:
            return _insert_review(conn, a_number, attempt_id, artifact_path, first_new_index, last_new_index)
        except ReviewRefused as e:
            conn.execute("UPDATE attempts SET extra = json_set(COALESCE(extra, '{}'), '$.review_refused', json(?)) "
                         "WHERE id = ?", (json.dumps({"prior_review": e.prior_id, "reason": str(e)}), attempt_id))
            return None


def release_recheck(conn: sqlite3.Connection, attempt_id: int, note: str) -> bool:
    """Give up on one `recheck_pending` win: the row becomes `verified`, so its sequence can be picked
    and attempted again. Returns False, and writes nothing, when the row is not `recheck_pending` -- the
    condition is in the UPDATE itself, so a re-check that resolved the row in between is not undone.

    Only `attempt.release_pending` may call this, and only for a win whose saved result can no longer be
    read. `extra` may have been edited by hand into something that is not a JSON object (operations.md
    says how to edit it), and `json_set` raises on that, so such a value is kept whole under
    `extra_was` rather than refusing the one command that exists for a row nothing else can move."""
    with conn:
        done = conn.execute(
            """UPDATE attempts SET outcome = 'verified',
                      extra = CASE WHEN json_valid(COALESCE(extra, '{}')) AND json_type(COALESCE(extra, '{}')) = 'object'
                                   THEN json_set(COALESCE(extra, '{}'), '$.recheck', ?1, '$.released_at', ?2)
                                   ELSE json_object('recheck', ?1, 'released_at', ?2, 'extra_was', extra) END
               WHERE id = ?3 AND outcome = 'recheck_pending'""", (note, now(), attempt_id)).rowcount
    return done == 1


def pending_rechecks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM attempts WHERE outcome = 'recheck_pending' ORDER BY id").fetchall()


def pending_recheck(conn: sqlite3.Connection, a_number: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM attempts WHERE a_number = ? AND outcome = 'recheck_pending' ORDER BY id DESC LIMIT 1",
                        (a_number,)).fetchone()


def is_dead_end(conn: sqlite3.Connection, a_number: str, program_sha: str, known_terms: int,
                budgets: config.Budgets) -> sqlite3.Row | None:
    """A previous attempt that ran this exact program against the same number of known terms and
    failed deterministically; or verified, found no new term, and either judged the next term infeasible
    under an extension time at least as large as this one and an *effective* memory cap at least this
    budget, or used up an extension time at least as large as this one with at least
    EXTEND_DEAD_END_MIN_CPU_SHARE of its wall time on the CPU (memory never ends a run as
    `extend_budget`, so memory is not compared there; attempts recorded before the budgets were stored in
    `extra` never count for either); or ran at least `verify_wall_s` seconds without reproducing the known
    terms (`verify_timeout`, keyed on the measured runtime, so older attempts count too) with at least
    EXTEND_DEAD_END_MIN_CPU_SHARE of **this** verify budget on the CPU. That last condition is item 58's:
    the verify budget is wall time, so a machine that slept or was busy through a verification used to
    retire a program that never had its minute. It asks what the run got against the budget now planned,
    not what share of its own wall time it had: a run that took 600 s at half speed still had 300 s of
    CPU, which settles a 60 s budget and not a 600 s one. On 2026-11-22, 5 of the 163 such rows were
    under 0.8 of their own wall time, all in three starved spells; the rule frees 2 sequences at the
    60 s tiers and 2 others at the 600 s tiers. The 0.8 is inherited from the extension rule, not fitted:
    undisturbed runs are at 0.95 and over. A row without a CPU figure never counts.

    The infeasible clause compares the cap the earlier run was actually judged against
    (`extra.mem_cap_bytes`, the budget lowered to free RAM minus the reserve) with the budget the planned
    run asks for. A run
    squeezed by a busy machine is therefore not retired at that budget: it is re-run once the RAM is back.
    Comparing the cap against the *configured* budget keeps the answer independent of free RAM at the time
    of asking, so a session's picks stay reproducible."""
    # The infeasible clause asks only about the budget the verdict was reached on, where the row says
    # which (`extra.infeasible_on`, written since 2026-09-30, item 51: `time`, `memory` or `time+memory`).
    # A verdict reached on time alone holds under any memory cap, and one reached on memory alone under
    # any extension time; rows without the key -- every one before that date -- keep needing both, which
    # is the conservative reading (they re-run whenever either budget grew)
    return conn.execute(f"""
        SELECT id, failure_mode, detail, verified, new_terms FROM attempts
        WHERE a_number = ? AND program_sha = ? AND known_terms = ?
          AND (failure_mode IN ({','.join('?' * len(DETERMINISTIC_FAILURES))})
               OR (verified = 1 AND new_terms = 0 AND failure_mode = 'infeasible'
                   AND CASE json_extract(extra, '$.infeasible_on')
                         WHEN 'time' THEN json_extract(extra, '$.extend_wall_s') >= ?
                         WHEN 'memory' THEN json_extract(extra, '$.mem_cap_bytes') >= ?
                         ELSE json_extract(extra, '$.extend_wall_s') >= ? AND json_extract(extra, '$.mem_cap_bytes') >= ?
                       END)
               OR (verified = 1 AND new_terms = 0 AND failure_mode = 'extend_budget'
                   AND json_extract(extra, '$.extend_wall_s') >= ? AND cpu_s >= ? * runtime_s)
               OR (failure_mode = 'verify_timeout' AND runtime_s >= ? AND cpu_s >= ?))
        ORDER BY id DESC LIMIT 1""", (a_number, program_sha, known_terms, *DETERMINISTIC_FAILURES,
                                      budgets.extend_wall_s, budgets.mem_bytes,
                                      budgets.extend_wall_s, budgets.mem_bytes,
                                      budgets.extend_wall_s, EXTEND_DEAD_END_MIN_CPU_SHARE,
                                      budgets.verify_wall_s,
                                      EXTEND_DEAD_END_MIN_CPU_SHARE * budgets.verify_wall_s)).fetchone()


# ------------------------------------------------------------------ reviews

class ReviewRefused(ValueError):
    """A review was not opened because the sequence already has a `rejected` one. `prior_id` is that row."""

    def __init__(self, a_number: str, prior: sqlite3.Row):
        self.prior_id = int(prior["id"])
        when = (prior["updated_at"] or "")[:10]
        note = (prior["note"] or "no note").replace("\n", " ")
        super().__init__(f"{a_number} already has a rejected review (#{self.prior_id}, {when}): {note[:160]}"
                         f"{'...' if len(note) > 160 else ''} -- not opening another for the same sequence")


def rejected_review(conn: sqlite3.Connection, a_number: str) -> sqlite3.Row | None:
    """The most recent `rejected` review for this sequence, or None."""
    return conn.execute("SELECT * FROM reviews WHERE a_number = ? AND status = 'rejected' ORDER BY id DESC LIMIT 1",
                        (a_number,)).fetchone()


def _insert_review(conn: sqlite3.Connection, a_number: str, attempt_id: int, artifact_path: str,
                   first_new_index: int, last_new_index: int) -> int:
    """Insert a review row. Refuses (`ReviewRefused`) when the sequence already has a `rejected` review:
    a rejection records that a result of this shape is not submittable -- reviews #2 and #3 are
    conjectural programs whose every value is conjecture -- and a `rejected` row does not gate
    `attempt_sequence` (only open statuses do, deliberately: item 48), so without this a targeted
    `oeisbot attempt A... --model` could open review #4 for the same false win (item 49's audit, item 51).
    A result that is genuinely different from what was rejected needs a human to reopen the question,
    by changing the old row's status, not the pipeline to guess."""
    if (prior := rejected_review(conn, a_number)) is not None:
        raise ReviewRefused(a_number, prior)
    t = now()
    return conn.execute("""
        INSERT INTO reviews(a_number, attempt_id, artifact_path, first_new_index, last_new_index, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""", (a_number, attempt_id, artifact_path, first_new_index, last_new_index, t, t)).lastrowid


def add_review(conn: sqlite3.Connection, a_number: str, attempt_id: int, artifact_path: str,
               first_new_index: int, last_new_index: int) -> int:
    with conn:
        return _insert_review(conn, a_number, attempt_id, artifact_path, first_new_index, last_new_index)


def review_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every review with what identifies it to a reader: the entry's name, the addition (`new_terms`,
    `first_new_index`..`last_new_index`), and the run that produced it (`program_origin`, `strategy`,
    `runtime_s`, `attempt_id`). Newest first. The CLI's `review list` and the dashboard's inbox both
    show these same facts, in the same order (item 51)."""
    return conn.execute("""
        SELECT r.*, s.name, a.strategy, a.program_origin, a.new_terms, a.runtime_s
        FROM reviews r JOIN attempts a ON a.id = r.attempt_id LEFT JOIN sequences s ON s.a_number = r.a_number
        ORDER BY r.id DESC""").fetchall()


def open_review(conn: sqlite3.Connection, a_number: str) -> sqlite3.Row | None:
    return conn.execute(f"""
        SELECT * FROM reviews WHERE a_number = ? AND status IN ({','.join('?' * len(OPEN_REVIEW_STATUSES))})
        ORDER BY id DESC LIMIT 1""", (a_number, *OPEN_REVIEW_STATUSES)).fetchone()


def set_review_status(conn: sqlite3.Connection, review_id: int, status: str, note: str | None = None) -> None:
    row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if row is None:
        raise KeyError(f"no review {review_id}")
    if status == "submitted":
        other = conn.execute("SELECT id FROM reviews WHERE a_number = ? AND status = 'submitted' AND id != ?",
                             (row["a_number"], review_id)).fetchone()
        if other:
            raise ValueError(f"{row['a_number']} already has a submitted review (#{other['id']}); not marking twice")
    with conn:
        conn.execute("UPDATE reviews SET status = ?, note = COALESCE(?, note), updated_at = ? WHERE id = ?",
                     (status, note, now(), review_id))


# ------------------------------------------------------------------ sequences

@dataclass
class SequenceRow:
    a_number: str
    name: str
    offset: int
    keywords: str
    data_terms: int
    data_last_digits: int | None
    program_langs: str
    more_credits: int
    value_dependent: bool
    difficulty: float | None = None


def upsert_sequences(conn: sqlite3.Connection, rows: list[SequenceRow]) -> None:
    t = now()
    with conn:
        conn.executemany("""
            INSERT INTO sequences(a_number, name, offset, keywords, data_terms, data_last_digits, program_langs,
                more_credits, value_dependent, difficulty, in_more, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(a_number) DO UPDATE SET
                name = excluded.name, offset = excluded.offset, keywords = excluded.keywords,
                data_terms = excluded.data_terms, data_last_digits = excluded.data_last_digits,
                program_langs = excluded.program_langs, more_credits = excluded.more_credits,
                value_dependent = excluded.value_dependent, difficulty = excluded.difficulty,
                in_more = 1, synced_at = excluded.synced_at""",
            [(r.a_number, r.name, r.offset, r.keywords, r.data_terms, r.data_last_digits, r.program_langs,
              r.more_credits, int(r.value_dependent), r.difficulty, t) for r in rows])


def mark_not_in_more(conn: sqlite3.Connection, still_more: set[str]) -> int:
    rows = conn.execute("SELECT a_number FROM sequences WHERE in_more = 1").fetchall()
    gone = [(r["a_number"],) for r in rows if r["a_number"] not in still_more]
    with conn:
        conn.executemany("UPDATE sequences SET in_more = 0 WHERE a_number = ?", gone)
    return len(gone)


def update_bfile_info(conn: sqlite3.Connection, a_number: str, status: str, terms: int | None = None,
                      last_index: int | None = None, last_digits: int | None = None) -> None:
    with conn:
        conn.execute("""UPDATE sequences SET bfile_status = ?, bfile_terms = ?, bfile_last_index = ?,
                        bfile_last_digits = ? WHERE a_number = ?""", (status, terms, last_index, last_digits, a_number))


def set_difficulty(conn: sqlite3.Connection, a_number: str, difficulty: float) -> None:
    with conn:
        conn.execute("UPDATE sequences SET difficulty = ? WHERE a_number = ?", (difficulty, a_number))


def refresh_difficulty(conn: sqlite3.Connection, score) -> int:
    """Recompute `sequences.difficulty` from the stored rows, in one transaction.

    `score` is `select.difficulty` (passed in: select imports db, not the other way round). A stored row
    carries the `bfile_*` columns that a `SequenceRow` does not, so this is the only way the column can
    hold what selection actually computes -- `sync` builds its rows from the entry alone and would
    otherwise discard whatever `fetch-bfiles` folded in. Every row is rescored, `in_more = 0` ones
    included, so the column means the same thing for the whole table. Returns the number of rows written."""
    rows = conn.execute("SELECT * FROM sequences").fetchall()
    updates = [(score(row), row["a_number"]) for row in rows]
    with conn:
        conn.executemany("UPDATE sequences SET difficulty = ? WHERE a_number = ?", updates)
    return len(updates)


# ------------------------------------------------------------------ pick-chance snapshots

def pick_digest(pairs) -> str:
    """A hash of (a_number, difficulty) pairs, whatever their order: what makes two snapshots, or a snapshot
    and the live pool, the same pool. It hashes the float's `repr`, so a change in the last bit counts."""
    ordered = sorted((str(a), float(d)) for a, d in pairs)
    return hashlib.sha256("\n".join(f"{a}\t{d!r}" for a, d in ordered).encode()).hexdigest()


POOLS = ("pari", "model")


def record_pick_snapshot(conn: sqlite3.Connection, pool: str, rows, *, session_id: int | None = None,
                         keep: int | None = None, budgets: str | None = None, rules: str | None = None) -> int | None:
    """Store `rows` -- (a_number, effective difficulty) pairs -- as the newest snapshot of `pool`, and
    prune that pool to its `keep` newest (default `config.PICK_SNAPSHOTS_KEPT[pool]`). Returns the new
    snapshot's id, or None when the newest one already holds exactly these rows (a session that changed
    nothing adds nothing, but its `budgets` and `rules` replace the newest snapshot's: they are those of the
    newest session that drew this very pool, and an edit that provably changed nothing must not leave the
    snapshot stamped with rules that "changed"). The comparison, the inserts and the pruning are one
    transaction that takes the write lock first (`BEGIN IMMEDIATE`), so two writers cannot both decide the
    pool is new, and a crash leaves either the old state or the new one, never a header without rows. It
    commits on its own, so a connection already inside a transaction is refused rather than having its
    pending writes committed or rolled back with the snapshot's. `keep` below 1 would delete the snapshot
    just written, so it is refused. `budgets` and `rules` describe what built the pool."""
    if pool not in POOLS:
        raise ValueError(f"unknown pool {pool!r}; expected one of {POOLS}")
    keep = config.PICK_SNAPSHOTS_KEPT[pool] if keep is None else keep
    if keep < 1:
        raise ValueError(f"keep must be at least 1, got {keep}")
    if conn.in_transaction:
        raise RuntimeError("record_pick_snapshot commits on its own and cannot run inside a transaction")
    pairs = sorted((str(a), float(d)) for a, d in rows)
    digest = pick_digest(pairs)
    conn.execute("BEGIN IMMEDIATE")
    with conn:
        newest = conn.execute("SELECT id, digest FROM pick_snapshots WHERE pool = ? ORDER BY id DESC LIMIT 1",
                              (pool,)).fetchone()
        if newest is not None and newest["digest"] == digest:
            conn.execute("UPDATE pick_snapshots SET budgets = COALESCE(?, budgets), rules = COALESCE(?, rules) "
                         "WHERE id = ?", (budgets, rules, newest["id"]))
            return None
        sid = conn.execute("INSERT INTO pick_snapshots(pool, taken_at, session_id, n, digest, budgets, rules) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (pool, now(), session_id, len(pairs), digest, budgets, rules)).lastrowid
        conn.executemany("INSERT INTO pick_snapshot_rows(snapshot_id, a_number, difficulty) VALUES (?, ?, ?)",
                         [(sid, a, d) for a, d in pairs])
        conn.execute("DELETE FROM pick_snapshots WHERE pool = ? AND id NOT IN "
                     "(SELECT id FROM pick_snapshots WHERE pool = ? ORDER BY id DESC LIMIT ?)", (pool, pool, keep))
    return sid


def has_pick_snapshots(conn: sqlite3.Connection) -> bool:
    """Whether the snapshot tables exist. A read-only connection cannot create them, and a database nothing
    has written to since they were added does not have them yet."""
    return conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name IN "
                        "('pick_snapshots', 'pick_snapshot_rows')").fetchone()[0] == 2


def pick_snapshot_headers(conn: sqlite3.Connection, pool: str) -> list[sqlite3.Row]:
    """The snapshots of `pool`, newest first, without their rows."""
    return conn.execute("SELECT id, taken_at, session_id, n, digest, budgets, rules FROM pick_snapshots "
                        "WHERE pool = ? ORDER BY id DESC", (pool,)).fetchall()


def pick_snapshot_difficulties(conn: sqlite3.Connection, snapshot_id: int) -> dict[str, float]:
    return {r["a_number"]: r["difficulty"] for r in conn.execute(
        "SELECT a_number, difficulty FROM pick_snapshot_rows WHERE snapshot_id = ?", (snapshot_id,))}
