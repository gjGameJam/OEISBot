"""Dashboard API (build step 8). Read-only over the SQLite database: every request opens a
mode=ro connection, and nothing here writes. Review status changes go through the CLI
(`oeisbot review set ...`) so the harness remains the only writer.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import statistics
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .. import config, db, pickmap, select

_log = logging.getLogger("oeisbot.dashboard")
STATIC = Path(__file__).parent / "static"
TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json", ".gp", ".py"}
SQLITE_MAX_INT = 2 ** 63 - 1

app = FastAPI(title="OEISBot dashboard", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

# The names a request may address this server by. The server has no authentication and binds to loopback, but a
# page on another site can still reach it from the user's own browser by pointing a host name it controls at
# 127.0.0.1 (DNS rebinding); such a request carries that name in `Host`, so it is refused here. Read on every
# request, so `oeisbot dashboard --host` (cli.cmd_dashboard) and the tests can change it; None turns the check
# off, which is what a wildcard bind does, with a printed warning. Starlette's own TrustedHostMiddleware is not
# used: it cuts `[::1]:8765` at the first colon, compares case-sensitively, and is fixed at the first request.
ALLOWED_HOSTS: set[str] | None = {"127.0.0.1", "localhost", "::1"}


_HOST = re.compile(r"(?:\[([0-9a-f:.]+)\]|([^:\[\]@/\s]+))(?::\d*)?")


def host_name(header: str) -> str:
    """The host of a `Host` header, lower-cased, without its port and without an IPv6 literal's brackets; ""
    for anything that is not a host and an optional numeric port and nothing else, so that `[::1]evil.example`
    or `127.0.0.1:x` names no host at all."""
    m = _HOST.fullmatch(header.strip().lower())
    return (m.group(1) or m.group(2)) if m else ""


@app.middleware("http")
async def guard(request: Request, call_next):
    """Refuse a request addressed to a name that is not this server's (see ALLOWED_HOSTS), refuse an API
    request that a browser says some other page made, and tell the browser never to guess a content type,
    since the file route serves text that programs wrote.

    "Some other page" is any `Sec-Fetch-Site` but `same-origin` (the dashboard's own page, the Vite dev server's
    proxied one included) and `none` (an address typed in, a bookmark): an `<img>` on any site, or on another
    port of this machine (`same-site`), could otherwise make this process build a pool or serialize the whole
    queue. A client that is not a browser sends no such header and is not affected."""
    allowed = ALLOWED_HOSTS
    if allowed is not None and host_name(request.headers.get("host", "")) not in allowed:
        response = JSONResponse({"detail": "this server does not answer to that host name"}, status_code=400)
    elif (request.url.path.lower().startswith("/api")
          and request.headers.get("sec-fetch-site", "same-origin").strip().lower() not in ("same-origin", "none")):
        response = JSONResponse({"detail": "requests from other pages are refused"}, status_code=403)
    else:
        response = await call_next(request)
    response.headers[NOSNIFF[0]] = NOSNIFF[1]
    return response


NOSNIFF = ("X-Content-Type-Options", "nosniff")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """An endpoint that raised: the plain 500 Starlette would send, with the header every other response has
    (the middleware above never sees this response; an exception passes through it). Starlette still logs the
    traceback and re-raises, so a test client configured to raise still raises."""
    return PlainTextResponse("Internal Server Error", status_code=500, headers={NOSNIFF[0]: NOSNIFF[1]})


# A win, for every number the dashboard shows: a run recorded `extended` whose review was not rejected and
# was not refused. `extended` alone is not enough. Reviews #2 and #3 (A162762, A162764) were rejected as
# conjectural, their attempts stay `extended` because the terms and artifact are kept, and a later run of such
# a sequence is `extended` with no review row at all and `extra.review_refused` set (db.record_win). `a` is the
# attempts row.
# CASE, not AND: SQLite does not promise to skip json_extract when json_valid is false, and it raises on text
# that is not JSON, which would take every endpoint that counts wins down with one bad row.
REJECTED_WIN = ("(a.outcome = 'extended' AND ((CASE WHEN json_valid(a.extra) THEN json_extract(a.extra, '$.review_refused') END) "
                "IS NOT NULL OR EXISTS (SELECT 1 FROM reviews r WHERE r.attempt_id = a.id AND r.status = 'rejected')))")
WIN = f"(a.outcome = 'extended' AND NOT {REJECTED_WIN})"


def short_name(name: str | None, limit: int = 90) -> str:
    """A sequence name cut to about `limit` characters for the Pick map, at a word boundary where there is one
    and always with an ellipsis when anything was dropped, so that a cut name never reads as a whole one."""
    name = name or ""
    if len(name) <= limit:
        return name
    cut = name[:limit]
    space = cut.rfind(" ")
    if space >= limit * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,;:([{") + "…"


def ro():
    if not config.DB_PATH.exists():
        raise HTTPException(503, f"no database at {config.DB_PATH}; run `oeisbot setup` and `oeisbot sync`")
    return db.connect(config.DB_PATH, readonly=True)


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


@app.get("/api/summary")
def summary():
    conn = ro()
    try:
        one = lambda q, *a: conn.execute(q, a).fetchone()[0]
        return {
            "candidates": one("SELECT COUNT(*) FROM sequences WHERE in_more = 1"),
            "attempts": one("SELECT COUNT(*) FROM attempts WHERE outcome != 'skipped'"),
            "skipped": one("SELECT COUNT(*) FROM attempts WHERE outcome = 'skipped'"),
            "wins": one(f"SELECT COUNT(*) FROM attempts a WHERE {WIN}"),
            "rejected_wins": one(f"SELECT COUNT(*) FROM attempts a WHERE {REJECTED_WIN}"),
            "new_terms": one(f"SELECT COALESCE(SUM(a.new_terms), 0) FROM attempts a WHERE {WIN}"),
            "open_reviews": one("SELECT COUNT(*) FROM reviews WHERE status IN ('new', 'reviewing')"),
            "machine_hours": one("SELECT COALESCE(SUM(runtime_s), 0) FROM attempts") / 3600,
            "oeisdata_commit": db.get_meta(conn, "oeisdata_commit"),
            "synced_at": db.get_meta(conn, "synced_at"),
        }
    finally:
        conn.close()


@app.get("/api/estimator")
def estimator():
    """Predicted vs actual cost of every projected term. Censored points ran out of time before
    finishing: their actual cost is at least censored_s."""
    conn = ro()
    try:
        points = rows(conn.execute("""
            SELECT p.id, p.attempt_id, a.a_number, a.strategy, p.n, p.cost_unit, p.model, p.trustworthy,
                   p.feasible, p.value_dependent, p.predicted_s, p.predicted_s_low, p.predicted_s_high,
                   p.actual_s, p.censored_s, a.started_at
            FROM predictions p JOIN attempts a ON a.id = p.attempt_id
            WHERE p.predicted_s IS NOT NULL AND p.predicted_s > 0
              AND (p.actual_s IS NOT NULL OR p.censored_s IS NOT NULL)
            ORDER BY p.id"""))
    finally:
        conn.close()
    # A term is finished when it has a positive time; a zero is not a measurement. Each point says which it
    # is, so that the page does not decide for itself (it used to draw a zero as finished).
    for p in points:
        p["finished"] = bool(p["actual_s"] and p["actual_s"] > 0)
    finished = [p for p in points if p["finished"]]
    ratios = [p["actual_s"] / p["predicted_s"] for p in finished]
    in_range = [p for p in finished if p["predicted_s_low"] is not None and p["predicted_s_high"] is not None
                and p["predicted_s_low"] * 0.5 <= p["actual_s"] <= p["predicted_s_high"] * 2]
    return {
        "points": points,
        "stats": {
            "finished": len(finished),
            "censored": len(points) - len(finished),
            "within_2x": sum(1 for r in ratios if 0.5 <= r <= 2) / len(ratios) if ratios else None,
            "median_ratio": statistics.median(ratios) if ratios else None,
            "mean_abs_log10_error": statistics.fmean(abs(math.log10(r)) for r in ratios) if ratios else None,
            "in_reported_range_2x": len(in_range) / len(finished) if finished else None,
            "underestimated_censored": sum(1 for p in points if not p["actual_s"] and p["censored_s"]
                                           and p["censored_s"] > 2 * (p["predicted_s_high"] or p["predicted_s"])),
        },
    }


@app.get("/api/queue")
def queue(alpha: float = Query(1.0, ge=0, le=pickmap.MAX_ALPHA), pari_only: bool = True,
          limit: int = Query(500, ge=0, le=30000),
          sort: str = Query("weight", pattern="^(weight|difficulty|a_number)$")):
    conn = ro()
    try:
        pool = select.candidates(conn, alpha=alpha, require_langs={"pari"} if pari_only else None)
        extra = {r["a_number"]: r for r in rows(conn.execute(
            "SELECT a_number, keywords, bfile_status, bfile_terms, data_terms, more_credits, value_dependent FROM sequences"))}
    finally:
        conn.close()
    total = sum(c.weight for c in pool) or 1.0
    key = {"weight": lambda c: -c.weight, "difficulty": lambda c: c.difficulty, "a_number": lambda c: c.a_number}[sort]
    out = []
    for c in sorted(pool, key=key)[:limit]:
        e = extra.get(c.a_number, {})
        out.append({"a_number": c.a_number, "name": c.name, "difficulty": c.difficulty, "weight": c.weight,
                    "pick_probability": c.weight / total, "program_langs": c.program_langs,
                    "keywords": e.get("keywords"), "bfile_status": e.get("bfile_status"),
                    "known_terms": e.get("bfile_terms") or e.get("data_terms"),
                    "more_credits": e.get("more_credits"), "value_dependent": bool(e.get("value_dependent"))})
    return {"total": len(pool), "alpha": alpha, "rows": out}


# The Pick map's live pool is the one a session draws from (attempt.session_pool), which costs several
# seconds to build. It is built on demand, never on a timer, and kept while nothing it was built from has
# changed: the stamp is the database file's and WAL's (mtime, size) -- any commit moves one of them, including
# a `sync` or a rescore that no table-level count would notice -- and the budgets it was built under must be
# the ones asked for. POOL_TTL_S is only a backstop for what the stamp cannot see. The lock means two requests
# that arrive together (a page load and its Refresh) wait for one build instead of making two, and a request
# accepts a build that finished after it asked even if the database has moved since. A lookup that finds a
# servable entry does not take the lock, so it never waits behind another pool's build. One entry per pool:
# alpha is applied afterwards.
POOL_TTL_S = 3600.0
RUNNING_SESSION_MAX_AGE = timedelta(hours=24)       # an unfinished session older than this crashed


class _Live(NamedTuple):
    stamp: tuple                                    # _db_stamp() just before the build read the database
    budgets: str                                    # budgets_json of what it was built under
    built: float                                    # time.monotonic()
    built_at: str
    rows: list[tuple[str, str, float]]              # (a_number, name, difficulty)
    note: str
    generation: int                                 # which build this was, counting every pool's builds


_live: dict[str, _Live] = {}
_live_lock = threading.Lock()
_generation = 0     # builds finished so far: a request that asked at generation g accepts any build numbered above g


def _db_stamp() -> tuple:
    stamp = [str(config.DB_PATH)]
    for suffix in ("", "-wal"):
        try:
            st = os.stat(str(config.DB_PATH) + suffix)
            stamp.append((st.st_mtime_ns, st.st_size))
        except OSError:
            stamp.append(None)
    return tuple(stamp)


def live_pool(pool: str, budgets, refresh: bool = False) -> _Live:
    global _generation
    from ..attempt import budgets_json, session_pool
    asked = _generation
    now = time.monotonic()
    wanted = budgets_json(budgets)

    def servable(hit: _Live | None, stamp: tuple) -> bool:
        # built under these budgets, and either finished after this request asked (another request built it
        # while this one waited for the lock: while a session is running the database moves all the time, so
        # the stamp alone would send every waiter to build again; a counter, not a clock, because Windows'
        # monotonic clock ticks every 16 ms and a build and the next request can read the same tick) or
        # unchanged and recent
        return bool(hit) and hit.budgets == wanted and (
            hit.generation > asked or (not refresh and hit.stamp == stamp and now - hit.built < POOL_TTL_S))

    hit = _live.get(pool)
    if not refresh and servable(hit, _db_stamp()):                      # a lookup never waits behind a build
        return hit
    with _live_lock:
        stamp = _db_stamp()
        hit = _live.get(pool)
        if servable(hit, stamp):
            return hit
        conn = ro()
        try:
            cands, keep = session_pool(conn, budgets, model=pool == "model")
        finally:
            conn.close()
        _generation += 1
        _live[pool] = hit = _Live(stamp, wanted, time.monotonic(), db.now(),
                                  [(c.a_number, c.name, c.difficulty) for c in cands], keep.summary(), _generation)
        return hit


_rules: str | None = None


def rules_loaded() -> str:
    """The rules fingerprint of the code this process has loaded, taken once. The live pool is built by that
    code, so it is the one to compare a snapshot's with: re-reading the files per request would report "the
    rules changed" the moment someone edited a file the running server had not reloaded."""
    global _rules
    if _rules is None:
        from ..attempt import rules_fingerprint
        _rules = rules_fingerprint()
    return _rules


def warm_live_pool(pool: str = "pari") -> _Live:
    """Build `pool`'s live pool under the budgets the Pick map will ask for, so that the first visit finds it."""
    from ..attempt import budgets_of
    rules_loaded()
    conn = ro()
    try:
        headers = db.pick_snapshot_headers(conn, pool) if db.has_pick_snapshots(conn) else []
    finally:
        conn.close()
    return live_pool(pool, budgets_of(headers[0] if headers else None))


def _chunks(items: list, n: int = 500):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _departures(conn, gone: list[tuple[str, float]], since: str, *, rules_changed: bool,
                budgets_changed: bool) -> dict[str, str]:
    """Why each sequence in `gone` is no longer in the pool (pickmap.departure_reason), from what the
    database recorded at or after `since`."""
    attempt: dict[str, tuple[str, str | None]] = {}
    review: dict[str, str] = {}
    in_more: dict[str, bool] = {}
    names = [a for a, _ in gone]
    open_statuses = db.OPEN_REVIEW_STATUSES
    for chunk in _chunks(names):
        marks = ",".join("?" * len(chunk))
        for r in conn.execute(f"SELECT a_number, outcome, failure_mode FROM attempts WHERE a_number IN ({marks}) "
                              f"AND started_at >= ? ORDER BY id", [*chunk, since]):
            attempt[r["a_number"]] = (r["outcome"], r["failure_mode"])
        for r in conn.execute(f"SELECT a_number, status FROM reviews WHERE a_number IN ({marks}) "
                              f"AND status IN ({','.join('?' * len(open_statuses))}) ORDER BY id",
                              [*chunk, *open_statuses]):
            review[r["a_number"]] = r["status"]
        for r in conn.execute(f"SELECT a_number, in_more FROM sequences WHERE a_number IN ({marks})", chunk):
            in_more[r["a_number"]] = bool(r["in_more"])
    return {a: pickmap.departure_reason(attempt=attempt.get(a), review=review.get(a),
                                        in_more=in_more.get(a), rules_changed=rules_changed,
                                        budgets_changed=budgets_changed) for a in names}


@app.get("/api/pickmap")
def pickmap_data(pool: str = Query("pari", pattern="^(pari|model)$"),
                 alpha: float = Query(1.0, ge=0, le=pickmap.MAX_ALPHA), refresh: bool = False):
    """Every candidate of a session's pool with its pick chance, and the change since the newest snapshot
    that differs from the live pool (pickmap.baseline). The live pool is built under the budgets of the
    pool's newest snapshot (the defaults when there is none), so what differs from the baseline is what
    happened and not a change of budget. `refresh` rebuilds it now. Read-only, and costs a pool build
    (several seconds) when the database has changed since the last one. A pool that cannot be built is a 503
    with a JSON body naming the reason (`pool_build_failed`), the traceback going to the log; nothing is cached
    for it, so the next request tries again."""
    from ..attempt import budgets_json, budgets_of
    conn = ro()
    try:
        have = db.has_pick_snapshots(conn)
        headers = db.pick_snapshot_headers(conn, pool) if have else []
        newest = conn.execute("SELECT id, started_at, finished_at FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    # only the newest session can be running: an unfinished older one was killed before it could finish
    cutoff = (datetime.now(timezone.utc) - RUNNING_SESSION_MAX_AGE).isoformat(timespec="seconds")
    running = newest if newest and newest["finished_at"] is None and newest["started_at"] >= cutoff else None
    budgets = budgets_of(headers[0] if headers else None)
    try:
        built = live_pool(pool, budgets, refresh)
    except HTTPException:       # no database: FastAPI's own 503, whose body names the file
        raise
    except Exception as e:      # noqa: BLE001 -- anything the pool build raised; the rest of this function is not guarded
        _log.exception("the %s pool could not be built for the Pick map", pool)
        reason = " ".join(f"{type(e).__name__}: {e}".split())[:200]
        return JSONResponse({"error": "pool_build_failed", "reason": reason}, status_code=503)
    live = {a: d for a, _, d in built.rows}
    names = {a: n for a, n, _ in built.rows}
    base_header = pickmap.baseline(headers, db.pick_digest(live.items()))
    conn = ro()
    try:
        base = db.pick_snapshot_difficulties(conn, base_header["id"]) if base_header else None
        cmp = pickmap.compare(live, base, alpha)
        budgets_differ = bool(base_header) and base_header["budgets"] is not None \
            and base_header["budgets"] != budgets_json(budgets)
        taken, loaded = (base_header["rules"] if base_header else None), rules_loaded()
        rules_differ = None if taken in (None, "unknown") or loaded == "unknown" else taken != loaded   # None: cannot tell
        why = _departures(conn, cmp["gone"], base_header["taken_at"], rules_changed=bool(rules_differ),
                          budgets_changed=budgets_differ) if base_header else {}
        top = cmp["gone"][:10]
        gone_names = {r["a_number"]: r["name"] for r in conn.execute(
            f"SELECT a_number, name FROM sequences WHERE a_number IN ({','.join('?' * len(top))})", [a for a, _ in top])}
    finally:
        conn.close()
    reasons: dict[str, list] = {}
    for a, p0 in cmp["gone"]:
        entry = reasons.setdefault(why[a], [0, 0.0])
        entry[0] += 1
        entry[1] += p0
    out = sorted(cmp["rows"], key=lambda r: -r["p"])
    for r in out:
        r["name"] = short_name(names[r["a"]])
    return {"pool": pool, "alpha": alpha, "n": len(out), "bands": pickmap.band_summary(out),
            "built_at": built.built_at, "age_s": time.monotonic() - built.built, "note": built.note,
            "running_session": {"id": running["id"], "started_at": running["started_at"]} if running else None,
            "snapshots": len(headers),
            "baseline": {**{k: base_header[k] for k in ("id", "taken_at", "n", "session_id")},
                         "budgets_differ": budgets_differ, "rules_differ": rules_differ} if base_header else None,
            "entered": cmp["entered"],
            "gone": {"n": len(cmp["gone"]), "share": sum(p0 for _, p0 in cmp["gone"]),
                     "reasons": [{"reason": k, "n": n, "share": s} for k, (n, s) in
                                 sorted(reasons.items(), key=lambda kv: -kv[1][1])],
                     "top": [{"a": a, "p0": p0, "name": short_name(gone_names.get(a)), "reason": why[a]}
                             for a, p0 in top]},
            "rows": out}


@app.get("/api/attempts")
def attempts(failure_mode: str | None = None, outcome: str | None = None, strategy: str | None = None,
             limit: int = Query(300, ge=0, le=5000)):
    """The newest `limit` attempts that match, with `total`, how many match in all, so that the page can say
    when it shows only some. A run with no stop reason is counted and filtered under `none` (a NULL key would
    reach the page as the string "null", which then filters on nothing). `win_rejected` marks an `extended`
    row that is not a win (REJECTED_WIN)."""
    conn = ro()
    try:
        where, params = [], []
        for col, val in (("failure_mode", failure_mode), ("outcome", outcome), ("strategy", strategy)):
            if col == "failure_mode" and val == "none":
                where.append("a.failure_mode IS NULL")
            elif val:
                where.append(f"a.{col} = ?")
                params.append(val)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        data = rows(conn.execute(f"""
            SELECT a.id, a.session_id, a.a_number, a.strategy, a.program_origin, a.started_at, a.verified, a.known_terms,
                   a.known_source, a.reproduced, a.new_terms, a.runtime_s, a.cpu_s, a.peak_mem_bytes, a.cost_unit,
                   a.projected_next_s_high, a.outcome, a.failure_mode, a.detail, a.artifact_path,
                   {REJECTED_WIN} AS win_rejected
            FROM attempts a {clause} ORDER BY a.id DESC LIMIT ?""", (*params, limit)))
        total = conn.execute(f"SELECT COUNT(*) FROM attempts a {clause}", params).fetchone()[0]
        failure_counts = dict(conn.execute(
            "SELECT COALESCE(failure_mode, 'none'), COUNT(*) FROM attempts WHERE outcome != 'skipped' GROUP BY 1").fetchall())
        skip_counts = dict(conn.execute(
            "SELECT COALESCE(failure_mode, 'none'), COUNT(*) FROM attempts WHERE outcome = 'skipped' GROUP BY 1").fetchall())
        outcome_counts = dict(conn.execute("SELECT outcome, COUNT(*) FROM attempts GROUP BY outcome").fetchall())
        strategies = [r[0] for r in conn.execute("SELECT DISTINCT strategy FROM attempts ORDER BY strategy")]
    finally:
        conn.close()
    for r in data:
        r["win_rejected"] = bool(r["win_rejected"])
    return {"rows": data, "total": total, "failure_counts": failure_counts, "skip_counts": skip_counts,
            "outcome_counts": outcome_counts, "strategies": strategies}


def _artifact_dir(path: str | None) -> Path | None:
    if not path:
        return None
    p = Path(path)
    p = (p if p.is_absolute() else config.ROOT / p).resolve()
    root = config.ARTIFACTS.resolve()
    if not p.is_relative_to(root) or not p.is_dir():
        return None
    return p


@app.get("/api/reviews")
def reviews():
    conn = ro()
    try:
        data = rows(conn.execute("""
            SELECT r.id, r.a_number, r.attempt_id, r.artifact_path, r.first_new_index, r.last_new_index, r.status,
                   r.note, r.created_at, r.updated_at, a.strategy, a.program_origin, a.new_terms, a.runtime_s,
                   a.known_terms, a.known_source, a.extra, s.name
            FROM reviews r JOIN attempts a ON a.id = r.attempt_id LEFT JOIN sequences s ON s.a_number = r.a_number
            ORDER BY CASE r.status WHEN 'new' THEN 0 WHEN 'reviewing' THEN 1 ELSE 2 END, r.id DESC"""))
    finally:
        conn.close()
    for r in data:
        folder = _artifact_dir(r["artifact_path"])
        r["files"] = sorted(f.name for f in folder.iterdir() if f.suffix in TEXT_SUFFIXES) if folder else []
        extra = json.loads(r.pop("extra") or "{}")
        r["weak_verification"] = bool(extra.get("weak_verification"))
        r["rewrites"] = extra.get("rewrites") or []
        r["below_bound"] = extra.get("below_published_bound")      # {"bound", "quote", "indices"} or None
    return {"rows": data}


@app.get("/api/reviews/{review_id}/files/{name}", response_class=PlainTextResponse)
def review_file(name: str, review_id: int = PathParam(ge=1, le=SQLITE_MAX_INT)):
    conn = ro()
    try:
        row = conn.execute("SELECT artifact_path FROM reviews WHERE id = ?", (review_id,)).fetchone()
    finally:
        conn.close()
    folder = _artifact_dir(row["artifact_path"]) if row else None
    if folder is None:
        raise HTTPException(404, "artifact folder not found")
    allowed = {f.name: f for f in folder.iterdir() if f.is_file() and f.suffix in TEXT_SUFFIXES}
    if name not in allowed:
        raise HTTPException(404, "no such file")
    return allowed[name].read_text(encoding="utf-8", errors="replace")


@app.get("/api/history")
def history(session_limit: int = Query(100, ge=0, le=5000)):
    """Runs per UTC day (`started_at` is stored in UTC and the day is its first ten characters) and the newest
    sessions. Wins are counted by WIN, per day and per session: a session's `wins` here is counted from its
    attempts and not read from `sessions.wins`, which was written when the session ended and still counts
    wins whose review was rejected afterwards. `rejected_wins` is the other half of `extended`."""
    conn = ro()
    try:
        attempts_rows = rows(conn.execute(
            f"SELECT a.started_at, a.outcome, a.runtime_s, a.session_id, {WIN} AS win, {REJECTED_WIN} AS rejected "
            "FROM attempts a"))
        sessions = rows(conn.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (session_limit,)))
        sessions_total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    finally:
        conn.close()
    days: dict[str, Counter] = defaultdict(Counter)
    per_session: dict[int | None, Counter] = defaultdict(Counter)
    for r in attempts_rows:
        d = days[r["started_at"][:10]]
        d["attempts" if r["outcome"] != "skipped" else "skipped"] += 1
        d["wins"] += r["win"]
        d["rejected_wins"] += r["rejected"]
        d["machine_s"] += r["runtime_s"] or 0
        per_session[r["session_id"]]["wins"] += r["win"]
        per_session[r["session_id"]]["rejected_wins"] += r["rejected"]
    series = [{"day": day, "attempts": c["attempts"], "wins": c["wins"], "rejected_wins": c["rejected_wins"],
               "skipped": c["skipped"], "machine_hours": c["machine_s"] / 3600} for day, c in sorted(days.items())]
    for s in sessions:
        s["wins"] = per_session[s["id"]]["wins"]
        s["rejected_wins"] = per_session[s["id"]]["rejected_wins"]
    return {"days": series, "sessions": sessions, "sessions_total": sessions_total}


# check_dir=False: the folder is looked for at each request, as the page below is, so a frontend built while the
# server runs is served without a restart (decided at import, the page appeared and its scripts did not)
app.mount("/assets", StaticFiles(directory=STATIC / "assets", check_dir=False), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    """The page itself, at `/` only. The tabs are addressed by the URL's fragment, which never reaches the
    server, so no other path has a page behind it: every other path that no route above claimed is a 404,
    `/api`, `/API/...` and `/docs` included (they used to come back as this page, with a 200). Registered
    whether or not the frontend has been built, so that the rule does not depend on it."""
    index = STATIC / "index.html"
    if path == "" and index.is_file():
        return FileResponse(index)
    raise HTTPException(404, "nothing here" if path else "dashboard not built: run `npm run build` in dashboard/")
