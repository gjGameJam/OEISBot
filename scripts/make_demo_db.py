"""Generate a synthetic database and artifacts for eyeballing the dashboard.

DESTRUCTIVE for its target: it deletes data/ and artifacts/ under OEISBOT_HOME before writing. It
refuses to run unless OEISBOT_HOME points somewhere other than the project root, so real data is safe.

    set OEISBOT_HOME=C:\\temp\\oeisbot-demo          (PowerShell: $env:OEISBOT_HOME = "C:\\temp\\oeisbot-demo")
    .venv\\Scripts\\python scripts\\make_demo_db.py
    .venv\\Scripts\\oeisbot dashboard --port 8766      (same OEISBOT_HOME)

All values are random: sequence names, predictions, failure modes and review folders are fake.
"""
import json
import math
import os
import random
import shutil
import sys
from pathlib import Path

from oeisbot import config, db

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    home = os.environ.get("OEISBOT_HOME")
    if not home or Path(home).resolve() == PROJECT_ROOT:
        sys.exit("refusing to run: set OEISBOT_HOME to a scratch directory (this script deletes its data/ and artifacts/)")
    rng = random.Random(3)
    for d in (config.DATA, config.ARTIFACTS):
        if d.exists():
            shutil.rmtree(d)
    conn = db.connect()

    rows = []
    for i in range(400):
        langs = rng.choice(["pari", "pari,mathematica", "mathematica", "", "python,pari", "maple,mathematica,pari"])
        rows.append(db.SequenceRow(f"A{100000 + i * 37:06d}", f"Demo sequence {i}: numbers k such that something holds", 1,
                                   "nonn,more" + (",hard" if i % 13 == 0 else ""), rng.randint(5, 60), rng.randint(1, 40),
                                   langs, rng.randint(0, 3), i % 7 == 0))
    db.upsert_sequences(conn, rows)
    db.set_meta(conn, "oeisdata_commit", "0000000000demo")
    db.set_meta(conn, "synced_at", "2026-09-17T13:06:08+00:00")

    failures = (["verify_timeout"] * 9 + ["wrong_term"] * 3 + ["crash"] * 4 + ["memory_cap"] * 2 + ["infeasible"] * 6
                + ["extend_budget"] * 5 + ["over_prediction"] * 3 + ["max_new_terms"] * 2 + ["bad_index"] * 2)
    skips = ["no_supported_program"] * 12 + ["inconsistent_known_terms"] * 2 + ["model_skip"] * 4 + ["all_programs_dead_ends"]
    days = ["2026-09-10", "2026-09-11", "2026-09-12", "2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17"]
    sid = db.start_session(conn, "demo")
    made = []
    for k, fm in enumerate(failures + skips):
        a = rows[rng.randrange(len(rows))].a_number
        day = rng.choice(days)
        skipped = fm in skips
        extended = fm == "max_new_terms" or (fm in ("extend_budget", "over_prediction", "infeasible") and rng.random() < 0.4)
        verified_stop = fm in ("infeasible", "extend_budget", "over_prediction")
        outcome = "skipped" if skipped else "extended" if extended else "verified" if verified_stop else "failed"
        runtime = None if skipped else rng.uniform(5, 7000)
        strategy = "pari" if skipped else rng.choice(["pari:a(n)", "pari:predicate", "pari:print-loop", "python:model"])
        with conn:
            cur = conn.execute("""INSERT INTO attempts(session_id, a_number, strategy, program_origin, started_at, finished_at,
                verified, known_terms, known_source, reproduced, new_terms, runtime_s, cpu_s, peak_mem_bytes, cost_unit,
                outcome, failure_mode, detail, extra) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sid, a, strategy, None if skipped else f"{a} %o (PARI) block 1", f"{day}T1{k % 10}:00:00+00:00",
                 f"{day}T1{k % 10}:30:00+00:00", int(outcome in ("verified", "extended")),
                 None if skipped else 40, None if skipped else "bfile", None if skipped else (17 if outcome == "failed" else 40),
                 rng.randint(1, 12) if extended else 0, runtime, runtime and runtime * 0.97,
                 None if skipped else rng.randint(20, 3000) << 20, None if skipped else rng.choice(["work", "cpu"]),
                 outcome, fm, f"demo detail for {fm}", json.dumps({})))
        made.append((cur.lastrowid, outcome, a))

    for aid, outcome, a in made:
        if outcome not in ("verified", "extended"):
            continue
        unit = rng.choice(["work", "cpu"])
        base, growth, noise = rng.uniform(0.01, 30), rng.uniform(1.3, 3.5), (0.25 if unit == "work" else 0.6)
        for j in range(rng.randint(2, 7)):
            pred = base * growth ** j
            actual, censored = pred * math.exp(rng.gauss(0.15, noise)), None
            if j == 6 or rng.random() < 0.08:
                censored, actual = actual * rng.uniform(1.5, 4), None
            with conn:
                conn.execute("""INSERT INTO predictions(attempt_id, n, cost_unit, predicted_s, predicted_s_low, predicted_s_high,
                    predicted_mem, model, trustworthy, feasible, value_dependent, actual_s, actual_mem, censored_s)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (aid, 30 + j, unit, pred, pred / rng.uniform(1, 2.5), pred * rng.uniform(1, 3), 1e8,
                     rng.choice(["exp", "poly", "ratio"]), int(rng.random() < 0.7), 1, 0, actual, 9e7, censored))
            if censored:
                break

    for aid, outcome, a in made:
        if outcome != "extended":
            continue
        folder = config.ARTIFACTS / a / f"attempt-{aid}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "README.md").write_text(f"# {a}: demo\n\nSynthetic review folder. Nothing has been submitted.\n")
        (folder / "program.gp").write_text("isok(k) = isprime(k^2+1)\n")
        (folder / f"b{a[1:]}.txt").write_text("\n".join(f"{n} {n * n + 1}" for n in range(1, 50)) + "\n")
        rel = str(folder.relative_to(config.ROOT))
        with conn:
            conn.execute("UPDATE attempts SET artifact_path = ? WHERE id = ?", (rel, aid))
        rid = db.add_review(conn, a, aid, rel, 41, 45)
        if rng.random() < 0.3:
            db.set_review_status(conn, rid, rng.choice(["reviewing", "rejected"]))
    db.finish_session(conn, sid)
    print("demo database at", config.DB_PATH)


if __name__ == "__main__":
    main()
