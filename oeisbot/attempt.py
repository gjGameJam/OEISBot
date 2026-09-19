"""Attempt one sequence end to end: known terms -> strategies -> verified run -> re-check -> artifact.

Strategy order: the entry's own PARI programs first, then, if a local model is configured and no run
found new terms, model-generated Python -- also after a PARI program that reproduced every known term but
found nothing new, since a faster program is exactly what that case needs. Every run is recorded; only
verified runs with new terms that survive the live re-check become review artifacts.

`pari_plan` decides which PARI programs are worth running (not known dead ends, not provably out of reach
of the verify budget). Selection uses the same function (`Runnable`), so a session does not pick
sequences an attempt could only skip.

A run with new terms is recorded as `recheck_pending`, and its result saved to data/pending/, *before*
the re-check starts; the re-check then resolves it. If the re-check cannot finish (oeis.org unreachable,
an error, the process stopped), it stays pending and `retry_pending_rechecks` resolves it later.
"""
from __future__ import annotations

import pickle
import random
import sqlite3
import time
import uuid
from collections import Counter
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
        # a run found new terms (whatever its re-check then says): stop trying anything else
        self.found_new = False
        # the latest run that reproduced every known term but found no new one: other PARI programs are
        # unlikely to do better cheaply, but a faster model-written program still might
        self.verified: codegen.VerifiedRun | None = None
        # one key for every run row this attempt writes (a skip row has no extra), so the failure penalty counts
        # attempts, not program runs (select.candidates). A uuid: two attempts on one sequence can start within
        # the same second
        self.call = uuid.uuid4().hex

    def run(self, prog: Program, form: str) -> AttemptResult:
        started = db.now()
        runs = config.DATA / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        log_path = runs / f"{self.known.a_number}-{time.strftime('%Y%m%d-%H%M%S')}-{prog.sha[:8]}.jsonl"
        if prog.language == "python":
            # keep every generated program as it ran (with the driver of a members(work) program), byte for
            # byte, so its sha256 prefix is the recorded program_sha (text mode would write CRLF on Windows)
            (runs / f"{log_path.stem}.py").write_bytes(prog.executed.encode("utf-8"))
        self.say(f"running {prog.strategy} from {prog.origin}")
        result = run_attempt(prog, self.known, self.budgets, name=self.entry.name, log_path=log_path)
        new = result.new_terms
        self.say(f"-> {result.outcome}: {result.stop.value} ({result.detail[:160]}); reproduced "
                 f"{result.reproduced}/{self.known.count}, {len(new)} new, {result.run.wall_s:.1f} s, "
                 f"peak {result.peak_mem_bytes / 2**20:.0f} MiB")
        extra = {"log": str(log_path), "form": form, "rewrites": prog.notes, "attempt_call": self.call,
                 "weak_verification": result.weak_verification,
                 # the budgets a verified run without new terms is judged against (db.is_dead_end)
                 "extend_wall_s": self.budgets.extend_wall_s, "mem_bytes": self.budgets.mem_bytes}
        if not new:
            attempt_id = db.record_attempt(self.conn, result, started_at=started, session_id=self.session_id,
                                           extra=extra)
            self.rep.attempt_ids.append(attempt_id)
            if result.verified:
                self.verified = codegen.VerifiedRun(prog.origin, self.known.count, result.stop.value, result.detail,
                                                    attempt_id, result.verified_at_s)
            return result

        # new terms: record and save them as pending first, so nothing below can lose them
        self.found_new = True
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


@dataclass
class PariPlan:
    """The entry's PARI programs, sorted into what an attempt would do with each."""
    runnable: list[pari.Candidate]                         # in the order they would run
    rejected: list[pari.Rejected]                          # blocks with no supported program form
    dead_ends: list[tuple[pari.Candidate, sqlite3.Row]]    # not worth running again (db.is_dead_end)
    out_of_reach: list[tuple[pari.Candidate, str]]         # cannot reproduce the known terms in the verify budget

    def nothing_to_run(self) -> tuple[str, str]:
        """The skip reason and detail recorded when none of the programs runs."""
        if not self.dead_ends and not self.out_of_reach:
            return "no_supported_program", "; ".join(r.reason for r in self.rejected) or "no PARI program, no model"
        if not self.dead_ends:
            return "verify_out_of_reach", "; ".join(why for _, why in self.out_of_reach)
        extra = f"; {len(self.out_of_reach)} more out of reach of the verify budget" if self.out_of_reach else ""
        return "all_programs_dead_ends", (f"{len(self.dead_ends)} already tried: failed the same way, or verified "
                                          f"and found nothing new with no smaller budget{extra}")


def pari_plan(conn: sqlite3.Connection, entry: Entry, known: KnownTerms, budgets: Budgets) -> PariPlan:
    candidates, rejected = pari.build_candidates(entry, known)
    plan = PariPlan([], rejected, [], [])
    for cand in candidates:
        if (dead := db.is_dead_end(conn, entry.a_number, cand.program.sha, known.count, budgets)) is not None:
            plan.dead_ends.append((cand, dead))
        elif (why := pari.out_of_reach(cand, known, budgets.verify_wall_s)) is not None:
            plan.out_of_reach.append((cand, why))
        else:
            plan.runnable.append(cand)
    # a dead end that verified does not hold the entry's other programs back: in a later attempt the next one
    # gets its turn (within one attempt a verified run still ends the PARI stage, attempt_sequence)
    return plan


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
    elif not bf.values:     # a b-file with no usable line: known_terms falls back to DATA
        db.update_bfile_info(conn, a_number, "present", 0)
    else:
        db.update_bfile_info(conn, a_number, "present", len(bf.values), bf.last_index,
                             len(str(abs(bf.values[bf.last_index]))))
    try:
        known = bfile.known_terms(entry, bf)
    except bfile.InconsistentTerms as e:
        return skip("inconsistent_known_terms", str(e))
    say(f"known {known.describe()}{' (' + '; '.join(known.notes) + ')' if known.notes else ''}")

    runner = _Attempter(conn, entry, known, budgets, session_id, rep, say, do_recheck)
    plan = pari_plan(conn, entry, known, budgets)
    for r in plan.rejected:
        say(f"PARI block {r.block}: {r.reason}")
    for cand, dead in plan.dead_ends:
        why = {"extend_budget": "verified before and found nothing new in no less time",
               "infeasible": "verified before and judged the next term infeasible with no less time and memory",
               }.get(dead["failure_mode"], "failed the same way before")
        say(f"{cand.program.origin}: {why} (attempt #{dead['id']}: {dead['failure_mode']})")
    for cand, why in plan.out_of_reach:
        say(f"{cand.program.origin}: not run: {why}")
    tried = 0
    for cand in plan.runnable:
        if tried >= max_programs or runner.found_new or runner.verified is not None:
            break
        tried += 1
        runner.run(cand.program, cand.form)

    if not runner.found_new and model is not None:
        if known.count < config.CODEGEN_MIN_KNOWN_TERMS:
            return skip("too_few_known_terms", f"{known.count} known terms; the model needs at least "
                        f"{config.CODEGEN_MIN_KNOWN_TERMS} so {config.CODEGEN_HELD_OUT_MIN} can be held out",
                        strategy="python:model")
        # an entry program that verified, in this attempt or in an earlier one that is now a dead end
        verified = runner.verified or next(
            (codegen.VerifiedRun(cand.program.origin, known.count, dead["failure_mode"], dead["detail"] or "", dead["id"])
             for cand, dead in plan.dead_ends if dead["verified"] and not dead["new_terms"]), None)
        if verified is not None:
            say(f"{verified.origin} is correct but found nothing new; asking the model for a faster program")
        try:
            outcome = codegen.generate_and_verify(entry, known, model, lambda prog: runner.run(prog, "model"),
                                                  log=say, verified_elsewhere=verified)
        except ModelUnavailable as e:
            say(f"model unavailable: {e}")
        else:
            if outcome.skipped:
                return skip("model_skip", outcome.skipped, strategy="python:model")
            if not outcome.attempts:
                return skip("model_no_runnable_code", "; ".join(outcome.rejected), strategy="python:model")
            tried += len(outcome.attempts)

    if tried == 0:
        return skip(*plan.nothing_to_run())
    return rep


class Runnable:
    """A `select.candidates` keep-check that leaves out sequences an attempt could only skip: a PARI-bearing
    sequence whose programs are all unsupported, known dead ends or out of reach of the verify budget, unless
    the model could take it. It runs the attempt's own `pari_plan` on the known terms the attempt would use,
    and never makes a request.

    Where the attempt's gates would record a skip -- entry missing, b-file not decidable offline (the
    attempt's lookup may download it, or record `bfile_error`), known terms inconsistent -- the row is kept
    and the attempt records what happens. An error the attempt has no gate for would stop the session, so
    such a row is left out and reported instead."""

    def __init__(self, conn: sqlite3.Connection, budgets: Budgets, model: bool):
        self.conn, self.budgets, self.model = conn, budgets, model
        self.left_out: Counter[str] = Counter()     # skip reason an attempt would record -> sequences
        self.undecided = 0                          # kept: the attempt's gates decide
        self.errors: list[str] = []                 # left out: the check raised where an attempt would too

    def __call__(self, row: sqlite3.Row) -> bool:
        if "pari" not in set(filter(None, row["program_langs"].split(","))):
            return True     # only in the pool when the model is on, which decides for itself
        a = row["a_number"]
        try:
            reason = self._why_not(a)
        except Exception as e:
            self.errors.append(f"{a}: {type(e).__name__}: {e}")
            return False
        if reason is None:
            return True
        self.left_out[reason] += 1
        return False

    def _gated(self, a_number: str) -> tuple[Entry, KnownTerms] | None:
        """Entry and known terms as the attempt gets them, or None where its gates would record a skip."""
        entry = oeisdata.load_entry(a_number)
        if entry is None:
            return None                             # not_in_oeisdata
        try:
            decided, bf = bfile.cached(a_number)
        except Exception:
            return None                             # bfile.fetch would raise too: bfile_error
        if not decided:
            return None                             # the attempt's lookup downloads it
        try:
            return entry, bfile.known_terms(entry, bf)
        except bfile.InconsistentTerms:
            return None                             # inconsistent_known_terms

    def _why_not(self, a_number: str) -> str | None:
        gated = self._gated(a_number)
        if gated is None:
            self.undecided += 1
            return None
        entry, known = gated
        plan = pari_plan(self.conn, entry, known, self.budgets)
        if plan.runnable:
            return None
        if self.model:
            # the model stage takes it, or records exactly this skip before trying
            return None if known.count >= config.CODEGEN_MIN_KNOWN_TERMS else "too_few_known_terms"
        return plan.nothing_to_run()[0]

    def summary(self) -> str:
        parts = [f"left out {sum(self.left_out.values())} that could only be skipped ("
                 + ", ".join(f"{c} {r}" for r, c in self.left_out.most_common()) + ")"] if self.left_out else []
        if self.undecided:
            parts.append(f"kept {self.undecided} that only an attempt can check")
        if self.errors:
            parts.append(f"left out {len(self.errors)} whose check failed (first: {self.errors[0]})")
        return "; ".join(parts)


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
            keep = Runnable(conn, budgets, model is not None)
            pool = select.candidates(conn, alpha=alpha, require_langs=None if model else {"pari"}, keep=keep)
            chosen = [c.a_number for c in select.pick(pool, count, random.Random(seed))]
            summary = keep.summary()
            log(f"session {session_id}: picked {len(chosen)} of {len(pool)} candidates (alpha={alpha})"
                + (f"; {summary}" if summary else ""))
        else:
            chosen = a_numbers[:count]
        for a in chosen:
            attempt_sequence(conn, a, budgets, session_id=session_id, log=log, model=model)
    finally:
        db.finish_session(conn, session_id)
    return session_id
