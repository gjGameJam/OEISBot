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
stderr). Any other stdout line is ignored, apart from being kept in the diagnostics tail — including a
line on which a program's own unterminated output precedes the driver's `@T` (A373945's `print1` put
`0, 1, ` before every term line in session 11), so such a run records no term and ends as an ordinary
`verify_timeout`; see [known limitations](known-limitations.md#strategies). An `@ERR`
whose message starts with `OEISBotContractError:` (`verify.CONTRACT_ERROR`, raised by the list
contract's driver) stops the run as `protocol` and turns every new term recorded so far into kind
`void`, so none counts: the program's order is wrong somewhere. The run log keeps them as they
arrived, as `new`. Once a run has stopped for any other reason the harness reads no more lines, so a
violation that would have come later is never seen.

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

A model program for a list of numbers defines `members(work)` instead, and the strategy appends a driver
that defines this `terms(work)` from it: it numbers the members from the offset and raises
`OEISBotContractError` on a pair or on a value not larger than the one before (see
[strategies](strategies.md#the-list-contract-memberswork)). The runner sees an ordinary `terms(work)`;
the harness treats that error specially (next section).

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
| `verify_wall_s` (`--verify-s`) | 60 s | all known terms must be reproduced within this. Short on purpose: it is the quick first pass, and the long extension budget is only spent on programs that pass it (600 s until 2026-09-18) |
| `extend_wall_s` (`--extend-s`) | 10,800 s | time for new terms, counted from the moment verification completed |
| `max_new_terms` (`--max-new`) | 200 | stop after this many new terms |
| `mem_bytes` (`--mem-gib`) | 6 GiB | job memory cap (further limited by free RAM) |
| `over_prediction_factor` | 2.0 | kill a term running this many times past its high estimate, when the projection is trusted; also the most a trusted projection's rate may drift (see [assessment](#assessment-estimateassess)) |
| `reserve_phys_bytes` | 3 GiB | RAM kept free (see sandbox) |
| `disk_bytes` | 512 MiB | scratch directory cap |
| `reserve_disk_bytes` | 8 GiB | free disk kept |
| `session_attempt_cap` | 25 | most sequences per `oeisbot run` |

The sandbox's wall-clock limit is `verify_wall_s + extend_wall_s + 30` s (or `verify_wall_s + 30` s when
extension is off); in practice the harness's own timers stop the run first.

The harness computes its memory budget once, at start: `min(mem_bytes, free physical RAM − reserve)`.

## Checks on each term (`Harness.on_line`)

For every `@T` line, in order:

1. **Parse.** Wrong field count or non-integers → stop `protocol`. So is any *counting* field longer than
   `verify.MAX_TERM_FIELD_DIGITS` (40): the index, the microseconds, the work units and the bytes. The
   term's own **value is exempt**, because OEIS terms are legitimately unbounded — it is why `verify.py`
   lifts Python's own `int`/`str` digit limit at import.

   The length check runs *before* `int()`, not after, and that ordering is the point. `on_line` runs in
   the sandbox's stdout reader thread, which has no exception handler: an `OverflowError` out of the
   float conversions a `TermRecord` needs (`cpu_us / 1e6`, `float(mem)`, `float(dwork)`) would kill the
   thread, stop the drain loop that keeps the child from blocking on a full pipe, and lose the reason the
   run failed. A program controls these fields directly — `py_runner` hands the candidate module the same
   stdout, and a gp program can `print` whatever it likes. 40 digits leaves every honest quantity ~20
   orders of magnitude of headroom and still sits ~268 digits below the point where `float()` overflows.

   This closes the overflow entirely; it does **not** close the quadratic-`int()` stall, because the
   value field is exempt — see [known limitations](known-limitations.md#term-lines-from-an-untrusted-program).
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
6. **At the last known index**: verification is complete. The guard here for "fewer than all known terms
   reproduced" (→ stop `incomplete`) cannot fire: steps 1–3 force consecutive indices and halt on the
   first value that differs, so every known index has been emitted and matched by the time the last one
   arrives. It is kept so that state could never be treated as verified. With extension off → stop
   `verified_only`; otherwise the [searched-bound check](#the-searched-bound-check) runs, and if it does
   not stop the run, the next term is projected.
7. **New term**: record the actual cost against the pending projection; after `max_new_terms` new terms →
   stop `max_new_terms`; otherwise project the next term.

**Nothing beyond the known terms counts unless every known term matched first**, because terms arrive
strictly in index order and the first mismatch stops the run.

### Timers (`Harness.on_tick`, every 0.25 s)

- Not yet verified and elapsed > `verify_wall_s` → stop `verify_timeout`.
- Verified and time since verification > `extend_wall_s` → stop `extend_budget`.
- The term currently being computed has run longer than its kill threshold (only trusted projections
  have one, see [assessment](#assessment-estimateassess)) → stop `over_prediction`.

### The searched-bound check

Many `more` entries publish, in a `%C` comment, a range a human has already searched and found empty:
`No more terms <= 2 * 10^38` (A194099), `a(29) > 10^13`, `Any subsequent terms are > 10^12`. The pipeline
already parses those lines (`Entry.comments`). Once verification completes, and before any extension time
is spent, `Harness._bound_exhausted` compares such a bound against the rate the run has just demonstrated:

```
X - last_known_value > SEARCHED_BOUND_MARGIN * measured_rate * extend_wall_s   ->  stop searched_bound
```

`measured_rate` (`verify.measured_rate`) is work per second over `records[-1]` minus `records[0]`. The
first record is dropped for the same reason `Harness.points` drops it -- it carries interpreter start-up,
which for gp is most of a short verification -- and because including it *understates* the rate, which
would make the skip fire more often. `config.SEARCHED_BOUND_MARGIN` is 10.

**Predicate form only.** Only there do term values equal the driver's work count: the driver tests
k = `search_start`, `search_start`+1, ... and the terms *are* the k that pass, so a bound on a value is a
bound on work. For the other two forms the loop variable need not be the term value at all -- A038582's
terms are `k` (numbers whose first k primes sum to a palindrome) while A038583's are those sums, the same
search with opposite mappings -- and `work` is hard-coded to 0 in both drivers, so there is no rate to
measure. `attempt._Attempter.run` supplies a bound only for `pari:predicate`. The `work > 0` guard in the harness
backs that up for the other two **PARI** forms, whose drivers report a literal zero; it cannot back it up
for a model program, whose runner reports a positive work count in whatever unit that program counts, so
for the model form the gate in `attempt` is the only thing standing between a bound and a meaningless
comparison. `tests/test_bounds.py` asserts all four forms.

The check cannot fire without a bound, a positive extension budget, at least two term records, a positive
measurement window and a positive gap. Every one of those guards exists because its absence produced a
measured error while the feature was being sized; the table in
[known limitations](known-limitations.md#searched-bounds) lists what it still gets wrong.

**A bound is an unverified human claim.** It is only ever used to decline to spend time. It never decides
a term's value or index, and it is never evidence that a term is correct -- that rule is why the check
lives after verification (which is evidence) rather than replacing any part of it. The stop's `detail`
names only the bound and the budget: it reaches the model through `codegen.slow_program_note`, whose
contract is timing and the stop reason but never a term value, and publishing the rate and margin beside
the bound would let the held-out last known term be recovered by arithmetic. The rate, the window, the
quote and `verified_scan_to` -- how far this run's own scan actually reached, which is the part that is
*not* a claim -- go to the attempt's `extra` instead.

**A new term inside the range the bound calls empty is flagged, never refused** (2026-09-30, history
item 51). When a run with an applicable bound emits a new term whose value is at or below the bound,
`Harness.below_bound` records its index; the attempt's `extra.below_published_bound` carries the bound,
the quoted comment and the indices; the console prints a `WARNING`; and the artifact README and the
dashboard inbox say the two disagree. The term stays a term and the run goes on, because the doubt cuts
both ways — the published search may be the wrong one — and only a human can say which. This is the safe
direction of invariant 10: a published claim may cast doubt on a term and must never confirm one. No
real case exists yet; `tests/test_bounds.py` drives it synthetically.

## Progress heartbeats (predicate form only)

The predicate driver used to print only when the predicate was **true**, so a run killed mid-scan had
emitted nothing since its last term and where its scan reached was unrecoverable. Across the 49 predicate
runs that ended at `verify_timeout` or `extend_budget`, 30,312 s of scan position was thrown away that
way, and every re-pick began again at `search_start`. Only **21,002 s** of that is recoverable by
resuming *above* the known terms (14 runs over 13 sequences): the 35 `verify_timeout` runs never
reproduced the known terms, so their frontier lies below the last known value.

The scan now runs in blocks and prints `@P <k reached> <predicate calls made> <cpu us>` after each one.
The block is sized in **time**, not in k: it doubles while a block comes in under
`pari.HEARTBEAT_TARGET_MS` and halves when one overruns it fourfold, so the cadence holds whether a call
costs 0.2 us or 10 ms. A block fixed in k cannot do that, and one that only grew could swallow hours in a
single step -- losing exactly the progress the heartbeat exists to keep.

`verify.Harness` accepts a heartbeat only when all of these hold, and **drops the line rather than
halting** when they do not: a heartbeat can never make a term, so killing a sound run over a defect in a
progress report would be a self-inflicted wound. Each refusal is a case where believing the line would
later let a run skip a range that was never scanned:

| Refused when | Why |
|---|---|
| the caller passed no `ScanTracking` | only the predicate driver emits these by contract; the caller gate is in `attempt._Attempter.run`, and this is the mechanical half of the same two-gate pattern the searched-bound check uses |
| the line is over `MAX_HEARTBEAT_CHARS` | `int()` is quadratic and this runs in the sandbox's reader thread, which holds the same lock as `on_tick`: a program spraying huge numbers would stall the very clocks that kill it |
| malformed, or not four fields | as above -- dropped and counted, never fatal |
| `k - start + 1 != tested` | this driver tests every k from `start`, so the position and the work are one fact twice. A frontier that does not match the work claimed for it did not come from the driver we built |
| `tested <= 0` | a frontier that claims no work |
| not strictly beyond the frontier so far | it only ever moves forward |
| behind a term already emitted | a term at k proves the driver tested k |
| `tested` implies a rate above `pari.PREDICATE_MAX_RATE` | the same ceiling `out_of_reach` is built on, with gp's start-up granted because the harness clock counts it and the scan does not |

The result carries `scan_reached`, `heartbeats` and `heartbeats_ignored` (plus the first bad line), and
`attempt.py` writes them to the row's `extra`. The ignored count exists so that a driver bug mangling
every line shows up as a number rather than as silence -- otherwise the frontier would simply never move
and nothing would say why.

**What the frontier is worth.** It is *ours* but **reported**, not witnessed: the harness cross-checks it
against the work claimed and the fastest rate a predicate can be tested at, but it is still the program's
own word, and the program is untrusted. That is a step below `verified_scan_to`, where the harness
watched every known term arrive from the range, and a step above `searched_bound`, which is a human
claim. **Nothing consumes the frontier, and nothing is meant to**: recording it made the resume question
a measurement rather than a guess, and on 2026-09-23 the user took the decision — **not** to build
resume (history item 42). Do not build it without new evidence.

## Stop reasons

`verify.Stop` values, which become `attempts.failure_mode`:

| Stop | Phase | Meaning | Deterministic? |
|---|---|---|---|
| `wrong_term` | verify | a known term did not match | yes |
| `bad_index` | any | first index ≠ offset, or an index was skipped or repeated. After verification the run still counts as verified and earlier new terms stand | yes |
| `protocol` | any | malformed `@T` line, or a list-contract program yielding a pair or a value out of order (`OEISBotContractError`; after verification its new terms are voided) | yes |
| `crash` | verify | program errored (`@ERR`, other than `OEISBotContractError`) or exited non-zero before verification | yes |
| `incomplete` | verify | the program ended by itself before reproducing all known terms — always that, since the guard at the last known index cannot fire (step 6 above) | yes |
| `verify_timeout` | verify | known terms not all reproduced within `verify_wall_s` | no, but counts as a dead end for runs with a `verify_wall_s` no larger than the time it already ran |
| `timeout` | any | sandbox wall clock | no |
| `memory_cap` | any | job memory cap, or system RAM low | no |
| `cpu_cap` | any | job CPU cap (unused by the pipeline) | no |
| `disk_cap` | any | scratch too large or free disk low | no |
| `output_cap` | any | stdout too large or a line over 1 MiB | no |
| `launch_error` | start | not enough free RAM to start, or process creation failed | no |
| `harness_error` | any | **our own** `on_line` or `on_tick` raised inside the sandbox (`Status.CALLBACK_ERROR`, since 2026-09-30, history item 51); the detail names the exception. A harness bug, never the program's doing | **no, deliberately**: outside `db.DETERMINISTIC_FAILURES`, so a bug of ours cannot retire a program for ever |
| `verified_only` | extend | verification done and extension was not requested | n/a |
| `searched_bound` | extend | the entry publishes a searched range with no further term in it, and the extension cannot reach the end of it at the rate measured while verifying (predicate form only; see [above](#the-searched-bound-check)) | **no, and deliberately not a dead end**: nothing about the sequence has been disproved, so the program stays runnable. `extra.verified_scan_to` records how far this run's own scan reached |
| `infeasible` | extend | the next term's projection does not fit the remaining budget: a trustworthy cost fit's time, or the memory. `extra.infeasible_on` says which (`time`, `memory` or `time+memory`; since 2026-09-30, history item 51) | counts as a dead end if nothing new was found, but only for runs whose budget *for the reason recorded* is no larger than the one that stopped: a verdict on time holds under any memory cap and one on memory under any extension time; rows without the key need both |
| `over_prediction` | extend | a new term ran past `max(10 s, 2 × high estimate)` of a trusted projection | no |
| `extend_budget` | extend | `extend_wall_s` used up | no, but counts as a dead end if nothing new was found and the job had at least 80% CPU, for runs with an extension time no larger than the one it used up |
| `max_new_terms` | extend | enough new terms | n/a |
| `finished` | extend | program ended after verification, cleanly or not (new terms before the exit still count) | n/a |

"Deterministic" failures are what `db.is_dead_end` refuses to repeat for the same program and the same
number of known terms. A verified `infeasible` run with no new terms is also refused, unless the new run
has a larger `extend_wall_s` or `mem_bytes` than the budgets stored in that attempt's `extra`; an attempt
without stored budgets never counts. A verified `extend_budget` run with no new terms is refused too,
unless the new run has a larger `extend_wall_s` than the one stored (memory is not compared: running out
of memory ends a run as `memory_cap`, or as `finished` when gp's stack overflows, never as
`extend_budget`); it counts only if the job's CPU time was at least 80% of its wall time
(`db.EXTEND_DEAD_END_MIN_CPU_SHARE`; the nine real runs had 93–99%), so an extension spent on a busy
machine does not make a dead end. A `verify_timeout` run is refused unless the new run has a
`verify_wall_s` larger than that attempt's `runtime_s`: the program already ran that long without
reproducing the known terms. (The sandbox's own `timeout` never counts.) Model programs are not checked
here; within one model stage, a program the model sends again after a deterministic failure or a
`verify_timeout` is not run (see [strategies](strategies.md#steps)).

Why the verify budget is short: in the 16 PARI runs recorded before this change, the 3 that reproduced
their known terms did so within 2.6 s, and in 11 of the 13 that timed out the cost per term jumped by 10×
or more at the edge of the known terms (A272621's last three terms cost 1.4 s, 36 s and 417 s, and two
were still missing at 600 s; the exceptions are A309238 and A265383, whose next term was not reached
within 1.6× and 4.4× of the previous one's cost before the budget ran out). A longer budget bought almost
nothing.

When the harness itself did not stop the run, the sandbox status decides the reason: `timeout`,
`memory_cap`, `cpu_cap`, `disk_cap`, `output_cap` and `launch_error` map to the stop of the same name;
`callback_error` (our own callback raised, since 2026-09-30) maps to `harness_error`.
The sandbox's own `stopped` status (a program trying to start a child process) has no mapping. The job
is terminated with exit code 1, so the attempt is recorded as `crash` ("exit code 1"), or as `finished`
after verification, and the child-process reason is lost; any exit after verification → `finished` (even a crash; its
error text is not kept in the detail); `@ERR` or a non-zero exit before verification → `crash` (detail
from `@ERR`, or the exit code and last three stderr lines); a zero exit before it → `incomplete`
(detail: how many terms came out, then those same three stderr lines when the program said anything).

### The stderr tail in a detail

Every tail comes from `verify._stderr_tail`, which keeps the last three lines that say something, joined
with `" | "` and each cut to `STDERR_LINE_CHARS` (400). Blank lines and rules are dropped: gp underlines
the offending call with a caret rule on a line of its own, and keeping it would push out the line that
names the call. The per-line cap matters because the 64 KiB `stderr_tail` need not contain a line break
at all, and a detail is stored, shown in the dashboard and sent to the model.

Which stops carry one is a fixed list, `verify._TAIL_STOPS`: `incomplete` always, and `verify_timeout`,
`timeout`, `memory_cap`, `cpu_cap`, `disk_cap` and `output_cap` when the run produced no term at all. Those are the stops that do not themselves say why the program produced what it did. The
others are left alone deliberately — `crash` puts the tail in its own detail, `protocol`, `bad_index` and
`wrong_term` name the line, index or value at fault, `launch_error` never ran a process so there is no
stderr to keep, and after verification the terms are the evidence —
and a stop added to `Stop` belongs in the list only if the same is true of it.

`incomplete` is the case that needs this most, because a program can fail and still exit 0: gp prints its
error to stderr, skips the rest of the file and leaves with status 0, so the run is `incomplete` rather
than `crash` and, without the tail, nothing in the database, the artifact or the session log says why no
term came out. A gp program calling a helper that is defined in some other OEIS entry reads:

```
incomplete: program ended after 0 terms: ***   at top-level: print(A007947(3)) | ***   not a function
in function call | ... skipping file 'program.gp'
```

That particular family no longer reaches a run: since 2026-09-20 a PARI block calling another entry's
helper is rejected statically (see [strategies](strategies.md#programs-that-call-another-entrys-helper)).
The tail still earns its place on everything the static check cannot see — a helper reached only down a
branch, an internal limit, a gp warning before a silent stop.

A session log line carries `verify.brief_detail(detail)`: the first `CONSOLE_DETAIL_CHARS` (300)
characters, with `...` when it had to cut. Both places that log a stop use it — the per-attempt line in
`attempt` and the per-generation line in `codegen` — so a model run's failure is not cut shorter than a
PARI one's. The real `incomplete` details of A147803 and A147800 are 178 characters, so they arrive
whole; at 160 the cause was visible but the sentence was cut.

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
7. **Trustworthy** when disagreement ≤ 3 and at least 4 points were used. This judges the cost fit only.
   Only a trustworthy fit can make a term infeasible on time; whether the kill may act on the projection
   also depends on the conversion to seconds (`trusted`, in the
   [assessment](#assessment-estimateassess)).

### Assessment (`estimate.assess`)

For the next index, given the remaining extension time and the memory budget:

- **Noise floor.** Only points with cost ≥ 50 work units (or ≥ 0.05 CPU seconds) and positive wall time
  are fitted.
- **Value-dependent** if the name matches the search pattern (`smallest|least|minimal|minimum|lowest|first|largest|greatest`
  … `such that|for which|with|where|whose|that|having|so that`), or the data say so: with at least 6
  points, `R²(ln cost ~ n) < 0.8` and `R²(ln cost ~ ln|value|)` is higher by more than 0.15.
- **Memory.** Baseline = the smallest memory figure seen; project the growth above baseline from points
  more than 1 MiB above it; `mem_high = baseline + projected high`, or 1.25 × the largest figure seen when
  growth cannot be projected. **The budget it is compared with depends on the runtime** (since
  2026-09-30, history item 51): a Python program's figure is its process memory and is judged against
  the job cap (`Harness.mem_cap`); a gp program's figure is `default(parisize) + heap`, the PARI stack,
  and is judged against the stack ceiling gp was launched with (`Harness.stack_cap` = `parisizemax` =
  0.8 × the cap), which is what that figure can actually exhaust. Before this every gp figure was
  compared with the job cap, ~800× larger, so no gp run could be judged infeasible on memory.
- **No time projection** (fewer than 3 fitted points): feasible if memory fits; marked risky; no kill
  threshold, so only the extension budget limits the term.
- **Seconds.** `rate` = total wall seconds ÷ total cost over the last 5 fitted points; the point, low and
  high estimates are multiplied by it.
- **Rate drift.** The same 5 points' own rates (wall seconds ÷ cost) are fitted as `ln rate = a + b·n` and
  projected to the next index; `rate_drift` = that projected rate ÷ `rate`. It is about 1 when every cost
  unit takes as long as the last, and large when each unit keeps getting dearer: in "numbers k such that
  8191·2^k + 1 is prime" (A377248) work counts the candidates k, and each primality test grows with k, so
  a(7)'s rate drift was 11. The estimate in seconds is then low. It is not corrected: every correction
  tried on the real term logs judged more terms infeasible that would have finished within the budget,
  and such a stop gives the term up before it starts. Only trust is withdrawn (next point). The drift
  depends on how the cost is weighted: a rate growing 1.5× per term drifts 1.95 by the next term when
  the cost doubles per term (still trusted at the default factor of 2), and 2.9 when the cost is flat.
- **Trusted** (`Assessment.trusted(factor)`, with `factor` = `over_prediction_factor`): the cost fit is
  trustworthy (disagreement ≤ 3, at least 4 points) and `rate_drift ≤ factor`. A larger drift alone would
  carry a correct term past the kill. The stored `predictions.trustworthy` is this flag, and when only the
  drift withdrew it, the prediction's reasons say so (`drift_note`).
- **Infeasible** when either holds:
  - not value-dependent, the cost fit is trustworthy (disagreement ≤ 3, at least 4 points), and
    `seconds_high` > remaining extension time;
  - `mem_high` > memory budget.

  An untrustworthy cost fit is not judged on time (since 2026-09-19, offer F): its term runs, with no kill
  either, until it arrives or the extension budget is used up. When its `seconds_high` exceeds the
  remaining time, a reason says so ("... but the fit is untrustworthy: not judged infeasible on time").
  The trust is the cost fit's, not `trusted`: a fit that only the rate drift withdraws from the kill is
  still judged on its high end, since a drifting rate makes the seconds too low, not too high. Before
  offer F an untrustworthy fit stopped the run on its high end too, and also on a disagreement over 10
  with `seconds_high` above 10% of the remaining time. Replayed on every term log (each known term
  projected from the ones before it as if it were the first new term, at budgets of 60, 120, 300, 1800
  and 10,800 s), 33 of the 34 stops those rules made were on untrustworthy fits: 9 stopped a term that
  finished within the budget (A274508's a(16), A350878's a(14) and a(15), which took 0.3 to 8 s against
  high estimates of 122 to 204 s), 7 a term that took longer. Of the 28 finished projections (per run
  log) whose fit was untrustworthy, 10 took less than the low estimate and 14 more than the high one.
  The price: a run whose projection is untrustworthy spends its whole remaining extension when the term
  does not come, and then ends as `extend_budget`.

  **Measured on a real run for the first time on 2026-09-21, and it paid for itself.** In attempt #139
  (A385331, the project's first win) the pre-offer-F rule would have stopped the extension at six
  consecutive projections — n = 33 to 38, with `seconds_high` of 3.49e+08, 1.9e+09, 1.03e+10, 5.63e+10,
  3.06e+11 and 3,737 s against 1,221-1,279 s remaining. The n=33 projection amounts to eleven years for a
  term that cost **0.0006 s**. Offer F let all six through, and the run went on to produce 18 new terms
  instead of the 8 it would have kept. The seventh, at n=43, was on a *trustworthy* fit, so offer F did
  not shield it and the run stopped — correctly: a(43) has no prime factor below 2x10^8, which by the
  run's own cost law puts it at >= 1,626 s against the 1,068 s it had left. See
  [status](status.md#history-condensed) history item 35.
- **Risky** when value-dependent, the cost fit is untrustworthy, or climbing (the rate drift does not
  enter it). This lives only on the in-memory prediction: it is neither stored nor acted on.
- **Kill threshold** = `max(10 s, over_prediction_factor × seconds_high)`, only for a trusted
  projection. None when value-dependent, when there is no time projection, or when the projection is not
  trusted (disagreement > 3, fewer than 4 points, or a rate drift past the factor): only the extension
  budget stops such a term. So a kill is possible only for a stored prediction with `trustworthy = 1` and
  `value_dependent = 0`.
  Untrustworthy projections could kill until 2026-09-18; in session 5 that ended two of the three verified
  runs 10 s and 24 s into their first new term, both on 3-point projections that disagreed about 5×. At
  the edge of the known terms the next term usually costs more than extrapolation says, so an estimate the
  estimator doubts is no evidence that the term went wrong. The rate drift was added the same day (offer
  A): replaying the estimator on every term log, trustworthy work-unit projections would have killed
  A377248's a(7) at 11.2 s (it took 78.5 s) and A253773's a(26) at 10 s (31.8 s), with rate drifts of 11
  and 2.6. Every trustworthy work-unit projection in that replay drifted at least 2.6×, so in practice
  the kill now acts only on CPU-unit projections, whose drift was 1.01, and there it can still be wrong
  (see [known limitations](known-limitations.md#verification-and-estimation)).
- **Next-term size.** `next_bits_high` = the newest term's bit length plus the number of steps × 1.5 × the
  largest per-index bit growth among the last three steps, + 1. It is computed but not stored or used;
  Python and PARI integers do not overflow.

### When projections happen

- Right after verification completes, for the first new index.
- After each new term, for the following index.

A projection judged infeasible stops the run **before** that term starts.

### Where predictions are stored

Each projection becomes a `predictions` row:

- `predicted_s`, `predicted_s_low`, `predicted_s_high`, `predicted_mem`, `model`, `trustworthy` (whether
  the kill could act on it: `Assessment.trusted`, above; so a row with `trustworthy = 0` whose cost fit
  was trustworthy, withdrawn only by the rate drift, can still be `feasible = 0` on time), `feasible`,
  `value_dependent`, `cost_unit`;
- the cost fit's own statistics, since 2026-09-21: `fit_trustworthy` (`Projection.trustworthy`, the
  first half of `trustworthy` above), `fit_npoints`, `fit_disagreement`, `fit_climbing` and `rate_drift`.
  All five are NULL together, exactly when nothing could be fitted. `fit_trustworthy = 1` with
  `trustworthy = 0` is precisely a sound fit withdrawn from the kill by the drift;
- `actual_s` and `actual_mem` if that term finished;
- `censored_s` if the run stopped while that term was being computed (the term took at least that long).

Whenever a verified run ends and its last projection has no actual time and was feasible, `censored_s`
is set to the time between that projection and the end of the run. A projection that stopped the run as
`infeasible` gets no censored time, because its term never started: both `actual_s` and `censored_s`
stay NULL.

The dashboard's estimator view plots rows with a positive `predicted_s` and either an actual or a
censored time, so infeasible projections do not appear there.
