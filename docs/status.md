# Project status and handoff

Snapshot as of **2026-10-14**, written at the end of session 5 and updated after offer B, the
extension dead end, offers A, C, G, H, F, D and E, the flaky-test fix, session 6, items 2, 3, the
smaller-follow-ups bundle, session 7, the cost fit's statistics, the guards that keep them honest,
session 8, session 9, the searched-bound check, the predicate scan's progress heartbeats, the decision
not to build resume, the runtime versions, review #1's independent check, session 10's two conjectural
false wins, bundle A's three defect fixes, the conjectural-program check and its model-pool half,
the three reviews, session 11, the day every open decision was answered and the chosen items built,
session 12 with the offer (a) backfill, the two refusals that followed, the dashboard's Pick map and
its loose ends (history items 21 to 55), and the commit that landed items 34 to 54 (item 55 is built and
not committed).
This page
exists so work can resume in a new session without the history of the one that built the project. Update
it at the end of each working session.

**No task is in progress.** The latest is **history item 55** (2026-10-14): the Pick map's loose ends, each
one decided by the user as an option question ("Also after every sync", "Keep it fixed", "Add a footer chip",
"Make tiles focusable", "PARI only", "The newest snapshot's budgets", "Friendly message + retry"). `oeisbot
sync` now records a PARI snapshot after the sync (about 5.5 s on the real pool), the "All bands" view names
the bands it cannot draw, the tiles are reachable and operable from the keyboard, and a pool that cannot be
built shows its reason with a retry button instead of a bare 500. A critic on the plan (13 findings, all
accepted), mutation checks (Python 22 + 4 + 19 mutants, TypeScript 71, no survivor), an independent
audit (`data/item55/audits.txt`) and **no browser pass yet**, because the dashboard server was killed for
memory pressure and is not restarted unprompted. **Built on top of `f0081d9` and not committed**; the user
asked for the commit of items 34 to 54 only, so this waits for its own request. The one before it (the
user, 2026-10-13: "I like the idea of making the pick chance display a heat map like that one of the S&P such
that the pick chance is correlated with the size of the square on the map and the delta of pick chance can
also be displayed") was finished as **history item 54**:
a **Pick map** tab on the dashboard, a treemap in which a tile's area is a sequence's chance of being a
session's first pick and its colour is the change in that chance since an earlier snapshot of the pool,
grouped by difficulty band with a sub-tab per band. It needed the pool to be *recorded*, so two tables
now sit in the live database (`pick_snapshots`, `pick_snapshot_rows`; backup
`data/oeisbot-before-pickmap.sqlite3`), `run_session` and `oeisbot snapshot` write them (and, from item 55,
`oeisbot sync`), and **there was one snapshot when it landed, so the map is gray until the pool next
changes.** A critic on the plan, five
independent audits (33 findings), mutation checks, **567 tests**. No pipeline ran, nothing was
submitted, review #1 is untouched, and it was committed and pushed on 2026-10-14 with the
rest, as `f0081d9`.

Before it, the last ones (the user, 2026-09-30: "what are the next steps?", then "Present
all the decisions to me as questions with options") are finished as **history items 51, 52 and 53**.
**Every open decision was answered** — 19 in five batches, then 4 more once the measurements were in —
and everything chosen was built, measured or scoped the same day: the review refusal for rejected
sequences, the identity block in `review list` and the dashboard inbox, the honest header for a
disclaimed program in the model prompt, the sandbox callback guard (`harness_error`, never a dead end),
`infeasible` keyed by the budget it hit, the below-bound flag, gp memory judged against its stack
ceiling, balanced-parenthesis definitions with the whole-identifier helper check, and — in the
evening — refusal of print loops that start in the wrong place and of single-defaulted-parameter bulk
printers; six measurements and a Wolfram scoping note in `data/measure0930/`. **Session 12** ran in
the middle of it (item 52): 25 picks, 27 runs, 0.85 h, 2 verified, zero new terms, **Brier 0.000185
against 0.076756**, fifteen of seventeen predictions held outright, five picks lost to program
misreads, all foreseen; then the **offer (a) backfill re-keyed 48 attempt rows** (backup
`data/oeisbot-before-backfill.sqlite3`). **438 tests** (567 since item 54), checks clean, dashboard
rebuilt. **Not
committed when written** (the user was asked on 2026-09-30 and said "Not yet"; `f0081d9` landed it on
2026-10-14). Left as decided rather than built: the kill rules
stay, Wolfram is deferred, the `iferr` wrap is declined. **Still open: reading the 15 blocks that pair
a predicate with a list printer (next step vi), and review #1's steps 8 and 9, which are the user's
alone — the walkthrough was given, nothing has been submitted.**

Before it, "Do Another 60 s PARI session now", then "25 picks" and "Full" pre-registration (the user,
2026-09-29) was finished as **history item 50**: **session 11, 25 picks,
10,022 s (2.78 h), 5 verified, zero new terms, 8.98 picks/h** — session 8's rate again, for the same
reason (five full 1,800 s extensions). What it measured: a pre-registered **per-pick reading of every
program** predicted the outcome at Brier **0.0127 against the base rates' 0.1467** (the five verified
were exactly its four calls at >= .80 plus its .50 call), and **4 of the 25 picks (16%) were lost to
program-selection misreads**, each predicted before the run with the detail the row would carry:
A274003 calls a helper the `_ANAME_USE` check misses in *prefix* form (`is_A178751`), A335304's built
predicate is a helper for A054735, A290024's print loop starts at n = 1 while the emitter numbers from
offset 0 (**the program's values were right; only the index was off**), and A373945 is a bulk printer
whose own `print1` hides every `@T` line from a parser that ignores anything not starting with `@`. The
plan's own misses: its wall-clock band (by 65 s) and picks/h, because its Monte Carlo ignored what the
same page had proved about the picks that verified; a fresh audit then found **20 defects in the
write-up**, all of which held, including a false "first time" claim and an asserted-not-computed repair.
No code changed; one pipeline run; 25 attempt rows, 5 prediction rows, one `sessions` row; reviews
untouched; nothing submitted. **Review #1 still waits on the user for steps 8 and 9.**

Before it, "Tackle reviews 1-3. Go slow and ask questions when needed" (the user, 2026-09-28) was
finished as **history item 49**: **reviews #2 and #3 are closed as
`rejected`**, and review #1's step 7 was re-run and its step-8 material assembled. The close was
measured rather than argued — **both pools are unchanged**, 3,438 and 26,747, and A162761, the one
proved sibling, stays in. **It was not entirely free, and the audit caught the overstatement:** a `new`
review also gates `attempt_sequence` (`attempt.py:460`), so a targeted `oeisbot attempt A162762 --model`
now runs where it used to skip. Only the draw was ever measured; see item 49. Checking review #1's b-file against
[SubmitB.html](https://oeis.org/SubmitB.html) turned up a real defect: **every b-file the project writes
was missing the trailing blank line the rules require**, fixed at the call site in `artifact.write`.
**Review #1 still waits on the user for steps 8 and 9, and nothing has been submitted.** 423 tests,
2 of 2 mutations caught, no pipeline run; one database write, two review rows, backed up first.

**If you remember numbers from an earlier session, re-read them here: item 49's audit found a week of
drift and corrected it.** The real-run totals had been frozen at the `id <= 175` snapshot in three files
(107 sequences / 173 runs / 12.3 h, against the true **157 / 225 / 14.9 h**), the "Resuming" checklist's
two left-out tallies were stale, `data/runs/` was counted at 198 against **247**, `artifacts/` was
described as holding one folder when it holds **three**, and five pieces of local state — including two
database backups — were missing from the table below. All re-derived by query or by counting the disk.

Before it, "Present the decision to me with options",
then choosing to suppress the model path, was finished as **history item 48**: a sequence whose published
PARI program its author calls conjectural is now left out of the `--model` pool as well, not only the
PARI pool. A162763, A349899 and A351088 were in the model pool on the day item 47 shipped, where the
model is shown the entry's own `%C`/`%F` stating the conjecture and a Python re-derivation of it passes
verification by construction. Only the **draw** is blocked — `oeisbot attempt A... --model` still runs,
which is what made the trade cheap at 7 sequences of 26,752 (0.03%). 422 tests, 8 of 8 mutations caught,
no pipeline run and no database write.

Before it, "Yes plan (ii) — sections, critic on the
plan, independent audit" (the user, 2026-09-26) was finished as **history item 47**: a static check that refuses a PARI program
whose own author calls it conjectural or heuristic, with **no pipeline run and no database write**. The
pool moved 3,441 → 3,438, and the point is what it unblocked: **closing reviews #2 and #3 was free**,
because A162762 and A162764 stay out as `no_supported_program` instead of returning
at 2.32x and 1.56x mean pick weight — **done 2026-09-28 as item 49**, which measured the pool at 3,438
before and after. **A162761, the one proved sibling of four, keeps
its candidate**, so the pipeline can now tell them apart, which item 45 said it could not. 412 tests, 15
of 15 mutations caught. The critic overruled the plan's central design choice (where in the text to look)
and reversed its headline (the value claim is false under `--model`), and three of the eight planned
mutations turned out to be incapable of failing. **One limitation the item created** is recorded rather
than fixed: the model prompt no longer calls a conjectural program "correct", but it still quotes the
`%F` lines that state the conjecture — see item 47 and
[known limitations](known-limitations.md#strategies).

Before it, "What are the next steps for building out
functionality? I want to avoid running until everything is built out" (the user, 2026-09-25) finished as **history item 46**:
bundle A, three confirmed defects fixed with **no pipeline run and no database write** — a per-field digit
cap that stops an untrusted term line killing the sandbox's stdout reader thread, a `%o` block now
offering both its function form and its own print loop, and a def that needs a second argument no longer
driven with one. The pool moved 3,455 → 3,441; **A330204 and A366832, the two defects that motivated the
item, are back in it**, A330204 on a print-loop candidate while its predicate form keeps its `wrong_term`
dead end. The critic reversed the plan's central design decision (a static reproducibility check, measured
**wrong on 5 of the 32 blocks it was designed against**) and its audit then found two defects in shipped
code. 398 tests, 13 of 13 mutations caught.

Before it, "Tackle #1 I have time for a longer
run" (the user, 2026-09-24) finished as **history item 45**: session 10, 50 picks over two runs, 2.66 h, **zero genuine
new terms** — and a **new false-win class**. Two picks ran programs their authors call *conjectured*,
produced 200 values each, and opened `reviews` rows **#2 (A162762) and #3 (A162764)**. **Neither is
submittable**, and closing those two reviews is not free — it returns both sequences to the pool at
above-average weight where the same thing recurs. See item 45 and next-step (i). The write-up was
audited by a fresh critic who found **17 defects**, all of which held; three of them reversed a
conclusion, including the session's picks-per-hour story.

Before it, "Tackle A385331's review now" (2026-09-23) finished as **history item 44**: steps 2-7 of the
review checklist are done, **step 6 included** — an
independent check by a method sharing no arithmetic with the entry's program confirmed all 18 new terms,
after first reproducing all 23 known ones. **Nothing was submitted and the review row is untouched at
`new`**; steps 8 and 9 are the user's alone. Evidence in `data/review1/`.

Before it, "start on the resume item — evidence and a plan with a critic first" produced **two** history
items, neither of which is the one it set out to build:

- **Item 42: resume was measured, planned, reviewed and decided against**, by the user, after a critic's
  31 findings. **Do not re-open it without new evidence.** In short: the 21,002 s prize is retrospective
  (no attempt row carries a frontier, and no recorded predicate sha survives item 41's driver change);
  resume **saves no machine time** against a larger `--extend-s` and costs 2× on a find; and the design
  breaks [invariant 10](development.md#invariants), has no termination rule, and is damped geometrically
  by the selection failure penalty. The replacement is a targeted `oeisbot attempt A… --extend-s`, which
  nothing blocks — **A279795 needs ~1,900 s and A015766 ~9,817 s** to pass their published bounds.
- **Item 43: the runtime versions are recorded**, closing open offer (b). `gp_version` and
  `sandbox_python_version` in `meta`, plus a short `gp=2.17.4/GMP-6.1.2` token in each session's `note`,
  which is the half that survives a gp upgrade. **24 mutations, 23 caught**; the one that is not is
  recorded with the reason, and an earlier "17 of 17" was wrong (see item 43).

Both items corrected errors in this page: the "one-line fix would publish a two-run win" claim in item
41 (it takes **two** changes, the second a lie about `reproduced`), and the line-ending note, which was
wrong about `attempt.py` and which item 43's first attempt made **worse** before a byte-level audit
settled it — see section 6 of the process list below, including why not to measure this with `grep`.
Item 43's own independent audit then found **three real defects in shipped code** and, on its re-check,
two stale numbers the fixes had just introduced: the standing lesson is that a number is stale the
moment the thing it counts changes again, so **re-run the measurement, do not transcribe it**.

Before them, "build the post-verification check" was
finished as **history item 40**: `oeisbot/bounds.py` plus a new `searched_bound` stop at the verify/extend
boundary, **predicate form only**, with 22 new tests (340 total). Verified end to end on **A194099**, the
entry the whole item came from: it now verifies in 8.0 s and stops, where the same sequence spent 52.9 s
in session 8. Its plan was reviewed by a critic who found **seven** must-fix defects — including that
`Decimal ** int` is not exact (2^200 was wrong while 2^63 passed), and that the stop's detail would have
leaked a held-out term value into the model prompt.

Before it, "tackle item 1's measurement now" was finished as **session 9, history item 39**: the answer
was that **the 44.6% headline was the wrong quantity**. Most published bounds sit inside what a run scans
anyway; the actionable share for skipping a run is **162-241 of 3,450 (5-7%)**, and `pari.out_of_reach`
can never consume such a bound because it bounds *verification* on the *verify* budget. Details in item 39.

Before it, the user's "start the --verify-s 60 session" was finished as **session 8, history item 38**:
20 picks, 8,038.6 s, 5 verified, **0 new terms**, and that session's
next-step-1 question settled — **8.96 picks/h against session 7's 4.78, a 1.88x improvement, 83% of it
attributable to the gate itself**. The run was pre-registered, its plan reviewed by a critic who found
six errors, and its write-up then audited by a second critic who **reversed two of its three
conclusions** (the offer B attribution and the extension argument; details in item 38). Its most
valuable output came from that audit rather than from the run: **1,537 of the 3,450 candidates in the
live pool — 44.6% — publish a searched bound in a comment the pipeline never reads**, which is now
[next step 1](#open-offers-and-next-steps). Before it, the user's "Update the test
suite/documentation (if possible) to avoid defects in future runs" was finished as **history item 37**: the three failures
that recurred through item 36 are now machine-checked — the documented test counts against what pytest
collected, the `verify.Prediction`-to-column mapping, and `scripts/replay_predictions.py`'s bookkeeping,
which had no tests at all. Each guard was verified by re-introducing the defect it exists for. Before it,
**next step 2 — record the cost fit's own statistics in
`predictions`** (the user, 2026-09-21: "Do #2 now") was finished as **history item 36**: `predictions`
gained `fit_trustworthy`, `fit_npoints`, `fit_disagreement`, `fit_climbing` and `rate_drift`, and the 40
existing rows were backfilled by replaying their term logs. The whole history is **6 trustworthy cost
fits in 18 fitted projections**, and the one the audit had missed — A229209, prediction #18 — is now a
row anyone can find. The item also **corrected its own premise**: the claim that no query could answer
"has a trustworthy fit ever happened?" was too strong, because `disagreement` is arithmetically the
stored `predicted_s_high / predicted_s_low`. What was genuinely unrecoverable is `npoints` and
`rate_drift` (details in [data and schema](data-and-schema.md#predictions-one-row-per-projected-term)).
Before it, **next step 1 — the `--verify-s 600` pass** (the user, 2026-09-20: "Do step 1 — the run
`--verify-s 600` pass now") finished as **session 7** (history item 35) and produced **the project's
first new terms**: 18 of them for A385331, a(25)..a(42). Nothing has
been submitted. The run also gave offers F and A their first exercise on real runs — F six times, and it
is what made the win 18 terms instead of 8 — and measured its own premise as a failure: the 600 s gate
admitted one extra verified run in 20, which produced nothing, for 54% of the session's machine time.
Its first headline was **reversed by the audit** (the `infeasible` kill at a(43) was correct, not a false
positive, confirmed by re-deriving a(43) > 2x10^8 independently), which is the second session running
whose headline the audit had to reverse. Before it, next step 2's nine sub-items became six code changes
and three corrected documents (item 34), item 3 rejected PARI blocks calling another entry's helper
(item 33), and item 2 made a failed run record *why* it failed (item 32).

**One thing waits on the user.** A385331's open `reviews` row — **steps 2-7 of the review
checklist are done, step 6 included** (item 44) and **step 7 was re-run on 2026-09-28 and still passes**
(item 49), so what is left is the two steps only a human can do: submitting by hand and recording the
outcome, with the material assembled in `data/review1/SUBMISSION.md`. **The two conjectural false wins,
reviews #2 and #3, are no longer waiting**: they were closed as `rejected` on 2026-09-28 (item 49) at
the user's instruction, with both pools measured unchanged (3,438 and 26,747) — though **not free**: the
close also released the `open_review` gate on a targeted `--model` attempt of those two, see item 49.
**One thing waits on a commit: item 55.** Everything through item 54 is committed
and pushed as `f0081d9` (2026-10-14, at the user's request), but that answer covered the work to item 54
and not the Pick map follow-ups of item 55, which are built and uncommitted (`git status` lists the
files; history item 55 says what each does). The user commits, so do not commit or push unless asked again.
**One offer is still open** — what to do about the 35
sequences item 41 un-retired (changing the driver changed every predicate `program_sha`); see
[open offers](#open-offers-and-next-steps). **One new decision is waiting too** — next-step (v), created
by item 49 and found by its own audit: a `rejected` review no longer guards its sequence from a targeted
`oeisbot attempt A... --model`, and `db._insert_review` would let such a run open a fresh review for a
false win already rejected. The recommended fix is a guard in `_insert_review`, **not** in
`attempt_sequence`, which item 48 forbids touching. The other two questions are settled: the gp version
is recorded (item 43) and resume is decided against (item 42). No background jobs, no pending re-checks,
`data/pending/` is empty.

### What is committed

`origin/main` and `HEAD` are `f0081d9` ("Sessions 7 to 12, history items 34 and 36 to 54, and the
dashboard Pick map"), and `git status` was clean when it was pushed on 2026-10-14. The user asked for it
(the answer "Commit and push" to a question about item 54's loose ends), and it was pushed after a fetch
confirmed `origin/main` was still `3dacfb8`. It is **one commit on top of `3dacfb8`: 59 files, 46 modified
and 13 new, 12,230 insertions and 486 deletions** (`git show --stat f0081d9`). It holds **items 34, 36,
37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53 and 54** and everything from sessions 7
to 12 that reached a tracked file. They are one commit because they were never separated and could not be:
the items interleave in the same files (`db.py`, `attempt.py`, `cli.py`, `strategies/pari.py`, the docs
pages), so a split would have meant a commit that does not build or a test count that matches no commit.

The item-by-item file lists this section kept while the work was uncommitted are gone, because `git show
--stat f0081d9` is the authority on what is in the commit and a hand-kept list had drifted from it before
(item 45 was missing from it until item 49's audit found it). Items 42, 44, 45 and 50 are docs only and
item 52 is docs and local state; their evidence is in the gitignored `data/` and in the local database,
which git does not see (next paragraph). `data/item49/recheck_numbers.py` now checks that `f0081d9` is on
`origin/main` and in `HEAD`'s history and holds 59 files; it prints the working tree's counts but does not
check them, since they move with every edit.

**Changes git cannot see.** Item 36 altered the live database in place — five columns on
`predictions`, `schema_version` 1 → 2, and 18 rows backfilled — with a `VACUUM INTO` backup at
`data/oeisbot-before-fit-stats.sqlite3`. **Session 8 added 20 attempt rows (#156-175), 5 prediction rows
and a `sessions` row**, with its own backup at `data/oeisbot-before-session8.sqlite3`. And session 7's
win is local state `.gitignore` excludes: database rows, `data/session7_pari.log`, `data/p4_probe.log`,
`data/bfiles/A385/b385331.txt` and the `artifacts/A385331/attempt-139/` folder — so **the win exists
only on this machine**. Sessions 7 and 8 themselves changed no code. **Item 49 (2026-09-28) set reviews
#2 and #3 to `rejected` and wrote a `note` on each** — two rows, no other table touched — with a backup
at `data/oeisbot-before-close-reviews23.sqlite3` (integrity checked). It also added
`data/review1/SUBMISSION.md` and `data/review1/b385331-submit.txt`, both under the gitignored `data/`.
It did **not** modify `artifacts/A385331/attempt-139/b385331.txt`: that artifact is the record of what
the run produced, so the corrected copy sits beside the review evidence instead. **Session 11
(2026-09-29) added 25 attempt rows (#229-253), 5 prediction rows and a `sessions` row**, with its
backup at `data/oeisbot-before-session11.sqlite3`, its console in `data/session11_pari.log` and 21 new
term logs in `data/runs/`; no review row was touched and nothing was submitted. **Item 54 (2026-10-13)
added two tables to the live database and wrote one snapshot into them** (`pick_snapshots`, and
`pick_snapshot_rows` with 3,357 rows), after a `VACUUM INTO` backup at
`data/oeisbot-before-pickmap.sqlite3`; one of its mutation runs had already created the two *empty*
tables there by accident, so the backup contains them (the history entry has the account). Nothing else
in the database changed.

**Item 55 is not in the commit.** It was built on top of `f0081d9` on 2026-10-14 and sits in the working tree;
`git status` is the authority on which files (a hand-kept list drifted before), and its plan, critic, timing
scripts, mutation runs and audits are in the gitignored `data/item55/`. **It wrote nothing to the live
database:** at the time of writing `data/oeisbot.sqlite3` still has the modification time of item 54's
snapshot (2026-10-13 21:30) and the one snapshot in it, and the sync snapshot was timed on a `VACUUM INTO`
copy. The rules fingerprint is unchanged by it as well (`attempt.rules_fingerprint()` is `af16ba7ce8d3`,
equal to snapshot #1's), because `budgets_of` and `snapshot_after_sync` sit outside what the fingerprint
hashes; so the first snapshot a sync records will not carry a "the selection rules changed" note on that
account.

587 tests pass and `scripts/check_docs.py` reports no link problems. Every decision made so far is in the
table below; what could come next is in [next steps](#open-offers-and-next-steps).

## Offers G, H and F, one at a time (done)

The user's words (2026-09-19): "Implement G, H, and F one at a time. Break each item down into sections.
Use a critic agent to stay on task." Each item goes through these sections, in order, and the next item
starts only when the previous one is finished:

1. **Evidence**: measure the problem on the real data first (database read-only, term logs, replays).
2. **Plan**: a short written plan with that evidence, the channels or cases it covers, tests and docs.
3. **Critic review**: one critic agent per item, briefed with the plan and told to keep the work on task
   (flag scope creep as well as errors); the same agent is reused for section 7 (with SendMessage).
4. **Decisions**: ask the user only what is genuinely theirs (scope, trade-offs), with a recommendation.
5. **Implementation**.
6. **Tests and mutation checks**: every new behaviour broken on purpose, each break caught, files restored
   byte for byte. **Line endings are mixed across the repo and must be checked per file, never assumed**
   — audited byte for byte on 2026-09-23 (item 43): of 50 `.py` files under `oeisbot/`, `tests/` and
   `scripts/`, **19 are CRLF, 25 are LF and 6 are empty**, none mixed within itself. CRLF includes
   `verify.py`, `attempt.py`, `db.py`, `pari.py`, `codegen.py`, `estimate.py`, `artifact.py`, `cli.py`;
   LF includes `setup_tools.py`, `select.py`, `bounds.py`, `config.py`, `oeisdata.py`, and **most of
   `tests/`** (`test_attempt.py`, `test_codegen.py`, `test_db.py`, `test_verify.py`, `test_heartbeat.py`
   …). The only file this page ever had wrong was `attempt.py`, which is **CRLF**, not LF as sections 6
   and the `mutateHB.py` note said until now; history item 34 had already found that and the correction
   never reached either place. A multi-line mutation pattern written with a plain `\n` matches nothing in
   a CRLF file — write patterns line by line, or normalise first.
   **Check with Python (`b.count(b"\r\n")` against `b.count(b"\n")`), not with `grep -c $'\r$'`**: in
   this machine's Git Bash that grep reports every line as CRLF, in every file, which is how item 43's
   first attempt at this note managed to claim the exact opposite of the truth.
7. **Critic audit, then a re-check of the fixes** by the same critic. **Item 47 split this in two and it
   was worth it:** a *fresh* auditor on the shipped code (independent, not marking its own homework —
   the original critic's overrule was in that code) plus the original critic re-checking its own
   findings, which is the only thing it can do that a fresh agent cannot. Both found real defects the
   other did not. Two process rules came out of it:
   - **Do not mutate the working tree while an agent is auditing it.** Running the mutation harness
     during the audit showed the auditor `pari.py` in mutated states, including one with the check
     disabled, and it had to re-take every measurement at pinned hashes.
   - **A mutation's `expect` column is a comment unless something checks it.** With `-x`, a mutant that
     several tests can object to is reported "caught" while a test other than the named one fails. Item
     47 hit this three times in one item; the fix is an isolation list — run that mutation *without*
     `-x` and require the failing set to be exactly the named test. Item 46's note warns against `-k`
     *instead of* the whole suite; the answer is both, not neither.
8. **Docs and status**: every changed behaviour in its doc page, known limitations, this page.

Where each item stands:

- **G** (history item 25): **done.** All eight sections, including the critic's audit and its re-check
  of the fixes; 248 tests pass, 9 mutations caught (`mutateG.py`).
- **H** (history item 26): **done.** All eight sections, including the critic's audit and its re-check
  of the fixes; 248 tests pass, 9 mutations caught (`mutateH.py`).
- **F** (history item 27): **done.** All eight sections; the user chose the rule in section 4. 254 tests
  pass, 13 mutations caught (`mutateF.py`).

Working files from the session that did offers A, C and G (not in the repo; they stay on disk unless
Windows clears its temp folder), in `C:\Users\GRANTB~1\AppData\Local\Temp\claude\C--gtest-OEISBot\1eef21df-8ef2-4e13-91b7-c3612d34a306\scratchpad`:

- `baselineA\`, `baselineC\`, `baselineG\`: copies of the tree just before each offer;
- `mutateA.py`, `mutateC.py`, `mutateG.py`: the mutation checks (each applies text patterns to the
  sources, runs the tests, restores byte for byte and checks sha256; patterns must match the current code);
- `planA.md`, `planC.md`, `planG.md`; `offerA*.diff`, `offerC*.diff`, `offerG.diff`;
- the replays and measurements: `backtest*.py`, `growth.py`, `critic\feas.py`, `c_reindex.py`,
  `c_classify*.py`, `measureC_expected.md`, `c_measure_report.py`.

Working files from the session that did offers H, F, D and E, in
`C:\Users\GRANTB~1\AppData\Local\Temp\claude\C--gtest-OEISBot\2f7edb58-25f0-4309-8de7-4b8e603b688b\scratchpad`:

- H: `baselineH\` (the tree just before H), `h_evidence.py` (the repeat rule replayed over every model
  run), `planH.md`, `mutateH.py`, `offerH.diff` and `offerH_v2.diff` (after the audit's fixes), and the
  critic's scripts in `criticH\`;
- F: `baselineF\`, `f_evidence.py` and `f_alternatives.py` (the infeasibility check replayed over every
  term log, with the candidate rules), `f_check_critic.py`, `f_points.py` (the real points the tests
  pin), `planF.md` (sections 7 and 8: the revision after the critic, the user's decision), `mutateF.py`,
  `offerF.diff` and `offerF_v2.diff`, and the critic's scripts in `criticF\`;
- D: `baselineD\`, `d_evidence.py` (rows grouped into attempts, the penalty per option, the pools),
  `d_check.py` (the grouping proof and option 1c), `planD.md` (sections 5 and 6: the revision after the
  critic, the user's decision), `mutateD.py`, `d_backfill.py` (the one-off backfill, applied) and
  `d_backfill_rollback_check.py` (its rollback proven on copies), `offerD.diff` and `offerD_v2.diff`, and
  the critic's scripts in `criticD\`;
- E: `baselineE\`, `e_evidence.py` (what the rule held back, the 300 entries with siblings, history) and
  `e_reach.py` (which of them the rule can reach), `planE.md` (sections 4 and 5: the revision after the
  critic, the user's decision), `mutateE.py`, `offerE.diff` and `offerE_v2.diff`, and the critic's scripts
  in `criticE\` (its `test_longer_budget.py` shows the old rule's sibling never running).
- `flaky_compare.py`: the flaky test run N times with the current and the pre-F `estimate.py` (history
  item 30; it kept only the first failing line of each run).

Working files from the session that fixed the flaky test (history item 30), in
`C:\Users\GRANTB~1\AppData\Local\Temp\claude\C--gtest-OEISBot\7399237c-5c71-49f3-a34e-77da7ccb7057\scratchpad`:
`planT.md` (section 8: the revision after the critic; section 9: the user's decision), `flaky_evidence.py`
(the old test's call run N times, every assertion evaluated on its own, every assessment kept),
`flaky_show.py`, `flaky_under_load.py` (the same with one CPU burner per core), the data
`flaky_evidence_all.jsonl` (210 idle runs) and `flaky_evidence_load.jsonl` (18 under load), `mutateT.py`,
`repeatT.py` (the new tests N times, optionally under load), and the critic's scripts in `criticT\`.


Working files from the session that did items 36 and 37, in
`C:\Users\GRANTB~1\AppData\Local\Temp\claude\C--gtest-OEISBot\c6c9e317-11ff-42f3-b80e-abddd8d2f39e\scratchpad`
(a temp directory: treat it as evidence that may already be gone, not as a source of truth -- everything
load-bearing is in the repo or the database). `plan-item36.md` is the plan with the critic's 24 findings
and their resolutions; `expected-backfill.json` is the backfill's expected result, written from the term
logs **before any code existed**, and `check_against_expected.py` compares a database against it;
`probe.py`, `probe2.py` and `probe3.py` are the read-only probes that established the replay is faithful;
`verify_f11.py` and `verify_f3.py` re-derive the two derivability claims the audits corrected;
`prove_rollback.py` proves the backfill transaction rolls back by injecting a failure three rows in; and
the `mutate*.py` harnesses each re-introduce a defect to prove something catches it -- `mutate.py` and
`mutate6.py` for the write path, `mutate_csv*.py` for the `predictions.csv` column permutations, and
`mutate_guards*.py`, `mutate_docs.py` and `mutate_checkdocs.py` for item 37's guards.

Working files from session 8 (history item 38) were **copied out of the temp scratchpad into
`data/session8/`** (16 files, with a README explaining how to run them), so unlike every earlier
session's they are still on this machine.
`data/` is gitignored, so they are local state, not repo content. `planS8.md` is the
pre-registered prediction page as revised after its critic, `planS8-v1-precritic.md` the draft before it,
and `resultsS8.md` the write-up as corrected by the post-run audit. Before the run: `prepicks.py`
reproduces the draw read-only, `preevidence.py` builds each pick's plan, `baserates.py` and
`firstattempt.py` derive the historical rates, `intervals.py` computes the exact Poisson-binomial
intervals, and `checkcritic.py` re-derives the pre-run critic's six claims independently (the term-log
check that moved the base rate to 12/31 is there). After it: `postrun.py` re-derives the results from the
database, `a194099.py` investigates the `over_prediction` kill, `a194099_term29.py` computes A194099's
terms from the definition, and **`nomoreterms.py` is the one worth keeping** -- it measures the
searched-bound comments that are now next step 1.

Working files from the session that did **item 46** were copied out of the temp scratchpad into
**`data/item46/`** (12 files plus a `critic/` subfolder of 8, with a `README.md`), so they are still
on this machine. Three are worth naming:

- **`mutateA.py` is the one to re-run** before changing `verify.on_line`'s parse block,
  `pari._drivable`, `pari._classify`'s parameter handling, or `build_candidates`'
  `builds`/`block_rejects` structure — 13 mutations, 13 caught, whole suite per mutation,
  line-ending aware, both files restored byte for byte with a sha256 assertion.
- **`classify_m1.py` is kept as the record of a mistake, not as a tool.** It is the static
  "can the driver reproduce this loop?" check the plan proposed shipping, and it was measured
  **wrong on 5 of the 32 blocks it was designed against**. That measurement is why no such
  predicate exists in production. **Do not resurrect it without redoing the measurement.**
- **`pool_diff.py`** reproduces the 3,448 — 3,434 pool diff by emulating the *old* builder on top
  of the new code, which is how the 20 leaving and the 6 entering were established rather than
  inferred.

Working files from the session that did **items 42, 43 and 44** were **copied out of the temp scratchpad
into `data/`**, as sessions 8 and 9 did with theirs, so they are still on this machine:

- **`data/item42-43/`** (10 files with a `README.md`). **`planRESUME2.md` is the one to read before ever
  re-opening resume** — the plan with its critic's 31 findings folded in and my own three errors marked.
  **`mutate43.py` is the one to re-run before changing `runtime_versions`, `_probe_version`,
  `gp_session_token` or `db.set_meta_many`** — 24 mutations, 23 caught, line-ending aware, restoring both
  files byte for byte with a sha256 assertion. Also `planGPVER.md` and item 42's five read-only evidence
  scripts (`pop.py`, `deadend.py`, `reach.py`, `alt.py`, `blockers.py`) plus `verify_critic.py`, which
  re-derives the critic's load-bearing findings independently.
- **`data/review1/`** (5 files with a `README.md`): item 44's independent check and its 775 s sweep
  output, plus item 49's step-8 package (`SUBMISSION.md`, `b385331-submit.txt`).
  **Do not delete while review #1 is open.**

The original scratchpad was
`C:\Users\GRANTB~1\AppData\Local\Temp\claude\C--gtest-OEISBot\13875200-2a3f-4fbf-895c-2563421f737d\scratchpad`
(a temp directory: treat it as gone). Nothing load-bearing is left only there.

Working files from the session that did item 41 (progress heartbeats), in
`C:\Users\GRANTB~1\AppData\Local\Temp\claude\C--gtest-OEISBot\44ec7593-8354-4858-8ebc-321327dedc20\scratchpad`
(a temp directory: evidence that may already be gone, not a source of truth — everything load-bearing is
in the repo). `planRESUME.md` is the plan as the critic reviewed it, **including the resume design this
item deliberately did not build**, which is the best starting point for that item — read it with the
critic's findings, summarised in history item 41.

- Evidence, all read-only against the live database: `bits_evidence.py` (+ `.json`) priced the
  `_bits_bound` follow-up that measurement killed; `recall_size.py` and `why_nobound.py` sized the
  extractor's recall gaps, splitting the 767 predicate candidates with no applicable bound into "no `%C`
  lines at all", "correctly rejected" and "recall could help"; `frontier.py` reconstructs each exhausted
  run's scan frontier from its term log and compares it with `bounds.applicable`.
- Sandbox measurements: `heartbeat_cost.py` (the three heartbeat forms), `heartbeat_tune.py` (block size
  and a realistic predicate), `block_small.py` (small blocks), and **`loopform.py`, the one worth
  keeping** — it isolates the cost to the finite loop bound, and any re-measurement of the ~4% should
  start there. `e2e_heartbeat.py` drives the real driver and prints the accepted heartbeats and the
  block sizes as they adapt.
- `mutateHB.py` is the mutation check: 17 mutations against `pari.py`, `verify.py` and `attempt.py`,
  tests run for each, file restored byte for byte with a sha256 assertion. It is **line-ending aware** on
  purpose: a multi-line pattern written with a plain newline silently matches nothing in a CRLF file,
  which is how its first run reported false catches. Its own comment said `verify.py` was CRLF and
  `attempt.py` LF; **both are CRLF** (byte-counted 2026-09-23 — see section 6 above, which has the audit
  of all 50 files and the reason not to measure this with `grep`).

## Resuming in a new session

1. **Work in the right directory.** The git repository is nested: `C:\gtest\OEISBot\OEISBot` holds the
   code; the outer `C:\gtest\OEISBot` is just a folder. Start sessions in the inner directory, so
   `CLAUDE.md` loads automatically.
2. **Read** `CLAUDE.md`, this page, then [known limitations](known-limitations.md).
3. **Confirm the machine is still set up** (every command should succeed without reinstalling):

   ```
   .venv\Scripts\python -m pytest            # expect 587 passed (on an otherwise idle machine: history item 30)
   cd dashboard && npm test                  # 33 node tests (the Pick map's pure logic); npm run build must be clean too
   .venv\Scripts\oeisbot model-check         # expect 'ready' (first call loads the model, about a minute)
   .venv\Scripts\oeisbot stats               # expect 26,814 candidates (14,436 with no program)
   .venv\Scripts\oeisbot attempts --limit 300 # expect 280 rows, ids 1-280; failure modes include
                                              # searched_bound: 5 (A325963, session 12) and
                                              # max_new_terms: 2 (session 10), wrong_term: 33 and
                                              # incomplete: 11 (session 12 added 3 and 1; session
                                              # 11 had brought them to 30 and 10)
   .venv\Scripts\oeisbot queue --all --limit 0  # the --model pool: expect 26745 candidates; left out
                                             # 18 (11 too_few_known_terms, 7 conjectural_program).
                                             # Was 26747 / 16 (9 / 7) until 2026-09-30: item 51's
                                             # helper check refused A122036's block (1 known term)
                                             # and item 52's backfill retired A309238's program (2
                                             # known terms), so both now fall to too_few_known_terms.
                                             # NEW in this checklist for item 48: the PARI line below
                                             # cannot show that item at all, because item 48 changes
                                             # only this pool. Was 26752, left out 9
                                             # too_few_known_terms, measured before the change.
                                             # The count was 5 conjectural_program until item 49
                                             # (2026-09-28): closing reviews #2 and #3 let A162762 and
                                             # A162764 reach this gate instead of being dropped as
                                             # open reviews earlier in select.candidates, so the same
                                             # two sequences moved from one exclusion to another.
                                             # The POOL TOTAL did not move, and that was the point
   .venv\Scripts\oeisbot queue --limit 0    # expect 3357 candidates; left out 1958 (1432 / 383 / 143)
                                             # the three add up to the 1958: 1432 no_supported_program,
                                             # 383 verify_out_of_reach, 143 all_programs_dead_ends.
                                             # Was 3375 / 1940 (1407 / 383 / 150) until item 53 (2026-09-30,
                                             # later the same day) refused 28 print loops and 4 bulk
                                             # printers: -18 pool, +25 no_supported_program, -7 dead ends
                                             # (sequences retired only through a now-refused loop). At
                                             # the run's --extend-s 1800: 3334 / 1981 (1432 / 383 / 166).
                                             # Evidence: data/measure0930/diff2.txt, pools_after_item53.txt.
                                             # Was 3418 / 1897 (1420 / 383 / 94) until 2026-09-30,
                                             # when three things moved it in one day: item 51's
                                             # builder change (+13 pool, -13 no_supported_program,
                                             # +2 out of reach, -2 dead ends), session 12 (item 52:
                                             # -23 pool, +23 dead ends) and the offer (a) backfill
                                             # (-33 pool, +35 dead ends, -2 out of reach). At the
                                             # run's --extend-s 1800 the line reads 3352 / 1963
                                             # (1407 / 383 / 173). Evidence: data/session12/
                                             # pools_post.txt, deadends_isolated.txt and
                                             # data/offerA/pools_after.txt. The older note follows:
                                             # Was 3438 / 1877 (1420 / 383 / 74) until session 11
                                             # (2026-09-29, item 50) retired 20: 16 verify_timeout,
                                             # 2 wrong_term, 2 incomplete. At the run's own
                                             # --extend-s 1800 the line reads 3407 / 1908 (105): the
                                             # same 20 plus 4 full extensions (A034293's is not one:
                                             # its second program never ran, so it stays in the pool).
                                             # no_supported_program was 1418 until item 49, +2 for the
                                             # same reason as above:
                                             # the two closed reviews' sequences are now counted here
                                             # THESE ARE AT DEFAULT BUDGETS. verify_out_of_reach and
                                             # all_programs_dead_ends both move with --extend-s (at
                                             # 1800 s it is 383 / 105, was 383 / 81 before session 11);
                                             # only no_supported_program is
                                             # budget-independent, so a different budget is not staleness.
                                             # Was 3441 / 1872 (1415 / 383 / 74) before item 47,
                                             # 3455 / 1858 (1391 / 389 / 78) before item 46, and
                                             # 3497 / 1818 (1391 / 389 / 38) before session 10.
                                             # Item 46 moved it by -14, re-run not hand-derived: 20
                                             # sequences whose only def needs a second argument became
                                             # no_supported_program; 6 came back on a print-loop
                                             # candidate (A130817, A134865, A277041, A330204, A338998,
                                             # A366832); and 4 moved from verify_out_of_reach to
                                             # no_supported_program because the out-of-reach candidate
                                             # is the one that went away -- named, not inferred:
                                             # A119751, A119752, A175261, A219953
   .venv\Scripts\oeisbot recheck             # expect "no wins are waiting for a re-check"
   .venv\Scripts\oeisbot review list         # expect THREE rows, ONE of them open: #1 A385331
                                             # a(25)..a(42) at `new`, waiting on the user; #2 A162762
                                             # and #3 A162764 are `rejected` with a note (item 49) --
                                             # NOT submittable, see history item 45
   .venv\Scripts\python scripts\check_docs.py  # expect 0 link problems; the 10 IDENT lines are the expected
                                               # ones (a PARI type, illustrative names, and PARI function
                                               # names from OEIS entries' own programs -- not real code
                                               # identifiers). It checks that count itself now, so a new
                                               # one is a problem, not a judgement call. Was 5 until
                                               # session 11 (2026-09-29) cited is_A274003, is_A178751 and
                                               # is_A034293 in CLAUDE.md and this page; 6 until item
                                               # 43, whose tests name the last Python builtin on the list
   .venv\Scripts\python scripts\replay_predictions.py   # expect "455 stored predictions; 455 replayed
                                               # (433 with no cost fit, 22 with one, 8 of those
                                               # trustworthy)" and exit code 0. Was 450 / 430 / 20 / 8
                                               # before session 11 and 45 / 19 / 7 before session 10
   ```

   **All of these were re-run and matched on 2026-09-23**, the `queue` pool scan included, after
   items 42, 43 and 44 — 390 passed, 26,814 candidates, 176 attempt rows, 3,497 / 1,818
   (1391 / 389 / 38), one open review still at `new`, no pending re-checks, 45 of 45 replayed, 0 link
   problems. **None of the three items wrote a database row**, so nothing here moved; the `meta` rows
   item 43 adds appear at the next `oeisbot setup` or `oeisbot run`.

   **Session 11 (2026-09-29, history item 50) moved the attempt, session, prediction and PARI-pool
   lines, and nothing else.** Re-run after the session: **253 attempt rows** (ids 1-253), **11**
   sessions, **455** predictions, `queue` **3,418 / 1,897 (1420 / 383 / 94)** — 20 retirements, the
   `all_programs_dead_ends` count moving 74 → 94 and the other two splits untouched — 455 of 455
   replayed at exit 0 (433 / 22 / 8), three review rows with one still open (#1 `new`, `updated_at`
   unchanged), no pending re-checks, `data/pending/` empty, `queue --all` unchanged at 26,747 / 16,
   423 passed. **One pipeline run: 25 attempt rows, 5 prediction rows, one `sessions` row; no code
   changed and no other database write.** The pre-run copy is `data/oeisbot-before-session11.sqlite3`.

   **Session 12, item 51's builder change and the offer (a) backfill (all 2026-09-30, items 51 and 52)
   moved the attempt, session, prediction and pool lines again, and the test total.** Re-run afterwards:
   **280 attempt rows** (ids 1-280), **12** sessions, **456** predictions, `queue` **3,375 / 1,940
   (1407 / 383 / 150)** — then **3,357 / 1,958 (1432 / 383 / 143)** once item 53's two refusals landed
   that evening — `queue --all` **26,745 / 18 (11 / 7)**, **438 tests** (567 after item 54), three review rows with
   one still open (#1 `new`, `updated_at` unchanged), `data/runs/` 290, `data/pending/` empty. The
   checklist above says how each of the three moved the pool; `data/item49/recheck_numbers.py` was
   re-baselined to these numbers and passes. Two database copies predate the day's writes:
   `data/oeisbot-before-session12.sqlite3` (before the run) and `data/oeisbot-before-backfill.sqlite3`
   (before the backfill, i.e. after the run). Item 54 (2026-10-13) then added the pick-snapshot tables and
   snapshot #1 (3,357 rows) without moving any of these counts; its backup is
   `data/oeisbot-before-pickmap.sqlite3`.

   **Item 49 (2026-09-28) moved the review line and nothing else.** `review list` now shows **three rows,
   one open**: #1 `new`, #2 and #3 `rejected`. Both pool lines were re-run through the CLI after the
   close and are **unchanged** — `queue` 3,438 (1,420 `no_supported_program` / 383 `verify_out_of_reach`
   / 74 `all_programs_dead_ends`) and `queue --all` 26,747 — which is the measurement that made closing
   the reviews free: the two sequences simply changed which gate excludes them. `left_out` on the model
   line now reads `conjectural_program: 7` where item 48 recorded 5, and that is the same 7: item 48's
   count omitted A162762 and A162764, which its `Runnable` never reached because their open reviews
   excluded them earlier in `select.candidates`. Also re-run and matched: **423 passed** (422 + 1),
   26,814 candidates, 228 attempt rows, 10 sessions, 450 predictions, no pending re-checks, 0 link
   problems with the expected 5 IDENT lines. **One database write, two review rows**; no pipeline run.

   **Item 48 (2026-09-26) moved only the `--model` pool**, and that is the point of adding the `--all`
   line above: 26,752 → **26,747**, with `conjectural_program: 5` newly reported in `left_out`. The
   PARI `queue` line did **not** move (3,438, same split), because item 48 changes only the model
   branch of `Runnable._why_not`. Re-run and unchanged: 422 passed (414 + 8 new tests), 26,814
   candidates, 228 attempt rows, 450 of 450 predictions replayed at exit 0, three open reviews all
   `new`, no pending re-checks, 0 link problems with the expected 5 IDENT lines, and
   `oeisbot stats --forms` byte-identical after the `cli.form_bucket` refactor (predicate 2,128,
   `a(n)` 1,029, print-loop 739, no usable function 905, list printer 443, helper 65, conjectural 7).
   **No database row and no pipeline run.**

   **Item 47 (2026-09-26) re-ran them and they matched**, except the two it changed by design:
   **412 passed** (398 + 14 new tests) and the `queue` line, 3,441 — 3,438 (`no_supported_program`
   1,415 — 1,418; the other two splits unmoved). Re-run and re-confirmed by command, not derived:
   26,814 candidates, 228 attempt rows with the same failure-mode histogram, 450 of 450 predictions
   replayed at exit 0, three open reviews all `new`, no pending re-checks, 0 link problems with the
   expected 5 IDENT lines. **Item 47 wrote no database row and ran no pipeline**, so the three sequences
   that left the pool (A162763, A349899, A351088) left it *derivationally* — the same "stale without a
   run" effect item 46 had. One number **not** in this checklist also moved and is worth knowing about:
   `oeisbot stats --forms` now has a seventh row, and re-measuring it showed the coverage table in
   [strategies](strategies.md#coverage-2026-09-26-snapshot) had been stale since item 46 (runnable
   3,925 — 3,896). Nothing guards that table either.

   **Item 46 (2026-09-25) re-ran every one of them and they matched**, except the two it changed by
   design: **398 passed** (390 + 8 new tests) and the `queue` line, 3,455 — 3,441. Unchanged and
   re-confirmed: 26,814 candidates, 228 attempt rows (ids 1-228), 450 predictions, 10 sessions, three
   open reviews all `new`, no pending re-checks, 450 of 450 replayed at exit 0, 0 link problems with the
   expected 5 IDENT lines. **Item 46 wrote no database row and ran no pipeline** — but note that it
   *did* move the `queue` numbers anyway, because the pool is derived from the code, not stored. That is
   the one way this page's counts can go stale without a run.

   **Session 10 (2026-09-24/25, history item 45) then moved most of them**, and the numbers above are
   its post-run values, re-derived from the database after the run. `predictions` went **45 → 450**,
   and `replay_predictions.py` was re-run against all of them: **450 of 450 replayed, exit 0**, with
   **8 trustworthy fits in 20 fitted projections** — the new one is #449 (attempt #209, A033852),
   whose projection then killed its own run at `over_prediction`.

   **A warning for whoever updates these numbers next.** The `389` in the `queue` line above was
   silently corrupted to `390` by a blanket `.replace("389", "390")` made while updating the *test*
   count — the two numbers happened to coincide, and the split stopped adding up to 1,818. Caught only
   by re-running the command. `tests/test_docs.py` guards the test total in its eight places; **nothing
   guards the database counts on this page**, so re-run the command and compare, never search-and-replace
   across the file.

   **Item 40 moved only the attempt count**, and that is the point worth carrying forward: its A194099
   run added row #176 with the new `searched_bound` mode, and the `queue` line did **not** move
   (3,464 / 1,851, the same split). That is the check behaving as designed — it is deliberately not a
   dead end, so the sequence stays in the pool and can be drawn again. `predictions` also stayed at 45,
   because the check fires before the first projection is ever made.

   If a count differs, the database has moved on from this page: trust the database and update the page.
   The **test** count is the exception: it is not a judgement call and not to be edited by hand.
   `tests/test_docs.py` compares it — and `development.md`'s per-file table and collected-counts
   paragraph — against what pytest collected in the same run, so a mismatch fails the suite and names
   what is stale. Take the new numbers from `python -m pytest --collect-only -q`. The same goes for
   `check_docs.py`'s expected-hits count, which it checks itself (history item 37).
   The `queue` line has moved twice. First from 3,494/1,822 (1391/388/43) to 3,479/1,836
   (1391/387/58). Two things changed it, and the
   totals do not balance unless both are known: session 7's runs retired 15 more sequences into
   `all_programs_dead_ends` (43 → 58, one of them moving out of `verify_out_of_reach`, 388 → 387, because
   dead ends are checked first), **and A385331 left the pool altogether** — its open review makes
   `select.candidates` (`select.py:136`) drop it from both the pool and the left-out tally, which is why
   3,479 + 1,836 = 5,315 against the earlier 5,316 PARI candidates.

   Then session 8 took it to **3,464/1,851 (1391/387/73)**: 15 of its 20 picks retired into
   `all_programs_dead_ends` (58 → 73) and the pool lost exactly those 15, with the total holding at
   5,315. The five that did not retire at these budgets are the four that used their whole 1,800 s
   extension — `db.is_dead_end`'s `extend_budget` clause needs the earlier run's
   `extra.extend_wall_s >= 10800`, and 1,800 is not — plus **A194099**, whose `over_prediction` kill
   retires a program at no budget at all, so it stays in the pool and can be drawn again. All of this was
   predicted before the run and matched exactly (history item 38).

   **The open review is the one piece of state that is waiting on the user**, not on the code — see
   [next steps](#open-offers-and-next-steps). Do not close it, submit anything, or re-run A385331 on your
   own initiative.

4. **Do not redo** the expensive setup: the oeisdata clone (2.3 GB), the model pull (9 GB) and `oeisbot
   setup` are done. Do not delete `data/`: it holds the attempt history.
5. **Work the way the user asks for** ("go slow and use a critic", "review your work as you go"): write a
   short plan with the evidence, have a separate agent critique it before coding, ask the user only the
   decisions that are theirs, implement with tests, break each new behaviour on purpose to prove a test
   fails (restore files byte for byte; line endings differ per file), have a separate agent audit the
   change without being told it looks right, fix, and send the fixes back to the same auditor. Check every
   number a reviewer reports before repeating it, re-deriving it from the raw data by your own method:
   in item 30 the check used the reviewer's method and inherited its bug (distinct run ids over a file
   whose ids repeat), and in item 33 the first sizing of a change was measured against the wrong pool.
   Before calling something a test gap, run the mutant against the whole suite, not only the test you
   have in mind -- and read the mutated line back, because a mutant that does nothing (item 33: a ``
   that became a literal backspace) looks exactly like an untested branch. Before a real run, write the
   expected results down. Where a measurement decides a design, make the measurement call the production
   function: in item 33 a separate scan of the same rule disagreed with it and the scan was the wrong one.
   Every stage so far found something the previous one missed (history items 11, 18, 21, 22, 23, 24,
   25, 26, 27, 28, 29, 30, 32, 33). The user's latest instruction (2026-09-20, item 33): "go slow and
   review work as you go to avoid defects"; earlier, "Implement G, H, and F one at a time. Break each
   item down into sections. Use a critic agent to stay on task" and, for D and E, "Go one item at a time
   and slow. Break down items into subitems when possible and use a critic agent to avoid defects" (the
   sections are in [the G, H, F task](#offers-g-h-and-f-one-at-a-time-done); one critic agent per item,
   reused through SendMessage for the audit and the re-check). Items 32 and 33 each ran a critic on the
   plan, mutation checks on every branch, and a separate auditor on the finished diff; both auditors
   found real defects, so keep all three stages. A change to the database itself (history
   item 28): a scratch script with a dry run on a `VACUUM INTO` copy, its rollback proven there, the
   critic's review of the script, a `VACUUM INTO` backup in `data/`, then one `BEGIN IMMEDIATE`
   transaction holding every read, write and check.

## Where things stand

- **Build:** all eight steps of the [design spec](design-spec.md) are implemented, with 587 passing tests.
- **Session 11 ran** (item 50, 2026-09-29): 25 PARI picks at the 60 s gate, 5 verified, **0 new terms**,
  2.78 h, 8.98 picks/h. Its lasting output is a **method and a defect class**, not a term. The method:
  read every pick's program before the run (`data/session11/progs.py`), pre-register a per-pick
  probability of verifying beside the pooled base rate, score both by Brier afterwards — the reading
  scored **0.0127 against the base rates' 0.1467**, calling all five verifiers and all twenty failures at
  <= .05 — and make the cost model use what the page proves (the one place the plan missed). The defect
  class: **four of 25 picks were program-selection misreads** (A274003, A335304, A290024, A373945; next
  steps 5, 7, (vi), (vii)), each predicted before the run with the detail its row would carry, and each
  now a dead end though the sequence was never tested. No code changed. Plan, write-up and evidence in
  `data/session11/`; the write-up was audited (20 findings, all held) and re-checked (6, all held).
- **A program its author calls conjectural is refused** (item 47, 2026-09-26): `pari.conjectural` reads
  the author's own disclaimer out of a `%o` part's comments — `conjectur[a-z]*|heuristic[a-z]*|unproved|
  unproven|not proved`, in a comment or string and never in live code — and `build_candidates` refuses
  every form that part could yield. The reason is that the **gate cannot help here**: conditional on a
  conjecture published in OEIS, the closed form reproduces every known term by construction, so
  verification learns nothing and the run emits values until `max_new_terms` stops it, which is exactly
  what session 10 did twice. Pool 3,441 — 3,438 (A162763, A349899, A351088), and **A162761, the one
  proved sibling of four, keeps its candidate**. The point is what it unblocks: **closing reviews #2 and
  #3 is now free**, in a model session too since item 48. See
  [strategies](strategies.md#programs-whose-author-calls-them-conjectural) and
  [known limitations](known-limitations.md#strategies).
- **…and it leaves the `--model` pool too** (item 48, 2026-09-26): `Runnable._why_not` returns
  `conjectural_program` with the model on as well, so the model is not drawn onto a sequence whose
  entry states a conjecture it could implement in Python — where verification cannot tell a
  re-derivation from a real result. Model pool 26,752 — 26,747. **Only the draw is blocked**:
  `oeisbot attempt A162763 --model` still runs, which is what made the trade cost 7 sequences of
  26,752 (0.03%); that asymmetry is deliberate and tested. The one limit still open is that such a
  deliberate run's prompt still quotes the `%C`/`%F` lines stating the conjecture — next-step (iv).
- **Program selection reads a block properly** (item 46, 2026-09-25): a `%o` part now offers **both**
  its function form and its own print loop, and `pari._drivable` refuses a def the drivers would
  call with a missing argument — gp binds such an argument to 0 rather than erroring, so the run
  silently computes something else. **There is deliberately no static check** deciding which form is
  right: one was written and measured **wrong on 5 of the 32 real blocks it was designed against**,
  so both are offered and the gate decides. Pool 3,455 — 3,441; A330204 and A366832 are back in it,
  A330204 on a print-loop candidate while its predicate form keeps attempt #227's `wrong_term` dead
  end. See [strategies](strategies.md#program-forms).
- **A term line cannot kill the sandbox's reader thread** (item 46, 2026-09-25):
  `verify.MAX_TERM_FIELD_DIGITS` caps a `@T` line's index, microseconds, work and bytes at 40 digits
  *before* `int()` runs. The term's **value stays exempt** and must: OEIS terms are legitimately
  unbounded. It closes the `OverflowError` entirely and the quadratic-`int()` stall only partly —
  both residues, and the one hole it widened in invariant 5, are in
  [known limitations](known-limitations.md#term-lines-from-an-untrusted-program).
- **Runtime provenance** (item 43, 2026-09-23): `setup_tools.runtime_versions()` records which gp and
  which sandbox Python produced a result — `meta` keys `gp_version` and `sandbox_python_version`, written
  at `oeisbot setup` and refreshed at every `oeisbot run`, plus a short `gp=2.17.4/GMP-6.1.2` token in
  each session's `note`, which is the half that survives a gp upgrade. `attempts.program_sha` already
  pinned the *program*; this pins the *runtime*, which nothing recorded before. A probe that cannot be
  trusted records `unknown` and never raises. It is the **only** code path that runs a sandbox runtime
  on the host rather than through `sandbox.run` — see [sandbox](sandbox.md#gp-outside-the-sandbox) before
  adding another. Rows written before this item are unattributable and deliberately not backfilled.
- **Resume is decided against** (item 42, 2026-09-23, by the user): the frontier item 41 records is
  still consumed by nothing, and should stay that way absent new evidence. It saves no machine time
  against a larger `--extend-s`, costs 2x on a find, and the design breaks
  [invariant 10](development.md#invariants). See history item 42 before re-opening it.
- **The searched-bound check** (item 40, 2026-09-22): when an entry's own `%C` comments publish a range
  already searched and empty, `verify.Harness._bound_exhausted` skips the extension if that range is out
  of reach at the rate just measured while verifying. **Predicate form only** — only there do term values
  equal the driver's work count, and `work` is hard-coded to 0 in the other two drivers. Replayed over
  the project's history it would have skipped **11,277.5 s, 55% of all predicate extension time**, and
  on A194099 it turned a 52.9 s run into an 8.0 s one. Deliberately **not** a dead end: the sequence
  stays in the pool and `extra.verified_scan_to` records how far the run's own scan actually reached, as
  distinct from the entry's unverified claim. A bound is only ever a reason to stop spending time —
  never evidence about a term. See
  [verification](verification-and-estimation.md#the-searched-bound-check) and
  [known limitations](known-limitations.md#searched-bounds).
- **The cost fit's statistics are recorded** (item 36, 2026-09-21): `predictions` has
  `fit_trustworthy`, `fit_npoints`, `fit_disagreement`, `fit_climbing` and `rate_drift`, all NULL
  together exactly when nothing could be fitted, and the 40 pre-existing rows were backfilled by
  replaying their term logs. A query can now answer "has a trustworthy cost fit ever happened?": **7 in
  19 fitted projections** (6 in 18 before session 8), five from attempt #139, one — prediction #18,
  A229209 — that session 7's audit had missed, the only row where a sound fit was withdrawn from the kill
  by the rate drift alone, and one from session 8 (prediction #45, A194099) that is the project's first
  *optimistic* trusted projection and the only one ever to fire an `over_prediction` kill.
  `trustworthy` keeps its old meaning (the kill's permission). The item also corrected its own premise:
  what was genuinely unrecoverable is `rate_drift`, and `npoints` on the `exp` rows — the rest was
  derivable from columns that already existed. Details and the full accounting in
  [data and schema](data-and-schema.md#predictions-one-row-per-projected-term).
- **The documentation's numbers are machine-checked** (item 37, 2026-09-21): `tests/test_docs.py`
  compares the test total, the per-file table and the collected-counts paragraph against what pytest
  collected in the same run; `tests/test_replay.py` covers `scripts/replay_predictions.py`, which had
  none; two tests in `test_db.py` pin the whole `verify.Prediction`-to-column mapping; and
  `check_docs.py` checks its own expected-hits count. **Adding a test now fails the suite until the docs
  catch up** — take the new numbers from `pytest --collect-only -q`, never by hand.
- **The first win** (session 7, 2026-09-21): **A385331 extended by 18 terms, a(25)..a(42)**, in
  `artifacts/A385331/attempt-139/` with an open `reviews` row **still awaiting the user**. Steps 2-7 of
  the review checklist are done (item 44, 2026-09-23), **step 6 included**: an independent check by a
  different method — modular inverses rather than the Fermat reduction the entry and the first
  re-derivation share — reproduced all 23 known terms and confirmed all 18 new ones, and for n up to 10
  the real integer `N(n)` was factored directly with no modular arithmetic at all. **Step 7 was re-run on
  2026-09-28** (item 49) and still passes, and the step-8 material is assembled in
  `data/review1/SUBMISSION.md`. **Nothing has been submitted to OEIS, the pipeline never will be, and the
  review row is untouched**: steps 8 (submit) and
  9 (record) are the user's. Because `.gitignore` excludes `artifacts/` and `data/`, the win and its
  review evidence (`data/review1/`) exist only on this machine. History items 35, 44 and 49.
- **The smaller follow-ups** (item 34, 2026-09-20): a pending win is saved as JSON rather than a pickle
  and its fields are checked against the code when it is read back; a win that keeps failing its
  re-check now says how often it has failed the same way (and is still retried for ever); the
  `infeasible` dead end keys on the memory cap a run actually got, not the one it asked for; `sync` no
  longer leaves `sequences.difficulty` stale; a capped `run -n` says so; and `verify.on_line`'s
  unreachable `incomplete` guard was kept deliberately, with a test and the reason recorded.
- **A run that produced nothing says why** (item 32, 2026-09-20): `verify._stderr_tail` puts the last
  three stderr lines that say something into the `detail` of an `incomplete`, and of any other
  `verify._TAIL_STOPS` stop that produced no term. A gp program can fail and still exit 0, so without it
  nothing recorded said why. `extra.log` is left unset when no term log was written, the kept Python
  program is named as `extra.program`, and a session log line carries 300 characters of a detail.
- **PARI blocks calling another entry's helper are rejected** (item 33, 2026-09-20):
  `pari.undefined_a_numbers` finds an A-number a program calls or indexes but never defines — those
  helpers live in a different OEIS entry and gp errors as soon as it reaches one. 65 sequences leave the
  PARI-only pool (1.97% of its pick weight, ~0.39 picks per 20-pick session) and 5 more lose one of two
  programs. All 71 rejected candidates were run first: none reproduced its known terms.
- **Selection and the model after PARI** (session 5, 2026-09-18): the verify budget is a 60 s first pass,
  timed-out programs are dead ends up to the time they already ran, provably hopeless predicate searches
  are not run, sessions no longer pick sequences an attempt could only skip, and with `--model` a PARI
  program that verifies but finds nothing new hands over to the model. Planned with a critic, audited
  independently, re-checked. History items 17-20.
- **Over-prediction kill** (offer B, 2026-09-18, after session 5): only a trustworthy projection can kill
  a term now; an untrustworthy one leaves the term to the extension budget. History item 21. **Still the
  only one of the three never exercised on a real run** as of session 7: no projection whose *cost fit*
  was untrustworthy has had its term approach twice its `seconds_high`. Note the database cannot show
  this directly — A229209's row has `predictions.trustworthy = 0` and its term ran 1,800 s against a
  795 s threshold, but that row's fit *was* trustworthy and it was offer A's rate-drift test, not offer
  B, that suppressed the kill (`predictions.trustworthy` stores `Assessment.trusted`; see
  [data-and-schema](data-and-schema.md#predictions-one-row-per-projected-term)).
- **Rate drift** (offer A, 2026-09-18): nor can a projection whose seconds per cost unit, projected to
  the next term, exceed the rate it was converted with by more than the kill factor (2). The estimate
  itself is not corrected. History item 23. **First exercised in session 7** (A229209, `rate_drift`
  7.79): pre-offer-A the term would have been killed at 795.4 s; it ran its full 1,800.4 s and produced
  nothing, so on its one sample the rule was a pure cost (item 35).
- **The list contract** (offer C, 2026-09-19): for a sequence the model judges to be a list of numbers
  with a property, and whose known terms strictly increase, it writes `members(work)` and a driver
  numbers the members; a program identical to one that already failed the same way is not run.
  History item 24.
- **Held-out values in retries** (offer G, 2026-09-19): a failure description no longer shows a program
  value equal to a held-out term that the prompt does not already show (either sign); text the program
  wrote itself (a crash's message, the stderr tail, a printed line that became a `protocol` stop) is
  still passed on (known limitation). History item 25.
- **No rerun after a timeout** (offer H, 2026-09-19): within one model stage, a program identical to one
  that ran out of the verify budget is not run again either (`codegen.REPEATS_IN_STAGE`); it uses up its
  generation like any other repeat. History item 26.
- **No infeasible stop on an untrustworthy projection** (offer F, 2026-09-19): only a trustworthy cost
  fit can stop a run as infeasible on time (memory is checked as before), so a run whose projection is
  untrustworthy goes on until its term arrives or its extension is used up. History item 27. **This is
  the rule that produced the project's first win.** In session 7 it acted six times on attempt #139,
  including on a projection of 3.49e+08 s for a term that cost 0.0006 s; without it the run stops at
  a(32) with 8 new terms instead of a(42) with 18 (item 35).
- **Failure penalty per attempt** (offer D, 2026-09-19): the selection's ×2 counts attempts (one
  `attempt_sequence` call, its run rows sharing `extra.attempt_call`), not program runs; the existing
  rows were backfilled once, after a backup. History item 28.
- **No hold-back** (offer E, 2026-09-19): once one of an entry's PARI programs is a budget dead end, a
  later attempt at that budget runs the next one, with its own extension. History item 29.
- **The flaky test fixed** (2026-09-19): the extension's infeasible stop is now tested in memory with
  controlled times (`test_estimate.py`), and the sandbox only has to end a run on that stop, with no
  extension time (`test_verify.py::test_infeasible_stop_ends_the_sandboxed_run`); no test asserts on
  sub-second real timings any more. Nothing under `oeisbot/` changed. History item 30, which also
  corrects item 27's claim that offer F had made the test flakier.
- **Extension dead end** (2026-09-18): a verified run that used its whole extension without a new term,
  on at least 80% CPU, is not repeated at the same or a smaller `--extend-s`; the entry's other PARI
  programs get their turn in later attempts (since offer E; it held them back until then). History items
  22, 29.
- **Fixes after the build** (session 3, 2026-09-17): the four offers from the end of session 2 are done,
  an independent audit of those fixes was addressed, the `fini` mismatch is fixed and the test suite grew
  from 92 to 141 tests. See history items 10 and 11.
- **Docs:** complete and independently audited against the code (23 findings, all fixed), and updated
  and audited with every change since (session 3, session 5, offer B, the extension dead end, offers A,
  C, G, H, F, D and E, the flaky-test fix, sessions 6 and 7, and items 31-35). Session 7's own doc pass
  was audited the same way and **29 findings came back**, most of them stale counts this page had
  carried since earlier sessions (`README.md` still said "no new terms", the b-file and attempt totals
  had drifted, and four `verify.py:113` citations pointed at a blank line); all are fixed.
- **Real runs:** 207 sequences attempted, 277 program runs, **1 genuine win** (A385331, 18 new terms,
  session 7; 42 runs verified in all, and 3 `extended` — the other two extensions are session 10's
  conjectural false wins, reviews #2 and #3, now `rejected`). 18.6 machine-hours. **Re-derived by query
  2026-09-30 after session 12 (item 52)**; `sequences attempted` counts distinct A-numbers over every
  attempt row, skips included, as `data/item49/recheck_numbers.py` defines it (204 without skips).
  **Re-derived by query 2026-09-29 after session 11 (item 50)**, and before that on 2026-09-28 (item
  49), which found these left at the `id <= 175` snapshot — 107 sequences, 173 runs, 12.3 h — since
  before item 40's run and the whole of session 10.
  Database session 4 showed that
  verification, not extension, is the binding constraint (history item 16). Session 5 measured the
  quick-first-pass selection: 0 wasted picks, 3.6× the program runs per hour of the earlier PARI-only
  sessions and about 3× the runs past the known terms per hour, but the same per-run pass rate (3 of 22)
  and still no new term (item 19). The model, given its first correct-but-slow PARI programs, failed all
  9 generations, 8 of them on index bookkeeping (item 20). After offer B, session 5's two killed
  sequences ran again and each used its whole 300 s extension (item 21). With the list contract the
  model verified two sequences at the first try and had no `bad_index` in 20 runs, but found no new
  term (item 24). Session 6 ran the full-extension probe at the same budgets: 4 of 20 picks verified and
  each used its whole 1800 s, but none had a fittable cost history, so it neither confirms nor challenges
  offers B, A and F; its lasting results are the 10-known-term ceiling and the never-trustworthy
  projection (item 31). **Session 7 broke the drought**: A385331 verified 24 known terms in 0.157 s and
  produced 18 new ones, offer F acted six times to let it get past a projection of 3.49e+08 s for a term
  that cost 0.0006 s, and the 600 s gate it was run to test turned out to buy nothing (item 35).
  **Session 8 settled the gate question** — 8.96 picks/h against session 7's 4.78, 1.88x, 83% of it the
  gate — and produced the first *optimistic* trusted projection (A194099, a(29) at 22.3 s for a term the
  entry says is beyond 2x10^38), which only `over_prediction` caught (item 38). Details
  in [known limitations](known-limitations.md#observations-from-real-runs).
- **Git:** the user committed and pushed everything up to session 4 themselves (`1b6881d` "started oeis
  bot", on `main`). On 2026-09-19, at the user's request ("Commit and push before we start"), session 5,
  offer B, the extension dead end and offers A, C, G, H, F, D and E were committed and pushed as
  `5e4665a` (after 256 tests passed and `origin/main` was checked unchanged). Three more commits follow
  it, each at the user's request: `63cc9ae` (the flaky-test fix, history item 30, tests and docs only),
  `f325786` (items 32 and 33) and `3dacfb8` (the git TLS flag in CLAUDE.md). On 2026-10-14, again at the
  user's request ("Commit and push"), **`f0081d9` landed items 34 and 36 to 54 and everything from
  sessions 7 to 12 in one commit**, and it is `HEAD` and `origin/main`; nothing is uncommitted. What it
  holds is in [what is committed](#what-is-committed), the one place to update when this changes (the
  bullet and the two paragraphs in the header have drifted from it before). Do not commit or push
  unless the user asks. `.gitignore` excludes the local state below.
- **Background processes:** none. The Ollama tray app keeps its server running on port 11434.

### Local state on this machine (not in git)

| Item | State |
|---|---|
| `.venv/` | Python 3.11.9 venv with the package installed editable (`-e ".[dev]"`) plus fastapi, uvicorn, httpx |
| `tools/python/` | embeddable CPython 3.11.9 with gmpy2 2.3.1, sympy 1.14.0, mpmath 1.3.0, precompiled |
| `tools/pari/gp.exe` | PARI/GP 2.17.4 standalone |
| AppContainer `OEISBot.Sandbox` | profile created; read grants on `tools/python`, `tools/pari`; modify grant on `data/scratch` |
| `data/oeisdata/` | synced to commit `956668977564dbec38a657dafa875f021b4d052b` at 2026-09-17 13:06 UTC; the candidate table was rebuilt from that same checkout after the `fini` fix (`sync --no-pull`) |
| `data/oeisbot.sqlite3` | **Item 54 (2026-10-13) added two tables, `pick_snapshots` (1 row: the PARI pool, 3,357 candidates, rules `af16ba7ce8d3`) and `pick_snapshot_rows` (3,357 rows); every count below is unchanged** (checked by `data/item49/recheck_numbers.py`). **Re-derived 2026-09-30 after items 51 and 52 (session 12, then the offer (a) backfill): 280 attempt rows (ids 1-280; 48 of them with a backfilled `program_sha`), 12 sessions, 456 predictions, 3 reviews (#1 `new`), 26,814 sequences; `queue` 3,357 / 1,958 (1432 / 383 / 143) after item 53; `queue --all` 26,745 / 18** — checked by `data/item49/recheck_numbers.py`, re-baselined the same day. Before that: **Re-derived 2026-09-29 after session 11 (item 50), by query, not by hand** — first re-derived 2026-09-28 (item 49), when this row had been left at session 7's numbers and was wrong on five counts after session 10. 26,814 candidates; **11** sessions; **253** attempt rows by outcome (207 `failed`, 40 `verified`, **3 `extended`**, 3 `skipped`) over **182** distinct sequences; **455** predictions; **3 reviews** — #1 A385331 `new`, #2 A162762 and #3 A162764 `rejected` (item 49). 44 rows have no `session_id`: standalone `oeisbot attempt` runs, including the A129250 re-attempt, the 12 rows of the step-2 run (history item 20), the 2 rows of the offer-B check (item 21), the 20 rows of the offer-C measurement (item 24) and the 3 rows of session 7's targeted P4 probe (item 35). A copy taken just before session 5 is in that session's scratchpad only, not in the repo. Since offer D (2026-09-19) the run rows carry `extra.attempt_call` (`legacy-<first row id>` for the pre-D ones), **202** distinct attempts — counted the way `select.candidates` counts them, `COALESCE(json_extract(extra,'$.attempt_call'), 'row:'||id)`, so the 3 rows with no `extra` at all (ids 1, 5, 11, all `skipped`) each count as one; the distinct non-null `attempt_call` values number **199**. The failure penalty uses the same COALESCE but only over `failed`/`verified` rows, so no skip reaches it; see the backups below |
| `data/oeisbot-before-offerD.sqlite3` | a copy of the database (`VACUUM INTO`, checked table by table) taken just before offer D's backfill wrote `extra.attempt_call` into the 108 run rows on 2026-09-19; nothing else in the database was changed. Safe to delete once D is accepted |
| `data/oeisbot-before-session6.sqlite3` | a copy (`VACUUM INTO`, integrity-checked: 111 attempt rows, 26,814 sequences) taken just before session 6 on 2026-09-19, so the pre-run pool can still be rebuilt now that the run has changed it (history item 31 uses it for the H10 pool comparison and the wasted-pick sizing). Safe to delete once item 31 is accepted |
| `data/oeisbot-before-session8.sqlite3` | a copy (`VACUUM INTO`) taken just before session 8 on 2026-09-21: 155 attempt rows, 40 predictions, 7 sessions. Lets session 8's pre-run pool be rebuilt now that the run has moved it. Safe to delete once item 38 is accepted |
| `data/oeisbot-before-searched-bound.sqlite3` | a copy (`VACUUM INTO`) taken on 2026-09-22 just before item 40's end-to-end check of the searched-bound stop: 175 attempt rows, 45 predictions. The only change after it is row #176 (A194099, `verified` / `searched_bound`). Safe to delete once item 40 is accepted |
| `data/oeisbot-before-fit-stats.sqlite3` | a copy (`VACUUM INTO`) taken on 2026-09-21 just before item 36 altered `predictions` in place -- five new columns, `schema_version` 1 -> 2, 18 rows backfilled. **Named in `CLAUDE.md` and in "Changes git cannot see" but missing from this table until item 49's audit.** Safe to delete once item 36 is accepted |
| `data/oeisbot-before-session10.sqlite3` | a copy (`VACUUM INTO`) taken just before session 10 on 2026-09-24: 176 attempt rows, 45 predictions, 9 sessions. Lets session 10's pre-run pool be rebuilt now that its 52 rows have moved it. **Was referenced nowhere outside the disk until item 49's audit.** Safe to delete once item 45 is accepted |
| `data/session10/` | 49 files: session 10's pre-registration, logs and write-up working files (referenced from history item 45). Safe to delete once item 45 is accepted |
| `data/item47/` | 9 files: item 47's corpus measurement and mutation script, to re-run before widening `pari._CONJECTURAL`. Safe to delete once item 47 is accepted |
| `data/item48/` | 2 files, including `mutate48.py` -- re-run it before changing `Runnable._why_not`'s model branch, `pari.rejected_as_conjectural`, `CONJECTURAL_REASON` or `cli.form_bucket`. Safe to delete once item 48 is accepted |
| `data/oeisbot-before-close-reviews23.sqlite3` | a copy (`VACUUM INTO`, `pragma integrity_check` ok, all three reviews still `new`) taken on 2026-09-28 just before item 49 set reviews #2 and #3 to `rejected`. The only difference from the live database is those two rows' `status`, `note` and `updated_at`. Safe to delete once item 49 is accepted |
| `data/oeisbot-before-session11.sqlite3` | a copy (`VACUUM INTO`, `pragma integrity_check` ok) taken on 2026-09-29 just before session 11: 228 attempt rows, 10 sessions, 450 predictions, 3 reviews, 5,664,768 bytes (`data/session11/backup.txt`). Lets session 11's pre-run pool be rebuilt now that its 25 rows have moved it; `predict_fixed.py` uses `id <= 228` for the same purpose. Safe to delete once item 50 is accepted |
| `data/oeisbot-before-session12.sqlite3` | a copy (`VACUUM INTO`, `pragma integrity_check` ok) taken on 2026-09-30 at 13:30 EDT just before session 12: 253 attempt rows, 11 sessions, 455 predictions, 3 reviews; 5,685,248 bytes (`data/session12/backup.txt`). |
| `data/oeisbot-before-backfill.sqlite3` | a copy (`VACUUM INTO`, integrity ok, 280 attempt rows, 5,701,632 bytes) taken on 2026-09-30 at 14:32 EDT, after session 12 and just before the offer (a) backfill rewrote `program_sha` on 48 rows in one transaction (`data/offerA/backfill_apply.txt`); every changed row carries `extra.program_sha_backfilled = {from, on, item}`. |
| `data/oeisbot-before-pickmap.sqlite3` | a copy (`VACUUM INTO`, `pragma integrity_check` ok, 280 attempt rows, 5,718,016 bytes) taken on 2026-10-13 just before item 54 wrote snapshot #1. It already holds the two *empty* pick tables (see item 54's disclosure), and is otherwise the database as session 12 and the backfill left it. |
| `data/item54/` | 6 files and a `mutation/` folder of 9, local state like the rest of `data/`: `README.md` (what each file is and how to re-run it), `area_spread.ts` / `area_spread.txt` / `pickmap_pari.json` (how faithfully the map draws area in proportion to chance: the script, its output, and the saved `/api/pickmap` response it reads), `critic.txt` (the critic's report on the plan), `audits.txt` (the five audits' reports), and `mutation/` (the harnesses, the specs and the output of the final mutation run: 261 Python and 21 TypeScript mutants, the seven survivors explained in the README) |
| `data/session12/` | 39 files with a `README.md`, plus `check/` (7: my re-derivation of the pre-run critic), `critic/` (47: the critic's own probes and `findings.md`) and `audit/` (the post-run auditor's scripts and `findings.md`): session 12's pre-registration (`planS12.md`, `planS12-v1-precritic.md`), evidence scripts and outputs, `resultsS12.md`. Referenced from history item 52. Safe to delete once that item is trusted. |
| `data/measure0930/` | 19 files: item 51's measurements — `shapes.py` (loop starts, helper-beside-predicate, bulk-printer signal, the A-name check before and after), the two candidate snapshots and `diff.txt` (the parser change as a diff), `headonly.txt`, `valuedep_replay.py` / `valuedep.txt`, `riskflags_replay.py` / `riskflags.txt`, `wolfram_scoping.md`, and item 53's third snapshot with `diff2.txt` and `pools_after_item53.txt`. All read-only; each is cited from item 51 and the next-steps list. |
| `data/offerA/` | 7 files: `recount.py` / `recount.txt` (the 2026-09-30 recount of offer (a)), `backfill.py` (dry run by default, `--apply` writes), `backfill_dryrun.txt`, `backfill_apply.txt`, `pools_after.txt` (the pool lines after the backfill). |
| `data/session9/` | 17 files: the measurement of next step 1 and the build that followed. `README.md` explains how to run them; **`resultsS9.md` is the one to read** (the write-up as corrected by its audit), with `planS9.md` / `planS9-v1-precritic.md` (nine must-fix defects between them) and `planBUILD.md` (seven more) as the pre-registrations, `labels.jsonl` as the 241-entry hand census, and five read-only scripts (`bounds.py`, `reach.py`, `rates.py`, `retro.py`, `sample.py`). Safe to delete once items 39 and 40 are accepted |
| `data/review1/` | 5 files. The independent check that discharged step 6 of review #1 (history item 44): `indep_A385331.py` (run it with `tools\python\python.exe` -- gmpy2 and sympy live in the sandbox runtime, not the venv), `deep_sweep_output.txt` (the 775 s sweep of 11,078,935 primes to 2x10^8: 41 agree, 0 disagree, 0 unsettled) and a `README.md` with the whole account and the checklist's state. Then the step-8 package (item 49): `SUBMISSION.md` (the re-run step 7, the DATA line, the `%E` line, and the b-file rules checked one by one) and `b385331-submit.txt` (the artifact b-file plus the required trailing blank line; **rename it `b385331.txt` before uploading**). **Do not delete while review #1 is open** -- it is the evidence behind it |
| `data/item49/` | 7 files with a `README.md`: item 49's working scripts. **`recheck_numbers.py` is the one to re-run** -- it checks ~30 documented numbers against the database, the disk, `git status` and the live `queue` lines, and exits non-zero on a mismatch; `tests/test_docs.py` guards the test totals and nothing else, which is where this item's audit found a week of drift. Also `pool_check.py` (both pools through the real `select.candidates`), `gate_check.py`, `step7.py` (the review checklist's step 7 via `attempt.recheck`), `check_bfile.py` (a b-file against every SubmitB.html rule) and `build_package.py`. Safe to delete once item 49 is accepted, except `recheck_numbers.py` if the pattern proves worth keeping. **Its expectations were updated to session 11's counts on 2026-09-29 and re-baselined on 2026-10-13 (567 tests, 46 modified, 13 untracked, and a check of the snapshot tables)** |
| `data/session11/` | 38 files with a `README.md`: session 11's pre-registration (`planS11.md`, and `planS11-v1-precritic.md` before its critic), the write-up as corrected by its audit (`resultsS11.md`), the read-only scripts behind them with their outputs (`prepicks`, `preevidence`, `progs`, `baserates`, `prebounds`, `rates`, `predict`, `checkcritic`, `backup`, `postrun`, `postcheck`, `brier`, `checkaudit`, `predict_fixed.py`, `pools_post.txt`). **`progs.py` + `predict.py` + `brier.py` is the per-pick method the next plan should reuse.** Safe to delete once item 50 is accepted |
| `data/item42-43/` | 10 files with a `README.md`: items 42 and 43's working files, copied out of the temp scratchpad so they survive. **`planRESUME2.md`** is to be read before ever re-opening resume, and **`mutate43.py`** re-run before changing `runtime_versions` or `db.set_meta_many` (24 mutations, 23 caught; line-ending aware). Safe to delete once items 42 and 43 are accepted |
| `data/item46/` | 12 files and a `critic/` subfolder with 8 more, all with a `README.md`: item 46's evidence, harnesses and the critic's scripts from all three of its passes. **`mutateA.py`** is to be re-run before changing `verify.on_line`'s parse block, `pari._drivable` or `build_candidates`' structure (13 mutations, 13 caught; whole suite per mutation; line-ending aware). **`classify_m1.py` is kept as the record of a mistake** -- the static check that was measured wrong on 5 of 32 and therefore does not ship. **`pool_diff.py`** reproduces the 3,448 -> 3,434 diff by emulating the old builder on top of the new code. Safe to delete once item 46 is accepted |
| `data/runs/` | **290** files (268 until session 12 added 22 on 2026-09-30 — five of its 27 runs accepted no term and so wrote no log; 247 until session 11 added 21 on 2026-09-29 — four of its 25 runs accepted no term and so wrote no log; 198 until session 10 added 49) (term logs and generated programs from the runs above; a run that stopped at its first term has no term log, so 35 of the older run rows name one that was never created. Rows written since the item-32 fix leave `extra.log` out instead) |
| `data/pending/` | exists and is **empty**. Created by session 7's win, which saved `attempt-139.json` before its re-check and deleted it after the re-check succeeded, so only `_save_pending` has ever run — `_load_pending` is still unexercised |
| `data/session8/` | 16 files (a `README.md` explaining how to run them, plus 15): session 8's prediction page (`planS8.md`, and `planS8-v1-precritic.md` before its critic), the corrected write-up (`resultsS8.md`) and the 10 scripts plus 2 JSON fixtures behind them. Copied out of the temp scratchpad so they outlive it. `nomoreterms.py` measured what became next step 1; `data/session9/` supersedes it. Safe to delete once item 38 is accepted |
| `data/*.log` | `session12_pari.log` (session 12's console, 2026-09-30), `clone.log`, `session1.log`, `session2_model.log`, `session3_real.log`, `session5_probe.log`, `session5_model_step2.log`, `session6_pari.log`, `session7_pari.log`, `session8_pari.log`, `p4_probe.log`, `offerB_check.log`, `offerC_measure.log`, `bfile_sweep.log`, `model_smoke2.log`, `ollama_pull.log`, `session10_runA.log`, `session10_runB.log`, `session11_pari.log` (console output of earlier runs; safe to delete). `session6_pari.err` was created empty and stays empty |
| `data/bfiles/` | **71** files in 55 subfolders, but still 68 b-files as far as the code is concerned: **three** oeis.org re-checks cached OEIS's synthesized b-file -- session 7's for A385331 and session 10's for A162762 and A162764 -- and `bfile.cached` ignores them because they have no LFS pointer. (Was written as 69 files and one synthesized copy; re-counted 2026-09-28, item 49.) Harmless dead weight. `fetch-bfiles` has resolved every candidate: 68 have a b-file, 26,746 do not |
| `artifacts/` | **Three** folders, not one (re-counted 2026-09-28, item 49). **`A385331/attempt-139/`** — the project's first win: README, `b385331.txt`, `executed.gp`, `program.gp`, `predictions.csv`, `run.json`, `timing.csv`, `verification.md`. Then **`A162762/attempt-186/`** and **`A162764/attempt-191/`**, session 10's two conjectural false wins (8 files each), whose reviews are `rejected` — keep them as the record of what was rejected and why; they must never be submitted. Not in git |
| `dashboard/node_modules/`, `oeisbot/dashboard/static/` | installed and built (rebuilt 2026-10-13 after item 54's Pick map tab; before it 2026-09-30 after item 51's inbox identity block and below-bound warning; `npm run build` needs `NODE_USE_SYSTEM_CA=1` on this machine) |
| Ollama | 0.34.1, installed with `winget --source winget`; `qwen2.5-coder:14b` pulled; runs 100% on GPU at 8k context |

### Machine facts that shaped the design

- Windows 11 Pro, Intel i5-9600K (6 cores), 32 GB RAM, RTX 4070 (12 GB VRAM), about 44 GB free disk at
  the start.
- No WSL, no Docker, no Hyper-V. This is why the sandbox is native Windows (Job Object + AppContainer)
  rather than the spec's `setrlimit` + container.
- HTTPS is intercepted by a local certificate (antivirus or proxy): uv, git, npm and winget each need their
  system-store workaround (see [operations](operations.md#tls-errors-on-downloads)). Python's `urllib`
  works as is.

## Decisions

| Decision | Made by | Recorded in |
|---|---|---|
| Native Windows sandbox (Job Object + AppContainer) instead of WSL2/Docker | proposed by the assistant when the machine turned out to have neither; the user continued with it | [sandbox](sandbox.md), [design spec](design-spec.md#part-2-implementation-map-and-deviations) |
| Use oeisdata's Git LFS pointer files to decide whether a b-file exists and whether the cache is stale | assistant, on finding the pointers | [pipeline](pipeline.md#b-file-lookup-ingestbfilefetch) |
| Support PARI print loops by rewriting them, with every rewrite flagged | assistant, after measuring coverage (61% → 75%) | [strategies](strategies.md#program-forms) |
| Install Ollama and `qwen2.5-coder:14b` | user | this page |
| Hold out known terms from the model, reject copied literals, redact held-out values | assistant, after the model hard-coded known terms | [strategies](strategies.md#why-the-defenses-exist) |
| Do not commit yet | user ("Do not worry about committing for now") | this page |
| Docs for the operator and for contributors/AI agents; README + `docs/`; keep the original spec with a deviation map; document code/intent mismatches as-is without code changes | user, answering the documentation questions | these docs |
| Fix the re-check crash, the infeasible dead end, the holdout gap and near-zero `censored_s` | user accepted all four offers (session 3) | [pipeline](pipeline.md), [verification](verification-and-estimation.md) |
| Holdout for short sequences: always hold out 2 known terms, no model below 3 known terms (rather than refusing below 5, or requiring a b-file) | user chose among three options | [strategies](strategies.md#what-the-model-is-shown) |
| A run with new terms is recorded as `recheck_pending` and its result saved to `data/pending/` *before* the re-check (as a pickle until 2026-09-20, JSON since: item 34); network errors are retried twice in place; an unfinished re-check is retried by `oeisbot recheck` and at each `oeisbot run`; no artifact until a re-check succeeds | assistant (the user's offer said "record with a clear outcome, retry later"); save-first ordering added after the audit showed Ctrl+C during the retry waits could still lose a win | [pipeline](pipeline.md#7-re-check-and-artifact-only-when-new-terms-were-found), [operations](operations.md#a-win-whose-re-check-failed-recheck_pending) |
| With `--model`, sequences with no PARI program and fewer than 3 known terms (after their b-file lookup) leave the selection pool | assistant, after the audit noted they would otherwise be re-picked and skipped every session | [pipeline](pipeline.md#2-selection-oeisbot-run--n-n---alpha-a---seed-s---model) |
| Infeasible dead ends are keyed on `extend_wall_s` and memory, stored in `attempts.extra` (no schema change); since 2026-09-20 the memory half is the *effective* cap `mem_cap_bytes`, not the configured `mem_bytes` (item 34) | assistant | [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first) |
| No long default-budget run yet | user ("Not yet", session 3) | this page |
| Stop excluding `fini` from candidates, and fill the known test gaps | user ("Tackle these small defects...", session 3) | [pipeline](pipeline.md#1-sync-oeisbot-sync---no-pull), [development](development.md#tests) |
| Make the retry prompt depend on the failure type, before running another session | user ("Tackle the failure-type-aware retry prompt before the run", session 4) | [strategies](strategies.md#steps) |
| Do steps 1 (cheaper candidates: a quick first pass) and 2 (the model after a correct-but-slow PARI run) together, then a real session; go slow and use a critic | user (session 5) | history items 17-20 |
| Default verify budget 600 s → 60 s, model programs included | user chose it among two options | [verification](verification-and-estimation.md#budgets) |
| Test run in two parts: a PARI-only session of 20 picks (60 s verify, 1800 s extend), then `attempt` with `--model` on the three known correct-but-slow sequences | user chose it among three options, after the critic showed a `--model` session would blur the step-1 measurement | history items 19-20 |
| A timed-out program is a dead end for any verify budget no longer than its recorded `runtime_s` (so older attempts count); predicate searches get a static bound (`PREDICATE_MAX_RATE` 2 × 10^7 calls/s); selection and attempts share `attempt.pari_plan`; selection reads b-files only from the cache | assistant, reviewed by the critic and the audit | [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first) |
| The model is told when the entry's program already verified (also from an earlier attempt), and the reviewer gets a "compare with the entry's program" warning | assistant (critic and audit) | [strategies](strategies.md#what-the-model-is-shown) |
| Leave the failure penalty counting rows (a `--model` attempt can add up to 6 doublings) until the user decides | assistant; open offer D until the user chose per attempt on 2026-09-19 (rows below) | [strategies](strategies.md#failure-penalty) |
| Do offer B first | user ("Start with B", after the roadmap question) | this page |
| Only a trustworthy projection (disagreement ≤ 3, at least 4 points) can kill a term; no larger grace for untrustworthy ones; the wall-per-work rate gap stays with offer A | assistant, reviewed by a critic, which also found the rate gap | [verification](verification-and-estimation.md#assessment-estimateassess), [known limitations](known-limitations.md#verification-and-estimation) |
| Make a verified run that used its whole extension without a new term a dead end, before a long session | user ("Yes before a long session make such runs dead ends") | this page |
| Key that dead end on `extend_wall_s` only (not memory) and require at least 80% CPU over the run's wall time; word the log and skip detail by stop reason | assistant; the CPU guard proposed by the critic, the wording fixed after the audit | [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first), [verification](verification-and-estimation.md#stop-reasons) |
| An `infeasible` or `extend_budget` dead end holds back the entry's other PARI programs at that budget (a verified run already ended the PARI stage within one attempt); a program broken after verifying holds nothing back | assistant, after the audit found siblings would otherwise get the full extension in the next attempt; reversed by the user on 2026-09-19 (offer E, rows below) | [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first), [strategies](strategies.md#order-and-limits) |
| Offer A: withdraw trust (so no kill) when the rate drifts; keep the over-prediction kill otherwise | user ("Drift check only", over turning the kill off by default or stretching the kill point) | [verification](verification-and-estimation.md#assessment-estimateassess) |
| Offer A: do not correct the estimate in seconds for a growing rate | user ("Leave the number", over extrapolating the rate or taking the higher of work and wall-time projections) | [known limitations](known-limitations.md#verification-and-estimation) |
| Measure the drift as the rate projected to the next term over the rate used, and compare it with `over_prediction_factor`, for both cost units (instead of a per-term growth threshold of 1.25) | assistant, adopting the critic's proposal: no new constant, the same result on the replay | [verification](verification-and-estimation.md#assessment-estimateassess) |
| Offer C: the model writes `members(work)` for a list (rather than `isok(k)`, with or without a members fallback) | user ("members only") | [strategies](strategies.md#the-list-contract-memberswork) |
| A program repeating one that already failed the same way is not run and uses up its generation (rather than re-asking without counting it, or running it) | user ("Don't run, count it") | [strategies](strategies.md#steps) |
| Measure offer C on ten sequences at `--verify-s 60 --extend-s 120` | user ("Ten sequences, 60/120 s") | this page |
| Ask list-or-function as a question of its own, only when the known terms strictly increase | assistant, after the same question folded into the classify prompt missed 2 of 44 | [strategies](strategies.md#the-list-contract-memberswork) |
| Under the list contract a held-out wrong term shows neither value, and the driver's errors name positions only | assistant, from the critic | [strategies](strategies.md#steps) |
| Offer G: hide a program value equal to a held-out term (either sign) in `wrong_term` and `bad_index` details; leave a crash's message and stderr tail as a known limitation | user ("Details only") | [strategies](strategies.md#steps), [known limitations](known-limitations.md#strategies) |
| Offer H: a `verify_timeout` makes a repeat within the model stage (`codegen.REPEATS_IN_STAGE`), handled like offer C's repeats (not run, uses up its generation); `db.DETERMINISTIC_FAILURES` unchanged, so a longer `--verify-s` still revisits a timed-out PARI program | assistant, carrying out the user's offer H with the offer-C decision ("Don't run, count it"); the critic reviewed the plan and found no decision for the user | [strategies](strategies.md#steps) |
| No CPU-share guard on that rule (a timeout on a busy machine still counts as a repeat, costing one generation), as `db.is_dead_end` has none; recorded as a known limitation | assistant, the critic agreeing; told to the user, who can ask for the guard | [known limitations](known-limitations.md#strategies) |
| Offer F: an untrustworthy cost fit never stops a run as infeasible on time (rather than judging it by the low end of its range, or leaving the gate as it was) | user ("Never (F as written)"), on the assistant's recommendation, which the critic had turned from the low-end rule to this one | [verification](verification-and-estimation.md#assessment-estimateassess), [known limitations](known-limitations.md#verification-and-estimation) |
| Offer D: the failure penalty counts attempts (one `attempt_sequence` call each), not rows, and the existing rows are backfilled once (rather than grouping only session rows at query time, leaving model rows out, or no change) | user ("Per attempt + backfill (Recommended)") | [strategies](strategies.md#failure-penalty) |
| D's attempt key is a uuid in `extra.attempt_call` (not a column, not `extra.attempt`, which would read as a row id); a row without it or with an unreadable `extra` counts on its own; the backfill is a one-off scratch script in one transaction, after a `VACUUM INTO` backup, not added to the repo | assistant, reviewed by the critic (the transaction after its audit) | [data and schema](data-and-schema.md#attempts-one-row-per-program-run-or-per-skip) |
| Offer E: reverse the hold-back rule, so after a budget dead end the entry's other PARI programs get their turn in later attempts (rather than keeping it, or keeping it only after `extend_budget`) | user ("Reverse: siblings get a turn (Recommended)"), on the assistant's recommendation, which the critic's review had turned from confirming | [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first), [known limitations](known-limitations.md#pipeline-and-recording) |
| The flaky test: drop the 4× accuracy check on real timings (rather than keep one with terms of about 1 s) | user ("Drop it (Recommended)") | [development](development.md#tests), history item 30 |
| Split it into the extension's infeasible stop in memory with controlled times (`test_estimate.py`) and the sandbox ending a run on that stop with no extension time (`test_verify.py`); fix the test, not the rule | assistant, from the step's own wording; the critic's review made the zero extension and the stop-source checks | [development](development.md#tests), history item 30 |
| F's trust is the cost fit's (`Projection.trustworthy`), not `Assessment.trusted`, so a fit withdrawn from the kill only by the rate drift is still judged on its high end; the disagreement-over-10 rule and its constant removed; an untrustworthy projection over the budget gets a reason saying it was not judged on time; memory unchanged | assistant, reviewed by the critic | [verification](verification-and-estimation.md#assessment-estimateassess) |
| The documentation's counts are checked by the suite rather than maintained by hand, and a checked sentence that is reworded away fails too | user ("Update the test suite/documentation (if possible) to avoid defects in future runs"), after the same drift three times in item 36 | [development](development.md#tests), history item 37 |
| Item 36 stores five fit columns, not four: `fit_climbing` too, so the estimator's `risky` flag is reconstructible | user ("Yes, add it"), on the assistant's recommendation | [data and schema](data-and-schema.md#predictions-one-row-per-projected-term) |
| `trustworthy` keeps its name and meaning (the kill's permission) rather than being renamed or recomputed; the new flag is `fit_trustworthy` beside it | assistant, on the replay showing the column consistent across all 40 rows; the critic agreed | [data and schema](data-and-schema.md#predictions-one-row-per-projected-term) |
| The dashboard is not changed to show the new columns; noted as a follow-up instead | user ("Leave it, note it") | [dashboard](dashboard.md), next steps |
| `scripts/replay_predictions.py` is committed, with `--write` guarded to rows where every fit column is NULL (rather than the one-off scratch script offer D's backfill used) | user ("Permanent scripts/replay_predictions.py"), the guard from the critic | [development](development.md#helper-scripts) |
| No migration hook in `db.connect()`: the columns are added by the one-off backfill, and the project keeps having no migrations | assistant and critic agreeing, against adding a new mechanism to the one path every command touches | [data and schema](data-and-schema.md#database) |
| Do the smaller follow-ups (next step 2) before the 600 s pass; go slow, review as you go, use a critic | user ("tackle #2 before moving onto #1... Spin up a critic agent") | history item 34 |
| Keep `verify.on_line`'s unreachable `incomplete` guard rather than delete it as dead code | user ("Keep the guard"), on the assistant's recommendation | [verification](verification-and-estimation.md#checks-on-each-term-harnesson_line), history item 34 |
| A pending win whose re-check keeps failing is flagged with a count, never given up on | user ("Flag only"), on the recommendation the critic had turned from giving up after 3 tries | [known limitations](known-limitations.md#pipeline-and-recording) |
| The `infeasible` dead end keys on the effective memory cap the run got, compared against the *configured* budget of the planned run (not against the cap that run would get, which would make picks depend on free RAM) | user ("Effective cap vs budget"), the option proposed by the critic over both the assistant's | [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first) |
| `sync` recomputes `sequences.difficulty` from the stored rows, rather than dropping the column or leaving it stale | user ("Make sync consistent") | [data and schema](data-and-schema.md#sequences-the-candidate-table) |
| Design-intent mismatches 1, 3 and 5 are corrected documentation, not code (the proposed fix for 1 is a no-op here; 3 cannot be tested on this machine; 5 is deliberate) | assistant, from the evidence; the user can still ask for any of them | [known limitations](known-limitations.md#differences-from-the-design-intent) |
| The pending file is indented JSON | assistant, after a mutation showed the byte-mode write was otherwise unverifiable, and because operations.md sends a human to that file | [data and schema](data-and-schema.md#directory-layout) |
| `AttemptResult` carries `mem_cap`, so the stored cap is the one `estimate.assess` was judged against rather than the sandbox's own reading an instant later | assistant, **departing from the user's approved wording** ("RunResult already carries it, so nothing new to serialise"): the audit showed that rationale was wrong, since memory freed between the two readings makes the sandbox's value overstate the cap the verdict used — the direction that wrongly retires a working program | [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first), history item 34 |
| Session 8 is 20 picks (matching sessions 5-7 for comparability) rather than the 25 cap or a 10-pick probe, and runs the full pre-registration before launching rather than starting immediately | user ("-n 20 (Recommended)", "Full pre-registration (Recommended)") | history item 38 |
| Session 8 does **not** re-sync the oeisdata mirror, so the pool stays comparable with the documented counts | assistant, stated in the plan and not challenged by the critic | history item 38 |
| **Do not build resume at all**; use a targeted `oeisbot attempt A... --extend-s` instead (rather than the minimum build, wiring the frontier into `_bound_exhausted` as a rate, or the full build) | user ("Stop; use targeted --extend-s"), after the evidence and a critic's 31 findings; the assistant had recommended the same with one small addition the user declined | history item 42, [next steps](#open-offers-and-next-steps) |
| Record the gp and sandbox-Python versions in `meta`, **plus** a short `gp=...` token in `sessions.note` (rather than a `meta` row alone, which is overwritten on upgrade and would then describe no historical row) | user ("Yes, one meta row", then "Yes, short token in the note" when the critic showed `meta` alone would not do the job) | [data and schema](data-and-schema.md#meta), history item 43 |
| No backfill of the runtime versions for existing rows, and no per-attempt `extra` key for them | assistant, in the plan the user approved: the version that produced those rows is genuinely unknown and inventing one would be worse than the gap | [known limitations](known-limitations.md#runtime-provenance) |
| Fix both documentation errors the resume review turned up (the "one-line fix" claim and the line-ending note) | user ("Yes, fix both") | history items 42 and 43 |
| Do the checkable part of review #1, but **leave the review row at `new`** and submit nothing | user ("Tackle A385331's review now"); the status is the user's own workflow marker, and steps 8-9 are theirs alone | history item 44, [operations](operations.md#reviewing-a-result) |
| Session 11 is 25 picks (the per-invocation cap, one run) with the full pre-registration and a critic on the plan before launch, rather than 20 for comparability or 50 over two runs | user ("25 picks (Recommended)", "Full (Recommended)", 2026-09-29) | history item 50, `data/session11/planS11.md` |
| A session's plan reads **every** pick's program (`progs.py`) and pre-registers a per-pick probability beside the pooled base rate, scored afterwards by Brier score — rather than a reading of a few picks, which session 10's audit found weakly supported | assistant; adopted for session 11 and worth keeping, since the reading scored 0.0127 against the base rates' 0.1467 | history item 50 |
| When the plan proves something about a pick (no projection possible, so no `infeasible`), the wall-clock model must use it instead of the pooled cost sample | assistant, after session 11's P9 missed its band for exactly that reason and the pre-run critic did not catch it | history item 50, `data/session11/resultsS11.md` |
| Every open decision presented as an options question, five batches of up to four, then four more once the measurements were in | user ("Present all the decisions to me as questions with options", 2026-09-30) | history items 51 and 53 |
| Review #1: walk through submitting; standardize a review's identity block in `oeisbot review list` and the dashboard inbox (not in chat, not in the README) | user | history item 51; [operations](operations.md#reviewing-a-result) |
| Do not commit yet (fifth time; asked directly) | user ("Not yet", 2026-09-30) | this page |
| Offer (a): re-derive the count first, then **backfill `program_sha`** on the lost-retirement rows after a `VACUUM INTO` backup, in one transaction, after session 12 | user, on the recount (45 sequences, not 35) | history items 51 and 52; `data/offerA/` |
| Session 12: 25 picks, full pre-registration with a critic, **launch first, edit during, run tests after** | user | history item 52 |
| A `rejected` review refuses a later review for the same sequence (`db.ReviewRefused`), caught inside `record_win`'s transaction rather than raised | user chose the refusal; the transaction placement is the assistant's, from the pending-file retry loop it would otherwise create | history item 51; [data and schema](data-and-schema.md#reviews-the-human-queue) |
| The model prompt quotes a disclaimed program under an honest header (`codegen.CONJECTURAL_PROGRAMS_NOTE`) instead of dropping it — reversing the 2026-09-26 choice | user | history item 51; [strategies](strategies.md#programs-whose-author-calls-them-conjectural) |
| The A-name helper check captures the whole identifier, and definitions are read with balanced parentheses (item 46's deferral), built after measuring | user ("Design, measure, then build") | history item 51; [strategies](strategies.md#programs-that-call-another-entrys-helper) |
| Both sandbox backends guard `on_line`/`on_tick`; a raise is `Status.CALLBACK_ERROR` → `harness_error`, outside the dead-end rules | user (both of item 46's deferrals); the status mapping is the assistant's | history item 51; [sandbox](sandbox.md#what-it-guarantees) |
| An `infeasible` verdict records the budget it ran out of and the dead-end rule compares only that budget | user | history item 51; [verification](verification-and-estimation.md#stop-reasons) |
| A new term at or below the published bound is flagged, never refused | user | history item 51; [verification](verification-and-estimation.md#the-searched-bound-check) |
| gp's memory figure is judged against `parisizemax` (`Harness.stack_cap`), Python's against the job cap | user ("compare like with like") | history item 51; [verification](verification-and-estimation.md#assessment-estimateassess) |
| Do **not** wrap a predicate in `iferr` | user | history item 51 |
| Measure before deciding: loop starts, helper-beside-`lista`, bulk-printer signal, value dependence (both directions), risk flags (replay), Wolfram (scope) | user | history item 51; `data/measure0930/` |
| Refuse a print loop whose start disagrees with where the emitter numbers from (index loop off the offset; filter loop printing its variable above the first term), rather than renumber | user, on the measurement (44 pool sequences) | history item 53; [strategies](strategies.md#program-forms) |
| Refuse a def whose only parameter has a default (a bulk printer) | user, on the measurement (4 of 4) | history item 53 |
| Leave the over-prediction kill rules as they are (no kill on untrusted risky fits, no withdrawal of trust when risky) | user, on the replay (4,423 s saved on record against a six-term sample of finished terms) | history item 53 |
| Defer Wolfram Engine, scoping note attached; value dependence: leave it (nothing on the record gains) | user | history item 53; `data/measure0930/wolfram_scoping.md`, `valuedep.txt` |
| Pick map: a tile's colour is the change since the last snapshot, and the tiles are grouped by difficulty band, with an "All bands" tab and a tab per band, so 5,000 tiles are never in one display | user ("Change since the last snapshot"; "Group them by difficulty band but also make tabs...", 2026-10-13) | history item 54 |
| Pick map follow-ups: **also snapshot after every `oeisbot sync`** (PARI pool only, under the newest snapshot's budgets); the colour horizon stays **fixed** at the newest *different* snapshot, no picker; a **footer chip** for the bands too small to draw in "All bands"; tiles **keyboard-focusable**; a failed pool build shows a **friendly message with a retry** | user, asked 2026-10-14 ("Also after every sync", "Keep it fixed", "Add a footer chip", "Make tiles focusable", "PARI only", "The newest snapshot's budgets", "Friendly message + retry") | history item 55: built 2026-10-14, not yet committed |
| Commit and push everything through item 54 | user ("Commit and push", 2026-10-14) | `f0081d9`; [what is committed](#what-is-committed) |

## History (condensed)

1. **Sandbox first.** Built the Windows sandbox and an adversarial test suite, which caught:
   - AppContainer launches need `LOCALAPPDATA` in the environment;
   - uv's hard links hid packages from the container;
   - a disk-cap bug that let two test runs write about 10 GB each.
2. **Gate and estimator.** Built the verification harness and the feasibility estimator with synthetic
   cost-curve tests.
3. **Database.** SQLite in WAL mode.
4. **Ingest.** Cloned oeisdata (needed git's schannel backend), found the LFS pointers, and measured
   program types: 54% of candidates have no program, 31% Mathematica, 20% PARI.
5. **PARI strategy.** Coverage of PARI-bearing candidates went from 61% to 75% with print-loop rewriting.
   The first real runs mostly hit `verify_timeout` on 2-minute budgets. Found that gp commits its whole
   `parisizemax`.
6. **Model code generation.** Built and tested with a scripted fake model.
7. **Dashboard.** FastAPI + React, checked visually against a demo database. Fixed a resize feedback
   loop, hash navigation and chart sizing in hidden tabs.
8. **Real model.** Installed Ollama and the model. The first real test caught the model hard-coding known
   terms, which led to the holdout defenses. Found and fixed inflated peak-memory reports for refused
   allocations. Session 2 with `--model`: 18 generations, 0 verified.
9. **Documentation.** Wrote these docs; an independent audit found 23 inaccuracies, all fixed.
10. **Fixes (session 3).** Resumed from this page; all setup checks passed. With the user's approval:
    - **Re-check errors** no longer abort the session or lose a win:
      - a run with new terms is recorded as `recheck_pending` and saved to `data/pending/` first (a pickle then, JSON since item 34);
      - transient errors are retried twice in place (`_recheck_with_retries`), other errors are not;
      - an unfinished re-check stays pending, and the sequence is blocked from attempts and picks;
      - `retry_pending_rechecks` runs at each `oeisbot run` and on the new `oeisbot recheck` command, and
        never raises for a single attempt;
      - wins are recorded with `db.record_win` (one transaction), and artifact folders carry an
        `.incomplete` marker until then, so resolving can be repeated.
    - **Infeasible dead ends** now only block a program when the earlier run's `extend_wall_s` and
      `mem_bytes` (newly stored in `attempts.extra`) were at least as large.
    - **Holdout**: `shown_indices` always holds out 2 known terms (`config.CODEGEN_HELD_OUT_MIN`). With
      fewer than 3 known terms the sequence is skipped for the model (`too_few_known_terms`) and
      `generate_and_verify` raises. Such sequences without a PARI program leave the pool once their
      b-file lookup has run.
    - **`censored_s`** is no longer set on infeasible projections, so they leave the estimator view.
    - **Independent audit** of the first version by a separate agent: it found the win could still be
      lost (Ctrl+C during the retry waits, or a failed pickle write), that one bad pending attempt made
      every `oeisbot run` crash at startup, that non-network errors were retried and kept pending, and
      several doc inaccuracies. All were fixed, and while fixing them a further gap (a database failure
      after the artifact was written would block the win forever) was found and fixed too.
    - 18 new tests (92 → 110) and doc updates across pipeline, operations, data/schema, verification,
      strategies, development, dashboard, design spec, known limitations, README and CLAUDE.md. A
      pre-change copy of source, tests and docs was kept only in that session's temporary directory, so
      no snapshot of the code before these fixes survives (there is no commit either).
11. **`fini` fix and test gaps (session 3, after the above).** `EXCLUDED_KEYWORDS` no longer contains
    `fini`, so finite-but-incomplete sequences are candidates: the first design-intent mismatch is gone and
    `oeisbot sync --no-pull` on the same checkout took the table from 26,628 to 26,814 candidates. All the
    counts measured from the table were refreshed in the docs. 31 more tests (110 → 141), closing the three
    known gaps and others found while looking:
    - the keyword filter (checked against the old behavior too, so it would catch a regression) and
      `sync` clearing `in_more`;
    - the re-check verdicts and the `oeisbot recheck` command (new `tests/test_recheck.py`);
    - the model client, which had no tests at all (new `tests/test_model.py`: both API shapes,
      `ModelUnavailable`, `available()`);
    - an infeasible dead end re-run under a bigger budget through `attempt_sequence`;
    - `too_few_known_terms` after a failed PARI run, `model_no_runnable_code`, an unreachable model;
    - every per-sequence gate skip, an HTML page instead of a b-file, and a win surviving a failed save
      of its pending result.
12. **B-file sweep (session 4).** `oeisbot fetch-bfiles --all --limit 30000` resolved the b-file status of
    every candidate in about three minutes: **68 have a b-file, 26,746 do not**, 0 errors. No candidate is
    left in the unresolved state that kept short sequences ambiguously in the pool. The sweep also showed
    that fetching b-files is not the lever [known limitations](known-limitations.md#strategies) suggested
    it was: 61% of OEIS sequences have a b-file (243,052 of 399,307), but only 0.25% of `more` candidates
    do, because the keyword selects for sequences with few known terms. DATA-only verification is
    structural here, not a gap prep work can close.
13. **First real-budget session (session 4).** `run -n 5 --model --verify-s 600 --extend-s 1800`, database
    session 3. 16 program runs, **0 wins**, 10.1 minutes of sandbox time. It did not test the budget
    hypothesis: 15 of the 16 runs were model generations consuming **8 seconds in total**, and the single
    PARI run (A272621) used 600.3 s of it. Nothing reached the extension phase, so the 1800 s extend budget
    was never exercised at all. Two findings came out of it:
    - **The retry prompt is blind to the failure type.** `codegen.RETRY` always says to "re-read the
      sequence definition and find where your program's reading of the definition differs". That fits
      `wrong_term`, but not a crash: A129250 failed all three generations with the identical
      `AttributeError: module 'gmpy2' has no attribute 'prime_range'`, was told the error each time, and
      was steered at the definition rather than at the missing API. 4 of the 16 runs were crashes.
    - **`GENERATE` lists module names but no function names** (`imports=", ".join(sorted(ALLOWED_IMPORTS))`),
      so the model guesses APIs. `gmpy2` has no `prime_range`; sympy's is `primerange`.
    Failure modes: `wrong_term` 6, `bad_index` 5, `crash` 4, `verify_timeout` 1. The temperature ramp
    (0.2/0.5/0.8) and the error feedback are both implemented correctly; the repeats are the model, not a
    bug in the loop.
14. **Failure-type-aware retry prompt (session 4).** `codegen.retry_guidance(stop)` now chooses the
    instruction sent with a retry: crashes are told to fix the error and are given `API_HINTS` (a list of
    real `gmpy2`/`sympy`/`math` functions built from `API_NAMES`); `bad_index`/`protocol` are told it is an
    output-protocol error and to keep the algorithm; timeouts are told the program was too slow, not wrong;
    `memory_cap` is told to use a memory-lean method; `wrong_term`/`incomplete` keep the original
    "re-read the definition" wording. The static-rejection path (program never ran) gets its own short
    message instead of definition advice. Two tests (141 → 143): one covering every branch, one running the
    **sandbox interpreter** to prove no hinted name is invented — `gmpy2` and `sympy` are not in the venv,
    so checking them there would have silently passed.
    Verified against the sequence that prompted it: re-attempting A129250 produced no missing-API crash;
    all three generations ran and failed on `wrong_term` instead. That is one stochastic sample, not proof
    (the classify step even picked a different approach), but the crash class did not recur.
15. **Independent audit of item 14, and its fixes (session 4).** A separate agent audited the change. Its
    findings, all confirmed and fixed:
    - **The feature was not held in place by any test.** Stubbing `retry_guidance` to return the generic
      message for every stop left all 143 tests passing: the unit test called the function directly, and
      the one test that inspects a real prompt asserted only on text coming from `describe_failure`. The
      end-to-end test now asserts the stop-specific guidance reaches the model; the same stub now fails 3
      tests.
    - **Host conditions were blamed on the program.** `launch_error` (no free RAM, or `CreateProcess`
      failing), `disk_cap` and `output_cap` fell through to the definition advice — exactly the misdirection
      item 14 set out to remove, on failures the model cannot fix at all. Each has its own branch now, and
      `cpu_cap` joins the timeout branch.
    - **`incomplete` was misclassified.** It means the generator returned instead of yielding forever, so
      the fix is the contract, not a re-reading; item 14 had asserted the opposite in a test, which would
      have locked the wrong behavior in.
    - **Duplicated advice.** `describe_failure` and `retry_guidance` both told the model to be faster and
      to use less memory; `describe_failure` now states only the fact.
    - Doc errors: a stale test-count table in `development.md`, a present-tense claim in
      `known-limitations.md` that the retry text is still failure-blind, and run totals that had not
      absorbed the A129250 re-attempt.
    A new test asserts that every `Stop` able to reach a retry is classified, so the next one added cannot
    silently inherit the definition advice. 145 tests.

16. **The PARI-only budget run, and what it settled (session 4).**
    `run -n 5 --verify-s 600 --extend-s 1800 --seed 101`, no `--model`; database session 4, 5 picks from
    5,316 PARI candidates, 6 program runs (A101722 had two `%o (PARI)` blocks and both were tried),
    80 minutes of machine time, 0 wins, 0 new terms. This is the first session whose time went into
    arithmetic rather than into model generation, so unlike database session 3 it actually answers the
    budget question. It answered it in the negative, and for a reason worth keeping.

    | Sequence | Definition | Result |
    |---|---|---|
    | A273521 | `10*14^n - 1` prime | 7 of 8 known terms in 600 s; a(6)=1233 cost 2.5 s, a(7) unreached in ~596 s |
    | A101722 | primes in `A(n) = 10*A(n-1) - 61` | 1 of 4, twice (both PARI blocks) |
    | A391617 | `sigma(k) - 2k = 54` | 4 of 7; a(4)=2040832 cost 1.5 s, a(5) unreached in ~598 s |
    | A377248 | `8191*2^k + 1` prime | 7 of 12; a(7)=10176 cost 78.5 s, a(8) unreached in 516 s |
    | A247883 | consecutive exclusionary cubes | 10 of 10 in **57 ms**, then 1800 s of extension, 0 new terms |

    - **Verification, not extension, is the binding constraint.** Five of the six runs stopped at
      `verify_timeout` without ever reaching the extend phase, so the 1800 s extension budget was spent
      exactly once. Raising `--extend-s` cannot help a candidate set that cannot get through the gate.
      None of the five failures was a bug: every one was genuine arithmetic cost.
    - **The cost cliff sits exactly at the edge of the known terms, and that is selection, not luck.**
      A sequence carries `keyword:more` *because* its next term is expensive — anyone who could compute
      it cheaply would have submitted it already. A247883 shows the shape starkly: a(1)..a(10) in 57 ms
      total, a(11) not found in 1800 s, a jump of at least four orders of magnitude at the boundary.
    - **So the estimator is built for the wrong half of the problem.** Its whole input is the cost history
      of the known terms, and for search-type sequences that history is uninformative by construction.
      For A247883 it honestly declined to project: every per-term CPU cost (0.016 s at most) is below
      `estimate.CPU_FLOOR_S = 0.05`, so `project()` returned `None` and the attempt recorded a projected
      memory but no projected seconds. Correct behaviour, and a structural limit on what extrapolation
      can ever contribute here.
    - **The `work` cost unit can underestimate badly, and A377248 measures by how much.** `points()`
      prefers instrumented work units whenever the program reports them, on the grounds that they are
      hardware-independent and smooth. On A377248 work grew 1.9–2.1x per term while wall time grew
      15.4–15.7x: work counts candidates tested and ignores the cost of each primality test, which itself
      grows with the exponent. Replaying `estimate.assess` on the recorded points projects a(8) at
      **149 s (range 149–734 s)** from work, against **1191 s (range 1161–1191 s)** from CPU. a(8) is
      known to exceed 516 s, so the work point estimate is wrong by at least 3.5x and its whole range
      sits below the CPU estimate. The work path did flag the trouble (`climbing`, ratio model,
      `risky=True`, 4.9x disagreement) — it is the number, not the warning, that misleads. See open
      offer A.

17. **Steps 1 and 2, planned and critiqued (session 5, 2026-09-18).** The user asked for "steps 1 and 2
    together, then a real session to see whether more runs get past the known terms", to go slow and to
    use a critic. The evidence first: the 3 PARI runs that ever verified did so within 2.6 s, and 11 of the
    13 timeouts show the next term costing 10× or more than the last one reached, so time past a minute
    bought almost nothing. A written plan was critiqued by a separate agent before any code. It corrected
    several evidence claims, asked for one function shared by selection and attempts and for offline
    b-file reads, and showed that a `--model` session would mostly pick sequences that bypass the PARI
    check. The user then chose the 60 s default and the two-part test run.
18. **Implementation, independent audit, fixes (session 5).**
    - `config.Budgets.verify_wall_s` 600 → 60.
    - `db.is_dead_end`: `verify_timeout` is a dead end for verify budgets up to the attempt's `runtime_s`.
    - `pari.out_of_reach`: a predicate driver needs one call per integer up to the last known term; a
      search needing more than `PREDICATE_MAX_RATE` × `verify_wall_s` calls is not run (skip
      `verify_out_of_reach`). The cheapest predicate measured 5.8 × 10^6 calls/s; a sandbox test guards
      the constant.
    - `attempt.pari_plan` sorts an entry's PARI programs into runnable, dead ends and out of reach;
      `attempt.Runnable`, passed to `select.candidates(keep=...)`, uses it to leave out sequences an attempt
      could only skip (1,731 of 5,316 PARI-bearing candidates at 60 s), with `bfile.cached` for offline
      b-file reads. `oeisbot queue`/`pick` use it too.
    - `_Attempter.finished` split into `found_new` (stop everything) and `verified`; the model stage runs
      after a verified run with no new terms, gets a note (`codegen.VerifiedRun`, `slow_program_note`) and
      tags each program for the reviewer (README and Review inbox).

    The independent audit found no way to lose or publish a win, escape the sandbox or leak a held-out
    term, but: a correct program recorded as an infeasible dead end in an earlier session reached the
    model without the note; the selection check kept rows an attempt would crash on (now left out and
    reported); the `--model` pool counted the wrong skip reason; the rate constant had only 1.7× headroom
    (raised from 10^7 to 2 × 10^7); 10 behaviours had no test; and several doc claims were wrong, one of
    them a number copied from the critic unchecked (arrival times quoted as per-term costs). A re-check of
    the fixes found an untested guard whose removal could put a held-out value into the prompt (test
    added), a wrong penalty count in the docs, and an older crash on a b-file with no usable line (fixed).
    145 → 178 tests; 34 deliberate code mutations, each caught by a test. The mutation scripts restore
    files byte for byte (the first version rewrote line endings; restored from a backup).
19. **Session 5: the quick first pass, measured.** `run -n 20 --verify-s 60 --extend-s 1800 --seed 202`,
    no `--model`. Hypotheses were written down before the run.

    | Measure | Earlier PARI-only sessions (1 and 4) | Session 5 | Expected |
    |---|---|---|---|
    | Picks wasted as skips | 2 of 14 | **0 of 20** | about 0 |
    | Program runs past the known terms | 2 of 12 | 3 of 22 (14%) | unchanged, about 20% |
    | Program runs per hour of wall clock | 7.7 | **27.6** | clearly higher |
    | Runs past the known terms per hour | 1.3 | **3.8** | higher |
    | New terms | 0 | 0 | probably 0 |

    47.8 minutes of wall clock in all; the 17 `verify_timeout` failures cost 17 minutes together, where
    the old 600 s budget would have spent almost 3 hours on them. Other stops: 1 `wrong_term`, 1
    `incomplete`. The per-run rate did not rise and was not expected to: step 1 changes what a failure
    costs and what gets picked, not what a run can do. Most picks were searches of the form "numbers k
    such that c·b^k ± d is prime", expensive per call, which no static bound can flag.

    The finding worth acting on: **2 of the 3 verified runs were killed by `over_prediction` after 10.6 s
    and 28.5 s**, using under 2% of their 1800 s extension. A277532's a(7) was projected at 2.3 s (high
    11.7 s, CPU unit) and A390295's a(10) at 2.5 s (work unit); both projections were marked
    untrustworthy, but `estimate.Assessment.kill_after_s` did not look at that (fixed by offer B, item
    21). Only A323252 used its whole extension (no new term in 1800 s). See offer B.
20. **Step 2 exercised.** `attempt A247883 A057246 A246855 --model --verify-s 60 --extend-s 120`. Each
    PARI program verified again (10/10, 4/4, 3/3), found nothing in 120 s, and the model stage then ran
    with the note on all three, as designed. All 9 generations failed: 8 `bad_index`, 1 `crash`
    (`gmpy2.sum_divisors` does not exist). The generated programs show why: for "numbers k such that"
    sequences the model ties the index to the candidate (`n += 1` alongside `k += 1`, or `yield (n, n)`),
    and for two of the three sequences it sent the byte-identical program three times despite the
    protocol guidance. The feature works; the model cannot yet use it. See offer C.
21. **Offer B: no over-prediction kill on an untrustworthy projection.** `estimate.Assessment.kill_after_s`
    now returns no threshold unless the cost projection is trustworthy (disagreement ≤ 3 and at least 4
    fitted points), matching the stored `predictions.trustworthy`. Options weighed: no kill (chosen), a
    larger grace scaled by the disagreement (rejected: arbitrary, and A277532's projection was
    untrustworthy for having 3 points, not only for disagreeing), or `risky` instead of `trustworthy`
    (rejected: not stored, and a trustworthy climbing projection uses the ratio model built for it). A
    critic reviewed the plan first. It confirmed the evidence from the database (both kills were on 3-point
    projections that disagreed about 5×, and replaying the term logs reproduces the recorded estimates
    exactly) and found a case the rule does not cover: trust judges the cost fit, not the conversion to
    seconds. On A377248 a *trustworthy* work projection for a(7) (high 5.6 s, kill at 11.2 s) met an actual
    78.5 s, because the wall seconds per work unit grew about 8× per term; that is left to offer A and
    documented. It also corrected the plan's cost claim: at the default 3 h `--extend-s`, an unproductive
    run now costs the whole 3 h, and `extend_budget` is still not a dead end (changed in item 22).
    Tests: the recorded session-5 points replayed (their recorded high estimates reproduced, no kill), both
    sides of the 10 s floor, no kill on disagreement or on too few points, and a sandbox run whose first new
    term outlives the old threshold and is kept. 178 → 182 tests. An independent audit found no defect in
    the code or downstream (dead ends, penalties, artifacts, dashboard and the model hand-over do not
    depend on the kill), confirmed the doc numbers against the database, and found two mutations the
    tests missed (`risky` instead of `trustworthy`; the point estimate instead of the high one), now
    covered by a trustworthy climbing projection, plus one stale count and wording nits, fixed. 10
    deliberate mutations (the old rule, never killing, inverted trust, disagreement only, point count
    only, no floor, `risky`, point estimate, no value-dependent check, a harness that never kills), each
    caught, and the four new tests each fail on their own under the old rule.
    Real check: `attempt A277532 A390295 --extend-s 300` (attempts 90 and 91, PARI only, 60 s verify). Both
    verified again, and both first projections were again untrustworthy (3 points; high 7.1 s and 2.6 s,
    so the old rule would have killed at 14.2 s and 10 s). Both ran the whole 300 s and stopped
    `extend_budget`, with censored times of 300.3 s and 300.2 s. No new term.
22. **A used-up extension is a dead end.** The user asked for it before a long session: after offer B an
    unproductive verified run whose first projection is untrustworthy spends its whole extension. New
    clause in `db.is_dead_end`: verified, no new terms, `extend_budget`, stored `extend_wall_s` at least
    the current one, and `cpu_s ≥ 0.8 × runtime_s` (`EXTEND_DEAD_END_MIN_CPU_SHARE`). A critic reviewed the
    plan and replayed the selection check in memory: the PARI-only pool is unchanged at the default 3 h
    and loses 2, 4 and 6 sequences at 1800, 300 and 120 s (never one for `--model`). It confirmed on
    `gp.exe` that memory never ends a run as `extend_budget` (a stack overflow at `parisizemax` ends as
    `finished`), so memory is not compared; proposed the CPU guard (the nine real runs had 93–99% CPU);
    and found two tests the log rewording would break. An independent audit then found the rewording keyed
    on the wrong thing (a program that verified and later emitted a bad index was logged as "found
    nothing new with no less time"; now worded by stop reason) and a gap: within one attempt a verified
    run ends the PARI stage, but in the next attempt the dead end was skipped and the entry's *other*
    programs ran with the full extension instead (300 of the 3,568 pool sequences have 2 or more
    runnable programs). Now an `infeasible` or `extend_budget` dead end holds the others back at that
    budget (a held-back list in `PariPlan`, removed again by offer E, item 29); a deterministic dead end that verified first holds nothing back. The
    pool numbers above are unchanged (each of the six has one runnable program).
    Tests: the clause in `test_db` (boundary, more time, memory, new terms, no stored budgets, starved
    CPU, exactly the CPU share, `over_prediction`), an end-to-end sandbox run that searches until its 2 s
    extension runs out and is then skipped at 2 s and 1 s but run again at 3 s, the selection check
    agreeing, a two-program entry whose other program is held back, every sibling held back by an
    `infeasible` or `extend_budget` dead end (three blocks; added after the re-check), a
    broken-after-verifying program that holds nothing back, and the model note from such a dead end. The
    auditor's re-check found no defect, only those last two test gaps. 182 → 189 tests; 16 deliberate
    mutations, each caught.
23. **Offer A: the conversion to seconds joins trust.** The evidence first: the estimator replayed on
    all 57 term logs (39 sequences), projecting each known term from the ones before it as if it were new.
    In most predicate searches the seconds per work unit grow from term to term (1.4× to 7.3× per term,
    against 0.6× to 1.02× on CPU-unit runs), and trustworthy work-unit projections would have killed
    A377248's a(7) (78.5 s against an 11.2 s kill) and A253773's a(26) (31.8 s against 10 s). A trustworthy
    CPU projection would have killed A274508's a(15) (32.4 s against 22.1 s), which is not a conversion
    problem. A critic reviewed the plan. It confirmed the numbers and found three things: the replay had
    left out each log's unfinished last term, where two more kills of unknown merit sit (A273521's a(7),
    still running after 597 s, and A350878's a(16), after 38 s); the proposed threshold of 1.25× growth
    per term rested on almost no steady work-unit data; and a better measure, used instead. The user chose
    to withdraw trust only, rather than turn the kill off by default or stretch it, and to leave the
    estimate uncorrected: every correction tried added 3 or 4 wrong infeasible stops (a term at one of
    five budgets, finished within it) to the current rule's 9.
    - `estimate.assess` fits the own rates (wall seconds per cost unit) of the five points the rate is
      taken from, projects them to the next term, and stores that over the rate used as
      `Assessment.rate_drift`.
    - `Assessment.trusted(factor)` needs a trustworthy cost fit and a drift no larger than the kill factor.
      The kill (`kill_after_s`) and the stored `predictions.trustworthy` (`Prediction.from_assessment`,
      which now takes the factor) both use it, and `drift_note` adds the reason to the prediction.
    - In the replay this withdraws every work-unit kill (drifts 2.6 to 17) and keeps the CPU ones (1.01).

    Tests: A377248's real points (trustworthy fit, drift 11, no kill, stored untrusted with its reason),
    the exact definition and both sides of the factor, the five-point window, the CPU unit steady and
    starved, and a sandbox run whose terms get 3× dearer per term under a flat cost fit (the old rule kills
    its first new term, the new one keeps it). 14 deliberate mutations, each caught; the timing-sensitive
    kill tests passed 20 runs in a row.
    An independent audit found no code defect. It replayed the old and the new estimator on all 360
    prefixes of the 57 logs and found the estimates, ranges, feasibility at five budgets and reasons
    identical, and the wrong kills down from 3 to 1. It re-derived every quoted number. Its findings,
    all confirmed and fixed:
    - the doc reason for not correcting the estimate was wrong: a run that goes on is not "only time",
      since a used-up extension is itself a dead end (item 22); the difference is that it can still
      find the term. The "3 or 4 more" counted stops at five budgets, not terms;
    - three mutants survived: a drift window of four or six points (the window test only ruled out seven
      or more) and the harness storing trust at a fixed 2 instead of its budget's factor. A test with
      irregular rates now pins the five-point fit against an independent least-squares fit, and one
      drives the harness in memory at factors 2 and 20;
    - operations.md claimed every climbing rate is untrusted: a rate growing 1.5× per term drifts only
      1.95 under a doubling cost (2.9 under a flat one), so it can still be killed; the docs now say so,
      and known limitations records the drift's own limits (a one-step extrapolation from five points;
      A253773's a(26) was withdrawn at 2.6);
    - `trustworthy` described as "the kill could act on it" ignored value-dependent rows, and stale
      "trustworthy projection" wording remained in `config.py` and `verify.py`.
    The auditor's re-check confirmed each fix (and 15 further mutations of its own, all caught except an
    untested overflow cap) and found three small things, fixed: the in-memory harness test depended on
    free RAM through the memory cap (now stubbed) and its last check sat on the 10 s floor (now at factor
    100); the stored `trustworthy` definition did not hold for session 5's two kills, stored before
    offer B with `trustworthy = 0` (the schema and dashboard pages now say so); and operations.md said
    work unit and twice where it means cost unit and the kill factor.
    189 → 196 tests; 17 deliberate mutations, each caught.

24. **Offer C: the list contract and repeated programs (2026-09-18/19).** The evidence first: of the 45
    model generations so far, all 17 `bad_index` failures were on sequences that are lists of numbers with
    a property, and the programs show why (`yield (n, n)` while counting candidates, or the prime
    `c·b^k ± d` yielded where k belonged). Run again in the sandbox with the runner numbering the values
    they yielded, 6 of the 17 reproduced every known term (every step-2 program for A247883 and A057246),
    4 were right as far as they got within 60 s, and 7 were still wrong (4 of them the prime instead of k).
    19 of the 45 generations were byte-identical to the one before (in 11 of the 15 model stages); the
    temperature ramp does reach the model, so the retry, which shows it its own last program, is what it
    copies. A critic reviewed the plan. It confirmed the numbers and found that the proposed measurement
    (`attempt A247883 A057246 A246855 --model` at the default budgets) would have rerun three PARI programs
    for 3 h each on sequences whose entries rule out new terms; that the re-index evidence favoured a
    members generator over the `isok(k)` predicate the offer named (no isok program was ever tested, and
    about 18% of list-style candidates without PARI end at terms a counting predicate cannot reach); that
    a list-contract retry showing the program's wrong value at a held-out index would tell the model that
    number is not a member. The user chose `members(work)`, not running a repeat (and counting it as a
    generation), and a ten-sequence measurement at 60/120 s.
    - `codegen.FORM`: when the known terms strictly increase, the model is asked on its own whether the
      sequence is a list or a(n) of n. Folded into the classify question as a field it called two real
      lists functions 4 times out of 4 (42 of 44 right); asked alone, 44 of 44. The classify prompt and the
      whole `terms(work)` prompt are unchanged, word for word.
    - `codegen.MEMBERS`: `members(work)` yields the members; `MEMBERS_DRIVER`, appended as
      `Program.script`, numbers them from the offset and raises on a pair or a value not larger than the
      previous one, naming positions only. The static check and code extraction follow the contract, the
      name `terms` may not be bound at module level beside `members`, and under the list contract a
      held-out wrong term shows neither value.
    - A program with the syntax tree (`ast.dump`) of one that already ran in the stage and failed
      deterministically is not run: it is a rejection, uses its generation, and the retry says so.
    - The strategy stays `python:model` (the AI-generated warnings match that exact string); the origin
      names the contract; a "list contract" note shows as **Numbered by the runner** in the README and the
      dashboard (rebuilt). `data/runs/*.py` now holds the executed program, driver included, so its hash is
      the attempt's `program_sha`. `fixed_bounds` also reads constant expressions such as `10**7`.

    Tests: 25 new at first (196 → 221), including the driver in the sandbox at offsets 0, 1 and 5, both driver
    errors naming no value, a `members(work)` win end to end, the repeat rule after each deterministic stop
    and not after the others, and no held-out value in any list prompt. 31 deliberate mutations, each
    caught; the first run let one through (the driver error naming the value), and the test was tightened.
    An independent audit then found, all confirmed and fixed:
    - **a wrong new term could be recorded.** A program yielding 2, 3, 5, 7, 11 (the known terms), 17, 13
      had a(6) = 17 recorded as new, outcome `extended`: the driver saw 13 only after 17 was out, and an
      error after verification counted as a normal finish. The driver now raises `OEISBotContractError`
      (`verify.CONTRACT_ERROR`), which the harness turns into a `protocol` stop that voids the run's new
      terms (kind `void`);
    - the name `terms` bound at module level other than by `def` (`terms = []`, a class, an import) passed
      the static check and was silently replaced by the driver; any module-level binding is now refused;
    - a list retry could still show a held-out value, when the program's value at a shown index was a
      held-out member (a(9) = 29 where 29 is the hidden a(10)); such a value is no longer shown;
    - the run file was written in text mode, so on Windows its bytes (CRLF) did not hash to `program_sha`;
      it is now written byte for byte;
    - a long constant expression could crash the session through `ast.dump` or `_int_value` recursion (and
      a longer one already through `ast.parse`); both are bounded, and unparsable code is a rejection;
    - several surviving mutants (an equal value let through, `-` read as `+`, the repeat retry without the
      stop's guidance, extraction without the contract, the form question's temperature, and any rewording
      of the classify or `terms(work)` prompts, which the "unchanged" test compared only with itself),
      and doc errors (a stage of repeats cannot end as `model_no_runnable_code`, three stale mentions of the
      old contract or context, the predicate rate given for one driver only). The prompts are now pinned
      against the old text.
    The auditor's re-check confirmed those fixes and found: the voiding only works while the run is
    going (the harness reads nothing after a stop, so the last new terms of every productive run are
    unchecked for order), which the docs had not said; four more surviving mutants (only the latest new
    term voided, an unreadable value taken as small, `del terms` and `import terms.x` missed), now
    tested; and a few more module-level bindings of `terms` (`except ... as terms`, a `match` capture,
    assignment expressions in defaults and class bases), now refused. Two pre-existing issues it found
    are recorded as known limitations rather than changed: a `terms(work)` retry can show a program
    value that equals a held-out term (offer G), and the artifact's `executed.py` is written in text
    mode, so it does not hash to the sha256 in its `verification.md`.
    196 → 242 tests; 51 deliberate mutations, each caught.
    Measurement (the user's choice, written down beforehand in the session's scratchpad):
    `attempt A247883 A057246 A246855 A253773 A272621 A253380 A345338 A383336 A095751 A320768 --model
    --verify-s 60 --extend-s 120`, attempts 92-111, console log `data/offerC_measure.log`. No PARI program
    ran (dead ends or none). Every expectation held: the list question was asked for the 9 with strictly
    increasing known terms and answered right for all 9 (8 lists, A383336 a function); 0 `bad_index` in 20
    runs; A247883 and A057246 verified at generation 1 (then `extend_budget`, and `infeasible` at a 3,583×
    disagreement, offer F's case); A246855, A253773, A272621 and A253380 stopped at `verify_timeout`
    without the "prime instead of k" failure; A345338 `wrong_term` again; 5 repeats not run, 1 generation
    rejected for copying 7 known terms; no new term; 16 minutes of runs. Not expected: 7 of the 20 runs
    were identical programs run again after a `verify_timeout`, which the repeat rule allows (offer H).

25. **Offer G: no held-out value in a failure description (2026-09-19).** Planned in sections, with one
    critic agent from the plan to the audit. The evidence: of the 65 model runs, 23 were
    `wrong_term`; replaying each retry description, one carried a held-out value, attempt #105
    (A345338, list contract): `a(1) = -10031`, the held-out a(4) = 10031 with its sign flipped, which no
    "equals a held-out term" rule would catch. The critic confirmed it and found two more channels the
    plan had missed (the `bad_index` detail, where 5 of 17 real ones put a value in the index slot, and a
    crash's own message), that comparing absolute values breaks for values of 60+ digits (the harness's
    abbreviation counts the sign), that a value both shown and held out must stay shown (A111731), and that
    an offer-C test asserted the leak. The user chose to fix the failure details and leave the free text (a
    crash's message and stderr tail) as a known limitation, the CLAUDE.md rule reworded to match.
    `describe_failure` now leaves out a program value whose printed form, either sign, is that of a
    held-out term not also shown (`_held_out_forms`), in `wrong_term` details at any index and in
    `bad_index` details, with the wording already used for the list contract, so it does not say the
    value is a term. Tests: 6 new (242 → 248), the offer-C test inverted.
    The critic's audit found the change within the user's scope and two untested behaviours (a
    `bad_index` value printed in full, over 60 digits, and a negative one), now tested; the CLAUDE.md
    rule claiming more than the code (a value the prompt also shows is kept on purpose), now qualified;
    and a third unscrubbed text (a line the program printed that became a `protocol` stop), now named
    in CLAUDE.md and known limitations. 9 deliberate mutations, each caught. The critic's re-check
    confirmed every fix with four mutations of its own (all caught), found nothing broken and nothing
    beyond the user's scope, and G was closed.
26. **Offer H: no rerun of a program that timed out in the same model stage (2026-09-19).** In sections,
    with one critic agent from the plan to the re-check. The evidence, replaying the repeat rule over all
    65 model runs (25 stages): 26 runs had the syntax tree of an earlier run in their stage (all also
    byte-identical). 19 followed a deterministic failure, all before offer C's rule existed (ids up to
    85). The other 7 followed a `verify_timeout`: #95, #96, #98, #99, #103, #108, #109, reruns of 4
    programs in the offer-C measurement. Each timed out again with the same number of known terms
    reproduced, 421.6 s of the measurement's 16 minutes. No model run has stopped at any other resource
    or host stop, and no program ran in two stages. After a "not run" rejection the model has sent the
    same program again (A095751), so H saves time rather than bringing a different program.
    `codegen.REPEATS_IN_STAGE` is `db.DETERMINISTIC_FAILURES` plus `verify_timeout`, and
    `generate_and_verify` records a failed program for the repeat check when its stop is in it: every
    generation of a stage runs under the same verify budget. `db.DETERMINISTIC_FAILURES` is unchanged,
    since adding the timeout there would make a timed-out PARI program a dead end at every `--verify-s`.
    The critic confirmed the evidence and found: the plan's reasons for leaving `cpu_cap` (the Windows
    job has a CPU cap too) and `output_cap` (it comes from the program) out were wrong, though leaving
    them out is right; 5 of the 30 PARI timeouts had under 80% CPU, so a timeout on a busy machine can
    happen and still counts as a repeat (a known limitation; no guard, as `db.is_dead_end` has none); an
    end-to-end test was more than needed (dropped); two doc pages were missing from the plan. Tests: the
    `verify_timeout` case moved from "run again" to "not run again" (248 tests still). The audit found the
    code within H and correct, and: a program first failing in generation 2 was untested (for every stop,
    a gap from offer C; the commonest real case), a timeout reproducing some terms was untested (the fake
    runner reported 0), a count in the docs (7 reruns, but of 4 programs), and the module docstring still
    stating the old rule. All fixed; 9 deliberate mutations, each caught. The re-check confirmed the
    fixes and found nothing new. Side effect: a repeat that is not run adds no `failed` row, so no
    doubling of the selection penalty (offer D): the offer-C stages of A246855, A253773 and A383336
    would each have added one doubling instead of three (all three are at or near the ×64 cap anyway).
27. **Offer F: no infeasible stop on an untrustworthy projection (2026-09-19).** In sections, with one
    critic agent. The evidence: one real `infeasible` stop in the database, attempt 93 (A057246, 3 points,
    3,583× disagreement, high 13,026 s, merit unknown). Replaying `estimate.assess` on every term log
    (each known term projected from the ones before it as if it were the first new term, at 60, 120,
    300, 1800 and 10,800 s): 34 stops, 33 on untrustworthy fits; 9 wrong (A274508's a(16), A350878's
    a(14) and a(15)), 7 right, 18 unknown. Trust did not separate them. The plan recommended judging an
    untrustworthy fit by the low end of its range (0 wrong, 5 right on the replay's budgets). The critic
    confirmed every count and showed that this came from the budget grid: with the remaining time
    shrinking as an extension runs, the low-end rule still stops finished terms (A350878's a(14): low
    44.5 s, actual 0.3 s), 10 of 28 finished untrustworthy projections took less than their low end, at
    1800 s and above both options are the same, and all 6 real time projections were untrustworthy, so
    either option in practice turns the time check off. The recommendation changed to F as written, and
    the user chose it. `estimate.assess` makes a term infeasible on time only on a trustworthy cost fit;
    otherwise a reason says it was not judged on time; the disagreement-over-10 rule is gone. Tests:
    3 new functions (248 → 254): the replay's untrustworthy projections at budgets from 1 s to 3 h, a
    trustworthy one still stopping on its high end, a drift-withdrawn one too, and the harness driven
    in memory past an untrustworthy projection, keeping the new term. The audit found the code exactly
    the user's choice, and: the memory check untested for an untrustworthy fit (two mutants survived;
    now tested), a wrong count wording and a wrong end state (`timeout` cannot end a verified run), the
    stale projection counts in known limitations and the dashboard page (13 predictions, 6 with a time
    estimate; 5 points in the estimator view), and a reason that contradicted a memory stop. All fixed;
    13 deliberate mutations, each caught, including the two options not chosen. The re-check confirmed
    the fixes and found nothing new. Cost, as told to the user: a run whose projection is untrustworthy
    now spends its whole remaining extension when the term does not come. Found later the same day:
    `test_verify.py::test_extension_stops_when_next_term_is_projected_infeasible`, already flaky on
    timing, gained a failure mode from F (a noisy run whose deciding projection is untrustworthy ends
    `extend_budget` instead of `infeasible`); it passed during F's tests and audit. (Corrected in item 30:
    F cannot affect that test, whose cost fits are always trustworthy; the `extend_budget` ending likely
    came from a starved machine, as it did under load.)
28. **Offer D: the failure penalty counts attempts, not rows (2026-09-19).** The user asked for D and E
    "one item at a time and slow", in subitems, with a critic. The evidence: the 111 rows form 63
    attempts (one `attempt_sequence` call each: session rows by session and sequence, the 40 standalone
    rows by runs of one sequence, a grouping proven by model generation numbers restarting at 1 in each
    call, PARI rows first and equal known terms and budgets within each). Per-attempt counting changes 17
    of the 44 penalised sequences (A246855, A057246, A247883 ×64 → ×8; A383336, A129250, A253380,
    A253773, A272621 ×64 → ×4; ...), all through model generations or two PARI programs in one attempt;
    their share of the pick weight is small either way (0.07% → 0.09% of the PARI pool). No test covered
    the penalty. The critic corrected two statements the user would have read (9 sequences have only
    model rows, not 13; without a backfill the 17 would never change, not "until attempted again"),
    proposed the no-write option (grouping session rows at query time: 14 of the 17, but not the three
    ×64 ones in the PARI pool) and the key's name. The user chose per attempt with a backfill.
    Subitems: D1 `_Attempter` makes one uuid per call and every run row stores it in
    `extra.attempt_call`; D2 `select.candidates` counts distinct keys, a row without one (or with an
    unreadable `extra`) on its own; D4 tests (254 → 256: the count's rules one by one, and end to end a
    failed PARI run and a model generation as one attempt, a second attempt as another, the key on a
    win's row and through `retry_pending_rechecks`), 12 deliberate mutations, each caught (the first
    run let "verified rows not counted" through: the verified case was split); D3 the backfill, a
    scratch script, dry-run on a copy first; D5 docs. The audit found the code, tests and docs correct,
    and one real defect in the backfill script: its checks ran after the commit, so a failed check would
    have left the rows written. It now runs in one `BEGIN IMMEDIATE` transaction, rolled back on any
    failure (proven on copies: a wrong expectation leaves 0 keys; a second run is refused), and checks
    that no PARI program appears twice in a group. The re-check tested the transaction under an
    interrupt and a competing writer and found nothing new. Applied: `data/oeisbot-before-offerD.sqlite3`
    first, then 108 rows written in 63 attempts (60 distinct keys: 3 attempts were skips), exactly the 17
    expected changes, 385 `is_dead_end` answers unchanged, every other column and `extra` field unchanged;
    afterwards `attempts` still 111 rows, the pool still 3,568, integrity ok.
29. **Offer E: the hold-back rule reversed (2026-09-19).** The evidence: the rule had never held anything
    back (0 at the default, 1800, 300 and 120 s budgets; the only entries whose two PARI programs both ran,
    A101722, A101569 and A101583, both timed out verifying, alike). 300 of the 5,316 PARI-bearing
    candidates have two or more runnable programs; 223 of them are one template ("numbers n such that
    (c·10^n − d)/9 is prime", one block computing the number, the other building it), both doing the same
    primality tests. The plan recommended confirming the rule on that ground. The critic corrected it:
    under the rule a sibling of a program that verifies never ran in the PARI stage at any budget (at a
    longer `--extend-s` the first program runs first again, verifies and ends the stage; its test shows
    it), not just "at that budget" as the docs said; "3 h per sibling" held only for `extend_budget` (an
    `infeasible` dead end can only come right at verification); and the rule acts only after a program
    verifies, while 220 of the 223 template entries need primality proofs for numbers of over 1000 digits
    just to verify, so the rule never reaches them. The reachable entries are mostly ones whose siblings
    differ (13 of them use a different primality test). The recommendation changed to reversing, the
    critic added the middle option (hold back after `extend_budget` only), and the user chose to reverse.
    Removed: the constant naming the two budget dead ends, the plan's held-back list, the step in
    `pari_plan`, its log line and its `nothing_to_run` wording. The two hold-back tests inverted (256 tests still): after a used-up extension
    the sequence stays in the PARI-only pool and a later attempt runs the next program, which wins; after
    either kind of budget dead end the others run in order. 7 deliberate mutations, each caught; the
    audit's own mutant (only the next sibling kept after a dead end) survived the first version, because
    the next sibling won; that sibling now fails, so the one after it must run too. The audit also
    corrected "up to three extensions" (the cap of 3 is per attempt; across attempts every runnable
    program gets one) and "indices over 1000" (numbers of over 1000 digits). The re-check found nothing
    new. Found on the way, not changed: a flaky timing check in `test_verify.py` (fixed in item 30).
30. **The flaky test fixed (2026-09-19).** `test_verify.py::test_extension_stops_when_next_term_is_projected_infeasible`
    ran a doubling brute-force program (known terms a(0)..a(18)) through the sandbox with a 2 s extension
    and asserted the run stopped `infeasible` (line 191) inside the extension (194), with every finished
    term within 4× of its projection (200). The evidence: the test's call run 210 times, every assertion
    evaluated on its own and every assessment kept. 35 runs failed (1 in 6): line 200 in 32, line 194 in 6
    (3 both), line 191 in none. The cause is wall time the program did not spend computing: in 64 runs a
    term of 1-140 ms (a(15)..a(22), 0.06-0.22 s into the run) took 0.2-0.4 s more wall time than CPU time
    (in 3 more line-200 failures, 0.16-0.19 s), with the next term normal, so the program was held up, not
    the parent's reading. That term's projection was up to 21× short, and since the rate is taken from the
    last five fitted terms, the next three or four were up to 18× long. Line 194 failed when the kill took
    longer than what was left of the extension (-0.06 to 0.38 s left; the kill took 0.02-0.40 s, 0.07 s
    at the median over all runs). Under full CPU load (one burner per core, 18 runs) verification took
    24-40 s, the kill 2.4-5.2 s, and line 191 failed twice: a(19), projected at 0.017 s, was still running
    when the 2 s extension ran out, and the run ended `extend_budget` 2.44 and 2.52 s after a(19) started. This corrects item 27: offer F
    cannot affect the test. Its cost unit is `work`, reported exactly as 2^n, so the cost fits of all
    1,463 projections (and all 18 under load) were trustworthy, with disagreement 1.00 and 12 points, and
    F changes only what happens on untrustworthy cost fits. The 2 line-191 failures of 30 after F (0 of 30 before, a
    difference within chance) likely came from a busier machine; `flaky_compare.py` kept only the first
    failing line, so they cannot be checked. The fix, in the test only: the extension's infeasible stop
    moved to `test_estimate.py` under the same name, through `run_attempt` with `sandbox.run` replaced by
    a replay at controlled times (after 0.05 s of start-up, a(n) takes 2^n × 32 ns, as on this machine), so each
    projection is exact and the stop comes on a(24)'s line (a(19)..a(24) take 1.057 s; a(25) would take
    1.074 s with 0.943 s left), before a(25) starts, with no censored time. In the sandbox,
    `test_verify.py::test_infeasible_stop_ends_the_sandboxed_run` runs the real program with no extension
    time, so the stop is certain (a fitted term always took some time) and comes in the callback that
    verifies a(18): it asserts the sandbox ended the run on that stop. The 4× accuracy check on real
    timings was dropped (the user's choice); the in-memory test checks each projection exactly, and
    accuracy on clean data was already tested. Tests: 256 → 257. The critic corrected the evidence (a
    projection count, the stalls on the longer terms, the causes' list), and found two mutants the plan
    said were caught that its tests as written let through (a stop recorded but not requested to the
    sandbox, stopped by the next tick instead; `dt` as time since start, compared with itself), and a
    0.001 s extension a burst of late reads could have met; all adopted. 10 deliberate mutations, each
    caught: a missing kill by `test_sandbox.py::test_on_tick_can_stop` (the new tests leave the kill's
    timing to it), and lines still passed on after a stop by `test_verify.py`'s
    `test_correct_program_is_verified_and_extended` and `test_gp_program_verified` (3 of 3 runs each; the new sandbox test catches it only when a(19) arrives before the kill, 2 of 7). The
    audit found that last mutant covered after all (the first report called it a gap), a stall count of
    56 that should be 64 (run ids repeat in the joined data), and a claim the data did not hold (that
    a(19) got no CPU under load); its own four mutants were caught. The new tests passed 50 of 50 runs
    each, and the sandbox one 3 of 3 under full CPU load. Found on the way, not changed: on terms of 0.3-0.8 s wall time runs about
    1.5× CPU time at the median; the sandbox runs programs at below-normal priority.
31. **Session 6: the full-extension PARI run (2026-09-19).** The user: "Tackle item 1 now." Next step 1,
    run as `run -n 20 --verify-s 60 --extend-s 1800 --seed 206`, no `--model`; 22:35:35Z to 00:50:45Z,
    **8,110 s wall**, 21 program runs over 20 picks, **4 verified, 15 `verify_timeout`, 2 `incomplete`,
    0 skips, 0 new terms**. Console in `data/session6_pari.log`; the pre-run database copy is
    `data/oeisbot-before-session6.sqlite3`.

    **Predicted in advance, then checked.** Because `run_session` draws every pick before the first
    attempt, the exact 20 A-numbers were computed read-only beforehand and written down with eleven
    hypotheses. All eleven held: the picks and their order were **identical**, the console's pool line was
    byte-identical to the predicted string, 21 runs matched "20 or 21" (A101011 ran both its programs),
    the 15 timeouts ran 60.14–60.53 s, the four verified runs used 1800.47–1801.91 s at 0.98–0.99 CPU
    share, and the pool moved 3,566 → **3,546** with dead ends 31 → **51** — the pre-registered "both
    A101011 programs fail" branch. Wall clock came to 8,110 s against a predicted 8,100 s (+0.12%).
    4 verified sat inside the predicted 90% range 1–7, above the point estimate 3.

    **The audit reversed the headline.** The first write-up claimed the run showed offers B, A and F
    working, because 4 of 4 verified runs used their whole extension where 2 of session 5's 3 were killed
    early. That is wrong: none of the four produced a cost fit, so `seconds_high` was `None`, and the
    **pre-offer-B** `kill_after_s` (`1b6881d`) already returned `None` in exactly that case. The old code
    would have produced the same four rows, and the database already held two pre-offer-B full-extension
    runs (#55, #56), both with 0 points above the noise floor. Session 5's kills happened on runs that did
    produce fits (npoints 3, disagreement 4.76 and 5.19), conditions session 6 never recreated. **Session 6
    neither confirms nor challenges offers B, A and F.** What it does constrain: 4 × 1800 s exercised
    `estimate.assess`'s `proj is None` early return, where feasibility falls back to the memory test
    alone, with no spurious `infeasible`, `finished` or resource-cap stop — the branch the plan review had
    flagged as the live risk. The audit also withdrew H7's "+0.0 s session overhead" as vacuous
    (`db.finish_session` *defines* `machine_s` as `SUM(runtime_s)`, so it is identically zero) and
    corrected the structural mechanism below.

    **Two corpus-wide findings, neither needing another run.** Over all 64 PARI program runs ever
    recorded, **0 of the 31 with more than 10 known terms has ever verified, against 15 of 33 at or below
    10** (verified median 6 known terms; timeouts median 12, range 2–72). The confound is ruled out: pick
    weight tracks population share across known-term buckets, so this is the verify gate's doing, not
    `select.difficulty`'s. And replaying every verified run's first projection from its term log:
    **`project()` gave no fit in 11 of 15, the 4 fits all had `npoints = 3`, and `npoints >= 4` has never
    been reached** — so no verified run has ever been *able* to produce a trustworthy projection
    (`trustworthy` needs disagreement ≤ 3 **and** npoints ≥ 4). The cause is the cost cliff (item 16), not
    the number of known terms: A277532 has 6 known terms and produced a fit, A247883 has 10 and had 0
    points above the floor. Session 6's four verified in 0.063–1.544 s, far below `WORK_FLOOR`/`CPU_FLOOR_S`.

    **A third finding and a new limitation.** Both `incomplete` rows (A147803, A147800, 0 terms in 0.0 s)
    come from PARI blocks calling `A007947`, defined in another OEIS entry and nowhere in the block. The
    diagnosis is inferred from the entry source, because the run records nothing: `verify._result` reaches
    `INCOMPLETE` only on `exit_code == 0` and **discards `res.stderr_tail`** there, no term log is written,
    and `extra.log` names a file that does not exist (new known limitation). Sizing over the pre-run pool
    is method-sensitive but the conclusion is not: 54–60 affected entries, 1.85–2.05% of pick weight,
    ~0.4 expected wasted picks per 20, so drawing 2 was a ~5% outcome; the affected entries cluster in
    families (A147800, A147803 and A147805 all). The cost is one pick per sequence *ever*, since the row
    is a deterministic dead end.

    **Base rates for the next prediction**, superseding the 11/43 and 6/35 the plan used: **15 of 64 PARI
    program runs verified (23.4%)**, **10 of 55 sequences with a PARI run (18.2%)** → about 3.7 verified
    per 20 picks.

32. **Item 2: a run that produced nothing now says why (2026-09-20).** The user: "tackle item 2 next. I
    want to get more functionality in place before more runs occur." Next step 2 is done; no run was made.

    **The premise was checked first.** The whole fix rests on gp writing its error to *stderr*, which the
    limitation asserted but nothing had verified. Running a one-line file calling an undefined `A007947`
    through `tools/pari/gp.exe` with the harness's own flags (`-q -f`) gives **exit code 0**, nothing on
    stdout but a break-loop banner, and four stderr lines: `***   at top-level: ...`, a caret rule under
    the offending call, `***   not a function in function call`, `... skipping file`. The sandbox closes
    the child's stdin write end (`sandbox/windows.py:424`), so the break loop reads EOF immediately and
    the run ends in 0.0 s — which is exactly what session 6's two rows recorded.

    **The change.** `verify._stderr_tail(res, lines=3)` joins the last three stderr lines *that say
    something* with `" | "`, dropping blank lines and rules: keeping gp's caret rule would push out the
    line naming the call, the one line worth reading. Which stops carry a tail is an explicit list,
    `verify._TAIL_STOPS`: `incomplete` always, and `verify_timeout`, `timeout`, `memory_cap`, `cpu_cap`,
    `disk_cap` and `output_cap` when no term came out at all. `crash` keeps the tail in its
    own detail as before, now through the same helper, and each line is capped at `STDERR_LINE_CHARS` = 400,
    as every other program text in a detail is: a program may write the whole 64 KiB tail without one line
    break. In `attempt.Attempt.run`, `extra.log` is written
    only when the term log exists, the kept Python program is named as `extra.program` in its own right
    (it was only findable by deriving it from `extra.log`, which this change removes), and the session
    log prints `verify.CONSOLE_DETAIL_CHARS` = 300 characters of a detail instead of 160, through
    `verify.brief_detail`, which `codegen` uses for its per-generation line too (it had a 120 of its own).

    **Checked against the two rows that motivated it.** A147803 and A147800 were re-run through
    `pari.build_candidates` and the harness as the bot would run them (20 s verify, no session, nothing
    recorded). Both still stop `incomplete` at 0 terms with exit code 0, and their details are now 178
    characters and self-explanatory — and better than the one-line probe above, because gp names the
    entry's own function rather than the top level:
    `program ended after 0 terms: ***   in function A147803: ...n);for(a=1,n\2,a%p||next;A007947(n-a)*A007947( | ***   not a function in function call | ... skipping file 'program.gp'`.
    `A007947` appears at character 83 and the reason at 113, so 160 characters would have shown the cause
    and cut the sentence; 300 carries the whole tail.

    **The critic earned its place twice.** On the plan it found that the fix as written in the limitation
    stops short of its own goal: a 0-term run killed at the verify budget or by a sandbox cap still
    explained nothing, since only the `INCOMPLETE` branch was in scope. Extending the rule to those stops
    is what `_TAIL_STOPS` is. It also found that `known-limitations.md`'s "Text the program wrote itself
    reaches the retry as it is" ends "stderr is not stored, so that channel is unmeasured" — no longer
    true once a tail reaches `attempts.detail`, the dashboard and the model, and a user decision
    (not to scrub these texts) sits behind that paragraph, so it is updated rather than left to rot.
    Two of its suggestions were declined deliberately: the duplicate stderr in a model retry prompt
    (`describe_failure` adds 12 lines of its own) is left as it is, because that is already what `crash`
    does and the 12-line block is the more useful one; and `" | "` is kept as the join although a detail
    containing it would add phantom columns to the artifact README's table (`artifact.py:115`), since
    artifacts are written only for wins, whose stops never carry a tail.

    **The first attempt was wrong and the tests caught it.** Written as "any stop with no terms", the
    rule appended a traceback to a `protocol` stop whose contract error fires on the very first yield,
    breaking `test_the_driver_rejects_what_is_not_a_list`, which asserts that detail exactly. That stop
    already carries the program's own message, so the allow-list replaced the blanket rule. Each half was
    then mutation-checked: dropping the rule filter makes the gp test fail with the caret line in place of
    the call; reverting the `incomplete` tail fails both new stop tests while the no-stderr test still
    passes (so it is not over-asserting); dropping the `or not self.records` half lets a `verify_timeout`
    that did produce terms collect stderr; and restoring the unconditional `extra.log` fails the new
    0-term attempt test. **266 tests pass** (257 before, 9 added: six driven in memory with a fabricated
    `RunResult`, two through the sandbox, one through `attempt_sequence`).

    **The independent audit found nine defects, all real, none in the stop rule itself.** It walked every
    member of `Stop` against `_TAIL_STOPS`, reproduced gp's behaviour and every database figure on its
    own, and reported: the test count was stale in six places and is now 266 everywhere (`CLAUDE.md`,
    `development.md` twice plus two rows of its per-file table, `operations.md`, `status.md` twice);
    three pages said the run log is missing when a run "produced no term" when the rule is really *no
    term accepted*, which is what 26 of the 35 rows above (`wrong_term` and `bad_index`) actually are;
    this item claimed "a real row now reads" for an example no row had ever produced, which is why the
    two real ones were measured and are quoted above; the reason given for widening the console line was
    wrong (what runs past 160 characters is the end of the tail, not the name of the missing call);
    `codegen` kept a 120-character cut of its own, so the documented 300 was not true of a model run's
    line, now fixed by sharing `brief_detail`; the new limitation text said the tail reaches artifact
    JSON, which it cannot, since an artifact is written only for a win and no win's stop carries a tail;
    an unbounded stderr line could put 64 KiB in a detail, now capped; the `or not self.records` half of
    the rule was covered by no test (deleting it left all tests green); and the `crash` branch this change
    edited had no test of its own, before or after. The last three were fixed in code, the rest in the
    docs. Two notes it raised but did not call defects were checked and acted on. `LAUNCH_ERROR` was dead
    weight in `_TAIL_STOPS`: both of `sandbox/windows.py`'s launch failures (340, 418) build their
    `RunResult` before any process exists, so `stderr_tail` is always `""` and the detail already names
    the reason; it has been removed from the list. And `verify.py`'s mid-stream
    `_halt(Stop.INCOMPLETE, "reproduced X of Y known terms")` is indeed unreachable: indices are strictly
    consecutive from the offset, every known index lies in that range, and `KnownTerms.count` is
    `len(values)`, so reaching the last known index implies every known term was reproduced. It is left
    in place as a guard rather than removed under this item — see next steps.

    **Not fixed retroactively.** 35 of the 129 run rows written before today name a run log that was never
    created — 14 `wrong_term`, 12 `bad_index`, 6 `crash`, 2 `incomplete`, 1 `verify_timeout` — because a
    term is logged only after it passes its checks, so a run whose very first term was wrong logs none.
    That is more than the two `incomplete` rows item 31 counted; the condition was never specific to them.

33. **Item 3: PARI blocks that call another entry's helper are rejected before they run (2026-09-20).**
    The user: "tackle item 3 now. go slow and review work as you go to avoid defects." Next step 2 is
    done; no session was run.

    **What gp actually does decided the rule.** An unknown name is not an error in gp by itself — it is a
    polynomial variable. Run directly against `tools/pari/gp.exe`: a **call** `A007947(n)` always errors
    ("not a function in function call") and an **index** `A007947[n]` always errors ("incorrect type"),
    but a bare mention often does not — `n + A007947` prints the expression unevaluated, `#A007947` returns
    2. So
    `pari.undefined_a_numbers` flags calls and indexes only. Bare mentions are left to fail later, where
    item 32's stderr tail now explains them.

    **Definedness is read generously on purpose.** A name wrongly called undefined throws away a program
    that runs; a name wrongly called defined costs only the pick it would have cost anyway. So any
    definition, assignment, parameter name or `my()`/`local()` declaration counts, and strings and
    comments are masked out with the module's own `code_mask`. The check runs on `Program.executed`, the
    text that actually runs — not the block — because driver statements are dropped for the function
    forms, and a helper named only in a dropped statement is never called.

    **Validated by running every program it rejects.** All 71 rejected candidates (65 entries that lose
    every candidate, 5 that lose one of two) were run through the real harness at an 8 s verify budget
    before the check was wired in: **none reproduced its known terms** — 70 `incomplete`, and A130288
    `wrong_term`, which returns a wrong first term before it ever reaches its undefined call. 69 of the 71
    details name the missing helper, which is exactly the cheap validation route item 32 predicted. So the
    rule costs nothing: no working program is lost.

    **Two sizing errors, both mine.** Item 31 said 54–60 entries, 1.9–2.1% of pick weight and ~0.4
    wasted picks per 20. Its *entry count* was wrong — it matched block text instead of asking which
    blocks produce a candidate; the real number is **65** that lose every candidate, 5 more that lose one
    of two. Its *weight* was right, and my first attempt to "correct" it to 1.40% / 0.28 made it worse:
    that is the share of the whole 5,316-candidate corpus, but a session draws from
    `select.candidates(require_langs={"pari"}, keep=Runnable(...))`, which has already filtered the pool
    to **3,552**. Against that pool the 65 are **1.97%** of the pick weight and **0.39** picks per 20, so
    item 31's figure stood all along. With `--model` on it is 0.47% and 0.09, because nothing leaves that
    pool — which is why the slip was easy to miss, those two numbers being right either way. The session
    pool shrinks by 58 rather than 65: 5 of the entries were already `verify_out_of_reach` and 2
    `all_programs_dead_ends`.
    My first *entry* count was wrong too, at 59, because it treated every identifier inside a parameter
    list or a `my()` as a *definition* — so `A242998(n, p = A000043[n])` counted `A000043` as defined when
    it is the very thing being used. The critic's independent prototype said 65, the diff exposed the bug,
    and measurement and production now share one implementation so they cannot drift again.

    **The critic also caught four things the plan would have missed**: `oeisbot stats --forms` would have
    filed these 65 under "no usable function (unsupported)", which is untrue of them, so `cli.py` gets a
    bucket of its own and `strategies.md`'s coverage table moves 65 out of the runnable rows (15
    predicate, 48 `a(n)`, 2 print loop: 3,990 runnable becomes 3,925); the payoff — removal from the pool
    — is pinned by `test_attempt.py`'s parametrized selection test, not by anything in `test_pari.py`, so
    a row was added there; `docs/pipeline.md`'s left-out snapshot and the `pari.py` module docstring both
    needed the new reason; and `Rejected` carries only a block number while `split_signed_programs` cuts a
    block into parts, so the reason says "not in this program" rather than implying the whole block —
    A277317 really does define its helpers in a *different part* of the same block, and A383301 in a
    different block entirely.

    **Ten mutants, all caught**: dropping the index arm of the use regex; counting a default value's
    identifiers as definitions (the bug above); not masking strings and comments; checking the raw block
    instead of the script; reading `==` as a definition; removing the rejection altogether; dropping each
    of the three parameter sources (named, by reference, closure); and honouring a bare `my(x)` as a
    definition. **274 tests pass** (266 before, 8 added: 7 in `test_pari.py` and one row of the selection
    test).

    **The independent audit found eight defects and confirmed the rest.** It re-ran all 71 rejections
    itself (0 verified) and reproduced every corpus figure, then reported: the pick-weight denominator
    above; that `n + A007947` does not print what this item claimed; that "any parameter name counts as
    defined" was untrue of closure parameters `(x) -> ...` and reference parameters `&x`, both of which
    gp really does run — now handled in code, so the claim is true rather than softened; that the
    `my()`/`local()` branch was dead weight, unreached by any test and able only to suppress correct
    rejections, since a bare `my(x)` is exactly what gp still errors on — deleted, and the deletion is
    pinned by a test; a misaligned column in `stats --forms`; a missing print-loop rejection test and an
    assertion filed under the wrong test name; two code docstrings that claimed such a program "can never
    reproduce the known terms" when eight of the 71 emit 1–5 terms first; and an example in
    `verification-and-estimation.md` drawn from a sequence this item stops from ever running.
    One of its mutants appeared to survive; the mutant was malformed — a `` had become a literal
    backspace, so its regex matched nothing. Rebuilt properly, the test catches it.

34. **The smaller follow-ups, next step 2 (2026-09-20).** The user: "tackle #2 before moving onto #1. Go
    slow and review your work as you go. Spin up a critic agent to ensure best practices are followed and
    no defects are introduced." Nine sub-items; **six became code, three became corrected documentation.**
    274 → 294 tests, **33 deliberate mutations, each caught**, every file restored byte for byte.

    **The evidence came first, and it reshaped the list.** Measured read-only against the real database
    before any code: no win, pending re-check or review has ever existed and `data/pending/` had never
    been created (so the pickle work is preventive, and nothing had to be migrated); exactly one run ever
    ended `infeasible` (#93 A057246) and it was judged on **time**, not memory, with 0 `memory_cap` stops
    ever; all three `incomplete` rows carry the wording of the `_result` branch, not the mid-stream
    guard; and the stored `difficulty` column matched what selection computes for all 26,814 rows — for the 68
    with a b-file because `fetch-bfiles` had rewritten it after the last sync, and for the other 26,746
    because with no b-file facts to add, the entry-only score and the stored-row score are the same
    number.

    **What was done.**
    - **Pending wins are JSON, not pickles.** Written field by field, enums by value, known-term indices
      and program-reported integers as strings, indented, with a `format` version; on loading, each saved
      field set is checked against its dataclass, so a field added or removed since the save is a named
      `ValueError` instead of a silently defaulted value. Tests pin the program sha, both enums, the
      int-keyed known terms, a 1268-digit term, and an artifact rebuilt from the reloaded result **byte
      for byte**.
    - **A re-check that keeps failing says so** (`extra.recheck_failures`, reset when the error changes):
      `still pending (URLError: ...) -- the same way 7 times now`. It is still retried for ever, and the
      counter's own database failure cannot cost the win (invariant 7).
    - **The `infeasible` dead end keys on the cap the run got** (`extra.mem_cap_bytes`), so a run squeezed
      by a busy machine is no longer retired for good at that budget.
    - **`sync` no longer leaves `difficulty` stale**: it recomputes the column from the stored rows in one
      `executemany` in one transaction.
    - **A capped `run -n` says so**, including when the cap truncates an explicit list.
    - **The unreachable `incomplete` guard is kept**, with the reason in the code and a white-box test.

    **The critic was right about almost everything, and I was wrong three times.** It reproduced every
    database figure by its own route and then found: that **E was the user's decision, not mine**
    (status.md says "decide"); that doing the JSON change *last* could strand a pickle written by a
    session run mid-bundle, so A moved before B; and a better option for C than either of mine — compare
    the stored effective cap against the *configured* budget, which needs no new `AttemptResult` field and
    keeps selection independent of free RAM, where the documented fix would have made `is_dead_end` read
    live memory and picks stop being predictable. My three errors: `attempt.py` is **CRLF**, not LF (the
    mutation checks claim byte-for-byte restoration, so the list mattered); "an added field is a loud
    `TypeError`" is **false** for a field with a default, which is what every class here has, so the
    explicit field-set check replaced it; and my cost objection to reading free RAM was wrong —
    `avail_phys_bytes()` takes **1.36 µs**, 5.4 ms over a 4,000-row scan, so the real objection is
    reproducibility, not cost.

    **One of its claims did not survive.** It said ingest forbids gaps in known terms; my probe accepted
    one. Re-checking settled it in the critic's favour and against my probe: the gap I built was filled
    from the DATA line, and a genuine gap *is* rejected (`known terms have 2 gaps, first at n=3`). Driving
    the production `on_line` with hand-built gapped known terms anyway, the guard still never fires — a
    third independent derivation of item 32's proof, after the critic's 4,677-stream sweep.

    **A mutation found a claim that could not be tested.** Writing the pending file in text mode survived
    the whole suite, because `json.dumps` emitted one ASCII line with no newline to translate — so
    `write_bytes` was an unverifiable precaution. Indenting the file (which `operations.md` sends a human
    to read) made the property real, and the mutant is now caught.

    **The independent audit found three defects, one of them mine and serious.** Re-running the same
    critic over the finished diff:
    - **The failure counter broke invariant 7.** `_note_failure` guarded only `json.loads`, so an `extra`
      that parsed to a JSON *array* reached `.get` and raised `AttributeError` — out of
      `retry_pending_rechecks`, which `run_session` calls before picking, so **one hand-edited row would
      have crashed every `oeisbot run` at startup**: the exact failure history item 10 records having
      already been fixed once. Reproduced here before fixing (`[]` raises; `{}`, NULL and unparseable text
      do not). The whole read is now guarded, and a test drives six shapes of `extra` through a session.
    - **Five mutants the suite could not catch**, all confirmed by running them: dropping the field-set
      check for `AttemptResult`, `KnownTerms` or `Prediction` (the parametrized test damaged only four of
      the seven classes — and `AttemptResult` is precisely the one that gained a field below); a
      `COALESCE` fallback in `is_dead_end` letting a pre-2026-09-20 row count on its configured budget
      (no test used the shape every real row has: budgets stored, no cap); and `refresh_difficulty`
      skipping retired rows. Each now has a test.
    - **The source of the memory cap was wrong.** I stored `RunResult.mem_cap_bytes`, the sandbox's own
      reading, while the verdict was reached against `Harness.mem_cap` — the same formula read an instant
      earlier. My defence, that the exposure was "a race at exactly the threshold", was **wrong**: any
      release of memory by another process between the two reads, anywhere in the starvation band, makes
      the stored cap overstate the one the verdict used, which is the direction that wrongly keeps a dead
      end. Rather than document the caveat, `AttemptResult` now carries `mem_cap` and the recorded number
      is the one `estimate.assess` was given. A test gives the harness and the sandbox deliberately
      different views of free RAM, so the recorded value can only have come from one of them.

    It also **confirmed the indented-JSON decision** (it reproduced the surviving text-mode mutant), and
    six stale or overstated doc lines, all corrected — including this item's own claim that the
    difficulty column matched "because `fetch-bfiles` had rewritten it", which explains 68 rows of 26,814.

    **The re-check of those fixes found three more**, the first of them a consequence of one of the
    fixes: deleting a redundant `isinstance` guard (a mutant showed the outer handler already covered it)
    left the *restart value* as that branch's only behaviour, and `times = 0` in place of `times = 1`
    passed the whole suite — now pinned; `development.md` said `test_db.py` had 14 test functions when it
    has 13, and none of the round's three new pieces of coverage was described in its table; and
    `pipeline.md` claimed only that *writing* the counter cannot cost a win, when the exposure the audit
    found was in *reading* `extra`. It also established, by measuring SQLite directly, why leaving
    `db.set_recheck_result` alone is right and not merely convenient: `json_set` on a non-object returns
    it **unchanged** rather than blanking it, so `attempt_call`, `log` and `program` survive — and that
    statement is shared with `db.record_win`, so "repairing" a malformed `extra` there would mean
    rewriting a row's `extra` on the winning path.

    **Three mismatches became documentation instead of code**, each with the evidence: mismatch 1's
    proposed fix is a **no-op** here (`select.pick` already zeroes a chosen leaf, so a sequence cannot be
    drawn twice in a session, and the penalty is per-A-number, so it cannot move any other candidate's
    weight — the spec assumed sampling *with* replacement); mismatch 3 (the POSIX backend) cannot be
    tested on a machine with no Linux, WSL or Docker; mismatch 5 (no CPU-time limit) is deliberate, since
    wall clock is the unit every dead-end rule reasons in. The user can still ask for any of them.

35. **Session 7: the `--verify-s 600` pass, and the project's first new terms (2026-09-21).** The user:
    "Do step 1 — the run `--verify-s 600` pass now." Planned with a written prediction page (P1-P12),
    reviewed by a critic before the run, audited by a fresh critic afterwards, and the audit's three
    decisive claims then re-derived independently here. **20 attempts, 4 h 11 m, 15,073 s of machine
    time, 1 win.** Three results, only one of which the plan anticipated.

    **A385331 was extended by 18 terms, a(25)..a(42)** — attempt #139, the first `outcome = 'extended'`
    row and the first `reviews` row the project has ever written. It reproduced all 24 known terms in
    **0.157 s**, produced the new terms in 731.8 s, and was then stopped by the first `infeasible` kill
    on a real run. The oeis.org re-check ran before the artifact was written and confirmed the live
    entry still ends at a(24). **Nothing has been submitted, and nothing here changes that**; the
    artifact exists so the user can decide. Invariant 7 held on the first occasion it ever mattered: the
    row was recorded as `recheck_pending` and saved to `data/pending/` before the re-check, and there is
    no window in which the win was unrecorded.

    **The new terms were re-derived from the sequence's name, not from the entry's program.** The n-th
    numerator of the partial sum of Liouville's constant is `N(n) = sum_{k=1..n} 10^(n!-k!)`, so a prime
    q's divisibility is testable by Fermat as `sum_k 10^((n!-k!) mod (q-1)) mod q`. The critic swept
    primes to 10^6; this session then swept to **2x10^8** with its own sieve, validated exactly against
    trial division. **All 41 terms agree** — the 23 known ones from a(2) and every one of the 18 new
    ones, including a(25) = 174,443,251, whose minimality needs 9,737,494 trial divisions. Be precise
    about what this is worth: it shares no *code* with `program.gp`, and deriving `N(n)` from the
    definition is genuinely independent work, but it is the same *algorithm* — trial division by rising
    primes — so it is one route run twice at two bounds, not two methods. The 10^6 sweep also leaves
    a(25), a(32), a(37) and a(38) unsettled, so those four rest on the deep sweep alone. Two structural facts fell out and both check: `N(n) = 1
    (mod 10)`, so no even prime and no multiple of 5 can ever appear (which is why the entry's program
    starts at 3); and the digit sum of `N(n)` is `n`, which *proves* the entry's own `a(3k) = 3`.

    **Offer F acted on a real run for the first time, six times, and is what made the win 18 terms
    instead of 8.** Every projection is made when the previous term arrives; the pre-offer-F rule stops
    a run whenever `s_high` exceeds the remaining budget, whatever the fit is worth:

    | n | remaining | projected high | pre-F | today |
    |---|---|---|---|---|
    | 33 | 1279 s | **3.49e+08 s** | infeasible | feasible |
    | 34-37 | 1279 s | 1.9e+09 .. 3.1e+11 s | infeasible | feasible |
    | 38 | 1221 s | 3,737 s | infeasible | feasible |
    | 39-42 | 1068 s | 393 .. 918 s | feasible | feasible |
    | 43 | 1068 s | 1,217 s | infeasible | **infeasible (fired)** |

    At n=33 the estimator projected **eleven years** for a term that cost 0.0006 s. Offer F refused to
    act on a fit the estimator itself did not trust, and the run went on to a(42). Pre-offer-F it halts
    at the n=33 projection with a(25)..a(32) — **8 new terms**. This is the direct answer to the
    question the run was built to ask, and it is a clear positive.

    **Offer A also acted for the first time, and cost 1,005 s for nothing.** A229209's first projection
    (attempt #138) had `npoints = 5`, `disagreement = 1.754`, `Projection.trustworthy = True` and
    `rate_drift = 7.79`. Pre-offer-A the term would have been killed at 795.4 s; it ran 1,800.4 s and
    produced no term. One sample, and on this sample the rule was a pure cost — but it is the first live
    measurement of it. **Offer B remains untested**: no untrustworthy projection's term ever approached
    twice its `seconds_high`.

    **The `infeasible` kill at a(43) was correct.** The audit reversed this session's own headline, which
    had called it a false positive on the grounds that 14 of the 18 new terms cost under the 0.05 s noise
    floor and were invisible to the fit. Every mechanical step of that analysis is confirmed — 5 of 41
    points above `CPU_FLOOR_S` (n = 20, 25, 32, 37, 38), `npoints = 5`, `disagreement = 1.483`,
    `rate_drift = 1.023`, `value_dependent = 0`, both value-dependence detectors blind — but the
    conclusion was wrong. **a(43) > 2x10^8** (verified here), so gp must test at least 11,078,936 primes
    before it can return. Calibrating on the run's own four expensive terms, the cost laws fit like this,
    and the floor each puts under a(43) using its own **smallest** measured constant:

    | law | spread over the 4 terms | a(43) floor |
    |---|---|---|
    | `c * pi(a) * n^2` | **1.03x** | 1,510 s |
    | `c * pi(a) * n * log2(n!)` | 1.13x | 1,626 s |
    | `c * pi(a) * log2(n!)` | 1.34x | 1,070 s |
    | `c * pi(a) * n` | 1.57x | 878 s |
    | `c * pi(a)` | 2.39x | 510 s |

    The two laws that actually fit both put a(43) at **1,500-1,650 s against the 1,068 s it had left**,
    so the stop was right; the laws that give a lower floor are the ones the data rejects. (The 1,626 s
    figure is in CPU seconds, the unit the run's `cost_unit` used; in wall seconds it is 1,645 s. Note
    `n^2` fits *better* than the law quoted first here, which was picked before that comparison was run.)

    **What survives of that analysis is still worth acting on**: in the same run the estimator made
    **four trustworthy projections wrong by 10^4 to 10^6** (288-632 s predicted for terms that cost
    0.0005 s). They were harmless only because they happened to fit inside the budget. Right answer at
    a(43), unsound process.

    **The 600 s verify budget itself did nothing.** Of the 20 picks only **A019288** needed more than
    60 s to verify (497.3 s), and it produced nothing in a full 1,800 s extension. Every other run that
    got through the gate — including the win, at 0.157 s, and both many-known-term runs — would have
    cleared a 60 s gate. Counting A019288's whole attempt plus the 11 timeouts' extra 540 s each,
    **~8,177 s of 15,073 s (54%) of the session went on the budget increase for zero return**; at 60 s
    these same 20 picks cost ~6,900 s, i.e. **2.2x more picks per hour**, and picks are what produced
    the win. A385331 is a `pari:a(n)` program, and `pari.out_of_reach` never excludes a non-predicate
    form at any budget, so it was in the 60 s pool too and had simply never been drawn.

    **Predictions.** P1 (the 20 picks in order, pool 3,622), P2a, P2b, P3, P4, P5, P9, P10, P11 and P12
    held; **P6, P7 and P8 broke.** P6 broke in the best possible way. P7 gave 11 timeouts, not 12-16
    (times all within band). P8 broke on two picks — see the limitations below. The item-31
    10-known-term ceiling is **not** what session 7 broke: 2 of 15 many-term picks got through, but both
    verified in under 60 s, so it was sampling, not budget. Pooled it is 2 of 49 (P(0 of 31) = 0.13 over that population, 0.28 as independent trials),
    and the gradient survives intact: **>10 known terms 4.1%, <=10 known terms 47.4%.**

    **P4 held by both routes, not the one this session first claimed.** A229209 produced a 5-point
    trustworthy fit **at verification**, so the plan's "P4 is decided at verification" was never
    refuted. It was missed here because **`predictions.trustworthy` stores `Assessment.trusted`, not
    `Projection.trustworthy`** (`verify.Prediction.from_assessment`), and there is no `npoints`, `disagreement` or
    `rate_drift` column at all — so the database cannot answer the question the run existed to ask.

    **The targeted probe that ran first (attempts #133-135, 21 min)** broke its own prediction T1: none
    of A277041, A391937, A265938 verified at 600 s. Its finding is stronger than the prediction it broke
    — **ten times the budget bought exactly one term** on each of the two that reached the gate (13→14
    of 15, 26→27 of 33), on the three sequences closest to verification in the whole corpus. It also
    produced the **first `memory_cap` stop in the project's history**, with `extra.mem_cap_bytes` =
    6.00 GiB equal to the configured budget, proving the stop was the program's appetite and not a
    starved machine — item 34's field doing its job on its first real exercise. Because two of the three
    became `verify_timeout` dead ends at <= 600 s, the pool fell 3,624 → 3,622 and P1 was re-derived and
    re-written before the session started, exactly as the plan said it would have to be.

    **Two corrections to this session's own earlier claims**, both found by the audit: only
    `_save_pending` ran, not `_load_pending`, so item 34's reload path is **still unproven**; and
    `refresh_difficulty` was **not exercised at all**, since its only caller is `sync` and no sync ran.

    **A process note.** The independent re-derivation of a(43) caught **two bugs in its own verification
    code** before it agreed with the critic: a Fermat reduction applied at q = 5, where it is invalid
    (`10^e = 0 mod 5` for every `e >= 1`), which reported the impossible `a(43) = 5`; and a segmented
    sieve that advanced to an even lower bound after its first segment and emitted composites. The first
    was caught by noticing the answer was impossible, the second by an assertion added in response to the
    first. Neither touched project code, but they are the reason the re-check is worth its cost.

36. **The cost fit's own statistics, recorded in `predictions`** (the user, 2026-09-21: "Do #2 now").
    Next step 2. Five columns — `fit_trustworthy`, `fit_npoints`, `fit_disagreement`, `fit_climbing`,
    `rate_drift` — plus a backfill of the 40 existing rows by replaying their term logs. Five, not the
    four the list promised: the user chose to add `fit_climbing` as well, on the assistant's
    recommendation that it was not otherwise recoverable and would make the estimator's `risky` flag
    reconstructible. **The audit showed both halves of that recommendation were wrong.** `fit_climbing`
    is exactly `model = 'ratio'` — `estimate.project` selects that model for a climbing series and only
    for one — so it was already recoverable, and `risky` was already reconstructible without it. The
    column is kept as a direct, contemporaneous record, but it was mis-sold when the user chose it.

    **The premise was partly wrong, and the item corrected it.** "No query can answer 'has a trustworthy
    fit ever happened?'" was too strong: `Projection.disagreement` is arithmetically identical to the
    already-stored `predicted_s_high / predicted_s_low` (the seconds-per-unit rate cancels; checked on
    all 18 fitted rows, agreeing to 2.6e-16), so a ratio query would have found the right six rows. Only
    by luck, though — `Projection.trustworthy` also needs `npoints >= 4`, and no 3-point fit in this
    database happens to disagree by under 3x. The first correction of this was itself wrong in two
    places, caught by the audit: `fit_climbing` is recoverable (above), and `fit_trustworthy` follows
    from the ratio alone on every `poly` or `ratio` row, because both models require at least 4 points.
    **Genuinely unrecoverable: `rate_drift`, and `npoints` on the `exp` rows** — which is 16 of the 18.
    The full accounting is in
    [data and schema](data-and-schema.md#predictions-one-row-per-projected-term). The overstatement was
    in the plan, in `data-and-schema.md` and in `known-limitations.md`; all three were corrected rather
    than repeated. The critic found the first layer, the auditor the second.

    **The replay is evidence, not assertion.** `scripts/replay_predictions.py` rebuilds each stored
    prediction from `data/runs/*.jsonl` and re-derives seven values that *are* stored — `model`, the three
    predicted seconds, `predicted_mem`, `value_dependent` and `trustworthy` — plus `feasible` for the 23
    rows whose attempt recorded both budgets it depends on. **All 40 rows reproduce exactly**, including
    #37, the `infeasible` verdict on A385331's a(43). The five unstored values come out of the same
    `estimate.assess` call, so a clean comparison is the evidence the backfilled numbers are the run's
    own; `trustworthy` is in that list because it is the only stored column that constrains a replayed
    `rate_drift` at all. A row that cannot be replayed is reported and counted separately, and blocks
    `--write`: the first version of the script counted such rows as "reproduced" and still exited 0. `--write` fills only rows where all five columns are NULL, so it can never overwrite a
    contemporaneous value with a replayed one.

    **Result: 6 trustworthy cost fits in the whole history**, of 18 fitted projections in 40 rows.
    Five are attempt #139 (A385331, n=39..43). The sixth is **prediction #18, attempt #138, A229209
    n=12** — `npoints = 5`, `disagreement = 1.754`, `rate_drift = 7.794`, stored `trustworthy = 0`. It is
    the fit session 7's audit missed, and the only row in the database where a sound fit was withdrawn
    from the kill by the drift alone. The evidence base is thin and the page says so: 18 fitted rows from
    8 attempts, 11 of them from #139.

    **Process.** A critic reviewed the plan and returned 24 findings; every number it reported was
    re-derived independently before being acted on. Its blocker was one the plan had missed:
    `attempt._checked` requires the saved field set to match `verify.Prediction` exactly, so adding
    fields would make any `data/pending/*.json` unloadable **for ever** (`retry_pending_rechecks`
    swallows the error). `data/pending/` was empty and no attempt was `recheck_pending`, checked twice;
    `PENDING_FORMAT` went 1 -> 2 anyway. Eight mutations were run against the whole suite: **seven were
    caught, one was not** — `fit_disagreement` could be replaced by the constant 1.0 and the suite still
    passed, because the test's cost series was a perfect exponential whose disagreement *is* exactly 1.0.
    The test was fixed to pin the number on a series that disagrees. The database change followed the
    item-28 pattern: `VACUUM INTO` copy, rollback proven on it by injecting a failure three rows in (the
    `ALTER` vanished with the updates), `VACUUM INTO` backup at
    `data/oeisbot-before-fit-stats.sqlite3`, then one `BEGIN IMMEDIATE` transaction. A first dry run
    found an idempotence bug — the 22 rows with no fit are legitimately all-NULL, so the "only fill empty
    rows" guard rewrote them on every run and reported work it had not done. Expected results were
    written down before any code and the real run was compared against that file, not recomputed.

    **The audit ran twice, and the second round mattered as much as the first.** Round one returned 14
    findings, of which two were defects in the work and the rest were wrong or overstated claims in the
    prose. Round two, on the fixes, found that two of them were incomplete and that the fixes had
    introduced a fresh crop of stale counts: `replay_predictions.py` still swallowed a *truncated* log
    into a note about missing budgets, leaving the row counted as reproduced (the same defect class as
    the one round one had just fixed, in the same function); and the new `predictions.csv` test pinned
    the header and the row width but cross-checked only 6 of 18 values, so `fit_disagreement` and
    `fit_climbing` could swap places undetected — 5 of 6 value-permutation mutants passed. Both are
    fixed, all 6 permutations now fail, and the counts are recomputed from `--collect-only` rather than
    edited by hand. The lesson recorded for next time: **a fix that adds a test or changes a script's
    output silently invalidates the counts and descriptions elsewhere in the docs**, and that happened
    on both rounds.

    Round three found two more, both in the test round two had just strengthened: its expected mapping
    had three duplicated values, so `feasible`/`fit_trustworthy`, `trustworthy`/`fit_climbing` and
    `actual_mem`/`censored_s` could still trade places (a single row cannot separate four booleans --
    the fix is a second row with the opposite pattern), and switching to a dict comparison had dropped
    the ordered-header assertion, so a consistently reordered file passed. Six permutation mutants now
    fail where three did. It also showed the replay would accept a log belonging to a *different* run:
    the script now refuses a log whose name carries another program's sha, whose known-term count
    disagrees with the attempt, or that two attempts name at once -- the last being the only check that
    catches a re-run of the same program on the same sequence, and the only one that needs no reasoning
    about local time. Three rounds, and each found something real in the round before it.

    Not done, and noted rather than silently skipped: the **dashboard still shows only `trustworthy`**
    (the user's call), so its "trusted projections only" filter hides a fit withdrawn by the drift while
    SQL reads it as sound. `Projection.parity_split` and `Assessment.next_bits_high` stay unstored.

37. **Guards, so item 36's defects cannot come back quietly** (the user, 2026-09-21: "Update the test
    suite/documentation (if possible) to avoid defects in future runs"). Three of item 36's failures
    were the same shape: something true was written down, something changed, and nothing noticed. Each
    is now machine-checked.

    **`tests/test_docs.py` (3 tests)** compares the documented test total -- in all eight places -- the
    per-file table's function counts, and the collected-counts paragraph against what pytest collected
    *in that same run*, read from `request.session.items`. It cannot disagree with the suite it belongs
    to, and it skips rather than lying when only part of the suite was collected. Two details matter:
    `status.md`'s history section is excluded, because a number inside a history item is that session's
    own record and must never be updated; and a checked sentence being *reworded away* fails too, so the
    guard cannot go quietly dead. This is the failure that recurred three times in item 36, and once
    before it in item 34.

    **`tests/test_replay.py` (5 tests, 12 cases)** covers `scripts/replay_predictions.py`, which had no
    tests and produced more defects than anything else in the item. It drives the script against a
    synthetic database whose `predictions` predates the fit columns, and pins the bookkeeping rather
    than the arithmetic: eight distinct ways a row can fail to replay are each reported, counted apart
    from the rows that reproduced, and made to refuse the write; the write is idempotent; a
    disagreement blocks it; and a failure part way takes the `ALTER` with it. The fixture derives its
    expected values from `estimate.assess` directly, never from the script, since a fixture built with
    the code under test agrees with it whatever either one does.

    **Two tests in `test_db.py`** pin the whole `verify.Prediction`-to-column mapping, including the
    four fields deliberately *not* stored, and round-trip every stored field with a distinct value. A
    field added to the dataclass, or to `db.SCHEMA`, or to the INSERT but in the wrong position, now
    fails instead of writing silently wrong rows -- which is exactly how item 36 could have gone wrong.

    **`check_docs.py` checks its own expected-hits count**, so a new unexplained identifier, one that
    becomes real code, or the sentence being deleted is a problem with a non-zero exit.

    Every guard was verified by re-introducing the defect it exists for: the truncated-log note, rows
    counted as reproduced, the idempotence guard, a dropped INSERT column, an unmapped new field, four
    kinds of stale doc number, and three ways the expected-hits check can rot -- **each failed exactly
    the guard meant to catch it, and nothing else**. Two gaps in the guards themselves were found that
    way and fixed: the idempotence test had no row *without* a cost fit, which is the only kind the
    guard concerns, and a helper named `test_functions` was being collected as a test.

38. **Session 8: the `--verify-s 60` pass, and an audit that reversed two of three conclusions
    (2026-09-21).** The user: "start the --verify-s 60 session", after choosing `-n 20` and full
    pre-registration. Run as `run -n 20 --verify-s 60 --extend-s 1800 --seed 208`, no `--model`;
    database session 8, attempts #156-175, 21:37:48Z to 23:51:51Z. **20 picks, 20 program runs, 0 skips,
    8,038.6 s of machine time (2.23 h), 5 verified, 0 new terms.** Console in `data/session8_pari.log`;
    the pre-run database copy is `data/oeisbot-before-session8.sqlite3`. No code changed.

    **The measurement the run existed to make is confirmed: 8.96 picks/h against session 7's 4.78, a
    1.88x improvement.** Decomposed, **83% of the 7,034.9 s difference is the verify gate** (session 7's
    11 timeouts cost 6,603.1 s; session 8's 13 cost 784.1 s) and 17% is draw luck in which verified runs
    happened to be killed early. Next step 1 is therefore settled: **60 s is the gate to run.**

    **Pre-registered in `planS8.md` before the run**, with the picks computed read-only from the seed and
    a critic reviewing the page first. That critic found **six errors**, every one re-derived here from
    the raw data before being accepted (the rule from item 30). The two that mattered: the `<=10 known`
    base rate had to drop from 13/31 to **12/31**, because A019288 reached its last known term only at
    **t = 497.26 s** and verified solely thanks to session 7's 600 s gate — counting it would have been
    the same double standard this page criticises elsewhere; and the wall-clock model's claim to
    reproduce sessions 5 and 6 was false (**+125%** on session 5, not 0.3%), because a verified run does
    not always cost a full extension — `E[cost | verified] = 1,418 s`, not 1,810.

    **10 of 11 predictions held.** Exact hits: the 20 picks in order; the pool line byte-identical at
    173 characters; and P10's pool arithmetic, `queue` moving **3,479 -> 3,464** with dead ends
    **58 -> 73**. **P5 broke**: 2 of the 11 many-known-term picks verified against a pre-registered
    P(>=2) of 8.7%. First runs per distinct sequence now stand at **<=10 known 40.0% (16/40), >10 known
    7.3% (4/55)**. The first write-up called that "the count breaking, not the gradient"; the audit
    rejected the framing, and rightly — the **gradient ratio fell from 9.23x to 5.50x**, a 40% collapse
    in the statistic the prediction rests on, weakening at every threshold tested. Whether that is drift
    or sampling needs another session. (A270393, one of the two breakers, has 11 known terms but a(11)
    has **3 digits**: its term count carries none of the difficulty the heuristic assumes.)

    **A194099 is the session's real result, and not for the reason first written.** Attempt #175
    reproduced all **28 known terms in 8.075 s**, the estimator projected **a(29) at 22.3 s** with
    `trustworthy`, `fit_trustworthy` and `feasible` all 1 (`fit_npoints` 12, `fit_disagreement` 2.948,
    `rate_drift` 1.473), and `over_prediction` killed it at **44.78 s of extension**, leaving 1,755 s
    unused. The kill was right. But the first write-up presented an "independent derivation from the
    definition" that m must be odd and a(29) > 10^13 — and **both are published comments in the entry
    the pipeline parsed**, the second twenty-five orders of magnitude stronger:
    `%C A194099 No more terms <= 2 * 10^38. - Charles R Greathouse IV, Aug 22 2011`. The derivation is
    sound (it reproduces all 28 known terms; the audit confirmed the smoothness argument, the odd-m
    argument and the primorial bound `k <= 19`, and re-derived the result two further ways), but it
    restates a 2011 result more weakly. Against the entry's own bound the estimator's error is **~10^31**,
    not the "3.5 million" first claimed.

    **This produced the most valuable finding of the session, and it came from the audit, not the run:**
    **1,537 of the 3,450 candidates in the live pool — 44.6% — carry a comment asserting a searched
    bound** ("No more terms <= X", "a(n) > X, if it exists", "Next term > X"); over all 26,814
    candidates it is 4,561 (17.0%), of which 2,181 have a PARI program. **The pipeline reads none of
    them.** See next steps.

    **The offer B attribution was backwards and is corrected here.** The first write-up called the kill
    "a clear positive for offer B". It is not: `kill_after_s` returns `None` unless `trusted(factor)`
    (`estimate.py:88-95`), so offer B can only ever *suppress* a kill, never cause one, and this
    projection was trusted — **the pre-offer-B rule would have killed at the identical
    `max(10, 2 x 22.3086) = 44.62 s`**. It is evidence for the `over_prediction` rule, which predates
    offer B. The irony runs the other way: `fit_disagreement` 2.948 against a trust threshold of 3.0 is a
    **1.7% margin**, and a marginally worse fit would have made offer B suppress the kill and burn all
    1,800 s. "A rule that needs no fit to be right" was also false — the threshold *is*
    `2 x predicted_s_high`.

    What survives: this is the **first `over_prediction` kill since offer B** (the only others, #57 and
    #62, are both session 5 and predate it), so the first time the rule fired on a projection the
    estimator trusted, and the **first *optimistic* trusted projection**. Session 7's four wrong
    trustworthy projections were pessimistic, which can only stop a run early; an optimistic one is the
    dangerous direction, because `feasible = 1` is what keeps `infeasible` from firing. "Nothing in the
    estimator caught it" was overstated: `fit_climbing = 1` made the assessment `risky` and `rate_drift`
    recorded the rate climbing 47% — **the flags it raised are not wired to anything that stops a run.**

    **The extension argument was wrong and its own counter-example disproves it.** The first write-up
    noted that 22 full-extension runs have spent 27,195 s for 0 new terms and concluded the marginal
    value of late extension seconds is "unmeasured and assumed". A385331's term log says otherwise: all
    18 of its new terms arrived at **t = 454.18, 520.99, 578.68 and 731.71 s** of extension, the last
    five **0.07 s before** the `infeasible` kill. A 300 s or 400 s extension would have given this
    project zero wins. The 22-run figure also needed three qualifications the first draft omitted, one
    of which its own plan had forbidden: **22 runs are only 18 distinct sequences** (A247883 x3,
    A246855 x2, A057246 x2) — the plan devotes a paragraph to not counting repeats as independent
    observations — **only 14 had an 1,800 s extension** (four had 120 s, two 300 s), and **one is a
    `python:model` run**. What remains true: four full extensions took **7,201 s, 89.6% of this
    session's machine time**, for nothing.

    **"The 60 s gate cost nothing" was unsupported** and is corrected to what the data supports: it cost
    784.1 s, four timeouts died **one known term short** (A119739 6/7, A341812 2/3, A120094 12/13,
    A215195 3/4), and session 7's base rate suggests a 20-pick session loses about one verified run to
    the gate — which by the project's own rates would cost ~1,800 s and produce nothing. A good trade,
    not a free one.

    Full write-up in **`data/session8/resultsS8.md`**, with `planS8.md`, `planS8-v1-precritic.md` and
    the scripts (`prepicks.py`, `preevidence.py`, `baserates.py`, `firstattempt.py`, `intervals.py`,
    `checkcritic.py`, `postrun.py`, `a194099.py`, `a194099_term29.py`, `nomoreterms.py`). Unlike earlier
    sessions' working files these were copied out of the temp scratchpad, so they are still here.

39. **Next step 1 measured: the searched-bound comments (session 9, 2026-09-22).** No code changed; the
    whole item is evidence, in `data/session9/` (`resultsS9.md` first, then `planS9.md` and
    `planS9-v1-precritic.md`). Pre-registered, plan reviewed by a critic who found **nine** must-fix
    defects, write-up then audited by a second critic who corrected **four** things in it.

    **Session 8's 44.6% is real and reproduces exactly — and is the wrong quantity.**
    `PREDICATE_MAX_RATE` (2e7 calls/s) is an upper bound on speed; the measured verification-phase rate
    over 52 logged runs had median **1,576 calls/s, 12,687x slower** *as measured on 2026-09-22, over
    the 52 predicate logs that existed then, on the **raw** definition* (last cumulative work over
    last timestamp, which includes gp's startup and so understates the rate). **This ratio moves every
    session and must always be quoted with its date, population and definition** — session 10 took it
    to **15,244x (median 1,312, 83 logs)**, and the *startup-stripped* definition, which is what
    `verify.measured_rate` actually computes for the searched-bound check, gives **8,178x (median
    2,446, 82 logs)** against 4,482x before that session. The argument below is unaffected: every one
    of these medians is orders of magnitude below the constant. So a published `No more terms
    <= 10^8` above a last term of 10^6 is 5 s of work at the constant and ~17 h in reality: most bounds
    sit *inside* what a run scans, and ignoring them costs nothing. The chain: pool 3,450 → 1,537
    matched (44.55%) → 1,421 current and non-stale (41.19%) → **230-241 beyond a real run's reach** →
    **162-172 in the predicate form** (4.7-5.0%), the only form where this is deployable. The range is
    the estimator's, not hedging.

    **The critic's defect 1 redirected the session:** `pari.out_of_reach` can never consume a comment
    bound. It bounds the *verification* scan against `verify_wall_s` (`pari.py:359-372`,
    `attempt.py:377`), is monotone decreasing in the budget, and returns `None` on A194099 — the entry
    the item exists for. The check that fits is new and belongs at the **verify/extend boundary**, where
    the rate is measured rather than guessed:
    `X - last_known_value > measured_rate * extend_wall_s`.

    **Replayed over history** (`retro.py`), using each run's own measured rate and only what the pipeline
    knew at that moment: of 53 `pari:predicate` attempts, 16 reached extension, 15 were evaluable, 10
    would have been cut short — **11,277.5 s, 55.0% of all predicate extension time**, 5,756.3 s of it
    provable at any rate. 3,600.6 s rests on margins under 10x (A279795 at 1.11x), so the robust core is
    **7,676.9 s**; a 10x safety margin costs only 172 → 148 candidates.

    **Safety rests on a census, not on the retrospective.** All **241** beyond-reach candidates were read
    by hand: 240/241 genuine current bounds, **171/172 of the predicate-form ones correctly skippable**.
    The two wrong skips are both instructive — A274994 borrows *A001220's* 4.97e17 (its own bound is 2e6,
    inside reach), and A088783's 16,777,216 is a per-candidate *exponent* limit while the entry says its
    next term may be 185. The guard for borrowed bounds ("reject a bound whose sentence names another
    A-number") is not free: it also drops six sound bounds, four of them deployable.

    **Restricting to the predicate form is mechanical, not a judgement call.** Only there do term values
    equal the driver's work count (A038582's terms are `k`; A038583's are the sums — same search,
    opposite mapping), and `work` is hard-coded to 0 for both other drivers (`pari.py:395, 450`), so
    there is no rate to measure at all.

    **What the audit corrected in the write-up:** `rates.py`'s premise that a log's final `work` is the
    highest value a run reached is **false** (the driver emits only on a term found, and no predicate
    attempt has ever found one, so every log stops at the end of verification — attempt 56 ran 1,800 s
    with its last record at 0.025 s); the median was an off-by-one; the "zero wins cut short" row is
    **vacuous** because there are no positive instances at all; and the recall frame's regex was broken
    on its own stems (`searched`, `verified` never matched), making recall **≤85%, not 91%**. Five
    extractor bugs were found and fixed along the way — one of which *created* the A088783 false
    positive. Corrections are marked in `resultsS9.md`.

40. **The searched-bound check, built (2026-09-22).** The user: "build the post-verification check".
    Design in `data/session9/planBUILD.md`, reviewed by a critic who found **seven** must-fix defects
    before a line was written.

    **What it is.** `oeisbot/bounds.py` reads a published searched bound out of an entry's `%C` lines;
    `verify.Harness._bound_exhausted` stops the run with the new `Stop.SEARCHED_BOUND` when
    `X - last_known_value > 10 * measured_rate * extend_wall_s`. The rate comes from
    `verify.measured_rate`, work per second between the first and last term records — the first is
    dropped because it carries gp's start-up, and including it would *understate* the rate and make the
    skip fire more often, the unsafe direction. `config.SEARCHED_BOUND_MARGIN` is 10 and is deliberately
    not a `Budgets` field (that would invalidate every saved win in `data/pending/`).

    **Verified end to end on A194099**, attempt #176: `verified` / `searched_bound`, 28/28 reproduced,
    8.0 s. The same sequence took 52.9 s in session 8 — 8.1 s verifying and 44.8 s extending into a range
    the entry has said was empty since 2011. Recorded `measured_rate` 160,256/s over a 7.9 s window,
    `verified_scan_to` 1,267,111.

    **Not a dead end, by the user's own instruction** ("if there are more sequences just denote where the
    progress stopped so the next time it can be resumed"). The sequence stays in the pool, and the
    attempt records two different things, named apart on purpose: `verified_scan_to` is *ours* — the
    driver tested every k up to it and the harness watched every term arrive, so resuming past it would
    be sound — while `searched_bound` is the entry's **unverified human claim**. Resuming past *that*
    would make a later term's index depend on the claim, which is exactly what a bound must never be used
    for, so the resume machinery itself is not built. The cost of not retiring is real and measured: 8 of
    the 10 historical firings ended at `extend_budget`, which today retires them permanently at that
    budget.

    **Predicate form only, and mechanically so.** Only there do term values equal the driver's work count
    — A038582's terms are `k`, A038583's are the sums of the very same search — and `work` is hard-coded
    to 0 in both other drivers (`pari.py:395, 450`), so there is no rate to measure. `attempt` supplies a
    bound only for `pari:predicate`; the harness's `work > 0` test is the backstop.

    **What the critic caught, all fixed.** `Decimal ** int` rounds at 28 significant digits, so the
    prototype's "exact" parser turned 2^200 into a number ending in 92 zeros while 2^63 passed because it
    is only 19 digits — the exactness had been tested only in base 10. The stop's detail would have
    reached the model through `codegen.slow_program_note`, whose contract is "never a term value", and
    publishing the bound beside the rate and margin lets the held-out last known term be recovered by
    arithmetic; the detail now names only the bound and the budget, with the rate, window and quote in
    `extra`. `tests/test_codegen.py` enumerates `Stop` and would have failed on the new member. Two of
    the eight machine-checked test-total sites (`README.md`, `docs/operations.md`) were missing from the
    plan's docs list. And the plan's claim that not retiring was "strictly better than today" was false.

    **Two guards, both paid for.** A bound whose sentence names another A-number is rejected (A274994
    quotes *A001220's* 4.97e17 while its own is 2e6 — the one wrong skip in session 9's census), which
    also drops three sound bounds among the deployable set. A claim qualified to a subset of terms is
    rejected (A146566's `No other term multiple of 12 below 10^9`). The loose `searched to X` phrasing is
    not a pattern at all: it produced A088783's false positive and **no** deployable candidate needs it.
    Net effect on the pool: 172 deployable before, **179** after, with the known wrong skip gone.

    **The independent audit found six more things**, all fixed. A bare `>` also matched the one inside an
    arrow, so A337671's `a(17)? -> 2^9216 - ...` parsed as a 2,775-digit bound on a(17) — a real wrong-skip
    bug, latent only because that entry is not in the predicate pool. The justification written into the
    code for keeping the bound's quote out of `detail` was **false**: `codegen._context` already shows the
    model `entry.comments[:8]`, which covers 142 of the 146 entries the check can fire on; the narrower
    true reason (a later session replaying this row's `detail` with no comments beside it) is now what the
    comment says. And **four of the 22 tests were not testing what they claimed** — the bridge-guard test's
    fixture produced zero regex matches, so it passed with the guard deleted; `_borrowed` was untested on
    the indexed call site; `applicable`'s `max` was untested; and nothing tested the predicate-only gate at
    all. Mutation testing now confirms all four are caught.

    The audit also **hand-read all 146 entries the check currently fires on and found no false positive**,
    and measured the parser at 0.04 ms per predicate run with no catastrophic backtracking. Its remaining
    findings — a trailing qualifier slipping past, index bounds read as value bounds, a citation split
    across sentences, and several `parse_number` shapes that are silently wrong (all but one in the
    understating, safe direction) — are now in `docs/known-limitations.md#searched-bounds` rather than
    fixed, since none is live.

    340 tests pass (26 new in `tests/test_bounds.py`) and `check_docs.py` reports no link problems.
    `docs/known-limitations.md#searched-bounds` records what it still gets wrong, including measured
    recall of about 85%.

41. **Progress heartbeats: a predicate scan now records where it stopped (2026-09-23).** The user: "start
    on the post item 40 work", then, after the evidence below, "build the heartbeat half now". Three of
    item 40's four follow-ups were measured before anything was built, and **two of them died**:

    **`_bits_bound` was dropped, on three premise errors.** The pitch (item 39's audit note, repeated on
    this page) was that feeding a published bound to `estimate._bits_bound` would reach 1,421 entries
    against the skip's 179 and "feed the feasibility and `over_prediction` machinery". It feeds nothing.
    `next_bits_high` flows `estimate.assess` → `verify.Prediction` and stops: no column in `predictions`,
    no reader in the repo, and its only consumer `Assessment.exceeds_int64` is referenced solely by a
    test — which `docs/known-limitations.md` already said, so the page contradicted itself. Second, a
    searched bound is a **lower** bound on a(n) while `_bits_bound` returns a **high** estimate of the
    same term's bit length; only `max()` combines them. Third, the reach is real but inert: measured over
    the live pool, **1,443 of 3,450 (41.8%)** carry an applicable bound, **318** would have their number
    changed at all, **31** flip `exceeds_int64`, and **nothing reads it** — which cannot fire anyway, as
    both runtimes are arbitrary-precision (`design-spec.md`). The reach does not transfer either: value
    implies cost only for the predicate form, which `pari.py:363` states outright and item 40 covers.

    **The extractor's recall gaps are smaller than advertised.** The usable population is the 767
    predicate candidates with no applicable bound: 253 have no `%C` lines at all, 122 are stale and 8
    wrong-index (both *correct* rejections), leaving 384 where recall could matter. The documented gap
    shapes match about 18 of them, and most are index or exponent limits rather than value bounds
    (`Checked up to n = 1053627`, `Tested to 4500`) — the A088783 false-positive class session 9
    deliberately excluded. Estimated with fresh regexes, not session 9's labelled sample.

    **What the evidence said about resuming.** 54 `pari:predicate` attempts: 35 `verify_timeout`
    (9,310.2 s), 14 `extend_budget` (21,002.1 s), 1 `searched_bound` (8.0 s). The first headline here —
    30,312 s across 49 runs — **was wrong, and the critic caught it**: all 35 `verify_timeout` rows have
    `reproduced < known_terms`, so their frontier lies *below* the last known value and a rule that
    resumes above the known terms cannot use them. The recoverable figure is **21,002 s over 13
    sequences**, a 31% overstatement corrected before the user chose. Reconstructing each exhausted run's
    frontier from its term log and comparing with `bounds.applicable`: 3 have no published bound, 2
    already scanned past theirs, 9 fall short — but **5 of the 14 would now be stopped at the verify
    boundary by item 40** and never extend, leaving exactly the productive cases. A279795 is the concrete
    one: 2.9e6 to go at 1,455 calls/s ≈ 2,000 s, just over one extension.

    **The driver could not say where it stopped**, which is why this item exists at all: it printed only
    when the predicate was *true*, so a run killed mid-scan left no trace of its position. Heartbeats are
    a precondition, not an optimisation. Three forms were timed in the sandbox on the cheapest predicate
    there is: a per-iteration `tested % N == 0` costs **23.5%** (dead), the blocked loop **3.6-4.9%**, a
    hand-rolled `while` with `k++` **43.9%**. A finite loop bound alone costs **2.1%** against today's
    `+oo` loop, so that much is a floor no block size can remove; whether the remainder is per-iteration
    or per-block the sweep **cannot resolve**, since it sits inside a ±2% noise floor (the audit caught
    this stated as settled fact — see below). Block size is chosen for cadence because nothing measured
    argues otherwise. On a realistic `isprime` predicate the whole cost measured 2.9%.

    **What was built.** `pari.PREDICATE_DRIVER` scans in blocks sized by *time* (doubling under
    `HEARTBEAT_TARGET_MS`, halving when a block overruns it fourfold, so an expensive predicate cannot go
    hours between reports) and prints `@P k tested cpu_us` after each. `verify.Harness` accepts one only
    when the caller supplied `ScanTracking` (predicate form only), the line is short enough to parse
    safely in the reader thread, the position matches the work claimed for it (`k - start + 1 == tested`),
    the frontier moves strictly forward and is not behind a term already emitted, and the implied rate is
    below `PREDICATE_MAX_RATE`. A line that fails any of these is **dropped, never fatal** — a heartbeat
    can make no term — and counted, with the first bad line kept, so a driver mangling every line is a
    number rather than silence. `attempt.py` writes `scan_reached`, `heartbeats` and (only when something
    was dropped) `heartbeats_ignored` and `first_bad_heartbeat`.

    **Nothing consumes the frontier.** Resuming is deliberately not built: it needs its own correctness
    argument, and the critic's trace found the population is mostly retired already (11 of the 14 are
    dead ends at 1800 s — the critic said all 14, which is wrong because three rows recorded extension
    budgets below 1800 s). The frontier is **reported, not witnessed**: below `verified_scan_to`, above a
    published `searched_bound`, and the docs now rank all three.

    **What the critic caught.** 22 findings on a plan that covered heartbeats *and* resume. The decisive
    ones: `is_dead_end` has already retired most of the target population, so resume could never fire;
    the resumed run would halt with `bad_index` on its first term (`verify.py:275`) and be starved at the
    60 s verify budget; the "no downstream path needs changing" claim held only because `new_terms`
    returns `[]` when `verified` is False, so the one-line fix would silently publish a two-run win
    (**overstated — corrected by item 42**, which drove the real `Harness._result`: `verified` is
    `verified_at is not None and reproduced == known.count`, and `reproduced` stays 0 on a resumed run,
    so the win path needs *two* changes, the second a deliberate lie about what the run reproduced); a
    frontier column stored as TEXT would compare lexicographically in SQLite (`'9000000' > '10000000'`), losing
    precisely the progress the item exists to keep; and the adaptive block needed a shrink rule. The item
    was split at the critic's seam and only the first half built.

    **Mutation checks: 17, all caught** (`mutateHB.py` in this session's scratchpad), but only after the
    first run exposed **three real gaps in the new tests** — the over-long-line test was passing because
    the rate ceiling rejected the same line anyway rather than the length cap; the shrink test asserted
    `min < max`, which mere growth satisfies; and one intended mutation was a no-op (moving the print
    above the increment reports the same k by different arithmetic). All three fixed.

    **The independent audit found no must-fix in running code** and confirmed by search that nothing
    anywhere consumes the frontier. It found two documentation faults, and its re-check then caught the
    second fix landing in only one of the four places that asserted the claim — the same split-brain as
    the first fault, and in the same place: the module comment a reader of the code lands on. Both are
    now fixed everywhere: the *superseded*
    30,312 s headline was still in the `pari.py` module comment and on the verification page — the two
    places a reader of the code lands — and the throughput claim asserted more than the measurement
    supports. The measurement establishes a **~2.1% floor** (a finite loop bound alone, against the `+oo`
    loop it replaced) and cannot resolve the block-size effect above a ±2% noise floor; "the cost is not
    tunable" was too strong, and the 10^8 point (which came out *faster* than baseline) had been left out
    of the quoted range. The regime every run starts in, `HEARTBEAT_BLOCK0` = 10^4, is still unmeasured.

    **The sharpest finding is one to carry into the resume item**, re-derived here rather than taken on
    trust: the refusal set bounds a lying heartbeat against `PREDICATE_MAX_RATE`, a *universal* ceiling,
    not against the predicate's own speed. `@P 10000000 10000000 0` is accepted at t = 0, because 10^7 is
    not greater than 2e7 × the 0.5 s start-up grace — while A176090 really scans at 256 calls/s, so a
    consistently lying driver could run some 78,000x ahead of the truth. Nothing consumes the frontier, so
    nothing is exposed; anything that later resumes from it must validate against the run's own
    `measured_rate`. The audit also showed the two checks are complementary rather than redundant: the
    identity alone accepts `@P 10^300 10^300 0`, the ceiling alone accepts `@P 10^300 1 0`.

    Also recorded rather than fixed, all deliberately out of this item's scope: `oeisbot_blk /= 2` is
    integral only because the block is `10^4 * 2^j` and the guard keeps `j >= 1` — GP's `/` yields an exact
    fraction otherwise, which the harness would then drop as unparseable, so the failure mode is "no
    frontier" rather than a wrong one; the **gp version is recorded nowhere** and cannot be recovered for
    rows being written now (`program_sha` already pins the driver text, since it hashes `Program.executed`,
    so that half is covered for free); and the `k - start + 1 == tested` identity is now cheap to apply to
    `@T` lines too, where `work` feeds `measured_rate` and the estimator but is cross-checked by nothing
    until a block completes.

    **An unanticipated side effect, found by running the resuming checklist rather than by review:
    changing the driver invalidated every past predicate result.** `attempts.program_sha` is
    `sha256(Program.executed)[:16]` and `executed` contains the driver text, so all **49** distinct
    `(a_number, program_sha)` predicate rows are now orphaned — `db.is_dead_end` keys on that sha and can
    no longer match any of them. `oeisbot queue` went from **3,464 candidates (73 `all_programs_dead_ends`)
    to 3,497 (38)**: 35 sequences retired as dead ends are back in the pool, 2 of them re-classified as
    `verify_out_of_reach` and 33 runnable. Re-running them will mostly re-derive the same `verify_timeout`
    verdict, 4% slower, and they displace better picks while doing it — an estimated half-hour of machine
    time spread over the next sessions. The selection failure penalty is **not** affected: it is keyed on
    the A-number, not the sha (`select.py`), so those sequences are still damped.

    It is semantically right — the program that runs really is different — and it is the same property
    the audit counted as a *benefit* for the resume item, since a driver change invalidates a stale
    frontier automatically. It is also unpaid-for waste. **Left for the user** (see
    [open offers](#open-offers-and-next-steps)): accept it, or backfill the 49 rows' `program_sha` to the
    new value, which would be a live-database write asserting that the old verdicts apply to the new
    program — defensible for `verify_timeout`, whose scan range is unchanged, but it is an assertion.

    362 tests pass (20 new in `tests/test_heartbeat.py`, 2 in `tests/test_attempt.py`) and
    `check_docs.py` reports no link problems. **No live database rows were written** by this item: the
    measurements read the database read-only and the end-to-end checks drove the harness directly.

42. **Resuming a predicate scan: measured, planned, reviewed and NOT built (2026-09-23).** The user:
    "start on the resume item — evidence and a plan with a critic first". The answer is **don't build
    it**, chosen by the user after the evidence and a critic's 31 findings. No code changed; the
    database was read-only throughout. The plan and the five evidence scripts are in this session's
    scratchpad (temp: treat as evidence that may already be gone).

    **The prize is retrospective and unrealisable today.** **Zero attempt rows carry
    `extra.scan_reached`** — item 41 wrote none — so a resume feature would be inert on the first day
    and stay inert until exhausted predicate runs accumulate, at a measured **1.5 per session** (12 over
    8 sessions; the other 2 of the 14 were manual runs with no `session_id`). And **0 of the 13
    sequences** has a recorded `program_sha` today's driver still reproduces, so nothing historical
    could be matched either.

    **Resume saves no machine time.** Reaching frontier F costs `(F − search_start) / R` seconds of
    scanning whoever does it: today every run restarts at `search_start` and re-covers the same range,
    so the frontier is hard-capped at one extension for ever; resume covers `[F(n−1), F(n−1)+R·T]`; a
    larger `--extend-s` covers `[last_known, last_known+R·B]`. **Total scan seconds are identical in all
    three.** Resume buys granularity and durability, not time — and on a find it costs **2×**, because a
    resumed run may never win and the cold confirming run must re-cover `[search_start, F]` in a single
    run, which is the very long run resume exists to avoid.

    **Nothing blocks the alternative.** `db.is_dead_end`'s `extend_budget` clause needs the earlier run's
    `extra.extend_wall_s >=` the planned one, so any larger budget re-opens a retired program — and since
    item 41 changed every predicate sha, all 14 are already un-retired at **every** budget. A targeted
    `oeisbot attempt A… --extend-s` is the whole of the alternative. **A279795 needs ~1,900 s and
    A015766 ~9,817 s** to pass their published bounds, `_bound_exhausted` fires for neither at
    1800/5400/10800 s, and all 14 runs' predictions are `trustworthy = 0`, so `over_prediction` cannot
    cut a longer extension short. Note `--extend-s` applies to *every* attempt in a session, so only the
    targeted single-sequence form is cheap.

    **What the critic caught: 31 findings (8 must-fix), including three errors of mine.** Six were
    re-derived here independently before being accepted. The decisive structural ones:
    `verify.Harness._bound_exhausted` is reachable **only** from the `n == known.last_index` branch,
    which a resumed run never reaches, so a resumed run would scan **straight past a published bound**,
    breaking [invariant 10](development.md#invariants); bypassing the `extend_budget` dead end leaves
    resume with **no termination rule at all** (a resumed run's sha differs on every resume because
    `start` differs, and it records `verified = 0`, so `is_dead_end` can never see the chain);
    `select.candidates` counts `outcome IN ('failed','verified')` and multiplies difficulty by
    `2^failures`, so **every resume halves the sequence's pick weight**, damping geometrically the one
    benefit resume has; and the durability claim is mostly false, since the checkpoint would be written
    only after `run_attempt` returns, so an interrupted *session* loses the frontier entirely — and
    **0 of 54** predicate runs has ever ended in the harness/sandbox kill that durability would cover.

    **My three errors**, all corrected above: I wrote that the win path is guarded only by `new_terms`
    returning `[]` when `verified` is False, so "the one-line fix" of setting `verified_at` would publish
    a two-run win — **false**, and item 41 records the same wrong claim (now corrected in place). Driving
    the real `Harness._result`: `verified` is `verified_at is not None and reproduced == known.count`,
    `reproduced` stays 0 on a resumed run, and the win path needs a *second* change faking `reproduced`.
    Second, my `is_dead_end` budget table was computed against the **recorded** shas while production
    `pari_plan` uses today's, making it a counterfactual (the conclusion survives, and is stronger).
    Third, "the 17 recorded predicate shas" conflated rows with shas: there are **49** distinct predicate
    shas, and 17 is the count of predicate rows that *verified*, carrying 14 distinct shas.

    **Numbers corrected in this page.** Item 40 stops **5** of the 14 at a uniform 1800 s (as recorded)
    but **6** at each run's own recorded budget; **8** distinct sequences still extend, not the 9 this
    page and `planRESUME.md` said — that 9 counts *runs* (A057246 appears twice). A279795 scans at
    **1,528** calls/s by `verify.measured_rate`, not the 1,455 recorded. And `measured_rate`'s window for
    this population is **under 0.4 s in 9 of 14 cases and under 10 ms in three**, so both budget figures
    above rest on sub-second measurements.

    **Left on the table, deliberately:** the critic's best idea, which is to spend the frontier as a
    **rate estimate** rather than as a resume point — `scan_reached / wall_s` over a full run is far
    better than `measured_rate`'s sub-second window, and feeding it to `_bound_exhausted` needs no new
    invariant, no evidence chain, no schema and no dead-end bypass. The user declined it for now; it
    cannot be tested against real data until a frontier is actually recorded.

43. **The runtime versions are recorded (2026-09-23).** Closes open offer (b), which had been waiting
    since item 41. The user: "Yes, one meta row", and then "Yes, short token in the note" when the
    critic showed a `meta` row alone would not do the job.

    **What it does.** `setup_tools.runtime_versions()` probes the two runtimes the sandbox actually runs
    and writes `gp_version` and `sandbox_python_version` to `meta`, from `oeisbot setup` and again at
    every `oeisbot run` (so an upgrade between the two is still caught). Each session's `note` gains a
    short `gp=2.17.4/GMP-6.1.2` token. `attempts.program_sha` already pinned the *program* text; this
    pins the *runtime*, which nothing recorded before.

    **Why both places.** `meta` is overwritten the next time gp changes, so on its own it would describe
    **no historical row at all** after the first upgrade — the very weakness offer (b) named. `note` is
    written once at `db.start_session` and never touched again. It is a *short token* because the
    dashboard renders `note` verbatim as the Settings column (`dashboard/src/views.tsx`), which a
    230-character banner would wreck.

    **Three things the evidence changed.** `gp --version` writes to **stderr**, not stdout — a probe
    reading stdout records an empty string and nothing says so. The banner is **five** lines, not the two
    the plan assumed, and the plan would have dropped the `compiled:` line, which is the only thing that
    tells two builds of one version on one GMP apart; it now keeps every line, so a reordered banner
    cannot silently cost the wrong half. And the dangerous failure is not a probe that fails — that is
    discarded — but one that **exits 0 with the wrong text**, so the value is recorded only if it says
    `GP/PARI` (`Python ` for the other), else `unknown`.

    **The critic's 14 findings**, of which the sharpest: "43 of 176" mixed two populations (it is **44 of
    176**, or 43 of 173); the never-raise rationale cited invariant 7, which is about not losing a win and
    would mislead a later reader — the real reason is that `run_session` builds its note *before* its own
    try/finally, so a raise there kills `oeisbot run` having done nothing; the named catch list missed
    `PermissionError` and `UnicodeDecodeError`, so it is `except Exception`; pass `-f` (mirroring
    `Harness.argv`) because `--version` ignoring a broken gprc is a property of *this* gp build, verified
    for 2.17.4 and guaranteed by nothing after an upgrade; pin the decoding (`subprocess` defaults to the
    ANSI codepage on Windows) and close stdin, since gp is a REPL. It also confirmed the item does **not**
    touch invariant 2: `--version` passes no file and evaluates nothing, and `install_python` already
    runs `uv`/`pip` unsandboxed.

    **Mutation checks: 24, of which 23 caught** (`mutate43.py`). The first run reported 17 of 17 and was
    **wrong**, which the independent audit caught: `tests/test_runtimes.py`'s banner fixture was written
    with a literal backslash-n, so it was a **single line**, every "collapsed to one line" assertion held
    before the code ran, and a driver keeping only the first three banner lines passed the entire suite.
    The one `[:2]` mutation that did fail failed by accident, through an unrelated test whose extra
    warning line shifted the GMP line out of the window. The fixture now uses real newlines and asserts
    its own shape, and `[:1]`..`[:4]` are all mutations in their own right. Two other real gaps came out
    of mutation: `setup()` had no test at all, and `meta` had no direct test either, though `sync` has
    written to it since session 1.

    The **one uncaught mutation is recorded rather than papered over**: swapping `db.set_meta_many` for a
    loop of `db.set_meta` calls is invisible from outside, because the end state is identical and only a
    crash between the two writes tells them apart. `tests/test_db.py` pins `set_meta_many`'s atomicity
    directly instead; asserting which function a caller chose would be testing the implementation.

    **What the independent audit found: 11 findings, 2 must-fix.** Besides the fixture above and the
    line-ending count (below), three real defects in shipped code: the `GP/PARI` guard was checked
    against the **uncapped** text while the **capped** text was stored, so a wrapper with a preamble past
    300 characters passed the guard and wrote its own output in as `gp_version` while the session note
    said `gp=unknown` — the two records disagreeing about one run; the cap could cut a version number in
    half, so `Version 2.17.4` straddling the limit would write `gp=2.17` into a note that is never
    rewritten (it now cuts at a word boundary, making it an honest `unknown`); and `setup()` wrote the
    two keys in **two** transactions, against this project's one-checked-transaction rule, so a crash
    between them could leave a fresh gp version beside a stale Python one (hence `db.set_meta_many`).
    It also corrected a false rationale in a code comment — the lazy `setup_tools` import was claimed to
    keep `urllib`/`zipfile` out of the session path, and `ingest.bfile` already imports `urllib.request`
    at module level — and noted that nothing pinned the *ordering* the never-raise contract rests on,
    since both new session tests check post-conditions only and pass with the block moved inside the
    `try`. There is a test for the ordering now.

    **The audit agreed the item does not breach invariant 2**, but flagged a status-quo change worth
    recording: before this item `config.GP` was only ever executed through `sandbox.run`, and it now runs
    host-side at every `oeisbot setup` and `oeisbot run`. See
    [sandbox](sandbox.md#gp-outside-the-sandbox).

    **A documentation error of my own, caught by the byte count.** While correcting this page's "attempt.py
    is LF" note I first "corrected" it to *every* file being CRLF — measured with `grep -c $'\r$'`, which
    in this machine's Git Bash reports **every line of every file** as CRLF. The truth, byte-counted: of
    50 `.py` files, **19 are CRLF, 25 are LF, 6 empty**, none mixed within itself; `attempt.py` is CRLF
    and `setup_tools.py`, `select.py` and most of `tests/` are LF. Section 6 above now carries the audit
    and the warning not to measure this with `grep`. The original note was wrong about exactly one file,
    `attempt.py` — which history item 34 had already found, and whose correction never reached the two
    places that actually instruct a reader. (The first *corrected* figure was wrong too, as 20/24/6 —
    caught by the audit, and by the re-check's independent third count. Why it was wrong is not
    recoverable: this item's own new test file changed convention during the work and is untracked, so
    there is no history to check, and the file's mtime is *earlier* than the page's. The checkable lesson
    is the one to keep: **the figure was written from a measurement that was not re-run** after the files
    it counted had changed again.)

    390 tests pass (24 in the new `tests/test_runtimes.py`, 3 in `tests/test_attempt.py`, 1 in
    `tests/test_db.py`) and `check_docs.py` reports no link problems. **No live database rows were
    written** by this item: every test uses a temporary database, and the measurements read the live one
    read-only. The next `oeisbot setup` or `oeisbot run` will write the two `meta` rows for the first
    time.

44. **Review #1 (A385331): steps 2-7 done, step 6 discharged (2026-09-23).** The user: "Tackle A385331's
    review now". **Nothing was submitted and the review row was untouched** — steps 8 and 9 are the
    user's, and the pipeline must never submit. Evidence and the full account: `data/review1/`.

    **Step 6 was the open one**, and `docs/operations.md` said so in terms: `scripts/verify_A385331.py`
    re-derives the sequence from its *name* rather than from the entry's program, but by the **same
    method** — trial division with the exponent reduced by Fermat, `sum_k 10^((n!-k!) mod (q-1)) mod q`
    — so a fault in that arithmetic path would show up identically in it and in `program.gp`. The new
    `data/review1/indep_A385331.py` never forms `n!-k!` and never reduces modulo `q-1`: it uses modular
    **inverses**, `10^(n!-k!) = 10^(n!) * inv(10^(k!))` with `10^(k!)` built by iterated small-exponent
    powering (`R_k = R_{k-1}^k`), and `gmpy2.invert` is extended Euclid, so Fermat is used nowhere in the
    file. Different bignum library (gmpy2), different prime source (sympy). It **reproduced all 23 known
    terms a(2)..a(24) first** — validating the method against OEIS ground truth before trusting it on
    anything new — then **confirmed all 18 new terms**: 11,078,935 odd primes swept to 2x10^8 in 775 s,
    41 agree, 0 disagree, 0 unsettled. It also re-derives **a(43) > 2x10^8**, a third independent
    confirmation that session 7's `infeasible` stop was right.

    **Two checks beside it, both stronger than a re-implementation.** The definition resolves: `N(n) =
    sum_{k=1..n} 10^(n!-k!)` **is** A145571 ("Numerators of partial sums for Liouville's constant"),
    checked against the live entry for all 5 of its published terms — so the name of A385331 resolves to
    what the program computes. And for n = 2..10 the **real integer** `N(n)` was built and its smallest
    prime factor found by plain trial division, with no modular arithmetic anywhere, agreeing with the
    b-file every time — up to n = 10, whose `N` has **3,628,800 digits**. Past about n = 11 the integer
    has tens of millions of digits, so modular arithmetic is unavoidable and the inverse method is what
    carries the rest.

    **The other steps.** The program is one line and its correctness rests on two facts, both checked
    rather than assumed: the `k = n` term is `10^0 = 1` and every other is a positive power of 10, so
    `N(n) == 1 (mod 10)` and `forprime(p=3, oo, ...)` is right to skip 2 and 5; and `N(n)` is a sum of n
    *distinct* powers of 10, so its digit sum is exactly n, which **proves** the entry's `a(3k) = 3` and
    also forces `a(n) != 3` whenever `3` does not divide `n` — both hold across all 42 terms. Offset 1,
    first new index 25, b-file contiguous. `timing.csv` looks alarming and is not: cost tracks the *size
    of a(n)*, not n, and the four slow terms (454 s, 66.8 s, 57.7 s, 153 s) are exactly the four with
    7-9 digit factors, with primes-below-a(n) x n landing within a small factor of each observed time.
    Step 7 re-run live the same day through `ingest.bfile`: the entry still ends at a(24), keyword
    `more` is still there, all 24 known terms still agree and none of the new terms is published.

    **One dead end worth recording:** the first direct-factorisation attempt called `sympy.factorint` on
    `N(n)`, which tries for a *full* factorisation and is hopeless on a 40,320-digit number — it hung
    and was killed. Only the **smallest** factor is wanted, so plain trial division is both the right
    tool and far faster.

45. **Session 10: 50 picks over two runs, and a new false-win class (2026-09-24/25).** The user:
    "Tackle #1 I have time for a longer run", then chose 50 picks as two back-to-back sessions and
    `--extend-s 1800`. Database sessions **9** (seed 209) and **10** (seed 210), attempt rows 177-228.
    Pre-registered in `data/session10/planS10.md` and `planS10-runB.md`; results and the full
    scorecard in `data/session10/resultsS10.md`. **50 picks, 52 program runs, 9,562 s (2.66 h),
    10 verified, and zero genuine new terms.**

    **The headline is a failure class, not a pick.** Two run-A picks — **A162762** (#186) and
    **A162764** (#191) — each produced 200 values in 0.1 s, passed their oeis.org re-check, and opened
    `reviews` rows **#2 and #3**. Both programs compute *proved upper bounds* that their authors state
    are only **conjectured to be exact**, in a comment carried verbatim into `program.gp`. **Neither is
    submittable.** The right argument is not that such a program matches the known terms "by
    construction" — these are algorithm-derived, not fitted — but that *conditional on a conjecture
    being published in OEIS*, agreement with the known terms carries almost no information, so the
    pipeline's whole gate learns nothing. `max_new_terms = 200` is the only thing that stopped either.

    **Closing those two reviews is not free, and this is the trap.** `rejected` is not in
    `db.OPEN_REVIEW_STATUSES`, `db.is_dead_end` returns None for both rows (`max_new_terms` is not a
    deterministic failure and `new_terms != 0`), and `select.candidates`' failure penalty counts only
    `failed`/`verified` outcomes while these are `extended`. So closing them **returns both sequences
    to the pool at 2.29x and 1.55x the mean pick weight**, where the next draw writes the same 200
    values, a new artifact and a new review row. Decide what to do about that before closing them.

    **Class size, measured (`data/session10/conjecture.py`):** 4 of 3,448 pool programs use conjecture
    language, but only **two** are this failure mode — A162763 (the third sibling, still live, same
    author) and, differently, A349899 (explicitly heuristic). A213062 is a false positive (a usage
    note). An independent `%C`/`%F` scan found **no** additional same-shape members, so the class is
    genuinely rare; but the word list misses scope caveats (`For k<6.`) in at least six more programs,
    so "programs warning against extrapolation" is ~0.26%, not 0.1%. Sibling **A162761 is proved** and
    would extend genuinely: of four siblings exactly one is proved, and the pipeline cannot tell them
    apart.

    **Amended 2026-09-26 (item 47): the last clause is no longer true, and the class size here is
    stale.** The pipeline *can* tell the siblings apart — A162761's `%o` carries no disclaimer while the
    other three say `conjectured`, so a check on the program text keeps A162761 and refuses the rest.
    The scan above also ran before item 46 changed the builder (pool 3,448, and it stopped at the first
    matching candidate per sequence, which under-counted every superset pattern). Re-measured against
    the current code: **7 parts of 5,315 match, 3 of them in the 3,441 pool.** The paragraph is kept as
    written because it is session 10's own record of what was believed then; item 47 has the corrected
    figures and the measurement behind them.

    **Both features built since session 8 worked.** The searched-bound check fired **3** times
    (A137056, A270538, A136009), saving ~5,400 s of extension — a counterfactual checked by feeding
    each run's records to the production `estimate.assess`, which returns `feasible=True` and no
    `kill_after_s` for all three, so each really would have run the full 1,800 s. The scan heartbeats
    ran **for the first time ever** (0 of the previous 176 rows had one): 6 rows carry a frontier,
    and `heartbeats_ignored` is absent on all 52.

    **What the audit reversed.** A fresh critic found 17 defects in the first write-up and all 17 held
    on re-derivation. The three that matter: (1) **the picks/h story was wrong** — 18.82 vs session 8's
    8.96 is not like-for-like, because *both* sessions paid exactly four full extensions; what changed
    is `E[cost | verified]`, 1,451 s → 721 s, and giving the five near-zero verifications full
    extensions gives 9.70 picks/h. (2) **The plan's "flat-cost predicate" call was not vindicated**:
    its trio went 3/3 (n=3), but the run total of 7 only reaches the predicted number by counting the
    two conjectural instant-verifiers — without them it is 5, the pooled prediction it was arguing
    against — while the other eight `<=10 known` picks went 1 of 8 against an expected 3.0. Two errors
    cancelled. (3) **The rate-floor proof's "cannot fire" half was never tested**: all four picks it
    excluded ended `verify_timeout` and never reached the check, so the falsifier could not have
    triggered. The genuinely discriminating case is **A033852** (#209), whose gap sits *above* its rate
    floor so the measured rate decides it — 346,740 calls/s put the threshold at 6.24e9 against a 1e8
    gap, and it correctly did not fire, against A136009 which did. That two-sided test was missing
    from the first draft entirely.

    **Three defects this session exposed, two of them undocumented** — see next steps.

46. **Bundle A: three confirmed defects, fixed without a run (2026-09-25).** The user: "What are the next
    steps for building out functionality? I want to avoid running until everything is built out", then
    chose this bundle over the conjectural-program check, the estimator items and Wolfram Engine, and
    accepted the pool shrink. **No pipeline run, no database write, no new attempt row.**

    **The evidence changed the size of the item.** `docs/status.md` next-step (iii) described two
    anecdotes (A330204, A366832). Scanned over the live pool through the production functions, it is
    **32 blocks that discard a usable print loop — 18 of them, hand-checked, the drivers cannot
    reproduce — and 24 whose chosen def needs a second argument: 39 distinct sequences, 1.13% of the
    pool**, each of which could only ever waste a pick. And the decisive fact was not in any note: **gp does not refuse
    a call that omits an argument, it binds the parameter to 0 and runs on** (`f(a,b)=a+b; f(1)` prints
    1 on this machine's gp 2.17.4), so A366832's recorded `incomplete` is just `digits(k, 0)`.

    **What shipped.** (A1) `verify.MAX_TERM_FIELD_DIGITS` caps a `@T` line's counting fields at 40
    digits *before* `int()`, closing an `OverflowError` that would have killed the sandbox's stdout
    reader thread — a real, reachable path, since `py_runner` hands the candidate module the same stdout
    and `verify.py` lifts Python's digit limit at import. Four unguarded sites, not the two first found.
    (A2a) a `%o` part now offers **both** its function form and its own print loop, function form first.
    (A2b) `pari._drivable` refuses a def the drivers would call with a missing argument.

    **The critic reversed the central design decision, and was right.** The plan proposed a static check
    that would prefer the loop when the driver provably could not reproduce it. The critic measured that
    predicate against the 32 blocks it was designed on and found it **wrong on 5, in both directions** —
    A256652 and A283364 were false positives (a `&&` application and an `==1` on a 0/1 predicate), and
    A254042, A254716 and A254717 were false negatives that **neither form can verify**, because their
    `first_index` is 0 while their own loops start at n=1 and `_EMIT` labels the first value with
    `first_index` regardless. All five were re-derived from the entries before the reversal. The shipped
    change therefore contains **no reproducibility predicate at all**: both candidates are offered and
    the gate decides.

    **Measured effect, by emulating the old builder on top of the new code rather than reasoning:**
    pool **3,448 → 3,434** (`oeisbot queue`: 3,455 → 3,441). Exactly the predicted **20 leave**, no
    others. **Six enter** — and the one that matters is **A330204, back on a print-loop candidate while
    its predicate form keeps attempt #227's `wrong_term` dead-end record**: the sequence is un-retired
    without erasing the verdict on the bad program, which is the property the critic argued for.
    A366832 returns the same way. **One orphaned attempt row**, against item 41's 49.

    **The audit found two defects in shipped code.** `_drivable` implemented a *count* of parameters
    lacking defaults, which accepts `f(a=1, b)` — still broken, because gp fills omitted arguments from
    the left (`f(a=1,b)=[a,b]; f(7)` gives `[7, 0]`, verified). Zero occurrences in the corpus today, so
    it was a guard against a `sync`, not a live bug, and it is now `all(defaults[1:])`. And the comment
    on `MAX_TERM_FIELD_DIGITS` **claimed to close the quadratic-`int()` stall and does not**: the value
    field is exempt by design and `MAX_LINE` is 1 MiB, so 10^6 digits still costs 3.7 s to parse and
    13.1 s to render — measured independently, matching the audit. Both are in
    [known limitations](known-limitations.md#term-lines-from-an-untrusted-program), with the second
    limitation this item introduced: an over-long index now reaches `protocol`, whose raw-line detail
    `describe_failure` does not scrub, exposing **149 of 26,736 model-eligible sequences (0.56%)**. That
    figure is over the *model-eligible* pool; the audit's own was over the PARI pool and much smaller —
    the population trap this page warns about, caught in both directions in one item.

    398 tests (390 + 8), **13 mutations, 13 caught** after one miss was closed, both source files
    restored byte for byte with sha256. The mutation harness's own docstring claimed it ran the whole
    suite while passing `-k`; the audit caught that too, and it now does.

47. **A program its author calls conjectural is refused (2026-09-26).** The user: "Yes plan (ii) —
    sections, critic on the plan, independent audit", after choosing this item from the next-steps list.
    All eight sections. **No pipeline run and no database write.** 412 tests (398 + 14), **15 mutations,
    15 caught**, both source files restored byte for byte with sha256.

    **What shipped.** `pari.conjectural(text)` matches `conjectur*|heuristic*|unproved|unproven|not
    proved`, case-insensitively, **only where `code_mask` says the character is not code** — the signal
    is the author's prose, and a GP identifier named `heuristic` would be a false positive a future
    `sync` could introduce. `build_candidates` checks the **raw `%o` part text** before building
    anything and refuses **every** form the part could yield, because a disclaimer is about the
    arithmetic and all three drivers share it. `codegen._context` also drops a flagged PARI block from
    its "Existing programs (correct, possibly slow)" list.

    **Why the gate cannot do this job, which is the whole argument.** Conditional on a conjecture
    published in OEIS, the closed form reproduces every known term *by construction*, so agreement
    carries almost no information and verification — the basis on which this project believes any term —
    learns nothing. `max_new_terms = 200` was all that stopped either of session 10's runs. This is
    **not** the mistake item 46 threw away (`data/item46/classify_m1.py`, wrong on 5 of 32 blocks): that
    check *inferred* a semantic fact the text never stated, while this one reads an explicit human
    declaration. Invariant 10's frame applies — an unverified human claim may stop us spending time and
    may never be evidence about a term's value, and this only ever stops a run.

    **Effect.** Pool 3,441 → 3,438, losing A162763, A349899 and A351088; A107263 and A393125 match but
    are **inert** (they already yielded no candidate). The point is not the three: **A162762 and A162764
    now stay out once reviews #2 and #3 are closed**, instead of returning at 2.32x and 1.56x mean pick
    weight to repeat the whole thing, which is what next-step (i) was blocked on. **A162761, the one
    proved sibling, keeps its candidate** — so the pipeline can tell them apart, which item 45 said it
    could not (that paragraph is amended above rather than rewritten).

    **The measurement corrected the item's own premise twice.** Session 10's "precision is the problem,
    not recall" is wrong at this width: **7 of 7 corpus hits are true positives**, and A213062's "upper
    bound" false positive exists only in the wider list, which was measured (20 hits, dominated by
    parameters literally named "upper bound" and by the "assuming the vector A002975 holds enough
    terms" shape) and rejected. And the "six other programs with scope caveats" are **not one class**:
    of 12 found in the pool, ~2 are genuine domain caveats, ~7 are performance caveats the gate already
    handles correctly (a slow program times out; it cannot emit a wrong term), 1 is external data and 1
    was a false positive of my own scan. Counting performance caveats as misses overstates the gap, and
    an earlier draft of the write-up did exactly that.

    **My own errors, for the record.** The first evidence scan attributed each part to only its *first*
    matching pattern, so every superset under-counted — it reported 6 for `conjectur` and 0 for a
    pattern containing it. And it wrote `c_evidence.json` into the repo working tree, where
    `.gitignore` does not cover it, leaving 9 untracked files beside the 8 the user is about to commit;
    the critic caught that as its first finding.

    **The critic's 19 findings on the plan** (5 must-fix, 7 should-fix, 7 notes), all accepted, six
    re-derived rather than transcribed. The three that changed the design or the claim:
    - **It overruled the plan's central choice about *where* to look.** The draft matched raw text
      anywhere and argued a comments-only check needed new machinery; both grounds were false — it is
      two lines using the `code_mask` idiom already at `pari.py:321`, and 0 of 20 corpus matches sit
      inside a string literal. Taken, and the test inverted.
    - **The headline value claim was false under `--model`.** `Runnable._why_not` returns `None` for any
      PARI-bearing sequence with at least `CODEGEN_MIN_KNOWN_TERMS` terms whatever the PARI verdict, so
      the check removes nothing from a model session's pool. The user chose to also withhold a flagged
      program from `_context`, which stops the model being told a conjectural program is "correct" but
      does **not** restore the pool block. The claim now carries that condition everywhere.
    - **Three of the eight planned mutations could not bite**, and saying they were caught would have
      been the same defect item 43's audit found once already. `drop re.I` is impossible to fail (all 7
      real hits are lowercase, verified case-sensitively across 5,781 parts) and was dropped; the
      `code`→`script` mutation raised an unbound-name error and failed the whole suite; "move after
      `builds`" is
      behaviourally identical. Replaced by a two-part mutation, a `block_rejects` mutation, and nothing.
    - It also corrected the plan's pick weights (2.32x/1.56x, not 2.29x/1.55x — the older figures were
      right against session 10's 3,448 pool), found A376243 misclassified (a genuine class member the
      narrow pattern misses), showed `undefined_a_numbers` does **not** cover the "assuming …" shape the
      plan credited it with, and insisted item 45's paragraph be amended rather than overwritten.

    **The mutation run found two real test gaps**, both mine: a mutation that only *added* a script
    check left the real one firing and was reported missed for the wrong reason (the harness now
    supports multi-site mutations), and the `codegen` test's Magma fixture carried no flagged word, so
    widening the filter to every language changed nothing. Both fixed.

    **The section-7 re-check then found the same class of defect a third time, in the fix.** The
    two-site mutation *was* caught, but its moved check recorded no `Rejected`, so tests 1, 3, 4, 5 and 9
    also failed on `len(rej) == 1`; `-x` stopped at test 1, 36 lines above the test 6 the mutation
    claimed to pin. The harness now carries an isolation list: for such a mutation it runs the suite
    **without `-x`** and requires the failing set to be **exactly** the named test. That is the general
    lesson — item 46's note warns against `-k` *instead of* the whole suite, and the answer is both, not
    neither, because an `expect` column nothing checks is a comment. With the fix, only
    `test_a_disclaimer_on_the_entrys_own_loop_rejects_the_part` fails. **15 of 15.**

    It also found **two tests the plan promised and I did not write** — the skip `detail` carrying the
    reason end to end (`Rejected.reason` → `nothing_to_run()` → `db.record_skip`), and the `_context`
    filter's per-block granularity — and **one limitation this item created**, below. 412 tests.

    **The independent auditor (a fresh agent, on the shipped code) found no must-fix and three
    should-fix, all taken.** It reproduced the pool figures, the corpus scan and the live effect
    independently, and confirmed the bookkeeping the `continue` skips is sound in six shapes.
    - **The `\w*` tails let digits out of a comment into `Rejected.reason`**, so the code comment's
      claim that naming the word made a value leak "structurally impossible" was simply false:
      `\\ conjectured86` reported `conjectured86`, and 86 is a real known term of A162762. Now
      `[a-z]*` — verified over all 5,781 parts as **identical verdicts, the same 7 flagged**, since
      `re.I` already covers case. A mutation and three digit-glued fixtures now hold the bound.
    - **`oeisbot stats --forms` filed the refusals under "no usable function (unsupported)"**, which is
      false for 5 of the 7 — they define a perfectly good `a(n)` or predicate. This is the same defect a
      critic caught on the same function in item 33. It has its own bucket now, and **the coverage table
      in `strategies.md` was re-measured rather than adjusted**: it turned out to be stale from *item
      46*, not from this item (predicate 2,138 → 2,128, `a(n)` 1,052 → 1,029, print-loop 735 → 739,
      runnable 3,925 → 3,896). The auditor's predicted arithmetic assumed the old table was current;
      measuring rather than transcribing is why that did not propagate.
    - **"A162762 is clean only by luck" understated it.** It avoids the *word*, not the substance: its
      prompt still carries `Empirical g.f.: 2*x^2*(x^2-x+1)*(x^3-x-1)/…` and "a(n) = 2n - 2 …, **with
      equality for all known terms and the above g.f.**", either of which reproduces all 17 known terms
      in Python and then runs on. On a wider word list the counts are A162762: 3, A162763: 3, A162764: 4
      — so the sequence that already burned a pick is as exposed as its siblings.
    Also taken: `_context` now slices **before** filtering, so this item's change is provably
    *subtractive* and can never promote a fifth program into a prompt (latent — all 7 flagged entries
    have exactly one eligible program — but invariant 5 makes it worth closing); the reason reads
    "a comment calls it *{word}*", because the old phrasing rendered as "describes itself as
    conjecturally" for A393125 and because a comment near a program is not always a claim about it; and
    the recall gaps `not proven` (an asymmetry with `not proved`), A291786 and A277967 are recorded.
    **Its own evidence that this is not item 46's mistake:** the shipped word list applied to every
    **non-PARI** block in the corpus — a sample the check never sees — gives 8 matches, **8 of 8 genuine
    author disclaimers**.

    **A process error of mine:** I ran the mutation harness while that auditor was reading the tree, so
    it saw `pari.py` in mutated states (including one with the check disabled) and had to re-take its
    measurements at pinned hashes. Do not mutate the working tree while an agent is auditing it.

    **What this item does NOT fix, and the write-up must not round up.** The `_context` filter removes
    the flagged program but **not the conjecture**: `entry.comments[:8]` and `entry.formulas[:8]` are
    still quoted verbatim, and A162763's prompt carries **3** conjecture lines and A162764's **2**,
    including "Conjectured to hold with equality for all n" and a conjectured g.f. A162762 is clean only
    by luck. So a model can read the conjectured closed form out of the "Formulas:" block and implement
    it in Python, where nothing can detect it. "The model is no longer handed their program as correct"
    is true; "the model no longer sees the conjecture" is false. Filtering `%C`/`%F` is not the obvious
    fix — reading those fields to *reject* would have falsely flagged A162761, the proved sibling — and
    is left open, bounded by there having been no model session since session 4. Recorded in
    [known limitations](known-limitations.md#strategies).

    Working files are in **`data/item47/`** with a `README.md`: `c_evidence.py` (the population and
    pattern scan — writes beside itself, never into the repo), `c_reach.py` (what the check would do,
    through the production functions), `c_verify_critic.py` (re-derives the critic's findings),
    `planCONJ.md` (the plan with all 19 findings and their resolutions as section 0), and
    **`mutateCONJ.py`, the one to re-run** before changing `pari.conjectural`, `_CONJECTURAL`, the check
    in `build_candidates`, or the filter in `codegen._context`.

48. **A conjectural sequence leaves the `--model` pool too (2026-09-26).** The user, shown four options:
    "Suppress the model path for flagged sequences". **No pipeline run and no database write.** 422 tests
    (414 + 8), **8 mutations, 8 caught**, all three files restored byte for byte with sha256.

    **Why item 47 did not already cover this.** `Runnable._why_not` returns `None` for any PARI-bearing
    sequence with at least `CODEGEN_MIN_KNOWN_TERMS` terms *whatever* the PARI verdict, so refusing the
    entry's program left the sequence in the model pool — and **A162763, A349899 and A351088 were in it
    on the day item 47 shipped**, with A162762 and A162764 joining them whenever their reviews close.
    The model is shown the entry's own `%C`/`%F`, which state the conjecture outright, and a Python
    re-derivation of a conjectured closed form reproduces every known term by construction, so
    verification cannot tell it from a real result. That is session 10's failure with a program the
    static check cannot see.

    **What shipped.** `pari.CONJECTURAL_REASON` plus `pari.rejected_as_conjectural(rejected)` — callers
    key on that, never on the sentence, which had already been reworded once while two call sites went
    on matching the old text. `Runnable._why_not` returns `conjectural_program` with the model on.
    `cli.form_bucket` was extracted as a pure function and now uses the same marker.

    **The trade, and the property it rests on:** only the *draw* is blocked. `attempt_sequence` has no
    such gate, so `oeisbot attempt A162763 --model` still runs the model and records what happens. That
    is what made this cheap rather than lossy, and it is pinned by
    `test_a_targeted_attempt_still_runs_the_model_on_a_conjectural_sequence` and by a mutation that adds
    the gate there. **Do not "fix" the asymmetry.** It costs **7 sequences of 26,752 (0.03%)** — an order
    of magnitude less than item 47's write-up implied when it called this "discarding sequences a model
    could legitimately extend", which is corrected above.

    `left_out`'s `conjectural_program` is therefore the **one key that is a selection policy rather than
    the skip an attempt would record**; `Runnable`'s docstring says so, because the class's whole
    contract is that its keys predict attempt behaviour.

    **Two things this item's own process turned up.**
    - **An existing test caught the change, correctly.**
      `test_selection_leaves_out_what_could_only_be_skipped` asserts "with the model on, the model can
      still take it" for every case it parametrizes — which is exactly what this item changes. The
      conjectural case was **removed from that parametrize** rather than the shared assertion weakened,
      with a pointer to the three dedicated tests.
    - **`oeisbot stats --forms` had no test at all**, which is how it mis-filed a bucket twice (item
      33's critic, then item 47's auditor). The first mutation run MISSED the bucket mutation for that
      reason. The logic is now `cli.form_bucket`, a pure function with a seven-case parametrized test,
      and the mutation is caught. A bucket-*order* mutation was drafted and deliberately left out: no
      corpus entry is both conjectural and helper-calling, so it was a mutation known in advance to
      miss.

    Working files in **`data/item48/`**: `mutate48.py` is the one to re-run before changing
    `Runnable._why_not`'s model branch, `pari.rejected_as_conjectural`, `CONJECTURAL_REASON` or
    `cli.form_bucket` — 8 mutations, 8 caught, three of them with the isolation check that requires the
    named test to be the *sole* failure.

49. **All three reviews tackled: #2 and #3 closed, #1's step 7 re-run and packaged (2026-09-28).** The
    user: "Tackle reviews 1-3. Go slow and ask questions when needed", then, asked three questions,
    chose to have the agent close #2 and #3, re-run step 7 and prepare #1's package, and update the docs.
    **423 tests (422 + 1), 2 mutations, 2 caught.** One database write: two review rows.

    **Reviews #2 (A162762) and #3 (A162764) are `rejected`**, each with a note naming the reason. The
    standing rule in `CLAUDE.md` and `operations.md` was that a coding agent must not close them; the
    user lifted it for these two rows and it still stands for every other. Backup at
    `data/oeisbot-before-close-reviews23.sqlite3`, integrity checked before the write.

    **The draw was verified unchanged, end to end, not argued.** `select.candidates` with the real
    `attempt.Runnable` gate, against the live database and against the backup: **3,438 either way** and
    **26,747 either way**. The two sequences only changed which gate excludes them — before, `blocked`
    in `select.candidates` dropped them as open reviews; now `pari.conjectural` does, which is why
    `no_supported_program` went 1,418 → 1,420 and `conjectural_program` 5 → 7 with both totals still.
    **A162761, the one proved sibling, is in both pools**, which is the discrimination item 47 claimed
    and item 45 said was impossible.

    **"The close cost nothing" was wrong, and the audit caught it.** That claim was made off the pool
    measurement alone, and a `new` review guards a second, independent path: `attempt_sequence` skips on
    `db.open_review` (`attempt.py:460`). With the rows `rejected` that guard is gone, so
    **`oeisbot attempt A162762 --model` now runs the model** on a sequence whose `%F` states the
    conjecture outright and which a Python re-derivation reproduces by construction — where before item
    49 the same command returned `skip("open_review")`. Worse, `db._insert_review` has **no check against
    a prior `rejected` row for the same A-number** (only `set_review_status` guards the `submitted`
    case), so such a run would open a *new* review for the same false win. The honest statement is the
    narrow one: **the draw is unchanged in both pools, and the close cost the `open_review` guard on a
    deliberate targeted `--model` attempt of exactly the two sequences known to produce conjectural false
    wins.** Nothing was done about it — it needs a decision, not a patch, because the nearest fix (gating
    `attempt_sequence`) is the asymmetry item 48 says in terms not to "fix". See next-step (v).
    This is the second time a "cost nothing" claim in this project went past the evidence behind it; the
    first is recorded at item 41's audit. The conjectural status of all three was re-read from the entries rather than taken from
    this page: A162762's "Empirical g.f." and "equality for all known terms", A162763's and A162764's
    "(conjectured)" g.f.s — against A162761's "Conjectured by _Colin Barker_ … **edited and proved by
    _M. F. Hasler_**".

    **Review #1's step 7 was re-run** through `attempt.recheck` — the pipeline's own path, so the verdict
    is the one a run would reach — five days after item 44's check. Still new: the live entry ends at
    a(24), keyword `more` is present, all 24 published terms agree, none of a(25)..a(42) is published.
    The cached b-file was backed up first because `recheck` refreshes it; it came back byte-identical.

    **A defect found while checking the b-file against the rules, and fixed.**
    [SubmitB.html](https://oeis.org/SubmitB.html) requires a b-file to end with a blank line, warning in
    capitals that *"THE LAST DATA LINE MAY BE IGNORED"* otherwise — and the last data line is the highest
    new term. `terms.format_bfile` newline-terminates each line and adds no blank one, so **every b-file
    the project has ever written violates a published OEIS requirement**, not just review #1's. The
    `+ "\n"` went at the **call site** in `artifact.write`, not in the helper, because the README's
    new-terms fence uses the same helper and its closing fence sits on that trailing newline — the
    mutation that moves the fix into the helper is caught by the fence half of the new test. Everything
    else on that page already passed, checked on the raw bytes: 42 well-formed lines, contiguous from
    the entry's offset, 9 digits at most, ASCII, no BOM, no tabs. **What is *not* claimed: nobody tested
    whether OEIS's parser really drops the line.** The defect is the documented-rule violation, which is
    verified; the consequence is OEIS's own warning, quoted rather than reproduced.

    **Two follow-ons from the audit, both about the helper's blast radius.** `terms.format_bfile` now
    carries a docstring saying in terms that it returns the **body only** and **the caller owns the
    trailing blank line** — without it, the next writer of a b-file re-introduces exactly this bug and
    `tests/test_recheck.py` would not catch it, because that test reaches the helper only through
    `artifact.write` and the helper has no direct unit test. And `scripts/make_demo_db.py` was writing
    its demo b-file the old way, so the demo database no longer matched the shape
    `docs/data-and-schema.md` documents; it now writes the blank line too. Neither is load-bearing —
    the demo database is for looking at the dashboard — but the docstring is the one that stops this
    recurring.

    **The step-8 package is `data/review1/SUBMISSION.md`**, beside item 44's evidence: the corrected
    `b385331-submit.txt` (to be renamed `b385331.txt`), the DATA line, and the `%E` line. The DATA
    finding is worth keeping — **all 42 terms are 191 characters**, inside the style sheet's 260-character
    guide, so nothing needs truncating and the b-file carries no term DATA could not hold; the first
    draft of that file said the opposite and was corrected before anyone read it. The artifact's own
    `b385331.txt` was deliberately **left alone**: it is the record of what the run produced.

    **Two stale claims corrected, in two files.** This page's next-step (i) and `CLAUDE.md` both said
    that under `--model` the conjectural check "removes nothing" — falsified by item 48 two days
    earlier, and in `CLAUDE.md` sitting a few paragraphs from a correct description of item 48. Neither
    was load-bearing for the close, but (i) was the paragraph a reader would have used to decide it.

    **Two independent audits, one on the code and database and one on the documentation.** The code
    audit confirmed the change and the write — two differing rows, both in `reviews`, every other table
    byte-identical to the backup; both mutations effective; its own restorations exact to the blob hash
    — and found the `open_review` overstatement above, which is the finding that mattered. The docs
    audit found **14 confirmed defects**, most of them not this item's: the two pool *left-out* tallies
    in the "Resuming" checklist, which item 49 itself made stale (1,418 → 1,420 and 5 → 7, with the
    totals unmoved); a surviving "the model pool is unaffected" in `pipeline.md`; `item 45 missing from
    the canonical uncommitted list`; and a block of **session-10 residue** nobody had caught for a week
    — the real-run totals in three files frozen at the `id <= 175` snapshot (107 sequences / 173 runs /
    12.3 h, against 157 / 225 / 14.9 h), `data/runs/` counted at 198 against 247, `data/bfiles/` at 69
    against 71 with one synthesized copy against three, `artifacts/` described as one folder when it
    holds three, and five pieces of local state — `data/session10/`, `data/item47/`, `data/item48/` and
    two database backups — missing from the table a session uses to decide what is safe to delete. All
    fixed here, each number re-derived by query or by counting the disk, not copied from the audit.

    **The pattern worth keeping:** every one of those was a number that stopped being re-measured. The
    checklist that exists to catch drift had drifted; the local-state table that says what is safe to
    delete omitted two backups. `tests/test_docs.py` guards the test counts and nothing else, which is
    why the test totals were the one family of numbers that was right. So item 49 leaves
    **`data/item49/recheck_numbers.py`**, which checks about thirty of the unguarded ones against the
    database, the disk, `git status` and the live `queue` lines and exits non-zero on a mismatch. It is
    not a test and is deliberately not wired into the suite: several of its expectations are
    hand-written prose figures that a legitimate change should move. Run it at the end of a session that
    touches counts, and **update it when the docs legitimately change.**

50. **Session 11: one 60 s PARI pass, 25 picks, and a per-pick reading that beat the base rates
    (2026-09-29).** The user: "Do Another 60 s PARI session now", then **25 picks** (the cap, one run)
    and **full pre-registration**. Run as `run -n 25 --verify-s 60 --extend-s 1800 --seed 211`, no
    `--model`, with `PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1` (console encoding and buffering only);
    database session **11**, attempts **#229-253**, 17:07:56Z to 19:55:03Z. **25 picks, 25 program runs,
    0 skips, 10,022.4 s (2.78 h), 5 verified, 0 new terms, 8.98 picks/h.** 16 `verify_timeout`
    (60.23-60.32 s), 5 `extend_budget`, 2 `wrong_term`, 2 `incomplete`. Console `data/session11_pari.log`;
    pre-run copy `data/oeisbot-before-session11.sqlite3`; everything else in `data/session11/`
    (`README.md` first, then `planS11.md` and `resultsS11.md`). No code changed.

    **Pre-registered in `planS11.md`** — the picks, the pool line, and, new this session, **every pick's
    program read before the run** (`progs.py`) with a per-pick probability of verifying beside the pooled
    known-term base rate, the two vectors to be scored by Brier. A critic reviewed the draft and returned
    13 findings; all held on independent re-derivation (`checkcritic.py`) and all were taken. The one
    that mattered most: the draft predicted A373945 would end `protocol`, and the critic showed from
    `verify.on_line` that a stdout line not starting with `@` is *ignored*, so the run would be a
    `verify_timeout` with no record at all — which is what happened. The critic also moved A348329 from
    .45 to .80 on the term logs' factor-predicate anchors (it verified in 6.13 s at 365k calls/s), and
    corrected a floor formula, two frontier bands and the `infeasible` reasoning.

    **Sixteen of eighteen predictions held**, counting P18 by its sub-claims. Exact hits: the 25 picks in
    order; the pool line byte for byte (`3431 ... 1420 / 383 / 81`); 25 runs; 5 verified inside both
    intervals; 2 of the 16 many-known-term picks; timeouts dominant; no new terms; +5 prediction rows,
    none trustworthy; no `searched_bound` firing, with A175807 reaching the check at 28,872 calls/s and
    not firing; **exactly the five named frontier rows, each inside its band** (A034293 339,999; A348329
    414,709,999; A339009 920,000; A175807 1,670,000, past its own 10^6 bound; A281663 640,000); dead ends
    +24 at the run's budgets (band 22-24) and +20 at `queue`'s (93-96); and all five P7 mechanisms, with
    A335304's `a(1) = 8, known value 2`, A290024's `a(1) = 2, known value 1` and A373945's `reproduced 0
    of 23 known terms within 60 s` verbatim, A274003's tail naming `is_A178751`, A300397's naming
    `parisizemax`. **Two missed, for one cause**: the wall clock (10,022 s against a 90% band topping at
    9,957) and picks/h (8.98 against 12.8-13.4), because the Monte Carlo drew every verified pick's cost
    from the historical mix while the same page had proved that three of them could not be stopped early
    and argued a fourth would not be. The write-up's first repair of this ("pin three, the actual lands
    inside") was **asserted, not computed, and wrong** — pinning three leaves the actual 6 s outside;
    pinning all four brings it inside (`predict_fixed.py`). The plan also carried an arithmetic slip in
    one P11 figure (a pool total minus a dead-end total instead of its increment) that the critic missed.

    **P4 is the result.** Brier **0.0127** for the per-pick reading against **0.1467** for the pooled
    rates; the five verified picks were exactly the four the reading put at >= .80 plus the one at .50,
    and all twenty it put at <= .05 failed. The pre-critic reading would have scored 0.024 — the critic
    improved the calibration, not the conclusion. One draw of 25; session 10's three-pick reading had
    been found weakly supported, and reading all 25 is the difference. The timeout-vs-deterministic
    split the plan offered as a second discriminator was inconclusive (4 deterministic, between the two
    expectations).

    **P7 is the finding: four of 25 picks (16%) were program-selection misreads**, every one retiring its
    sequence as `all_programs_dead_ends` (the three deterministic rows at every budget, A373945's timeout
    at gates up to 60.3 s) although none was actually tested. (a) **A274003**: `is_A274003` calls
    `is_A178751`, defined in A178751's entry; `pari._ANAME_USE` is `\b([Aa]\d{4,7})\s*[(\[]` and `_` is a
    word character, so the *prefix* form has no `\b` — next step 5 knew the *suffix* form. **The obvious
    widening is wrong**: dropping the `\b` with the group on the A-number would also flag `A034293` in
    `is_A034293(n)=...`, rejecting a program that verified this session; the check would have to capture
    and compare the whole identifier (`checkaudit.txt`, F6). `known-limitations.md` named A274003 only
    for its *rejected* second block. (b) **A335304**: the block defines `is(n)` (a helper, commented
    `\\ A054735`) and `lista(nn)`, the real algorithm; the builder took the one-argument def. Not in the
    docs before. (c) **A290024**: the entry's loop `for(n=1, 7, ...)` prints a(1) onward while `%O` is 0,
    and the emitter numbers from `known.first_index` — **the values were right, the index was off by
    one**, and a correct program's sequence is retired under this sha. `strategies.md` documents the
    counter; the failure mode was not stated anywhere. (d) **A373945**: `a373945(upto=10^8)` is a bulk
    printer read as `a(n)` (next step 7's shape), and its `print1` puts `0, 1, ` before every `@T` on
    the same line, which `on_line` ignores. Session 10 had reported 2 selection defects in 50 picks, but
    from the deterministic rows only — A373945's kind leaves no trace in the row — so the two rates are
    not comparable and 16% stands on its own.

    **Three observations, not results.** A348329's driver *reported* reaching 414,709,999 with no ninth
    term (a(9) > 4.1e8 if the program is right and the report honest; Eldar's comment puts a term at
    3.96e24); A175807's reported scan passed its published 10^6 bound by 1.67x — the second such row, after
    A038703 (#192, database session 9) at 147x in working session 10, and the first passed by less than
    2x; A270102 reproduced 22
    of 24 terms in 37.6 s and the whole difficulty is a(23)-a(24) (5,102 → 49,163).

    **Pool and counts, re-derived by query**: `queue` 3,438 → **3,418**, dead ends 74 → **94**; at the
    run's budgets 3,431 → 3,407 (81 → 105; A034293 stays in, its second program unrun); `queue --all`
    unchanged at 26,747 / 16; attempts 253, sessions 11, predictions 455 (455 of 455 replayed), 182
    sequences, 250 runs, 17.7 h; `data/runs/` 268. Base rates for the next plan: `<= 10 known` 24/72,
    `> 10 known` 8/96 (10/98 with the pair), 1 genuine win in 32 verified first runs at the gate;
    E[cost | verified, not bound-stopped] 1,501 s over 27 rows.

    **Audit.** A fresh critic found **20 defects** in the write-up; each was re-derived (`checkaudit.py`,
    `predict_fixed.py`) and **all 20 held** — the false "first time" claim, the asserted repair, "sixteen"
    for twenty, "at every budget" for a timeout, a double-counted cost decomposition, the regex proposal
    that would reject A034293, a misattributed quote, a split scored a hit that was inconclusive, a
    comparison that was not like-for-like, and "reached" where the project's own vocabulary says
    "reported". Full list at the end of `resultsS11.md`. Three decisions rows added; two next steps
    extended (5, 7) and two added ((vi), (vii)).

51. **Every open decision answered, and the chosen items built while session 12 ran (2026-09-30).** The
    user: "Present all the decisions to me as questions with options". Nineteen questions in five
    batches; the answers, in the order asked: review #1 — walk through submitting, and standardize how
    a review is identified, **in `oeisbot review list` and the dashboard inbox** (not in chat, not in
    the README); commit — **not yet**; offer (a) — **re-derive the count first**, then (after the
    recount) **backfill `program_sha`**; session 12 — **25 picks now, full pre-registration with a
    critic**, and **launch first, edit during, test after**; item (v) — **refuse in `_insert_review`**;
    item (vii) — **measure the pool first**; item 5 — **design, measure, then build**; item 7's bulk
    printer — **measure the signal**; item 7's `iferr` wrap — **do not wrap**; item (iv)'s remainder —
    **quote the flagged program under an honest header**; item 4 — **measure both directions first**;
    item 6 — **compare like with like**; item 10 — **replay first**; item 9 — **scope it first**; item
    46's two deferrals — **both** (the `_DEF` nested-paren fix and the `on_line` wrap); the small
    leftovers — **all three** (`cpu_us` overflow, keying `infeasible` by time vs memory, flagging a term
    below a published bound). Everything below was built after session 12 launched and before its
    tests ran, per that sequencing; **the test suite, the dashboard build and the backfill are in item
    52** with the session's results. No database row was written by this item.

    **Review #1 (A385331 a(25)..a(42))**: the step-8 walkthrough was written for the user (eight steps
    from signing in to saving the edit, then step 9's `review set`); nothing was submitted. The
    identity block: `db.review_rows` joins each review with its attempt and sequence, `cli.review_block`
    prints three lines (sequence and name; `N new terms, a(i)..a(j), from <origin>, attempt #k`; folder
    and note), `/api/reviews` gained `program_origin`, and `views.tsx` shows the same three facts in the
    same order. Rendered against the live database in `operations.md`.

    **A `rejected` review now refuses a later one for the same sequence (item v)**: `db.ReviewRefused`
    raised by `_insert_review`; `db.record_win` catches it *inside* its transaction — raised out of it,
    the rollback would leave the attempt `recheck_pending` to be retried and refused every session — and
    records the attempt `extended` with its artifact and `extra.review_refused = {prior_review, reason}`;
    `_resolve` says `review refused: ... nothing was added to the inbox`. Reopening the old row lifts
    it. Three tests (`test_db` ×2, `test_attempt` end to end).

    **The model prompt quotes a disclaimed program under an honest header (item iv)**:
    `codegen.CONJECTURAL_PROGRAMS_NOTE` ("Programs the author calls conjectural or heuristic (do NOT
    assume they are correct: ...)") with the author's matched word beside each block, replacing the
    2026-09-26 decision to drop the block; the `progs[:4]` slice still precedes the partition, so a
    flagged block never frees a slot. Rendered on A162763. Three tests rewritten. Whether the header
    restrains a model is unmeasured: no model session since 4.

    **Offer (a), recounted (`data/offerA/recount.py`)**: 59 attempt rows are orphaned (their sha is no
    longer produced by the builder; item 41 counted 49 and item 46 one more), 51 of them lost a
    retirement, **45 un-retired sequences sit in today's pool at the run's budgets (34 at `queue`'s),
    none re-attempted since**, and 46 of the 47 pending rows map to exactly one current candidate of the
    same form (A366832's does not). Re-deriving them at today's gates would cost about 6.1 h (35 timeouts
    at 60 s, 11 full extensions at 1,800 s). The user chose the backfill; it is deferred to item 52
    because changing the pool before the launch would have changed the seed-212 draw the plan is built on.

    **A callback exception no longer kills the reader thread silently (item 46's deferral)**: both
    sandbox backends guard `on_line` and `on_tick`; an exception stops the job as
    `Status.CALLBACK_ERROR` with a reason naming it, the pipes keep draining, and the harness records
    `Stop.HARNESS_ERROR` — outside `db.DETERMINISTIC_FAILURES` and `_TAIL_STOPS`, so a bug of ours
    retires nothing and no stderr is appended. Two attacking sandbox tests (a raising `on_line` on a
    print flood, a raising `on_tick`), one harness test, one dead-end test; `sandbox.md` guarantee row.
    `posix.py` is edited symmetrically and, as ever, cannot be exercised here.

    **An `infeasible` verdict names the budget it ran out of**: `estimate.Assessment.infeasible_on`
    (`time`, `memory` or both) → `Harness.infeasible_on` → `AttemptResult.infeasible_on` →
    `extra.infeasible_on` (`time`, `memory`, `time+memory`); `db.is_dead_end`'s infeasible clause is a
    `CASE` on it — a verdict on time holds under any memory cap and one on memory under any extension
    time; rows without the key (every row before today) still need both. The skip detail now reads
    "with no more of the budget it ran out of". Tests in `test_estimate` (three variants) and `test_db`.

    **A new term below a published bound is flagged, never refused**: `Harness.below_bound` collects the
    indices of new terms at or below `searched_bound.value`; `AttemptResult.below_bound` = `{bound,
    quote, indices}`; `extra.below_published_bound`; a console `WARNING`; a README note ("Either that
    search or this program is wrong"); a dashboard warning. The safe direction of invariant 10. No real
    case exists; `tests/test_bounds.py` drives it, `tests/test_recheck.py` checks the README. **Adding these two fields to
    `AttemptResult` invalidates any pending win saved before today; `data/pending/` was verified empty.**

    **The gp memory projection compares like with like (item 6)**: `Harness.stack_cap` (= the
    `parisizemax` gp is launched with, 0.8 × the cap) is the memory budget `assess` is judged against
    for gp; Python keeps the job cap. Before this every gp figure — `default(parisize) + heap`, the
    stack — was compared with the job's commit cap, ~800× larger, so no gp run could be judged
    infeasible on memory. A synthetic test drives the same term lines through a gp and a Python harness
    and requires the gp one to stop strictly earlier. What the projection still cannot see is memory gp
    takes outside the stack (GMP temporaries — A277041's actual death); `known-limitations.md` says what
    catching that would take.

    **The `cpu_us` overflow leftover was already closed by item 46**: the 40-digit field cap precedes
    `int()`, `cpu_us / 1e6` cannot overflow a float at that width, and `on_line` catches
    `OverflowError` beside `ValueError`; two tests pin it. Documented, no code.

    **Definitions are read with balanced parentheses, and the helper check compares whole identifiers
    (items 5 and 46)**: `pari._def_head` and `_defined_names` replace the `[^()]*` regexes
    (`f(n, p = part(n)) = ...` is a def; its parameters count as defined); `_ANAME_USE` captures
    `\w*[Aa]\d{4,7}\w*` and `undefined_a_numbers` compares the identifier itself, so `is_A178751`
    (prefix) and `a375301_row` (suffix) are caught while `is_A034293` defined in its own block is not.
    **Measured as a diff of two candidate snapshots** (`data/measure0930/diff.txt`): exactly the **40
    statements in 36 blocks** item 46 counted move from call to def; **31 sequences gain a candidate**
    (4 only a new sha, a helper def now kept beside the program) and **12 lose one, every one a genuine
    other-entry helper by inspection**; candidates 4,239 → 4,253, rejections 1,576 → 1,562. All 27
    genuinely new programs were read: mostly ordinary defs with defaults after the first parameter; a
    few will only waste a pick (A277852/A277853 return a set; A278832 is an "illustrative" chess brute
    force; A294900's def is head-only). **A gap the reading found: 11 defs in 10 sequences end at `=`
    with their `{` body on the next line**, which `split_statements` breaks apart — recorded in
    `strategies.md`, not fixed (`data/measure0930/headonly.txt`). Two tests.

    **Measurements owed, all done, all read-only (`data/measure0930/`)**:
    - **(vii) print-loop start vs offset** (`shapes.txt`): of 108 index loops (emit on every
      iteration) **26 start somewhere other than the offset**; of 921 filter loops **20 start above the
      first known value**; **47 candidates listed, 44 in the pool**. A decision for the user with a real
      number behind it now: number from the loop start (a flagged rewrite) or refuse the form when the
      start disagrees.
    - **(vi) predicate beside other defs**: **235 blocks** define a drivable predicate *and* another def
      (133 in the pool); **15** of them define a list printer (`lista`, ...), A335304's shape. Which
      predicates are the real one needs reading, block by block; the 15 are the natural first sample.
    - **(7) the bulk-printer signal**: **4 defs whose only parameter has a default** (`a368124(rmax=205)`,
      `a368129(rmax=235)`, `a373945(upto=10^8)`, `a375093(upto=600000)`), **all four bulk printers**, 2
      in the pool. The signal is exact on this corpus; a static refusal would cost nothing today.
    - **Item 4, value dependence, replayed both ways** (`valuedep.txt`): over the 39 attempts with
      replayable projections, the data test on positive-cost points flips 5 attempts on, the 4-point
      threshold 2, the widened name test 1, and **in every variant the only attempt whose outcome
      changes is A385331** — its `infeasible` stop is withdrawn and the extension runs on for
      **+1,068 s** with no term gained or lost (the 18 were found before the stop); the other flips are
      `extend_budget` runs, unchanged. On the selection side the widened name test newly flags **9 pool
      sequences** ("Smallest prime factor of 10^(2^n) + 1", ...), 0.17% of the draw, cut to 0.11%.
      **Recommendation: leave it**; nothing on the record gains.
    - **Item 10, the risk flags, replayed** (`riskflags.txt`): of 455 projections, 448 are untrusted and
      risky, 6 trusted and not risky, **1 trusted and risky — A194099's, the case that raised the
      item**. *Withdrawing trust when risky* (R1) would touch only that row and would undo the one kill
      that saved the run (it would run on to its 1,800 s budget): harmful. *Arming the kill for
      untrusted risky projections* (R2, 2× the high estimate, 10 s grace) would have killed **0 terms
      that went on to finish** and cut **8 runs earlier, saving 4,423 s** (six `extend_budget` runs
      cut at 10-800 s instead of 120-1,800 s; two session-5 kills unchanged) — on a thin sample of 14
      scored untrusted rows. **A decision for the user**, with the caveat that the trust rule exists
      precisely so an untrustworthy fit cannot kill a term, and the record's zero losses are six
      finished terms wide.
    - **Item 9, Wolfram Engine, scoped** (`wolfram_scoping.md`): 8,394 candidates have Mathematica,
      **5,282 have it and no PARI**; the strategy needs a sandboxable runtime (activation without
      network is the open question), a Mathematica builder of the PARI builder's size, drivers, grants,
      tests and docs — three to five items — and its expected yield is lower than PARI's per run. The
      go/no-go experiment is an afternoon: install, activate, relocate the licence, run one block in the
      container.

    **Docs touched**: `operations.md` (guard, block, `harness_error`, `infeasible`, checklist warning),
    `data-and-schema.md` (reviews, `extra` keys), `dashboard.md`, `strategies.md` (honest header,
    helper check, measurement, head-only gap), `known-limitations.md` (six passages),
    `verification-and-estimation.md` (stop table, mapping, memory budget, below-bound), `pipeline.md`,
    `sandbox.md`. `CLAUDE.md` at the end of the working day.

52. **Session 12, then the offer (a) backfill, then the tests (2026-09-30).** The user: "Run 25 picks
    now", "Full, as session 11", "Launch first, edit during, test after". Run as `run -n 25 --verify-s 60
    --extend-s 1800 --seed 212`, no `--model`, detached from the terminal (`data/session12/pid.txt`)
    with `PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1`; database session **12**, attempts **#254-280**,
    17:31:33Z to 18:22:46Z. **25 picks, 27 program runs (A062274 and A101075 ran both their programs),
    0 skips, 3,069.0 s (0.85 h), 2 verified, 0 new terms, 29.33 picks/h.** 21 `verify_timeout`
    (60.31-60.42 s), 3 `wrong_term`, 1 `incomplete`, 1 `extend_budget` (A255730, the full 1,800 s), 1
    `searched_bound` (A325963, 0.663 s). Console `data/session12_pari.log`; pre-run copy
    `data/oeisbot-before-session12.sqlite3`; everything else in `data/session12/` (`README.md` first,
    then `planS12.md` and `resultsS12.md`). The code that ran was session 11's: item 51's edits landed
    while the run was in progress, and the process had its modules loaded at launch and spawns only
    `gp.exe`.

    **Pre-registered in `planS12.md`**, by session 11's method: the picks, the pool line, every pick's
    program read (`progs.txt`) with three gp probes of the semantics the readings rest on, a per-pick
    probability beside the pooled base rate, and — the correction session 11's miss asked for — a
    Monte Carlo that **pins** what the page proves (A255730's extension cannot be stopped early: no
    projection is possible and its bound cannot fire; A325963's 10^12 bound fires at any physical rate).
    A critic returned 14 findings; all held on re-derivation (`check/`) and all were taken. The one that
    mattered most: the cost model had scaled every pseudoprime family from one anchor by bit count,
    ignoring how many k survive trial division; timing each family's own predicate over k = 1..1000 moved
    three verification-time estimates by 1.3-1.7× and one reproduced-count band (A062274's `(n!)!` loop:
    `primelimit` is 1,048,576, so (9!)! factors by trial division in 15 s).

    **Fifteen of seventeen predictions held outright; P16 held except its runtime band (0.6635 s
    against 0.7-1.2 s); P17 held on 20 of 21 reproduced counts (A079009's a(8) arrived at 2.31 s where
    the plan said it would not fit); P11's retirement counts (24 at the run's budgets, 23 at `queue`'s)
    held under a constant-code re-measurement, its literal pool numbers made unobservable by item 51's
    builder change during the run.** Exact hits: the 25 picks in order; the pool line byte for byte; 27
    rows; 2 verified inside both intervals; 0 of the 15 many-known-term picks; the mode counts
    21/4/1/1; **all five P7 mechanisms with their detail strings verbatim** — A215906 `a(1) = 6, known
    value 0` (the loop starts at i = 2 and never emits the term 0), A396944 `a(0) = 3, known value 2`
    (the search runs over odd k only), A138595's three-line `incomplete` tail naming `BPSW_psp (t_FRAC)`
    at 0.026 s (a predicate valid only from k = 11, handed a fraction at k = 1 — the `iferr` shape the
    user declined the same day), A264886 `a(1) = 2, known value 1` (the def `a(n)` is the primorial
    helper; the entry's real loop was not lifted because its bound `1e3` is not an integer literal),
    and A058235 `reproduced 0 of 24` because **the entry's own program is never true** (`x^k + x*x + 1`
    where the name says `x^n + x^2 + 2`; root 1 over GF(3) for every k — a correction a human could send
    OEIS); no new terms; +1 `predictions` row (`fit_trustworthy` NULL, no fit possible); exactly one
    `searched_bound` (A325963: bound 10^12, `measured_rate` 553,798, `verified_scan_to` 349,440); exactly
    three frontiers, **A325963's the predicted 310,000** (five heartbeats: the only schedule the
    doubling rule admits), A276238 47,670,000 and A137210 34,550,000 inside their bands; wall clock
    **2 s** from the spike (3,069 against 3,071) and 29.33 picks/h against 29. **Brier 0.000185 for the
    per-pick reading against 0.076756 for the pooled rates** (session 11: 0.0127 vs 0.1467): the two
    verified picks were the two at .95 and .98, and all 23 at .03 or below failed.

    **Five of 25 picks (20%) were program misreads that retired their sequence untested** (session 11:
    16%), each foreseen: two loops starting above the first term (item (vii)'s shape, 44 pool sequences
    by item 51's measurement), a predicate outside its domain, a helper named `a` beside the real loop
    (item (vi)'s shape), and a wrong entry program, which nothing can see. Item 51 closed one of
    session 11's four (the A-number helper name) during this run; none of this session's five is
    closed. Three observations, not results: A276238's frontier sits below its next known term with
    no published bound; A137210's below both a(7) and its 3.4×10^10 bound (a timeout row: the check
    never ran); A325963 is the first row carrying both a bound stop and a frontier.

    **Pool and counts, re-derived by query.** At 18:23-18:25Z, before the backfill: `queue` 3,418 →
    3,408 (94 → 115 dead ends), at the run's budgets 3,407 → 3,396 (105 → 127), `queue --all` 26,747 →
    26,746 / 17 — the differences from the session's own 23/24 are item 51's (13 fewer
    `no_supported_program` net, 2 more out of reach, A274003 and A375302 refused before they can be
    dead ends, A122036 dropping to `too_few_known_terms`); `deadends_isolated.py` proves the session's
    part with the code held constant, and reproduces only against `data/oeisbot-before-backfill.sqlite3`
    now. Attempts 280, sessions 12, predictions 456, reviews unchanged (#1 `new`), 207 distinct sequences
    attempted (204 without skips), 277 program runs, 18.6 machine-hours, `data/runs/` 290, `data/pending/`
    empty, nothing submitted. Base rates for the next plan: `<= 10 known` 26/82, `> 10 known` 8/111
    (10/113 with the pair), **1 genuine win in 34** verified first runs at the gate.

    **The backfill (offer (a), the user's choice after the recount).** After the run and after the test
    suite passed: `VACUUM INTO data/oeisbot-before-backfill.sqlite3` (5,701,632 bytes, integrity ok, 280
    rows), then **one transaction rewriting `program_sha` on 48 rows** — the lost retirements whose old
    verdict retires at the run's or `queue`'s budgets and whose block yields exactly one current candidate
    of the same form (46 of them in the pool, 2 out of it for other reasons; the recount's 47th, A366832,
    is unmappable); each carries `extra.program_sha_backfilled = {from, on, item}`
    (`data/offerA/backfill.py`, dry run by default; `backfill_apply.txt`). Effect: `queue` **3,408 →
    3,375 (150 dead ends)**, at the run's budgets **3,396 → 3,352 (173)**, `queue --all` 26,746 →
    **26,745 / 18** (A309238, two known terms, whose only program's timeout row now keys). 13 orphaned
    rows were deliberately left: verdicts that retire nothing (`over_prediction`, `extend_budget` under
    the CPU share, `max_new_terms`) and blocks with no current candidate of the form.

    **Then the tests and the build, per the sequencing the user chose.** `436 passed` (69 s; 423 + 13
    new: 2 sandbox, 2 verify, 4 db, 1 attempt, 1 bounds, 1 recheck, 2 pari, plus the three rewritten
    codegen tests and one new classification branch `retry_guidance` needed for `harness_error`); the
    eight documented totals, the per-file table and the collected-counts paragraph moved with them, and
    `tests/test_docs.py`'s two timing patterns moved from "50 s" to "70 s" because the suite now takes
    that long; `check_docs.py` 0 problems with its expected-hits count re-judged to 5 (the three
    session-11 names became fixtures in `test_pari.py`); `npm run build` rebuilt the dashboard with the
    inbox identity block and the below-bound warning; `data/item49/recheck_numbers.py` re-baselined to
    today's counts and passing.

    **Audit.** A fresh auditor read `resultsS12.md` against the database, both backups, the term logs,
    the plan and the code and returned **16 findings**; each was re-derived (`audit/checkaudit.txt`) and
    **all 16 held**: the write-up's "Final state" had been overtaken by the backfill written after it;
    P16's 0.7 s was a rounded 0.6635 s below its band; "seventeen of seventeen" overstated three
    verdicts; the win rate was 1 in 35 by counting a 600-s-gate verification (34); A276238 has no
    bound; 204 vs 207 by the project's definition; `fit_trustworthy` NULL not 0; a 4.5 ms rate window;
    "384×" from rounded scores; two softened cost claims and one invented figure; an inferred schedule
    presented as observed; "half" for one; probe counts; the README citing this item before it existed.
    `resultsS12.md` carries the full list.

53. **The four decisions the day's measurements produced, and the two refusals they chose
    (2026-09-30, evening).** Asked as options with item 51's numbers behind them, the user chose:
    **refuse a print loop whose start disagrees** with where the emitter numbers from, over renumbering
    (a refusal costs a candidate, a wrong renumbering costs a sequence); **refuse a def whose only
    parameter carries a default** (the bulk-printer signal, 4 of 4 on the corpus); **leave the kill
    rules as they are** — the 4,423 s the untrusted-risky kill would have saved on record was judged
    against a sample of six finished terms and the trust rule's purpose; and **defer Wolfram Engine**
    with the scoping note attached. Next steps (vii) and 7 are therefore built, 10 and 9 are decided.

    **Built** (`pari.loop_start_problem` on `LoopFacts`, which `rewrite_print_loop` now returns as a
    fourth element; `pari._bulk_printer`): an *index* loop — a plain `for` whose print is a top-level
    statement of its body, executed once per iteration — is refused unless it starts at the offset; a
    *filter* loop — the print inside an `if(...)`, inside an inner loop, or behind `&&`/`||` — that
    prints its own variable is refused if it starts above the first known term; only literal starts are
    judged, and a filter loop printing an expression, or a `forprime`/`forstep` loop, is left to the
    gate. The first version treated any inner loop before the print as a guard, which excused index
    loops that compute their value in an inner loop and then print — the candidate diff showed 21
    sequences against the measurement's 44 and the criterion was replaced by the precise one (is the
    print at parenthesis depth zero of the loop body, with no `&&`/`||` before it). A def whose single
    parameter has a default yields neither an `a(n)` nor a predicate candidate, and the block's reason
    names it as a bulk printer; its own loop, if any, is still offered. Two tests, one per rule, each
    with the shapes that must *not* be refused.

    **Measured as a candidate diff against item 51's snapshot** (`data/measure0930/diff2.txt`,
    `pools_after_item53.txt`): **32 candidates refused in 30 sequences** — 13 index loops off the offset
    (A003112's two blocks among them), 11 filter loops above the first term (A215906's and A002475's
    among them), 4 bulk printers (A368124, A368129, A373945, A375093) — and 0 gained. Candidates 4,253 →
    **4,221**, rejections 1,562 → 1,591. Only 5 of the 30 are in today's pool with another candidate;
    the rest were already dead ends or out of reach, or had nothing else. The pool: `queue` **3,375 →
    3,357 / 1,958 (1432 / 383 / 143)** — 18 fewer to draw, 25 more `no_supported_program`, 7 fewer
    dead ends (sequences retired only through a loop now refused, which would have been re-drawn and
    re-retired otherwise). Fewer than the 44 pool sequences item 51's heuristic counted, by design: the
    measurement flagged every `for` loop with an `if` anywhere in its body that started above the first
    term, whether or not it printed the loop variable, and the built rule judges only what it can prove
    wrong from the text. A290024 and A215906 would both have been refused before running.

    **Not built, recorded**: the kill rules stay (next step 10 closes as "leave"); Wolfram stays on the
    list as deferred (next step 9). Tests **438 passed** (the two new pari tests; the total's eight places
    and the per-file table moved); `check_docs.py` 0 problems; `recheck_numbers.py` re-baselined to the
    new pool and passing. Docs: `strategies.md` (both rules, in the program-forms section),
    `known-limitations.md` (the two shapes marked refused), this page. No database write.

54. **The Pick map: the pick chance as a heat map, coloured by its change since an earlier snapshot
    (2026-10-13).** The user: "I like the idea of making the pick chance display a heat map like that one
    of the S&P such that the pick chance is correlated with the size of the square on the map and the delta
    of pick chance can also be displayed". Asked two questions, the user chose **"Change since the last
    snapshot"** for the colour and **"Group them by difficulty band but also make tabs such that different
    categories can be switched between via the tabs. Thus avoids having to display 5000 in one display"**
    for the layout. Built as a new **Pick map** tab (`#pickmap`): a tile is one sequence, its area is its
    chance of being the *first* pick of the next session (`weight / sum of weights`, `weight = difficulty
    ** -alpha`; the one share of the pool that adds up to 100%), its colour is the change in that chance
    since an earlier snapshot of the pool (seven classes, "within 1%" gray, a hatch for a sequence that
    was not in the earlier pool), nested inside nine difficulty bands, with a sub-tab for "All bands" and
    one for each non-empty band, a PARI-pool / model-pool switch, an α box (0 to 6), "Rebuild now", and a
    table twin under the legend. Docs: [dashboard.md](dashboard.md#pick-map) (the page and the endpoint),
    `known-limitations.md` (The Pick map: twelve notes on reading it too strongly), `data-and-schema.md`,
    `operations.md`.

    **What was built.** `oeisbot/pickmap.py` (132 lines, pure functions over `{a_number: difficulty}`:
    `chances`, `baseline`, `compare`, `band_summary`, `departure_reason`, `BAND_EDGES` = 0.5, 0.75, 1, 1.5,
    2, 4, 8, 16). Two tables in the existing database, `pick_snapshots` (id, pool, taken_at, session_id, n,
    digest, budgets, rules) and `pick_snapshot_rows` (`WITHOUT ROWID`, `ON DELETE CASCADE`), created by
    `connect()`'s `IF NOT EXISTS` (`schema_version` stays 2); `db.record_pick_snapshot` (one
    `BEGIN IMMEDIATE` transaction: dedupe on the newest digest, insert, prune to
    `config.PICK_SNAPSHOTS_KEPT` = 30 PARI and 10 model). `attempt.record_snapshot` / `snapshot_pool`
    (never raises: a failure is logged as `pick snapshot not recorded: ...` and the session runs on),
    called by `run_session` right after the "picked N of M candidates" line and before any program runs, so
    the snapshot is the pool the picks were drawn from; `attempt.rules_fingerprint`; the CLI command
    `oeisbot snapshot [--all]`; `GET /api/pickmap?pool=&alpha=&refresh=` in the dashboard app (read-only
    like every endpoint, a 422 for a bad pool or an alpha outside 0 to 6) with a one-entry-per-pool cache and
    a warm-up thread that `cmd_dashboard` starts. Frontend: `dashboard/src/treemap.ts` (squarified layout,
    band fairness, lumping, the seven change classes, the request path; React-free so node can test it),
    `pickmap.tsx` (the page), the `Tooltip` exported from `charts.tsx`, a `pollPath` argument on `useApi`,
    the tab in `main.tsx`, the styles. Retention was measured, not assumed: about **78 KB** per PARI
    snapshot and **0.62 MB** per model snapshot, **about 8.5 MB at full retention** against a 6.8 MB
    database. A snapshot of a pool identical to the newest is not stored again, so not every session has one.

    **The plan was criticised before any code, and the critic's first point changed the design.**
    Seven areas, each checked against the code and the session backups, not argued:
    (1) *The colour would have been constant.* From the pool before session 12 (3,412) to the one now
    (3,357), 55 sequences left holding 1.94% of the picks and 2 doubled in difficulty, and a plain
    `p / p_then` painted the **other 3,355 tiles** all the same "up 2%" (every one at 1.0198) -- true, and
    nothing about any of them. So the change is measured
    against the sequences that were in **both** pools (`pickmap.compare`: shares renormalised over the
    intersection, so a failed sequence reads 0.5 and the rest 1.0), and departures and entrants are
    first-class: hatched tiles, the "Left the pool" card, KPI counts. (2) *The pool is not a function of
    the database.* Session 12 ran `--verify-s 60 --extend-s 1800`, and its pool was 3,412 under the default
    budgets and 3,401 under those, so a comparison made under other budgets invents about 11 departures;
    and the pool is also a function of the code (items 46-53 each changed it). Hence `budgets` and `rules`
    columns **now**, because the schema has no migrations: the live pool is built under the newest
    snapshot's budgets, and a note says when budgets or rules differ. (3) *Cache and concurrency:* keyed
    by the database's stamp, single-flight, a plain `def` endpoint, built only on demand and never on a
    timer (a 5-8 s CPU job must not run while a session times programs), warm-up in `cmd_dashboard` and
    not a startup hook. (4) *Departures need reasons:* 33 of session 12's 55 departures were not session
    picks (the backfill and the dead-end changes of items 51 and 53), so each gets one read from the
    database -- review, attempt, left `more`, rules changed, budgets differ, else "unexplained" -- and
    small tiles that moved are never lumped into a gray "N smaller". (5) *Hermetic tests:* the endpoint
    tests stand in for `attempt.session_pool`, so none reads the developer's oeisdata or b-file cache, the
    pool line stays the first line of a session's output, and `test_api_never_writes` checks that every
    connection the endpoints open is read-only. (6) Snapshot
    mechanics: `BEGIN IMMEDIATE`, no `CHECK` on the pool, a cap on the model pool's retention. (7) Alpha
    clamped to 0 to 6 (`0.3 ** -1000` overflows), the "up 10%" class edge (the plan said 1.11, the code
    1.1; 1.1 stayed), and "extend, not new" for `treemap.ts` and its test, which the prototype had already
    put on disk.

    **Measured, and what it did to the claims.** `data/item54/area_spread.ts` lays the real 3,357 tiles
    out with the page's own layout and prints the drawn area per unit of chance for each band: **0.929 to
    0.930 for bands 0 to 6 at 1232 x 680** (0.918 at 900 x 600, 0.901 at 400 x 700), so area means the same
    in every band and is about 0.9 of the chance (header, padding and the 1 px inset of each tile). Two
    things the claim has to carry: **band 8 (2 sequences, 0.002%) has no inner width and is not drawn in
    "All bands" at any size tried** (its tab shows it), and band 7 collapses to 0.042 at 400 x 700. A fuzz
    of 5,000 random layouts whose band shares span 10^6 put the worst ratio of largest to smallest
    area-per-chance at **2.47** (the real pool spans 2.5 x 10^4 and agrees to a thousandth), so the
    docs say "the same scale to within about 2.5x when every band is big enough to see", not "exact". The
    first layout did not hold this (a thin band lost its header and padding out of its share and was drawn
    up to 1.10x smaller); `fairRects` now enlarges each band's rectangle by the part its frame takes, until a
    band's frame takes more than three quarters of it (`MIN_KEPT`, 0.25). **Pool-build time** was claimed
    from memory ("about 30 s for the model pool", "7 to 12 s for PARI") and the docs now carry what was
    measured: 6 to 12 s for either pool, **25 s for the first PARI build on a cold disk** (25.1, 5.8 and 5.7 s;
    model 9.3, 6.0 and 6.7 s), the cause of the slow first one presumably the disk cache, which was not
    isolated.

    **Five independent audits, 33 findings, every one that held fixed or written down.** None changes a
    pick, aborts a session or corrupts the database; the defects are in what the map says about itself.
    *`pickmap.py` and `compare`* (6): a mutant that let entrants into the survivors' normalisation passed all
    63 tests (tests added for entrants, for the order of `gone` and for review beating attempt); a docstring
    gave "20 sequences holding 2%", false because a weight is at most 3.33 (corrected to the measured 55
    and 1.9%); the tooltip's "Chance before" was the *rescaled* share (now labelled so, and the In / out tile
    names which pool each share is of); "failed reads 0.5, others 1.0" holds only at alpha 1 and for movers
    holding little mass (qualified); the sum over a set made the ratios differ by 4e-15 between hash seeds
    (`math.fsum`, and the weights summed in sorted order); a NaN difficulty draws nothing where
    `select.pick` would clamp it (unreachable, documented). *Frontend* (9): **"Rebuild now" was sticky**
    (every later alpha edit and hourly poll re-sent `refresh=true`, a full pool build each time; it is now
    one request, `pollPath`); an error survived the next request; the stale guard ignored alpha; an
    invalid alpha was ignored without a word (now `aria-invalid` and a message); area was proportional
    only within a band (the `fairRects` fix above); tiles are not keyboard-reachable (left: the table twin
    carries the same data, and its rows are links; **closed by item 55**); an empty pool drew a blank canvas (now a sentence); the
    test gaps (the frontend suite went from 11 tests to 20). *`record_pick_snapshot`* (5): inside a caller's transaction it silently
    committed the caller's writes (now refused with a `RuntimeError`); a deduped run left the snapshot
    stamped with the old budgets and rules (the newest snapshot's stamp is now refreshed by `COALESCE`);
    two tests passed with the code they pinned removed. *`app.py`* (7): **a committing session defeated the
    request coalescing** (6 requests, 6 serial builds -- the cache key was taken before the lock; a build
    counter now orders freshness, because Windows' monotonic clock ticks every 16 ms and could not), a
    cache hit waited behind the other pool's build (the lookup is now lock-free), `running_session` could
    name a crashed older session (only the newest session counts), and the rules fingerprint was read from
    disk where the server's pool came from loaded code (`rules_loaded()`, once per process); a NaN
    difficulty is a 500 (unreachable) and a failed build a bare 500 (left; **closed by item 55**). *The snapshot code and the
    fingerprint* (6): **the fingerprint missed code that decides who is in the pool** (`pari_plan`,
    `db.is_dead_end`, two constants, `seqfile.py`, `oeisdata.load_entry`, the b-file readers: all hashed
    now) and **depended on line endings** (a CRLF checkout read as "the rules changed"; sources are
    normalised first), and three tests did not pin what they claimed (that the pool is built once, the
    `except Exception` clause, the model pool kept apart from the PARI one). Left as they are: `oeisbot snapshot` stores
    `DEFAULT_BUDGETS` pools only and lets an exception through; a snapshot written by a *session*
    fingerprints the files on disk seconds after its pool was built, so an edit in that window would be
    stamped; the "built N min ago" text is the age at the last response, which can be an hour old; a raw
    `sqlite3` connection without foreign keys would leave orphan rows on pruning (no production path
    opens one).

    **Mutation checks** on the finished code (`data/item54/mutation/`, each worker in its own
    `OEISBOT_HOME`): **261 Python mutants, 254 killed** -- `pickmap.py` 63 of 65, `db.py` 53 of 54,
    `dashboard/app.py` 92 of 94, `attempt.py` 39 of 41, `cli.py` 7 of 7. **The seven survivors are all
    equivalent**, each for a reason that can be read off the code (the README in that folder has them):
    summing the weights ascending or descending; the scale guard of `compare` when the earlier pool has no
    mass (zero times any scale); `record_pick_snapshot` sorting rows that `pick_digest` sorts again (the
    same edit inside `pick_digest` is killed); the extra `not refresh` before `live_pool`'s lock-free
    lookup (`servable` already refuses a hit on a refresh); the default of `in_more.get`, which
    `departure_reason` only tests with `is False`; and two in the fingerprint (deleting lone CRs that no
    source contains, and normalising `inspect.getsource`, whose text is already newline-normalised). A
    mutant counts as killed only by a test that passes unmutated: 54 tests in `tests/test_attempt.py` need
    the sandbox runtimes, which the copies do not have, so they cannot kill (a mutant only they would catch
    would show as a survivor; none did). The gaps the audits found (entrants in the normalisation, the
    order of `gone`, review over attempt, the pool built once, the `except Exception` clause, the model
    pool kept apart) were closed by tests before this re-run.
    The TypeScript side (`tsmut.py`): **21 of 21 killed** by the 20 tests in
    `dashboard/test/treemap.test.ts` (`npm test`); the frontend audit's own run had killed 19 of 23, the
    survivors being the header-height condition and three near-equivalents.

    **A disclosure.** An early "writable connection" mutant of `app.py` ran a bare `db.connect()` against
    the **live** database twice, which created the two empty pick tables there. Checked afterwards: 0
    snapshot rows, 280 attempts and 12 sessions unchanged, integrity ok. It was DDL only and no backup was
    taken before it; the backup that followed (`data/oeisbot-before-pickmap.sqlite3`, `VACUUM INTO`, 5,718,016
    bytes, integrity ok, 280 attempts) therefore already holds the empty tables. Every later mutation run
    gives each worker its own `OEISBOT_HOME` so that this cannot recur.

    **The one database write.** After the backup, `oeisbot snapshot` stored **snapshot #1** of the PARI pool
    (3,357 rows, rules `af16ba7ce8d3`, the default budgets, `session_id` NULL, 11.8 s wall); nothing else
    changed, no pipeline ran, no review row was touched and nothing was submitted. The map has one
    snapshot, so until the pool next changes it compares with nothing and draws gray; the first real
    comparison is whatever the next session or `sync` does to it. The comparisons in the docs (session 12's)
    were recomputed from `data/oeisbot-before-session12.sqlite3`.

    **Tests and checks.** The full suite: **567 passed in 81 s**, and the frontend's 20 tests pass under
    `npm test`. `npm run build` rebuilt `oeisbot/dashboard/static`; `recheck_numbers.py` re-baselined (567
    tests, 46 modified and 13 untracked) and passing; `scripts/check_docs.py` 0 problems. The suite now
    takes about 100 s (81 to 165 s measured, by load; 70 s at 438 tests), so the two timing patterns in
    `tests/test_docs.py` moved from "70 s" to "100 s". Two pre-existing errors found
    on the way and corrected: this page said "438 tests" for item 49, which recorded 423, and `CLAUDE.md`
    still carried the pool counts from before item 53 (3,375 / 1,940 for 3,357 / 1,958).
    Not committed when written; committed and pushed with items 34 to 53 as `f0081d9` on 2026-10-14.
    Files: new `oeisbot/pickmap.py`, `tests/test_pickmap.py`, `dashboard/src/pickmap.tsx`,
    `dashboard/src/treemap.ts`, `dashboard/test/treemap.test.ts`; changed `oeisbot/db.py`, `attempt.py`,
    `cli.py`, `config.py`, `dashboard/app.py`, `dashboard/src/{charts,lib,main}.tsx`, `styles.css`,
    `dashboard/package.json`, `tests/test_attempt.py`, `tests/test_dashboard.py`, and the docs.

55. **The Pick map's loose ends: a snapshot after every sync, the bands too small to draw, the keyboard, and
    a pool that cannot be built (2026-10-14).** Asked what item 54 had left unfinished (the user: "Grill me
    on anything that is missing/not fully fleshed out"), the user answered seven option questions: **"Also
    after every sync (Recommended)"** for when to snapshot, **"Keep it fixed"** for the colour horizon,
    **"Add a footer chip (Recommended)"** for the bands "All bands" cannot draw, **"Make tiles focusable"**,
    **"PARI only (Recommended)"** for which pool a sync records, **"The newest snapshot's budgets
    (Recommended)"** for the budgets it records under, and **"Friendly message + retry (Recommended)"** for a
    pool that cannot be built. The same answer-set ended with "Commit and push", which landed items 34 to 54
    as `f0081d9` and **did not cover this item**: it is built on top of that commit and not committed. The
    plan is `data/item55/plan.md`, its critic `data/item55/critic.txt`. Nothing in the item touches the pool
    (what a session draws from), the pick maths, the schema or a review; the one new write is a snapshot
    after `oeisbot sync`, and no pipeline ran.

    **A snapshot after every sync.** `attempt.snapshot_after_sync(conn, log)`, which `cmd_sync` calls after
    `oeisdata.sync` on the same connection (`oeisbot sync --no-pull` too: it rebuilds the candidate table
    all the same), records the **PARI** pool through the same `record_snapshot` a session uses, with
    `session_id` NULL, so the map has something to compare with when entries change between sessions and not
    only after one. It reads the budgets of the newest PARI snapshot with `attempt.budgets_of` (the defaults
    when there is none or they do not parse; **moved from `dashboard/app.py`'s `_budgets_of`**, so the CLI and
    the dashboard cannot disagree about what "the pool as the newest snapshot saw it" means), builds the pool
    under them and stores it unless the newest snapshot already holds exactly that pool, so a sync that
    changed nothing stores nothing. **It never raises**: a sync that has pulled and parsed everything must
    not fail for the map's record, so any exception is logged as `pick snapshot not recorded: <Type>:
    <message>` and the sync's own rows stay committed (`tests/test_attempt.py` drives the real
    `oeisdata.sync` through `cmd_sync` to show it, and that a sync which raises takes no snapshot). **A pool
    whose per-sequence check failed (`keep.errors`) is refused**, with the count and the first error in the
    log: those sequences would be missing for a reason that has nothing to do with them, and the next
    snapshot would show them as arrivals. A session still records such a pool, since it drew from it.
    **What it costs:** 5.4 to 5.8 s per call, timed on a `VACUUM INTO` copy of the live database with the
    real 3,357-candidate pool (`data/item55/time_snapshot.py`: 5.79 s and 5.45 s in its last run); both
    calls found the pool unchanged, so the figure is the pool build and the digest, and a store adds one
    transaction of about 3,400 rows that was not timed on its own. Two things the dedupe does not do, both
    found by the critic and left as notes: it compares only the **newest** snapshot, so a pool that flips
    A, B, A stores each time (acceptable: the map colours by the newest *different* snapshot, so only the
    newest two ever matter), and with 30 kept, many such syncs would push an older baseline out. The rules
    fingerprint recorded is that of the code on disk, which is what just built the pool, and may differ from
    the code a running dashboard loaded. A snapshot with a NULL `session_id` is a CLI or sync snapshot: the
    tile's sub-label omits the session (`pickmap.tsx`), `_departures` compares on `taken_at` alone, and
    `tests/test_pickmap.py` drives a NULL-session baseline through the endpoint. **Not done, by decision:**
    the model pool is not recorded by a sync (about 30 s to build; its map stays gray until a `--model`
    session), and there is no `--no-snapshot` flag. The live database was **not** written by any of this.

    **Bands too small to draw.** In "All bands", band 8 (2 sequences, 0.002% of the picks) is allotted less
    than a pixel and band 7 is a sliver at most widths, so a tile there can be neither seen nor pointed at.
    The critic showed the first definition (the band's rect, under 8 px) would flicker on resize and miss a
    band whose inner area was 4 px, so `treemap.undrawn(layout, minSide)` is defined on the **inner** rect,
    what the leaves actually get, with `MIN_DRAWN_SIDE` = 6 px; a band with no area counts. A line under
    the map ("Too small to draw here:") lists them as buttons that open the band's tab and put the keyboard
    focus on it. The area maths is not touched. **Measured** with the page's own `layoutGroups` call on the
    real PARI pool at 32 widths from 360 to 1,600 px (`data/item55/inner_sizes.ts`): band 8 has no inner
    width at any of them and band 7 has 0 to 5.1 px at 30 of the 32 (8.2 px at 1,240 and 11.4 at 1,440), so
    the line is normally there. A band's own tab never has it.

    **Keyboard.** Every tile can be reached and used without the mouse: one tab stop, the arrow keys move to
    the nearest tile in that direction (`treemap.neighbour`: the gap along the axis plus **twice** the miss
    across it, then the closer centre, then the smaller A-number), Home and End go to the ends of the layout,
    Enter or Space opens the entry (a lump opens its band), Escape closes the tooltip, and a tile focused by
    the keyboard shows the same tooltip as a hovered one. The SVG changes from `role="img"` to `"group"`
    (an `img` cannot have focusable children); a sequence tile is a `link`, a lump a `button`, each with an
    `aria-label`. `treemap.focusOrder` lists what the keys can reach: not the leaves of a band in the
    "too small" line, not a tile with no area, and not a lump on a band's own tab. **Three design points from
    the critic:** (1) a tab stop held in React state would re-render all ~2,300 tiles on every key press, so
    each leaf is one memoised `LeafTile` and a change of stop renders two; (2) the tooltip now has one owner
    (`Shown {tip, by}`): the mouse leaving does not close a tooltip the keyboard opened, blur does not close
    one the mouse opened, and a new layout shows the tooltip of the tile that has keyboard focus
    (`showFor`, which requires `:focus-visible`) and closes it otherwise; (3) Space calls `preventDefault`,
    or the page scrolls, and a key held down acts once (`e.repeat`).
    **Not checked in a browser** (see below): `:focus-visible` on SVG elements, the tab order on a real
    page, and what a screen reader makes of 2,300 labelled links are exactly what the node tests cannot
    reach, because node cannot run `.tsx`, and `pickmap.tsx` has no automated test of its own.

    **A pool that cannot be built.** `pickmap_data` guards only the call to `live_pool`: a missing database
    keeps FastAPI's own 503 (`except HTTPException: raise`, the critic's second finding), and **any other
    exception** is logged with its traceback to the `oeisbot.dashboard` logger and answered as a **503 with
    `{"error": "pool_build_failed", "reason": "<Type>: <message>"}`**, the message on one line and cut at
    200 characters. Nothing is cached for it, so the next request builds again
    (`test_a_failed_build_is_not_cached_so_the_next_request_tries_again`). The page reads the reason out of
    the error text `useApi` keeps, which is **`Error: 503: {...}`** and not `503: {...}` (the critic's first
    finding: the plan's test input had the wrong shape and would have passed while the UI always fell
    through), with `treemap.failureReason`, and shows "The PARI pool could not be built: <reason>" above the
    last map that loaded, with a **Try again** button that asks for a rebuild. Any other failure reads
    "Could not load: ..." with the same button. The map is dimmed only while a request is out (`stale` used
    to survive a failed request, leaving the message over a permanently 60% map), and `aria-busy` follows
    `loading`. The traceback reaches the terminal of `oeisbot dashboard`: uvicorn's logging configuration
    touches only its own three loggers, so Python's last-resort handler prints this one (checked).

    **The colour horizon is unchanged**, by the user's choice: the change since the newest *different*
    snapshot, no picker. [known limitations](known-limitations.md#the-pick-map) has the note.

    **The plan was criticised first, then every claim was checked.** 13 findings, all accepted (the
    response is at the foot of `critic.txt`): two bugs in the plan (the `Error: ` prefix, the
    `HTTPException`), the failed-check snapshot, the resize flicker of the first `undrawn`, the re-render
    cost of the tab stop, the tooltip contest, the sticky `stale`, a sync test that would have run on an
    empty pool and so proved nothing, and the text-matching mutation specs of item 54 that the move of
    `_budgets_of` made stale (they are rewritten in `data/item55/mutation/pymut_specs.py`).

    **Mutation checks** (`data/item55/mutation/`, each worker in its own `OEISBOT_HOME`, the lesson of item
    54's disclosure): **Python 45 mutants, none survived** (`attempt.py` 22, `cli.py` 4, `dashboard/app.py`
    19), **TypeScript 71 killed of 71**. They found real gaps, closed by tests before the final runs: the
    sync took the newest snapshot's budgets and nothing proved it was not the oldest's; the
    failed-checks count was indistinguishable from the pool size; only a `RuntimeError` was tested as a
    build failure (now OSError, `sqlite3.OperationalError`, KeyError and ValueError too); and the TypeScript
    suite grew until every one of its 71 was caught. Three TypeScript mutants and one in `cmd_sync` are
    **equivalent** and left out, each with its reason as a comment in the spec files (the source's own
    centre is never beyond itself; ids are unique; `JSON.parse("null")` throws into the same `catch`; and
    moving the snapshot out of `cmd_sync`'s `with` changes nothing because `with` on a sqlite3 connection
    commits and does not close). A worker copy needs stub runtime files (`tools/python/python.exe`,
    `tools/pari/gp.exe`, `data/scratch/`) or `tests/test_attempt.py` is skipped and every mutant survives
    for the wrong reason, which is how the first run of the `attempt` suite looked; in the `cli` suite 35
    sandbox tests fail identically on the baseline copy and on every mutant, and are diffed out.

    **Tests and checks.** **20 new Python tests** (587 collected, from 567: 11 in `tests/test_attempt.py`,
    9 in `tests/test_pickmap.py`, four of them one parametrized test) and **13 new node tests** (33, from
    20). `npm run build` (strict `tsc` and `vite build`) is clean. Counts were taken from `pytest
    --collect-only` and the docs edited to match; `tests/test_docs.py` and `data/item49/recheck_numbers.py`
    (a read-only checker, re-baselined to 587) then confirm them.

    **Audit.** An independent audit of the finished item (`data/item55/audits.txt`, 8 findings, the
    disposition of each written beneath the report) led to changes in `pickmap.tsx`, `styles.css` and the
    `snapshot` help text. **Fixed:** (1) **Try again** lost the keyboard focus, because the failure block
    unmounts while its button has it, so it now hands the focus to **Rebuild now**, and both buttons are
    `aria-disabled` and not `disabled` while a request is out (a focused button is never disabled under the
    keyboard); (2) a resize or the hourly refresh wiped the tooltip of the tile the keyboard was on, and the
    pointer crossing a band header wiped it too, so the layout effect now shows it again (`showFor`) and
    `onMove` ends only a tooltip the pointer owns; (5) a held Enter opened a tab per key repeat
    (`e.repeat`). **Documented and not changed:** the dropped-focus case in (2), the React code having no
    automated test (4), Shift with an arrow or Enter and Space on a link tile (5), the budgets of `oeisbot
    snapshot` following whoever wrote last (6), a sync-made snapshot keeping `session_id` NULL when a
    session later draws the same pool (7); finding 8 (a corrupt budgets row) was ignored; the stale docs of
    (3) were rewritten. **A second reader then checked those fixes** and found one regression of mine:
    Escape stopped sticking, since a re-layout showed again the tooltip Escape had closed. Fixed with a
    `dismissed` ref, cleared when the focus next lands on a tile. Three of its smaller points need a browser
    and stay in [known limitations](known-limitations.md#the-pick-map). **Neither the audit's fixes nor this
    one has a mutation check or a test of its own**, because they live in the React component: they were
    verified by `tsc`, `vite build`, the 33 node tests (which cover only the pure functions) and by reading
    the code twice.

    **Not done, and why.** **No browser pass.** The dashboard server was killed under memory pressure and
    was not restarted without being asked, so the keyboard focus ring and tooltip, the "Too small to draw
    here" chips, the failure message and the retry button have been read and tested in pieces but **never
    seen**; the user is to be asked before the server is started. The model pool is not recorded by a sync.
    `oeisbot snapshot` still stores `DEFAULT_BUDGETS` pools only and lets an exception through (item 54's
    note, unchanged). A running dashboard needs a restart to pick up the new endpoint behaviour, and
    `npm run build` rebuilds `oeisbot/dashboard/static`, which is not committed.
    Files: changed `oeisbot/attempt.py`, `cli.py`, `dashboard/app.py`, `dashboard/src/{pickmap.tsx,
    treemap.ts,styles.css}`, `dashboard/test/treemap.test.ts`, `tests/test_attempt.py`,
    `tests/test_pickmap.py`, and the docs; no new tracked file. Not committed.

## Open offers and next steps

**No offer waits for an answer (2026-09-30).** Offer (b), recording the gp version, was **taken** —
built as history item 43. Offer (a) was **recounted and decided on 2026-09-30** (history item 51): the
number was **45 un-retired sequences at the run's budgets, 34 at `queue`'s, none re-attempted**, and
the user chose the **backfill** of `program_sha` (46 of 47 rows map to exactly one current candidate),
scheduled after session 12 because it changes the pool and so the draw; see item 52 for whether it has
run. The paragraph below is the offer as it stood.

**Built 2026-10-14, uncommitted: history item 55, the Pick map's loose ends.** What it left is two things,
neither a decision: **a browser pass** and **its own request to commit**. **The browser pass was done on
2026-11-17** (the user: "start the server and do the browser pass"), in Chrome against
`oeisbot dashboard` on 127.0.0.1:8765, PARI pool, 3,357 candidates, no console errors: Tab enters the map
with a visible focus ring and the tooltip, the arrow keys move the ring, Enter on a tile opens its oeis.org
entry and Enter on a lump opens its band with focus on the first tile; the "Too small to draw here" row
lists `8 to 16` and `16 and up` and a chip opens its band; the failure message, with the last map kept
below it, and **Try again** were seen with the 503 **simulated in the page** (`fetch` replaced for
`/api/pickmap`), so the server's own 503 path has still only its automated test. Seen and left alone: a
long name is cut mid-word in the tooltip and the `aria-label` ("... the repunit (A00227"). The first `oeisbot sync` after this lands will store
the second PARI snapshot if the pool changed, and from then on the map is coloured; until then it is gray.

**(a) The 35 sequences item 41 un-retired.** Changing the predicate driver changed every predicate
program's `program_sha`, which is what `db.is_dead_end` keys on, so all 49 past predicate records are
orphaned and `oeisbot queue` went from 3,464 candidates (73 `all_programs_dead_ends`) to 3,497 (38).
Those 35 will be re-attempted and will mostly re-derive the same `verify_timeout` verdict. **Options:**
accept it (a one-off cost of roughly half an hour of machine time, spread out, and the verdicts do get
re-derived against the current driver); or backfill the 49 rows' `program_sha` to the value the current
driver produces, which is a live-database write — with a `VACUUM INTO` backup first, as every other
database change in this project has had — asserting that the old verdicts still apply to the new
program. That assertion is sound for `verify_timeout` (the scan range is identical and the driver is
only slower) and weaker for the rest. Recommended: accept, unless a long session is imminent.
**The counts in this offer are item 41's epoch (2026-09-23) and are stale**: `all_programs_dead_ends`
at the default budgets has since gone 38 → 78 (session 10) → 94 (session 11), and sessions 10 and 11 will
have re-attempted some of the 35 already. Before deciding, re-derive how many of the 49 orphaned
predicate records still have no attempt under the current driver's `program_sha` — the number to decide
on is that, not 35.

**~~(b) Record the gp version.~~ Done 2026-09-23 as history item 43** — the user: "Yes, one meta row",
then "Yes, short token in the note". `gp_version` and `sandbox_python_version` are written to `meta` by
`oeisbot setup` and refreshed at every `oeisbot run`, and each session's `note` carries a short
`gp=2.17.4/GMP-6.1.2` token, which is the half that survives a gp upgrade. See
[data and schema](data-and-schema.md#meta) and [known limitations](known-limitations.md#runtime-provenance).

Two related findings from item 41's audit were deferred *with the critic's agreement* and need no
decision: `oeisbot_blk /= 2` staying exact division rather than GP's integer division (the invariant is
written down, and a fraction would make the line unparseable, so the failure mode is "no frontier"
rather than a wrong one), and applying the `k - start + 1 == tested` identity to `@T` lines as well —
whose natural home was the resume item, now decided against (item 42), so it needs a home of its own if
it is ever wanted.

**This list has been renumbered several times, so cite items by name, not by number.** References
elsewhere in this page to "next step N" mean the numbering *at the time that text was written*; each one
names the item it refers to, which is the durable identifier. Done and struck from the list below: the
`--verify-s 60` pass (session 8, item 38, 2026-09-21), the cost fit's statistics (item 36) and the guards
that keep its documentation honest (item 37), the `--verify-s 600` pass (session 7, item 35, whose
results reordered the list completely), the `incomplete` stop that recorded no cause and the static check
for PARI blocks calling another entry's helper (items 32 and 33, 2026-09-20), and the bundle of smaller
follow-ups (item 34, the same day).

**Session 8 reordered the list again:** its audit turned up the searched-bound comments, which go
straight in at 1, and the `--verify-s 60` question it was run to settle is now closed.

**Session 9 measured item 1 rather than building it** (history item 39). The item stays at 1, but it is
now a *decision* with a costed design behind it, not an open question — and it is much smaller than
session 8's audit implied. Two things it turned up belong to other items on this list: item 6's
observation that the gp memory projection compares different quantities has a sibling — the *rate*
constant `PREDICATE_MAX_RATE` is thousands of times the median measured rate (12,687x on 52 logs in
September 2026, **15,244x on 83 logs after session 10**; see item 39 for why this figure must always
carry its date, population and definition), so anything reasoning with it is
reasoning about a machine that does not exist; and item 10's "risk flags are not wired to anything" now
has a concrete candidate for something they could be wired to.

**Item 36 leaves one small follow-up of its own:** the dashboard reads only `predictions.trustworthy`, so
its "trusted projections only" filter treats a sound cost fit withdrawn by the rate drift as untrusted.
Showing `fit_trustworthy` there means `dashboard/src/views.tsx`, `oeisbot/dashboard/app.py` and an
`npm run build` (output not committed). Left out deliberately (the user, 2026-09-21: "Leave it, note it").

**One thing is waiting on the user, and it is not a code change.** A385331 has an open `reviews` row
(status `new`) for 18 new terms. **The checkable part of the review is done** (item 44, 2026-09-23):
steps 2-7 of the [checklist](operations.md#reviewing-a-result) including step 6, whose independent check
confirmed all 18 new terms by a method that shares no arithmetic with the entry's program. **Step 7 was
re-run on 2026-09-28** (item 49) through `attempt.recheck`, the pipeline's own path rather than a
hand-rolled check: the live entry still ends at a(24), keyword `more` is present, and all 24 published
terms agree with the run. What is left is what only a human may do — **step 8, submitting by hand, and
step 9, recording the outcome** — and the material for step 8 is assembled in
`data/review1/SUBMISSION.md`. The review row was deliberately left at `new` rather than `reviewing`: it
is the user's workflow marker.

OEIS policy is no bulk or automated submissions and no programs you do not understand, so read
`program.gp` yourself before submitting; the one-line explanation is in item 44 and the artifact's
README lists the checks. Until the row is closed the sequence is blocked from every future session by
`select.candidates`, which is correct — but it also means the decision cannot be deferred indefinitely
without quietly costing a candidate. It is **not** a dead end (`is_dead_end` needs `new_terms = 0`), so
once the review is closed it would be re-run from a(1), and at `--extend-s >= ~1,950 s` the a(43)
projection becomes feasible — though `a(43) > 2x10^8` is now confirmed by two independent methods, so
that run would be a long one.

**Session 10 (item 45) added three items, and they go near the top.** They are listed here rather than
renumbered into the list below, which has been renumbered too often already:

- **~~(i) Decide what to do about the two conjectural false wins, reviews #2 and #3~~ — done 2026-09-28
  as history item 49**, by the user ("Tackle reviews 1-3"). Both rows are `rejected`, each with a note
  recording that the entry's own program is conjectural. Item 47 had removed the trap that made this
  expensive; **the draw was then measured, before and after, and is unchanged**: the non-model pool
  stayed at **3,438** and A162762, A162763 and A162764 are all absent, while **A162761, the one proved
  sibling, stays in**. **It was not free, though** — item 49's audit found that a `new` review also
  gates `attempt_sequence`, so a targeted `oeisbot attempt A162762 --model` now runs where it used to
  skip; that is next-step (v) below, and the reason "cost nothing" does not appear here.
  **One paragraph that stood here was stale and is corrected**: it said that under `oeisbot run --model`
  the check removes nothing, because `Runnable._why_not` keeps any PARI-bearing sequence whatever the
  PARI verdict. **Item 48 falsified that two days before this list was read**, and the same wrong claim
  was in `CLAUDE.md` beside a correct description of item 48. `_why_not` returns `conjectural_program`
  with the model on too, measured here at **7 sequences left out, against a 26,747 pool**, so neither
  sequence returns to a model session's draw either. (Item 48 recorded this as "5 of 26,752" and was
  right then: A162762 and A162764 were still excluded earlier as open reviews and never reached the
  gate to be counted. Same check, two epochs — do not read the two figures as a disagreement.) The lesson is the one item 43 already recorded: a number or a claim
  is stale the moment the thing it describes changes again — **re-derive it, do not carry it forward.**
- **~~(v) A `rejected` review no longer guards its sequence, and a new review can be opened for a false
  win that was already rejected~~ — done 2026-09-30 as history item 51**, the user choosing the
  `_insert_review` refusal: `db.ReviewRefused`, caught inside `record_win`'s transaction, the win keeps
  its `extended` row and artifact, the inbox stays empty, and reopening the old row lifts it. As it
  stood: found by item 49's audit, immediately after that item created the
  situation. Two facts: `attempt_sequence` skips only on `db.open_review`, so with reviews #2 and #3
  `rejected` a targeted `oeisbot attempt A162762 --model` runs the model where it used to skip; and
  `db._insert_review` has no check against a prior `rejected` row, so that run could open review #4 for
  the same conjectural values session 10 already produced twice. **The random draw is not affected** —
  both pools were measured unchanged — so this needs a deliberate command to reach.
  **The obvious fix is the forbidden one:** gating `attempt_sequence` on the conjectural check is
  exactly the asymmetry item 48 records as deliberate and says not to "fix", because being able to run
  one on purpose is what made item 48 cheap. **Two alternatives that do not touch it:** have
  `db._insert_review` refuse (or flag) a second review for an A-number with a `rejected` one, which
  guards the *output* rather than the run and costs nothing anyone wants; or leave it and rely on the
  reviewer, since such a row would arrive with the same `%F` evidence that got the first two rejected.
  Recommended: the `_insert_review` guard, as a small item with its own test. **Not urgent** — it takes
  a deliberate `--model` attempt on one of 7 flagged sequences, and no session since 4 has used
  `--model` at all.
- **~~(iv) The `--model` half of the conjectural class~~ — the pool half is done 2026-09-26 as history
  item 48**, the user choosing it over three alternatives. `Runnable._why_not` now returns
  `conjectural_program` with the model on too, so a flagged sequence is not drawn into a `--model`
  session. **The one piece that remained open was closed 2026-09-30 (item 51)**: the flagged block is
  now quoted under `codegen.CONJECTURAL_PROGRAMS_NOTE` with the author's own word, the auditor's
  alternative, reversing the section-4 decision as the user chose. As it stood:
  - **The prompt still states the conjecture**, for a sequence reached some other way (a targeted
    attempt, or a future change). `codegen._context` no longer lists a flagged program under "Existing
    programs (correct, possibly slow)", but it still quotes `entry.comments[:8]` and
    `entry.formulas[:8]`, where A162763 (3 lines), A162764 (2) and **A162762** (an "Empirical g.f." plus
    a recurrence "with equality for all known terms") state it outright. **The auditor's alternative is
    strictly better on both axes and was not taken only because it reverses a section-4 decision:**
    quote the flagged block under an honest header ("the author calls this one conjectural or heuristic;
    do not assume it is correct") instead of dropping it. That keeps the algorithm, removes the false
    claim, and removes the `progs[:4]` interaction. Filtering `%C`/`%F` instead is *not* the fix —
    reading those to reject would have falsely flagged A162761, the proved sibling.

  **Much less urgent now** that the draw is blocked: reaching a flagged sequence with the model takes a
  deliberate `oeisbot attempt A... --model`, and no session since 4 has used `--model` at all.
- **~~(ii) A static check for conjectural programs~~ — done 2026-09-26 as history item 47.** Built at
  the recommended width, `conjectur*|heuristic*|unproved|unproven|not proved`, matched in comments and
  strings but never in live code, on the raw `%o` part text. The premise needed two corrections on the
  way: session 10's "precision is the problem" was **wrong at this width** — 7 of 7 corpus hits are
  true positives, and A213062's "upper bound" false positive only exists in the *wider* list that was
  measured and rejected — and the "six other programs" with scope caveats are **not one class**, most
  being performance caveats the gate already handles correctly (taxonomy in
  [known limitations](known-limitations.md#strategies)). The class it cannot see at all is a program
  that is conjectural and says so nowhere.
- **~~(iii) Two program-selection defects~~ — done 2026-09-25 as history item 46**, and they were not
  two: the scan found **32 blocks discarding a usable loop (17 unreproducible) and 24 needing a second
  argument, 38 sequences in all**. A `%o` block now offers both its function form and its own loop, and
  `pari._drivable` refuses a def the drivers would call with a missing argument. A330204 and A366832 are
  both back in the pool. The A309533 rational-type instance is untouched and remains item 7 below.

  **Two things item 46 deliberately did not do, and why:**
  - **The `_ANAME_USE` widening and the `_DEF`/`_DEFINES` nested-paren fix (item 5 below) were dropped
    from the bundle.** The widening is measured at **one block in today's pool** (A394893), and its
    stated blocker A122172 is **not in the pool**, so it is free but nearly worthless right now. The
    paren fix is the expensive half: a nested-paren-tolerant `_DEF` reclassifies **40 statements in 36
    blocks over 36 sequences** from `call` to `def`, several of which would start running programs never
    run before — a new strategy surface needing its own evidence, not a rider. A2b did not need it.
  - **Wrapping the `on_line` call site in both sandbox backends** is its own item: it creates a new
    sandbox guarantee, which needs an attacking test and a `docs/sandbox.md` entry, and a decision about
    what status a callback exception maps to — if it landed in `db.DETERMINISTIC_FAILURES` a *harness*
    bug would permanently retire a program. `posix.py` cannot be exercised on this machine.

- **(iii-original) Two program-selection defects, each of which wrongly retired a sequence forever.** Both are
  the same shape — `pari.build_candidates` keeps the `def` and **discards the entry's own loop**,
  along with the domain or the constant that loop supplies — and neither is in
  [known limitations](known-limitations.md):
  - **A330204** (#227, `wrong_term`): the block is `isok(k) = ...` plus
    **`forcomposite (k=1, 10000, ...)`**, and the sequence is *composite* numbers. The predicate
    driver scans every k from 1 and emits k=1 against a known a(1) = 4. A correct print-loop sat in
    the same block and was never built, because the predicate branch precedes it and only one
    candidate is made per block.
  - **A366832** (#223, `incomplete`): `isok(k, b)` with the entry's loop supplying `b = 9`. The
    builder accepts any def with `len(params) >= 1`; the driver calls `isok(k)` and `b` is unbound,
    giving "domain error in digits: abs(B) < 2".

  That is 2 of session 10's 40 retirements (5%) lost to a selection defect rather than to anything
  about the sequence. A third, **A309533** (`(144^n+1)/145` → t_FRAC), is a fresh instance of the
  already-documented limitation that is item 7 below.

**Session 11 (item 50) adds two items and extends items 5 and 7 below.** All four are program-selection
misreads found by reading every pick's program before the run; each cost a pick and retired a sequence
that was never actually tested. None is a rider on an existing item — each needs the measurement item 46's
did (how many pool blocks have the shape, how many are misreads) before it is worth a check:

- **(vi) A predicate-shaped def beside a list printer is probably a helper.** A335304's block defines
  `is(n)` (commented `\\ A054735`) and `lista(nn)`, which is the sequence's real algorithm; the builder
  took `is(n)` and the first emitted term was 8 against a(1) = 2. A static rule — "a block that defines
  both a one-argument def and a `lista`/`first`-style printer yields no predicate" — would have skipped it
  as `no_supported_program`, which is the right outcome. Unmeasured: how many pool blocks have that shape,
  and how many of *their* predicates are the real one. Recommended: measure, then decide.
  **Measured 2026-09-30 (item 51, `data/measure0930/shapes.txt`): 235 blocks define a drivable
  predicate beside another def (133 in the pool), 15 of them a list printer.** Which predicates are the
  real one still needs reading; the 15 are the first sample. **Decision owed** once read.
- **(vii) A print loop that starts above the offset shifts every index.** A290024's `for(n=1, 7, ...)`
  prints a(1) onward while `%O` is 0; the emitter numbers from `known.first_index` (`pari.py:466, 613`),
  so a correct program ended `wrong_term` at index 1 and is retired under this sha. Two fixes, neither
  free: number from the loop variable's start when the loop is `for(v=START, ...)` and the printed value
  is not `v` itself (a rewrite that changes indices, so it must be flagged like every other rewrite); or
  refuse the print-loop form when `START != offset` (loses the rewrite for every entry whose loop starts
  at 1 with offset 0 — common). `strategies.md` now states the failure mode; a decision for the user.
  **Measured 2026-09-30 (item 51, `data/measure0930/shapes.txt`)**: of 108 index loops (emit on every
  iteration) **26 start away from the offset**; of 921 filter loops **20 start above the first known
  value** (A215906's shape, which session 12 then hit); **47 candidates listed, 44 in the pool**. The
  user chose "measure first", then, with the numbers, **refusal over renumbering — built the same
  evening as history item 53** (`pari.loop_start_problem`): index loops off the offset and filter loops
  printing their variable above the first term are refused; 32 candidates in 30 sequences went.

Suggested next steps, roughly by value:

1. **(Done 2026-09-22, history item 40.)** The post-verification searched-bound check is built and
   verified end to end on A194099 (8.0 s where session 8 spent 52.9 s). What it *leaves*, roughly by
   value:

   - **~~Resuming a scan~~ — decided against 2026-09-23 (item 42), by the user, after the evidence and
     a critic's 31 findings.** Do not re-open it without new evidence; the full argument is in item 42.
     In short: the 21,002 s prize is retrospective (**no attempt row carries a frontier**, and 0 of 13
     sequences has a sha today's driver reproduces), resume **saves no machine time** against a larger
     `--extend-s` and costs 2× on a find, and the design breaks
     [invariant 10](development.md#invariants) — `_bound_exhausted` is reachable only from the
     `n == known.last_index` branch a resumed run never reaches, so it would scan straight past a
     published bound — while having no termination rule and being damped geometrically by the selection
     failure penalty. **The replacement is a targeted `oeisbot attempt A… --extend-s`**, which nothing
     blocks: A279795 needs ~1,900 s and A015766 ~9,817 s to pass their published bounds. Still worth
     doing if the frontier is ever wanted: spend it as a **rate estimate** for `_bound_exhausted`
     instead of as a resume point (item 42's "left on the table").
   - **Fix the extractor's remaining recall gaps. Measured as near-empty (item 41) — deprioritised.**
     Of the 767 predicate candidates with no applicable bound, 253 have no `%C` lines, 122 are stale and
     8 wrong-index (correct rejections), leaving 384 where recall could matter; the documented gap
     shapes reach about 18 of them and most are index or exponent limits, not value bounds — the
     A088783 false-positive class. Measured recall is about **85%**. Still missed:
     number words beyond million/billion/trillion, `Checked up to X`, `the only terms known up to X`,
     `none was found up to X`, and primorial or factorial notation (`no other terms found up to 23#`).
     1,135 pool entries have `%C` lines no sampling frame has covered, so that 85% is an upper bound on
     what is *known* to be missing.
   - **~~Use a bound for `estimate._bits_bound`~~ — dropped 2026-09-23 (item 41), premise false.**
     `next_bits_high` feeds nothing: no column in `predictions`, no reader in the repo, and its only
     consumer `Assessment.exceeds_int64` cannot fire because both runtimes are arbitrary-precision. A
     searched bound is also a *lower* bound on a(n) where `_bits_bound` returns a *high* estimate. The
     reach is real (1,443 of 3,450 carry an applicable bound) and inert: 318 would change the number, 31
     flip `exceeds_int64`, nothing reads it. Revisit only if something ever consumes a size bound.
   - **~~Flag a term that lands below a published bound~~ — done 2026-09-30 (item 51):**
     `Harness.below_bound`, `extra.below_published_bound`, a console warning, a README note and a
     dashboard warning; driven synthetically in `tests/test_bounds.py`, since no real case exists. As it stood:
     a run that emits a new term *inside* a range a human said was empty is worth surfacing to the
     reviewer — the safe direction of the "never evidence a term is correct" rule.
   - **Whether to retire a skipped program after all.** Deliberately not done, on the user's
     instruction. The measured cost: 8 of the 10 historical firings ended at `extend_budget`, which
     retires them permanently at that budget; they now stay in the pool and pay verification on every
     future pick, damped but not stopped by the selection failure penalty.

2. **(Done 2026-09-21, session 8 / history item 38.)** Go back to `--verify-s 60`. Confirmed at
   **8.96 picks/h against session 7's 4.78, 1.88x**, with 83% of the gain attributable to the gate
   itself. 60 s is the gate to run; the question is settled and needs no further session to re-measure.
3. **(Done 2026-09-21, history item 36.)** Record the cost fit's own statistics in `predictions`.
   Five columns and a backfill of all 40 rows. The whole history is 6 trustworthy fits in 18 fitted
   projections; the audit's miss, A229209's prediction #18, is now a row a query finds. The item's own
   premise needed correcting on the way — see the history item.
4. **Value-dependence detection, but measure both directions first.** `_value_dependent_by_data`
   (`estimate.py:258`) is fed the **noise-floored** points and needs 6 of them, so on A385331 it saw 5
   and said no; the same test on the 12 positive-cost points says **yes** (r^2 0.146 by n, 0.865 by
   value). `name_suggests_search` (`estimate.py:219`) needs a `such that`/`for which` connective and so
   misses "smallest prime **factor of** ...", with ~160 such names in the 600 s PARI pool. **But the
   honest counterfactual on A385331 is that firing it would have gained nothing and cost 1,068 s**, and
   `value_dependent` also multiplies `select.difficulty` by 1.5, which would have cut A385331's own pick
   weight by 33% and changed the draw that produced the win. Worth doing; worth evidence first.
   **Measured 2026-09-30 (item 51, `data/measure0930/valuedep.txt`)**: over the 39 attempts with
   replayable projections, every widening (positive-cost points, a 4-point threshold, the wider name
   test, both) changes the outcome of **exactly one run, A385331 — +1,068 s and no term gained or
   lost**; the other flips are `extend_budget` runs, unchanged. The wider name test newly flags 9 pool
   sequences (0.17% of the draw → 0.11%). **Recommendation: leave it**; nothing on the record gains.
5. **(Done 2026-09-30, history item 51 — both halves, with item 46's `_DEF` fix first.)** `_ANAME_USE`
   captures the whole identifier and `undefined_a_numbers` compares it; definitions are read with
   balanced parentheses. Measured as a candidate diff: 40 statements reclassified, 31 sequences gain a
   candidate, 12 lose one (all genuine helpers). As it stood: **`pari._ANAME_USE` misses suffixed
   A-names.** It needs `[Aa]\d{4,7}` followed immediately by `(` or
   `[`, so `a375301_row(n)` slips through — one wasted pick in session 7 (A375302, whose block even says
   `\\ uses function a375301_row from A375301`). Widening to `[Aa]\d{4,7}\w*` and checking the full name
   against the existing `defined` set newly flags **five** blocks: A122172, A375302, A378164, A378166,
   A394893. Only **one of them is still in the pool** (A394893) — A375302 retired itself as a dead end in
   session 7, and the other two are already `no_supported_program` — so the change buys one pool sequence,
   not two. **It is not free:** A122172 would be a false positive, because its block *defines*
   `A122172_row(n, p=part(n))={...}` itself and `_DEFINES` misses that through the nested parentheses in
   the default argument. So the widening needs `_DEFINES` fixed first, or it trades one wasted pick for
   another. A368129's `BijectionD` (helpers in linked `.txt` files) needs the general "called but never
   bound and not a gp built-in" rule instead.
   **Session 11 added the *prefix* case (item 50): A274003's `is_A274003(n)={is_A178751(n) && ...}`**,
   where `is_A178751` lives in A178751's entry — one wasted pick, `incomplete` at 0.0 s, and the sequence
   retired. The `\b` before `[Aa]` is what misses it (`_` is a word character), so the `\w*` suffix
   widening above does not reach it, and **dropping the `\b` with the capture group left on the A-number
   is wrong**: it would also flag `A274003` in its own definition and `A034293` in `is_A034293(n)=...`,
   rejecting a program that verified in session 11, because `_defined_names` holds `is_A034293`, not
   `A034293`. The check would have to capture the whole identifier (`\b(\w*[Aa]\d{4,7}\w*)`) and compare
   *that* against the defined names — a design change with its own false-positive measurement, not a
   re-run of the old one (`data/session11/checkaudit.txt`, F6).
6. **(Done 2026-09-30, history item 51: `Harness.stack_cap`.)** A gp run's stack figure is now judged
   against the `parisizemax` it is launched with; the job cap stays for Python; what gp allocates
   outside the stack is still invisible (`known-limitations.md`). As it stood: **For gp, the memory
   projection compares different quantities, so no gp run can ever be judged
   infeasible on memory.** `estimate.assess` is fed `TermRecord.mem` — gp's *stack* figure, 8,001,936 B
   on every one of attempt #139's 42 terms — and compares it against the 6 GiB **job commit** cap, which
   is ~805x larger. A277041 died at `memory_cap` on the job cap while reporting 8 MiB throughout, so the
   projection saw nothing coming. Not introduced by item 34, and not currently documented as a
   limitation.
7. **Two candidate shapes that can never verify and have no static check** (one wasted pick each,
   forever): `a368129(rmax=235)` is a bulk printer whose parameter is a radius bound, not an index, and
   `_is_a_name` accepts any `a<digits>` name; and A231865's `is(n)=ispseudoprime((43^n+1)/44)` is correct
   only on odd n, while the generic predicate driver calls it for every k. Wrapping the predicate in
   `iferr` would fix the second but risks turning a genuinely broken program into one that "verifies" by
   swallowing errors — a decision for the user, not a recommendation.
   **A373945 (session 11, item 50) is a second instance of the bulk-printer shape**, `a373945(upto=10^8)`,
   with a mechanism the first did not show: its own `print1(0,", ",1,", ")` writes to stdout without a
   newline, so the driver's `@T` lands on the same line and `verify.on_line` ignores it (a line must
   *start* with `@`), and the run is a plain `verify_timeout` with no record — nothing in the row says
   the program was misread. A def whose only parameter has a default (`upto=...`, `rmax=...`) is a
   candidate signal for this shape; unmeasured.
   **Measured 2026-09-30 (item 51)**: **4 defs** whose only parameter has a default (A368124, A368129,
   A373945, A375093), **all four bulk printers**, 2 in the pool — the signal is exact on this corpus,
   so a static refusal would cost nothing today. **Refused, built 2026-09-30 as history item 53**
   (`pari._bulk_printer`). The `iferr` wrap for A231865's
   shape was **declined** by the user the same day (and session 12's A138595 then failed exactly that
   way, `isprime` on a fraction at k = 1 — a program valid only from k = 11).
8. **(Done 2026-09-20, history item 34.)** What is left of that bundle, all of it optional and none of it
   a defect: the `infeasible` dead end still cannot tell a verdict reached on *time* from one reached on
   *memory*, because the row does not record which (keying them apart needs a new `extra` field); a
   pending win whose classes have drifted still needs the manual release in
   [operations](operations.md#a-win-whose-re-check-failed-recheck_pending), and a field that keeps its
   name but changes meaning still reloads without complaint; `sequences.difficulty` is now always correct
   but still has no reader in the code; and the three design-intent mismatches that became documentation
   (1, 3 and 5) could still be built if wanted — for 1 the only version that would do anything is
   penalising *related* candidates after a failure, which nothing in the code defines yet. Also noted by
   the critic while reading, and **not part of that bundle**: `verify.on_line` computes
   `cpu_s = cpu_us / 1e6` on an integer parsed from untrusted program output, so a several-hundred-digit
   `cpu_us` would raise `OverflowError` inside the sandbox's stdout reader thread. Unverified, and worth a
   look on its own. **Looked at 2026-09-30 (item 51): already closed by item 46's 40-digit field cap,
   with `OverflowError` caught beside `ValueError` and two tests; and the reader thread is now guarded
   anyway.** The `infeasible` time-vs-memory keying in this bundle is **done** (item 51,
   `extra.infeasible_on`); the manual release for a drifted win, the `sequences.difficulty` reader and
   the three design-intent mismatches remain as written.
9. Decide on Wolfram Engine: 5,282 candidates have Mathematica but no PARI program. **Scoped
   2026-09-30 (item 51, `data/measure0930/wolfram_scoping.md`)**: what a strategy needs (a runtime the
   AppContainer can start without network, a Mathematica builder of the PARI builder's size, drivers,
   grants, tests, docs — three to five items), an honest yield expectation (lower per run than PARI's),
   and the go/no-go experiment: one afternoon to install, activate, relocate the licence and run one
   block in the container. **Decided 2026-09-30 (item 53): deferred**, the note attached; neither run nor
   struck.
10. **The estimator's risk flags are not wired to anything that stops a run.** Session 8's A194099
   produced the project's **first *optimistic* trusted projection**: a(29) projected at 22.3 s with
   `trustworthy`, `fit_trustworthy` and `feasible` all 1, against a term that is not reachable at all
   (the entry publishes `No more terms <= 2 * 10^38`). The direction matters — session 7's four wrong
   trustworthy projections were *pessimistic*, and a pessimistic projection can only stop a run early,
   whereas `feasible = 1` is exactly what keeps `infeasible` from firing. The estimator was not silent:
   it set `fit_climbing = 1` (so `Assessment.risky` was True) and recorded `rate_drift = 1.473`. Nothing
   reads those to stop a run; only `over_prediction` did, by watching reality diverge. Worth deciding
   what, if anything, `risky` should do. Related and uncomfortable: that kill survived on a
   `fit_disagreement` of 2.948 against a 3.0 trust threshold — **a 1.7% margin** — and a marginally
   worse fit would have made offer B suppress it and burn all 1,800 s (history item 38).
   **Replayed 2026-09-30 (item 51, `data/measure0930/riskflags.txt`)**: of 455 projections, 448 are
   untrusted and risky, 6 trusted and not risky, and **1 trusted and risky — A194099's**. *Withdrawing
   trust when risky* would touch only that row and undo the one kill that saved the run: harmful.
   *Arming the kill for untrusted risky projections* (2× the high estimate, 10 s grace) would have
   killed **no term that went on to finish** and cut **8 runs earlier for 4,423 s** — but the record of
   finished terms under untrusted projections is six terms wide, and the trust rule exists so an
   untrustworthy fit cannot kill a term. **Decided 2026-09-30 (item 53): leave the rules as they are.**

11. **Another 60 s PARI session, when picks are wanted — done again 2026-09-30 as session 12 (history
   item 52; 0.85 h, 2 verified, 0 new terms, Brier 0.0002 vs 0.0768) and 2026-09-29 as session 11 (item
   50), and repeatable as written in `data/session12/`.** 25 picks, 10,022 s, 5 verified, 0 new terms, 8.98
   picks/h: the rate is set by how many verified picks run their full 1,800 s (five did), not by the
   gate. Reuse `data/session11/`'s method — `progs.py` to read every pick's program, a per-pick
   probability beside the pooled rate, Brier afterwards, and a cost model that uses what the page
   proves. Sessions 5, 6, 7, 8, 10 and 11 have now run this
   configuration; session 8 settled the gate question (1.88x picks/h over 600 s, 83% of it the gate).
   **Wins come from picks, and the rate is roughly 1 in 130 runs**, so more picks per hour is the right
   strategy — but note that over 8 sessions the base rate is 1 win in 107 PARI program runs, and
   **no run that exhausted its extension has ever produced a term** (22 such runs, 27,195 s, 0 terms;
   see item 38 for the three qualifications that figure needs). The one win arrived **late** in its
   extension — all 18 terms after 454 s, the last five 0.07 s before the kill — so shortening
   `--extend-s` is *not* the implied conclusion, however tempting the 89.6%-for-nothing figure looks.

## Helper scripts

In `scripts/` (see [development](development.md#helper-scripts)):

- `model_smoke.py`: real-model check on well-known sequences, no database writes.
- `make_demo_db.py`: synthetic database for looking at the dashboard. Refuses to run without a scratch
  `OEISBOT_HOME`.
- `check_docs.py`: doc link/anchor checker plus a list of code names the docs mention.
- `replay_predictions.py`: rebuilds every stored prediction from its attempt's term log and reports any
  disagreement with the stored row; `--write` adds the cost fit's columns and backfills rows that have
  none. Read-only otherwise, and safe to re-run. A quick health check on the estimator against real
  data: it should print "reproduces the stored values for 45 of 45 replayed rows" (45 since session 8;
  item 40 added none, because the searched-bound check fires before the first projection is made).
- `verify_A385331.py`: independent re-derivation of the first win's terms from the sequence's name,
  sharing no code with the entry's PARI program. `--bound 1000000` settles 37 of 41 terms in about 13 s;
  the default 2e8 settles all 41 and bounds a(43). Reads the artifact's b-file; writes nothing.

Not in `scripts/`, because they are evidence rather than tools: **`data/session9/`** holds the five
read-only scripts behind items 39 and 40 (`reach.py`, `rates.py`, `retro.py`, `sample.py` and the
`bounds.py` prototype that became `oeisbot/bounds.py`), with a `README.md` saying how to run each. They
need `PYTHONIOENCODING=utf-8` on a cp1252 console, because OEIS comments carry non-ASCII author names.

**`data/item49/recheck_numbers.py` is the one to run at the end of a session that touches counts.** It
checks about thirty documented numbers against the database, the disk, `git status` and the live `queue`
lines, and exits non-zero on any mismatch — the numbers `tests/test_docs.py` does *not* guard, which is
where item 49's audit found a week of drift. Its siblings in that folder are `pool_check.py` (both pools
through the real `select.candidates`), `gate_check.py`, `step7.py` (a review's step 7 through
`attempt.recheck`), `check_bfile.py` (a b-file against every SubmitB.html rule) and `build_package.py`.
It is a checklist with arithmetic, not a test: **update its expectations when the docs legitimately
change**, or it will start reporting the truth as a failure.
