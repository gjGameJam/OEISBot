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
| `dashboard/app.py` | read-only API, serves the built frontend | `db`, `select` |
| `dashboard/` (repo root) | React frontend (Vite + TypeScript) | |

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
   stderr tail are not scrubbed (a known limitation).
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

## Tests

`python -m pytest` runs 257 tests in about 50 s. Tests that need the sandbox runtimes are marked
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

Counts are test functions; parametrized cases bring `test_pari.py` to 16, `test_codegen.py` to 83,
`test_attempt.py` to 51, `test_estimate.py` to 28, `test_model.py` to 10 and `test_recheck.py` to 9
collected tests.

| File | Test functions | Covers |
|---|---|---|
| `test_sandbox.py` | 16 | each sandbox guarantee attacked directly: memory cap (gradual, single huge allocation, swallowed `MemoryError`), wall and CPU caps, child processes, network, filesystem, output flood, disk cap, stop callbacks, kill-on-close, gp inside the sandbox and gp shell-out |
| `test_verify.py` | 16 | the gate through the real sandbox: correct/extended, verify-only, offset error, shifted values, late wrong term, skipped index, crash, float values, early end, verify timeout, gmpy2 values, an infeasible stop ending the sandboxed run (no extension time, so no timing dependence; no new term, no censored time), over-prediction kill on a trusted projection, no kill on an untrustworthy one (where the old rule would have killed), no kill when the seconds per work unit climb 3× per term under a trustworthy cost fit (the rule before offer A would have killed), gp program |
| `test_estimate.py` | 24 | synthetic cost curves: exponential, polynomial, factorial (climbing ratio), odd/even alternation, disagreement, too few points, seconds conversion and budget, memory, search names, open search, int64 bound, cheap sequences; the kill threshold (both sides of its 10 s floor, none on disagreement or on too few points, a trustworthy climbing projection still killed from its high estimate) and session 5's recorded A277532 and A390295 points replayed to their recorded estimates with no kill; the rate drift (A377248's real points: a trustworthy cost fit withdrawn by an 11× drift, the stored flag and its reason; the exact definition and both sides of the factor; exactly the last five fitted points counted, against an independent fit; the CPU unit, steady and starved; the harness, driven in memory, using its budget's kill factor for both the stored flag and the kill); the infeasibility check on time (four untrustworthy projections from the offer-F replay, A274508's a(16), A350878's a(14) and a(15), A265383's a(8), never infeasible at budgets from 1 s to 3 h, each with the reviewer's note when over the budget and a search with none; a trustworthy one, A274508's a(17), still infeasible on its high end with its low end inside the budget, and feasible at a budget equal to the high end; A377248's drift-withdrawn fit still judged on its high end; the harness, driven in memory, running on past an untrustworthy projection and keeping the new term); the extension's infeasible stop, through `run_attempt` with the sandbox replaced by a replay at controlled times (the doubling program's terms each projected exactly, the stop on the line of the last term that fits, at a term the test computes itself, before the next starts, and no censored time) |
| `test_pari.py` | 14 | statement splitting, each program form and rewrite, rejected shapes, all three forms verified and extended in the sandbox, predicate work counts, syntax error, `search_start` equal to the driver's start, the out-of-reach bound (boundary, other forms never bounded, huge values), the real driver's rate on a do-nothing predicate staying below `PREDICATE_MAX_RATE` |
| `test_codegen.py` | 42 | code extraction, plan parsing, static checks, holdout in the prompt, at least 2 terms held out at every size, copied-term rejection, fixed-bound flags, redaction of held-out values, retry with the real error then success (scripted fake model, asserting the stop-specific guidance reaches the model), guidance per failure type, host conditions not blamed on the program, every retryable `Stop` classified, `API_HINTS` names checked against the sandbox interpreter, generation cap, too few known terms never reach the model, no runnable code, an unreachable model, model skip; the list contract (the form question asked only for strictly increasing known terms, its parse defaulting to function, `members(work)` only for a list whose terms increase, the classify and `terms(work)` prompts unchanged, the static check and extraction per contract (the name `terms` refused at module level in 13 forms, a local of that name allowed, an unfenced program still extracted), the prompts for a function word for word the old ones, constant expressions such as `10**7` or `10**4 - 1` as fixed bounds, code too deep to parse rejected and a deep expression unable to crash the stage, no held-out value in any list prompt (a program value past the last shown term included, in retries and repeat messages), the driver numbering from offsets -2, 0, 1 and 5 and ending a lower, equal or paired value as `protocol` without naming a value, every new term voided when members arrive out of order after verification (and standing after any other error), a value too long to print never shown, and a `members(work)` win end to end: `python:model`, the AI-generated and numbered-by-the-runner warnings, `executed.py` and the run file holding the driver, the run file's bytes hashing to `program_sha`); repeats (not run after each deterministic failure or a `verify_timeout`, caught with comments and layout changed, when not the latest and when it first failed in generation 2, counted as a generation, the message and both guidance texts reaching the model; run again after each other failure); no retry showing a program value that is a held-out term, under `terms(work)` too (a shown and a held-out index, a `bad_index` index, the sign flipped as in attempt #105 under both contracts, long values matched as printed, a value that is also shown kept, through the loop) |
| `test_ingest.py` | 14 | entry parsing, signed data, program splitting, b-file parsing, known-term merging and conflicts, LFS-pointer cache logic (and `bfile.cached` agreeing with it offline, with and without a mirror), an HTML page instead of a b-file, keyword filtering (`fini,more` kept, `full`/`dead`/`dumb`/non-`more`/no-DATA dropped), `sync` writing candidates and clearing `in_more`, sum tree sampling, weighted pick, difficulty features |
| `test_model.py` | 5 | the model client with a stubbed server: the Ollama and OpenAI request/response shapes, `ModelUnavailable` when nothing answers, and `available()` against a model listing (exact name, name before the tag, missing model, empty listing, dead server) |
| `test_db.py` | 11 | WAL + read-only reader, attempt and prediction rows, dead ends, infeasible dead ends only without a bigger budget, a used-up extension as a dead end only without more time (never with new terms, without stored budgets, on a starved CPU or for `over_prediction`; memory not compared), verify timeouts as dead ends up to the time already spent (the sandbox's `timeout` never), `record_win` rolls back as a whole, pool leaves out sequences only the model could attempt but would refuse, the failure penalty counting attempts, not rows (one attempt's rows once; a verified row alone; attempts with only wins, superseded runs or skips not at all; a row without a key, or with an unreadable `extra`, on its own; the ×64 cap), double-submit guard, session roll-up |
| `test_attempt.py` | 38 | orchestration with stubbed network: win with artifact and review (and stored budgets), superseded run, dead end not repeated, a used-up extension not run again without more time (end to end through the sandbox, the selection check agreeing) and not holding back the entry's other programs (in a later attempt the others run in order, a failing one not stopping the next, and one wins; the sequence stays in the PARI-only pool; for an `infeasible` dead end too), nor does a program broken after verifying, each per-sequence gate recording a skip and running nothing (entry missing, `more` gone, b-file lookup failing, b-file disagreeing with DATA), an infeasible dead end run again under a bigger budget, `too_few_known_terms` recorded after a failed PARI run, re-check error retried in place, unreachable re-check kept pending (blocked from attempts and picks) and later resolved as a win or as superseded, Ctrl+C during the re-check leaves a resolvable pending win, non-network errors not retried, a win surviving a failed save, pending retries surviving an unloadable pickle (inside a session too), a foreign artifact folder and a failed database write; an out-of-reach predicate never run (and still handed to the model), dead ends checked before reach and the skip reason each combination records, a verified PARI program or a win stopping the other PARI programs while a failed one does not, the model tried after a verified-but-unproductive PARI run in this attempt (its note surviving truncation and retries, no held-out value in any prompt, the reviewer warning on the winning generation's README) or in an earlier one now a dead end (infeasible or a used-up extension; and never from a dead end that did not verify or that found new terms, so no held-out value can reach the prompt), a verified run with too few terms for the model, an empty b-file falling back to DATA, new PARI terms keeping the model away whatever the re-check says, and the selection check (leaves out each unrunnable kind, keeps them for the model or names `too_few_known_terms`, uses the cached b-file, keeps what the attempt's gates decide, leaves out and reports what would stop a session, uses the session's own budgets, `queue`/`pick` showing the session pool); every row of an attempt carrying one `attempt_call` (a failed PARI run and a model generation counted as one attempt, a second attempt as another; the key on a win's row from `recheck_pending` to `extended`, and surviving `retry_pending_rechecks`) |
| `test_recheck.py` | 2 | the re-check verdicts against a stubbed oeis.org (still new, `more` removed, overlapping terms, a disagreeing value, a live b-file that already has them, an unreadable entry, an entry without terms), and `oeisbot recheck` (nothing pending, then a pending win it cannot load: message and non-zero exit) |
| `test_dashboard.py` | 3 | every endpoint, artifact file confinement, API never writes |

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
and extend `tests/test_dashboard.py` for new endpoints.

## Helper scripts

Run from the project root with the venv's Python.

| Script | Purpose |
|---|---|
| `scripts/model_smoke.py [A-numbers...]` | End-to-end check of the real local model (classify, generate, static checks, sandboxed verification) on well-known sequences, using DATA terms and short budgets. Writes nothing to the database or `artifacts/`. Defaults to A000005, A001358, A000108 |
| `scripts/make_demo_db.py` | Builds a synthetic database and review folders so every dashboard view has data. Deletes `data/` and `artifacts/` under `OEISBOT_HOME` first, and refuses to run unless `OEISBOT_HOME` is set to a directory other than the project root. Serve it with `oeisbot dashboard --port 8766` under the same `OEISBOT_HOME` |
| `scripts/check_docs.py` | Fails if a doc link or heading anchor does not resolve. Also lists backticked code names from the docs that are not found in `oeisbot/`, `tests/`, `scripts/` or `dashboard/src/`; expected hits are `PermissionError` (built-in), `CREATE_NO_WINDOW` (the flag deliberately not used) and `is_A123456` (an illustrative name) |

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
