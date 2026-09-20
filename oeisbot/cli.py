"""oeisbot command line. Nothing here submits anything anywhere."""
from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from dataclasses import replace

from . import config, db
from .config import GiB


def _budgets(args) -> config.Budgets:
    b = config.DEFAULT_BUDGETS
    if getattr(args, "verify_s", None) is not None:
        b = replace(b, verify_wall_s=args.verify_s)
    if getattr(args, "extend_s", None) is not None:
        b = replace(b, extend_wall_s=args.extend_s)
    if getattr(args, "mem_gib", None) is not None:
        b = replace(b, mem_bytes=int(args.mem_gib * GiB))
    if getattr(args, "max_new", None) is not None:
        b = replace(b, max_new_terms=args.max_new)
    return b


def _add_budget_args(p):
    p.add_argument("--verify-s", type=float, help=f"seconds to reproduce all known terms (default {config.DEFAULT_BUDGETS.verify_wall_s:g})")
    p.add_argument("--extend-s", type=float, help=f"seconds to look for new terms (default {config.DEFAULT_BUDGETS.extend_wall_s:g})")
    p.add_argument("--mem-gib", type=float, help=f"memory cap per job (default {config.DEFAULT_BUDGETS.mem_bytes / GiB:g})")
    p.add_argument("--max-new", type=int, help="stop after this many new terms")


def cmd_setup(args):
    from .setup_tools import setup
    setup()


def cmd_sync(args):
    from .ingest import oeisdata
    with db.connect() as conn:
        oeisdata.sync(conn, pull=not args.no_pull)


def cmd_stats(args):
    from .ingest import oeisdata
    from .ingest.bfile import InconsistentTerms
    from .strategies import pari
    from .terms import KnownTerms

    conn = db.connect()
    counts = oeisdata.program_stats(conn)
    total = counts.pop("(total)", 0)
    print(f"{total} candidates (keyword 'more'), by program language present:")
    for lang, c in counts.most_common(15):
        print(f"  {lang:<14} {c:>6}  {100 * c / max(total, 1):5.1f}%")
    if args.forms:
        forms: Counter = Counter()
        for (a,) in conn.execute("SELECT a_number FROM sequences WHERE in_more = 1 AND program_langs LIKE '%pari%'"):
            entry = oeisdata.load_entry(a)
            if entry is None or not entry.data:
                continue
            known = KnownTerms(a, entry.offset, entry.data_values, "data")
            cands, rejected = pari.build_candidates(entry, known)
            if cands:
                forms[cands[0].form] += 1
            elif any("list-printing" in r.reason for r in rejected):
                forms["list printer only (unsupported)"] += 1
            elif any("another OEIS entry" in r.reason for r in rejected):
                forms["calls another entry's helper (unrunnable)"] += 1
            else:
                forms["no usable function (unsupported)"] += 1
        print("PARI-bearing candidates by the best supported program form:")
        for form, c in forms.most_common():
            print(f"  {form:<42} {c:>6}")


def _session_pool(conn, args):
    """The pool `oeisbot run` would pick from with default budgets (`--all` = the `--model` pool)."""
    from . import select
    from .attempt import Runnable
    keep = Runnable(conn, config.DEFAULT_BUDGETS, model=not args.pari)
    return select.candidates(conn, alpha=args.alpha, require_langs={"pari"} if args.pari else None, keep=keep), keep


def cmd_queue(args):
    conn = db.connect()
    pool, keep = _session_pool(conn, args)
    total_w = sum(c.weight for c in pool) or 1
    key = {"difficulty": lambda c: c.difficulty, "weight": lambda c: -c.weight, "a": lambda c: c.a_number}[args.sort]
    summary = keep.summary()
    print(f"{len(pool)} candidates; alpha={args.alpha}" + (f"; {summary}" if summary else ""))
    print(f"{'A-number':<9} {'difficulty':>10} {'pick %':>8}  {'programs':<24} name")
    for c in sorted(pool, key=key)[: args.limit]:
        print(f"{c.a_number:<9} {c.difficulty:>10.3f} {100 * c.weight / total_w:>8.4f}  {c.program_langs[:24]:<24} {c.name[:70]}")


def cmd_pick(args):
    from . import select
    conn = db.connect()
    pool, _ = _session_pool(conn, args)
    for c in select.pick(pool, args.k, random.Random(args.seed)):
        print(f"{c.a_number}  d={c.difficulty:.3f}  {c.program_langs:<20} {c.name[:80]}")


def _model(args):
    if not getattr(args, "model", False):
        return None
    from .model import LocalModel
    m = LocalModel()
    problem = m.available()
    if problem:
        raise SystemExit(f"--model: {problem}")
    return m


def cmd_attempt(args):
    from .attempt import attempt_sequence
    conn = db.connect()
    model = _model(args)
    for a in args.a_numbers:
        attempt_sequence(conn, a.upper(), _budgets(args), do_recheck=not args.no_recheck, model=model)


def cmd_run(args):
    from .attempt import run_session
    conn = db.connect()
    run_session(conn, args.n, _budgets(args), alpha=args.alpha, seed=args.seed, model=_model(args))


def cmd_recheck(args):
    from .attempt import retry_pending_rechecks
    conn = db.connect()
    if not db.pending_rechecks(conn):
        print("no wins are waiting for a re-check")
        return
    left = retry_pending_rechecks(conn)
    if left:
        raise SystemExit(f"{left} win(s) still waiting for a re-check")


def cmd_model_check(args):
    from .model import LocalModel
    m = LocalModel()
    problem = m.available()
    if problem:
        print(problem)
        raise SystemExit(1)
    reply = m.chat([{"role": "user", "content": "Reply with the single word: ready"}], max_tokens=10)
    print(f"{m.name} at {m.url} ({m.api}): {reply.strip()!r}")


def cmd_fetch_bfiles(args):
    from . import select
    from .ingest import bfile
    conn = db.connect()
    pool = sorted(select.candidates(conn, alpha=1.0, require_langs={"pari"} if args.pari else None),
                  key=lambda c: c.difficulty)
    done = 0
    for c in pool:
        if done >= args.limit:
            break
        row = conn.execute("SELECT bfile_status FROM sequences WHERE a_number = ?", (c.a_number,)).fetchone()
        if row["bfile_status"] in ("present", "absent"):
            continue
        try:
            bf = bfile.fetch(c.a_number)
        except Exception as e:
            db.update_bfile_info(conn, c.a_number, "error")
            print(f"{c.a_number}: error {e}")
            continue
        if bf is None:
            db.update_bfile_info(conn, c.a_number, "absent")
        else:
            last = bf.values[bf.last_index]
            db.update_bfile_info(conn, c.a_number, "present", len(bf.values), bf.last_index, len(str(abs(last))))
        new_row = conn.execute("SELECT * FROM sequences WHERE a_number = ?", (c.a_number,)).fetchone()
        db.set_difficulty(conn, c.a_number, select.difficulty(new_row))
        done += 1
        print(f"{c.a_number}: {'no b-file' if bf is None else f'{len(bf.values)} terms to a({bf.last_index})'}")


def cmd_attempts(args):
    conn = db.connect()
    q = "SELECT * FROM attempts"
    params: list = []
    if args.failure:
        q += " WHERE failure_mode = ?"
        params.append(args.failure)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(args.limit)
    for r in conn.execute(q, params):
        print(f"#{r['id']:<5} {r['a_number']} {r['strategy']:<16} {r['outcome']:<10} {r['failure_mode'] or '':<22} "
              f"new={r['new_terms']:<3} {(r['runtime_s'] or 0):7.1f}s  {(r['detail'] or '')[:70]}")
    print("\nfailure modes:", dict(conn.execute("SELECT failure_mode, COUNT(*) FROM attempts GROUP BY failure_mode").fetchall()))


def cmd_dashboard(args):
    import uvicorn
    from .dashboard.app import STATIC, app
    if not STATIC.is_dir():
        print("dashboard not built: run `npm install` and `npm run build` in dashboard/ (API still available)")
    print(f"OEISBot dashboard (read-only) on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def cmd_review(args):
    conn = db.connect()
    if args.action == "list":
        for r in conn.execute("SELECT * FROM reviews ORDER BY id DESC"):
            print(f"#{r['id']:<4} {r['a_number']} a({r['first_new_index']})..a({r['last_new_index']}) "
                  f"{r['status']:<10} {r['artifact_path']}  {r['note'] or ''}")
    else:
        db.set_review_status(conn, args.id, args.status, args.note)
        print(f"review #{args.id} -> {args.status}")


def main(argv: list[str] | None = None) -> int:
    sys.set_int_max_str_digits(0)
    p = argparse.ArgumentParser(prog="oeisbot", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="install sandbox runtimes, grant sandbox access, create the database").set_defaults(fn=cmd_setup)

    s = sub.add_parser("sync", help="git pull oeisdata and rebuild the candidate table")
    s.add_argument("--no-pull", action="store_true")
    s.set_defaults(fn=cmd_sync)

    s = sub.add_parser("stats", help="program languages among candidates")
    s.add_argument("--forms", action="store_true", help="also classify PARI program forms (slower)")
    s.set_defaults(fn=cmd_stats)

    for name, fn, help_ in (("queue", cmd_queue, "candidates with difficulty and pick probability"),
                            ("pick", cmd_pick, "weighted random pick")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("--alpha", type=float, default=1.0)
        s.add_argument("--all", dest="pari", action="store_false",
                       help="the `run --model` pool: include sequences without a PARI program")
        if name == "queue":
            s.add_argument("--limit", type=int, default=40)
            s.add_argument("--sort", choices=["difficulty", "weight", "a"], default="difficulty")
        else:
            s.add_argument("-k", type=int, default=10)
            s.add_argument("--seed", type=int)
        s.set_defaults(fn=fn)

    s = sub.add_parser("attempt", help="attempt specific sequences")
    s.add_argument("a_numbers", nargs="+")
    s.add_argument("--no-recheck", action="store_true", help="skip the oeis.org re-check (testing only)")
    s.add_argument("--model", action="store_true", help="fall back to local-model code generation")
    _add_budget_args(s)
    s.set_defaults(fn=cmd_attempt)

    s = sub.add_parser("run", help="pick and attempt sequences")
    s.add_argument("-n", type=int, default=5)
    s.add_argument("--alpha", type=float, default=1.0)
    s.add_argument("--seed", type=int)
    s.add_argument("--model", action="store_true", help="also pick sequences without PARI and use the local model")
    _add_budget_args(s)
    s.set_defaults(fn=cmd_run)

    sub.add_parser("recheck", help="retry the oeis.org re-check of wins left as recheck_pending").set_defaults(fn=cmd_recheck)

    sub.add_parser("model-check", help="check the local model server").set_defaults(fn=cmd_model_check)

    s = sub.add_parser("fetch-bfiles", help="prefetch b-files for the easiest candidates (1 request/s)")
    s.add_argument("--limit", type=int, default=100)
    s.add_argument("--all", dest="pari", action="store_false")
    s.set_defaults(fn=cmd_fetch_bfiles)

    s = sub.add_parser("attempts", help="recent attempts")
    s.add_argument("--limit", type=int, default=30)
    s.add_argument("--failure")
    s.set_defaults(fn=cmd_attempts)

    s = sub.add_parser("dashboard", help="read-only web dashboard")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.set_defaults(fn=cmd_dashboard)

    s = sub.add_parser("review", help="review inbox")
    rs = s.add_subparsers(dest="action", required=True)
    rs.add_parser("list")
    st = rs.add_parser("set")
    st.add_argument("id", type=int)
    st.add_argument("status", choices=["new", "reviewing", "submitted", "rejected"])
    st.add_argument("--note")
    s.set_defaults(fn=cmd_review)

    args = p.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
