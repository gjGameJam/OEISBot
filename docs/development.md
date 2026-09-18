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
| `select.py` | difficulty, sum tree, candidate pool, weighted pick | `db` |
| `strategies/pari.py` | GP statement parsing, program forms, drivers | `seqfile`, `terms` |
| `strategies/codegen.py` | prompts, static checks, generation loop | `model`, `verify`, `terms` |
| `model.py` | Ollama / OpenAI-compatible client | `config` |
| `attempt.py` | per-sequence orchestration, re-check (with retries and pending re-checks), sessions | everything above |
| `artifact.py` | review folders | `verify`, `terms` |
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
   terms and the redaction of held-out values in `describe_failure`.
6. **Every run is recorded** (attempt row + predictions). Every generated program that runs is saved in
   `data/runs/`, and every accepted term is logged as it arrives.
7. **A win is re-checked against oeis.org before an artifact or review is created, and is never lost to
   a failed re-check.** A run with new terms is recorded as `recheck_pending` and its result saved to
   `data/pending/` before the re-check starts; only a finished re-check changes that outcome. The sequence
   is blocked while pending. `retry_pending_rechecks` never raises for a single attempt, and resolving an
   attempt must stay safe to repeat (the `.incomplete` marker, `db.record_win`'s single transaction).
8. **The dashboard never writes.** It uses `db.connect(readonly=True)`, and review status changes go
   through the CLI.
9. **Artifacts carry their warnings**: weak verification, rewrites, AI-generated, hard-coded bounds.

## Tests

`python -m pytest` runs 145 tests in about 25 s. Tests that need the sandbox runtimes are marked
`sandbox` and are skipped automatically when `oeisbot setup` has not been run (`runtime_problems()`).
The `network` marker is declared but unused: tests stub out network calls.

Counts are test functions; parametrized cases bring `test_pari.py` to 13, `test_codegen.py` to 31,
`test_attempt.py` to 16, `test_model.py` to 10 and `test_recheck.py` to 9 collected tests.

| File | Test functions | Covers |
|---|---|---|
| `test_sandbox.py` | 16 | each sandbox guarantee attacked directly: memory cap (gradual, single huge allocation, swallowed `MemoryError`), wall and CPU caps, child processes, network, filesystem, output flood, disk cap, stop callbacks, kill-on-close, gp inside the sandbox and gp shell-out |
| `test_verify.py` | 14 | the gate through the real sandbox: correct/extended, verify-only, offset error, shifted values, late wrong term, skipped index, crash, float values, early end, verify timeout, gmpy2 values, infeasible stop before the term (with no censored time), over-prediction kill, gp program |
| `test_estimate.py` | 12 | synthetic cost curves: exponential, polynomial, factorial (climbing ratio), odd/even alternation, disagreement, too few points, seconds conversion and budget, memory, search names, open search, int64 bound, cheap sequences |
| `test_pari.py` | 11 | statement splitting, each program form and rewrite, rejected shapes, all three forms verified and extended in the sandbox, predicate work counts, syntax error |
| `test_codegen.py` | 18 | code extraction, plan parsing, static checks, holdout in the prompt, at least 2 terms held out at every size, copied-term rejection, fixed-bound flags, redaction of held-out values, retry with the real error then success (scripted fake model, asserting the stop-specific guidance reaches the model), guidance per failure type, host conditions not blamed on the program, every retryable `Stop` classified, `API_HINTS` names checked against the sandbox interpreter, generation cap, too few known terms never reach the model, no runnable code, an unreachable model, model skip |
| `test_ingest.py` | 13 | entry parsing, signed data, program splitting, b-file parsing, known-term merging and conflicts, LFS-pointer cache logic, an HTML page instead of a b-file, keyword filtering (`fini,more` kept, `full`/`dead`/`dumb`/non-`more`/no-DATA dropped), `sync` writing candidates and clearing `in_more`, sum tree sampling, weighted pick, difficulty features |
| `test_model.py` | 5 | the model client with a stubbed server: the Ollama and OpenAI request/response shapes, `ModelUnavailable` when nothing answers, and `available()` against a model listing (exact name, name before the tag, missing model, empty listing, dead server) |
| `test_db.py` | 8 | WAL + read-only reader, attempt and prediction rows, dead ends, infeasible dead ends only without a bigger budget, `record_win` rolls back as a whole, pool leaves out sequences only the model could attempt but would refuse, double-submit guard, session roll-up |
| `test_attempt.py` | 12 | orchestration with stubbed network: win with artifact and review (and stored budgets), superseded run, dead end not repeated, each per-sequence gate recording a skip and running nothing (entry missing, `more` gone, b-file lookup failing, b-file disagreeing with DATA), an infeasible dead end run again under a bigger budget, `too_few_known_terms` recorded after a failed PARI run, re-check error retried in place, unreachable re-check kept pending (blocked from attempts and picks) and later resolved as a win or as superseded, Ctrl+C during the re-check leaves a resolvable pending win, non-network errors not retried, a win surviving a failed save, pending retries surviving an unloadable pickle (inside a session too), a foreign artifact folder and a failed database write |
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
   the run log, the re-check and artifacts all happen. Respect `runner.finished`, and decide where the
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
