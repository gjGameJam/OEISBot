# Known limitations

Current behavior that is incomplete, surprising, or differs from the design intent, with where it lives
and a suggested fix. Last reviewed 2026-09-17 against the code at that date.

## Differences from the design intent

### 1. Failure penalties do not affect the current session

`select.candidates` applies the ×2-per-failure penalty when the pool is built, and `attempt.run_session`
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

### 6. The model is never tried after a verified PARI run

`attempt._Attempter.run` marks a sequence finished when a PARI program verifies but finds no new terms,
and `attempt_sequence` then skips the model stage. A faster model-written program is never attempted
for sequences whose existing PARI program is merely slow.
**Fix:** let a verified-but-`infeasible`/`extend_budget` PARI result fall through to the model stage.

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

### Verification and estimation

- **The known terms say little about the cost of the next one, for exactly the sequences targeted here.**
  The estimator's only input is the cost history of the known terms, but a sequence carries `keyword:more`
  *because* its next term is expensive, so the cost cliff sits at the edge of the known terms by
  selection. Measured in database session 4: A247883's a(1)..a(10) cost 57 ms in total and a(11) was not
  found in 1800 s. Extrapolation cannot bridge a gap of that shape, and this is a structural limit rather
  than a tuning problem.
- **The `work` cost unit can understate growth badly.** `verify.Harness.points()` prefers instrumented
  work units whenever the program reports them, because they are hardware-independent and smooth, and
  `estimate.assess` converts them to seconds using the mean wall-per-work rate of the last five terms —
  which assumes that rate is roughly constant. When the per-unit cost is itself growing, it is not. On
  A377248 (`8191*2^k + 1` prime) work grew 1.9–2.1x per term while wall time grew 15.4–15.7x, because
  work counts candidates tested and ignores the widening primality test. Replaying `estimate.assess` on
  the recorded points projects a(8) at 149 s (range 149–734 s) from work against 1191 s (range
  1161–1191 s) from CPU; a(8) is known to exceed 516 s, so the work estimate is low by at least 3.5x and
  its whole range falls below the CPU one. The work path does flag the trouble (`climbing`, ratio model,
  `risky=True`, 4.9x disagreement) — the number misleads, not the warning.
- **Projections rarely exist for real runs.** The estimator needs 3 terms above the noise floor (50
  work units or 0.05 CPU s), excluding the first term. Short DATA-only sequences rarely have them, so
  no time projection is made, there is no over-prediction kill, and only the extension budget applies.
  All three projections recorded so far had a projected memory but no time estimate, including the one
  made after A247883 verified all ten of its known terms.
- **Coarse CPU timing.** Windows process CPU time advances in 15.6 ms steps and gp's `getabstime` in ms,
  so uninstrumented programs contribute noisy costs for fast terms.
- **Search detection is a heuristic.** The name regex flags 3,060 candidates, including names that are
  not searches, such as "First differences of the primes that are congruent to 1 mod 4". A false
  positive:
  - exempts the terms from both time-based infeasibility checks, so only the extension budget stops
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
- **The generation prompt lists module names, not function names.** `GENERATE` interpolates
  `", ".join(sorted(ALLOWED_IMPORTS))`, so the model knows `gmpy2` and `sympy` are available but has to
  guess what is in them; `gmpy2.prime_range` does not exist (sympy's is `primerange`). The function list
  is currently sent only *after* a crash, by `retry_guidance`, so the first generation still guesses.
  **Fix:** put `API_HINTS` in `GENERATE` as well, if a first-generation improvement is wanted.
  (The retry half of this was fixed on 2026-09-17: see [strategies](strategies.md#steps).)
- **Heuristics are untuned.** The difficulty factors, the "later PARI program first" ordering and the
  estimator thresholds are initial guesses. The attempts and predictions tables exist to tune them.
- **Model capability.** `qwen2.5-coder:14b` solved simple sequences but failed every real candidate it
  was given (see below), often by misreading the definition.

### Operations

- **One job at a time.** Sessions are sequential; there is no parallelism across CPU cores.
- **No pruning.** `data/runs/` and `data/bfiles/` grow without limit.
- **No schema migrations.** Schema changes need manual `ALTER TABLE` or a fresh database.
- **Runtime downloads are not hash-pinned.** `setup` prints the sha256 of the Python zip and `gp.exe`
  but does not check them against known values.
- **The dashboard has no authentication.** It binds to localhost by default.
- **The `network` pytest marker is declared but unused.** Tests that would touch the network stub it out.

## Observations from real runs

All on 2026-09-17, with the oeisdata snapshot `9566689775`, which held 26,628 candidates at the time
(26,814 once `fini,more` entries were included later that day).

| Run | Settings | Sequences | Program runs | Result |
|---|---|---|---|---|
| Manual `attempt` | PARI; verify 120 s, extend 120 s | 3 | 2 | 1 skipped (list printer); A246855 verified 3/3 known terms, no new terms in 120 s; A309238 `verify_timeout` |
| Session 1 | PARI only; verify 120 s, extend 240 s; seed 7 | 8 | 6 | 2 skipped (unsupported forms); 5 `verify_timeout`; A057246 verified 4/4, no new terms in 240 s |
| Session 2 | `--model`; verify 120 s, extend 300 s; seed 21 | 6 | 19 | 18 model generations (10 `wrong_term`, 4 `bad_index`, 2 `crash`, 2 `verify_timeout`) + 1 PARI run (`verify_timeout`, 26 of 41 known terms) |
| Session 3 (db) | `--model`; verify 600 s, extend 1800 s | 5 | 16 | 15 model generations (6 `wrong_term`, 5 `bad_index`, 4 `crash`) totalling **8 s** + 1 PARI run (A272621, `verify_timeout`, 13 of 15 known terms in 600 s) |
| Session 4 (db) | PARI only; verify 600 s, extend 1800 s; seed 101 | 5 | 6 | 5 `verify_timeout` (A273521 7/8, A101722 1/4 on each of its two PARI blocks, A391617 4/7, A377248 7/12) + A247883 verified 10/10 in 57 ms then found no new term in 1800 s |

Totals: 27 sequences, 52 program runs, **0 wins**, 1.9 machine-hours. (Six runs belong to no session:
standalone re-attempts, including the A129250 one that checked the retry-prompt fix.)

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

Model check on easy, well-known sequences (outside the database, DATA terms only): correct programs for
A000005, A000108, A002385 and A000079 on the first generation; A001358 (semiprimes) failed all 9
generations across three runs by leaving out squares.
