# Known limitations

Current behavior that is incomplete, surprising, or differs from the design intent, with where it lives
and a suggested fix. Last reviewed 2026-09-23 against the code at that date (items 42 and 43; the
searched-bound and heartbeat sections were last revised on 2026-09-22 and 2026-09-23 by items 40 and 41).

## Differences from the design intent

### 1. Failure penalties do not affect the current session

`select.candidates` applies the ×2-per-failed-attempt penalty when the pool is built, and `attempt.run_session`
draws all sequences before attempting any. A failure only changes the next session's odds. The sum tree
serves sampling without replacement, not the "update weights after failures" the spec described.

**The fix this entry used to propose — draw one sequence at a time and update its leaf after each
attempt — would change nothing** (checked 2026-09-20). `select.pick` already sets a chosen leaf's weight
to zero (`tree.update(i, 0.0)`), so a sequence cannot be drawn twice in one session, and the penalty is
keyed on the A-number, so raising one sequence's difficulty cannot move any other candidate's weight.
The spec's wording assumed sampling *with* replacement, which this code does not do; redrawing per
attempt would also re-run the `Runnable` check on every draw. The difference from the spec is real and
stays recorded here, but it costs nothing today.
**What would do something:** penalising *related* candidates after a failure — the A147798–A147805 style
families, where one entry's failure predicts its siblings'. Nothing defines "related" in the code, so
that is a possible feature rather than a pending fix.

### 2. (Fixed 2026-09-20) `sequences.difficulty` went stale at every sync

`oeisdata.sync` computed difficulty from DATA-line features only and overwrote the column on every sync,
discarding the b-file facts that `fetch-bfiles` had folded in. Measured before the fix: the next sync
would have broken **32 of the 26,814 rows** — every one of the 68 with a b-file whose facts changed the
score — the worst by 98.7% (A295928: 257.862 stored, 3.313 after a sync, while selection kept using
257.862). `sync` now recomputes the column from the stored rows after its upsert
(`db.refresh_difficulty`, one `executemany` in one transaction), so it always equals what
`select.difficulty` computes.
The column is still **unused by the code**: `select.candidates` recomputes difficulty from each row at
pick time, and nothing — not `queue`/`pick`, not the dashboard — reads the column. It matters only to
someone querying the database by hand. Dropping it was the other option and was not chosen: the project
has no migration machinery, so an existing database would need a hand-written `ALTER TABLE`.
The heading is kept so references to "item 2" stay valid.

### 3. The POSIX sandbox backend cannot run the pipeline

`sandbox/posix.py` exists but has never run. The rest of the project assumes Windows: `config.py`
hard-codes `tools/python/python.exe` and `tools/pari/gp.exe`, and `oeisbot setup` downloads Windows
binaries and sets AppContainer ACLs. The POSIX backend also has no filesystem confinement.
**Fix:** platform-specific runtime paths and setup, a real test run on Linux/WSL, and a low-privilege
user or container for filesystem isolation.
**Not planned here** (reviewed 2026-09-20): this machine has no Linux, WSL, Docker or Hyper-V, so none
of that work could be tested. `posix.py` stays as a starting point, unused and unexercised, and the
project remains Windows-only in practice.

### 4. (Fixed 2026-09-20) `oeisbot run -n` was silently capped at 25

`attempt.run_session` used `min(count, budgets.session_attempt_cap)` without saying so. It now logs
`asked for N, capped at 25 (budgets.session_attempt_cap)` when the cap bites — including when it
truncates an explicit list of A-numbers — and `run --help` names the cap. The cap itself is unchanged.
The heading is kept so references to "item 4" stay valid.

### 5. No CPU-time limit in the pipeline

The sandbox supports a job CPU cap (`Limits.cpu_s`, tested), but `verify.Harness.run` never sets one.
Wall clock is the only time limit. Jobs run at below-normal priority, so a busy machine slows them down
rather than the other way around.
**Deliberate** (reviewed 2026-09-20): wall clock is the unit the rest of the design reasons in --
`verify_wall_s` and `extend_wall_s`, dead ends keyed on the measured `runtime_s`, the 80% CPU-share guard
on a used-up extension. A CPU cap would add a second stop reason (`cpu_cap`) interacting with all of
them, for a problem no run has shown. `Limits.cpu_s` stays available to a caller that wants it.

### 6. (Fixed 2026-09-18) The model was never tried after a verified PARI run

A PARI program that reproduces every known term but finds nothing new now still ends the PARI stage, but
with `--model` the model stage runs next and is told the entry's program is correct but too slow (see
[pipeline](pipeline.md#4b-local-model-code-generation---model-only)). The heading is kept so references to
"item 6" stay valid.

## Further issues found while documenting

### Pipeline and recording

- **(Fixed 2026-09-20) Pending re-checks were saved as pickles.** A win waiting for its re-check is kept
  in `data/pending/attempt-<id>.json`, which since 2026-09-20 is JSON rather than a pickle: a code change
  to the classes it holds (`AttemptResult`, `Program`, `KnownTerms`, `TermRecord`, `Prediction`,
  `RunResult`, `Budgets`) or to `verify.Stop` / `sandbox.Status` no longer makes the file unloadable by
  itself. It is written field by field, and on loading the saved field names are checked against the
  dataclasses, so a field added or removed since the save is a named `ValueError` rather than a value
  quietly defaulted — the failure is loud, and the win still stays `recheck_pending` with its new terms
  in the run log (see [operations](operations.md#a-win-whose-re-check-failed-recheck_pending)).
  Nothing was migrated because nothing existed to migrate: when this was written on 2026-09-20 no win
  had ever been recorded and `data/pending/` had never been created. **Session 7 then produced one**
  (A385331, 2026-09-21), which saved `attempt-139.json`, passed its re-check and deleted it — so the
  *save* path has now run for real, and the *load* path (`_load_pending`, reached only from
  `retry_pending_rechecks`) still has not. `AttemptResult` gained two fields on 2026-09-30
  (`infeasible_on`, `below_bound`; history item 51) with `data/pending/` verified empty first, so no
  saved win was invalidated; a pending file from before that date would now fail the field check.
  What remains: a *changed meaning* of a field that keeps its name still reloads without complaint, and a
  win whose classes have drifted still needs the manual release documented in operations. Rebuilding the
  artifact from the run log instead was the other option and was not chosen: the log holds terms only —
  no program, no sandbox result, no budgets — so an artifact cannot be written from it.
- **(Fixed 2026-09-20) A program that errored but exited 0 was recorded as `incomplete` with its cause
  discarded.** `verify._result` reached the `INCOMPLETE` branch only when the child's `exit_code == 0`,
  and that branch kept only "program ended after N terms" — unlike the `CRASH` branch, it dropped
  `res.stderr_tail`. A run that produced no term also writes no term log, while `extra.log` still named
  the path one would have had, so that file did not exist. Nothing in the database, the artifact or the
  session log said *why* the program produced nothing. gp does this routinely: a call to an undefined
  function prints `*** at top-level: ... not a function in function call` and still exits 0. Session 6
  spent two of its twenty picks on such rows (A147803, A147800) and the cause — a PARI block calling
  `A007947`, which is defined in a different OEIS entry and nowhere in the block — had to be inferred by
  reading the entry source afterwards.
  **Fixed by** keeping the tail for `incomplete` and for any other `verify._TAIL_STOPS` stop that came
  without a term, leaving `extra.log` unset when no term log was written, naming the kept Python program
  as `extra.program` instead of deriving it from `extra.log`, and printing 300 rather than 160 characters
  of a detail in the session log (see [verification](verification-and-estimation.md#the-stderr-tail-in-a-detail)).
  Nothing is fixed retroactively: 35 of the 129 run rows written before that date name a run log that
  was never created (14 `wrong_term`, 12 `bad_index`, 6 `crash`, 2 `incomplete`, 1 `verify_timeout` — a
  term is logged only once it has passed its checks, so a run whose very first term was wrong logs none).
- **(Fixed 2026-09-20) PARI blocks could call helpers that only exist in another OEIS entry.** An entry's
  `%o` block may call `A007947(...)` or similar, defined in that other entry and never in this one; the
  program was accepted, ran, emitted nothing and was recorded as `incomplete` — whose detail now names the
  missing call (above), so such a row diagnoses itself, but only after a pick has been spent on it.
  Affected entries cluster in families (A147798 to A147805 are eight of them).
  **Fixed by** `pari.undefined_a_numbers`, a static check for an A-number a program calls or indexes but
  never defines, rejected in `build_candidates` so it surfaces as `no_supported_program` and never reaches
  a pick (see [strategies](strategies.md#programs-that-call-another-entrys-helper)). It covers undefined
  *arrays* too (A147805 reads `a147798[n]`), which a check for missing *functions* would have missed.
  **The earlier entry count here was wrong**, though its weight figure was right: it said 54–60 entries,
  from matching block text. Counting only blocks that actually produce a candidate, it is **65 entries
  that lose every candidate** and 5 more that lose one of two. The weight it gave — 1.9–2.1%, about 0.4
  wasted picks per 20 — stands: measured on 2026-09-20 against the pool a PARI-only session then drew
  from (3,552 candidates after `Runnable`; it is 3,497 today), the 65 are **1.97%** of the pick weight
  and **0.39** picks per 20. With `--model` on
  it is 0.47% and 0.09, because nothing leaves that pool.
  A *bare* mention of another entry's A-number is deliberately still allowed: gp does not fail on one.
- **A re-check that fails the same way every time keeps a win pending forever.** Only transient errors
  are retried within the run, but every later `oeisbot run` tries again (up to two requests to oeis.org
  per pending win) and logs the same error, until someone intervenes as above. Since 2026-09-20 the log
  at least says how often: each failure to resolve is counted in `extra.recheck_failures`, reset when the
  error changes, and a repeat reads `still pending (URLError: ...) -- the same way 7 times now`.
  **Retrying for ever is deliberate**, and was chosen over giving up after a fixed number of tries: a
  pending win is unpublished new terms, an error that looks permanent can be a long outage, and the
  sequence stays blocked either way, so stopping the retries would only move the work to a human without
  releasing anything. The manual release above is still the only exit.
- **A session's `wins` count misses late re-checks.** `sessions.wins` is computed when the session ends,
  so a `recheck_pending` win resolved later is not added to the session that found it, and a win whose
  review is rejected later is not taken off it (session 9's stored 2 are reviews #2 and #3). The dashboard
  no longer shows that stored count (history item 56): its Sessions table, header and per-day chart all
  count `attempts` when asked, and a late win appears on the day its run started. `sessions.wins` itself
  is still written the old way (`db.finish_session`: `extended` runs at the session's end), and nothing in
  the code reads it any more; a query that does gets the old meaning.
- **An unreadable live entry costs the win.** If the entry text cannot be parsed or returns nothing, or
  neither it nor the live b-file yields any terms, the run is recorded as `superseded` ("could not read
  the live entry", "could not read any terms from the live entry") and no artifact is written.
- **The artifact's `executed.py` does not hash to the sha256 its `verification.md` prints.** `artifact.write`
  writes the program files in text mode, which on Windows turns line ends into CRLF, while the recorded
  hash is of the program as it ran. (The run file in `data/runs/` is written byte for byte since
  2026-09-19.) Found by the offer-C audit; not changed.
- **A crash after verification is recorded as `finished`.** `Harness._result` does not keep the error
  text when a program errors after producing new terms. The terms themselves are valid.
- **Re-checks overwrite the b-file cache with the live copy.** If the live b-file differs from the
  snapshot's LFS pointer, the next `fetch` for that sequence re-downloads until the next sync.
- **`verified` outcomes count as failures** in the selection penalty, the same as `failed`.
- **(Fixed 2026-09-20) The infeasible dead-end check compared configured budgets, not the effective
  memory cap.** A run may be judged infeasible on memory because the harness capped it at free physical
  RAM − 3 GiB, below `mem_bytes`; the program then stayed a dead end at the same `--extend-s` and
  `--mem-gib` even after the RAM was freed. Each run now records the cap it actually got
  (`extra.mem_cap_bytes`, the `Harness.mem_cap` that `estimate.assess` was actually given; the sandbox's own `RunResult.mem_cap_bytes` is the same formula read an instant later, so it can differ) and `db.is_dead_end` keys the `infeasible`
  clause on that. It is compared against the *configured* `mem_bytes` of the planned run rather than
  against the cap that run would get, which was the other option: that would make selection depend on
  free RAM at the moment of asking, and this project predicts its picks in advance (history item 31).
  The chosen rule is the stricter of the two, so it can never keep a dead end it should not; the cost is
  re-running a starved program once while RAM is still tight.
  Never observed when the fix was made: of the 129 runs recorded before it, exactly one ended
  `infeasible` (#93 A057246) and it was judged on **time**, not memory, and none had stopped at
  `memory_cap`. **Both halves have since been overtaken** (2026-09-21): attempt #133 (A277041) is the
  project's first `memory_cap`, and attempt #139 (A385331) the first `infeasible` on a real extension —
  again on time, not memory.
  The one pre-fix `infeasible` row loses its dead-end status, since `extra.mem_cap_bytes` is absent from
  it — the same rule that already applied to rows recorded before the budgets were stored.
  What remains: the memory term also gates dead ends whose `infeasible` verdict was reached on *time*,
  because the row does not record which of the two reasons decided it. Keying them separately would need
  a new `extra` field; not done.
- **Trying to start a child process is recorded as a plain crash.** The sandbox stops the job with
  status `stopped`, which the harness does not map to a stop reason. The attempt becomes `crash`
  ("exit code 1"), or `finished` after verification, and the "tried to start a child process" reason
  is lost.
- **`bad_index` after verification marks the program a dead end** even though the run verified and its
  earlier new terms count.
- **A verify timeout on a busy or sleeping machine becomes a dead end.** `db.is_dead_end` refuses a
  program that already ran at least the current `verify_wall_s` without reproducing its known terms. Jobs
  run at below-normal priority, so heavy use of the PC during a session (or the PC sleeping) can time out
  a program that would have passed on an idle machine, and it is then not re-run at that budget. A larger
  `--verify-s` revisits it.
- **(Fixed 2026-09-18) A verified run that used its whole extension budget was not a dead end**, so a
  later session could repeat the same extension with the same program for nothing, and since offer B more
  runs end that way. It is now a dead end for any run with no more extension time (see
  [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first)). What remains:
  - **A used-up extension on a slower machine still becomes a dead end.** The CPU guard (at least 80% of
    the wall time on the CPU) catches a busy machine, but not a slower CPU (a power-saving plan, thermal
    throttling, another PC), where the program did less work in the same time. Whether time asleep counts
    against the extension was not checked; if it does, the guard catches that too. A larger `--extend-s`
    revisits the program.
  - **Each of an entry's PARI programs can cost a whole extension.** One unproductive run at the default
    3 h retires that program at the default budget, and since 2026-09-19 (offer E) the entry's next
    program gets its turn in a later attempt, with its own extension (see
    [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first)): across attempts every runnable
    program gets its own extension before the sequence leaves the PARI-only pool at that budget (in
    today's candidate table at most three: 299 entries have two runnable programs, one has three).
    A sibling that is the same computation repeats the work: in the candidate table most such pairs are
    one template, "numbers n such that (c·10^n − d)/9 is prime" (223 of the 300 entries with two or more
    runnable programs), and 220 of those need primality proofs for numbers of over 1000 digits just to
    verify, so they end as `verify_timeout` and seldom get that far. At a longer `--extend-s` the first program runs first
    again, and only when it is a dead end at that budget too does the next one run.
  - **`over_prediction` is not a dead end.** The kill does not depend on the extension budget, so the same
    program is likely killed again at any budget. Rare since offers B and A; not changed.
- **Model-stage skips hide what happened earlier.** With `--model`, a sequence whose PARI program verified,
  or whose PARI programs were all out of reach, can end with a model-stage skip row (`too_few_known_terms`,
  `model_skip`, `model_no_runnable_code`), so the report's `skipped` reason names the model stage even
  though a program ran or the real obstacle was the PARI stage. The PARI stage's own rows and log lines
  are still there.
- **The selection check cannot see every b-file.** `attempt.Runnable` builds known terms from the cached
  b-file only (no request). A sequence whose b-file exists but is not cached is kept in the pool
  unchecked; the session log counts these as "kept ... that only an attempt can check". On 2026-09-18 every b-file
  was cached, so none were.
- **The dashboard's Queue tab shows the wider pool.** It does not apply the selection check (see
  [dashboard](dashboard.md#queue)); `oeisbot queue` does.

### Term lines from an untrusted program

Added 2026-09-25 with `verify.MAX_TERM_FIELD_DIGITS`. A `@T` line's counting fields are capped at 40
digits before `int()` runs, which closes the `OverflowError` that would otherwise kill the sandbox's
stdout reader thread (the `cpu_us / 1e6` conversion included: a 40-digit integer divides into a float
without overflow, and `on_line` catches `OverflowError` beside `ValueError` in case the cap is ever
raised). Since 2026-09-30 the reader thread itself is also guarded: any exception escaping `on_line`
stops the job as `Status.CALLBACK_ERROR` and the run records `harness_error` (history item 51), so a
future hole here ends a run loudly instead of silently. Two things the cap deliberately does **not**
close:

- **A huge term value still costs real time in the reader thread.** The value field is exempt — OEIS
  terms are legitimately unbounded — and `sandbox.windows.MAX_LINE` is 1 MiB, so a program can put ~10^6 digits
  there. Measured on this machine (2026-09-25, CPython 3.11.9): `int()` on 10^6 digits takes **3.7 s**
  and `str()` on the result **13.1 s**; at 10^5 digits it is 37 ms and 133 ms. `str()` is reached twice
  — `_short(value)` in a `wrong_term` halt, and `str(rec.value)` in `_log`, once per accepted term — and
  the thread holds the same lock as `on_tick` throughout, so the harness's own clocks stall with it. The
  cap narrowed this from five fields to one rather than removing it. A generous absolute cap on the value
  would close it and has not been added, because it is the first limit that could refuse a genuine
  sequence. For scale, the longest last-known term in this project's own corpus is 1,031 digits
  (A295928, from `sequences.bfile_last_digits`), so a 10^5-digit cap would leave two orders of
  magnitude of headroom at 38 ms to parse and 133 ms to render -- but "every real OEIS term" is a
  claim about OEIS, not about this corpus, and it has not been measured.
- **The `protocol` detail carries the raw line, which the held-out scrub does not cover.** An over-long
  index is now refused at the parse step, *before* the index check, so a program that puts a term's value
  where the index belongs stops at `protocol` with `malformed term line: '<the line>'` instead of at
  `bad_index`, whose detail `codegen.describe_failure` scrubs. That scrub covers `wrong_term` and
  `bad_index` only. It bites only when the held-out value is longer than 40 digits (a shorter one still
  parses and still reaches the scrubbed path) and only in a `--model` session. **Measured 2026-09-25 over
  the model-eligible pool — sequences with at least 3 known terms, 26,736 of them: 149 (0.56%) have a
  held-out term over the cap**, the longest **1,031 digits** (A295928). Population matters here: over
  the PARI-bearing pool alone the figure is far smaller, and the model path is not restricted to it.
  This widens the already-documented limitation that a `protocol` stop passes on text the program wrote
  itself; it is a mechanical narrowing of [invariant 5](development.md#invariants), recorded rather than
  fixed.

### Verification and estimation

- **The memory projection sees the PARI stack, not everything gp allocates (2026-09-30, history item
  51).** The gp driver reports `default(parisize) + heap`, and since item 51 that figure is judged
  against the stack ceiling gp is launched with (`parisizemax`) rather than the job's commit cap, ~800×
  larger — the mismatch under which no gp run could ever be judged infeasible on memory (next step 6:
  A277041 died at `memory_cap` reporting 8 MiB on every term). What the projection still cannot see is
  memory gp takes *outside* the PARI stack — GMP's own temporaries for very large operands — which is
  what the job cap is enforced on and what A277041 actually exhausted. Catching that needs the sandbox
  to sample the job's commit per term and hand it to the harness (the Windows monitor loop already has
  the job handle; the tick callback would gain an argument); not built, and the `memory_cap` stop still
  retires nothing, so the cost is a wasted extension, not a lost sequence.

- **The known terms say little about the cost of the next one, for exactly the sequences targeted here.**
  The estimator's only input is the cost history of the known terms, but a sequence carries `keyword:more`
  *because* its next term is expensive, so the cost cliff sits at the edge of the known terms by
  selection. Measured in database session 4: A247883's a(1)..a(10) cost 57 ms in total and a(11) was not
  found in 1800 s. Extrapolation cannot bridge a gap of that shape, and this is a structural limit rather
  than a tuning problem.
- **The `work` cost unit can understate growth badly, and the estimate in seconds stays low.**
  `verify.Harness.points()` prefers instrumented
  work units whenever the program reports them, because they are hardware-independent and smooth, and
  `estimate.assess` converts them to seconds using the mean wall-per-work rate of the last five terms —
  which assumes that rate is roughly constant. When the per-unit cost is itself growing, it is not. On
  A377248 (`8191*2^k + 1` prime) work grew 1.9–2.1x per term while wall time grew 15.4–15.7x, because
  work counts candidates tested and ignores the widening primality test. Replaying `estimate.assess` on
  the recorded points projects a(8) at 149 s (range 149–734 s) from work against 1191 s (range
  1161–1191 s) from CPU; a(8) is known to exceed 516 s, so the work estimate is low by at least 3.5x and
  its whole range falls below the CPU one. The work path does flag the trouble (`climbing`, ratio model,
  `risky=True`, 4.9x disagreement) — the number misleads, not the warning.
  One step earlier it does not even warn: projecting A377248's a(7) from the terms up to a(6) gives a
  trustworthy cost fit (4 points, 1.36x disagreement) with a high estimate of 5.59 s, a kill at 11.2 s,
  but a(7) took 78.5 s, because the wall seconds per work unit grew 7.5x, 8.1x and 7.5x at a(5), a(6)
  and a(7). Since 2026-09-18 (offer A) this no longer reaches the over-prediction kill: the rate is
  projected to the next term too, and a projection whose rate drifts past the kill factor is not trusted
  (A377248's a(7): drift 11; see [verification](verification-and-estimation.md#assessment-estimateassess)).
  What remains is the number. It is not corrected, so the infeasibility check lets such a run go on into
  a term it cannot finish, and the run ends at its extension budget rather than stopping early.
  Corrections were tried in a replay on every real term log (extrapolating the rate, projecting wall
  seconds instead, taking the higher of the two). Counting a term once for each budget of 60, 120, 300,
  1800 and 10,800 s at which it was stopped, each correction added 3 or 4 wrong stops (terms judged
  infeasible that finished within the budget) to the 9 of the rule then in force (all 9 on untrustworthy
  fits, which since offer F no longer stop a run on time; see below). A wrong stop gives the term up
  before it starts, while a run that goes on can still find it; either way, a run with nothing new is a
  dead end at that budget (`infeasible`, or a used-up extension on a job with at least 80% CPU).
- **The over-prediction kill can still misfire on a trusted CPU projection.** In the offer-A replay (every
  term log, each known term projected from the ones before it as if it were new), A274508's a(15) had a
  trustworthy CPU projection (poly, 4 points, 1.87x disagreement, high 11.1 s, kill at 22.1 s) and took
  32.4 s; its rate drift was 1.01, so nothing in the conversion flags it. Counting real runs and the replay,
  the kill has been wrong five times (the two session-5 kills, fixed by offer B; A377248's a(7) and
  A253773's a(26), fixed by offer A; A274508's a(15)) and never known to be right. Two more replayed
  kills would have stopped terms that were still running when their runs ended (A273521's a(7) after
  597 s and A350878's a(16) after 38 s, both against a 10 s kill), so their merit is unknown; the rate
  drift withdrew both. Turning the kill off by default was considered on 2026-09-18 and not chosen.
  The rate drift itself is a one-step extrapolation from at most five points. A slow moment on one of
  them, odd and even terms with different rates, or gaps between the fitted indices can overstate it
  (which only withdraws a kill) or understate it (which leaves the kill as it was before offer A).
  A253773's a(26) was withdrawn at a drift of 2.6, close to the factor of 2. A milder climb stays
  trusted: a rate growing 1.5× per term drifts 1.95 by the next term under a doubling cost, though 2.9
  under a flat one.
- **An untrustworthy projection costs a whole extension.** Since 2026-09-19 (offer F) only a trustworthy
  cost fit can stop a run as infeasible on time, as only a trusted one can kill a term. In the replay this
  removed all 9 wrong stops (A274508's a(16), A350878's a(14) and a(15), each counted at every budget of
  60, 120, 300, 1800 and 10,800 s at which it was stopped though it finished in time) and also the 7
  right ones (A253773's a(27), A265383's a(8), A272621's a(14) and A377248's a(8), which took longer
  than the budget): such a run now spends the rest of its extension, up to about 13 minutes over the whole replay, where the
  old rule stopped it early. At the long budgets the change is sharper: at 10,800 s the old rule's only
  stops were A057246's a(5) (attempt #93, high 13,026 s) and A265383's a(8) (high 652,000 s), both of
  unknown merit, and at 1800 s those two and a wrong one (A274508's a(16)); each such run can now use its
  whole extension (3 hours or 30 minutes).
  All 6 time projections stored from real runs were untrustworthy when this was written, so the time
  check then stopped almost nothing; the extension budget did, and a used-up extension is itself a dead
  end at that budget when the job had at least 80% CPU. **Session 7 overtook this too** (2026-09-21):
  there are now 18 stored projections with a time estimate, 5 of them trustworthy (attempt #139,
  n = 39..43), and the time check is exactly what stopped the project's first win — correctly, at a(43). A run that goes on can also end as `memory_cap` or `disk_cap`,
  or be killed (`over_prediction`) once a later projection is trusted; none of these is a dead end, so
  it may be run again later. Judging an untrustworthy fit by its low
  estimate instead was weighed and not chosen: it would have kept 5 of the 7 right stops, but still
  stopped terms that finished in time once little extension time was left (A350878's a(14): low 44.5 s,
  actual 0.3 s), and of the 28 finished projections with an untrustworthy fit (per run log), 10 took less
  than the low end.
- **Projections rarely exist for real runs.** The estimator needs 3 terms above the noise floor (50
  work units or 0.05 CPU s), excluding the first term. Short DATA-only sequences rarely have them, so
  no time projection is made, there is no over-prediction kill, and only the extension budget applies.
  As of 2026-09-23 there are **45** projection rows over **27** attempts: **26** with a projected memory
  but no time estimate, and **19** with a time estimate. Before session 7 the figures were 13 and 6, and
  all six of those rested on 3 points and none was trustworthy — which since 2026-09-18 also meant no
  kill and since 2026-09-19 no infeasible stop on time. Session 7 changed the picture: **19 of the 45
  rows come from attempt #139 alone**, and 5 of them are trustworthy (7 of the 19 fitted projections are,
  across the whole history). The scarcity is still real for runs that stop at the gate; it is the runs
  that get *past* it and produce their own points that escape it. (The figures were 40 over 22 at
  2026-09-21; session 8 added the other 5, and this paragraph was not updated until item 44's audit.)
- **Only predicate searches have a static cost bound.** `pari.out_of_reach` knows that a predicate driver
  must call the predicate once per integer up to the last known term. Most expensive predicates are
  expensive per call instead (primality tests of `c·b^k ± 1` with a growing `k`); nothing flags those in
  advance, so each still costs one full verify budget before it becomes a dead end. Measured on history,
  the bound would have avoided 1 of the 13 verify timeouts (A391617); its main effect is on the pool
  (393 sequences left out at 60 s when measured on 2026-09-20; 387 today).
- **The short verify budget also applies to model programs.** A correct but slow generated program now
  stops at `verify_timeout` after 60 s instead of 600 s (the retry then asks for a faster algorithm).
- **Coarse CPU timing.** Windows process CPU time advances in 15.6 ms steps and gp's `getabstime` in ms,
  so uninstrumented programs contribute noisy costs for fast terms.
- **Search detection is a heuristic, and it misses in both directions.** The name regex flags 3,060
  candidates, including names that are not searches, such as "First differences of the primes that are
  congruent to 1 mod 4". A false positive:
  - exempts the terms from the time-based infeasibility check, so only the extension budget stops
    them;
  - exempts them from the over-prediction kill;
  - raises difficulty ×1.5.

  Session 7 found the first measured **false negative**, on the sequence that produced the win.
  `_VALUE_DEPENDENT` needs a `smallest|least|first|...` superlative *and* a
  `such that|for which|with|where|whose|that|having|so that` connective, so "the **smallest prime factor
  of** the n-th numerator ..." does not match although its cost plainly depends on the value found.
  About 160 names in the 600 s PARI pool carry a superlative with no connective (an upper bound — many,
  like "first k primes", are not searches). Note that the three effects above run **both** ways: flagging
  A385331 would also have cut its pick weight by 33% (weight 1.628 → 1.085, from a stored `difficulty`
  of 0.614 → 0.922 — the weight is the reciprocal, so the database shows the difficulty, not these two
  numbers) and so changed the draw
  that produced the win. The data-driven guard, `_value_dependent_by_data`, did not save it either: it is
  fed the noise-floored points and needs 6 of them, and the floor left 5.
- **B-file lines with trailing text are still used.** A line like `12 345 extra` is counted as malformed
  (noted) but its index and value become a known term.
- **Next-term size bound is computed but discarded.** `next_bits_high` and the `risky` flag are not
  stored in the database or artifacts.
- **No checkpoint/resume, and this is now a settled decision rather than a gap.** Only finished terms are
  saved; a killed run restarts from the offset. Since 2026-09-23 a predicate run *records* where its scan
  reached (`extra.scan_reached`, from the driver's progress heartbeats), and **nothing reads it,
  deliberately**: on 2026-09-23 the user decided against building resume (history item 42), after the
  evidence and a critic's 31 findings. In short — it saves **no machine time** against simply passing a
  larger `--extend-s`, costs 2x on a find (a resumed run may never win, so a cold confirming run must
  re-cover the whole range), breaks [invariant 10](development.md#invariants) because
  `_bound_exhausted` is unreachable from a resumed run so it would scan past a published bound, has no
  termination rule, and is damped geometrically by the selection failure penalty. **Do not build it
  without new evidence**; read history item 42 first. The replacement is a targeted
  `oeisbot attempt A... --extend-s`.
- **Progress heartbeats cost about 4% of predicate scan throughput, with a floor of about 2% that no
  block size can remove.** Measured in the sandbox on the cheapest predicate there is (a single
  comparison), against a baseline of 5.58e6 calls/s for the unbounded `for(k = start, +oo, ...)` loop the
  blocked form replaced. What is *established*: a finite loop bound on its own costs **2.1%**, so any
  periodic-progress formulation pays at least that; the blocked form measured 3.6-4.9%; and a hand-rolled
  `while` with `k++` costs 43.9%, which is why it is not used. What is **not** established is that the
  remainder is per-iteration: the block-size sweep (10^6 → 4.9%, 10^7 → 3.6%, 10^8 → 5.69e6 calls/s,
  i.e. *faster than baseline*) sits inside a ±2% noise floor and cannot resolve the question either way.
  So a larger block may or may not buy the excess back; the honest reading is a ~2.1% floor plus an
  unresolved remainder, and block size is chosen for cadence because nothing measured argues otherwise.
  On a realistic predicate (`k >= 10^6 && isprime(k)`) the whole cost measured 2.9%. **The regime every
  run actually starts in is unmeasured:** `HEARTBEAT_BLOCK0` is 10^4 and the sweep began at 10^6, so a
  short verification window -- the one that feeds `measured_rate` and so the searched-bound skip -- has
  never been timed. At `SEARCHED_BOUND_MARGIN` = 10 a few percent there changes nothing, which is why
  this is recorded rather than fixed.
- **The recorded frontier lags the real one by up to one block, and is absent for short scans.** The
  heartbeat prints *after* its block, so a run killed mid-block records the previous boundary; and a scan
  that finishes inside its first block (`pari.HEARTBEAT_BLOCK0` = 10^4 predicate calls) never emits one
  at all, so `scan_reached` is missing from those rows entirely. Both err in the safe direction --
  understating a frontier can only cost a later run time -- but neither is obvious from the row.
- **Changing a driver silently retires every past result for that form.** `attempts.program_sha` is
  `sha256(Program.executed)[:16]` and `executed` includes the driver, so editing a driver template
  changes the sha of every program built from it and `db.is_dead_end` — which keys on
  `(a_number, program_sha, known_terms)` — stops matching any historical row. Item 41's heartbeat change
  orphaned all 49 distinct predicate records at once: `oeisbot queue` went from 3,464 candidates with 73
  `all_programs_dead_ends` to 3,497 with 38, putting 35 previously retired sequences back in the pool to
  re-derive verdicts that had not changed. The selection failure penalty is unaffected (keyed on the
  A-number). This cuts both ways and is not simply a bug: the same property means a driver change
  automatically invalidates a stale recorded frontier, which is what a resume would have needed (it was decided against: item 42). **Expect
  it, and price it, before editing `A_DRIVER`, `PREDICATE_DRIVER` or `_EMIT`**; there is no migration
  path short of backfilling `program_sha` in place.
- **The frontier is the program's own word, and the ceiling it is held to is universal rather than its
  own.** `verify.Harness` cross-checks each heartbeat against the work it claims (`k - start + 1 ==
  tested`) and against `pari.PREDICATE_MAX_RATE`. The two are complementary, not redundant: without the
  ceiling the identity alone accepts `@P 10^300 10^300 0`, and without the identity the ceiling alone
  accepts `@P 10^300 1 0`, since one call is under any ceiling. What they do **not** do is bound the lie
  against *this* predicate's real speed. `@P 10000000 10000000 0` is accepted at t = 0 (10^7 is not
  greater than 2e7 × the 0.5 s start-up grace), and real predicates are far slower than the ceiling:
  A176090 scans at 256 calls/s, A229209 at 433, A279795 at 1,528, so a consistently lying driver could
  run some 78,000× ahead of its true position. Nothing consumes the frontier today, so nothing is
  exposed. **Nothing resumes from it (item 42), and anything that ever did would have to validate it against the run's own measured rate
  (`verify.measured_rate`, or the previous accepted heartbeat) rather than `PREDICATE_MAX_RATE`.**

### B-files are almost absent from this candidate set

- **Only 68 of the 26,814 candidates have a b-file** (0.25%), against 243,052 of the 399,307 sequences in
  the mirror (61%). The `more` keyword selects for sequences with few known terms, which are exactly the
  ones nobody has written a b-file for. Measured by `fetch-bfiles --all` on 2026-09-17, which resolved
  every candidate (68 `present`, 26,746 `absent`, 0 errors) in about three minutes.
- **Most real candidates are therefore verified against DATA only**, and this is structural rather than a
  gap that prep work can close. All 182 sequences attempted so far had no b-file (`known_source` is `data` on every one of the 250
  runs — re-checked 2026-09-29 after session 11: still 0 rows used a b-file), so known terms came from
  the DATA line; most had fewer than 10 terms, which the artifact flags as weak verification.
  The b-file path is covered by unit tests but has still not been exercised by a live run, and only those
  68 sequences could ever exercise it.

### Searched bounds

The [searched-bound check](verification-and-estimation.md#the-searched-bound-check) (added 2026-09-22)
reads a human claim out of a `%C` comment. Everything below was found by hand-reading all 241 pool
candidates whose bound is beyond a real run's reach, so these are measured limitations, not guesses.

- **A bound is an unverified human claim.** It is used only to decline to spend time. It is never
  evidence that a term is correct, and it never decides a term's index — which is why the check runs
  *after* verification rather than replacing any part of it, and why a run is never resumed past a
  published bound. `extra.verified_scan_to` records the part that *is* measured: how far this run's own
  scan actually reached.
- **Borrowed bounds are rejected, and that costs real ones.** A274994 quotes *A001220's*
  `4.97*10^17` while its own claim is `2*10^6`; reading the first was the single wrong skip in the
  census. The guard rejects any bound whose sentence names another A-number, which also drops bounds
  whose *justification* merely cites another entry — A087485, A127441 and A238739 among them, about 1.8%
  of the deployable set. The trade is deliberate: a wrong skip cannot be undone within a session, a
  missed one only costs time.
- **Qualified claims are rejected by keyword, so some genuine ones go too.** A146566's `No other term
  multiple of 12 below 10^9` is not a claim about all terms. The guard rejects `multiple of`, `of the
  form`, `congruent to`, `divisible by`, `with` and `whose` between the head and the connector, which
  also discards roughly twenty corpus-wide bounds of the shape "no more terms **with k** < X" (A036415,
  A046035, A082813, A176932, A240842 and others). None is in today's deployable set, but they matter for
  any future widening of the patterns.
- **Recall is about 85%, measured.** Phrasings still missed include number words beyond
  million/billion/trillion, `Checked up to X`, `the only terms known up to X`, `none was found up to X`
  and primorial or factorial notation (`no other terms found up to 23#`). 1,135 pool entries have `%C`
  lines that no sampling frame has covered, so this figure is an upper bound on what is known, not on
  what exists.
- **The loose `searched to X` phrasing is deliberately not a pattern.** It produced A088783's false
  positive, where a per-candidate *exponent* limit read as a term bound while the entry says its next
  term may be 185. No deployable candidate needs it.
- **The rate is measured over the verification phase, sometimes a very short one.** On the runs this
  would have fired on historically, several windows were under 0.1 s. The first term record is dropped
  because it carries interpreter start-up, and `config.SEARCHED_BOUND_MARGIN` is 10 for the same reason;
  `extra.rate_window_s` records how thin the measurement was, so a reviewer can judge it.
- **The extractor has known blind spots, none of them live today.** Found by an audit that hand-read all
  146 entries the check can currently fire on (all 146 are genuine, unconditional bounds for the next
  unknown index) and then attacked the parser: `_QUALIFIER` only inspects the text *before* the
  connector, so a trailing qualifier passes (`No other terms below 10^9 that are multiples of 12`); the
  bridge guard is applied to the indexed form only; an **index** bound reads as a **value** bound
  (`No others for n <= 10000`, A070525 — caught today only by the staleness filter); `no other <noun>`
  parses as a term bound (`no other divisors below 10^9`); the borrowed-bound guard looks at one sentence,
  so a citation split across two sentences slips through, and its `A\d{6}` pattern misses the
  abbreviated `A1969` forms `pari._ANAME_USE` accepts. `parse_number` is silently wrong on
  `3*2^(1000)` (parenthesised exponent → 3), `Fibonacci(104911)`, `1e9`, `5 quadrillion` and `5 times
  10^9` — all understating, so all safe — and on the European decimal comma `1,5*10^6`, which
  overstates. A bare `>` that is really the head of an arrow was a real defect until 2026-09-22:
  A337671's `a(17)? -> 2^9216 - ...` parsed as a 2,775-digit bound.
- **It is not a dead end.** A skipped sequence stays in the pool and is picked again, paying its
  verification each time. That is deliberate — nothing about the sequence has been disproved — but it
  forfeits the permanent retirement such a run would have earned by ending at `extend_budget`, which is
  what 8 of the 10 historical firings did. The selection failure penalty damps the re-picking without
  stopping it.

### Strategies

- **The conjectural-program check catches only programs that use its words** (item 47, 2026-09-26). It
  refuses a PARI part whose comments say `conjectur*`, `heuristic*`, `unproved`, `unproven` or
  `not proved` — **7 of 5,781 PARI parts, in 7 of the 5,315 part-bearing entries**, 3 of them in the
  live pool when this was measured on 2026-09-26. **That "3" is now 5**: item 49 closed reviews #2 and
  #3 on 2026-09-28, so A162762 and A162764 re-enter `select.candidates` and are excluded by this check
  rather than by their open reviews — which is exactly the `no_supported_program` 1,418 → 1,420 move.
  The check's live cost was understated by the close, not by the measurement. What it does **not** catch:
  - **A program that is conjectural and says so nowhere.** Nothing can detect this class statically, and
    its size is unknown and unmeasurable from the text. This is the honest limit of the whole idea.
  - **Scope caveats phrased differently.** Measured over the live pool (2026-09-26), 12 sequences carry a
    caveat in a program comment that these words miss. **They are not one class, and most are not this
    failure mode at all:**
    - **A wrong-value risk: exactly 1, A191363**, and it is worth naming rather than counting.
      `a(k)=(2^2^k+1)<<(2^k-1) \\ For k<6.` is the closest structural twin of the A16276x class — a
      closed form with an explicit range limit, and exactly 5 known terms for `k<6`. **It is harmless
      today only by an accident of its indexing**: the program is indexed from the Fermat-prime index,
      so the driver emits 10 at n=1 against a(1)=3 and verification fails at the first term. An upstream
      OEIS edit re-indexing it from 1 would silently reopen this hole, which is why it is named here.
    - **A272930 is *not* a wrong-value risk**, though its comment reads like one
      (`\\ works only if a(n) is not zero.`): `a(n)=my(r=1);while(sigma(sigma(r))!=n*r,r++);r` never
      terminates when the term does not exist, so the run hangs until the budget kills it. Timeout, not
      a wrong term.
    - **Performance/illustration caveats, 7** (A020754, A034174, A038460, A152097, A179094, A217016,
      A283438, A309370 — "too slow for n > 15", "for illustrative purpose only"). **These are not a hole
      in this check.** A slow program times out and the gate records `verify_timeout`, which is correct
      behaviour; it cannot emit a wrong term. (A020754 additionally returns a non-`t_INT`, so the driver
      errors.) Counting them as missed conjectural programs overstates the gap, which two earlier drafts
      of this note did — first as "3x the class this check catches", then as "2 genuine domain caveats".
      The honest comparison is **1 potential wrong-value case, itself already stopped by the gate,
      against 3 the check removes.**
    - **External data, 1:** A274003 (`\\ assuming the vector A178751 holds enough terms`) — a different
      failure, and one the helper check does *not* catch either, because `_ANAME_USE` needs `(` or `[`
      after the name and this one is followed by `,`.
  - **Wording the pattern just misses.** `unproved|unproven|not proved` but **not `not proven`** — an
    asymmetry with no corpus hit today, fixable with `not prov[a-z]+`. A disclaimer split across two
    `%o` lines (`not` / `proved`) or double-spaced is also missed, because the pattern matches within a
    line as the block is assembled. Two more from an independent scan of all 5,781 parts: **A291786**
    ("the suggested search limit L=n is only empirical") and **A277967** ("slow, only probabilistic
    primality test", `ispseudoprime` at 2^2^n scale) — the same failure mode in principle, negligible in
    practice for BPSW, and noted only so the list is honest.
  - **A genuine member whose words differ:** A376243's whole program is
    `select( {is_A376243(n)=!n||ellrank(...)}, [0..30]) \\ Assuming there's a rational solution iff the
    elliptic curve has rank > 0.` That is an assumption about the *membership criterion*, so it belongs
    to the class, and `assuming` is exactly the word the precision measurement forbids adding. Inert
    today: the part yields no candidate.
  - **The model prompt relabels the program, not the conjecture — a limitation this item created.**
    `codegen._context` does not list a flagged PARI block under "Existing programs (correct, possibly
    slow)" — since 2026-09-30 (history item 51) it quotes it under `CONJECTURAL_PROGRAMS_NOTE`, the
    author's own disclaimer; between 2026-09-26 and then it dropped it — but it still quotes
    `entry.comments[:8]` and `entry.formulas[:8]` verbatim, and for two of the three live siblings the
    conjecture is *in there*. Measured 2026-09-26, counting lines in the assembled prompt that match
    `conjectur|heuristic`:
    - **A162763: 3 lines**, including "a(n) = 2n - 2 … **Conjectured to hold with equality for all n**"
      and "G.f.: x*(2 + 2*x^6 …) **(conjectured)**"
    - **A162764: 2 lines**, the same shape plus a conjectured g.f.
    - **A162762, A349899, A351088: 0** — but **A162762 is not "clean"**, it merely avoids the *word*.
      Its prompt still carries, verbatim: `Empirical g.f.: 2*x^2*(x^2-x+1)*(x^3-x-1) /
      ((x-1)^3*(x+1)*(x^2+1))`; `a(n) = 2n - 2 for n < 2C + 2, a(n) <= 2n - 2 + C + a(n - 2C) otherwise,
      **with equality for all known terms and the above g.f.**`; and the whole upper-bound algorithm in
      Comments. Either of the first two, implemented in Python, reproduces all 17 known terms and then
      emits values indefinitely — session 10 exactly. On a word list of
      `conjectur|heuristic|empirical|upper bound|with equality|for all known` the counts are **A162762:
      3, A162763: 3, A162764: 4**. So the sequence that already burned a pick is **as exposed as its
      siblings**, and a `conjectur`-only count of its prompt is the wrong measurement to reassure
      anyone with.

    So a model asked for a faster program can read the conjectured closed form and generating function
    straight out of the "Formulas:" block and implement them in Python, where no disclaimer survives for
    anything to detect. What the change removes is the **"correct" label on the program**, which was a
    plain falsehood; it does not remove the conjecture from the prompt. Say it that precisely — "the
    model is no longer handed their program as correct" is true, "the model no longer sees the
    conjecture" is not.

    **The honest-header design was taken on 2026-09-30 (history item 51), reversing the 2026-09-26
    decision to drop the block:** the flagged block is quoted under a header carrying the author's own
    disclaimer, so the model keeps the algorithm that withholding cost it and loses only the false claim
    of correctness. The `progs[:4]` slice is still taken *before* the partition, so a flagged block still
    never frees a slot for a fifth program (the promotion interaction below is unchanged). Whether the
    header actually restrains a model is **unmeasured**: no model session has run since session 4.

    Filtering `%C`/`%F` is *not* the obvious fix, and this is where the fence above cuts the other way:
    reading those fields to **reject a sequence** is noisy and would have falsely flagged A162761, the
    proved sibling, whose comments discuss the very conjecture it proves. Reading them to decide **what
    to quote to a model** is a different question with a different cost, and it is unresolved. Note the
    exposure is bounded by there being no model session since session 4.
  - **Non-PARI blocks are not covered, and the relabelling is per block.** `codegen._context` moves a
    flagged **PARI** block under the conjectural header, but not a Mathematica, Maple or Magma block
    carrying the same disclaimer, because `pari.code_mask` implements GP's comment syntax and cannot be
    trusted on another language's. 5,282 candidates have Mathematica but no PARI program. The
    relabelling is also **per block** where `build_candidates` is per signed part: a block with one
    flagged part is quoted whole under the conjectural header, its clean part included, while the PARI
    stage still builds the clean part's candidate. That asymmetry is deliberate — `_context` quotes
    `p.code[:600]`, the whole block, and a clean part called conjectural costs the model a claim where a
    conjectural part called correct would cost it the truth — and `tests/test_codegen.py` pins it so the
    two granularities are not "harmonised" by mistake.
  - **The check does not make a sequence a dead end.** No row is written; the pool is derived from the
    code, so a future `sync` that removes a disclaimer returns the sequence by itself. That is the
    intended direction, but it also means the three sequences reappear if the wording changes.
  - **~~Reviews #2 and #3 are only conditionally solved~~ — the limitation was closed by item 48
    (2026-09-26); the review rows themselves were closed by item 49 (2026-09-28).**
    `Runnable._why_not` returns `conjectural_program` with the model on as well, so a flagged
    sequence is left out of both pools, and A162762 and A162764 stay out now that the two reviews are
    `rejected` — measured: both pools unchanged across the close, 3,438 and 26,747.
    **What remains, deliberately:** only the *draw* is blocked. `attempt_sequence` has no such
    gate, so `oeisbot attempt A162763 --model` still runs the model — and the prompt it builds still
    quotes the `%C`/`%F` lines above. That asymmetry is the reason suppressing the draw cost only 7
    sequences (0.03%; item 48 measured it as 5 of 26,752 before the reviews closed) instead of
    foreclosing those sequences entirely, and it is tested; do
    not close it without replacing the trade. **Item 49's audit found the sharp edge this leaves:**
    with the rows `rejected` rather than `new`, that targeted command is no longer stopped by
    `attempt_sequence`'s `open_review` skip either, and `db._insert_review` would let it open a fresh
    review for the same conjectural values. See next-step (v) in [status](status.md).

- **PARI list printers and vector builders are unsupported** (`lista(nn)`, `first(n)`, triangle
  `row(n)`): 434 candidates have only a list printer, 892 have nothing usable. A **fourth** shape joined
  them in session 7: `a368129(rmax=235)` is a bulk printer whose parameter is a *radius bound*, not an
  index, and returns a `List` — `_is_a_name` accepts any `a<digits>` name, so `build_candidates` made an
  `a(n)` candidate out of it and the run produced 0 terms in 0.0 s. **A second instance in session 11**
  (A373945, `a373945(upto=10^8)`, history item 50) showed how such a run can hide: the function's own
  `print1` writes `0, 1, ` to stdout without a newline, the driver's `@T` lands on the same line, and
  `verify.on_line` ignores any line that does not *start* with `@` — so the row is an ordinary
  (**refused since 2026-09-30, history item 53**: `pari._bulk_printer` rejects a def whose only parameter
  carries a default, the shape both instances share; measured 4 of 4 such defs in the corpus are bulk
  printers, so the rule costs nothing today — re-measure at a sync) —
  `verify_timeout` with no term and no protocol error, indistinguishable from a slow program.
- **A predicate-shaped def beside a list printer may be a helper, not the sequence's test** (session 11,
  item 50). A335304's block defines `is(n)` — commented `\\ A054735`, the test for "n is the sum of a
  twin prime pair" — and `lista(nn)`, the real algorithm, which prints with `print1`. The builder takes
  the one-argument def as the predicate, and the first emitted term was 8 against a(1) = 2
  (`wrong_term`, retiring the sequence). The shape is statically visible; how many pool blocks have it,
  and how many of their predicates are the real one, is unmeasured — see [status](status.md#open-offers-and-next-steps),
  item (vi).
- **The helper check catches names that carry an A-number, and nothing else** (item 33; widened
  2026-09-30, item 51). `pari._ANAME_USE` now captures the whole identifier around `[Aa]\d{4,7}` when it
  is followed by `(` or `[`, and compares that identifier with the block's definitions, so the
  **suffixed** shape (A375302's `a375301_row(n)`, session 7) and the **prefix** shape (A274003's
  `is_A178751(n)`, session 11) are both caught, while `is_A034293` defined in its own block is not
  flagged for the A-number inside it — the trap the naive widening would have sprung on a program that
  verified. What still slips through is a helper with an **arbitrary** name living in a linked file, as
  in A368129's `BijectionD(v, Bijectionk)`, which needs the general "called but never bound and not a gp
  built-in" rule; and a helper mentioned without `(` or `[` after it (A274003's other block, `assuming
  the vector A178751 holds enough terms`), which gp does not fail on either. The widening removed 12
  candidates, every one a genuine other-entry helper by inspection (see
  [strategies](strategies.md#programs-that-call-another-entrys-helper) for the list and the 31 sequences
  the balanced-parenthesis parse added at the same time).
- **A predicate can be called outside its domain.** The generic driver calls `is(k)` for every k from
  `search_start`, but A231865's `is(n)=ispseudoprime((43^n+1)/44)` is defined only for odd n — the
  quotient is a `t_FRAC` otherwise — so the program errors at once. The entry's program is correct on its
  intended domain; it is the driver that widens it. Wrapping the call in `iferr` would fix it but risks
  turning a genuinely broken program into one that "verifies" by swallowing errors, so it is listed in
  [status](status.md#open-offers-and-next-steps) as a decision, not a recommendation.
- **Predicate searches start at 1**, and **print-loop rewrites** can change a program's meaning beyond
  the known terms (see [strategies](strategies.md#correctness-caveats)). **A print loop that starts above
  the entry's offset shifts every index** (A290024, session 11, item 50): the entry's `for(n=1, 7, ...)`
  prints a(1) onward while `%O` is 0, and the emitter numbers from the first known index, so the program's
  correct values 1, 2, 4, ... were emitted as a(0), a(1), a(2), ... and the run ended `wrong_term` at
  index 1 — a correct program retiring its sequence under that sha. **Refused since 2026-09-30 (history
  item 53, `pari.loop_start_problem`)**, the user choosing refusal over renumbering: an index loop (a
  plain `for` printing once per iteration) must start at the offset, and a filter loop printing its own
  variable must start at or below the first known term (A215906's shape, session 12). Only literal
  starts are judged; a filter loop printing an expression is left to the gate, so the shape is narrowed,
  not closed — 32 candidates in 30 sequences refused against the 44 pool sequences the wider heuristic
  counted. A290024's sequence stays retired under its old sha until re-synced or backfilled.
- **gp programs are not scanned for hard-coded limits**; only generated Python is.
- **Short sequences give the model very little to work from.** `codegen.shown_indices` always holds out
  at least 2 known terms, so with 3 known terms the model sees only the first term and with 4 it sees 2.
  Sequences with 1 or 2 known terms are not given to the model at all (skip `too_few_known_terms`); those
  without a PARI program leave the selection pool once their b-file lookup has run. On the 2026-09-17
  snapshot, going by DATA terms (a b-file can add more), that is 75 candidates, and 334 would be shown one
  term and 941 two. Expect weak model results on them; the PARI strategy is unaffected.
  **Fix:** prefer sequences with more known terms when `--model` is used. (Looking b-files up first was
  also suggested here, but the sweep on 2026-09-17 showed it changes almost nothing: only 68 of the
  26,814 candidates have a b-file at all — see [b-files](#b-files-are-almost-absent-from-this-candidate-set).)
- **Text the program wrote itself reaches the retry as it is.** Since 2026-09-19 (offer G) no failure
  detail shows a held-out term, or a program value equal to one that the prompt does not already show,
  but three texts come from the program and are not scrubbed: a `crash` detail is its exception message
  (`KeyError: 10031`); a `crash` or `incomplete` retry also carries the last 12 stderr lines; and a
  `protocol` detail repeats a line the program printed itself (a malformed `@T` line, or a forged
  `@ERR OEISBotContractError: ...`), which it can only do by printing, against the prompt's rules. None
  of the 7 crash messages recorded so far holds a value. Since 2026-09-20 a stderr tail is also stored,
  in the `detail` of a `crash` and of the stops in `verify._TAIL_STOPS`, so it is shown in the dashboard
  and reaches a retry on its own line as well as in the 12-line block — and, for the first time, it can
  be measured: `SELECT detail FROM attempts WHERE failure_mode IN (...)` now shows what that channel
  carries. It never reaches an artifact: those are written only for wins, and no win's stop carries a
  tail — still true now that a win exists, and no longer vacuously so: A385331 stopped on `infeasible`,
  which is not in `verify._TAIL_STOPS`, and its `stderr_tail` was empty in any case.
  Since 2026-09-23 a **fourth** program-written text is stored: `extra.first_bad_heartbeat`, up to 200
  bytes of a rejected `@P` line, so a program could put a held-out value there by printing one. It is
  the only one of the four that reaches **no prompt and no artifact** -- `codegen` reads back
  `failure_mode` and `detail` and never `extra`, and `artifact.write` serialises only the run result and
  the budgets -- so it is a database-only channel, listed here because the list is meant to be complete.
  Scrubbing was considered and not chosen by the user. **Fix, if wanted:** scrub these texts,
  knowing it cannot be complete (single digits, traceback line numbers, `1.0031e4`, hex).
- **The generation prompt lists module names, not function names.** `GENERATE` interpolates
  `", ".join(sorted(ALLOWED_IMPORTS))`, so the model knows `gmpy2` and `sympy` are available but has to
  guess what is in them; `gmpy2.prime_range` does not exist (sympy's is `primerange`). The function list
  is currently sent only *after* a crash, by `retry_guidance`, so the first generation still guesses.
  **Fix:** put `API_HINTS` in `GENERATE` as well, if a first-generation improvement is wanted.
  (The retry half of this was fixed on 2026-09-17: see [strategies](strategies.md#steps).)
- **The list contract rests on the model's own judgement** (its answer to `FORM`). A list it calls a
  function gets `terms(work)`, with the index bookkeeping that caused every `bad_index` so far. A function
  with increasing known terms that it calls a list gets `members(work)`: its values in order are still
  numbered correctly, but the prompt fits it badly. The judgement was right on all 44 sequences tried, a
  small and partly name-picked sample, and it depends on the wording: folded into the classify question
  it missed 2 of them (see [strategies](strategies.md#the-list-contract-memberswork)). It costs one more
  model call per model stage whose known terms strictly increase.
- **A `members(work)` program can still yield the wrong thing**: the prime c·b^k ± d instead of k (as 4 of
  the 17 earlier `bad_index` programs did), or a list that skips a member. Within the known terms
  verification catches both as `wrong_term`. Beyond them the driver catches only a value that arrives
  out of order while the run is still going, and then voids the run's new terms. A late value that would
  have come after the run stopped (its extension budget, a kill, `max_new_terms`) is never seen, and a
  member skipped for good makes every later new term wrong without anything noticing; the reviewer is
  the only check left, since the re-check only compares with what oeis.org has published. A run voided after verification
  still ends the model stage (it verified), without a retry, and its run log still shows the voided
  terms as `new`.
- **Repeats are recognised narrowly.** A program counts as a repeat only within one model stage and only
  with the same syntax tree: a renamed variable is a different program and runs, and so does the same
  program in a later attempt.
- **A timeout on a busy machine still counts as a repeat.** A `verify_timeout` counts as a failure that
  recurs in the model stage whatever CPU share the run had: a program that ran out of time only because
  the machine was busy is not run again in that stage, which costs the stage a generation. The 16 model
  timeouts so far had 97% CPU or more, but 5 of the 58 PARI ones had less than 80% (jobs run at
  below-normal priority), so it can happen.
- **The strategy does not say which contract ran.** Both are `python:model`, which the AI-generated
  warnings depend on; the origin (`...; members(work), numbered by the runner`) and the notes in
  `attempts.extra` record it. The answer to the list question and the repeats that were not run appear
  only in the console log.
- **Heuristics are untuned.** The difficulty factors, the "later PARI program first" ordering and the
  estimator thresholds are initial guesses. The attempts and predictions tables exist to tune them.
- **Model capability.** `qwen2.5-coder:14b` solved simple sequences but failed every real candidate it
  was given until the list contract, often by misreading the definition; with it, two of its programs
  reproduced every known term (A247883 and A057246, both of which the entries' own programs had already
  done), and none has found a new term (see below).

### Operations

- **One job at a time.** Sessions are sequential; there is no parallelism across CPU cores.
- **No pruning.** `data/runs/` and `data/bfiles/` grow without limit. (The pick snapshots are the one thing
  that is pruned: [below](#the-pick-map).)
- **No schema migrations.** Schema changes need manual `ALTER TABLE` or a fresh database. A table that is
  only *added*, as the two pick-snapshot tables were (history item 54), needs neither: the writable
  `connect()` creates it with `CREATE TABLE IF NOT EXISTS`, and the read-only dashboard copes with its absence.
- **Runtime downloads are not hash-pinned.** `setup` prints the sha256 of the Python zip and `gp.exe`
  but does not check them against known values.
- **The dashboard has no authentication.** It binds to localhost by default.
- **The `network` pytest marker is declared but unused.** Tests that would touch the network stub it out.

### Runtime provenance

Since 2026-09-23 (history item 43) the gp and sandbox-Python versions are recorded, in `meta` and — as a
short token — in each session's `sessions.note`. Three gaps remain; two are deliberate, and one is
flagged for work before the first gp upgrade:

- **Rows written before 2026-09-23 have no runtime recorded and never will.** The version that produced
  them is genuinely unknown; inventing one would be worse than the gap, so there is no backfill. That is
  **44 of the 176** attempt rows existing at the time with no `session_id`, and in fact all 176, since
  nothing recorded a version before this item.
- **A standalone `oeisbot attempt` writes no session row**, so its only provenance is the `meta` row,
  which is overwritten the next time gp changes. Provenance is therefore complete for every row *until
  gp is next upgraded*; afterwards only session rows keep it. gp has been upgraded zero times so far, so
  the present gap is zero. Closing it properly would need a per-attempt `extra` key, which was weighed
  and left out (the user, 2026-09-23).
  **After an upgrade this is worse than a gap: it misattributes.** The single `meta` row then names the
  *new* gp while remaining the only provenance for every pre-upgrade standalone-attempt row, so it reads
  as a positive, wrong answer rather than as silence — and nothing records *when* `meta` was written, so
  the boundary is not recoverable either. A timestamp key beside the two version keys would make it
  datable for one more `set_meta_many` entry; it is not built, and should be before the first gp upgrade.
- **The versions are recorded, not enforced.** Nothing compares them between runs or warns that a
  result came from a different gp; they are there to be read afterwards.

### The Pick map

The dashboard's [Pick map](dashboard.md#pick-map) (history item 54) is a picture of the draw, and each of
these is a way it can be read too strongly.

- **The tile is the chance of being drawn *first*, not of being drawn.** The areas add up to 100% because
  `pickmap.chances` is `weight / sum of weights`. A session draws `k` distinct sequences, each draw
  proportional to weight among those not yet taken (`select.pick`), so a sequence's chance of appearing
  somewhere in a session of 25 is larger than its tile says, and the more so the larger the tile. Ranking
  is unaffected; the percentages should not be read as "chance of being run this session".
- **The α box changes the map, not the sessions.** A session uses `oeisbot run --alpha` (default 1.0). The
  snapshot stores difficulties, so the map can show any α, and a tile's size at α 2 is what a session run with
  `--alpha 2` would give it, not what the next default session will.
- **"Change" is relative to the sequences that were in both pools.** A tile that reads "0%" may have gained
  or lost chance in absolute terms: if others left the pool, every survivor's absolute chance rose a little,
  and that common drift is deliberately divided out (see `pickmap.compare` and the example there). The
  "Chance before (rescaled)" in a tooltip is therefore the earlier share *rescaled* so that before × change = now, not the
  stored earlier share; only the "Left the pool" table shows unrescaled earlier shares. A tile for a
  sequence that was not in the baseline has no change at all and is hatched. And "0%" is a *class*, not
  the absence of a movement: the neutral colour covers a change of up to 1% either way, and the others read
  `1 / (1 − f/2)` rather than exactly 1 when the sequences that moved hold a fraction f of the survivors'
  picks (1.006 for f = 1.25%).
- **Not every session has a snapshot.** A pool identical to the newest stored one is not stored again, so
  `pick_snapshots.session_id` is the session that *first* saw a pool, and a run of sessions that changed
  nothing leaves one snapshot. The baseline is the newest snapshot that **differs from the live pool**,
  which can be several sessions old; the tile "Compared with" says which and when. When the live pool
  equals the newest snapshot the map compares with the one before it, so it shows what changed *into* the
  live pool, not "no change"; when every snapshot equals the live pool it says so and draws gray.
- **The first snapshot is only as old as this feature.** Nothing before item 54 was recorded, so the
  first map has nothing to compare with until the pool changes after a snapshot exists. The comparisons in
  the documentation made before then were recomputed from the database backups
  (`data/oeisbot-before-session12.sqlite3`), not read from snapshots.
- **"Left the pool" reasons are read now, not recorded then.** The reason for each departed sequence
  comes from the database at the moment the page is built: its open review, its newest attempt since the
  snapshot, its `in_more` flag, then the two fingerprints (`pickmap.departure_reason`). A sequence that
  was attempted *and* later left the `more` list reads as attempted. A departure with none of these
  reads **`unexplained`**, and that is the label for anything the fingerprints cannot see. The `rules`
  fingerprint hashes the sources of `Runnable`, `PariPlan`, `pari_plan`, `db.is_dead_end`,
  `oeisdata.load_entry`, `bfile.cached` and `bfile.known_terms`, the whole of `select.py`,
  `strategies/pari.py` and `ingest/seqfile.py`, and four constants (`db.DETERMINISTIC_FAILURES`,
  `db.OPEN_REVIEW_STATUSES`, `db.EXTEND_DEAD_END_MIN_CPU_SHARE`, `config.CODEGEN_MIN_KNOWN_TERMS`). It does
  **not** see a change in what those call that lives elsewhere (`terms.py`, the helpers inside
  `oeisdata.py` and `bfile.py`, the rest of `db.py` and `config.py`), nor in the oeisdata mirror, the cached
  b-files or anything else under `data/` that the database does not record: any of those can add or remove
  sequences with the fingerprint unchanged. Two further limits of the comparison itself: the fingerprint
  the server compares with is the one of the code **this process loaded** (it describes the live pool the
  server built, which is the point), so after rule files are edited a server that was not restarted still
  builds its pool with the old code, and a snapshot written by a session that ran the new code reads as
  "the rules changed" until it is; and a fingerprint of `unknown` (a source file that could not be read) on
  either side disables the comparison rather than guessing, with a note saying so.
- **The live pool is built under the newest snapshot's budgets**, so a map and a session run with other
  budget flags (`--verify-s`, `--extend-s`) disagree about who is a dead end or out of reach. The snapshot a
  session stores carries *its* budgets, which is what the "budgets differ" note compares.
- **A running session blanks the cache.** Every commit changes the database file's stamp, so while a
  session runs each visit to the tab rebuilds the pool (6 to 12 s for either, 25 s for a first build on a cold disk) and
  the map shows the attempts the session has recorded so far. The page says when a session is unfinished;
  a session that crashed shows as running for 24 hours (`app.RUNNING_SESSION_MAX_AGE`).
- **The snapshot is a record for the map and nothing else.** A failure to write one is logged
  (`pick snapshot not recorded: ...`) and the session (or the sync) carries on; nothing reads the tables
  except the dashboard and `oeisbot snapshot`. Retention is 30 PARI snapshots and 10 model ones, so the
  history that can be compared with is bounded and the oldest are gone.
- **`oeisbot sync` also stores a snapshot, and that has four edges** (history item 55; the code is
  `attempt.snapshot_after_sync`). (1) **PARI only**: the model pool takes about half a minute to build, so a
  sync leaves it to `oeisbot snapshot --all` or a `run --model`, and a model map's baseline can be older than
  the PARI one. (2) **Its budgets are the newest PARI snapshot's** (`attempt.budgets_of`), not the defaults,
  so a sync after a session run with other `--verify-s` / `--extend-s` records under those; with no PARI
  snapshot at all it uses the defaults. That makes the budgets *follow whoever wrote last*: `oeisbot
  snapshot` takes no budget flags and stamps `config.DEFAULT_BUDGETS`, so running it after such a session
  puts the defaults back for the syncs and the dashboard that come after, and a short test session
  (`--verify-s 5`) pins them to 5 s until the next writer says otherwise. Nothing breaks, because the
  dashboard and the sync read the same stamp and so build the same pool, but it is that session's idea of
  who is out of reach, not necessarily the one the next default session draws from. (3) **`session_id` is
  NULL**, as it is for `oeisbot snapshot`, so nothing ties a sync's snapshot to a session, and it stays
  NULL if a session later draws the very same pool (that session stores nothing, so the "Compared with"
  tile then omits "session N"). (4) **A pool is compared with the newest snapshot only**
  (`db.record_pick_snapshot` dedupes on the newest digest), so a pool that goes A, B, A is stored each time:
  retention keeps 30, and a database that is synced often between two states of the pool fills them with
  alternating copies. That is the same behaviour a session's snapshot has always had; the sync makes it
  easier to reach. **The snapshot is not stored at all if the per-sequence check failed for any candidate**
  (`keep.errors`; a missing or unreadable b-file, say), because the sequences it lacks would then show as
  arrivals in the next comparison; the sync says so and moves on, and the next successful sync or session
  stores it. And **its rules fingerprint is the on-disk code's**, built by the sync process, while a dashboard
  server that has been running since before an edit to those files compares with the code it loaded (see "Left
  the pool" above). A sync that finds the pool unchanged stores nothing but, like any snapshot call, re-stamps
  the newest snapshot with its fingerprint (`db.record_pick_snapshot`), so syncing after an edit to the rule
  files makes a long-running server say "the rules changed" until it is restarted.
- **A pool that cannot be built is a retry, not a stack trace** (history item 55). `/api/pickmap` answers a
  failed `live_pool` with a 503 and `{"error": "pool_build_failed", "reason": ...}` (the reason is the
  exception's type and message, whitespace collapsed and cut to 200 characters), and the tab shows the
  reason with **Try again**. Two limits. The guard covers the call to `live_pool` only: a failure in the
  rest of the handler (the read of the snapshot headers before it, the comparison after it) is still an
  unguarded 500. The tab then reads "Could not load: 500: Internal Server Error" with the same **Try again** button,
  because only a 503 carrying `pool_build_failed` is recognised as a pool failure
  (`treemap.failureReason`). And nothing is cached for a failure (`live_pool` assigns its cache entry after
  the build returns), so a build that fails for a lasting reason fails again at every retry, taking as long
  as the pool takes to get as far as failing.
- **Keyboard use is checked in the geometry and by reading, not in a browser** (history item 55). The tiles
  are focusable (`role="link"` for a sequence, `"button"` for a lump of small ones; the map is one
  roving-tabindex stop, Tab reaching the tile last focused or else the first; arrows go to the nearest tile
  that is drawn, `treemap.neighbour`, in the order of `treemap.focusOrder`), and those two functions are
  covered by `dashboard/test/treemap.test.ts`. The component that wires them (`pickmap.tsx`: the focus,
  the tooltip's owner, Enter, Space, Escape) has no automated test: node cannot run `.tsx`, and no browser
  was driven for item 55 (the browser pass of 2026-11-17 and item 56's saw the focus ring, the tooltip, the
  arrows, Enter on a tile and on a lump, and the chips). **A tile that is not drawn cannot be reached by
  keyboard**: a tile with no area, a tile under 3 px on either side (`treemap.MIN_FOCUS_SIDE`, item 56; a
  band left with no stop at all keeps one on its largest tile), and every tile
  of a band too small to draw in *All bands*. For the bands, a footer line ("Too small to draw to scale here")
  lists each as a button that opens its tab, which draws it. A band is too small when its inner box is under
  `treemap.MIN_DRAWN_SIDE` = 6 px in either direction, a threshold chosen from the live pool's inner sizes at
  widths 360 to 1600 (`data/item55/inner_sizes.ts`), not a measurement of what a pointer can hit; at another
  width or for another pool a different set of bands falls under it. The line is computed from the layout
  the map draws, so it cannot disagree with the map. In a band's own tab a lump of small tiles is
  focusable since item 56 and opens the table view (there is no band left to open). Three smaller edges, all from reading the
  code and none seen in a browser: a refresh or resize whose new layout no longer has the focused tile
  (it became part of a lump, say) drops the focus to the page, because only opening a lump from the
  keyboard moves it on; **Space** opens a sequence's entry as Enter does, which a real link would not
  (it would scroll the page), kept so that both keys work on both kinds of tile; and Shift with an arrow or
  Enter acts as the key alone (only Alt, Ctrl and Meta are left to the browser). The re-check of the audit's
  fixes added three more, none seen in a browser: a resize or refresh while the pointer is over one tile and
  the keyboard is on another puts the keyboard's tooltip in place of the pointer's (the next mouse move
  corrects it); a tooltip is placed from where the focused tile is when its `focus` event fires, which may
  be before the browser scrolls a half-hidden tile into view (since item 56 that scroll puts the tooltip back
  where the tile now is, seen in a browser; any scroll closes a tooltip the pointer opened); and `:focus-visible` is the browser's own
  heuristic for a focus set by script (after an arrow key), so a browser that says no would show neither the
  ring nor the tooltip.
- **Area is exactly equal across bands; paint is not, some of a band's box can be empty, and a very small
  band is not drawn to scale** (history item 56; every figure from `data/item56/area_spread.txt`, the page's own
  `layoutGroups` call at every width the page gives the map, 200 to 1198 px, on the pools of 2026-11-17 at
  α 1). `treemap.layoutGroups` draws every band that has room for tiles at one scale, so the **rect** of a tile
  or a lump is the same number of px² per unit of pick chance in every such band: the largest band over the
  smallest is 1.000000000000 at all 999 widths, for both pools. Four things that is not:
  - **It is not the whole canvas.** Headers, padding and the empty part of roomier boxes leave the tile rects
    66.1% to 92.4% of the canvas per unit of chance on the PARI pool (median 87.7%; 92.4% at the full
    1198 × 659) and 61.4% to 92.6% on the model pool.
  - **Part of a box can be empty.** A band roomier than the tightest one leaves the rest of its inner box
    blank: a median of 0.4% of the framed area on the PARI pool (0.0% on the model pool), 5.1% (11.7%) at the
    90th percentile of widths, and **23.5% (25.0%) at the worst width**. The emptiness is the visible form of
    the difference the old layout hid, and a reader who does not know that may take it for missing data; the
    caption says a band with room to spare leaves some of its box empty.
  - **Paint is not rect.** Each tile is painted 0.5 px short of its rect on every side
    (`pickmap.TILE_INSET`), so a band of many small tiles shows less paint per unit of chance than a band
    drawn as one lump: between bands the painted area per unit of chance differs by **1.21× to 1.38×** on the
    PARI pool (1.11× to 1.32× on the model pool) across the widths. With the 1 px inset used until item 56 it
    was 1.48× to 2.04× (`area_spread_inset1.txt`). The eye compares paint, so two bands' *textures* are not
    comparable to better than that; two *tiles* are.
  - **A band with no room is not at the common scale.** A band whose inner box is under 6 px either way
    (`MIN_DRAWN_SIDE`) fills its sliver at its own, smaller scale and is named under the map: band 8 (16 and
    up, 2 sequences, 0.002%) at all 999 widths and band 7 (8 to 16, 25 sequences, 0.07%) at 678 of them on
    the PARI pool, band 8 at 102 widths on the model pool. **A changed tile in such a band does not show in
    *All bands*** (the "never lumped" rule cannot help a tile that has no room); its own tab shows it. One
    more hair: the part of a box a band draws in can itself come out a little under 6 px wide while the box
    passes (5.97 px at one model-pool width in a review's sweep), which nothing enforces.

  The figures are for these two pools. Item 54's script (`data/item54/area_spread.ts`) still runs, but it
  measures the frame's inner box, which the tiles no longer fill, at three sizes the page never produces; its
  0.93 and its 2.5× are not figures about what is drawn now.
- **The dashboard's safety checks have edges** (history item 56).
  - *Reading the database touches a file.* SQLite rewrites the `-shm` file beside a WAL database on every
    read, read-only connection or not; the database file and the WAL are not written
    (`tests/test_dashboard.py::test_api_never_writes` checks the database file's mtime and that every
    connection was opened read-only, and says so in its docstring).
  - *The Host check is off for a wildcard bind.* `oeisbot dashboard --host 0.0.0.0` (or `::`) prints a warning
    and accepts any `Host`, so DNS rebinding is possible again on such a server; a specific address keeps it.
    uvicorn's own 400s (a request with two `Host` headers, say) are sent before the app runs and carry no
    `nosniff` header.
  - *The refusal of other pages' requests trusts the browser.* It reads `Sec-Fetch-Site`, which every
    current browser sends; a client that sends none is taken for a tool, so the check is against a web page
    in a browser, not against a program on this machine, which could read the database file anyway. A link
    from another page straight to `/api/docs` is refused too (type the address instead).
  - *A HEAD or OPTIONS request is a 405 on every route*, `/` included, and when a query parameter is given twice
    the last one wins without a word. Neither was changed.
- **Freshness is ordered by a build counter, so a map can be one commit behind a running session.** A request
  accepts a live pool that finished building after the request asked, even if the database has changed
  since (`app.live_pool`, `_generation`); without that, every waiter behind a build would build again while a
  session is committing all the time. The price is that the map may be missing the last attempt or two, and
  the next visit rebuilds. The counter replaces a clock because Windows' monotonic clock ticks every 16 ms,
  which let a build and the next request read the same value; the age shown on the page and the one-hour
  backstop (`POOL_TTL_S`) still use that clock.
- **The frontend tests are not type-checked, and some depend on the Node they run under.** `npm test` runs
  the three files in `dashboard/test/` (`treemap`, `scale`, `format`) under node's
  own type stripping, and `npm run build`'s `tsc --noEmit` covers `src` only (`tsconfig.json` `include`),
  because checking the test would need `@types/node` and a tsconfig option that allows imports ending in
  `.ts`, which the build does not
  otherwise want. A type error in the test shows up as a failed run, not at build time. `format.test.ts`
  compares formatted dates and grouped numbers with exact strings, which come from the ICU data in the Node
  that runs it (checked on Node 24.19); it normalises the one difference known between ICU releases, the kind
  of space before "PM". And `src/scale.ts`, `src/format.ts` and `src/treemap.ts` must stay free of imports,
  or node cannot load them.

## Observations from real runs

2026-09-17 to 2026-09-21, with the oeisdata snapshot `9566689775`, which held 26,628 candidates
at first (26,814 once `fini,more` entries were included on 2026-09-17).

**The table below stops at session 8 and its totals line is scoped to it.** Three later runs are missing
from it and are counted in the whole-project totals under them: item 40's end-to-end check of the
searched-bound stop (row #176, A194099), **the whole of session 10** (rows #177-228, 50 picks over
two runs, history item 45) and **session 11** (rows #229-253, 25 picks, history item 50). Noted
2026-09-28 by item 49's audit, which found these totals had been read as current for a week.

| Run | Settings | Sequences | Program runs | Result |
|---|---|---|---|---|
| Manual `attempt` | PARI; verify 120 s, extend 120 s | 3 | 2 | 1 skipped (list printer); A246855 verified 3/3 known terms, no new terms in 120 s; A309238 `verify_timeout` |
| Session 1 | PARI only; verify 120 s, extend 240 s; seed 7 | 8 | 6 | 2 skipped (unsupported forms); 5 `verify_timeout`; A057246 verified 4/4, no new terms in 240 s |
| Session 2 | `--model`; verify 120 s, extend 300 s; seed 21 | 6 | 19 | 18 model generations (10 `wrong_term`, 4 `bad_index`, 2 `crash`, 2 `verify_timeout`) + 1 PARI run (`verify_timeout`, 26 of 41 known terms) |
| Session 3 (db) | `--model`; verify 600 s, extend 1800 s | 5 | 16 | 15 model generations (6 `wrong_term`, 5 `bad_index`, 4 `crash`) totalling **8 s** + 1 PARI run (A272621, `verify_timeout`, 13 of 15 known terms in 600 s) |
| Session 4 (db) | PARI only; verify 600 s, extend 1800 s; seed 101 | 5 | 6 | 5 `verify_timeout` (A273521 7/8, A101722 1/4 on each of its two PARI blocks, A391617 4/7, A377248 7/12) + A247883 verified 10/10 in 57 ms then found no new term in 1800 s |
| Session 5 (db) | PARI only; the new selection check; verify 60 s, extend 1800 s; seed 202 | 20 | 22 | 0 skips; 17 `verify_timeout`, 1 `wrong_term`, 1 `incomplete`; 3 verified: A323252 (no new term in 1800 s), A277532 and A390295 (both killed by `over_prediction` after 28.5 s and 10.6 s); 47.8 min of wall clock |
| Step-2 `attempt` | `--model`; verify 60 s, extend 120 s; A247883, A057246, A246855 | 3 | 12 | each PARI program verified again and found nothing in 120 s; the model stage then ran with the note: 9 generations, 8 `bad_index`, 1 `crash` |
| Offer-B `attempt` | PARI only; verify 60 s, extend 300 s; A277532, A390295 | 2 | 2 | both verified again; their untrustworthy projections no longer killed the first new term, and both ran the whole 300 s (`extend_budget`) without a new term |
| Offer-C `attempt` | `--model`; verify 60 s, extend 120 s; A247883, A057246, A246855, A253773, A272621, A253380, A345338, A383336, A095751, A320768 | 10 | 20 | no PARI program ran (dead ends or none); 8 of the 9 asked were judged lists, A383336 a function; 0 `bad_index`; A247883 and A057246 verified in generation 1 (then `extend_budget` and `infeasible`); 14 `verify_timeout`, 4 `wrong_term`; 5 repeats not run and 1 program rejected for copying known terms; 0 new terms |
| Session 6 (db) | PARI only; verify 60 s, extend 1800 s; seed 206 (2026-09-19) | 20 | 21 | 0 skips; 15 `verify_timeout` (60.14–60.53 s), 2 `incomplete` (A147803, A147800, 0 terms in 0.0 s); 4 verified, each using its whole extension (A015766, A279795, A222206, A293756, 1800.5–1801.9 s at 0.98–0.99 CPU share); 0 new terms; 8,110 s of wall clock. All 20 picks and their order were predicted in advance; none of the 4 verified runs produced a cost fit, so the run could not test offers B, A and F (status history item 31) |

| P4 probe `attempt` | PARI only; verify 600 s, extend 60 s; A277041, A391937, A265938 (2026-09-21) | 3 | 3 | none verified; A391937 13/15 → **14**/15 and A265938 26/33 → **27**/33, both `verify_timeout` at 600.3–600.4 s; A277041 stopped at the project's **first `memory_cap`** after 62.1 s, with `extra.mem_cap_bytes` = 6.00 GiB equal to the configured budget. Ten times the budget bought exactly one term on each run that reached the gate (status history item 35) |
| Session 7 (db) | PARI only; verify 600 s, extend 1800 s; seed 600 (2026-09-21) | 20 | 20 | 0 skips; 11 `verify_timeout` (600.1–600.4 s), 3 `incomplete`, 1 `wrong_term`; 4 verified, each using its whole extension; and **A385331 extended by 18 new terms**, the project's first win, stopped by the first `infeasible` kill on a real run. 15,073 s of wall clock. All 20 picks and their order predicted in advance (status history item 35) |
| Session 8 (db) | PARI only; verify 60 s, extend 1800 s; seed 208 (2026-09-21) | 20 | 20 | 0 skips; 13 `verify_timeout` (60.27–60.38 s), 2 `wrong_term`; 5 verified — four using their whole extension (A270393, A292083, A097402, A087280) and **A194099 killed by the first `over_prediction` since offer B**; 0 new terms; 8,038.6 s. **8.96 picks/h against session 7's 4.78, 1.88x**, 83% of it the verify gate. All 20 picks, their order and the pool line predicted in advance; 10 of 11 predictions held (status history item 38) |

Totals **for the table above, which stops at session 8**: 107 sequences, 173 program runs, **1 win**,
12.3 machine-hours of run time — that is attempt rows 1-175.
**Whole project as of 2026-09-29** (re-derived by query after session 11, item 50; first re-derived
2026-09-28 by item 49): **182 sequences, 250 program runs, 253 attempt rows, 17.7 machine-hours**,
still **1 genuine win** — session 10 added two `extended` rows whose programs are conjectural, reviews
#2 and #3, now `rejected`, and session 11 added 25 rows, 5 verified, 0 new terms. (43 of the runs, and 1 skip, belong
to no session: standalone `oeisbot attempt` runs, including the A129250 re-attempt that checked the
retry-prompt fix, the 12 runs of the step-2 attempt, the 2 of the offer-B check, the 20 of the
offer-C measurement and the 3 of session 7's P4 probe.)

**Session 11 (2026-09-29, rows #229-253, history item 50)** — PARI only, verify 60 s, extend 1800 s, seed
211: 25 picks, 25 runs, 0 skips; 16 `verify_timeout` (60.23-60.32 s), 2 `wrong_term`, 2 `incomplete`;
5 verified, every one using its whole 1,800 s (A034293, A348329, A175807, A273519, A281663, CPU share
0.983-0.986); **0 new terms**; 10,022 s, 8.98 picks/h. Two things it adds to this page. First, **a
per-pick reading of the programs predicts verification far better than the known-term base rates**:
scored by Brier over the 25 picks, 0.0127 against 0.1467, with the five verifiers exactly the reading's
four calls at >= .80 plus its .50 call. Second, **four of the 25 picks (16%) were program-selection
misreads** — the helper-name prefix, the helper-as-predicate, the print-loop index shift and the
hidden-output bulk printer, each described under [strategies](#strategies) above — every one predicted
from the program text before the run and every one retiring a sequence that was never actually tested.
Session 10 had counted 2 such defects in 50 picks, but from the deterministic-failure rows only; the
hidden-output kind leaves no trace in the row and is found only by reading the program. No
`searched_bound` firing (the seven bounded picks were decided in advance by the rate floor, five
"cannot fire" and none reached), and exactly the five predicted scan frontiers, all reported and none
witnessed.

Two patterns held across every PARI run up to session 6 (status history item 31). **Session 7 qualified
the first and broke the second** (item 35):

- **The 10-known-term ceiling is a gradient, not a wall.** Up to session 6, of the 64 PARI program runs,
  the 31 whose sequence had more than 10 known terms produced **0** verified runs and the 33 with 10 or
  fewer produced **15**. Session 7 got **2 of 15** many-term picks through — but **both verified in under
  60 s** (A385331 in 0.157 s, A229209 in 29.9 s), so the bigger gate is not what let them through and the
  absolute form ("0 of 31, never") fell to sampling, not to budget. Pooled it is 2 of 49, and
  P(0 of 31 | that rate) = 0.13 taking the 49 runs as the population, or 0.28 treating each as an
  independent trial — either way the two figures were never in tension. The gradient survives and is
  steep: **>10 known terms 4.1%, <=10 known terms 47.4%.**

  **Session 8 weakened it further, and this is now worth watching.** Two more many-term picks verified
  (A270393 at 11 known terms, A194099 at 28), against a pre-registered P(>=2) of 8.7%. Measured over the
  first run of each distinct sequence — the right denominator, since a session draws sequences it has
  never attempted — the rates are now **<=10 known 40.0% (16/40), >10 known 7.3% (4/55)**, against 41.9%
  and 4.5% before. **The ratio has fallen from 9.23x to 5.50x**, a 40% collapse, and it weakens at every
  threshold tested, not only at 10. Two sessions is not enough to separate drift from sampling. Note also
  that the term *count* is a crude proxy: A270393 has 11 known terms but a(11) has only **3 digits**, so
  it carries none of the difficulty the heuristic assumes.
- **A verified run can have a fittable cost history after all.** Up to session 6, `estimate.project`
  returned no fit at all in 11 of 15 verified runs and the other 4 all had `npoints = 3`, so no
  trustworthy projection had ever existed. Session 7 produced the first two, by different routes:
  **A229209's first projection at verification** had `npoints = 5`, `disagreement = 1.754` and
  `Projection.trustworthy = True`; and **A385331's fit became trustworthy during extension**, once the
  new terms themselves supplied points above the floor. So the cost cliff explanation was right about
  why it had never happened, but wrong that it never could.

  The consequence drawn here before session 7 — "the rules added by offers B and F cannot be exercised by
  any run that verifies at a 60 s budget, so testing them needs the slower pass" — was **half wrong**.
  Offers F and A were both exercised, but the slower pass is not what did it: A229209's fit was reachable
  at 60 s, and offer F's six firings came from the extension, not the gate. Offer B is still untested.

**A trustworthy projection is not a reliable one.** In the single run that produced them, attempt #139
made four trustworthy projections that were wrong by **10^4 to 10^6** — 288 s, 374 s, 486 s and 632 s
predicted for terms that cost 0.0005, 0.0005, 0.027 and 0.0004 s — and one, at a(43), that was right and
correctly stopped the run. They were harmless only because their `seconds_high` happened to fit inside
the remaining budget. The mechanism is that `estimate.assess` fits only points at or above
`CPU_FLOOR_S`, which on this sequence left **5 of 41** — precisely the terms whose smallest prime factor
happened to be large — while 14 of the 18 new terms fell below that floor (11 of them under a
millisecond) and were invisible to it.
Both value-dependence guards missed: `name_suggests_search` needs a `such that`/`for which` connective
and the name reads "the smallest prime **factor of** ...", and `_value_dependent_by_data` is fed the same
floored points and needs 6 of them. On the 12 positive-cost points it says **yes** (r^2 0.146 by n, 0.865
by value). Fixing that is next step 4 in [status](status.md#open-offers-and-next-steps), with the caveat
that on this run firing it would have gained nothing and cost 1,068 s.

**And in the dangerous direction too, since session 8.** All four of attempt #139's wrong projections
were *pessimistic*, which can only stop a run early. **A194099 (attempt #175) produced the first
optimistic one**: a(29) projected at **22.3 s** with `trustworthy`, `fit_trustworthy` and `feasible` all
1 (`fit_npoints` 12, `fit_disagreement` 2.948, `rate_drift` 1.473), for a term that is not reachable at
all — the entry itself carries `%C A194099 No more terms <= 2 * 10^38.` (Charles R Greathouse IV, 2011),
so the error is of order **10^31**. Optimism is the direction that matters, because `feasible = 1` is
exactly what stops `infeasible` from firing; a hopeless run can then consume its whole extension.

Nothing in the estimator stopped it, though it was not silent: `fit_climbing = 1` made
`Assessment.risky` True and `rate_drift` recorded the seconds-per-unit rate climbing 47%. **Those flags
are not wired to anything that ends a run.** What contained it was `over_prediction`, which watches the
term overrun its projection rather than trusting the fit — it killed at 44.78 s of extension, leaving
1,755 s unused. Note this is *not* evidence for offer B: `kill_after_s` returns `None` unless
`trusted(factor)` (`estimate.py:88-95`), so offer B can only suppress a kill, never cause one, and this
projection was trusted, so the pre-offer-B rule would have killed at the identical threshold. The
uncomfortable part is the margin — `fit_disagreement` 2.948 against a `TRUST_DISAGREEMENT` of 3.0, i.e.
**1.7%** — since a marginally worse fit would have made offer B suppress the kill and burn the full
1,800 s. What to do about `risky` is next step 10 in [status](status.md#open-offers-and-next-steps).

**Bounds published in the entries are never read.** A194099's own `.seq` file — parsed by this pipeline
— says `No more terms <= 2 * 10^38` and `All terms are odd`, and the pick ran anyway. This is not rare:
**1,537 of the 3,450 candidates in the live pool (44.6%)**, and 4,561 of all 26,814 candidates (17.0%,
2,181 of them with a PARI program), carry a comment asserting a searched bound — "No more terms <= X",
"a(n) > X, if it exists", "Next term > X", "no other terms below X". Reading them is next step 1 in
[status](status.md#open-offers-and-next-steps). Three constraints on any such rule: the counts above come
from crude patterns that need hand-checking first; the bounds are **unverified human claims**, so they may
bound what is worth spending time on but must never become evidence that a term is correct; and a bound on
a(n)'s *value* is directly usable by the predicate driver, which scans k upward, but not by the `a(n)` or
print-loop forms.

**The cost fit's own statistics were not recorded anywhere. Fixed 2026-09-21.**
`predictions.trustworthy` stores `Assessment.trusted` (`verify.Prediction.from_assessment`), not `Projection.trustworthy`,
and there was no `npoints`, `disagreement` or `rate_drift` column — so a query could not answer "has a
trustworthy fit ever happened?", the question sessions 6 and 7 were both built around, and session 7's
audit missed A229209's fit for exactly that reason. `predictions` now also stores `fit_trustworthy`,
`fit_npoints`, `fit_disagreement`, `fit_climbing` and `rate_drift`, and the 40 existing rows were
backfilled by replaying their term logs (`scripts/replay_predictions.py`). The whole history is now
**7 trustworthy fits in 19 fitted projections** — prediction #18 (A229209), #33-#37 (A385331) and #45
(A194099, added by session 8) — of which #18 is the one the audit missed, and it is the only row in the
database where a sound fit was withdrawn from the kill by the rate drift alone (`trustworthy = 0,
fit_trustworthy = 1`, drift 7.79x). #45 is the only one that ever fired an `over_prediction` kill, and
the only optimistic one.

Two corrections to how that gap was described here and in
[data and schema](data-and-schema.md#predictions-one-row-per-projected-term). The claim that *no* query
could answer it was too strong: `Projection.disagreement` is arithmetically identical to the
already-stored `predicted_s_high / predicted_s_low` (the rate cancels; verified to 2.6e-16 on all 18
fitted rows), so a ratio query would have found the same six rows — but only by luck, because
`Projection.trustworthy` also needs `npoints >= 4` and no 3-point fit in this database happens to
disagree by less than 3x. What is genuinely unrecoverable is `rate_drift`, and `npoints` on the
`exp` rows; `fit_climbing` is exactly `model = 'ratio'`, and `fit_trustworthy` follows from the ratio
alone on every `poly` or `ratio` row. The full accounting, with the mechanism behind each verdict, is in
[data and schema](data-and-schema.md#predictions-one-row-per-projected-term).

**For gp, no run can ever be judged infeasible on memory.** `estimate.assess`'s memory half is fed
`TermRecord.mem`, which for gp is the interpreter's *stack* figure (8,001,936 B on every one of attempt
#139's 42 terms), and compares it against the 6 GiB **job commit** cap — quantities that differ by ~805x
(#139's job commit peak was 4.81 GiB). A277041 died at `memory_cap` on the job cap while reporting 8 MiB
throughout, so the projection saw nothing coming. The per-term figure is the right one to *report* (gp
commits its whole `parisizemax` at startup, so the commit peak says nothing about the computation), but
it is the wrong one to compare against a commit cap.

Sessions 1 and 2 used deliberately short budgets. Session 3 used a realistic verify budget (600 s) but
still did not test it: 4 of its 5 picks had no usable PARI program, so 15 of 16 runs went to the model and
ended in milliseconds, and **nothing reached the extension phase** — the 1800 s extend budget was never
exercised.

Session 4 was the PARI-only run that tested it, and the answer is that **verification is the binding
constraint, not extension**. Five of its six runs never got through the gate, so the 1800 s extension
budget was spent exactly once; raising `--extend-s` cannot help a candidate set that cannot reproduce its
own known terms. None of the five failures was a defect — each was genuine arithmetic cost.

The reason is structural rather than a matter of budget size. A sequence carries `keyword:more` *because*
its next term is expensive, so the cost cliff sits exactly at the edge of the known terms by selection.
A247883 shows it plainly: a(1)..a(10) computed in **57 ms** in total, and a(11) not found in **1800 s**.
Session 7's P4 probe measured the same cliff head-on and more sharply: on the three sequences in the
whole corpus closest to verifying, **ten times the budget bought exactly one term** each (13→14 of 15,
26→27 of 33, and the third stopped on memory). The marginal term at the edge of the known terms costs
roughly the whole previous budget, so multiplying the budget buys terms one at a time, not verifications.

**The win is the counter-example that shows the cliff is about the edge, not the sequence.** A385331's
24 known terms cost 0.157 s in total, and a(25) alone cost 454 s — the cliff exactly at the edge, as
above. But past it the cost is not monotone at all: 11 of the 18 new terms cost under a millisecond while
a(32), a(37) and a(38) cost 66.8 s, 57.7 s and 153 s, because a(n) is the smallest prime factor of a
number — most numbers have a small one and a few have none below 10^7. A run that gets
over the cliff can therefore be very cheap afterwards, which is why the extension budget earned its keep
here and why an estimator that extrapolates a rising curve across the cliff mispredicts in **both**
directions.
Two consequences are recorded above under
[verification and estimation](#verification-and-estimation): extrapolation from the known terms is
uninformative for search-type sequences (A247883 produced no seconds projection at all, every per-term
cost being below the noise floor), and the `work` cost unit understated A377248's growth by more than 3.5x.

Three of the five sequences failed all three generations with a *byte-identical* error. The temperature
ramp (0.2/0.5/0.8 in `codegen`) and the error feedback in `RETRY` are both implemented as documented, so
this is mostly model capability rather than a defect in the retry loop. One contributing defect was found
and fixed the same day: the retry text used to be the same whatever the failure was, so a crash was
answered with advice about the sequence definition (see [strategies](strategies.md#steps)).

Session 5 measured the quick first pass with the selection check (60 s to reproduce the known terms,
sequences that could only be skipped left out). Against the two earlier PARI-only sessions it wasted no
picks (0 of 20, against 2 of 14), ran 27.6 programs per hour of wall clock instead of 7.7, and got 3.8
runs per hour past the known terms instead of 1.3. The share of runs that get past them did not change
(3 of 22), and was not expected to: most picks were searches like "numbers k such that c·b^k ± d is
prime", expensive per call. Two of its three verified runs were then stopped by the over-prediction kill
within half a minute, on projections the estimator had itself marked untrustworthy, so only one of them
used its 1800 s extension. Fixed the same day: only a trustworthy projection can kill a term now (see
[verification](verification-and-estimation.md#assessment-estimateassess)).

The step-2 run gave the model its first correct-but-slow PARI programs to beat. The hand-over worked as
designed on all three; the model did not. For these "numbers k such that" sequences it tied the index n
to the candidate k (`n += 1` next to `k += 1`, or `yield (n, n)`), and for two of the three it sent the
byte-identical program three times despite the `bad_index` guidance.

The offer-C measurement gave the same model the list contract (`members(work)`) on ten sequences, with
the results written down beforehand, and every expectation held. The list question was answered right
for all 9 sequences it was asked about. No generation failed on `bad_index` (17 of the 45 earlier ones
had). The two step-2 sequences whose programs had failed only on numbering, A247883 and A057246,
verified at the first generation, and none of the model's programs yielded the prime instead of k.
What remains is speed and correctness of the search itself: 14 of the 20 runs stopped at
`verify_timeout` (A246855, A253773, A272621, A253380, A383336), 7 of them identical programs run again
after timing out, and A345338's search was wrong again. No new term, as the entries predict for the
step-2 three.

Model check on easy, well-known sequences (outside the database, DATA terms only): correct programs for
A000005, A000108, A002385 and A000079 on the first generation; A001358 (semiprimes) failed all 9
generations across three runs by leaving out squares.
