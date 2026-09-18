# Project status and handoff

Snapshot as of **2026-09-17**, written at the end of session 4. This page exists so work can resume in a
new session without the history of the one that built the project. Update it at the end of each working
session.

**Nothing is in flight.** No background jobs, no half-finished edits, no pending re-checks. The working
tree is green: 145 tests pass and `scripts/check_docs.py` reports no link problems. Every decision made
so far is in the table below; the open questions are in [next steps](#open-offers-and-next-steps).

## Resuming in a new session

1. **Work in the right directory.** The git repository is nested: `C:\gtest\OEISBot\OEISBot` holds the
   code; the outer `C:\gtest\OEISBot` is just a folder. Start sessions in the inner directory, so
   `CLAUDE.md` loads automatically.
2. **Read** `CLAUDE.md`, this page, then [known limitations](known-limitations.md).
3. **Confirm the machine is still set up** (every command should succeed without reinstalling):

   ```
   .venv\Scripts\python -m pytest            # expect 145 passed
   .venv\Scripts\oeisbot model-check         # expect 'ready' (first call loads the model, about a minute)
   .venv\Scripts\oeisbot stats               # expect 26,814 candidates (14,436 with no program)
   .venv\Scripts\oeisbot attempts --limit 60 # expect 49 rows, ids 1-49
   .venv\Scripts\oeisbot recheck             # expect "no wins are waiting for a re-check"
   .venv\Scripts\python scripts\check_docs.py  # expect 0 link problems; the 6 IDENT lines are the expected ones
   ```

   If a count differs, the database has moved on from this page: trust the database and update the page.

4. **Do not redo** the expensive setup: the oeisdata clone (2.3 GB), the model pull (9 GB) and `oeisbot
   setup` are done. Do not delete `data/`: it holds the attempt history.

## Where things stand

- **Build:** all eight steps of the [design spec](design-spec.md) are implemented, with 145 passing tests.
- **Fixes after the build** (session 3, 2026-09-17): the four offers from the end of session 2 are done,
  an independent audit of those fixes was addressed, the `fini` mismatch is fixed and the test suite grew
  from 92 to 141 tests. See history items 10 and 11.
- **Docs:** complete and independently audited against the code (23 findings, all fixed); updated for
  the session 3 fixes. The session 3 doc changes were audited too; its findings are fixed.
- **Real runs:** 27 sequences attempted, 0 wins. Database session 4 was the first to spend its budget on
  arithmetic rather than model generation, and it found that verification — not extension — is the
  binding constraint: 5 of 6 PARI runs could not reproduce the known terms within 600 s, and the one that
  did found no new term in 1800 s. History item 16 has the numbers; details in
  [known limitations](known-limitations.md#observations-from-real-runs).
- **Git:** branch `main` has only the initial commit (`c1109d1`, a Python `.gitignore`). **All project
  work is uncommitted and untracked.** The user said not to worry about committing for now. `.gitignore`
  already excludes the local state below, so `git add -A` would stage only source, tests, docs and
  config.
- **Background processes:** none. The Ollama tray app keeps its server running on port 11434.

### Local state on this machine (not in git)

| Item | State |
|---|---|
| `.venv/` | Python 3.11.9 venv with the package installed editable (`-e ".[dev]"`) plus fastapi, uvicorn, httpx |
| `tools/python/` | embeddable CPython 3.11.9 with gmpy2 2.3.1, sympy 1.14.0, mpmath 1.3.0, precompiled |
| `tools/pari/gp.exe` | PARI/GP 2.17.4 standalone |
| AppContainer `OEISBot.Sandbox` | profile created; read grants on `tools/python`, `tools/pari`; modify grant on `data/scratch` |
| `data/oeisdata/` | synced to commit `956668977564dbec38a657dafa875f021b4d052b` at 2026-09-17 13:06 UTC; the candidate table was rebuilt from that same checkout after the `fini` fix (`sync --no-pull`) |
| `data/oeisbot.sqlite3` | 26,814 candidates; 4 sessions; 55 attempt rows (52 program runs, 3 skips) over 27 distinct sequences; 3 predictions; 0 reviews. Six rows have no `session_id`: standalone re-attempts, including the A129250 one that checked the retry-prompt fix |
| `data/runs/` | 67 files (term logs and generated programs from the runs above) |
| `data/pending/` | does not exist yet (created only when a re-check fails) |
| `data/*.log` | `clone.log`, `session1.log`, `session2_model.log`, `session3_real.log`, `bfile_sweep.log`, `model_smoke2.log`, `ollama_pull.log` (console output of earlier runs; safe to delete) |
| `data/bfiles/` | 123 files. `fetch-bfiles` has resolved every candidate: 68 have a b-file, 26,746 do not |
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

## Open offers and next steps

One offer is waiting for an answer:

- **A. Stop preferring `work` over CPU seconds when the conversion rate is itself growing.**
  `verify.Harness.points()` picks the work unit whenever the last record reports `work > 0`, and
  `estimate.assess` converts to seconds with the mean wall-per-work rate of the last five terms — which
  assumes that rate is roughly constant. On A377248 the rate grew about 7.5x per term, and the resulting
  projection was 3.5x low or worse (history item 16). Options: fit both units and take the more
  pessimistic projection; or detect a climbing wall-per-work rate and fall back to CPU. This is a change
  to the feasibility gate, so it wants its own tests and an independent audit.

Suggested next steps, roughly by value:

1. **Decide what the budget evidence means for candidate selection.** Database session 4 showed that a
   600 s verify budget clears the gate for 1 of 6 PARI runs, and that the failures are cost, not bugs.
   Raising the budget further is one option, but the cheaper one is to stop picking sequences whose last
   known term is already expensive — which is next step 2, now with data behind it.
2. Tune difficulty once there is data. Predicates and print loops whose last known term is large are
   expensive to verify, and the scoring does not see that.
3. Address the six remaining documented mismatches ([known limitations](known-limitations.md#differences-from-the-design-intent)).
4. Smaller follow-ups from session 3 ([known limitations](known-limitations.md#pipeline-and-recording)):
   save pending re-checks as JSON instead of pickles; give up on (or flag) a pending win whose re-check
   fails the same way every time; key the infeasible dead end on the effective memory cap.
   Untested paths that remain: the `fini` candidates have never been attempted (the 186 new ones are in the
   pool but no session has run since), and no live run has used a b-file.
5. Decide on Wolfram Engine: 5,282 candidates have Mathematica but no PARI program.
6. Commit the work when the user asks.

## Helper scripts

In `scripts/` (see [development](development.md#helper-scripts)):

- `model_smoke.py`: real-model check on well-known sequences, no database writes.
- `make_demo_db.py`: synthetic database for looking at the dashboard. Refuses to run without a scratch
  `OEISBOT_HOME`.
- `check_docs.py`: doc link/anchor checker plus a list of code names the docs mention.
