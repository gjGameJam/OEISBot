# Project status and handoff

Snapshot as of **2026-09-19**, written at the end of session 5 and updated after offer B, the
extension dead end, offers A, C, G, H, F, D and E and the flaky-test fix (history items 21 to 30). This page exists so work can resume in a new session
without the history of the one that built the project. Update it at the end of each working session.

**No task is in progress.** The last one, the flaky test (the user, 2026-09-19: "Yes start in step 1";
the step said "The fix belongs in the test (...), not in the rule; plan it with a critic like the
offers"), is finished, in the
same sections as the G, H, F task below with one critic agent: history item 30. The test was split into
an in-memory test with controlled times and a sandbox test with no extension time; neither depends on
timing. Its diagnosis corrects an earlier one: offer F did not add a failure mode (item 27 said it did).
No offers are waiting for an answer. No background jobs, no pending re-checks. At the user's request
("Commit and push before we start", then "commit and push" again after the fix), everything up to offer E
was committed and pushed as `5e4665a`, and the flaky-test fix is a second commit on top of it, so the
working tree is clean. 257 tests pass and `scripts/check_docs.py` reports no link problems. Every decision made so far is in the
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
   byte for byte (codegen.py, verify.py, estimate.py, artifact.py are CRLF; attempt.py, test_codegen.py
   are LF).
7. **Critic audit, then a re-check of the fixes** by the same critic.
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


## Resuming in a new session

1. **Work in the right directory.** The git repository is nested: `C:\gtest\OEISBot\OEISBot` holds the
   code; the outer `C:\gtest\OEISBot` is just a folder. Start sessions in the inner directory, so
   `CLAUDE.md` loads automatically.
2. **Read** `CLAUDE.md`, this page, then [known limitations](known-limitations.md).
3. **Confirm the machine is still set up** (every command should succeed without reinstalling):

   ```
   .venv\Scripts\python -m pytest            # expect 257 passed (on an otherwise idle machine: history item 30)
   .venv\Scripts\oeisbot model-check         # expect 'ready' (first call loads the model, about a minute)
   .venv\Scripts\oeisbot stats               # expect 26,814 candidates (14,436 with no program)
   .venv\Scripts\oeisbot attempts --limit 200 # expect 111 rows, ids 1-111
   .venv\Scripts\oeisbot queue --limit 0    # expect 3568 candidates; left out 1748 (1326 / 393 / 29)
   .venv\Scripts\oeisbot recheck             # expect "no wins are waiting for a re-check"
   .venv\Scripts\python scripts\check_docs.py  # expect 0 link problems; the 7 IDENT lines are the expected ones
   ```

   If a count differs, the database has moved on from this page: trust the database and update the page.

4. **Do not redo** the expensive setup: the oeisdata clone (2.3 GB), the model pull (9 GB) and `oeisbot
   setup` are done. Do not delete `data/`: it holds the attempt history.
5. **Work the way the user asks for** ("go slow and use a critic", "review your work as you go"): write a
   short plan with the evidence, have a separate agent critique it before coding, ask the user only the
   decisions that are theirs, implement with tests, break each new behaviour on purpose to prove a test
   fails (restore files byte for byte; line endings differ per file), have a separate agent audit the
   change without being told it looks right, fix, and send the fixes back to the same auditor. Check every
   number a reviewer reports before repeating it, re-deriving it from the raw data by your own method:
   in item 30 the check used the reviewer's method and inherited its bug (distinct run ids over a file
   whose ids repeat). Before calling something a test gap, run the mutant against the whole suite, not
   only the test you have in mind. Before a real run, write the expected results down.
   Every stage so far found something the previous one missed (history items 11, 18, 21, 22, 23, 24,
   25, 26, 27, 28, 29, 30). The user's latest instructions: "Implement G, H, and F one at a time. Break each
   item down into sections. Use a critic agent to stay on task" and, for D and E, "Go one item at a time
   and slow. Break down items into subitems when possible and use a critic agent to avoid defects" (the
   sections are in [the G, H, F task](#offers-g-h-and-f-one-at-a-time-done); one critic agent per item,
   reused through SendMessage for the audit and the re-check). A change to the database itself (history
   item 28): a scratch script with a dry run on a `VACUUM INTO` copy, its rollback proven there, the
   critic's review of the script, a `VACUUM INTO` backup in `data/`, then one `BEGIN IMMEDIATE`
   transaction holding every read, write and check.

## Where things stand

- **Build:** all eight steps of the [design spec](design-spec.md) are implemented, with 257 passing tests.
- **Selection and the model after PARI** (session 5, 2026-09-18): the verify budget is a 60 s first pass,
  timed-out programs are dead ends up to the time they already ran, provably hopeless predicate searches
  are not run, sessions no longer pick sequences an attempt could only skip, and with `--model` a PARI
  program that verifies but finds nothing new hands over to the model. Planned with a critic, audited
  independently, re-checked. History items 17-20.
- **Over-prediction kill** (offer B, 2026-09-18, after session 5): only a trustworthy projection can kill
  a term now; an untrustworthy one leaves the term to the extension budget. History item 21.
- **Rate drift** (offer A, 2026-09-18): nor can a projection whose seconds per cost unit, projected to
  the next term, exceed the rate it was converted with by more than the kill factor (2). The estimate
  itself is not corrected. History item 23.
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
  untrustworthy, as every real one so far, goes on until its term arrives or its extension is used up.
  History item 27.
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
  and audited with every change since (session 3, session 5, offer B, the extension dead end, offers A, C, G, H, F, D and E, and the flaky-test fix).
- **Real runs:** 47 sequences attempted, 108 program runs, 0 wins. Database session 4 showed that
  verification, not extension, is the binding constraint (history item 16). Session 5 measured the
  quick-first-pass selection: 0 wasted picks, 3.6× the program runs per hour of the earlier PARI-only
  sessions and about 3× the runs past the known terms per hour, but the same per-run pass rate (3 of 22)
  and still no new term (item 19). The model, given its first correct-but-slow PARI programs, failed all
  9 generations, 8 of them on index bookkeeping (item 20). After offer B, session 5's two killed
  sequences ran again and each used its whole 300 s extension (item 21). With the list contract the
  model verified two sequences at the first try and had no `bad_index` in 20 runs, but found no new
  term (item 24). Details in
  [known limitations](known-limitations.md#observations-from-real-runs).
- **Git:** the user committed and pushed everything up to session 4 themselves (`1b6881d` "started oeis
  bot", on `main`). On 2026-09-19, at the user's request ("Commit and push before we start"), session 5,
  offer B, the extension dead end and offers A, C, G, H, F, D and E were committed and pushed as
  `5e4665a` (after 256 tests passed and `origin/main` was checked unchanged). The flaky-test fix (history
  item 30; tests and docs only) is a second commit on top of it, pushed the same day at the user's
  request. Do not commit or push unless the user asks. `.gitignore` excludes the local state below.
- **Background processes:** none. The Ollama tray app keeps its server running on port 11434.

### Local state on this machine (not in git)

| Item | State |
|---|---|
| `.venv/` | Python 3.11.9 venv with the package installed editable (`-e ".[dev]"`) plus fastapi, uvicorn, httpx |
| `tools/python/` | embeddable CPython 3.11.9 with gmpy2 2.3.1, sympy 1.14.0, mpmath 1.3.0, precompiled |
| `tools/pari/gp.exe` | PARI/GP 2.17.4 standalone |
| AppContainer `OEISBot.Sandbox` | profile created; read grants on `tools/python`, `tools/pari`; modify grant on `data/scratch` |
| `data/oeisdata/` | synced to commit `956668977564dbec38a657dafa875f021b4d052b` at 2026-09-17 13:06 UTC; the candidate table was rebuilt from that same checkout after the `fini` fix (`sync --no-pull`) |
| `data/oeisbot.sqlite3` | 26,814 candidates; 5 sessions; 111 attempt rows (108 program runs: 43 PARI, 11 of them verified, and 65 model, 2 verified; 3 skips) over 47 distinct sequences; 13 predictions; 0 reviews. 40 rows have no `session_id`: standalone `oeisbot attempt` runs, including the A129250 re-attempt, the 12 rows of the step-2 run (history item 20), the 2 rows of the offer-B check (item 21) and the 20 rows of the offer-C measurement (item 24). A copy taken just before session 5 is in that session's scratchpad only, not in the repo. Since offer D (2026-09-19) the 108 run rows carry `extra.attempt_call` (`legacy-<first row id>`, 60 distinct attempts), backfilled once; see the backup below |
| `data/oeisbot-before-offerD.sqlite3` | a copy of the database (`VACUUM INTO`, checked table by table) taken just before offer D's backfill wrote `extra.attempt_call` into the 108 run rows on 2026-09-19; nothing else in the database was changed. Safe to delete once D is accepted |
| `data/runs/` | 140 files (term logs and generated programs from the runs above; a run that stopped at its first term has no term log) |
| `data/pending/` | does not exist yet (created only when a re-check fails) |
| `data/*.log` | `clone.log`, `session1.log`, `session2_model.log`, `session3_real.log`, `session5_probe.log`, `session5_model_step2.log`, `offerB_check.log`, `offerC_measure.log`, `bfile_sweep.log`, `model_smoke2.log`, `ollama_pull.log` (console output of earlier runs; safe to delete) |
| `data/bfiles/` | 68 b-files in 55 subfolders. `fetch-bfiles` has resolved every candidate: 68 have a b-file, 26,746 do not |
| `artifacts/` | empty (no wins) |
| `dashboard/node_modules/`, `oeisbot/dashboard/static/` | installed and built |
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
| A run with new terms is recorded as `recheck_pending` and its result pickled to `data/pending/` *before* the re-check; network errors are retried twice in place; an unfinished re-check is retried by `oeisbot recheck` and at each `oeisbot run`; no artifact until a re-check succeeds | assistant (the user's offer said "record with a clear outcome, retry later"); save-first ordering added after the audit showed Ctrl+C during the retry waits could still lose a win | [pipeline](pipeline.md#7-re-check-and-artifact-only-when-new-terms-were-found), [operations](operations.md#a-win-whose-re-check-failed-recheck_pending) |
| With `--model`, sequences with no PARI program and fewer than 3 known terms (after their b-file lookup) leave the selection pool | assistant, after the audit noted they would otherwise be re-picked and skipped every session | [pipeline](pipeline.md#2-selection-oeisbot-run--n-n---alpha-a---seed-s---model) |
| Infeasible dead ends are keyed on `extend_wall_s` and `mem_bytes`, stored in `attempts.extra` (no schema change) | assistant | [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first) |
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
      - a run with new terms is recorded as `recheck_pending` and pickled to `data/pending/` first;
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

## Open offers and next steps

Offers waiting for an answer: none. The previous next step 1, the flaky test, was done on 2026-09-19
(history item 30).

Suggested next steps, roughly by value:

1. A session like session 5 (`run -n 20 --verify-s 60 --extend-s 1800`, PARI only) to see what
   verified runs do with their full extension now that offers B, A and F no longer stop them early on an
   untrustworthy projection. Proposed to the user, not started. Write the expected results down first,
   as for session 5 (about 3 of 20 picks verify; those now run their whole 1800 s unless they find a
   term; about 1–2 h in all). At 1800 s the extension dead end leaves A247883 and A323252 out of the pool.
2. Smaller follow-ups ([known limitations](known-limitations.md#pipeline-and-recording)): save pending
   re-checks as JSON instead of pickles; give up on (or flag) a pending win whose re-check fails the same
   way every time; key the infeasible dead end on the effective memory cap. The five remaining documented
   mismatches ([known limitations](known-limitations.md#differences-from-the-design-intent)).
3. A second, slower pass (`run --verify-s 600`) would revisit the 24 PARI programs that timed out at 60 s
   (17) or 120 s (7); the 6 that already ran 600 s stay dead ends below `--verify-s` 601. The evidence so
   far says it will rarely pay.
4. Decide on Wolfram Engine: 5,282 candidates have Mathematica but no PARI program.
5. Commit the flaky-test fix when the user asks (everything before it is in `5e4665a`).

## Helper scripts

In `scripts/` (see [development](development.md#helper-scripts)):

- `model_smoke.py`: real-model check on well-known sequences, no database writes.
- `make_demo_db.py`: synthetic database for looking at the dashboard. Refuses to run without a scratch
  `OEISBOT_HOME`.
- `check_docs.py`: doc link/anchor checker plus a list of code names the docs mention.
