"""Dashboard API (build step 8). Read-only over the SQLite database: every request opens a
mode=ro connection, and nothing here writes. Review status changes go through the CLI
(`oeisbot review set ...`) so the harness remains the only writer.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .. import config, db, select

STATIC = Path(__file__).parent / "static"
TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json", ".gp", ".py"}

app = FastAPI(title="OEISBot dashboard", docs_url="/api/docs", openapi_url="/api/openapi.json")


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
            "wins": one("SELECT COUNT(*) FROM attempts WHERE outcome = 'extended'"),
            "new_terms": one("SELECT COALESCE(SUM(new_terms), 0) FROM attempts WHERE outcome = 'extended'"),
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
    finished = [p for p in points if p["actual_s"] and p["actual_s"] > 0]
    ratios = [p["actual_s"] / p["predicted_s"] for p in finished]
    in_range = [p for p in finished if p["predicted_s_low"] is not None
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
def queue(alpha: float = 1.0, pari_only: bool = True, limit: int = Query(500, le=30000),
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


@app.get("/api/attempts")
def attempts(failure_mode: str | None = None, outcome: str | None = None, strategy: str | None = None,
             limit: int = Query(300, le=5000)):
    conn = ro()
    try:
        where, params = [], []
        for col, val in (("failure_mode", failure_mode), ("outcome", outcome), ("strategy", strategy)):
            if val:
                where.append(f"{col} = ?")
                params.append(val)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        data = rows(conn.execute(f"""
            SELECT id, session_id, a_number, strategy, program_origin, started_at, verified, known_terms, known_source,
                   reproduced, new_terms, runtime_s, cpu_s, peak_mem_bytes, cost_unit, projected_next_s_high,
                   outcome, failure_mode, detail, artifact_path
            FROM attempts {clause} ORDER BY id DESC LIMIT ?""", (*params, limit)))
        failure_counts = dict(conn.execute(
            "SELECT failure_mode, COUNT(*) FROM attempts WHERE outcome != 'skipped' GROUP BY failure_mode").fetchall())
        skip_counts = dict(conn.execute(
            "SELECT failure_mode, COUNT(*) FROM attempts WHERE outcome = 'skipped' GROUP BY failure_mode").fetchall())
        outcome_counts = dict(conn.execute("SELECT outcome, COUNT(*) FROM attempts GROUP BY outcome").fetchall())
        strategies = [r[0] for r in conn.execute("SELECT DISTINCT strategy FROM attempts ORDER BY strategy")]
    finally:
        conn.close()
    return {"rows": data, "failure_counts": failure_counts, "skip_counts": skip_counts,
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
                   r.note, r.created_at, r.updated_at, a.strategy, a.new_terms, a.runtime_s, a.known_terms,
                   a.known_source, a.extra, s.name
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
    return {"rows": data}


@app.get("/api/reviews/{review_id}/files/{name}", response_class=PlainTextResponse)
def review_file(review_id: int, name: str):
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
def history():
    conn = ro()
    try:
        attempts_rows = rows(conn.execute("SELECT started_at, outcome, runtime_s FROM attempts"))
        sessions = rows(conn.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 100"))
    finally:
        conn.close()
    days: dict[str, Counter] = defaultdict(Counter)
    for r in attempts_rows:
        d = days[r["started_at"][:10]]
        d["attempts" if r["outcome"] != "skipped" else "skipped"] += 1
        d["wins"] += r["outcome"] == "extended"
        d["machine_s"] += r["runtime_s"] or 0
    series = [{"day": day, "attempts": c["attempts"], "wins": c["wins"], "skipped": c["skipped"],
               "machine_hours": c["machine_s"] / 3600} for day, c in sorted(days.items())]
    return {"days": series, "sessions": sessions}


if STATIC.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "no such API path")
        return FileResponse(STATIC / "index.html")
