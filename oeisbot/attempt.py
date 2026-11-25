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

import dataclasses
import json
import random
import sqlite3
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from http.client import HTTPException
from pathlib import Path
from typing import Callable

from . import artifact, bounds, config, db, guard, select
from .config import Budgets
from .ingest import bfile, oeisdata, seqfile
from .ingest.seqfile import Entry, parse
from .model import ModelClient, ModelUnavailable
from .sandbox import RunResult, Status
from .strategies import codegen, pari
from .terms import KnownTerms, Program
from .verify import (AttemptResult, Prediction, ScanTracking, Stop, TermRecord, brief_detail,
                     measured_rate, run_attempt)

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
    # a run of this attempt was stopped on request (verify.Stop.INTERRUPTED), or the request came between
    # two of its programs or model calls: no further program was started, and what is recorded is not
    # the whole attempt. (New terms such a run had already found are still re-checked and reviewed.)
    interrupted: bool = False


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
    return config.DATA / "pending" / f"attempt-{attempt_id}.json"


# A version for the file's shape, and not the real guard against drift -- the field-set check below is,
# and it names what changed; this only refuses a file whose shape is deliberately different, with a
# clearer message than a field list. 2 since 2026-09-21, when `verify.Prediction` gained the cost fit's
# statistics: `data/pending/` was empty and no attempt was `recheck_pending`, so no saved win was lost.
# No format-1 file has ever existed off this machine -- the format itself is not yet committed -- so the
# bump is for the next reader, not for anything on disk. 3 since 2026-09-23, when `AttemptResult` gained
# the predicate scan frontier and its heartbeat counts; `data/pending/` was again empty and no attempt
# was `recheck_pending`, both checked before the field was added
PENDING_FORMAT = 3
# ints a program reports itself, so unbounded: they travel as strings, as they do in the run log
# (Harness._log). That is for readers of the file, not for safety -- reading a term of a few thousand
# digits back needs the digit limit lifted either way, since str->int is capped exactly as json's own
# literal parsing is, and `oeisbot.verify` lifts it at import (sys.set_int_max_str_digits(0))
_BIG_INTS = ("value", "work", "mem", "dwork")


def _fields(obj, *, skip: tuple[str, ...] = (), big: tuple[str, ...] = ()) -> dict:
    """A dataclass instance as plain JSON types, field by field."""
    return {f.name: str(getattr(obj, f.name)) if f.name in big else getattr(obj, f.name)
            for f in dataclasses.fields(obj) if f.name not in skip}


def _checked(cls, saved: dict) -> dict:
    """`saved` with its keys checked against `cls`. Neither side may have a field the other lacks: a
    field added to the dataclass *with a default* would otherwise reload silently as that default, which
    is exactly the kind of drift this format exists to catch."""
    want = {f.name for f in dataclasses.fields(cls)}
    if set(saved) != want:
        raise ValueError(f"{cls.__name__}: saved fields do not match the code (missing "
                         f"{sorted(want - set(saved))}, unexpected {sorted(set(saved) - want)})")
    return dict(saved)


def _dump_pending(result: AttemptResult, entry_name: str, budgets: Budgets) -> bytes:
    """A pending win as JSON rather than a pickle, so a change to any of these classes between the save
    and the re-check cannot make the win unloadable (see docs/known-limitations.md)."""
    return json.dumps({
        "format": PENDING_FORMAT,
        "entry_name": entry_name,
        "budgets": _fields(budgets),
        "result": {
            **_fields(result, skip=("program", "known", "records", "predictions", "run", "stop", "scratch")),
            "stop": result.stop.value,                       # a str Enum dumps as a bare string
            "scratch": str(result.scratch) if result.scratch else None,
            "program": _fields(result.program),              # `script` None vs "" decides `executed`, so `sha`
            "known": {**_fields(result.known, skip=("values",)),
                      # JSON object keys are strings, and the values can be thousands of digits
                      "values": {str(n): str(v) for n, v in result.known.values.items()}},
            "records": [_fields(r, big=_BIG_INTS) for r in result.records],
            "predictions": [_fields(p) for p in result.predictions],
            "run": {**_fields(result.run, skip=("status",)), "status": result.run.status.value},
        },
    }, indent=2).encode("utf-8")      # readable: operations.md sends a human to this file by hand


def _load_pending(data: bytes) -> tuple[AttemptResult, str, Budgets]:
    saved = json.loads(data)
    if saved.get("format") != PENDING_FORMAT:
        raise ValueError(f"pending file format {saved.get('format')!r}, expected {PENDING_FORMAT}")
    r = saved["result"]

    known = _checked(KnownTerms, r["known"])
    known["values"] = {int(n): int(v) for n, v in known["values"].items()}
    records = []
    for rec in r["records"]:
        fields = _checked(TermRecord, rec)
        records.append(TermRecord(**{**fields, **{k: int(fields[k]) for k in _BIG_INTS}}))
    run = _checked(RunResult, r["run"])
    run["status"] = Status(run["status"])

    result = _checked(AttemptResult, r)
    result.update(program=Program(**_checked(Program, r["program"])), known=KnownTerms(**known),
                  stop=Stop(result["stop"]), records=records, run=RunResult(**run),
                  predictions=[Prediction(**_checked(Prediction, p)) for p in r["predictions"]],
                  scratch=Path(result["scratch"]) if result["scratch"] else None)
    return AttemptResult(**result), saved["entry_name"], Budgets(**_checked(Budgets, saved["budgets"]))


def _save_pending(attempt_id: int, result: AttemptResult, entry_name: str, budgets: Budgets) -> None:
    path = pending_path(attempt_id)
    guard.refuse_if_real(path, "saving a pending win")          # never from a test (oeisbot.guard)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(_dump_pending(result, entry_name, budgets))   # bytes: text mode would add CRLF here
    tmp.replace(path)


def _discard_pending(attempt_id: int, log: Callable[[str], None]) -> None:
    try:
        pending_path(attempt_id).unlink(missing_ok=True)
    except OSError as e:     # harmless: nothing reads the file once the attempt is resolved
        log(f"could not delete {pending_path(attempt_id)}: {e}")


def _resolve(conn: sqlite3.Connection, result: AttemptResult, attempt_id: int, entry_name: str, budgets: Budgets,
             still_new: bool, note: str, say: Callable[[str], None] = lambda m: None) -> str | None:
    """Apply a re-check verdict to a `recheck_pending` attempt: artifact folder + review for a win (returns
    its path), `superseded` otherwise. Safe to repeat after an interruption. A win whose sequence already
    has a `rejected` review gets its artifact and its `extended` row but **no review** (`db.record_win`,
    item 51); that is said aloud here, because nothing in the inbox will show it."""
    if not still_new:
        db.set_recheck_result(conn, attempt_id, note, outcome="superseded")
        return None
    folder = artifact.write(result, attempt_id, entry_name, budgets, note)
    rel = str(folder.relative_to(config.ROOT)) if folder.is_relative_to(config.ROOT) else str(folder)
    new = result.new_terms
    if db.record_win(conn, attempt_id, result.known.a_number, rel, new[0].n, new[-1].n, note) is None:
        prior = db.rejected_review(conn, result.known.a_number)
        say(f"review refused: {result.known.a_number} already has a rejected review (#{prior['id']}); the terms "
            f"and the artifact are kept on attempt #{attempt_id}, but nothing was added to the inbox")
    try:
        artifact.mark_complete(folder)
    except OSError:
        pass    # a stray marker in a recorded folder is harmless: only pending attempts' folders are rewritten
    return rel


def _note_failure(conn: sqlite3.Connection, attempt_id: int, row: sqlite3.Row, note: str,
                  say: Callable[[str], None]) -> str:
    """Count this win's failure to resolve, and describe how often it has now failed the same way.

    Only a flag: a pending win is retried for ever, because giving up on one is giving up on new terms,
    and an error that looks permanent (oeis.org unreachable) can simply be a long outage. What this
    removes is the silence -- the log used to repeat one line every session with no hint that it was the
    hundredth time.

    **Never raises**: this runs inside `retry_pending_rechecks`'s own failure handler, so anything
    escaping it would break invariant 7 and, through `run_session`, crash every `oeisbot run` at startup
    on one bad row. `extra` is JSON that a human may have edited by hand (operations.md says how) and can
    be any shape at all -- an array, a string, a number -- or unparseable, so neither the parse nor the
    stored counter may be trusted to have the type it should. A hand-edited counter that *is* a number
    but not a whole one keeps counting as a float rather than restarting; nothing else reads it."""
    times = 1
    try:
        before = json.loads(row["extra"] or "{}")
        times = (before.get("recheck_failures", 0) if before.get("recheck") == note else 0) + 1
    except Exception as e:      # any shape of extra: an array, a string, a number, an unaddable counter
        say(f"could not read the earlier re-check failures ({type(e).__name__}: {e})")
    try:
        db.set_recheck_result(conn, attempt_id, note, failures=times)
    except Exception as e:      # the row is already `recheck_pending`; the win is safe either way
        say(f"could not record the re-check failure ({type(e).__name__}: {e})")
    return f" -- the same way {times} times now" if times > 1 else ""


def retry_pending_rechecks(conn: sqlite3.Connection, log: Callable[[str], None] = print) -> int:
    """Re-check every win left as `recheck_pending`, once each, oldest first. Never raises for a single
    attempt: a failure is logged and the attempt stays pending. Returns how many are still pending."""
    still_pending = 0
    for row in db.pending_rechecks(conn):
        a, attempt_id = row["a_number"], row["id"]
        try:
            result, entry_name, budgets = _load_pending(pending_path(attempt_id).read_bytes())
            new = result.new_terms
            still_new, note = recheck(result.known, new[0].n, {t.n: t.value for t in new})
            log(f"[{a}] attempt #{attempt_id}: re-check: {note}")
            rel = _resolve(conn, result, attempt_id, entry_name, budgets, still_new, note,
                           lambda m: log(f"[{a}] {m}"))
        except Exception as e:
            again = _note_failure(conn, attempt_id, row, f"not done: {type(e).__name__}: {e}",
                                  lambda m: log(f"[{a}] {m}"))
            log(f"[{a}] attempt #{attempt_id}: still pending ({type(e).__name__}: {e}){again}; saved result: "
                f"{pending_path(attempt_id)}; new terms also in the run log named in attempts.extra")
            still_pending += 1
            continue
        if rel:
            log(f"[{a}] artifact: {rel}")
        _discard_pending(attempt_id, lambda m: log(f"[{a}] {m}"))
    return still_pending


class ReleaseRefused(ValueError):
    """`release_pending` was asked to give up on a win it must not, or on a row that is not one."""


def release_pending(conn: sqlite3.Connection, attempt_id: int, log: Callable[[str], None] = print) -> None:
    """Give up on one pending win whose saved result can no longer be read, so its sequence is free again.

    This is the hand-written `UPDATE attempts SET outcome = 'verified'` that operations.md used to
    prescribe, as a command with the checks a person at a SQL prompt does not get. **Never called by the
    pipeline**: a pending win is retried for ever (`_note_failure`), and only a person may decide that
    one is lost. Refused (`ReleaseRefused`, nothing written):

    * a row that is not `recheck_pending` -- there is nothing to release, and `verified` over an
      `extended` row would un-record a win;
    * a win whose saved result **still loads**. Its re-check can still finish -- oeis.org was
      unreachable, or a folder is in the way -- and releasing it would throw new terms away to save a
      wait. `oeisbot recheck` is the command for that one;
    * a saved result that exists and **could not be opened** just now (`OSError` other than a missing
      file: open in an editor, locked by a scanner). That says nothing about whether it still loads.

    The saved file is not deleted: it is renamed `attempt-<id>.released.json`, because a result whose
    fields drifted is still the whole result in readable JSON, and nothing reads that name again. The
    sequence comes back to the draw with the selection penalty a `verified` row carries, as the SQL this
    replaces left it.

    **One window is not closed.** A run records its row as `recheck_pending` a moment before it saves
    the result, so a release typed in that moment, while a session is running, sees no file and
    releases a live win; the run's own re-check then either records the win over the release or leaves
    the row `verified`. Do not release while `oeisbot run` is in progress."""
    row = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        raise ReleaseRefused(f"there is no attempt #{attempt_id}")
    if row["outcome"] != "recheck_pending":
        raise ReleaseRefused(f"attempt #{attempt_id} is not waiting for a re-check (its outcome is "
                             f"{row['outcome']})")
    path = pending_path(attempt_id)
    try:
        data = path.read_bytes()
    except FileNotFoundError as e:
        data, why = None, f"{type(e).__name__}: {e}"
    except OSError as e:
        raise ReleaseRefused(f"attempt #{attempt_id}'s saved result exists and could not be opened "
                             f"({type(e).__name__}: {e}); close whatever has {path} open and try again")
    if data is not None:
        try:
            _load_pending(data)
        except Exception as e:      # not JSON, another format, fields that drifted
            why = f"{type(e).__name__}: {e}"
        else:
            raise ReleaseRefused(f"attempt #{attempt_id}'s saved result still loads, so its re-check can "
                                 f"still finish: run `oeisbot recheck`. Releasing it would discard "
                                 f"{row['new_terms']} new term(s)")
    kept = path.with_name(f"attempt-{attempt_id}.released.json")
    if not db.release_recheck(conn, attempt_id, f"released by hand, saved result unreadable: {why}"):
        raise ReleaseRefused(f"attempt #{attempt_id} stopped waiting for a re-check while this ran")
    a = row["a_number"]
    log(f"[{a}] attempt #{attempt_id} released: the saved result could not be read ({why})")
    try:
        run_log = json.loads(row["extra"] or "{}").get("log")
    except Exception:           # a hand-edited extra of any shape; the release is already done
        run_log = None
    if run_log and Path(run_log).exists():
        where = f"they are in the run log: {run_log}"
    elif run_log:
        where = f"the run log the row names is gone: {run_log}"
    else:
        where = "the row names no run log"
    log(f"[{a}] its {row['new_terms']} new term(s) are not published; {where}")
    if data is not None:
        try:
            path.replace(kept)
            log(f"[{a}] the saved result is kept as {kept}")
        except OSError as e:    # the release is done; the file is only a keepsake
            log(f"[{a}] could not rename {path}: {e}")


class _Attempter:
    def __init__(self, conn: sqlite3.Connection, entry: Entry, known: KnownTerms, budgets: Budgets,
                 session_id: int | None, rep: SequenceReport, say: Callable[[str], None], do_recheck: bool,
                 should_stop: Callable[[], bool] | None = None):
        self.conn, self.entry, self.known, self.budgets = conn, entry, known, budgets
        self.session_id, self.rep, self.say, self.do_recheck = session_id, rep, say, do_recheck
        self.should_stop = should_stop
        # a run found new terms (whatever its re-check then says): stop trying anything else
        self.found_new = False
        # the latest run that reproduced every known term but found no new one: other PARI programs are
        # unlikely to do better cheaply, but a faster model-written program still might
        self.verified: codegen.VerifiedRun | None = None
        # one key for every run row this attempt writes (a skip row has no extra), so the failure penalty counts
        # attempts, not program runs (select.candidates). A uuid: two attempts on one sequence can start within
        # the same second
        self.call = uuid.uuid4().hex

    def run(self, prog: Program, form: str, search_start: int | None = None) -> AttemptResult:
        started = db.now()
        runs = config.DATA / "runs"
        guard.refuse_if_real(runs, "writing a run log")         # never from a test (oeisbot.guard)
        runs.mkdir(parents=True, exist_ok=True)
        log_path = runs / f"{self.known.a_number}-{time.strftime('%Y%m%d-%H%M%S')}-{prog.sha[:8]}.jsonl"
        kept_program = None
        if prog.language == "python":
            # keep every generated program as it ran (with the driver of a members(work) program), byte for
            # byte, so its sha256 prefix is the recorded program_sha (text mode would write CRLF on Windows)
            kept_program = runs / f"{log_path.stem}.py"
            kept_program.write_bytes(prog.executed.encode("utf-8"))
        # A published searched bound is only usable for the predicate form. There the driver tests
        # k = search_start, search_start + 1, ... so the term values ARE the work count; for a(n) and
        # print-loop the loop variable need not be the term value at all (A038582's terms are k,
        # A038583's are the sums of the very same search), and `work` is hard-coded to 0 in both of
        # those drivers, so there would be no rate to compare against either.
        bound = None
        scan = None
        if form == "predicate":
            bound = bounds.applicable(self.entry.comments, self.entry.a_number,
                                      self.known.values[self.known.last_index], self.known.last_index + 1)
            # the same caller gate as the bound, for the same reason: only this driver tests every k in
            # order, so only here does a progress heartbeat mean what the harness reads it as
            if search_start is not None:
                scan = ScanTracking(search_start, pari.PREDICATE_MAX_RATE)
        self.say(f"running {prog.strategy} from {prog.origin}")
        result = run_attempt(prog, self.known, self.budgets, name=self.entry.name, log_path=log_path,
                             searched_bound=bound, scan=scan, should_stop=self.should_stop)
        if result.stop is Stop.INTERRUPTED:
            self.rep.interrupted = True
        new = result.new_terms
        self.say(f"-> {result.outcome}: {result.stop.value} ({brief_detail(result.detail)}); reproduced "
                 f"{result.reproduced}/{self.known.count}, {len(new)} new, {result.run.wall_s:.1f} s, "
                 f"peak {result.peak_mem_bytes / 2**20:.0f} MiB")
        extra = {"form": form, "rewrites": prog.notes, "attempt_call": self.call,
                 "weak_verification": result.weak_verification,
                 # the budgets a verified run without new terms is judged against (db.is_dead_end).
                 # mem_bytes is what was asked for and is recorded but no longer read; mem_cap_bytes is
                 # the cap the feasibility check was actually judged against, smaller when free RAM held
                 # the harness below the budget, so it -- not mem_bytes -- keys the infeasible dead end
                 "extend_wall_s": self.budgets.extend_wall_s, "mem_bytes": self.budgets.mem_bytes,
                 "mem_cap_bytes": result.mem_cap,
                 # recorded since item 58 and read by nothing in the pipeline: `verify_timeout` is keyed on
                 # the measured runtime, not on this. It is here so a row says what it was run under --
                 # sessions 7 to 12 ran at budgets no row and no session note recorded in full
                 "verify_wall_s": self.budgets.verify_wall_s}
        if result.stop is Stop.INFEASIBLE:
            # which budget the verdict was reached on, so db.is_dead_end asks about that one (item 51)
            extra["infeasible_on"] = "+".join(result.infeasible_on) or "unknown"
        if result.below_bound:
            b = result.below_bound
            extra["below_published_bound"] = b
            self.say(f"WARNING: new term(s) a({'), a('.join(map(str, b['indices']))}) lie at or below the "
                     f"published bound {b['bound']}: either that search or this program is wrong (see the README)")
        # the harness creates the term log with the first term, so a run that produced none has no log to
        # name and naming one anyway sends a reader to a file that was never written. The kept program is
        # written whatever the run then does, so it is named on its own
        if log_path.exists():
            extra["log"] = str(log_path)
        if kept_program is not None:
            extra["program"] = str(kept_program)
        if bound is not None:
            # A string: entries publish bounds as large as 10^5000 (A069575) and SQLite integers stop at
            # 2^63. Written on every predicate run that has one, whether or not the check fired, so a
            # reader can see what was weighed. Of the DB columns, codegen reads back only failure_mode
            # and detail, never extra -- so keeping the quote here keeps it out of a later session's
            # replay of this row into slow_program_note, which is the path that carries no comments of
            # its own. (The model's own prompt already shows entry.comments[:8] directly.)
            extra["searched_bound"] = str(bound.value)
            extra["searched_bound_quote"] = bound.quote
            extra["searched_bound_margin"] = config.SEARCHED_BOUND_MARGIN
        if result.scan_reached is not None:
            # A string like `searched_bound`: a predicate scan can pass 2^63 in a long run, and SQLite
            # integers cannot. Distinct from `verified_scan_to` below on purpose -- see that comment
            extra["scan_reached"] = str(result.scan_reached)
        if result.heartbeats or result.heartbeats_ignored:
            extra["heartbeats"] = result.heartbeats
            if result.heartbeats_ignored:
                # a driver bug that mangles every line would otherwise be silence: the frontier simply
                # never advances and no row says why
                extra["heartbeats_ignored"] = result.heartbeats_ignored
                extra["first_bad_heartbeat"] = result.first_bad_heartbeat
        if result.stop is Stop.SEARCHED_BOUND:
            if (rate := measured_rate(result.records)) is not None:   # the call the decision was made with
                extra["measured_rate"], extra["rate_window_s"], extra["rate_work"] = rate
            # Where the scan actually reached. Recorded, and deliberately consumed by NOTHING: resume
            # was decided against on 2026-09-23 (history item 42) -- do not build it without new evidence.
            # THREE things, named apart on purpose, in decreasing order of how much they are worth:
            # `verified_scan_to` is *ours and witnessed* -- the driver tested every k up to it and the
            # harness watched every one of the known terms arrive from that range. `scan_reached` above
            # is ours and *reported*: the driver's own heartbeat, cross-checked against the work it
            # claims and the fastest rate a predicate can be tested at, but still the program's word.
            # `searched_bound` is the entry's unverified human claim; resuming past that would make a
            # later term's *index* depend on the claim, which is exactly what a bound must never be used
            # for. Recording all three, distinguished, is the whole point.
            extra["verified_scan_to"] = str(self.known.values[self.known.last_index])
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
                db.set_recheck_result(self.conn, attempt_id, f"not done: {type(e).__name__}: {e}", failures=1)
                self.say(f"re-check failed ({type(e).__name__}: {e}); {kept}")
                return result
        else:
            still_new, note = True, "skipped"
        self.say(f"re-check: {note}")
        try:
            rel = _resolve(self.conn, result, attempt_id, self.entry.name, self.budgets, still_new, note, self.say)
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
                     model: ModelClient | None = None,
                     should_stop: Callable[[], bool] | None = None) -> SequenceReport:
    """`should_stop`, when given, is asked on every tick of every run, before each program, before the
    model stage, and inside it before each model call and each run: True ends the run in hand as `interrupted`
    (verify.Stop.INTERRUPTED, which retires nothing) and starts no further program. New terms found
    before the stop still go through the re-check and the review, as any others do, so a stop can take
    as long as a re-check does. `rep.interrupted` says it happened. It is not asked during the gates
    (entry, b-file, known terms), which make at most one request.

    `should_stop` runs four times a second on the sandbox's own watchdog loop, with the lock the output
    reader needs: it must be cheap and must not block or do I/O. If it raises inside a run the run is a
    `harness_error`, which is not a dead end but is a `failed` row, and so counts in the failure penalty."""
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

    runner = _Attempter(conn, entry, known, budgets, session_id, rep, say, do_recheck, should_stop)
    plan = pari_plan(conn, entry, known, budgets)
    for r in plan.rejected:
        say(f"PARI block {r.block}: {r.reason}")
    for cand, dead in plan.dead_ends:
        why = {"extend_budget": "verified before and found nothing new in no less time",
               "infeasible": "verified before and judged the next term infeasible with no more of the budget it ran out of",
               }.get(dead["failure_mode"], "failed the same way before")
        say(f"{cand.program.origin} ({cand.form}): {why} (attempt #{dead['id']}: {dead['failure_mode']})")
    for cand, why in plan.out_of_reach:
        say(f"{cand.program.origin} ({cand.form}): not run: {why}")
    tried = 0
    for cand in plan.runnable:
        if tried >= max_programs or runner.found_new or runner.verified is not None or rep.interrupted:
            break
        if should_stop is not None and should_stop():
            rep.interrupted = True
            break
        tried += 1
        runner.run(cand.program, cand.form, cand.search_start)

    use_model = not runner.found_new and model is not None
    # Asked once more after the loop, but only if the model stage would otherwise start. The loop ends
    # without asking when the last program finished by itself or there was none to run, and the stage
    # would then begin with a stop pending (found by item 58's review: a model call, and a run killed on
    # its first tick). With no model stage to hold back the attempt is already complete, and it is
    # recorded as what it is
    if use_model and not rep.interrupted and should_stop is not None and should_stop():
        rep.interrupted = True
    if rep.interrupted:
        # Stopped with programs still unrun. Not the model stage: it would start new runs. And not the
        # skip below when nothing ran at all: its reason would say the sequence had nothing to run, when
        # its programs or the model were simply not started. No row is the honest record of that
        say("stopped on request; no further program was started")
        return rep

    if use_model:
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
                                                  log=say, verified_elsewhere=verified, should_stop=should_stop)
        except ModelUnavailable as e:
            say(f"model unavailable: {e}")
            if should_stop is not None and should_stop():
                # the model server went away in the same shutdown: not "no model", a stage cut short
                rep.interrupted = True
                say("stopped on request; no further program was started")
                return rep
        else:
            if outcome.stopped or rep.interrupted:
                # the stop came during the model stage. Whatever ran is recorded; a skip row saying the
                # model produced nothing runnable, or judged the sequence infeasible, is not written for
                # a stage that was cut short
                rep.interrupted = True
                say("stopped on request; no further program was started")
                return rep
            if outcome.skipped:
                return skip("model_skip", outcome.skipped, strategy="python:model")
            if not outcome.attempts:
                return skip("model_no_runnable_code", "; ".join(outcome.rejected), strategy="python:model")
            tried += len(outcome.attempts)

    if tried == 0:
        return skip(*plan.nothing_to_run())
    return rep


def offline_known_terms(a_number: str) -> tuple[Entry, KnownTerms] | None:
    """The entry and its known terms as an attempt would get them, decided without a request; None where
    an attempt's gates would record a skip, or only a download could tell (see `Runnable`)."""
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


class Runnable:
    """A `select.candidates` keep-check that leaves out sequences an attempt could only skip: a PARI-bearing
    sequence whose programs are all unsupported, known dead ends or out of reach of the verify budget, unless
    the model could take it. It runs the attempt's own `pari_plan` on the known terms the attempt would use,
    and never makes a request.

    Where the attempt's gates would record a skip -- entry missing, b-file not decidable offline (the
    attempt's lookup may download it, or record `bfile_error`), known terms inconsistent -- the row is kept
    and the attempt records what happens. An error the attempt has no gate for would stop the session, so
    such a row is left out and reported instead.

    `left_out` keys are the skip reason an attempt would record, with ONE deliberate exception:
    `conjectural_program` is a *selection policy*, not a prediction. `attempt_sequence` has no matching
    gate, so a targeted `oeisbot attempt A... --model` still runs the model on such a sequence and
    records whatever happens; only the random draw is blocked (item 48). Do not "fix" the asymmetry by
    adding the gate to `attempt_sequence` -- being able to run one deliberately is the reason this was
    acceptable at all."""

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
        return offline_known_terms(a_number)

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
            # A conjectural entry program is not an opportunity for the model, it is a trap. The model
            # is shown the entry's own `%C`/`%F`, which state the conjecture outright, and a Python
            # re-derivation of a conjectured closed form reproduces every known term by construction --
            # so verification cannot tell it from a real result, which is exactly how session 10
            # produced 200 values twice. Refusing the entry's PARI program does not cover this on its
            # own, because the model writes its own program and is kept for that (item 48).
            #
            # This is the ONE key here that is a selection policy rather than the skip an attempt would
            # record: `attempt_sequence` has no such gate, so a targeted `oeisbot attempt A... --model`
            # deliberately still runs the model. Only the random draw is blocked. That is the whole
            # trade -- a hard stop on selection, where a prompt could only ask -- and it costs 7
            # sequences of 26,752 (0.03%), measured 2026-09-26.
            if pari.rejected_as_conjectural(plan.rejected):
                return "conjectural_program"
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


def pool_name(model: bool) -> str:
    """The name a pool goes by in `pick_snapshots.pool`: `oeisbot run` draws from 'pari', `run --model` from 'model'."""
    return "model" if model else "pari"


def session_pool(conn: sqlite3.Connection, budgets: Budgets, *, model: bool,
                 alpha: float = 1.0) -> tuple[list[select.Candidate], Runnable]:
    """The pool a session draws from, and the `Runnable` that built it (its `summary()` says what it left
    out). `run_session`, `oeisbot queue` / `pick` / `snapshot` and the dashboard's Pick map all call this,
    so what they show is what a session would pick from: PARI-bearing sequences only, or with `model`
    every sequence the model could attempt."""
    keep = Runnable(conn, budgets, model)
    return select.candidates(conn, alpha=alpha, require_langs=None if model else {"pari"}, keep=keep), keep


def budgets_json(budgets: Budgets) -> str:
    """The budgets a pool was built under, as stored in `pick_snapshots.budgets`: sorted keys, so equal budgets
    are equal strings."""
    return json.dumps(dataclasses.asdict(budgets), sort_keys=True)


def budgets_of(header) -> Budgets:
    """The budgets a snapshot was built under (its `pick_snapshots.budgets`), or the defaults when there is no
    snapshot, it has none, or they do not parse. `oeisbot sync` and the dashboard both build "the pool as the
    newest snapshot saw it" from this, so the two cannot disagree about what that means."""
    try:
        return Budgets(**json.loads(header["budgets"]))
    except (TypeError, ValueError):
        return config.DEFAULT_BUDGETS


def rules_fingerprint() -> str:
    """A short hash of the code that decides which sequences are in a pool: the `Runnable` gates and the
    plan they build (`PariPlan`, `pari_plan`), the dead-end test, the entry and b-file readers they call,
    the three modules `select`, `pari` and `seqfile` (what counts as a usable program, what is refused as
    conjectural, how an entry is parsed), and the constants that retire a program or gate the model.
    Stored with each snapshot so the Pick map can say "the rules changed since" instead of presenting
    every sequence the new rules dropped as something that happened to it. Line endings are normalised
    first, so a checkout that converts CRLF to LF does not change it. 'unknown' if the sources cannot be
    read (a frozen install); never raises."""
    import hashlib
    import inspect

    def text(raw: bytes) -> bytes:
        return raw.replace(b"\r\n", b"\n")

    try:
        h = hashlib.sha256()
        for obj in (Runnable, offline_known_terms, PariPlan, pari_plan, db.is_dead_end, oeisdata.load_entry,
                    bfile.cached, bfile.known_terms):
            h.update(text(inspect.getsource(obj).encode()))
        for mod in (select, pari, seqfile):
            h.update(text(Path(mod.__file__).read_bytes()))
        h.update(repr((db.DETERMINISTIC_FAILURES, db.OPEN_REVIEW_STATUSES, db.EXTEND_DEAD_END_MIN_CPU_SHARE,
                       config.CODEGEN_MIN_KNOWN_TERMS, db.INTERRUPTED)).encode())
        return h.hexdigest()[:12]
    except (OSError, TypeError):
        return "unknown"


def record_snapshot(conn: sqlite3.Connection, pool: list[select.Candidate], *, model: bool, budgets: Budgets,
                    session_id: int | None = None) -> int | None:
    """Store `pool` as a pick-chance snapshot (`db.record_pick_snapshot`) under `budgets` and the current
    rules. Returns the snapshot id, or None when the newest snapshot already holds exactly this pool."""
    return db.record_pick_snapshot(conn, pool_name(model), [(c.a_number, c.difficulty) for c in pool],
                                   session_id=session_id, budgets=budgets_json(budgets), rules=rules_fingerprint())


def snapshot_pool(conn: sqlite3.Connection, pool: list[select.Candidate], *, model: bool, budgets: Budgets,
                  session_id: int | None = None, log: Callable[[str], None] = print) -> int | None:
    """`record_snapshot` that never raises: a snapshot is a record for the Pick map, and a session that
    cannot write one must still run. Returns the snapshot id, or None when nothing changed since the last
    one or the write failed (the log says which)."""
    try:
        return record_snapshot(conn, pool, model=model, budgets=budgets, session_id=session_id)
    except Exception as e:     # noqa: BLE001 -- see the docstring
        log(f"pick snapshot not recorded: {type(e).__name__}: {e}")
        return None


def snapshot_after_sync(conn: sqlite3.Connection, log: Callable[[str], None] = print) -> int | None:
    """Record the PARI pool as a snapshot once `oeisbot sync` has changed the data it is built from, so the Pick
    map has something to compare with when entries change between sessions. Never raises: a sync that has
    pulled and parsed everything must not fail because the map's record could not be written.

    It stores nothing when the pool is the one the newest snapshot holds, which is what a sync that changed
    nothing produces. The pool is built under the budgets of the newest PARI snapshot (the defaults when there
    is none), as the dashboard builds its own, so what differs between two snapshots is what happened and not a
    change of budget; the model pool is left alone (building it takes about half a minute). The rules recorded
    are those of the code on disk, which is the code that just built the pool. Returns the snapshot id, or None
    when nothing was stored.

    A pool whose check failed for some sequences is not stored: they would be missing for a reason that has
    nothing to do with the sequences, and the map would show them as arrivals in the next snapshot. A session
    records such a pool anyway, because it drew from it; a sync's snapshot is only a record."""
    try:
        headers = db.pick_snapshot_headers(conn, "pari")
        budgets = budgets_of(headers[0] if headers else None)
        pool, keep = session_pool(conn, budgets, model=False)
        if keep.errors:
            log(f"pick snapshot not recorded: the check failed for {len(keep.errors)} (first: {keep.errors[0]})")
            return None
        sid = record_snapshot(conn, pool, model=False, budgets=budgets)
    except Exception as e:     # noqa: BLE001 -- see the docstring
        log(f"pick snapshot not recorded: {type(e).__name__}: {e}")
        return None
    log(f"pick snapshot #{sid} stored ({len(pool)} candidates)" if sid is not None
        else f"pick snapshot unchanged ({len(pool)} candidates)")
    return sid


def run_session(conn: sqlite3.Connection, count: int, budgets: Budgets = config.DEFAULT_BUDGETS, *,
                alpha: float = 1.0, seed: int | None = None, log: Callable[[str], None] = print,
                a_numbers: list[str] | None = None, model: ModelClient | None = None,
                note: str = "", keep: Callable[[select.Candidate], bool] | None = None,
                before_attempt: Callable[[str], None] | None = None,
                may_start: Callable[[], bool] | None = None,
                should_stop: Callable[[], bool] | None = None, snapshot: bool = True) -> int:
    """One session: pick up to `count` sequences and attempt each. Returns the session id.

    The last six arguments are for a caller that runs sessions unattended (`oeisbot daemon`, item 58).
    Left at their defaults they change nothing but the session note, which now names the budgets:

    * `note` is appended to the session's note (the daemon names itself and its tier).
    * `keep(candidate)` is asked about every candidate of the pool, and one it refuses is not drawn. The
      snapshot stored for the Pick map is still the **whole** pool: what `keep` leaves out is the
      caller's own reason of the moment (a cooldown), not something that happened to the sequence, and
      the map would otherwise show it leaving and coming back. Ignored with `a_numbers`: a caller that
      names its own picks has already chosen.
    * `snapshot=False` stores no Pick-map snapshot. The dashboard builds its live pool under the newest
      snapshot's budgets, so a caller that runs sessions at several budgets in one night passes it for
      all but one of them; otherwise the map would compare pools built under different budgets.
    * `before_attempt(a_number)` is called before each pick starts. Whatever it raises is logged and
      ignored: it reports progress, and a reporting fault must not cost a pick.
    * `may_start()` is asked before each pick; False ends the session with the remaining picks unrun
      (the caller's window is too short for another). `should_stop()` is asked there too, first, and on
      every tick of every run: True also interrupts the run in hand (`attempt_sequence`, which says what
      the callback must not do). What either raises in the pick loop ends the session through the
      `finally` below, session row closed. Neither is asked before the session's own start-up (pending
      re-checks, the pool, the snapshot): a caller that is already stopping should not start a session."""
    requested, count = count, min(count, budgets.session_attempt_cap)
    # Which gp produced this session's rows. `meta` alone would not answer it: it is overwritten the next
    # time gp changes, so after an upgrade it describes no historical row at all, while a note is written
    # once and never touched again (`db.finish_session` leaves it alone). Refreshed here as well as at
    # `oeisbot setup`, so an upgrade between the two is still recorded, and written as one transaction.
    # Imported inside the function only to match how `cli` imports `setup_tools` -- it buys nothing here,
    # since `ingest.bfile` already pulls `urllib.request` in at module level and this import runs on
    # every session anyway. `runtime_versions` never raises -- it must not, because this runs *before*
    # `start_session` and before the try/finally below, so an exception would kill `oeisbot run` having
    # done nothing at all, not even leaving a session row behind
    from .setup_tools import gp_session_token, runtime_versions

    versions = runtime_versions()
    db.set_meta_many(conn, versions)
    # The budgets are in the note since item 58. Sessions 7 to 12 all ran with a 30-minute extension and
    # nothing but each attempt row's `extra` said so, which is how a plan came to be costed at the 3-hour
    # default they never used
    session_id = db.start_session(conn, note=f"count={count} alpha={alpha} seed={seed} "
                                             f"model={getattr(model, 'name', None)} "
                                             f"verify_s={budgets.verify_wall_s:g} extend_s={budgets.extend_wall_s:g} "
                                             f"{gp_session_token(versions['gp_version'])}"
                                             + (f" {note}" if note else ""))
    try:
        if requested > count:
            log(f"session {session_id}: asked for {requested}, capped at {count} "
                f"(budgets.session_attempt_cap)")
        if db.pending_rechecks(conn):
            left = retry_pending_rechecks(conn, log)
            log(f"session {session_id}: {left} win(s) still waiting for a re-check" if left else
                f"session {session_id}: pending re-checks resolved")
        if a_numbers is None:
            pool, runnable = session_pool(conn, budgets, model=model is not None, alpha=alpha)
            drawable = pool if keep is None else [c for c in pool if keep(c)]
            chosen = [c.a_number for c in select.pick(drawable, count, random.Random(seed))]
            summary = runnable.summary()
            held = len(pool) - len(drawable)
            log(f"session {session_id}: picked {len(chosen)} of {len(drawable)} candidates (alpha={alpha})"
                + (f"; {held} more held back by the caller" if held else "")
                + (f"; {summary}" if summary else ""))
            # after the "picked" line, which callers and tests read as the session's first line of output;
            # before any program runs, so the snapshot is the pool the picks were drawn from
            if snapshot:
                snapshot_pool(conn, pool, model=model is not None, budgets=budgets, session_id=session_id, log=log)
        else:
            chosen = a_numbers[:count]
        for done, a in enumerate(chosen):
            why = ("a stop was requested" if should_stop is not None and should_stop() else
                   "the caller will not start another" if may_start is not None and not may_start() else None)
            if why is not None:
                log(f"session {session_id}: stopping before {a}, with {len(chosen) - done} of {len(chosen)} "
                    f"picks not started: {why}")
                break
            if before_attempt is not None:
                try:
                    before_attempt(a)
                except Exception as e:      # noqa: BLE001 -- see the docstring
                    log(f"session {session_id}: before_attempt failed ({type(e).__name__}: {e}); going on")
            rep = attempt_sequence(conn, a, budgets, session_id=session_id, log=log, model=model,
                                   should_stop=should_stop)
            if rep.interrupted:
                log(f"session {session_id}: stopped during {a}, with {len(chosen) - done - 1} of "
                    f"{len(chosen)} picks not started")
                break
    finally:
        db.finish_session(conn, session_id)
    return session_id
