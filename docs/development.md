# Development guide

For people and coding agents changing OEISBot. Read [pipeline](pipeline.md) first for the runtime flow.

## Environment

```
uv venv .venv --python 3.11
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"     # UV_SYSTEM_CERTS=1 behind TLS inspection
.venv\Scripts\oeisbot setup                                      # sandbox runtimes (needed by most tests)
.venv\Scripts\python -m pytest
```

The core package uses only the standard library. The `dashboard` extra adds `fastapi` and `uvicorn`;
`dev` adds those plus `pytest` and `httpx`. Inside the sandbox, programs can import `gmpy2` and `sympy`
(installed into `tools/python` by setup).

## Module map

| Module | Responsibility | Depends on |
|---|---|---|
| `config.py` | paths (`ROOT`, `OEISBOT_HOME`), URLs, model settings, `Budgets` | |
| `cli.py` | argparse commands; imports lazily per command | most modules |
| `setup_tools.py` | download sandbox runtimes, AppContainer grants, create database | `sandbox.windows`, `db` |
| `sandbox/types.py` | `Limits`, `RunResult`, `Status`, callback types | `config` |
| `sandbox/windows.py` | Job Object + AppContainer runner (in use) | `ctypes` |
| `sandbox/posix.py` | `setrlimit` runner (never run) | |
| `sandbox/__init__.py` | picks the backend; `new_scratch_dir`, `runtime_problems` | |
| `runners/py_runner.py` | sandbox-side driver for Python programs (copied into scratch; must stay stdlib-only and self-contained) | |
| `terms.py` | `KnownTerms`, `Program`, b-file formatting | |
| `verify.py` | verification harness: protocol, checks, stop reasons, projections, run log | `sandbox`, `estimate`, `terms` |
| `estimate.py` | cost/memory projection and feasibility (pure functions) | |
| `db.py` | schema, connections, all writes, dead-end and review queries | `config` |
| `ingest/seqfile.py` | parse internal-format entries | |
| `ingest/bfile.py` | b-file fetch/cache/parse, rate-limited HTTP, `known_terms` | `config`, `terms` |
| `ingest/oeisdata.py` | git mirror, candidate sync, program stats | `db`, `estimate`, `seqfile` |
| `select.py` | difficulty, sum tree, candidate pool (with an optional keep-check), weighted pick | `db` |
| `strategies/pari.py` | GP statement parsing, program forms, drivers, the predicate reach bound | `seqfile`, `terms` |
| `strategies/codegen.py` | prompts (classify, the list-or-function question, the `terms(work)` and `members(work)` contracts), the members driver, static checks, generation loop (repeats not run) | `model`, `verify`, `terms`, `db` (which failures repeat) |
| `model.py` | Ollama / OpenAI-compatible client | `config` |
| `attempt.py` | per-sequence orchestration (`pari_plan`), re-check (with retries and pending re-checks), the selection check (`Runnable`), sessions | everything above |
| `artifact.py` | review folders | `verify`, `terms`, `strategies.codegen` (one note prefix) |
| `pickmap.py` | the Pick map's arithmetic, pure functions: a pick chance (`chances`, the first-draw share `d ** -alpha / Σ`, built from `select.weight`), a difficulty band (`band_of`), the change since a baseline snapshot (`compare`, `baseline`), and why a sequence left the pool (`departure_reason`) | `select` |
| `dashboard/app.py` | read-only API (the Pick map's `/api/pickmap` and its cached live pool included), serves the built frontend | `db`, `select`, `attempt` (the session pool and the rules fingerprint), `pickmap` |
| `dashboard/` (repo root) | React frontend (Vite + TypeScript); the Pick map is `src/pickmap.tsx` (the page) over `src/treemap.ts` (the layout and colour arithmetic, no React), with its tests in `dashboard/test/` | |

## Invariants

Changes must preserve these. Most have tests.

1. **Nothing submits.** The only oeis.org traffic is GET requests for b-files and entry text, all through
   `ingest.bfile.http_get`, which enforces the 1 request/second limit. Do not add another HTTP path to
   oeis.org.
2. **Untrusted code runs only through `sandbox.run` with `isolate=True`.** That covers every program from
   an entry or a model, in any language. `sandbox.run` reports program misbehavior through
   `RunResult.status` and does not raise for it.
3. **Verification is on (index, value) pairs.** The first emitted index is the first known index,
   indices are consecutive, and no term beyond the known range counts until every known term matched.
4. **Known terms are trustworthy or the sequence is skipped.** The b-file is the source of truth, merged
   with DATA; disagreements, gaps and duplicates raise `InconsistentTerms`.
5. **Held-out known terms stay hidden from the model.** `shown_indices` shows the first
   `min(30, max(3, ⌊0.6 × count⌋), count − 2)` known terms, so at least 2
   (`config.CODEGEN_HELD_OUT_MIN`) are always held out. Sequences with fewer than 3 known terms
   (`config.CODEGEN_MIN_KNOWN_TERMS`) never reach the model. Keep the literal check against all known
   terms and the redaction of held-out values in `describe_failure`: the correct value at a held-out
   index, any program value (in a `wrong_term` or a `bad_index` detail) that equals a held-out term not
   also shown, either sign, and under the list contract any program value at a held-out index or past
   the last shown term. Keep values out of the members driver's errors. A crash's own message and
   stderr tail are not scrubbed (a known limitation), and since 2026-09-25 neither is a `protocol`
   detail, which carries the raw term line: an index longer than `verify.MAX_TERM_FIELD_DIGITS` is now
   refused before the index check, so a program putting a held-out value where the index belongs reaches
   `protocol` rather than the scrubbed `bad_index`. Measured exposure and the reason it was recorded
   rather than fixed are in
   [known limitations](known-limitations.md#term-lines-from-an-untrusted-program).
6. **Every run is recorded** (attempt row + predictions). Every generated program that runs is saved in
   `data/runs/` as it ran (driver included), and every accepted term is logged as it arrives.
7. **A win is re-checked against oeis.org before an artifact or review is created, and is never lost to
   a failed re-check.** A run with new terms is recorded as `recheck_pending` and its result saved to
   `data/pending/` before the re-check starts; only a finished re-check changes that outcome. The sequence
   is blocked while pending. `retry_pending_rechecks` never raises for a single attempt, and resolving an
   attempt must stay safe to repeat (the `.incomplete` marker, `db.record_win`'s single transaction).
8. **The dashboard never writes.** It uses `db.connect(readonly=True)`, and review status changes go
   through the CLI.
9. **Artifacts carry their warnings**: weak verification, rewrites, AI-generated, numbered by the runner
   (a `members(work)` program), hard-coded bounds, and for a model program written after the entry's own
   program verified, a pointer to compare with it. The dashboard's Review inbox repeats them. The
   AI-generated warning depends on the exact strategy string `python:model`: keep it for every model
   program, whatever its contract.
10. **A bound published in an entry's comments is never evidence about a term.** `bounds.applicable`
    reads an unverified human claim. It may be used to stop spending time — that is the whole of the
    [searched-bound check](verification-and-estimation.md#the-searched-bound-check) — and never to decide
    a term's value, to decide its index, or to let a term be reported as new. This is why the check runs
    *after* verification rather than in place of any part of it, why nothing resumes a scan past a
    published bound (`extra.verified_scan_to` records the part that was actually measured), and why the
    check is confined to the predicate form, where a value bound really is a work bound. The stop's
    `detail` must also stay free of any term value: it reaches the model through
    `codegen.slow_program_note`, so naming the rate and the margin beside the bound would let a held-out
    term be recovered by arithmetic (invariant 5).

## Tests

**The numbers on this page are checked by `tests/test_docs.py`, not maintained by hand.** The test
total, this table's "Test functions" column and the collected-counts paragraph below are all compared
against what pytest collected in the same run, so adding a test fails the suite until the docs catch up.
Get the new values from `python -m pytest --collect-only -q` rather than editing them by guess. The same
holds for `check_docs.py`'s expected-hits count, which it now checks itself.

`python -m pytest` runs 567 tests in about 100 s. Tests that need the sandbox runtimes are marked
`sandbox` and are skipped automatically when `oeisbot setup` has not been run (`runtime_problems()`).
The `network` marker is declared but unused: tests stub out network calls.

Real timings on this machine are noisy, so tests do not assert on sub-second timings. In 210 runs of a
doubling program through the sandbox (2026-09-19), 64 had a term of 1-140 ms that took 0.2-0.4 s more wall
time than CPU time, and on terms of 0.3-0.8 s wall time was about 1.5× CPU time at the median. A test that
ran the extension on such terms and checked its projections failed about one run in six; the extension's
infeasible stop is now tested in memory with controlled times
(`test_estimate.py::test_extension_stops_when_next_term_is_projected_infeasible`), and in the sandbox only
with no extension time, which no timing can meet (`test_verify.py::test_infeasible_stop_ends_the_sandboxed_run`).
The sandbox tests that check kill thresholds are timing-sensitive but have passed repeatedly on an otherwise
idle machine. Under full CPU load, `test_on_tick_can_stop` (wall time under 3 s) and `test_wall_timeout`
(between 1.4 and 4 s) would likely fail: there a sandboxed run took 2.4-5.2 s from the stop to its end.

Counts are test functions; parametrized cases bring `test_pari.py` to 49, `test_codegen.py` to 87,
`test_attempt.py` to 80, `test_estimate.py` to 29, `test_model.py` to 10, `test_recheck.py` to 23,
`test_replay.py` to 12, `test_heartbeat.py` to 20, `test_runtimes.py` to 24 and `test_pickmap.py` to 116
collected tests.

| File | Test functions | Covers |
|---|---|---|
| `test_sandbox.py` | 18 | each sandbox guarantee attacked directly: memory cap (gradual, single huge allocation, swallowed `MemoryError`), wall and CPU caps, child processes, network, filesystem, output flood, disk cap, stop callbacks, kill-on-close, gp inside the sandbox and gp shell-out |
| `test_verify.py` | 30 | the gate through the real sandbox: correct/extended, verify-only, offset error, shifted values, late wrong term, skipped index, crash, float values, early end, verify timeout, gmpy2 values, an infeasible stop ending the sandboxed run (no extension time, so no timing dependence; no new term, no censored time), over-prediction kill on a trusted projection, no kill on an untrustworthy one (where the old rule would have killed), no kill when the seconds per work unit climb 3× per term under a trustworthy cost fit (the rule before offer A would have killed), gp program; and the stderr tail in a detail (`_stderr_tail` keeping the last three lines that say something and dropping gp's caret rule, a line capped at `STDERR_LINE_CHARS`, `brief_detail`'s cut, a `crash` from a non-zero exit including the bare `: ` when stderr is empty, an `incomplete` with and without stderr, a real gp program calling an undefined function end to end, a stop reached with no terms keeping the tail, and a stop outside `_TAIL_STOPS` and one inside it with terms both keeping their detail); the guard at the last known index that no stream can reach, driven by hand, so a run that missed a known term can never be treated as verified |
| `test_estimate.py` | 25 | synthetic cost curves: exponential, polynomial, factorial (climbing ratio), odd/even alternation, disagreement, too few points, seconds conversion and budget, memory, search names, open search, int64 bound, cheap sequences; the kill threshold (both sides of its 10 s floor, none on disagreement or on too few points, a trustworthy climbing projection still killed from its high estimate) and session 5's recorded A277532 and A390295 points replayed to their recorded estimates with no kill; the rate drift (A377248's real points: a trustworthy cost fit withdrawn by an 11× drift, the stored flag and its reason; the exact definition and both sides of the factor; exactly the last five fitted points counted, against an independent fit; the CPU unit, steady and starved; the harness, driven in memory, using its budget's kill factor for both the stored flag and the kill); the infeasibility check on time (four untrustworthy projections from the offer-F replay, A274508's a(16), A350878's a(14) and a(15), A265390's a(8), never infeasible at budgets from 1 s to 3 h, each with the reviewer's note when over the budget and a search with none; a trustworthy one, A274508's a(17), still infeasible on its high end with its low end inside the budget, and feasible at a budget equal to the high end; A377248's drift-withdrawn fit still judged on its high end; the harness, driven in memory, running on past an untrustworthy projection and keeping the new term); the extension's infeasible stop, through `run_attempt` with the sandbox replaced by a replay at controlled times (the doubling program's terms each projected exactly, the stop on the line of the last term that fits, at a term the test computes itself, before the next starts, and no censored time); a stored prediction carrying the statistics its verdict was made from: a sound cost fit withdrawn from the kill by the rate drift reading `trustworthy = 0` with `fit_trustworthy = 1`, the disagreement pinned on a series whose newest point disagrees (a perfect exponential has a disagreement of exactly 1.0, so asserting against one would hold for any constant), a climbing fit, and all five values NULL when nothing could be fitted |
| `test_pari.py` | 41 | statement splitting, each program form and rewrite, rejected shapes, programs calling a helper from another OEIS entry (calls and indexes found, bare mentions left alone, every way a name can be defined, strings and comments ignored, the `a(n)` and predicate forms rejected, a helper the block defines itself kept, a call in a dropped driver statement not counted, one rejected block leaving another runnable), all three forms verified and extended in the sandbox, predicate work counts, syntax error, `search_start` equal to the driver's start, the out-of-reach bound (boundary, other forms never bounded, huge values), the real driver's rate on a do-nothing predicate staying below `PREDICATE_MAX_RATE` |
| `test_heartbeat.py` | 15 | the predicate driver's progress heartbeats and what the harness will believe: a frontier that moves on a good line and never halts a run on a bad one; the refusals, each of which would otherwise let a later run skip a range that was never scanned -- no caller gate (a model program printing `@P`), a malformed or over-long line, a position that does not match the work claimed for it, a frontier that moves backwards or stands still or falls behind a term already emitted, and a rate no predicate could be tested at; the ignored count and the first bad line kept so a mangled driver is a number rather than silence; then the real driver in the sandbox -- heartbeats accepted with the block adapting upward, terms byte-identical across block seams at a forced tiny block (the one place the rewrite could duplicate or skip a k), and a frontier that never names a k the driver has not tested |
| `test_bounds.py` | 27 | searched bounds in `%C` comments and the skip they trigger, all driven in memory: exact parsing for every base (`Decimal ** int` rounds at 28 digits, so 2^200 and 3^100 were wrong while 2^63 passed), OEIS's notations including `10 billion` and an absurd exponent refused; which claims count (an unindexed bound below the last known term is stale, an indexed one counts only for the next unknown index, one beyond it is not used); the two guards that cost the census its only wrong skips (a bound borrowed from another entry's sentence, a claim qualified to a subset of terms) with the entry's own A-number not tripping the first; the six phrasings that were being missed; an interjection forbidden from bridging two clauses; the loose `searched to` pattern deliberately absent; and the check itself -- fires out of reach, does not fire inside it, and can never fire on a zero work count (the a(n)/print-loop drivers hard-code `work` to 0), a zero extension budget, a collapsed measurement window or a stale bound; then what the stop means downstream: a verified run with no new terms, not a dead end, a detail that leaks no held-out term value, and a 10^5000 bound surviving JSON and the detail |
| `test_codegen.py` | 46 | a run that produced no term naming the program it ran and no run log; code extraction, plan parsing, static checks, holdout in the prompt, at least 2 terms held out at every size, copied-term rejection, fixed-bound flags, redaction of held-out values, retry with the real error then success (scripted fake model, asserting the stop-specific guidance reaches the model), guidance per failure type, host conditions not blamed on the program, every retryable `Stop` classified, `API_HINTS` names checked against the sandbox interpreter, generation cap, too few known terms never reach the model, no runnable code, an unreachable model, model skip; the list contract (the form question asked only for strictly increasing known terms, its parse defaulting to function, `members(work)` only for a list whose terms increase, the classify and `terms(work)` prompts unchanged, the static check and extraction per contract (the name `terms` refused at module level in 13 forms, a local of that name allowed, an unfenced program still extracted), the prompts for a function word for word the old ones, constant expressions such as `10**7` or `10**4 - 1` as fixed bounds, code too deep to parse rejected and a deep expression unable to crash the stage, no held-out value in any list prompt (a program value past the last shown term included, in retries and repeat messages), the driver numbering from offsets -2, 0, 1 and 5 and ending a lower, equal or paired value as `protocol` without naming a value, every new term voided when members arrive out of order after verification (and standing after any other error), a value too long to print never shown, and a `members(work)` win end to end: `python:model`, the AI-generated and numbered-by-the-runner warnings, `executed.py` and the run file holding the driver, the run file's bytes hashing to `program_sha`); repeats (not run after each deterministic failure or a `verify_timeout`, caught with comments and layout changed, when not the latest and when it first failed in generation 2, counted as a generation, the message and both guidance texts reaching the model; run again after each other failure); no retry showing a program value that is a held-out term, under `terms(work)` too (a shown and a held-out index, a `bad_index` index, the sign flipped as in attempt #105 under both contracts, long values matched as printed, a value that is also shown kept, through the loop) |
| `test_ingest.py` | 15 | entry parsing, signed data, program splitting, b-file parsing, known-term merging and conflicts, LFS-pointer cache logic (and `bfile.cached` agreeing with it offline, with and without a mirror), an HTML page instead of a b-file, keyword filtering (`fini,more` kept, `full`/`dead`/`dumb`/non-`more`/no-DATA dropped), `sync` writing candidates and clearing `in_more`, sum tree sampling, weighted pick, difficulty features, `sync` keeping the difficulty the stored b-file facts imply (and not falling back to the entry-only score) |
| `test_model.py` | 5 | the model client with a stubbed server: the Ollama and OpenAI request/response shapes, `ModelUnavailable` when nothing answers, and `available()` against a model listing (exact name, name before the tag, missing model, empty listing, dead server) |
| `test_db.py` | 21 | WAL + read-only reader, attempt and prediction rows, dead ends, infeasible dead ends only without a bigger budget, a used-up extension as a dead end only without more time (never with new terms, without stored budgets, on a starved CPU or for `over_prediction`; memory not compared), verify timeouts as dead ends up to the time already spent (the sandbox's `timeout` never), `record_win` rolls back as a whole, pool leaves out sequences only the model could attempt but would refuse, the failure penalty counting attempts, not rows (one attempt's rows once; a verified row alone; attempts with only wins, superseded runs or skips not at all; a row without a key, or with an unreadable `extra`, on its own; the ×64 cap), a run squeezed for memory not retired (the infeasible dead end keys on the cap the run was judged against, not the one it asked for; and a row with budgets but no stored cap -- the shape of every row written before 2026-09-20 -- never counting), `refresh_difficulty` rescoring every row including one that has left `more`, double-submit guard, session roll-up, the cost fit's statistics stored as written and all five NULL together when there was no fit (so `int(None)` can never raise and a missing fit can never read as a negative verdict) |
| `test_attempt.py` | 64 | orchestration with stubbed network: win with artifact and review (and stored budgets), superseded run, dead end not repeated, a used-up extension not run again without more time (end to end through the sandbox, the selection check agreeing) and not holding back the entry's other programs (in a later attempt the others run in order, a failing one not stopping the next, and one wins; the sequence stays in the PARI-only pool; for an `infeasible` dead end too), nor does a program broken after verifying, each per-sequence gate recording a skip and running nothing (entry missing, `more` gone, b-file lookup failing, b-file disagreeing with DATA), an infeasible dead end run again under a bigger budget, `too_few_known_terms` recorded after a failed PARI run, re-check error retried in place, unreachable re-check kept pending (blocked from attempts and picks) and later resolved as a win or as superseded, Ctrl+C during the re-check leaves a resolvable pending win, non-network errors not retried, a win surviving a failed save, pending retries surviving an unreadable saved result (inside a session too), a foreign artifact folder and a failed database write; an out-of-reach predicate never run (and still handed to the model), dead ends checked before reach and the skip reason each combination records, a verified PARI program or a win stopping the other PARI programs while a failed one does not, the model tried after a verified-but-unproductive PARI run in this attempt (its note surviving truncation and retries, no held-out value in any prompt, the reviewer warning on the winning generation's README) or in an earlier one now a dead end (infeasible or a used-up extension; and never from a dead end that did not verify or that found new terms, so no held-out value can reach the prompt), a verified run with too few terms for the model, an empty b-file falling back to DATA, new PARI terms keeping the model away whatever the re-check says, and the selection check (leaves out each unrunnable kind, keeps them for the model or names `too_few_known_terms`, uses the cached b-file, keeps what the attempt's gates decide, leaves out and reports what would stop a session, uses the session's own budgets, `queue`/`pick` showing the session pool); every row of an attempt carrying one `attempt_call` (a failed PARI run and a model generation counted as one attempt, a second attempt as another; the key on a win's row from `recheck_pending` to `extended`, and surviving `retry_pending_rechecks`); a session saying when `-n` is capped (picked or listed) and staying quiet when it is not; a run held below its memory budget by free RAM recording the cap it got; a pending win counting how often it has failed the same way, the count reset by a different error, the counter's own database failure not costing the win, and six shapes of a hand-edited `extra` (an array, a string, a number, unparseable text, NULL, and an object whose counter cannot be added to) each leaving the session running and the win pending; a session recording which gp produced its rows (the short token in `sessions.note` beside the settings it already carried, the full banner in `meta`) and still running, and still finishing its session row, when the version probe raises; and the pool snapshot a session stores for the [Pick map](dashboard.md#pick-map): the pool it drew from already stored when the first pick starts (with the session, the budgets and the rules fingerprint it was built under), an unchanged pool storing nothing new, a session given its own list of sequences storing none, the model pool kept apart from the PARI one and holding what only the model can take (an empty pool stored as a pool), the pool built once and that same pool stored, the stored rows being exactly the `(a_number, difficulty)` pairs of the pool the session drew from and never the weights, `session_pool` weighing every candidate by its difficulty to the power of minus alpha at alphas 0, 1 and 2 with `run_session` passing its own alpha on, a snapshot that cannot be written or whose write raises (a disk error, a refused transaction, an unknown pool, an integrity error) costing the session nothing and logging one line, `snapshot_pool` reporting `None` for an unchanged pool, and `oeisbot snapshot` storing the PARI pool, with `--all` the model's too, and naming the right pool in each message |
| `test_recheck.py` | 9 | the re-check verdicts against a stubbed oeis.org (still new, `more` removed, overlapping terms, a disagreeing value, a live b-file that already has them, an unreadable entry, an entry without terms), and `oeisbot recheck` (nothing pending, then a pending win it cannot load: message and non-zero exit); the saved pending win as JSON: a round trip keeping the program sha, both enums, int-keyed known terms and a 1268-digit term, an artifact rebuilt from the reloaded result byte for byte, the file written as bytes with a `format` version, and a loud error for every field that no longer matches the code; and the artifact's own files: `predictions.csv`'s header lining up with its rows, and the b-file ending with the blank line OEIS requires while the README's new-terms fence does not |
| `test_docs.py` | 3 | The documentation's own numbers against this run's collection: the test total in its eight places, the per-file table's function counts, and the collected-count paragraph (including that a parametrized file is not missing from it). Skips on a partial collection, and fails loudly if a sentence it checks is reworded away rather than going quietly dead. `status.md`'s history section is excluded: a number inside a history item is that session's own record |
| `test_replay.py` | 5 | `scripts/replay_predictions.py` against a synthetic database whose `predictions` predates the fit columns: a clean replay backfills, the write is idempotent (turning on a row with no cost fit, where all-NULL is both the correct answer and indistinguishable from unwritten), a disagreement blocks it, a failure part way takes the `ALTER` with it, and each of eight ways a row can fail to replay -- missing log, unreadable or non-object `extra`, no `sequences` row, wrong program sha, wrong known-term count, a log truncated past the projection's own term, and one log named by two attempts -- is reported, counted apart from the rows that reproduced, and refuses the write |
| `test_dashboard.py` | 3 | every endpoint, artifact file confinement, API never writes (every database connection an endpoint opens is read-only, `/api/pickmap` for both pools included, and the file's mtime does not move) |
| `test_pickmap.py` | 92 | the Pick map, in three layers. The pure comparison (`oeisbot/pickmap.py`): a difficulty on a band edge in the band above, chances that are first-draw shares agreeing with what the session draws with, the baseline being the newest snapshot that is not the live pool, the ratio being a candidate's share among the sequences common to both pools (one failure showing as about a half and everyone else about one, a newcomer not moving the survivors against each other, `p / p0` equal to the ratio, the masses summed exactly wherever the set of common names puts a big share, the ratio independent of the order the pool was listed in), a row in the band of its difficulty now, those who left listed heaviest first, a chance that underflows giving no ratio instead of dividing by zero, and `departure_reason` in its fixed order. The snapshot tables (`db.record_pick_snapshot`): a snapshot with its rows and what built it, the digest ignoring order and seeing the last bit of a difficulty, an equal pool refreshing the stamp and storing nothing, retention per pool from the config, a failed write leaving the old state, the write lock taken before the pool is compared, writers racing, a connection already in a transaction refused, a database from before the tables gaining them at its next write open, a reader saying so when they are missing, cascade delete; the budgets JSON and the rules fingerprint (stable, `unknown` rather than raising, moving with the source of each function, class, module and constant it is made from, and not with a checkout's line endings). `/api/pickmap`: every candidate largest first, alpha validated and the frontend's limit equal to the server's, the pools separate, the map answering without the snapshot tables and not creating them, the baseline and "nothing to compare with", new candidates and departures with the reason the database gives and only the ten largest listed, names cut, a pool built under other budgets or rules said so, the live pool built once until the database moves or a rebuild is asked for (its time to live, the budgets it is asked under, the generation counter, concurrent requests sharing one build, a build that failed an error and not a stale map, the stamp of what the build read), the warm-up, and the whole thing over the real session pool |
| `test_runtimes.py` | 17 | runtime provenance (`setup_tools.runtime_versions`): the gp probe reading **stderr** and not stdout (both directions, because reading stdout records an empty string and nothing says so), the whole banner kept on one line rather than a fixed number of lines (so the `compiled:` line, the only thing telling two builds of one version apart, survives a reordering), and every way a probe can fail to be trustworthy -- a non-zero exit, no output, exit 0 from something that is not gp, a missing binary -- yielding `unknown`, with the exit-zero case proved to be exit zero so it cannot pass on the wrong reason; every error shape swallowed but Ctrl+C deliberately not (`except Exception`, so `oeisbot run` stays interruptible during the probe); a wrapper printing a warning before a real banner accepted, but one whose preamble runs past the cap **not** accepted, because the guard is checked on the value that is stored and not on the full text; the cap cutting at a word boundary, so a version number straddling the limit becomes an honest `unknown` rather than a truncated, plausible, permanent one in a session note; the configured binaries probed rather than a PATH lookup, with `-f`, `stdin=DEVNULL`, an explicit encoding and the timeout all pinned; the short `gp=2.17.4/GMP-6.1.2` session token including a non-GMP build and both unknown forms; a `meta` round trip, which nothing had tested before; and the banner fixture asserting its own shape, because written with a literal backslash-n it is one line, every collapsing assertion holds vacuously, and a "first three lines" driver passes the whole file -- which is what happened until the audit caught it |

**The frontend has two tests of its own, and `pytest` runs neither.** `npm run build` type-checks `src/`
(`tsc --noEmit`) and nothing runs the code. `cd dashboard && npm test` (`node --test "test/*.test.ts"`,
about half a second) runs 20 tests in `dashboard/test/treemap.test.ts` against `src/treemap.ts`, the Pick
map's layout and colour arithmetic, which is written without React for that reason: Node 24 runs the
TypeScript directly, so the suite needs no new dependency. They cover the squarified layout (areas
proportional, nothing outside or overlapping, tiles reasonably square), the grouped layout (leaves inside
their group, the small-leaf lump holding exactly the members left out, a lone small leaf drawn as itself, a
tile marked "keep" drawn alone, equal chances at alpha 0, the header only where it fits, the same chance
getting the same area in a small group as in a large one, a group the frame nearly swallows not blown up to
make up for it, and empty groups and zero values giving finite rects that still tile), the seven colour
classes (their edges where the legend says, monotone, one failed attempt far from an edge) and the formatting
and URL helpers. **They are not type-checked** (`tsconfig.json` has `include: ["src"]`), and **the page
itself, `src/pickmap.tsx`, has no test**: it was looked at in a browser while it was built (the map, a band's
tab, the tooltip, a rebuild, and a narrow-width view in an iframe), which is the only place the frame, the
labels and the tooltip can be seen. The Python mutation check of the same item
and the TypeScript one (21 of 21 mutants of `treemap.ts` killed) are recorded in
[status.md](status.md#history-condensed), item 54.

Real-model behavior is not covered by the suite (it needs a GPU and minutes per sequence). To check it by
hand, run `oeisbot attempt <A-number> --model` with short budgets, or call
`strategies.codegen.generate_and_verify` directly on well-known sequences.

## Extending

### Adding a strategy

1. Produce `terms.Program` objects:
   - `language`: `python` or `gp` (see below for a new language);
   - `source`: what a human should read;
   - `script`: what actually runs, if a driver wraps `source`;
   - `origin`: where it came from;
   - `strategy`: `<language>:<form>`;
   - `notes`: anything a reviewer must know. The artifact and the dashboard label notes from any
     strategy other than exactly `python:model` as "Program was rewritten". A new strategy with other
     kinds of notes needs its own label in `artifact.write` and `dashboard/src/views.tsx`.
2. Run each program with `_Attempter.run(program, form)` inside `attempt.attempt_sequence`, so recording,
   the run log, the re-check and artifacts all happen. Respect `runner.found_new` (stop everything) and
   `runner.verified` (a program already reproduced the known terms), and decide where the
   strategy sits in the order relative to PARI and the model.
3. For deterministic programs (same script every time), check `db.is_dead_end` (with the session's
   budgets) before running.
4. Record new skip reasons with `db.record_skip` and add them to [pipeline](pipeline.md) and
   [data and schema](data-and-schema.md).
5. Tests: program construction without the sandbox, and one sandboxed test that verifies and extends a
   well-known sequence.

### Adding a language (runtime)

1. Install the runtime under `tools/` in `setup_tools.py`, as copies rather than hard links.
2. Grant the AppContainer read/execute on its directory in `setup_tools.grant_access`.
3. Add a case to `verify.Harness.argv` that writes the program into the scratch directory and returns the
   command line.
4. Emit the `@T` protocol (a driver or runner, as `runners/py_runner.py` does for Python).
5. Add the file extension to `artifact.EXT`, and to `TEXT_SUFFIXES` in `oeisbot/dashboard/app.py` so the
   Review inbox lists and serves the program files.
6. Add sandbox tests showing the runtime works inside the container and cannot escape it.

### Changing the database

Edit `db.SCHEMA` and the write functions. There are no migrations: existing databases need a manual
`ALTER TABLE` (or a fresh database, losing history). Update [data and schema](data-and-schema.md) and any
dashboard endpoint that reads the table.

### Changing the estimator

`estimate.py` is pure and fast to test. Extend `tests/test_estimate.py` with a synthetic cost curve for
the behavior, and check real accuracy afterwards in the dashboard's Estimator accuracy view.

### Changing the dashboard

Run `oeisbot dashboard` and `npm run dev` together (Vite proxies `/api`). `npm run build` type-checks
(`tsc --noEmit`) and writes `oeisbot/dashboard/static/`, which is not committed. Keep endpoints read-only
and extend `tests/test_dashboard.py` for new endpoints (`tests/test_pickmap.py` for the Pick map's). Arithmetic
the page depends on belongs in a module with no React in it, as `src/treemap.ts` is, so that
`npm test` can run it; then add the test to `dashboard/test/`.

## Helper scripts

Run from the project root with the venv's Python.

| Script | Purpose |
|---|---|
| `scripts/model_smoke.py [A-numbers...]` | End-to-end check of the real local model (classify, generate, static checks, sandboxed verification) on well-known sequences, using DATA terms and short budgets. Writes nothing to the database or `artifacts/`. Defaults to A000005, A001358, A000108 |
| `scripts/make_demo_db.py` | Builds a synthetic database and review folders so every dashboard view has data. Deletes `data/` and `artifacts/` under `OEISBOT_HOME` first, and refuses to run unless `OEISBOT_HOME` is set to a directory other than the project root. Serve it with `oeisbot dashboard --port 8766` under the same `OEISBOT_HOME` |
| `scripts/check_docs.py` | Fails if a doc link or heading anchor does not resolve. Also lists backticked code names from the docs that are not found in `oeisbot/`, `tests/`, `scripts/` or `dashboard/src/`. There are 6 expected hits and they are all legitimate: the process-creation flag this project deliberately does not use, an illustrative function name, a PARI type name, a gmpy2 function that does not exist and is cited as not existing, a helper belonging to an OEIS entry's own program, and the JSON key the offer (a) backfill stamped on the 48 attempt rows it rewrote on 2026-09-30 (history item 52) -- written by a one-off script under `data/`, which this scan does not cover, and documented in data-and-schema.md as a live `extra` key. (It was 5 for a few hours on 2026-09-30, and 10 from 2026-09-29 to 2026-09-30: session 11, history item 50, had added three names from OEIS entries' own PARI programs — A274003's predicate, the A178751 helper it calls, and A034293's predicate — cited in `CLAUDE.md` and `docs/status.md` as that session's program-selection misreads, five hits over the two files, until item 51's parser tests took all three as fixtures and they resolved to real code; 5 until 2026-09-29; 8 until 2026-09-21, when the column data-and-schema.md had only proposed was built; 7 until 2026-09-22, when the second built-in stopped being a miss because `bounds.parse_number` now catches it; and 6 until 2026-09-23, when the last Python built-in stopped being one too — item 43's probe tests name it, so the docs' mention of it resolves to real code.) Naming them in backticks here would add them to the list, so they are described rather than quoted. **The count is checked against the run**: an extra hit, one that becomes real code, or this sentence being reworded away is reported as a problem and exits non-zero, so the list cannot quietly stop being judged |
| `scripts/replay_predictions.py` | Rebuilds every stored prediction from its attempt's term log and reports any disagreement with the stored row; `--write` adds the cost fit's columns and backfills rows that have none. Read-only otherwise. What makes it trustworthy is that it re-derives values that *are* stored — `model`, the three predicted seconds, `predicted_mem`, `value_dependent`, `trustworthy`, and `feasible` for attempts that recorded both budgets — from the same `estimate.assess` call that produces the unstored ones: 45 of 45 replayed rows reproduce exactly. `trustworthy` is in that list because it is `fit_trustworthy and rate_drift <= the kill factor`, making it the only stored column that constrains a replayed `rate_drift` at all. A row it cannot replay — no term log, a pruned or truncated one, a log holding two runs, one belonging to a different run (wrong program sha, wrong known-term count, or named by two attempts at once), a sequence no longer in `sequences`, an unreadable `extra` — is counted and named separately, never among the rows that reproduced, and it makes the exit code non-zero and blocks `--write`. `--write` only ever fills rows where all five columns are NULL, so a replayed value can never overwrite one a run recorded itself (the two can differ, for instance once `oeisbot sync` has changed a sequence's name, which feeds `value_dependent`) |
| `scripts/verify_A385331.py` | Re-derivation of the first win's terms from the sequence's *name*, sharing no code with the entry's PARI program — but **not** step 6 of the review checklist, because it uses the same *method*: trial division with the exponent reduced by Fermat, so a fault in that arithmetic path would show up identically in it and in `program.gp`. Its own docstring says so. `--bound 1000000` settles 37 of 41 terms in about 13 s; the default 2e8 settles all 41 in ~19 min and bounds a(43), the term the `infeasible` stop was made about. Writes nothing. Its default input is inside gitignored `artifacts/`, so on any other machine it needs an explicit `--bfile` |

**Step 6 of the [review checklist](operations.md#reviewing-a-result) is discharged by a different
script**, `data/review1/indep_A385331.py` (history item 44, 2026-09-23). It is not in `scripts/` because
it needs gmpy2 and sympy, which live in the **sandbox runtime** rather than the venv — run it as
`tools\python\python.exe data\review1\indep_A385331.py`. It never forms `n!-k!` and never reduces modulo
`q-1`, using modular inverses instead, so it shares no arithmetic with either `program.gp` or
`verify_A385331.py`. `--bound 100000` validates it against the 24 known terms in about a second; the
default 2e8 took 775 s and settled every term. `data/review1/README.md` has the full account and the
state of every checklist step. `data/` is gitignored, so it exists only on this machine.

## Windows development notes

- **Shell heredocs corrupt backslashes.** GP comments (`\\`), Windows paths and regex escapes are easy to
  mangle when a file is edited through `cat <<EOF` or `sed`. Edit such files with an editor or a
  file-writing tool, then run `python -m py_compile` on the result.
- **Moving the project directory** invalidates the AppContainer grants; run `oeisbot setup` again.
- **Large integers.** Modules that parse or print terms call `sys.set_int_max_str_digits(0)`, since terms
  can exceed Python's default 4,300-digit conversion limit.
- **Checking the dashboard with browser automation.** Chrome cannot screenshot a tab whose window is
  hidden or minimized (the capture times out while the page itself is fine). Check the DOM with
  JavaScript, or bring the window to the front.
