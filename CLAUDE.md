# CLAUDE.md

Guidance for coding agents working in this repository.

**Start here:** `docs/status.md` has the current state, decisions made with the user, open offers and
next steps. Read it before doing anything, and update it before ending a working session. The user
commits the work themselves; do not commit or push unless asked.

**Waiting on the user (2026-09-28), one review.** The project's first win, A385331 a(25)..a(42), sits in
`artifacts/A385331/attempt-139/` with an open `reviews` row at status `new` (`oeisbot review list`).
**Steps 2-7 of the review checklist are done, step 6 included** (item 44; evidence in `data/review1/`),
so do not redo them; **step 7 was re-run 2026-09-28 and still passes** (item 49). What is left is only
what a human may do: **step 8, submitting by hand, and step 9, recording the outcome**, with the material
assembled in `data/review1/SUBMISSION.md`. Nothing has been submitted. Do not close the review, change
its status, submit anything, or re-run A385331 on your own initiative. And **history items 34, 36, 37,
38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53 and 54 are uncommitted** on top of `3dacfb8`,
listed in `docs/status.md`; the user was asked on 2026-09-30 and said "Not yet".

**Session 12 ran on 2026-09-30 (item 52): 25 PARI picks, seed 212, 27 program runs, 0.85 h, 2 verified,
0 new terms, Brier 0.000185 for the per-pick reading against 0.076756 pooled.** Fifteen of seventeen
predictions held outright, the two others on all but one sub-claim; **five of 25 picks were program
misreads** retiring their sequences untested (16% in session 11, 20% here). The method to reuse is
`data/session12/`: `planS12.md` with a critic, a Monte Carlo that *pins* what the page proves, then
`resultsS12.md` audited (16 findings, all held). The offer (a) backfill then re-keyed 48 attempt rows
(`data/offerA/`, backup `data/oeisbot-before-backfill.sqlite3`): `queue` is **3,357 / 1,958
(1432 / 383 / 143)**, `queue --all` **26,745 / 18**, attempts **280**, **567 tests**.

**The dashboard has a Pick map tab (item 54, 2026-10-13):** a treemap whose tile area is a sequence's
chance of being the first pick (`pickmap.chances`) and whose colour is its change since the newest
*different* pool snapshot. Three things bind later work. **The change is measured over the sequences in
both pools** (`pickmap.compare`); a plain `p / p_then` paints every surviving tile the same colour whenever
anything leaves the pool (55 left between the pool before session 12 and now, and 3,355 tiles read "up 2%").
**`pick_snapshots` / `pick_snapshot_rows` are in the live database**, created by `connect()`, so a bare
`db.connect()` aimed at the real file (a test, a mutation run) creates them there: give tests and workers
their own `OEISBOT_HOME` (`pymut.py` does). **Snapshots are written by `run_session` and `oeisbot snapshot`
only**, never by the dashboard, which stays read-only; `data/oeisbot.sqlite3` holds snapshot #1 (3,357 rows,
2026-10-13) and `data/oeisbot-before-pickmap.sqlite3` is the backup taken before it. The map says area is
about 0.9 of the chance and that bands share a scale to within about 2.5x; do not tighten that without
re-running `data/item54/area_spread.ts`.

**Session 11 ran on 2026-09-29 (item 50): 25 PARI picks, 5 verified, 0 new terms, no code changed.** Two
things from it bind later work. **Four picks were program-selection misreads**, each now a dead end
though never really tested, and each is an *open item with a measurement owed*, not a quick fix:
A274003's helper `is_A178751` slips past `pari._ANAME_USE` in **prefix** form (the `\b` before `[Aa]`
never fires after `_`) — and the obvious widening would reject `is_A034293`, a program that verified, so
**do not drop the `\b` without capturing the whole identifier**; A335304's built predicate is a helper
defined beside the real `lista(nn)`; A290024's print loop starts at n = 1 while the emitter numbers from
offset 0, so a **correct** program failed `wrong_term`; and A373945's bulk printer hides every `@T` line
by `print1`-ing on the same stdout line, which `verify.on_line` ignores because the line does not start
with `@` — such a run looks like a plain timeout. Next steps 5, 7, (vi) and (vii). And **the way to plan
a session** is `data/session11/planS11.md`: read every pick's program (`progs.py`), pre-register a
per-pick probability beside the pooled base rate, score both by Brier afterwards (0.0127 vs 0.1467 this
time), and make the cost model use what the page proves — its wall-clock band missed for not doing so.

**Every open decision was answered on 2026-09-30 (item 51), and these now bind.** A `rejected` review
**refuses any later review for the same sequence** (`db.ReviewRefused`, caught inside `record_win`'s
transaction: the win keeps its `extended` row and artifact, the inbox stays empty; reopen the old row
to lift it — never patch around it). A disclaimed PARI program is quoted to the model **under
`codegen.CONJECTURAL_PROGRAMS_NOTE`**, never under "correct"; the wording is the protection, do not
soften it. A callback of ours raising inside the sandbox is `Status.CALLBACK_ERROR` → `harness_error`,
**outside `db.DETERMINISTIC_FAILURES`** — keep it there, a harness bug must never retire a program. An
`infeasible` row carries `extra.infeasible_on` and `db.is_dead_end` compares **only that budget**. A new
term at or below the entry's published bound is **flagged, never refused** (`below_bound`: README,
console, inbox). A gp run's memory figure is judged against **`Harness.stack_cap`**, the `parisizemax`
it is launched with, not the job cap. Definitions are read with **balanced parentheses**
(`pari._def_head`, `_defined_names`) and `_ANAME_USE` captures the **whole identifier** — the
`is_A034293` trap above is closed by design, not by luck. The `iferr` wrap for a predicate valid only
from some k was **declined** (session 12's A138595 then failed exactly so). Sequencing chosen for a
running session: **launch first, edit during, run tests after** the run ends. **The evening's second
round (item 53)**: a print loop is **refused** when an index loop (a plain `for` printing once per
iteration, at parenthesis depth zero of its body) starts off the offset, or a filter loop printing its
own variable starts above the first known term (`pari.loop_start_problem`; refuse, never renumber); a
def whose **only parameter has a default is refused as a bulk printer** (`pari._bulk_printer`); the
over-prediction **kill rules stay as they are** (do not arm the kill on untrusted fits: decided against
with the replay in hand); **Wolfram is deferred**, scoping note in `data/measure0930/wolfram_scoping.md`.
Still open: reading the 15 predicate-beside-`lista` blocks (next step vi).

**Reviews #2 (A162762) and #3 (A162764) were closed as `rejected` on 2026-09-28 (item 49), on the user's
explicit instruction.** They are NOT wins and must never be submitted (item 45): both programs compute
*proved upper bounds* that their own authors call **conjectured to be exact** — the disclaimer is the
first line of each `program.gp` — so the 200 values each produced are conjectural, not verified terms.
**The draw is unaffected**, measured before and after: both pools unchanged at **3,438** and **26,747**,
with the two sequences merely changing gate — `no_supported_program` without `--model`,
`conjectural_program` with it (items 47 and 48). **A162761 is the one sibling that is proved, and it
keeps its candidate** — verified in the same run. **But the close was not free**, and item 49's own
audit caught the overstatement: a `new` review also gates `attempt_sequence` (`attempt.py:460`), so
**`oeisbot attempt A162762 --model` now runs the model** where it used to skip, and `db._insert_review`
has no check against a prior `rejected` row, so such a run could open a new review for the same false
win. Left as a decision, not patched — the nearest fix is the asymmetry item 48 forbids touching; see
next-step (v) in `docs/status.md`. Closing a review remains the user's decision, not a coding agent's:
**do not close review #1, or any future row, without being told to.**

Two questions are **settled and must not be re-opened without new evidence**: the gp version is recorded
(item 43) and **resume is decided against** (item 42 — the argument is in that history item). The offer
about the sequences item 41 un-retired was **recounted (45, not 35) and decided on 2026-09-30**: the
user chose the `program_sha` backfill, run after session 12 (item 52; `data/offerA/`). Item 36 also changed the live
database, which git does not see (backup
`data/oeisbot-before-fit-stats.sqlite3`), and so did session 8 (item 38: 20 attempt rows, 5 prediction
rows, one session row; backup `data/oeisbot-before-session8.sqlite3`) and item 40's end-to-end check
(one attempt row, #176; backup `data/oeisbot-before-searched-bound.sqlite3`). **Items 42, 43 and 44 wrote
no database rows at all**; item 43's two `meta` rows appear at the next `oeisbot setup` or `oeisbot run`.

**A program its author calls conjectural is refused (2026-09-26, item 47).** `pari.conjectural` matches
`conjectur[a-z]*|heuristic[a-z]*|unproved|unproven|not proved` — **letters only, never `\w`**, or digits
from a comment reach `Rejected.reason` (`\\ conjectured86` reported `conjectured86`, and 86 is a known
term of A162762) — **in a comment or string, never in live code**, on
the **raw `%o` part text** — not on a candidate's script, because a disclaimer on the entry's own loop is
dropped with that statement for the function forms. `build_candidates` then refuses **every** form the
part could yield: a disclaimer is about the arithmetic, which all drivers share. The pool went
3,441 → 3,438 (A162763, A349899, A351088); **A162762 and A162764 stay out now that reviews #2 and #3 are
closed** (item 49, 2026-09-28), which is what made closing them safe. **A162761, the one proved sibling, keeps its candidate** —
the pipeline can now tell them apart, which history item 45 said it could not.
The words are deliberately narrow and **measured**: `upper bound`, `lower bound`, `assuming`, `probable`
and `believed` take the corpus count from 7 to 20 and are dominated by false positives (parameters
literally named that). **Do not widen without redoing the measurement** — `tests/test_pari.py` fails if
you do. The rejection reason names the matched **word, never the line**, because a comment could carry a
term value. `codegen._context` also drops a flagged **PARI** block from its "Existing programs (correct,
possibly slow)" list, since that label is a lie for such a program and the model could reproduce it in
Python where no disclaimer survives.

**A conjectural sequence is left out of the `--model` pool too (2026-09-26, item 48).**
`Runnable._why_not` returns `conjectural_program` with the model on as well, keyed on
`pari.rejected_as_conjectural` — **never on the reason text**, which was reworded once while two call
sites went on matching the old wording. **Only the draw is blocked:** `attempt_sequence` has no such
gate, so `oeisbot attempt A162763 --model` still runs the model, and that asymmetry is deliberate and
tested — **do not "fix" it.** It costs 7 sequences (0.03%) against a 26,747 pool; item 48 measured it as
5 of 26,752 before reviews #2 and #3 closed, and both figures are that item's own epoch, not a
disagreement. `conjectural_program` is the one
`left_out` key that is a selection policy rather than the skip an attempt would record.

**Two caveats that must stay in the write-up.** The `_context` filter removes the **program, not the
conjecture** — `entry.comments[:8]` and `entry.formulas[:8]` are still quoted, and A162763's and
A162764's `%F` state the conjecture outright, so never write "the model no longer sees the conjecture".
And the class of programs that are conjectural and say so **nowhere** is undetectable. See
`docs/known-limitations.md#strategies` for all three plus the scope-caveat taxonomy, where performance
caveats ("too slow for n>15") are deliberately *not* counted as misses and **A191363 is named** as the one
wrong-value shape the word list misses — harmless only by an accident of its indexing.

**A `%o` block now yields up to two candidates, and a def must be callable with one argument
(2026-09-25, item 46).** `pari.build_candidates` builds the function form **and** the block's own print
loop, function form first, because the generic drivers scan every index from the start and emit the bare
value while the entry's loop may restrict the domain (`forprime`, `forcomposite`, `forstep`), transform
what it prints (`2*n`, `n^3`) or supply an argument. **There is deliberately no static check deciding
which is right** — one was written and measured **wrong on 5 of the 32 real blocks it was designed
against** — so both are offered and the gate decides. Both carry the same `origin` and differ by
`strategy` and `program_sha`. A `Rejected` is reported only when the *whole block* came to nothing.
`pari._drivable` refuses a def whose parameters after the first lack defaults: **gp does not refuse a
call that omits an argument, it binds the parameter to 0 and runs on**, so such a program silently
computes something else. This removed 20 sequences from the pool and returned 6, A330204 and A366832
among them.

**A term line's counting fields are capped (2026-09-25, item 46).** `verify.MAX_TERM_FIELD_DIGITS` (40)
bounds the index, microseconds, work and bytes of a `@T` line *before* `int()` runs; the term's **value
is exempt** and must stay so. `on_line` runs in the sandbox's stdout reader thread, which has no
exception handler, so an `OverflowError` there killed the drain loop. It does **not** close the quadratic
`int()`/`str()` cost of a huge value, and it widened one hole in invariant 5 — both recorded in
`docs/known-limitations.md#term-lines-from-an-untrusted-program`. Do not "simplify" the cap into the
value field.

**An artifact b-file ends with a blank line (2026-09-28, item 49).** `https://oeis.org/SubmitB.html`
requires it in capitals — *"OTHERWISE THE LAST DATA LINE MAY BE IGNORED"* — and the last data line is
the highest new term, the whole point of the run. The `+ "\n"` is at the **call site** in
`artifact.write`, deliberately **not** in `terms.format_bfile`: the README formats its new-terms block
with the same helper inside a ``` fence whose closing fence sits directly on the helper's trailing
newline. `tests/test_recheck.py` pins both halves and fails if the fix is moved into the helper. Every
artifact written **before** this date lacks the blank line; `data/review1/b385331-submit.txt` is
review #1's corrected copy.

**The searched-bound check is built (2026-09-22, session 9 + item 40; `data/session9/resultsS9.md` is the
measurement, `planBUILD.md` the design).** `oeisbot/bounds.py` reads a published bound out of the entry's
`%C` lines; `verify.Harness._bound_exhausted` skips the extension when it is out of reach at the rate
measured during verification. **Predicate form only** — only there do term values equal the driver's work
count, and `work` is hard-coded to 0 in the other two drivers. It is deliberately **not** a dead end: the
sequence stays in the pool and `extra.verified_scan_to` records how far the run's own scan actually got.
A bound is an **unverified human claim**: it may bound what is worth spending time on and must never
become evidence a term is correct, which is why the check runs *after* verification and why nothing is
ever resumed past a published bound. Its `detail` is deliberately value-free — it reaches the model
through `codegen.slow_program_note`, whose contract is never to carry a term value.

**Predicate scans record where they stopped (2026-09-23, item 41).** `pari.PREDICATE_DRIVER` scans in
blocks sized by time and prints `@P k tested cpu_us` after each; `verify.Harness` accepts a heartbeat
only if it matches the work claimed for it and a rate no predicate can beat, drops the line rather than
halting when it does not, and reports `extra.scan_reached`. The frontier is *reported*, not witnessed:
below `verified_scan_to`, above a published `searched_bound`. It costs about 4% of scan throughput.
**Nothing consumes it, and resuming a scan was decided against** (item 42, by the user, after a critic's
31 findings): it saves no machine time against a larger `--extend-s`, costs 2x on a find, and would
break invariant 10 by scanning past a published bound. Do not build it without new evidence.

**Runtime versions are recorded (2026-09-23, item 43).** `setup_tools.runtime_versions()` probes
`gp --version` (**stderr**, not stdout) and `python -VV`, writing `gp_version` and
`sandbox_python_version` to `meta` at `oeisbot setup` and at every `oeisbot run`, plus a short
`gp=2.17.4/GMP-6.1.2` token in each session's `note` — the half that survives a gp upgrade. A probe that
cannot be trusted records `unknown`; it never raises, because it runs before `run_session`'s own
try/finally. This is the **only** code path that runs a sandbox runtime on the host rather than through
`sandbox.run`; see `docs/sandbox.md#gp-outside-the-sandbox` before adding another.

## What this is

OEISBot finds OEIS sequences with keyword `more`, runs programs (the entry's own PARI/GP code, or Python
from a local model) in a sandbox, verifies every known term, and writes review folders for a human. It
never submits anything to OEIS, and must never be changed to.

Windows-only in practice: the sandbox is a Job Object + AppContainer (`oeisbot/sandbox/windows.py`).

## Commands

```
.venv\Scripts\python -m pytest                 # 567 tests, ~100 s; sandbox tests skip if `oeisbot setup` has not run
.venv\Scripts\python -m pytest tests/test_sandbox.py
.venv\Scripts\oeisbot setup                    # sandbox runtimes + AppContainer grants + database (idempotent)
.venv\Scripts\oeisbot sync --no-pull           # rebuild the candidate table from the local oeisdata clone
.venv\Scripts\oeisbot attempt A123456 --verify-s 60 --extend-s 60   # one sequence, short budgets
.venv\Scripts\oeisbot run -n 5 [--model]       # a session: pick and attempt 5 candidates
.venv\Scripts\oeisbot recheck                  # finish any re-check left pending by an earlier failure
cd dashboard && npm run build                  # frontend; output in oeisbot/dashboard/static (not committed)
```

Installing Python packages behind this machine's TLS inspection needs `UV_SYSTEM_CERTS=1`; npm needs
`NODE_USE_SYSTEM_CA=1`; git needs `git -c http.sslBackend=schannel push` (the system config sets
`openssl`, which fails with "unable to get local issuer certificate"). More in
[operations](docs/operations.md#troubleshooting).

## Where things are

- Flow: `oeisbot/attempt.py` (orchestration) → `strategies/pari.py`, `strategies/codegen.py` →
  `verify.py` (gate) → `sandbox/` → `db.py`, `artifact.py`.
- Ingest: `ingest/oeisdata.py` (mirror + sync), `ingest/bfile.py` (b-files + known terms),
  `ingest/seqfile.py` (entry parser). Selection: `select.py`. Estimation: `estimate.py`.
  Searched bounds published in `%C` comments: `bounds.py`, consumed only by `verify.py`.
- Python program contract and term protocol: `oeisbot/runners/py_runner.py` docstring.
- Local state (never commit): `data/`, `tools/`, `artifacts/`, `oeisbot/dashboard/static/`,
  `dashboard/node_modules/`.

## Rules that must hold

The full list with rationale is in `docs/development.md#invariants`.

- All untrusted code runs through `sandbox.run(..., isolate=True)`. Never add a code path that runs
  entry or model programs outside it.
- oeis.org traffic only through `ingest.bfile.http_get` (rate-limited GETs). Never POST, never submit.
- New terms count only after every known term is reproduced as consecutive (index, value) pairs starting
  at the offset.
- Known terms beyond `codegen.shown_indices` are held out from the model (always at least 2; sequences
  with fewer than 3 known terms never reach the model), and the failure described in a retry prompt never
  carries a held-out value: not the correct one, and not a program value that equals one the prompt does
  not already show, either sign (`describe_failure`). Text the program wrote itself is passed on as it
  is: a crash's error message, the stderr tail, and a line it printed that became a `protocol` stop (see
  `docs/known-limitations.md`).
- Every run is recorded; wins are re-checked against oeis.org before an artifact is written. A run with
  new terms is recorded as `recheck_pending` and saved to `data/pending/` *before* its re-check starts,
  so an interrupted or failed re-check leaves it pending (never published unchecked, never lost).
  `retry_pending_rechecks` must not raise for a single attempt.
- The dashboard is read-only (`db.connect(readonly=True)`).
- Keep `tests/test_sandbox.py` passing. Add a test that attacks any new sandbox guarantee.

## Pitfalls

- Editing files that contain backslashes (GP `\\` comments, Windows paths, regex) through shell heredocs
  or `sed` corrupts escapes. Use a file-editing tool and `python -m py_compile` afterwards.
- AppContainer grants are path-based: after moving the project, run `oeisbot setup`.
- Packages in `tools/python` must be copies, not hard links (`--link-mode copy`), or the sandbox cannot
  read them.
- `gp.exe` commits its whole `parisizemax` at startup; job peak memory for gp is meaningless (the driver
  reports stack size instead).
- There are no database migrations; schema changes need `ALTER TABLE` on existing databases. Because
  `ADD COLUMN` can only append, add new columns at the *end* of the table in `db.SCHEMA` too, so a fresh
  database and an altered one match. `scripts/replay_predictions.py` is the worked example.
- Adding a field to `verify.Prediction`, `AttemptResult`, `Program`, `KnownTerms`, `TermRecord` or
  `Budgets` invalidates every saved win in `data/pending/` (`attempt._checked` compares the field set
  both ways, deliberately). Check that directory is empty and no attempt is `recheck_pending` first,
  or the win can never be re-checked.
- Real timings on this machine are noisy: a term of a few milliseconds can take 0.2-0.4 s more wall time
  than CPU time. Do not assert on sub-second timings in a test; drive the harness in memory with
  controlled times instead, as the harness tests in `tests/test_estimate.py` do.

## Docs

**Numbers in the docs are machine-checked.** `tests/test_docs.py` compares the test total (written out
in eight places), `development.md`'s per-file table and its collected-counts paragraph against what
pytest actually collected; `check_docs.py` does the same for its own expected-hits count. Adding a test
therefore fails the suite until the docs catch up -- deliberately, because these counts drifted three
times in one item. Take the new values from `python -m pytest --collect-only -q`, never by hand.

**Every number that is *not* machine-checked drifts, and item 49's audit (2026-09-28) found a week of
it.** The test totals were the one family that was right, because they are the one family guarded. Wrong
at that point: the real-run totals in three files, frozen at the `id <= 175` snapshot and read as
current for a week (107 sequences / 173 runs / 12.3 h, against 157 / 225 / 14.9 h); both left-out
tallies in `status.md`'s own drift-detection checklist; `data/runs/` at 198 against 247; `artifacts/`
described as one folder when it holds three; and five pieces of local state, two of them **database
backups**, missing from the table a session uses to decide what is safe to delete. **So: when you touch
a count, re-derive it by query or by counting the disk, and when you write a new one, say how you got
it.** A number with no stated method is the one nobody re-checks.

`docs/` describes current behavior precisely. When you change behavior, update the matching page
(`pipeline.md`, `sandbox.md`, `verification-and-estimation.md`, `strategies.md`, `data-and-schema.md`,
`dashboard.md`, `operations.md`) and `docs/known-limitations.md` if you fix or introduce a limitation.
