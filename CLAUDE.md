# CLAUDE.md

Guidance for coding agents working in this repository.

**Start here:** `docs/status.md` has the current state, decisions made with the user, open offers and
next steps. Read it before doing anything, and update it before ending a working session. The user
commits the work themselves; do not commit or push unless asked. **The resume point is its first
section, "Resume here (2026-11-23)"**: what is built and uncommitted, what must not be done unasked,
the user's own next steps in order with the command for each, Part B's decisions, where the record
is, and the read-only commands that check the state on arrival. Read that section first.

**Waiting on the user (2026-09-28), one review.** The project's first win, A385331 a(25)..a(42), sits in
`artifacts/A385331/attempt-139/` with an open `reviews` row at status `new` (`oeisbot review list`).
**Steps 2-7 of the review checklist are done, step 6 included** (item 44; evidence in `data/review1/`),
so do not redo them; **step 7 was re-run 2026-09-28 and still passes** (item 49). What is left is only
what a human may do: **step 8, submitting by hand, and step 9, recording the outcome**, with the material
assembled in `data/review1/SUBMISSION.md`. Nothing has been submitted. Do not close the review, change
its status, submit anything, or re-run A385331 on your own initiative. **History items 34 and 36 to 54 are
committed and pushed as `f0081d9`** (2026-10-14, on the user's "Commit and push"; `origin/main`,
what it holds is in `docs/status.md#what-is-committed`). That answer covered the work to item 54 only:
anything built after it still waits for its own request to commit. **Item 55 (the Pick map's loose ends) is
commit `a6ae951`, pushed, and `origin/main`** (2026-11-18, on the user's "Commit item 55 first", which included
the push). **Item 56 (the dashboard
defect sweep, 2026-11-17 and 18) is commit `31d5b7e`, pushed, and `origin/main`** (2026-11-18, on the user's
"Commit and push first"; the evidence is in `data/item56/`). **Item 57 (the tie-up of the open roadmap items,
2026-11-18) is built, audited and uncommitted** (`git status` lists it; the evidence is in `data/item57/`).
**Item 58, Part A (`oeisbot daemon`: sessions unattended in a nightly window, with the writers' lock, the
stop hooks and three selection-rule changes; 2026-11-22 and 23) is built, reviewed slice by slice and
uncommitted on top of it** (evidence in `data/item58/`, `final_audit.md` and then `safeguards.md` last; reference in `docs/daemon.md`),
**with its section F, the safeguards the user asked for on 2026-11-23** (arming, `oeisbot/guard.py`, the harness's own check); 903 tests
pass with both items in the tree (whole suite run 2026-11-23, the 3 documentation guards included). Anything built after a commit still waits for its own request.

**Item 58: what is and is not done (2026-11-23).** The user asked for the project to run continuously
and for submission to be automated, then ruled automated submission out ("It is against policy for
automated submissions and programs you do not understand"): **invariant 1, "Nothing submits", is
unchanged, and nothing may automate a submission.** Decided by the user: sync-driven picks and a budget
ladder, no model pool; idle hours only, window 22:00 to 08:00, the task may wake the machine; the daemon
first (Part A, built), then a dashboard "To submit" page (**Part B, decided and NOT built**: narrow
writes for review status, a Submit button that only opens oeis.org beside copy buttons, the user closes
reviews; plan in `data/item58/plan.md`). **Not done, and not to be done unasked:** the daemon has never
been run against the real project **and is NOT ARMED** (a start does nothing until the user runs
`oeisbot daemon --arm`); `oeisbot sync` has not been run since 2026-09-17 and should be run
once by hand, by the user, before the first unattended night; the scheduled task has not been imported
(`oeisbot daemon --task-xml FILE` only writes the definition; **nothing in the project registers a scheduled task, and
you must not either**); the dashboard's daemon line has not been seen in a browser; the user has no
OEIS account name yet (their TODO). Do not start the daemon, a sync or a session on your own initiative.
The user's steps in order, with commands, are in `docs/status.md`, "The user's next steps, in order".

**The safeguards (item 58, section F, 2026-11-23): what binds.** They exist because tests of item 58
reached the real project three times in two days (a real `git fetch`; a real `data/daemon/stop`
written by a mutant of the guard itself; the real database opened for writing by a draft test; no row
changed in any). **Never arm the daemon**: `oeisbot daemon --arm` (and `daemon.arm()`, and creating
`data/daemon/armed` by any other means) is the user's alone, like closing a review; unarmed, every
start logs one line and exits 2, and `Daemon.run` raises `NotArmed` (a refusal, exit 2, never a fault). **Never bypass `oeisbot/guard.py`
or the wall in `tests/conftest.py`**: do not remove a `guard.refuse_*` call, and in a test never
delete `PYTEST_CURRENT_TEST` or `OEISBOT_UNDER_TEST` from the environment or replace
`guard.REAL_DIRS` (only `tests/test_guard.py` may, to test the guard). **A test of a safeguard is
never aimed at the real project**: declare a temporary directory real and point every path there
(`test_guard.py`'s `fake_real`), stub the dangerous step first where there is no path to redirect,
and always give `real_connect` a path. **A new write under `data/` or `artifacts/` gets a
`guard.refuse_if_real` call before it** (15 today; table in `docs/development.md`, "The product's own
guard"). **In any experiment script set `OEISBOT_UNDER_TEST=1` and a fresh `OEISBOT_HOME` before
importing `oeisbot`.** **`data/item58/mutate.py` runs alone and only when the user asks**: it changes
the working tree, stops if the real project changes, and if killed leaves `MUTANT_IN_TREE.json` at the
root, which stops pytest, the harness and the daemon until the file it names is restored from its
`.orig` copy. **After any agent, harness or mutation run, verify the real project by looking**
(read-only): the database's size, time and counts (6,791,168 bytes, 2026-10-13 21:30, no `-wal` or an empty one;
280 attempts, 12 sessions, 3 reviews, 456 predictions, 1 snapshot), no `data/daemon/` and no
`data/writer.lock` (until the user creates them), no `*.lock` in `data/oeisdata/.git`, no
`MUTANT_IN_TREE.json`; the commands are in `docs/status.md`, "Checking the state on arrival". What
the safeguards do not cover: `docs/known-limitations.md`, "The safeguards against reaching the real
project". All four mutation sets were run clean on 2026-11-23 under the harness as it now is (29, 16,
107 and 44 mutants, 196, none surviving; `data/item58/mutation_slice1.txt` to `4`). **The one snapshot
that holds everything, the 14 untracked files included, is `refs/item58/complete`** (check it with
`git for-each-ref refs/item58/complete`); the older `refs/item58/*` hold tracked files only.

**After item 58: what binds.** **`interrupted` (`verify.Stop.INTERRUPTED`, `db.INTERRUPTED`) must stay
outside every dead-end rule, outside `db.DETERMINISTIC_FAILURES`, outside the failure penalty
(`select.candidates`) and uncooled** (`daemon.Cooldown`): the daemon stops runs every night for the
clock's reasons, and a row that counted would wear down its own pool. **Never add a `Budgets` field for
a tier**: a tier is `replace(DEFAULT_BUDGETS, verify_wall_s, extend_wall_s)` (`daemon.Tier.budgets`),
and a new field strands every saved win in `data/pending/`. **The cooldown judges a row only at budgets
no larger than the row's own** (`extra.verify_wall_s` / `extend_wall_s`); the first version did not and
emptied every tier above the first. **A `verify_timeout` is a dead end only with CPU time of at least
80% of the verify budget asked now** (`db.is_dead_end`), not of its own wall time: the second form let
two sequences with 288 s and 474 s of CPU back into the 60 s pool. **A sequence with a `rejected`
review is not drawn** (`select.candidates`), so every review status now keeps a sequence out of the
draw; only the draw, a targeted `oeisbot attempt` still runs it. **`Harness.on_line` reads nothing
after a halt** except the driver's contract error. **The daemon and the commands in `cli.LOCKED`
(`run`, `attempt`, `sync`, `recheck`, `fetch-bfiles`, `setup`, `snapshot`) share one writers' lock**
(`oeisbot/lock.py`, an OS lock on `data/writer.lock`; the file's contents decide nothing): **a new
command must be classified**, in `LOCKED` or in `tests/test_lock.py`'s `UNLOCKED_COMMANDS`, and a
script that calls the library directly must take `lock.writer` itself. **Tests never reach the real
database, mirror or network**: the autouse wall in `tests/conftest.py` raises `ReachedTheRealProject`,
and it exists because on 2026-11-22 a reviewer's mutant started a real daemon night from a test (a real
`git fetch` ran; a stale `index.lock` was left in the mirror and removed; the database was not
changed). **Do not bypass or weaken the wall**, and remember `data/item58/mutate.py` mutates the working
tree itself: nothing else may read, run or edit the code while it runs. **`dashboard/src/daemonline.ts`
joins the modules with no imports**, and `/api/daemon` must go on writing nothing (`lock.held` creates
no file). **A session that raises is charged to `Daemon.in_hand`, never to the heartbeat's
`a_number`** (the rework's one bug: an innocent finished sequence got the `daemon_error` skip). **Only
`--stop`, the window's end and Ctrl-C are graceful**; every other ending is a kill, and recovery at the
next start is the design, not an accident. **How old the mirror is comes from `meta.pulled_at`**
(`daemon.pulled_at`; written only by a sync that pulled), not from `synced_at`, which `sync --no-pull`
moves too; `synced_at` is read only while the key is absent, as it is in the live database until the
first pull. **The sync's repair removes the mirror's `index.lock` only after its own reset was ended by
the time limit** (`oeisdata.update`, `GitTimeout`); a reset git refused leaves the lock, the repair
fails on it, and `MirrorUnusable` costs that night its sessions: do not widen the removal, the lock may
be a live git's. **A daemon that finds the lock held waits for it while its window is open** (every 60 s);
the locked commands never wait. And git and the version probes are started with `CREATE_NO_WINDOW`
because the task runs under `pythonw`, where every console child would otherwise open a window (the
sandbox itself still uses `DETACHED_PROCESS`, see `docs/sandbox.md`).

**After item 57: what binds.** **A predicate driver's term line must keep `value - start + 1 == work`**
(`verify.Harness.on_line`, only with `ScanTracking`): a line that breaks it halts as `protocol`, before the
index or the value is looked at, and its detail carries no number; keep both. **`bounds.py` reads three more
things and deliberately not three others**: number words to `decillion`, a factorial directly after a whole
number (never `!=`, `!!` or `20!/2`, and its `!` does not end a sentence for `_borrowed`), and `are the only
terms [known] up to X` with nothing but a number in the clause (`_ONLY_TERMS`, `_NUMBER_ONLY`). `checked /
tested up to X`, `none found up to X` and primorials were measured as wrong about half the time they would be
live (`data/item57/bound_gaps.txt`) and `tests/test_bounds.py` pins them unread: **do not add them without
redoing that measurement**, a bound read too high is the one error a session cannot undo. **A pending win is
given up only by `oeisbot recheck --release <id>`**, never by the pipeline and never by SQL: it refuses a
saved result that still loads or that cannot be opened, and keeps a drifted one as
`attempt-<id>.released.json`; do not run it while a session is running. **`dashboard/src/tabs.ts` joins the
modules that must have no imports.** A row of tabs is one Tab stop and the arrow keys move the focus without
opening; on a touch screen a tile opens on the second tap (`tabs.tapActs`, with `armed` cleared whenever
another tooltip takes over); an `extended` run that is not a win says which kind (`tabs.notAWin`).
**Wolfram Engine is struck** (the user, 2026-11-18: "I don't need to use it and want to keep this project
lean"), after the shapes of the 5,282 Mathematica-only programs were counted (`data/item57/mma_shapes.txt`)
and the tradeoffs set out. Nothing was installed. Do not propose a second runtime, or re-open this, unless
the user asks.

**If 90 tests fail and every one says `disk_cap`, the disk is full, not the code** (2026-11-18). The sandbox
stops any run when the drive has less than `reserve_disk_bytes` (8 GiB) free, and `C:` had 7.3 GB. Do not
lower the reserve to get a green run; ask for disk space (the user freed some and the suite passed).

**The dashboard after item 56: what binds.** **A win is `app.WIN`**, an `extended` run whose review is not
`rejected` and which has no `extra.review_refused`; never count `outcome = 'extended'` for a figure a person
reads (it said 3 wins where there is 1), and the Sessions table counts from attempts, not from
`sessions.wins`. **The Pick map's bands share one exact scale** (`treemap.layoutGroups`, `commonScale`); the
price is empty space in roomier bands, and `fairRects` only picks the least wasteful of nine layouts: do not
restore it as the mechanism, it does not converge. **`scale.ts`, `format.ts`, `treemap.ts` and (item 57) `tabs.ts` must have no
imports**, or node cannot test them, and nothing in `format.ts` may print exponent notation. **The server
answers only to `app.ALLOWED_HOSTS`** and refuses API requests from other pages (`Sec-Fetch-Site`); tests
get `testserver` through `tests/conftest.py`, which first asserts the real set. Only `/` serves the page.

**Session 12 ran on 2026-09-30 (item 52): 25 PARI picks, seed 212, 27 program runs, 0.85 h, 2 verified,
0 new terms, Brier 0.000185 for the per-pick reading against 0.076756 pooled.** Fifteen of seventeen
predictions held outright, the two others on all but one sub-claim; **five of 25 picks were program
misreads** retiring their sequences untested (16% in session 11, 20% here). The method to reuse is
`data/session12/`: `planS12.md` with a critic, a Monte Carlo that *pins* what the page proves, then
`resultsS12.md` audited (16 findings, all held). The offer (a) backfill then re-keyed 48 attempt rows
(`data/offerA/`, backup `data/oeisbot-before-backfill.sqlite3`): `queue` was then **3,357 / 1,958
(1432 / 383 / 143)** and `queue --all` **26,745 / 18**; **since item 58's rule changes they are 3,359 / 1,954
(1430 / 383 / 141) and 26,745 / 16 (11 / 5)**, re-derived 2026-11-23 from the real `session_pool`, with no
row written (at the daemon's first tier, 60 s / 1,800 s: 3,336). Attempts **280**, **587 tests** then
(634 since item 56, 703 since item 57, 886 since item 58, 903 with its safeguards). The rules fingerprint is `260fee4c701e`
(snapshot #1 carries `af16ba7ce8d3`: the selection rules differ from the ones it was taken under).

**The dashboard has a Pick map tab (item 54, 2026-10-13):** a treemap whose tile area is a sequence's
chance of being the first pick (`pickmap.chances`) and whose colour is its change since the newest
*different* pool snapshot. Three things bind later work. **The change is measured over the sequences in
both pools** (`pickmap.compare`); a plain `p / p_then` paints every surviving tile the same colour whenever
anything leaves the pool (55 left between the pool before session 12 and now, and 3,355 tiles read "up 2%").
**`pick_snapshots` / `pick_snapshot_rows` are in the live database**, created by `connect()`, so a bare
`db.connect()` aimed at the real file (a test, a mutation run) creates them there: give tests and workers
their own `OEISBOT_HOME` (`pymut.py` does; since item 58 the wall in `tests/conftest.py` also refuses it). **Snapshots are written by `run_session`, `oeisbot snapshot` and
(item 55) `oeisbot sync`** (and so by `oeisbot daemon`, through its sync and its first base session of a night), never by the dashboard, which stays read-only; `data/oeisbot.sqlite3` holds snapshot #1 (3,357 rows,
2026-10-13) and `data/oeisbot-before-pickmap.sqlite3` is the backup taken before it. Since item 56 the
bands are drawn at exactly one scale (tile rects; paint differs up to about 1.4x between bands because of the
0.5 px tile inset, and up to a quarter of the framed area can be empty at the worst width): **restate any of
those figures only from `data/item56/area_spread.ts`**, which measures what the page draws at the page's own
sizes. Item 54's `area_spread.ts` measures the frame's inner box, which tiles no longer fill. **Item 55 built those loose ends (2026-10-14, uncommitted):**
`attempt.snapshot_after_sync` makes `oeisbot sync` record a PARI-only snapshot (never fails the sync;
budgets from the newest PARI snapshot, `attempt.budgets_of`), the colour horizon stays fixed (no
picker), a footer line names the bands "All bands" cannot draw (`treemap.undrawn`), tiles are
keyboard-focusable (roving tabindex, `treemap.focusOrder` / `neighbour`), and a pool that cannot be built
is a 503 `pool_build_failed` with a reason and a **Try again** button. **Only the pure logic has automated
tests; `pickmap.tsx` had its browser pass on 2026-11-17** (all four pieces seen working, the 503 simulated
in the page), and item 56's changes to it were each seen in a browser too. The dashboard server is not
started unprompted; the user started it on 2026-11-17 and it was restarted for item 56's server changes.

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
with the replay in hand); **Wolfram was deferred** then and **struck on 2026-11-18** (item 57).
The 15 predicate-beside-`lista` blocks were read on 2026-11-18 (item 57, `data/item57/lista15.txt`): 6 are the
sequence's own test and 9 are helpers, so a blanket refusal would be wrong 6 times in 15. **The user decided the same day to leave
it** ("Okay leave it"): no refusal and no lister-loop candidate; do not re-open it without new evidence.
**After item 57 nothing on the roadmap was open; item 58 (2026-11-19 to 23) opened one thing.** Open now:
**Part B, the dashboard's "To submit" page, decided and not built** (do not start it unasked; the user
asked for the build part by part, each reviewed by adversarial agents). The user's alone: review #1's
steps 8 and 9, registering an OEIS account name, one `oeisbot sync` by hand and then importing the
scheduled task, and the requests to commit items 57 and 58. Also a restart of the dashboard server on
port 8765, which predates item 57's API fields and item 58's `/api/daemon`.

**Reviews #2 (A162762) and #3 (A162764) were closed as `rejected` on 2026-09-28 (item 49), on the user's
explicit instruction.** They are NOT wins and must never be submitted (item 45): both programs compute
*proved upper bounds* that their own authors call **conjectured to be exact** — the disclaimer is the
first line of each `program.gp` — so the 200 values each produced are conjectural, not verified terms.
**The draw was unaffected**, measured before and after: both pools unchanged at **3,438** and **26,747**,
with the two sequences merely changing gate — `no_supported_program` without `--model`,
`conjectural_program` with it (items 47 and 48). **Since item 58 they are out for a plainer reason: a
sequence with a `rejected` review is not drawn at all** (`select.candidates`), so neither reaches those
gates. **A162761 is the one sibling that is proved, and it
keeps its candidate** — verified in the same run. **But the close was not free**, and item 49's own
audit caught the overstatement: a `new` review also gates `attempt_sequence`, so
**`oeisbot attempt A162762 --model` now runs the model** where it used to skip. At the time
`db._insert_review` had no check against a prior `rejected` row, so such a run could have opened a new
review for the same false win; **item 51 added that check** (`db.ReviewRefused`, see below), and this
paragraph went on saying it was missing until 2026-11-23. Closing a review remains the user's decision,
not a coding agent's: **do not close review #1, or any future row, without being told to.** Note what a
close now costs: since item 58 `submitted` and `rejected` both keep the sequence out of every draw.

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
closed** (item 49, 2026-09-28), which is what made closing them safe (and since item 58 their rejected
reviews keep them out of the draw before this check is reached). **A162761, the one proved sibling, keeps its candidate** —
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
tested — **do not "fix" it.** It cost 7 sequences (0.03%) against a 26,747 pool; item 48 measured it as
5 of 26,752 before reviews #2 and #3 closed, and both figures are that item's own epoch, not a
disagreement. **On 2026-11-23 it is 5 of a 26,745 pool again**: item 58 holds A162762 and A162764 out
by their rejected reviews before this gate, so they are no longer counted at it. `conjectural_program` is the one
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
.venv\Scripts\python -m pytest                 # 903 tests, ~100 s; sandbox tests skip if `oeisbot setup` has not run
.venv\Scripts\python -m pytest tests/test_sandbox.py
.venv\Scripts\oeisbot setup                    # sandbox runtimes + AppContainer grants + database (idempotent)
.venv\Scripts\oeisbot sync --no-pull           # rebuild the candidate table from the local oeisdata clone
.venv\Scripts\oeisbot attempt A123456 --verify-s 60 --extend-s 60   # one sequence, short budgets
.venv\Scripts\oeisbot run -n 5 [--model]       # a session: pick and attempt 5 candidates
.venv\Scripts\oeisbot recheck                  # finish any re-check left pending by an earlier failure
.venv\Scripts\oeisbot daemon --status          # is the unattended loop running, and what is it on (reads only)
.venv\Scripts\oeisbot daemon --stop            # ask it to stop; the run in hand is recorded `interrupted`, retiring nothing
.venv\Scripts\oeisbot daemon [--window 22:00-08:00] [--no-sync]   # one window of sessions; the USER starts this, not an agent
.venv\Scripts\oeisbot daemon --arm | --disarm  # allow nights here / take it back. The USER's alone: an agent NEVER arms
.venv\Scripts\oeisbot daemon --task-xml FILE   # write the Task Scheduler definition (UTF-16); the user imports it
cd dashboard && npm run build                  # frontend; output in oeisbot/dashboard/static (not committed)
```

`run`, `attempt`, `sync`, `recheck`, `fetch-bfiles`, `setup` and `snapshot` are refused, with a message
naming the holder, while another of them or the daemon is running (the writers' lock). If one is refused,
do not look for a lock file to delete: there is none to delete, and the holder is a live process.

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
- Unattended running (item 58): `daemon.py` (the window, the ladder, the cooldown, recovery, the heartbeat),
  `lock.py` (the writers' lock), `schedule.py` (the task definition), `guard.py` (the refusal of the
  real project under a test). Its state: `data/daemon/` (`armed`, `heartbeat.json`, `stop`,
  `daemon-YYYYMMDD.log`) and `data/writer.lock`. Reference: `docs/daemon.md`.
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
- One writer at a time: a command that runs programs, syncs, stores a pool or contacts oeis.org is in
  `cli.LOCKED`, and the daemon holds the same lock. A run stopped as `interrupted` retires nothing.
- No test reaches the real database, the mirror or the network (`tests/conftest.py` and
  `oeisbot/guard.py`), and the daemon runs only where the user has armed it.
- Keep `tests/test_sandbox.py` passing. Add a test that attacks any new sandbox guarantee.

## Pitfalls

- Editing files that contain backslashes (GP `\\` comments, Windows paths, regex) through shell heredocs
  or `sed` corrupts escapes. Use a file-editing tool and `python -m py_compile` afterwards.
- Git Bash `sed -i` strips the CR from CRLF files (most docs and many `oeisbot/*.py` are CRLF in the working
  tree, a few files LF): use the Edit tool, or a Python script in bytes mode, and check with `git ls-files --eol`.
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
`dashboard.md`, `operations.md`, `daemon.md`) and `docs/known-limitations.md` if you fix or introduce a limitation.
