# Verification and feasibility estimation

`oeisbot/verify.py` runs one program in the sandbox and judges every term as it streams out.
`oeisbot/estimate.py` decides, before each new term, whether computing it fits the remaining budget.

## Term protocol

Programs report terms on stdout, one line each:

```
@T <n> <value> <cpu_us> <work> <mem_bytes>
```

| Field | Meaning |
|---|---|
| `n` | index of the term |
| `value` | the term, as a decimal integer of any size |
| `cpu_us` | cumulative CPU time of the process, in microseconds |
| `work` | cumulative instrumented work units (0 when the program has no instrumentation) |
| `mem_bytes` | memory figure for this term (meaning depends on the runtime; see below) |

Also recognized: `@DONE` (generator finished) and `@ERR <message>` (program failed; details on
stderr). Any other stdout line is ignored, apart from being kept in the diagnostics tail.

### Python programs

`oeisbot/runners/py_runner.py` is copied into the scratch directory as `runner.py`; the program is written
as `candidate.py`. The command is:

```
tools\python\python.exe -B -u -X utf8 runner.py candidate.py
```

The contract a Python program must meet:

```python
def terms(work):
    # yield (n, a(n)) for n = offset, offset + 1, ... in order, until killed
    # call work(k) to report k units of real work (candidates tested, nodes visited, ...)
```

The runner:

- loads `candidate.py` and calls `terms(work)` (a load failure or a missing `terms` → `@ERR`, exit 3);
- converts each `n` and value with `operator.index`, so `int` and `gmpy2.mpz` are accepted and a float
  raises `TypeError`;
- reports `cpu_us` from `time.process_time_ns()`. Windows updates process time in 15.6 ms steps, which
  is why cheap terms fall below the estimator's CPU floor;
- reports `mem_bytes` as the peak private bytes since the previous term, sampled every 20 ms by a
  background thread;
- turns any exception into a traceback on stderr, `@ERR <type>: <message>`, exit code 3;
- disables Python's limit on integer string conversion, so huge values print in full.

### gp programs

The PARI strategy writes the program plus a driver to `program.gp` and runs:

```
tools\pari\gp.exe -q -f -D parisizemax=<80% of the job memory cap, at least 80% of 256 MiB> program.gp
```

The drivers print `cpu_us` as `getabstime() * 1000` (millisecond resolution), `work` as the number of
candidates tested for predicate programs (0 otherwise), and `mem_bytes` as
`default(parisize) + 8 * getheap()[2]`: the current PARI stack size (which grows toward `parisizemax`
and stays grown inside the driver's loop) plus the heap. For gp runs this figure, not the job's
commit peak, is what the attempt records as peak memory (see [sandbox](sandbox.md#windows-behaviors-this-backend-works-around)).

## Budgets

From `config.Budgets` (CLI flags in parentheses):

| Field | Default | Used for |
|---|---|---|
| `verify_wall_s` (`--verify-s`) | 600 s | all known terms must be reproduced within this |
| `extend_wall_s` (`--extend-s`) | 10,800 s | time for new terms, counted from the moment verification completed |
| `max_new_terms` (`--max-new`) | 200 | stop after this many new terms |
| `mem_bytes` (`--mem-gib`) | 6 GiB | job memory cap (further limited by free RAM) |
| `over_prediction_factor` | 2.0 | kill a term running this many times past its high estimate |
| `reserve_phys_bytes` | 3 GiB | RAM kept free (see sandbox) |
| `disk_bytes` | 512 MiB | scratch directory cap |
| `reserve_disk_bytes` | 8 GiB | free disk kept |
| `session_attempt_cap` | 25 | most sequences per `oeisbot run` |

The sandbox's wall-clock limit is `verify_wall_s + extend_wall_s + 30` s (or `verify_wall_s + 30` s when
extension is off); in practice the harness's own timers stop the run first.

The harness computes its memory budget once, at start: `min(mem_bytes, free physical RAM − reserve)`.

## Checks on each term (`Harness.on_line`)

For every `@T` line, in order:

1. **Parse.** Wrong field count or non-integers → stop `protocol`.
2. **Index.** The first term must have the first known index (the entry's offset). Each later term must be
   the previous index + 1. Otherwise → stop `bad_index`, detail `program emitted n=X, expected n=Y`
   (plus the offset on the first term).
3. **Known index.** If `n` has a known value it must match exactly, else → stop `wrong_term`, detail
   `a(n) = <got>, known value <expected>` (values over 60 digits abbreviated).
4. **Classify** the term as `known`, `unchecked` (an index inside the known range with no known value;
   cannot happen through the pipeline, which rejects gappy known terms) or `new` (beyond the last known
   index).
5. **Log.** The term is appended to the run's JSONL file immediately (the value as a string). A term that
   failed steps 1–3 stopped the run before this step, so it never appears in the log.
6. **At the last known index**: if fewer than all known terms were reproduced → stop `incomplete`;
   otherwise verification is complete. With extension off → stop `verified_only`; otherwise project the
   next term.
7. **New term**: record the actual cost against the pending projection; after `max_new_terms` new terms →
   stop `max_new_terms`; otherwise project the next term.

**Nothing beyond the known terms counts unless every known term matched first**, because terms arrive
strictly in index order and the first mismatch stops the run.

### Timers (`Harness.on_tick`, every 0.25 s)

- Not yet verified and elapsed > `verify_wall_s` → stop `verify_timeout`.
- Verified and time since verification > `extend_wall_s` → stop `extend_budget`.
- The term currently being computed has run longer than its kill threshold → stop `over_prediction`.

## Stop reasons

`verify.Stop` values, which become `attempts.failure_mode`:

| Stop | Phase | Meaning | Deterministic? |
|---|---|---|---|
| `wrong_term` | verify | a known term did not match | yes |
| `bad_index` | any | first index ≠ offset, or an index was skipped or repeated. After verification the run still counts as verified and earlier new terms stand | yes |
| `protocol` | any | malformed `@T` line | yes |
| `crash` | verify | program errored (`@ERR`) or exited non-zero before verification | yes |
| `incomplete` | verify | program ended cleanly before reproducing all known terms | yes |
| `verify_timeout` | verify | known terms not all reproduced within `verify_wall_s` | no |
| `timeout` | any | sandbox wall clock | no |
| `memory_cap` | any | job memory cap, or system RAM low | no |
| `cpu_cap` | any | job CPU cap (unused by the pipeline) | no |
| `disk_cap` | any | scratch too large or free disk low | no |
| `output_cap` | any | stdout too large or a line over 1 MiB | no |
| `launch_error` | start | not enough free RAM to start, or process creation failed | no |
| `verified_only` | extend | verification done and extension was not requested | n/a |
| `infeasible` | extend | the next term's projection does not fit the remaining budget | counts as a dead end if nothing new was found, but only for runs with an extension time and memory budget no larger than the one that stopped |
| `over_prediction` | extend | a new term ran past `max(10 s, 2 × high estimate)` | no |
| `extend_budget` | extend | `extend_wall_s` used up | no |
| `max_new_terms` | extend | enough new terms | n/a |
| `finished` | extend | program ended after verification, cleanly or not (new terms before the exit still count) | n/a |

"Deterministic" failures are what `db.is_dead_end` refuses to repeat for the same program and the same
number of known terms. A verified `infeasible` run with no new terms is also refused, unless the new run
has a larger `extend_wall_s` or `mem_bytes` than the budgets stored in that attempt's `extra`; an attempt
without stored budgets never counts.

When the harness itself did not stop the run, the sandbox status decides the reason: `timeout`,
`memory_cap`, `cpu_cap`, `disk_cap`, `output_cap` and `launch_error` map to the stop of the same name.
The sandbox's own `stopped` status (a program trying to start a child process) has no mapping. The job
is terminated with exit code 1, so the attempt is recorded as `crash` ("exit code 1"), or as `finished`
after verification, and the child-process reason is lost; any exit after verification → `finished` (even a crash; its
error text is not kept in the detail); `@ERR` or a non-zero exit before verification → `crash` (detail
from `@ERR`, or the exit code and last three stderr lines); a zero exit before it → `incomplete`.

## Outcome

- `verified` is true when the last known index was reached with every known term reproduced.
- `outcome` is `extended` (verified, at least one new term), `verified` (verified, none), or `failed`.
  The orchestrator may override it to `superseded` after the live re-check, or to `recheck_pending`
  when the re-check could not reach oeis.org (see [pipeline](pipeline.md#7-re-check-and-artifact-only-when-new-terms-were-found)).
- `new_terms` lists only terms after verification.
- `weak_verification` is true when there are fewer than 10 known terms. Reproducing that few terms is
  weak evidence, and the artifact says so.
- `peak_mem_bytes` is the job's clamped peak for Python and the largest reported stack figure for gp.
- `cost_unit` is `work` if the program reported any work, else `cpu`.

## Feasibility estimation

### Cost points (`Harness.points`)

Each term after the first becomes an `estimate.Point`. The first term is excluded because it carries
interpreter start-up time.

- `cost`: the term's own work units, or its own CPU seconds when the program reported no work;
- `wall_s`: time between this term's arrival and the previous one's;
- `mem`: the term's memory figure;
- `value`: the term itself.

### Projection (`estimate.project`)

Input: `(n, cost)` pairs with cost > 0 (most recent 24). Fewer than 3 → no projection.

1. **Log space.** Work with `ln(cost)`.
2. **Parity.** If there are at least 3 points of each parity, fit a line to all points and compare the
   median residual of points with the same parity as the target `n` against the other parity. If they
   differ by more than `ln 1.5`, keep only same-parity points.
3. **Window.** Keep the most recent 12.
4. **Climbing ratio.** Compute the growth rate `Δ ln(cost) / Δn` between consecutive points. With at
   least 3 rates, fit a line to them: the ratio is climbing if the slope is positive, slope × span > 0.15,
   and at least 60% of consecutive rates increase. Climbing → **ratio model**.
5. **Otherwise** (at least 4 points) choose **exp** or **poly** by which, fitted without the newest point,
   predicts the newest point better; with fewer points use **exp**.
   - exp: `ln c = a + b·n`
   - poly: `ln c = a + b·ln(n + shift)` (shift makes indices positive)
   - ratio: fit the growth rate linearly in `n` and integrate it forward from the newest point
6. **Range.** Predict the target with the model fitted to all points (`full`) and without the newest
   point (`dropped`). `disagreement = exp|full − dropped|`. When costs have been growing, both estimates
   are floored at the newest observed cost. `low`/`high` are the two sorted; `point` is `full`.
7. **Trustworthy** when disagreement ≤ 3 and at least 4 points were used.

### Assessment (`estimate.assess`)

For the next index, given the remaining extension time and the memory budget:

- **Noise floor.** Only points with cost ≥ 50 work units (or ≥ 0.05 CPU seconds) and positive wall time
  are fitted.
- **Value-dependent** if the name matches the search pattern (`smallest|least|minimal|minimum|lowest|first|largest|greatest`
  … `such that|for which|with|where|whose|that|having|so that`), or the data say so: with at least 6
  points, `R²(ln cost ~ n) < 0.8` and `R²(ln cost ~ ln|value|)` is higher by more than 0.15.
- **Memory.** Baseline = the smallest memory figure seen; project the growth above baseline from points
  more than 1 MiB above it; `mem_high = baseline + projected high`, or 1.25 × the largest figure seen when
  growth cannot be projected.
- **No time projection** (fewer than 3 fitted points): feasible if memory fits; marked risky; no kill
  threshold, so only the extension budget limits the term.
- **Seconds.** `rate` = total wall seconds ÷ total cost over the last 5 fitted points; the point, low and
  high estimates are multiplied by it.
- **Infeasible** when any of these hold:
  - not value-dependent and `seconds_high` > remaining extension time;
  - not value-dependent, disagreement > 10, and `seconds_high` > 10% of the remaining time;
  - `mem_high` > memory budget.
- **Risky** when value-dependent, untrustworthy, or climbing. This lives only on the in-memory
  prediction: it is neither stored nor acted on.
- **Kill threshold** = `max(10 s, over_prediction_factor × seconds_high)`; none when value-dependent or when
  there is no time projection.
- **Next-term size.** `next_bits_high` = the newest term's bit length plus the number of steps × 1.5 × the
  largest per-index bit growth among the last three steps, + 1. It is computed but not stored or used;
  Python and PARI integers do not overflow.

### When projections happen

- Right after verification completes, for the first new index.
- After each new term, for the following index.

A projection judged infeasible stops the run **before** that term starts.

### Where predictions are stored

Each projection becomes a `predictions` row:

- `predicted_s`, `predicted_s_low`, `predicted_s_high`, `predicted_mem`, `model`, `trustworthy`,
  `feasible`, `value_dependent`, `cost_unit`;
- `actual_s` and `actual_mem` if that term finished;
- `censored_s` if the run stopped while that term was being computed (the term took at least that long).

Whenever a verified run ends and its last projection has no actual time and was feasible, `censored_s`
is set to the time between that projection and the end of the run. A projection that stopped the run as
`infeasible` gets no censored time, because its term never started: both `actual_s` and `censored_s`
stay NULL.

The dashboard's estimator view plots rows with a positive `predicted_s` and either an actual or a
censored time, so infeasible projections do not appear there.
