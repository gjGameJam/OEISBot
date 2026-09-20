# Known limitations

Current behavior that is incomplete, surprising, or differs from the design intent, with where it lives
and a suggested fix. Last reviewed 2026-09-20 against the code at that date.

## Differences from the design intent

### 1. Failure penalties do not affect the current session

`select.candidates` applies the ×2-per-failed-attempt penalty when the pool is built, and `attempt.run_session`
draws all sequences before attempting any. A failure only changes the next session's odds. The sum tree
serves sampling without replacement, not the "update weights after failures" the spec described.
**Fix:** draw one sequence at a time and update its leaf (and related candidates, if any) after each
attempt.

### 2. `sequences.difficulty` is stale and unused

`oeisdata.sync` recomputes difficulty from DATA-line features only and overwrites the column on every
sync, discarding the b-file facts that `fetch-bfiles` had folded in. `select.candidates` never reads the
column: it recomputes difficulty from each row at pick time. The column only matters to someone querying
the database by hand.
**Fix:** drop the column, or have sync include the stored `bfile_*` columns and make selection read it.

### 3. The POSIX sandbox backend cannot run the pipeline

`sandbox/posix.py` exists but has never run. The rest of the project assumes Windows: `config.py`
hard-codes `tools/python/python.exe` and `tools/pari/gp.exe`, and `oeisbot setup` downloads Windows
binaries and sets AppContainer ACLs. The POSIX backend also has no filesystem confinement.
**Fix:** platform-specific runtime paths and setup, a real test run on Linux/WSL, and a low-privilege
user or container for filesystem isolation.

### 4. `oeisbot run -n` is silently capped at 25

`attempt.run_session` uses `min(count, budgets.session_attempt_cap)` without saying so.
**Fix:** print a warning, or expose the cap as a flag.

### 5. No CPU-time limit in the pipeline

The sandbox supports a job CPU cap (`Limits.cpu_s`, tested), but `verify.Harness.run` never sets one.
Wall clock is the only time limit. Jobs run at below-normal priority, so a busy machine slows them down
rather than the other way around.
**Fix:** set `cpu_s` from the budgets if CPU-time accounting is wanted.

### 6. (Fixed 2026-09-18) The model was never tried after a verified PARI run

A PARI program that reproduces every known term but finds nothing new now still ends the PARI stage, but
with `--model` the model stage runs next and is told the entry's program is correct but too slow (see
[pipeline](pipeline.md#4b-local-model-code-generation---model-only)). The heading is kept so references to
"item 6" stay valid.

## Further issues found while documenting

### Pipeline and recording

- **Pending re-checks are saved as pickles.** A win waiting for its re-check is kept in
  `data/pending/attempt-<id>.pickle`. A code change to the pickled classes (`AttemptResult`, `Program`,
  `KnownTerms`, `TermRecord`, `Prediction`, `RunResult`, `Budgets`) or enums (`verify.Stop`,
  `sandbox.Status`) before the re-check succeeds can make it fail to load or fail when used. Either way
  the attempt stays `recheck_pending` and its sequence stays blocked until the outcome is changed by hand
  (see [operations](operations.md#a-win-whose-re-check-failed-recheck_pending)). The new terms remain in
  the run log.
  **Fix:** serialize the result as JSON, or rebuild the artifact from the run log.
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
  wasted picks per 20 — stands: measured on the pool a PARI-only session draws from (3,552 candidates
  after `Runnable`), the 65 are **1.97%** of the pick weight and **0.39** picks per 20. With `--model` on
  it is 0.47% and 0.09, because nothing leaves that pool.
  A *bare* mention of another entry's A-number is deliberately still allowed: gp does not fail on one.
- **A re-check that fails the same way every time keeps a win pending forever.** Only transient errors
  are retried within the run, but every later `oeisbot run` tries again (up to two requests to oeis.org
  per pending win) and logs the same error, until someone intervenes as above.
- **A session's `wins` count misses late re-checks.** `sessions.wins` is computed when the session ends,
  so a `recheck_pending` win resolved later is not added to the session that found it. The dashboard's
  Sessions table shows that stored count. The header and the per-day chart count `attempts` directly, and
  a late win appears on the day its run started.
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
- **The infeasible dead-end check compares configured budgets, not the effective memory cap.** A run
  may be judged infeasible on memory because the harness capped it at free physical RAM − 3 GiB, below
  `mem_bytes`. The program then stays a dead end, at the same `--extend-s` and `--mem-gib`, even after
  RAM is freed. **Fix:** store the effective cap (`Harness.mem_cap`) and compare against the cap the
  next run would get.
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

### Verification and estimation

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
  All 6 time projections stored from real runs were untrustworthy, so in practice the time check now
  stops almost nothing: the extension budget does, and a used-up extension is itself a dead end at that
  budget when the job had at least 80% CPU. A run that goes on can also end as `memory_cap` or `disk_cap`,
  or be killed (`over_prediction`) once a later projection is trusted; none of these is a dead end, so
  it may be run again later. Judging an untrustworthy fit by its low
  estimate instead was weighed and not chosen: it would have kept 5 of the 7 right stops, but still
  stopped terms that finished in time once little extension time was left (A350878's a(14): low 44.5 s,
  actual 0.3 s), and of the 28 finished projections with an untrustworthy fit (per run log), 10 took less
  than the low end.
- **Projections rarely exist for real runs.** The estimator needs 3 terms above the noise floor (50
  work units or 0.05 CPU s), excluding the first term. Short DATA-only sequences rarely have them, so
  no time projection is made, there is no over-prediction kill, and only the extension budget applies.
  Of the thirteen projections recorded so far, seven had a projected memory but no time estimate,
  including the one made after A247883's PARI program verified all ten of its known terms. The other six
  are A277532 and A390295, twice each (session 5 and the offer-B check), and the first new terms after
  the offer-C model programs for A247883 and A057246 verified (attempts 92 and 93); all rested on 3
  points and none was trustworthy, which since 2026-09-18 also means no kill and since 2026-09-19 no
  infeasible stop on time.
- **Only predicate searches have a static cost bound.** `pari.out_of_reach` knows that a predicate driver
  must call the predicate once per integer up to the last known term. Most expensive predicates are
  expensive per call instead (primality tests of `c·b^k ± 1` with a growing `k`); nothing flags those in
  advance, so each still costs one full verify budget before it becomes a dead end. Measured on history,
  the bound would have avoided 1 of the 13 verify timeouts (A391617); its main effect is on the pool (393
  sequences left out at 60 s).
- **The short verify budget also applies to model programs.** A correct but slow generated program now
  stops at `verify_timeout` after 60 s instead of 600 s (the retry then asks for a faster algorithm).
- **Coarse CPU timing.** Windows process CPU time advances in 15.6 ms steps and gp's `getabstime` in ms,
  so uninstrumented programs contribute noisy costs for fast terms.
- **Search detection is a heuristic.** The name regex flags 3,060 candidates, including names that are
  not searches, such as "First differences of the primes that are congruent to 1 mod 4". A false
  positive:
  - exempts the terms from the time-based infeasibility check, so only the extension budget stops
    them;
  - exempts them from the over-prediction kill;
  - raises difficulty ×1.5.
- **B-file lines with trailing text are still used.** A line like `12 345 extra` is counted as malformed
  (noted) but its index and value become a known term.
- **Next-term size bound is computed but discarded.** `next_bits_high` and the `risky` flag are not
  stored in the database or artifacts.
- **No checkpoint/resume.** Only finished terms are saved; a killed run restarts from the offset.

### B-files are almost absent from this candidate set

- **Only 68 of the 26,814 candidates have a b-file** (0.25%), against 243,052 of the 399,307 sequences in
  the mirror (61%). The `more` keyword selects for sequences with few known terms, which are exactly the
  ones nobody has written a b-file for. Measured by `fetch-bfiles --all` on 2026-09-17, which resolved
  every candidate (68 `present`, 26,746 `absent`, 0 errors) in about three minutes.
- **Most real candidates are therefore verified against DATA only**, and this is structural rather than a
  gap that prep work can close. All 27 sequences attempted so far had no b-file, so known terms came from
  the DATA line; most had fewer than 10 terms, which the artifact flags as weak verification.
  The b-file path is covered by unit tests but has still not been exercised by a live run, and only those
  68 sequences could ever exercise it.

### Strategies

- **PARI list printers and vector builders are unsupported** (`lista(nn)`, `first(n)`, triangle
  `row(n)`): 434 candidates have only a list printer, 892 have nothing usable.
- **Predicate searches start at 1**, and **print-loop rewrites** can change a program's meaning beyond
  the known terms (see [strategies](strategies.md#correctness-caveats)).
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
  tail. Scrubbing was considered and not chosen by the user. **Fix, if wanted:** scrub these texts,
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
  timeouts so far had 97% CPU or more, but 5 of the 30 PARI ones had less than 80% (jobs run at
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
- **No pruning.** `data/runs/` and `data/bfiles/` grow without limit.
- **No schema migrations.** Schema changes need manual `ALTER TABLE` or a fresh database.
- **Runtime downloads are not hash-pinned.** `setup` prints the sha256 of the Python zip and `gp.exe`
  but does not check them against known values.
- **The dashboard has no authentication.** It binds to localhost by default.
- **The `network` pytest marker is declared but unused.** Tests that would touch the network stub it out.

## Observations from real runs

All on 2026-09-17 and 2026-09-18, with the oeisdata snapshot `9566689775`, which held 26,628 candidates
at first (26,814 once `fini,more` entries were included on 2026-09-17).

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

Totals: 67 sequences, 129 program runs, **0 wins**, 5.5 machine-hours. (39 of the runs, and 1 skip, belong
to no session: standalone `oeisbot attempt` runs, including the A129250 re-attempt that checked the
retry-prompt fix, the 12 runs of the step-2 attempt, the 2 of the offer-B check and the 20 of the
offer-C measurement.)

Two patterns hold across every PARI run recorded so far, not just one session (measured after session 6,
status history item 31):

- **Nothing with more than 10 known terms has ever verified.** Of the 64 PARI program runs, the 31 whose
  sequence had more than 10 known terms produced **0** verified runs; the 33 with 10 or fewer produced
  **15**. Verified runs' known-term counts are 3, 3, 4, 4, 5, 5, 6, 6, 6, 6, 8, 9, 9, 10, 10 (median 6);
  `verify_timeout` runs span 2 to 72 (median 12). This is the verify gate, not the selection weighting:
  pick weight tracks population share across known-term buckets. A larger `--verify-s` is the only lever
  that can move it.
- **No verified run has ever had a fittable cost history.** Replaying each verified run's first
  projection from its term log: `estimate.project` returned no fit at all in **11 of 15**, and the 4 fits
  all had `npoints = 3`. Since `Projection.trustworthy` needs `disagreement <= 3` *and* `npoints >= 4`,
  **no verified run has ever been able to produce a trustworthy projection**, so neither the
  over-prediction kill nor the infeasible-on-time stop has ever had grounds to fire on one. The cause is
  the cost cliff below (these terms cost far under `WORK_FLOOR` / `CPU_FLOOR_S`), not the number of known
  terms: A277532 has 6 known terms and produced a fit, A247883 has 10 and had 0 points above the floor.

  A practical consequence: the rules added by offers B and F cannot be exercised by any run that verifies
  at a 60 s budget, so testing them needs the slower pass, not another quick session.

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
