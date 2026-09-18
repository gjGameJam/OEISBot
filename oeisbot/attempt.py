"""Attempt one sequence end to end: known terms -> strategies -> verified run -> re-check -> artifact.

Strategy order: the entry's own PARI programs first (run longer), then, if a local model is
configured, model-generated Python. Every run is recorded; only verified runs with new terms that
survive the live re-check become review artifacts.

A run with new terms is recorded as `recheck_pending`, and its result saved to data/pending/, *before*
the re-check starts; the re-check then resolves it. If the re-check cannot finish (oeis.org unreachable,
an error, the process stopped), it stays pending and `retry_pending_rechecks` resolves it later.
"""
from __future__ import annotations

import pickle
import random
import sqlite3
import time
from dataclasses import dataclass, field
from http.client import HTTPException
from pathlib import Path
from typing import Callable

from . import artifact, config, db, select
from .config import Budgets
from .ingest import bfile, oeisdata
from .ingest.seqfile import Entry, parse
from .model import ModelClient, ModelUnavailable
from .strategies import codegen, pari
from .terms import KnownTerms, Program
from .verify import AttemptResult, run_attempt

MAX_PROGRAMS_PER_SEQUENCE = 3
RECHECK_RETRY_WAITS_S = (30.0, 120.0)   # pauses between re-check tries before a win is left pending
# re-check errors worth waiting for (network, server, an error page); anything else is not retried
TRANSIENT_ERRORS = (OSError, HTTPException, bfile.UnexpectedResponse)


@dataclass
class SequenceReport:
    a_number: str
    attempt_ids: list[int] = field(default_factory=list)
    skipped: str | None = None
    artifact: str | None = None
    lines: list[str] = field(default_factory=list)


def recheck(known: KnownTerms, first_new_index: int, new_values: dict[int, int]) -> tuple[bool, str]:
    """Ask oeis.org, right before recording a win, whether someone has extended the sequence meanwhile.
    Returns (still_new, note)."""
    a = known.a_number
    live = bfile.fetch(a, refresh=True)
    text = bfile.fetch_entry_text(a)
    entry = parse(text) if text else None
    if entry is None:
        return False, "could not read the live entry"
    live_values = dict(entry.data_values)
    if live:
        live_values.update(live.values)
    if not live_values:
        return False, "could not read any terms from the live entry"
    overlap = {n for n in new_values if n in live_values}
    conflicts = [n for n in overlap if live_values[n] != new_values[n]]
    if conflicts:
        return False, f"live entry now has a({conflicts[0]}) = {live_values[conflicts[0]]}, which DISAGREES with this run"
    if overlap:
        return False, f"live entry already has {len(overlap)} of the new terms (up to a({max(live_values)}))"
    if "more" not in entry.keywords:
        return True, "keyword 'more' was removed from the live entry; new terms still unpublished"
    return True, f"live entry ends at a({max(live_values)}); new terms start at a({first_new_index})"


def _recheck_with_retries(result: AttemptResult, say: Callable[[str], None]) -> tuple[bool, str]:
    """recheck(), tried again after transient errors. Raises the last error, or any other error at once."""
    new = result.new_terms
    for wait in (*RECHECK_RETRY_WAITS_S, None):
        try:
            return recheck(result.known, new[0].n, {t.n: t.value for t in new})
        except TRANSIENT_ERRORS as e:
            if wait is None:
                raise
            say(f"re-check failed ({type(e).__name__}: {e}); trying again in {wait:g} s")
            time.sleep(wait)


def pending_path(attempt_id: int) -> Path:
    """The saved AttemptResult of a win waiting for its re-check. Outside data/scratch, so the sandbox
    cannot write it."""
    return config.DATA / "pending" / f"attempt-{attempt_id}.pickle"


def _save_pending(attempt_id: int, result: AttemptResult, entry_name: str, budgets: Budgets) -> None:
    path = pending_path(attempt_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(pickle.dumps({"result": result, "entry_name": entry_name, "budgets": budgets}))
    tmp.replace(path)


def _discard_pending(attempt_id: int, log: Callable[[str], None]) -> None:
    try:
        pending_path(attempt_id).unlink(missing_ok=True)
    except OSError as e:     # harmless: nothing reads the file once the attempt is resolved
        log(f"could not delete {pending_path(attempt_id)}: {e}")


def _resolve(conn: sqlite3.Connection, result: AttemptResult, attempt_id: int, entry_name: str, budgets: Budgets,
             still_new: bool, note: str) -> str | None:
    """Apply a re-check verdict to a `recheck_pending` attempt: artifact folder + review for a win (returns
    its path), `superseded` otherwise. Safe to repeat after an interruption."""
    if not still_new:
        db.set_recheck_result(conn, attempt_id, note, outcome="superseded")
        return None
    folder = artifact.write(result, attempt_id, entry_name, budgets, note)
    rel = str(folder.relative_to(config.ROOT)) if folder.is_relative_to(config.ROOT) else str(folder)
    new = result.new_terms
    db.record_win(conn, attempt_id, result.known.a_number, rel, new[0].n, new[-1].n, note)
    try:
        artifact.mark_complete(folder)
    except OSError:
        pass    # a stray marker in a recorded folder is harmless: only pending attempts' folders are rewritten
    return rel


def retry_pending_rechecks(conn: sqlite3.Connection, log: Callable[[str], None] = print) -> int:
    """Re-check every win left as `recheck_pending`, once each, oldest first. Never raises for a single
    attempt: a failure is logged and the attempt stays pending. Returns how many are still pending."""
    still_pending = 0
    for row in db.pending_rechecks(conn):
        a, attempt_id = row["a_number"], row["id"]
        try:
            saved = pickle.loads(pending_path(attempt_id).read_bytes())
            result: AttemptResult = saved["result"]
            new = result.new_terms
            still_new, note = recheck(result.known, new[0].n, {t.n: t.value for t in new})
            log(f"[{a}] attempt #{attempt_id}: re-check: {note}")
            rel = _resolve(conn, result, attempt_id, saved["entry_name"], saved["budgets"], still_new, note)
        except Exception as e:
            log(f"[{a}] attempt #{attempt_id}: still pending ({type(e).__name__}: {e}); saved result: "
                f"{pending_path(attempt_id)}; new terms also in the run log named in attempts.extra")
            still_pending += 1
            continue
        if rel:
            log(f"[{a}] artifact: {rel}")
        _discard_pending(attempt_id, lambda m: log(f"[{a}] {m}"))
    return still_pending


class _Attempter:
    def __init__(self, conn: sqlite3.Connection, entry: Entry, known: KnownTerms, budgets: Budgets,
                 session_id: int | None, rep: SequenceReport, say: Callable[[str], None], do_recheck: bool):
        self.conn, self.entry, self.known, self.budgets = conn, entry, known, budgets
        self.session_id, self.rep, self.say, self.do_recheck = session_id, rep, say, do_recheck
        self.finished = False      # a success, a superseded run, or a verified dead end: stop trying

    def run(self, prog: Program, form: str) -> AttemptResult:
        started = db.now()
        runs = config.DATA / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        log_path = runs / f"{self.known.a_number}-{time.strftime('%Y%m%d-%H%M%S')}-{prog.sha[:8]}.jsonl"
        if prog.language == "python":
            (runs / f"{log_path.stem}.py").write_text(prog.source, encoding="utf-8")   # keep every generated program
        self.say(f"running {prog.strategy} from {prog.origin}")
        result = run_attempt(prog, self.known, self.budgets, name=self.entry.name, log_path=log_path)
        new = result.new_terms
        self.say(f"-> {result.outcome}: {result.stop.value} ({result.detail[:160]}); reproduced "
                 f"{result.reproduced}/{self.known.count}, {len(new)} new, {result.run.wall_s:.1f} s, "
                 f"peak {result.peak_mem_bytes / 2**20:.0f} MiB")
        extra = {"log": str(log_path), "form": form, "rewrites": prog.notes,
                 "weak_verification": result.weak_verification,
                 # the budgets a verified-but-infeasible run is judged against (db.is_dead_end)
                 "extend_wall_s": self.budgets.extend_wall_s, "mem_bytes": self.budgets.mem_bytes}
        if not new:
            self.rep.attempt_ids.append(db.record_attempt(self.conn, result, started_at=started,
                                                          session_id=self.session_id, extra=extra))
            if result.verified:
                self.finished = True   # verified but cannot go further: other variants unlikely to do better cheaply
            return result

        # new terms: record and save them as pending first, so nothing below can lose them
        self.finished = True
        extra["recheck"] = "not done yet"
        attempt_id = db.record_attempt(self.conn, result, started_at=started, session_id=self.session_id,
                                       outcome="recheck_pending", extra=extra)
        self.rep.attempt_ids.append(attempt_id)
        kept = (f"kept as recheck_pending (attempt #{attempt_id}); `oeisbot recheck` or the next `oeisbot run` "
                "retries it")
        if self.do_recheck:
            try:
                _save_pending(attempt_id, result, self.entry.name, self.budgets)
            except Exception as e:
                self.say(f"could not save the result for a later re-check ({type(e).__name__}: {e}); "
                         f"the terms are in {log_path}")
            try:
                still_new, note = _recheck_with_retries(result, self.say)
            except Exception as e:
                db.set_recheck_result(self.conn, attempt_id, f"not done: {type(e).__name__}: {e}")
                self.say(f"re-check failed ({type(e).__name__}: {e}); {kept}")
                return result
        else:
            still_new, note = True, "skipped"
        self.say(f"re-check: {note}")
        try:
            rel = _resolve(self.conn, result, attempt_id, self.entry.name, self.budgets, still_new, note)
        except Exception as e:
            self.say(f"recording the re-check result failed ({type(e).__name__}: {e}); {kept}")
            return result
        _discard_pending(attempt_id, self.say)
        if rel:
            self.rep.artifact = rel
            self.say(f"artifact: {rel}")
        return result


def attempt_sequence(conn: sqlite3.Connection, a_number: str, budgets: Budgets = config.DEFAULT_BUDGETS, *,
                     session_id: int | None = None, log: Callable[[str], None] = print,
                     max_programs: int = MAX_PROGRAMS_PER_SEQUENCE, do_recheck: bool = True,
                     model: ModelClient | None = None) -> SequenceReport:
    rep = SequenceReport(a_number)

    def say(msg: str):
        rep.lines.append(msg)
        log(f"[{a_number}] {msg}")

    def skip(reason: str, detail: str = "", strategy: str = "pari") -> SequenceReport:
        rep.skipped = reason
        rep.attempt_ids.append(db.record_skip(conn, a_number, strategy, reason, detail, session_id))
        say(f"skip: {reason}{': ' + detail if detail else ''}")
        return rep

    entry = oeisdata.load_entry(a_number)
    if entry is None:
        return skip("not_in_oeisdata")
    if "more" not in entry.keywords:
        return skip("no_more_keyword")
    if (review := db.open_review(conn, a_number)) is not None:
        return skip("open_review", f"review #{review['id']} is {review['status']}")
    if (pending := db.pending_recheck(conn, a_number)) is not None:
        return skip("recheck_pending", f"attempt #{pending['id']} found new terms and waits for `oeisbot recheck`")
    try:
        bf = bfile.fetch(a_number)
    except Exception as e:
        db.update_bfile_info(conn, a_number, "error")
        return skip("bfile_error", str(e))
    if bf is None:
        db.update_bfile_info(conn, a_number, "absent")
    else:
        db.update_bfile_info(conn, a_number, "present", len(bf.values), bf.last_index,
                             len(str(abs(bf.values[bf.last_index]))))
    try:
        known = bfile.known_terms(entry, bf)
    except bfile.InconsistentTerms as e:
        return skip("inconsistent_known_terms", str(e))
    say(f"known {known.describe()}{' (' + '; '.join(known.notes) + ')' if known.notes else ''}")

    runner = _Attempter(conn, entry, known, budgets, session_id, rep, say, do_recheck)
    candidates, rejected = pari.build_candidates(entry, known)
    for r in rejected:
        say(f"PARI block {r.block}: {r.reason}")
    tried = dead_ends = 0
    for cand in candidates:
        if tried >= max_programs or runner.finished:
            break
        if (dead := db.is_dead_end(conn, a_number, cand.program.sha, known.count, budgets)) is not None:
            say(f"{cand.program.origin}: failed the same way before (attempt #{dead['id']}: {dead['failure_mode']})")
            dead_ends += 1
            continue
        tried += 1
        runner.run(cand.program, cand.form)

    if not runner.finished and model is not None:
        if known.count < config.CODEGEN_MIN_KNOWN_TERMS:
            return skip("too_few_known_terms", f"{known.count} known terms; the model needs at least "
                        f"{config.CODEGEN_MIN_KNOWN_TERMS} so {config.CODEGEN_HELD_OUT_MIN} can be held out",
                        strategy="python:model")
        try:
            outcome = codegen.generate_and_verify(entry, known, model, lambda prog: runner.run(prog, "model"), log=say)
        except ModelUnavailable as e:
            say(f"model unavailable: {e}")
        else:
            if outcome.skipped:
                return skip("model_skip", outcome.skipped, strategy="python:model")
            if not outcome.attempts:
                return skip("model_no_runnable_code", "; ".join(outcome.rejected), strategy="python:model")
            tried += len(outcome.attempts)

    if tried == 0:
        if dead_ends:
            return skip("all_programs_dead_ends")
        return skip("no_supported_program", "; ".join(r.reason for r in rejected) or "no PARI program, no model")
    return rep


def run_session(conn: sqlite3.Connection, count: int, budgets: Budgets = config.DEFAULT_BUDGETS, *,
                alpha: float = 1.0, seed: int | None = None, log: Callable[[str], None] = print,
                a_numbers: list[str] | None = None, model: ModelClient | None = None) -> int:
    count = min(count, budgets.session_attempt_cap)
    session_id = db.start_session(conn, note=f"count={count} alpha={alpha} seed={seed} model={getattr(model, 'name', None)}")
    try:
        if db.pending_rechecks(conn):
            left = retry_pending_rechecks(conn, log)
            log(f"session {session_id}: {left} win(s) still waiting for a re-check" if left else
                f"session {session_id}: pending re-checks resolved")
        if a_numbers is None:
            pool = select.candidates(conn, alpha=alpha, require_langs=None if model else {"pari"})
            chosen = [c.a_number for c in select.pick(pool, count, random.Random(seed))]
            log(f"session {session_id}: picked {len(chosen)} of {len(pool)} candidates (alpha={alpha})")
        else:
            chosen = a_numbers[:count]
        for a in chosen:
            attempt_sequence(conn, a, budgets, session_id=session_id, log=log, model=model)
    finally:
        db.finish_session(conn, session_id)
    return session_id
