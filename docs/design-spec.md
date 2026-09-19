# Original design spec, and how the implementation follows it

Part 1 is the design spec this project was built from, kept as written (only the bullet glyphs were
converted to Markdown lists). Part 2 maps every point to where it is implemented and records each
place where the implementation deviates, and why.

---

## Part 1: the spec as written

### Purpose

A local triage tool that finds OEIS sequences needing more terms, attempts to compute them, and produces verified, reviewable artifacts. It never submits anything. The human reviews, understands the program, and submits by hand.

### Constraints

- Runs on a single laptop/desktop. All data and models stay local.
- LLM step uses a local code model (7–14B range).
- OEIS policy forbids bulk/serial automated submissions and forbids submitting AI-generated programs the submitter doesn't understand. Design accordingly: the output is a review queue, not a submission pipeline.

### 1. Ingest

- Clone oeis/oeisdata from GitHub for the full sequence database. git pull at the start of each session.
- Filter entries on the keyword line for more.
- Always fetch the b-file for each candidate: https://oeis.org/A######/b######.txt. B-files are not in the git repo. Cache permanently to disk, rate-limit to ~1 request/second. A 404 means no b-file exists, which is normal, not an error.
- The b-file is the source of truth for known terms; the DATA line shows only a few. Verifying against DATA alone risks "extending" to a term already published.
- Parse and store the offset (index of the first term). All verification is on (index, value) pairs, never bare lists. Off-by-one from a mishandled offset is the most common silent failure.
- Re-check an entry immediately before acting on a result; someone may have extended it mid-run.

### 2. Difficulty scoring and weighted selection

- Score each candidate from cheap features:
- Existing PARI or Mathematica program in the entry → strong "easy" signal (may just need running longer).
- hard keyword, very large last terms, multiple "More terms from…" credits → harder (already pushed by humans).
- Pick with probability proportional to 1/d^α; α tunable to control how strongly it favors easy targets.
- Use a sum tree if weights update after failures. random.choices is fine for a static set.

### 3. Strategy and code generation

- Classify the sequence and choose among: rerun an existing program longer, brute force, a smarter method (DP, transfer matrix), or skip.
- PARI/GP is a first-class strategy. Free, small install, millisecond startup, called as a subprocess (gp -q -f script.gp). Fast arbitrary-precision and number-theory routines. Has its own parisizemax stack cap as a second safety layer. Given a local-only model, "run existing code further" is a primary source of wins, not a fallback.
- Wolfram Engine (for the many Mathematica programs in entries) is a later experiment: multi-GB install, account activation, slow startup, restrictive license, manages its own memory so external caps are less reliable. First measure how many more sequences actually carry each program type before deciding.
- Local model emits a single function with a fixed signature that yields terms one at a time, so the harness can time each term and stop cleanly.
- On failure, retry with the actual error text. Cap at 2–3 attempts.
- Hard gate: code must reproduce every known term (from the b-file, with correct offset) before any output is trusted.

### 4. Feasibility estimation

- Fit instrumented work counts (nodes visited, states expanded) against n, not wall time. Hardware-independent and smoother. Convert to seconds via a measured rate.
- Extrapolate memory the same way as time. A job is feasible only if both projections fit budget.
- Examine ratios t(n+1)/t(n), not just the fit. A climbing ratio means super-exponential growth, which an exponential fit will badly underestimate.
- Fit odd and even n separately; many combinatorial sequences alternate in cost.
- Report a range: fit with and without the newest point. Large disagreement means the model is untrustworthy → mark risky or skip.
- Re-estimate at checkpoints during the run. Kill or deprioritize anything running >2× over prediction.
- Flag value-dependent cost ("smallest k such that…"): runtime tracks the unknown answer's size, not n, so n-based extrapolation misleads. Treat as a budgeted open search.
- Bound the size of the next term before running. Passing on known terms won't catch int64 overflow that first occurs at the new term; use Python ints or gmpy2 where needed.

### 5. Execution sandbox

Build this first — every other safeguard assumes jobs can fail safely.

- Each attempt runs in a subprocess with resource.setrlimit(RLIMIT_AS, ...) and a wall-clock timeout.
- Never let a job reach swap. Swap is the worst cliff: slow enough to stall the machine without crashing.
- The model's code is untrusted code on a personal machine. rlimits don't cover filesystem or network. Minimum: low-privilege user in a scratch directory. Better: container with no network.
- Budgets: ~10 min for verification, a few hours for an extension attempt, plus a cap on total attempts per session.
- Prefer memory-lean approaches: DFS/backtracking over BFS; generators over materialized candidate lists; numpy arrays or bitsets over Python int sets.
- Shrink state space where possible: symmetry reduction (canonical forms only). For DP/transfer-matrix, state count is computable up front — a free feasibility check.
- Checkpoint long runs to disk so a kill costs minutes, not days.

### 6. Attempts database

SQLite, WAL mode. One row per attempt: A-number, strategy, verified y/n, runtime, peak memory, projected next-term cost, outcome, failure mode, timestamp.
Feeds difficulty weights, prevents repeating dead ends, and supplies the data to check whether the estimator works.
Harness writes; dashboard only reads. WAL lets the dashboard read during a mid-write job.

### 7. Review artifact

For each success, write a folder containing:

- b-file in OEIS format with the new terms
- the program
- which known terms it reproduced
- full timing and memory record

This folder is what gets read before deciding whether the program is understood well enough to submit.

### 8. Dashboard

FastAPI + React, read-only over the SQLite database.

- Estimator accuracy — predicted vs actual cost, log-log scatter. Build this view first; it's what tells you whether step 4 works at all.
- Queue — candidates with difficulty score, pick weight, available program types. Sortable, to sanity-check the weighting.
- Attempts — all runs, filterable by failure mode. Counts of timeout vs memory cap vs wrong terms vs crash show what to fix next.
- Review inbox — successes linked to artifact folders, with status (new / reviewing / submitted / rejected) so nothing gets submitted twice.
- Run history — attempts and wins over time, machine hours spent.

### Build order

1. Subprocess sandbox with resource limits
2. Verification harness: run any program against known terms under limits, output verified-or-not
3. Work-count instrumentation + cost/memory projection
4. Attempts database
5. Ingest + difficulty scoring + weighted pick
6. PARI/GP strategy
7. Local model code generation
8. Dashboard (estimator-accuracy view first)

### Expected outcome

A trickle, not a flood. Many more sequences are stuck because the next term is genuinely expensive; the easy ones get taken by humans quickly.

---

## Part 2: implementation map and deviations

Status: **Done** = implemented as specified. **Changed** = implemented differently (reason given).
**Partial** = part of the point is implemented. **Not done** = not implemented.

### Constraints

| Spec point | Status | Where | Notes |
|---|---|---|---|
| Single machine, data and models local | Done | whole project | Only outbound traffic: GitHub (oeisdata clone), oeis.org (b-files, entry re-check), one-time runtime downloads, Ollama model pull. |
| Local 7–14B code model | Done | `oeisbot/model.py` | `qwen2.5-coder:14b` via Ollama by default. |
| Output is a review queue, never a submission | Done | `artifact.py`, `db.reviews`, CLI | Nothing in the code can submit. Review status is set by hand with `oeisbot review set`. |

### 1. Ingest

| Spec point | Status | Where | Notes |
|---|---|---|---|
| Clone oeisdata; `git pull` each session | Changed | `ingest/oeisdata.py` | Shallow clone (`--depth 1`); updates use `git fetch --depth 1` + `git reset --hard FETCH_HEAD` because shallow pulls are fragile. Updating is a separate command (`oeisbot sync`), not automatic at session start. On Windows git is run with `-c http.sslBackend=schannel`. |
| Filter on keyword `more` | Changed | `oeisdata.iter_more_entries` | Also excludes entries with `dead`, `full`, `allocated`, `recycled`, `dumb`, and entries without DATA. `fini` entries were excluded too until 2026-09-17, which dropped 186 finite-but-incomplete sequences. |
| Always fetch the b-file; cache permanently; 1 req/s; 404 = no b-file | Changed | `ingest/bfile.py` | The oeisdata repo carries a Git LFS pointer file (sha256 + size) for every supporting file, b-files included. No pointer means no b-file, so no request is made. A cached copy is reused only while its sha256 matches the pointer. Fetching is lazy: when a sequence is attempted, or in bulk with `oeisbot fetch-bfiles`. A 404 always writes an `.absent` marker, but the marker is consulted only when no oeisdata snapshot exists. |
| B-file is the source of truth | Done | `bfile.known_terms` | B-file values win; DATA terms beyond the b-file are merged; any DATA/b-file disagreement, gap, duplicate index or unexplained offset mismatch skips the sequence. |
| Parse offset; verify (index, value) pairs | Done | `seqfile.parse`, `verify.Harness.on_line` | The first emitted index must equal the first known index; every later index must be the previous + 1. |
| Re-check before acting on a result | Changed | `attempt.recheck` | Done right before a win is recorded (live b-file + live entry text from oeis.org), not before starting a run. The run is recorded as `recheck_pending` and its result saved before the re-check; network errors are retried twice in place, and a re-check that does not finish is retried later (`oeisbot recheck`, or the next `oeisbot run`). No artifact is written before a re-check succeeds. |

### 2. Difficulty scoring and weighted selection

| Spec point | Status | Where | Notes |
|---|---|---|---|
| Cheap-feature difficulty score | Done | `select.difficulty` | Program present (PARI ×0.3, Python ×0.45, Sage ×0.5, else Mathematica ×0.6, Maple ×0.7), `hard` ×6, large last term, "More terms" credits, plus two extra features: value-dependent name ×1.5 and number of known terms. |
| Pick ∝ 1/d^α, α tunable | Done | `select.weight`, `--alpha` | |
| Sum tree when weights update after failures | Partial | `select.SumTree`, `select.candidates` | The sum tree is used for weighted sampling without replacement. Failure penalties (×2 per earlier attempt with a failed or verified-without-new run, counted once per attempt however many programs it ran, capped ×64) are applied when the pool is built, so they take effect in the **next** session, not during the current one. |

### 3. Strategy and code generation

| Spec point | Status | Where | Notes |
|---|---|---|---|
| Classify; choose rerun / brute force / smarter method / skip | Changed | `attempt.attempt_sequence`, `strategies/codegen.py` | No up-front classifier for the whole sequence. The entry's own PARI programs are always tried first; the model's classification step (brute_force, search, dp_or_transfer_matrix, formula, skip) happens only on the model path. |
| PARI/GP first-class, `gp -q -f`, `parisizemax` | Done | `strategies/pari.py`, `verify.Harness.argv` | `gp.exe -q -f -D parisizemax=<80% of the job memory cap> program.gp`. Supports `a(n)` functions, predicates, and single print loops (rewritten). |
| Wolfram Engine deferred; measure program types first | Done | `oeisbot stats` | Measured on the 2026-09-17 snapshot: of 26,814 `more` candidates, 54% have no program, 31% Mathematica, 20% PARI; 5,282 have Mathematica but not PARI. Wolfram Engine not integrated. |
| Model emits one generator with a fixed signature | Done | `runners/py_runner.py` | `def terms(work)` yielding `(n, a(n))`; `work(k)` reports instrumented work. For a sequence the model judges to be a list of numbers with a property (known terms strictly increasing), `def members(work)` yielding the members instead, which an appended driver (`codegen.MEMBERS_DRIVER`) numbers into `terms(work)`. |
| Retry with actual error text, cap 2–3 | Done | `codegen.generate_and_verify` | 3 generations. Retries carry only the latest attempt and its failure; temperature rises 0.2 → 0.5 → 0.8. A program repeating one that already failed in the stage in a way that would recur there (the same way every time, or by running out of the stage's verify budget) is not run, and uses up its generation. |
| Hard gate: reproduce every known term with correct offset | Done, extended | `verify.py`, `codegen.py` | Extended after the model was caught hard-coding known terms: the model is shown at most 30 terms, at most `max(3, ⌊0.6 × count⌋)`, and always at least 2 fewer than are known; sequences with fewer than 3 known terms are not given to the model. Programs with ≥6 known values as literals are rejected, and held-out values are never revealed in retries. |

### 4. Feasibility estimation

| Spec point | Status | Where | Notes |
|---|---|---|---|
| Fit work counts vs n; convert via measured rate | Done | `estimate.assess` | Work counts when the program reports them, CPU seconds otherwise. Rate = wall seconds per cost unit over the last 5 fitted terms. The rate is also projected to the next term (`rate_drift`); it is not used to correct the estimate, only to withhold trust (next rows). |
| Extrapolate memory; feasible only if both fit | Done | `estimate.assess` | |
| Examine ratios; climbing ratio = super-exponential | Done | `estimate._is_climbing` | Switches to a ratio-extrapolation model. |
| Fit odd and even n separately | Done | `estimate._parity_series` | Only when the two parities' costs actually differ (median residuals > ×1.5 apart). |
| Range from fits with/without the newest point; disagreement → risky/skip | Changed | `estimate.project`, `estimate.assess` | Disagreement > 3× (or fewer than 4 fitted points) → untrustworthy (risky), and then no over-prediction kill (next row) and no infeasible stop on time: "skip" was dropped on 2026-09-19 (offer F), after a replay showed such fits stopping terms that finished within the budget (the rule was: > 10× and not negligible against the budget → infeasible). |
| Re-estimate at checkpoints; kill > 2× over prediction | Changed | `verify.Harness._project_next`, `on_tick`, `estimate.Assessment.kill_after_s` | Re-estimated after every new term. A term running longer than max(10 s, 2 × high estimate) is killed, but only when that projection is trusted (since 2026-09-18): its cost fit is trustworthy (in session 5 the kill ended two of three verified runs within half a minute, both on untrustworthy projections), and its rate is not projected to drift more than 2× by the next term (a replay of the real term logs showed trustworthy work-unit projections killing terms that took 14× and 66× their high estimate). Otherwise only the extension budget stops the term. |
| Flag value-dependent cost; budgeted open search | Done | `estimate.name_suggests_search`, `_value_dependent_by_data` | Value-dependent terms are never judged infeasible by time and never killed for over-prediction; only the extension budget stops them. |
| Bound the next term's size | Partial | `estimate._bits_bound` | Computed on every projection but not stored or acted on. Both runtimes use arbitrary-precision integers (Python int, gmpy2, PARI), so int64 overflow cannot happen in the programs the pipeline runs today. |

### 5. Execution sandbox

| Spec point | Status | Where | Notes |
|---|---|---|---|
| Subprocess with `setrlimit(RLIMIT_AS)` + wall timeout | Changed | `sandbox/windows.py` | The machine runs Windows 11 without WSL or Docker, where `setrlimit` does not exist. A Windows Job Object enforces a hard commit-charge cap, one process, kill-on-close and below-normal priority; the harness enforces wall clock. A `setrlimit` backend exists (`sandbox/posix.py`) but has never run. |
| Never reach swap | Done | `sandbox/windows.py` | Job cap = min(6 GiB, free physical RAM − 3 GiB) at launch; any job is stopped if free physical RAM falls below 1.5 GiB. |
| Filesystem/network isolation (low-privilege user or container) | Changed (stronger) | `sandbox/windows.py`, `setup_tools.grant_access` | AppContainer with no capabilities: no network (loopback included), filesystem access only where the container SID is granted (read: sandbox runtimes; write: scratch). |
| Budgets: ~10 min verify, a few hours extend, session cap | Changed | `config.Budgets` | 60 s, 3 h, 25 sequences per session. Verification was 600 s until 2026-09-18; real runs showed that time past a minute bought almost nothing (the programs that passed did so within 2.6 s), so the verify budget is now a quick first pass and a program that times out is revisited only with a larger `--verify-s`. |
| Memory-lean approaches | Partial | model prompt | Stated as rules in the code-generation prompt; not enforced (the memory cap is the enforcement). |
| Symmetry reduction; up-front state counts | Not done | | Would belong in specific strategies; none implement it. |
| Checkpoint long runs to disk | Partial | `verify.Harness._log` | Every term is appended to `data/runs/*.jsonl` as it arrives, so finished terms survive a kill. Program state is not checkpointed and runs cannot be resumed. |

### 6. Attempts database

| Spec point | Status | Where | Notes |
|---|---|---|---|
| SQLite WAL; one row per attempt with the listed fields | Changed | `db.py` | One row per program run: an attempt of a sequence writes one per PARI run or model generation and at most one skip row, which has no key; its run rows share `extra.attempt_call`, which is what the failure penalty counts. Plus `predictions` (per projected term), `reviews`, `sessions`, `sequences`, `meta`. |
| Feeds difficulty weights | Done | `select.candidates` | Failure penalty (applied at next session). |
| Prevents repeating dead ends | Done | `db.is_dead_end`, `attempt.Runnable` | Same program (sha256) + same number of known terms + deterministic failure, or verified-but-infeasible under an extension time and memory budget at least as large as the current run's, or verified with its whole extension time (at least the current run's) used up without a new term, on at least 80% CPU, or a verify timeout after at least the current verify budget. Neither verified kind holds back the entry's other PARI programs (since 2026-09-19): they get their turn in later attempts. Selection also leaves out sequences whose programs are all dead ends. |
| Data to check the estimator | Done | `predictions` table, dashboard | |
| Harness writes; dashboard reads | Done | `dashboard/app.py` | Dashboard opens `mode=ro` connections; tested to never write. |

### 7. Review artifact

| Spec point | Status | Where | Notes |
|---|---|---|---|
| b-file with new terms, program, reproduced terms, timing and memory | Done | `artifact.py` | Also: the exact executed script (driver included), per-term predictions, run/budget JSON, and a README with warnings (weak verification, rewritten program, AI-generated, hard-coded bounds) and a pre-submission checklist. |

### 8. Dashboard

| Spec point | Status | Where | Notes |
|---|---|---|---|
| FastAPI + React, read-only | Done | `oeisbot/dashboard/app.py`, `dashboard/` | |
| Estimator accuracy, log-log | Done | Estimator accuracy tab | Stopped-before-finishing terms shown hollow (lower bounds). |
| Queue, sortable | Done | Queue tab | α adjustable in the page. |
| Attempts filterable by failure mode | Done | Attempts tab | Click a bar to filter; separate chart for skip reasons. |
| Review inbox with status | Done | Review inbox tab | Read-only; status is changed with the CLI. Artifact files viewable in the page. |
| Run history | Done | Run history tab | Runs and wins per day, machine hours per day, sessions table. |

### Build order and expected outcome

The build order was followed as listed. The expected outcome has held so far: 17 sequences attempted
across two sessions and a few manual attempts on 2026-09-17, zero wins. See
[known limitations](known-limitations.md#observations-from-real-runs).
