"""Attempts database (build step 4). SQLite in WAL mode: the harness writes, the dashboard only reads.

One row per attempt; one row per projected term (predicted vs actual cost) so the estimator can be
checked; review rows track what a human has done with each success so nothing is submitted twice.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import config

SCHEMA_VERSION = 1

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
    censored_s       REAL                      -- still running when stopped: at least this long
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
"""

OPEN_REVIEW_STATUSES = ("new", "reviewing", "submitted")
# failures that will repeat identically if the same program is run again on the same known terms
DETERMINISTIC_FAILURES = ("wrong_term", "bad_index", "protocol", "crash", "incomplete")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path = config.DB_PATH, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    else:
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
                predicted_mem, model, trustworthy, feasible, value_dependent, actual_s, actual_mem, censored_s)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", [
            (attempt_id, p.n, p.unit, p.seconds, p.seconds_low, p.seconds_high, p.mem_high, p.model,
             int(p.trustworthy), int(p.feasible), int(p.value_dependent), p.actual_s, p.actual_mem, p.censored_s)
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


def set_recheck_result(conn: sqlite3.Connection, attempt_id: int, note: str, outcome: str | None = None) -> None:
    """Store the re-check note in attempts.extra, and change the outcome if given."""
    with conn:
        conn.execute(_SET_RECHECK, (outcome, None, note, attempt_id))


def record_win(conn: sqlite3.Connection, attempt_id: int, a_number: str, artifact_path: str,
               first_new_index: int, last_new_index: int, recheck_note: str) -> int:
    """After a successful re-check: mark the attempt `extended` with its artifact and queue a review, in one
    transaction. Returns the review id."""
    with conn:
        conn.execute(_SET_RECHECK, ("extended", artifact_path, recheck_note, attempt_id))
        return _insert_review(conn, a_number, attempt_id, artifact_path, first_new_index, last_new_index)


def pending_rechecks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM attempts WHERE outcome = 'recheck_pending' ORDER BY id").fetchall()


def pending_recheck(conn: sqlite3.Connection, a_number: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM attempts WHERE a_number = ? AND outcome = 'recheck_pending' ORDER BY id DESC LIMIT 1",
                        (a_number,)).fetchone()


def is_dead_end(conn: sqlite3.Connection, a_number: str, program_sha: str, known_terms: int,
                budgets: config.Budgets) -> sqlite3.Row | None:
    """A previous attempt that ran this exact program against the same number of known terms and
    failed deterministically, or verified but judged the next term infeasible under an extension time
    and memory budget at least as large as these. (Attempts recorded before the budgets were stored in
    `extra` never count as infeasible dead ends.)"""
    return conn.execute(f"""
        SELECT id, failure_mode, detail FROM attempts
        WHERE a_number = ? AND program_sha = ? AND known_terms = ?
          AND (failure_mode IN ({','.join('?' * len(DETERMINISTIC_FAILURES))})
               OR (verified = 1 AND new_terms = 0 AND failure_mode = 'infeasible'
                   AND json_extract(extra, '$.extend_wall_s') >= ? AND json_extract(extra, '$.mem_bytes') >= ?))
        ORDER BY id DESC LIMIT 1""", (a_number, program_sha, known_terms, *DETERMINISTIC_FAILURES,
                                      budgets.extend_wall_s, budgets.mem_bytes)).fetchone()


# ------------------------------------------------------------------ reviews

def _insert_review(conn: sqlite3.Connection, a_number: str, attempt_id: int, artifact_path: str,
                   first_new_index: int, last_new_index: int) -> int:
    t = now()
    return conn.execute("""
        INSERT INTO reviews(a_number, attempt_id, artifact_path, first_new_index, last_new_index, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""", (a_number, attempt_id, artifact_path, first_new_index, last_new_index, t, t)).lastrowid


def add_review(conn: sqlite3.Connection, a_number: str, attempt_id: int, artifact_path: str,
               first_new_index: int, last_new_index: int) -> int:
    with conn:
        return _insert_review(conn, a_number, attempt_id, artifact_path, first_new_index, last_new_index)


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
