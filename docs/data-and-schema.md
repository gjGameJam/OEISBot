# Data, files and database schema

## Directory layout

Everything lives under the project root (`config.ROOT`), or under `OEISBOT_HOME` if that environment
variable is set. `OEISBOT_HOME` moves `data/`, `tools/` and `artifacts/` together, so a new home needs
its own `oeisbot setup`. None of these directories is committed (see `.gitignore`).

| Path | Written by | Contents |
|---|---|---|
| `data/oeisbot.sqlite3` (+ `-wal`, `-shm`) | harness, CLI | the database (below) |
| `data/oeisdata/` | `oeisbot sync` | shallow clone of `github.com/oeis/oeisdata`: `seq/A123/A123456.seq` entries and `files/A123/...` Git LFS pointers. About 2.3 GB, 676k files |
| `data/bfiles/A123/b123456.txt` | `bfile.fetch` | cached b-files, exact bytes as downloaded. `b123456.absent` is written on any 404 but only consulted when there is no oeisdata snapshot |
| `data/runs/<A>-<YYYYmmdd-HHMMSS>-<sha8>.jsonl` | verification harness | every term a run emitted, one JSON object per line, as it arrived (a new term later voided by a list program's contract error stays `new` here; the attempt row counts it out). A term is written only once it has passed its index and value checks, so a run that had none accepted — including one whose very first term was wrong — leaves no file, and its attempt row names none |
| `data/runs/<same stem>.py` | orchestrator | every Python (model-generated) program that ran, as it ran: for a `members(work)` program, with the driver that numbers its members (so its sha256 prefix is the attempt's `program_sha`) |
| `data/scratch/<A>-<lang>-<hex>/` | harness | a run's sandbox working directory; deleted after the run |
| `data/pending/attempt-<id>.json` | orchestrator | the full in-memory result of a win whose re-check could not reach oeis.org (outcome `recheck_pending`), as indented JSON with a `format` version; deleted once a later re-check resolves it |
| `data/writer.lock` | `oeisbot.lock` (the commands in `cli.LOCKED`, and `oeisbot daemon`) | the writers' lock (history item 58). An operating-system lock held on it while a command runs; its contents are only a description of the holder, `{"pid", "command", "started_at"}` (local time), emptied when the command ends, and possibly stale or empty. Nothing decides anything from the contents. Created by the first locked command; does not exist on 2026-11-23, since none has run since the lock was built. Safe to delete while no command is running. See [daemon](daemon.md#the-writers-lock) |
| `data/daemon/heartbeat.json` | `oeisbot daemon` | the last state a daemon wrote, rewritten at least every 30 s through `heartbeat.part`; fields in [daemon](daemon.md#the-heartbeat-file-and---status). Not evidence that one is running |
| `data/daemon/stop` | `oeisbot daemon --stop` | the stop request: a file holding the UTC time it was made. Deleted by the daemon that honours it, and by the next start's recovery when older than that start |
| `data/daemon/daemon-YYYYMMDD.log` | `oeisbot daemon` | the daemon's log and its sessions' output, one file per local day, UTF-8, each line prefixed `HH:MM:SS`. Never pruned. An unarmed start writes its one `not started: not armed` line here and nothing anywhere else |
| `data/daemon/armed` | `oeisbot daemon --arm` (`daemon.arm`); deleted only by `--disarm` | the user's standing permission for unattended nights (history item 58, section F): the daemon runs a night only while this file exists. It holds the local time it was written, e.g. `2026-11-23 21:05:12 (local time)`, which nothing reads; only its existence is asked (`daemon.is_armed`). Nothing the daemon does removes it. **Does not exist on 2026-11-23: the daemon is not armed, and creating it is the user's step, never an agent's.** Deleting it by hand is the same as `--disarm`. See [daemon](daemon.md#arming) |
| `tools/python/` | `oeisbot setup` | embeddable CPython 3.11.9 with gmpy2 and sympy (about 110 MB) |
| `tools/pari/gp.exe` | `oeisbot setup` | standalone PARI/GP 2.17.4 |
| `tools/downloads/` | `oeisbot setup` | the downloaded Python zip |
| `artifacts/<A>/attempt-<id>/` | orchestrator | review folders for wins |
| `oeisbot/dashboard/static/` | `npm run build` | built dashboard frontend |

Nothing cleans up `data/runs/`, `data/bfiles/` or `data/daemon/`; they grow with use. `data/daemon/`
does not exist until a daemon is first started, armed or not, or `--arm` is run (neither has happened,
as of 2026-11-23: `ls`). A run directory in
`data/scratch` that a killed process left behind is removed by `oeisbot daemon` at its next start, once
it is 6 hours old and only if its name is one the harness gives a run
([daemon](daemon.md#recovery)); nothing else removes one.

### Run log lines (`data/runs/*.jsonl`)

One object per emitted term, written the moment it arrives:

| Key | Meaning |
|---|---|
| `n` | index |
| `value` | term as a decimal string |
| `t` | seconds since the run started, at arrival |
| `cpu_s`, `work` | cumulative CPU seconds and work units reported by the program |
| `mem` | the term's memory figure in bytes |
| `dt`, `dcpu`, `dwork` | this term's own wall time, CPU time and work |
| `kind` | `known`, `new` or `unchecked` |

A log contains every term the harness accepted up to the stop. A term that failed a check (malformed
line, wrong index, wrong value) is not logged; the attempt's `detail` describes it. The log is the only
record of terms from a run whose attempt row was never written (for example, when the process was
killed during a run).

## Artifact folders

`artifacts/<A-number>/attempt-<attempt id>/`, written only for wins (verified, new terms, still new on
oeis.org). The folder is written after a successful re-check, which for a `recheck_pending` win is a
later one. It is created with an empty `.incomplete` marker file, removed once the database has recorded
the win. While the attempt is still `recheck_pending`, a folder with the marker is an unfinished write and
is replaced on the next try. The marker can also remain, harmlessly, in a recorded win's folder if the
process stopped just after recording it.

| File | Contents |
|---|---|
| `README.md` | Title with the new index range; the sequence name; a table (strategy and origin, known terms reproduced, new-term range and largest digit count, wall time on new terms, peak memory, stop reason); warnings; a five-point checklist before submitting; the new terms |
| `b123456.txt` | OEIS b-file format (`n value` per line): all known terms plus the new ones, ending with the blank line [SubmitB.html](https://oeis.org/SubmitB.html) requires (added at the call site in `artifact.write`, not in `terms.format_bfile`, which the README's new-terms fence also uses) |
| `program.gp` / `program.py` | the program as a human should read it: the entry's statements that were kept (for print loops, the original block), or the generated code |
| `executed.gp` / `executed.py` | exactly what ran, drivers included |
| `verification.md` | known-term source and range, offset and first emitted index, reproduced count, notes on the known terms, program origin, sha256 prefix, time to verify, the live re-check result |
| `timing.csv` | per term: `n, kind, digits, wall_s, cpu_s, work, peak_mem_bytes, arrived_at_s` |
| `predictions.csv` | per projected term: unit, model, trustworthy, feasible, predicted point/low/high seconds, predicted memory, actual seconds and memory, censored seconds, the cost fit's statistics (`fit_trustworthy`, `fit_npoints`, `fit_disagreement`, `fit_climbing`, `rate_drift`), the estimator's reasons |
| `run.json` | attempt id, strategy, stop and detail, cost unit, the full sandbox result, the budgets used |

README warnings, when they apply:

- **Weak verification**: fewer than 10 known terms.
- **AI-generated program**: any `python:model` result, plus **Numbered by the runner** when the model
  wrote `members(work)` and the driver in `executed.py` numbered the members, each **Hard-coded** bound
  the static scan found, and **Compare with the entry's program** when the entry's own program had
  already reproduced the known terms without finding new ones (naming it and its attempt id).
- **Program was rewritten**: each note on a program from any strategy other than `python:model`. Today
  that means the print-loop rewrites.

## Database

SQLite at `data/oeisbot.sqlite3`. `db.connect()` sets `journal_mode=WAL`, `synchronous=NORMAL`,
`foreign_keys=ON`, `busy_timeout=5000` and creates the schema if missing. The harness and CLI are the
only writers; the dashboard opens `mode=ro` connections. `schema_version` is recorded in `meta`, but
there are no migrations: the schema uses `CREATE TABLE IF NOT EXISTS`, so adding a column to an
existing database needs a manual `ALTER TABLE`. It is 2 since 2026-09-21, when `predictions` gained the
cost fit's statistics; nothing reads it, and `connect` writes it with `INSERT OR IGNORE`, so an existing
database keeps its recorded value unless a migration sets it, as that one-off backfill did. Because
`ALTER TABLE ADD COLUMN` can only append, `db.SCHEMA` lists new columns last, so a database created from
the schema and one altered in place have the same column order.

### `sequences`: the candidate table

| Column | Meaning |
|---|---|
| `a_number` (PK) | `A123456` |
| `name` | `%N` |
| `offset` | first number of `%O` |
| `keywords` | `%K`, comma-separated |
| `data_terms`, `data_last_digits` | count of DATA terms; digits of the last one |
| `program_langs` | normalized languages present, comma-separated (`pari`, `mathematica`, `maple`, `python`, `sage`, `magma`, ...) |
| `more_credits` | "more terms" credits on `%E` lines |
| `value_dependent` | name matches the search pattern |
| `bfile_status` | `NULL` (not looked up yet), `present`, `absent`, `error` |
| `bfile_terms`, `bfile_last_index`, `bfile_last_digits` | filled when a b-file is found |
| `difficulty` | what `select.difficulty` computes for the stored row. `sync` recomputes it for every row after its upsert (`db.refresh_difficulty`, one transaction), so the b-file facts `fetch-bfiles` folded in are no longer discarded; `fetch-bfiles` also writes it per row. Informational: selection recomputes difficulty at pick time and never reads the column |
| `in_more` | 1 if the entry had `more` (and no excluded keyword) at the last sync |
| `synced_at` | last sync that saw this row |

### `sessions`

One row per `oeisbot run`, and one per session `oeisbot daemon` runs: `id`, `started_at`, `finished_at` (NULL while running or if the process was
killed), `attempts` (all attempt rows in the session, skips included), `wins` (rows with outcome
`extended`), `machine_s` (sum of `attempts.runtime_s`), `note` (count, alpha, seed, model, and since
2026-09-23 a short `gp=2.17.4/GMP-6.1.2` token). The counts are computed once, when the session ends, so
a `recheck_pending` win resolved later is not added to its session's `wins`.

**The note's format since history item 58** (`attempt.run_session`):
`count=<n> alpha=<a> seed=<s> model=<name or None> verify_s=<seconds> extend_s=<seconds> gp=<token>`,
followed for a daemon's session by ` daemon=1 tier=<base|verify600|long>`. The two budgets are new: the
12 session rows written before it (ids 1 to 12) do not carry them, and their budgets are only in their
attempt rows' `extra`. A session row left open by a killed process and later closed by the daemon's
recovery has ` (closed by recovery: its process ended mid-session)` appended, and its `finished_at` is
the time of its last attempt row, not the time of the recovery ([daemon](daemon.md#recovery)).

The gp token is the half of the runtime provenance that **lasts**: the `meta` rows above are overwritten
the next time gp changes, so after an upgrade they describe no historical row at all, while `note` is
written once at `db.start_session` and never touched again (`db.finish_session` updates the counters and
leaves it alone). It is a short token rather than the full banner because the dashboard renders `note`
verbatim as the Settings column.

### `attempts`: one row per program run or per skip

| Column | Meaning |
|---|---|
| `id` | attempt id (also the artifact folder suffix) |
| `session_id` | NULL for `oeisbot attempt` |
| `a_number` | sequence |
| `strategy` | `pari:a(n)`, `pari:predicate`, `pari:print-loop`, `python:model`; skip rows use `pari`, except the model-stage skips (`too_few_known_terms`, `model_skip`, `model_no_runnable_code`), which use `python:model`, and the daemon's own `daemon_error` skip, which uses `daemon` |
| `program_origin` | e.g. `A123456 %o (PARI) block 2`, `model qwen2.5-coder:14b, generation 1 (AI-generated)`. **Not unique per (sequence, block)** since 2026-09-25: one `%o` block can yield both a function form and its own print loop, which share this label and are told apart by `strategy` and `program_sha` |
| `program_sha` | first 16 hex digits of the sha256 of the executed script |
| `started_at`, `finished_at` | UTC ISO timestamps |
| `verified` | 1 if every known term was reproduced |
| `known_terms`, `known_source` | count and source (`bfile` or `data`) of known terms |
| `reproduced`, `new_terms` | counts |
| `runtime_s`, `cpu_s` | sandbox wall time and job CPU time (for a `verify_timeout` row, `runtime_s` is what the dead-end check compares with the next run's `verify_wall_s`, and since history item 58 `cpu_s` must also be at least 80% of that `verify_wall_s`; a row with no `cpu_s` is never such a dead end) |
| `peak_mem_bytes` | clamped job peak (Python) or largest reported stack figure (gp) |
| `cost_unit` | `work` or `cpu` |
| `projected_next_s_low/high`, `projected_next_mem` | the last projection made in the run |
| `outcome` | `extended`, `verified`, `failed`, `superseded`, `recheck_pending` (new terms found, re-check not finished), `skipped` |
| `failure_mode` | why it stopped: a [stop reason](verification-and-estimation.md#stop-reasons) for runs, or a skip reason (below). `interrupted` (since history item 58) is the stop of a run its caller asked to stop; it is on a `failed` or `verified` row, or on a win's row when the run had found new terms first, and it never makes a dead end or a failure penalty |
| `detail` | human-readable detail |
| `extra` | JSON: `log` (run log path; **absent when no term was accepted**, because a term is logged only once it has passed its checks, so a run whose first term was wrong logs none — rows written before 2026-09-20 name it anyway, and that file was never created), `program` (the kept copy of a Python program as it ran, `<run log stem>.py`; Python only, and written whatever the run then does, so it is there even when `log` is not), `form` (`a(n)`, `predicate`, `print-loop`, `model`), `rewrites` (program notes), `weak_verification`, `verify_wall_s` (the verify budget the run was given; written since history item 58, absent on the 280 rows before it; the dead-end rules do not read it, the daemon's cooldown does, taking a row without it as having had any budget), `extend_wall_s` and `mem_bytes` (the budgets the run asked for) and `mem_cap_bytes` (the memory cap the feasibility check was judged against, `min(mem_bytes, free physical RAM − reserve)` as the harness read it — zero or negative when free RAM was below the reserve, which simply never matches a dead end; the `infeasible` dead end keys on this one, so a run squeezed by a busy machine is not retired — added 2026-09-20, absent on earlier rows, which therefore never count as `infeasible` dead ends; `extend_wall_s` and `mem_bytes` absent on rows older than 2026-09-18, which never count as `extend_budget` dead ends; `mem_bytes` itself is now recorded but no longer read by anything), `attempt_call` (a key shared by every row of one `attempt_sequence` call, so the selection's failure penalty counts attempts, not rows: a random hex string, or `legacy-<first row id of the attempt>` on the 108 run rows written before 2026-09-19, set once from their grouping; skips have no `extra`), `recheck` (only when new terms were found: the re-check note; while `recheck_pending`, `not done yet` or, after a failed re-check, `not done: <ErrorType>: <message>`) and `recheck_failures` (how many times in a row the win has failed to resolve with that same note; reset when the error changes, and left in place once the win finally resolves), and the searched-bound keys added 2026-09-22: `searched_bound` (the published bound as a **string** — entries reach 10^5000, which no SQLite integer holds — written on every `pari:predicate` run that has an applicable bound, whether or not the check fired), `searched_bound_quote` (the `%C` line it was read from) and `searched_bound_margin` (`config.SEARCHED_BOUND_MARGIN` as it was at the time); and, only on a run the check actually stopped, `measured_rate`, `rate_window_s` and `rate_work` (the rate the decision was made with and how thin the window behind it was) plus `verified_scan_to` — the largest value this run's own scan actually covered, which unlike the bound is measured rather than claimed; and the progress-heartbeat keys added 2026-09-23, written on every `pari:predicate` run whose scan crossed at least one block: `scan_reached` (the frontier the driver reported, as a **string** — a long scan passes 2^63; convert it in Python before comparing, and never order or compare it in SQL, where SQLite compares text lexicographically and `'9000000'` beats `'10000000'`), `heartbeats` (how many were accepted) and, only when something was dropped, `heartbeats_ignored` and `first_bad_heartbeat` (truncated), so a driver mangling every line shows as a number rather than as silence. A short scan that finished inside its first block records none of these. Three things are named apart on purpose and rank in this order: `verified_scan_to` is ours and **witnessed** (the harness watched the known terms arrive from that range), `scan_reached` is ours and **reported** (cross-checked against the work claimed for it and the fastest rate any predicate can be tested at, but still the program's own word), and `searched_bound` is an unverified **human claim**. Two keys added 2026-09-30 (history item 51): `infeasible_on` (only on `infeasible` rows: `time`, `memory` or `time+memory`, the budget the projection exceeded; `is_dead_end` compares that budget alone, and rows without the key need both as before) and `below_published_bound` (only when a new term landed at or below the entry's searched bound: `{"bound", "quote", "indices"}`; the README and the inbox show it); `review_refused` (`{"prior_review", "reason"}`, only on a win whose review was refused because the sequence has a `rejected` one); and `program_sha_backfilled` (`{"from", "on", "item"}`, on the 48 rows whose `program_sha` item 52's backfill rewrote to the sha today's builder produces for the same block and form, `from` being the old sha) |
| `artifact_path` | set for wins, relative to the project root |

Skip reasons: `not_in_oeisdata`, `no_more_keyword`, `open_review`, `recheck_pending`, `bfile_error`,
`inconsistent_known_terms`, `no_supported_program`, `all_programs_dead_ends`, `verify_out_of_reach` (every
PARI program is a predicate search too long for the verify budget; since 2026-09-18), `too_few_known_terms`,
`model_skip`, `model_no_runnable_code`, and `daemon_error` (since history item 58: written by
`oeisbot daemon`, not by an attempt, for the pick in hand when a session raised; `strategy` is `daemon`,
`session_id` is NULL and `detail` holds the exception; the daemon's cooldown then holds the sequence
back for 14 days). Sessions no longer pick sequences that would get one of
`no_supported_program`, `all_programs_dead_ends` or `verify_out_of_reach` when that can be decided offline
(see [pipeline](pipeline.md#2-selection-oeisbot-run--n-n---alpha-a---seed-s---model)), so these mostly
come from `oeisbot attempt`. Skip rows leave the run columns NULL, except `verified` and
`new_terms`, which are `NOT NULL DEFAULT 0` and hold 0. A skip row with reason `recheck_pending` is an
ordinary `skipped` row; only a program run's row carries the `recheck_pending` outcome.

### `predictions`: one row per projected term

`attempt_id`, `n`, `cost_unit`, `predicted_s`, `predicted_s_low`, `predicted_s_high`, `predicted_mem`,
`model` (`exp`, `poly`, `ratio`, or NULL when nothing could be projected), `trustworthy` (whether the
over-prediction kill acts on the projection, unless `value_dependent` is set; since 2026-09-18 this also requires that the seconds
per cost unit are not projected to drift past the kill factor, see
[verification](verification-and-estimation.md#assessment-estimateassess). This holds for rows stored since
offer B: before it the kill ignored the flag, so the two kills of session 5, attempts 57 and 62, are stored
with `trustworthy = 0`), `feasible` (0 when the projection stopped the run: projected memory over the
budget, or projected time over the remaining extension on a trustworthy cost fit; before offer F on
2026-09-19 an untrustworthy fit could do it too, as for attempt 93, the only such row),
`value_dependent`, `actual_s` and `actual_mem` (NULL if the term never finished), `censored_s` (set on
a verified run's last projection when it has no actual time and was feasible: the time from that
projection to the end of the run). A projection that stopped the run as infeasible has neither an actual
nor a censored time, since its term never started. The estimator's next-term bit bound
(`Assessment.next_bits_high`) and `Projection.parity_split` are not stored.

Then the cost fit's own statistics, added 2026-09-21: `fit_trustworthy` (`Projection.trustworthy`),
`fit_npoints`, `fit_disagreement`, `fit_climbing` and `rate_drift` (`Assessment.rate_drift`). All five
are NULL together, exactly when nothing could be fitted — so NULL means "no cost fit", never "the fit
said no". The estimator's `risky` flag is not stored but can be reconstructed from them, and the
`model IS NULL` arm is not optional: without it SQL's three-valued logic returns NULL, not 1, for every
row that had no fit (`risky` is hard-coded true there, `estimate.py:278`):

```sql
SELECT id, model IS NULL OR value_dependent OR NOT fit_trustworthy OR fit_climbing AS risky FROM predictions;
```

**`trustworthy` does not answer "was the cost fit trustworthy?"** It stores `Assessment.trusted`
(`verify.Prediction.from_assessment`) — `fit_trustworthy` **and** the rate-drift test — so a sound fit
whose rate is drifting reads `trustworthy = 0, fit_trustworthy = 1`. That pair is the point of the new
columns: it is the question sessions 6 and 7 were both designed around, and it cost session 7's audit its
biggest miss (A229209, prediction #18: a 5-point trustworthy fit withdrawn from the kill by a 7.79×
drift, found only by replaying the term log). `trustworthy` keeps its name and meaning, and is consistent
across the whole table: before offer B `from_assessment` stored `Projection.trustworthy` instead, but
replaying all 45 rows shows the two definitions never disagree on this data, because the older fits were
untrustworthy either way.

How much of this was genuinely unrecoverable from the columns that already existed. The first answer
written here got two of these wrong, so each is now stated with the mechanism that decides it:

- **`rate_drift`: entirely unrecoverable.** Nothing stored constrains it except `trustworthy`, which
  only says which side of the kill factor it fell on.
- **`fit_climbing`: fully recoverable — it is exactly `model = 'ratio'`.** In `estimate.project` a
  climbing series is the only thing that selects the ratio model and always selects it
  (`estimate.py:190-200`), so the two are equivalent, not merely correlated. Confirmed on 4,000
  synthetic series and on all 18 fitted rows: no counterexample.
- **`fit_disagreement`: recoverable in practice.** It equals `predicted_s_high / predicted_s_low`,
  because the seconds-per-unit rate is a common factor (`estimate.py:286`); checked on all 18 fitted
  rows, agreeing to 2.6e-16. Three things break it, none yet seen, and they fail in two different ways.
  **Silently**, returning a plausible wrong number: the `floor` clamp, when **either** fit falls below
  the newest observed cost (`estimate.py:209-210` — so a *flat* series can clamp, but a falling one
  never can, since the floor is then `-inf`), and the `min(…, 700)` saturation in `project`'s return,
  which a super-exponential fit can reach. **Visibly**, returning nothing: `predicted_s_low` underflows
  to `0.0` once its exponent falls below about -745 (`math.exp(-745)` is 4.9e-324, `math.exp(-746)` is
  `0.0`), and SQLite then gives NULL for the ratio. The underflow is the *safe* failure of the three —
  the two silent ones are the reason to store the number rather than recompute it.
- **`fit_npoints`: the exact value is unrecoverable**, but not opaque: `model IN ('poly', 'ratio')`
  implies at least 4 points, since `poly` needs `len(series) >= 4` and `ratio` needs `_is_climbing`,
  which returns False below 4 (`estimate.py:154-157, 194-198`). That recovers the `>= 4` threshold, not
  the value: #32 is `poly` with 4 points and #18 is `ratio` with 5, and nothing stored separates those
  from 6 or 8. For the threshold itself only `exp` rows are ambiguous — and 16 of the 18 fitted rows
  are `exp`.
- **`fit_trustworthy`: recoverable for every `poly` and `ratio` row** (they already imply
  `npoints >= 4`, leaving the ratio test), and ambiguous only for `exp` rows, where `npoints` may be 3.
  A plain `predicted_s_high / predicted_s_low <= 3` query happens to return exactly the right six rows
  today only because no 3-point fit in this table disagrees by less than 3× — luck, not a property.

One more relation, looked for as a further recovery path and worth recording because it is not one:
`predicted_s` is always *exactly* `predicted_s_low` or `predicted_s_high`, never between them, because
`Projection.point` is one of the same two fits through the same clamps (18 of 18 fitted rows: 16 low,
2 high). What that recovers is the *direction* of the disagreement, not its size and not `npoints`.
`predicted_mem` comes from a separate `project` call on the memory series and constrains the cost fit
not at all.

So the two columns that carry information no query could otherwise get are **`fit_npoints`** (for `exp`
rows) and **`rate_drift`**. The other three are stored because they are free, direct to query, and
record what the estimator decided at the time rather than what today's constants would decide.

The rows written before 2026-09-21 were backfilled by replaying each attempt's term log
(`scripts/replay_predictions.py`); see [development](development.md#helper-scripts) for what makes that
faithful. One caveat on the oldest rows: `Assessment.rate_drift` did not exist before 2026-09-19, so for
predictions #5, #6 and #10-#13 the stored `rate_drift` is a quantity that run never computed. It is a
well-defined statistic of that run's own term log, and all six have `fit_trustworthy = 0`, so nothing
downstream reads differently — but "what `trustworthy` was decided from" is literally true only from
2026-09-19 on.

### `reviews`: the human queue

`id`, `a_number`, `attempt_id` (unique), `artifact_path`, `first_new_index`, `last_new_index`, `status`
(`new`, `reviewing`, `submitted`, `rejected`; enforced by a CHECK constraint), `note`, `created_at`,
`updated_at`.

- A review in `new`, `reviewing` or `submitted` blocks that sequence from being picked or attempted. So
  does an attempt with outcome `recheck_pending`.
- A review in `rejected` blocks its sequence from being **picked** (since history item 58,
  `select.candidates`), though not from a targeted `oeisbot attempt`. So every status a row can have
  now keeps its sequence out of the draw, and no command deletes a review row.
- `db.set_review_status` refuses to mark a review `submitted` when another review for the same A-number
  is already `submitted`.
- `db._insert_review` refuses (`db.ReviewRefused`) to open a review for an A-number that has a
  `rejected` one (2026-09-30, history item 51). `db.record_win` catches that inside its transaction: the
  attempt is still marked `extended` with its artifact, `extra.review_refused` = `{"prior_review": id,
  "reason": ...}`, and no row is inserted. Caught inside on purpose — raised out of the transaction, the
  rollback would leave the attempt `recheck_pending` and it would be retried, and refused, every session.
- `db.review_rows` joins each review with its attempt (`strategy`, `program_origin`, `new_terms`,
  `runtime_s`) and the sequence's `name`; `oeisbot review list` and `/api/reviews` both read those.
- **There is exactly one row** as of 2026-09-21: `#1 A385331 a(25)..a(42) new`, from session 7, the
  project's first win (status history item 35). It is waiting on the user, and while it sits in `new`
  A385331 is blocked from every session — which is correct, but means the row should not be left
  indefinitely. (Reviews #2 and #3 were added by session 10 and are `rejected`.) A385331 is *not* a
  dead end (`is_dead_end` needs `new_terms = 0`), and until history item 58 closing the review as
  `rejected` made it pickable again, to be re-run from a(1). **That is no longer so**: `submitted` and
  `rejected` both keep it out of the draw, and only a targeted `oeisbot attempt A385331` after a
  `rejected` close would run it.

### `meta`

`schema_version`, `oeisdata_commit`, `synced_at`, since history item 58 `pulled_at`, and since
2026-09-23 (history item 43) the two runtime versions below.

`synced_at` is written by every sync, `oeisbot sync --no-pull` included, so it says when the candidate
table was last rebuilt, not how old the mirror's data is. **`pulled_at`** is written only by a sync that
pulled (`oeisdata.sync` with `pull=True`: `oeisbot sync` without `--no-pull`, and the daemon's nightly
sync). `oeisbot daemon` decides from it whether the mirror is too stale to climb to longer budgets, and
whether a skip has been followed by a pull (`daemon.pulled_at`); where the key is absent it falls back
to `synced_at`. The live database has no `pulled_at` row on 2026-11-23: no sync has pulled since the key
was added.

The **runtime versions**:

| key | example |
|---|---|
| `gp_version` | `GP/PARI CALCULATOR Version 2.17.4 (released) amd64 running mingw (x86-64/GMP-6.1.2 kernel) 64-bit version compiled: Jun 20 2026, gcc version 14-posix (GCC) …` |
| `sandbox_python_version` | `Python 3.11.9 (tags/v3.11.9:de54cf5, Apr 2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]` |

Written by `oeisbot setup` and refreshed at the start of every `oeisbot run`, so an upgrade between the
two is still recorded. The whole banner is kept, collapsed to one line and capped at
`setup_tools.RUNTIME_VERSION_CHARS` (300): the **GMP kernel** is what `ispseudoprime` actually runs on,
and the `compiled:` line is the only thing that tells two builds of one version on one GMP apart. The cap
cuts at a word boundary when it would otherwise split one, so the stored value can be a little shorter
than 300 — a truncated `Version 2.17` would be a plausible, wrong, permanent record.

A probe that cannot be trusted records `unknown` rather than a plausible-looking guess. Four ways that
happens: the binary is missing or the probe times out (10 s); a non-zero exit; no output; or exit 0 from
something whose banner does not say `GP/PARI` (`Python ` for the other key) — **including a real gp
behind a wrapper whose preamble runs past the cap**, because the check is applied to the value that gets
stored, not to the full text. So `unknown` beside a `gp --version` that visibly works by hand means a
wrapper, a timeout, or a banner past the cap.

`attempts.program_sha` already pins the *program* text (it hashes `Program.executed`, driver included);
these pin the *runtime*, which nothing recorded before. Rows written before 2026-09-23 are genuinely
unattributable and are deliberately **not** backfilled — see
[known limitations](known-limitations.md#runtime-provenance).

### `pick_snapshots` and `pick_snapshot_rows`: the pool a session drew from (history item 54)

The dashboard's [Pick map](dashboard.md#pick-map) shows how each candidate's pick chance moved since an
earlier look at the pool, so something has to remember the earlier look. These two tables are that
memory. Nothing else reads them and nothing in the attempt flow depends on them.

`pick_snapshots`, one row per stored snapshot:

| Column | Meaning |
|---|---|
| `id` (PK) | snapshot id; also the order: a larger id is a newer snapshot |
| `pool` | `pari` (what `oeisbot run` draws from) or `model` (`run --model`). Checked in Python against `db.POOLS`, not by a SQL constraint, so a third pool needs no schema change |
| `taken_at` | UTC ISO timestamp |
| `session_id` | the session whose picks were drawn from this pool; NULL for one taken by `oeisbot snapshot` or by `oeisbot sync` |
| `n` | how many candidates the pool held |
| `digest` | sha256 of the sorted `(a_number, difficulty)` pairs, hashing each float's `repr` so a change in the last bit counts (`db.pick_digest`). Two snapshots, or a snapshot and the live pool, are "the same pool" exactly when their digests are equal |
| `budgets` | `attempt.budgets_json(budgets)`: the `Budgets` the pool was built under, as JSON with sorted keys. NULL on a row written by something that did not pass it |
| `rules` | `attempt.rules_fingerprint()`: 12 hex digits hashing the code that decides who is in a pool: the sources of `Runnable`, `PariPlan`, `pari_plan`, `db.is_dead_end`, `oeisdata.load_entry`, `bfile.cached` and `bfile.known_terms`, the whole files `select.py`, `strategies/pari.py` and `ingest/seqfile.py`, and the values of `db.DETERMINISTIC_FAILURES`, `db.OPEN_REVIEW_STATUSES`, `db.EXTEND_DEAD_END_MIN_CPU_SHARE` and `config.CODEGEN_MIN_KNOWN_TERMS`. Line endings are normalised first, so a checkout that converts CRLF to LF does not change it. `unknown` if a source cannot be read |

`pick_snapshot_rows`, one row per candidate in a snapshot: `snapshot_id`, `a_number`, `difficulty`, primary
key `(snapshot_id, a_number)`, `WITHOUT ROWID`, `ON DELETE CASCADE` from the header. The row holds the
**effective** difficulty `select.candidates` computed (features times failure history), because that is
what the weight `d ** -alpha` is taken from. It holds no pick chance: that depends on `alpha`, which the
map lets the reader change, so it is derived at read time (`pickmap.chances`). A snapshot is about 3,400
rows for `pari` and about 26,700 for `model`.

- **Written in three places.** `attempt.run_session` records the pool right after it is built and before any
  program runs, so the snapshot is exactly the pool the picks came from (`attempt.snapshot_pool`, which
  logs and swallows any failure: a session that cannot write a snapshot must still run). An explicit
  `a_numbers` list builds no pool and so records none. `oeisbot snapshot [--all]` records the current
  pool without running anything, under the default budgets. `oeisbot sync` records the PARI pool after it
  has refreshed the data (`attempt.snapshot_after_sync`, history item 55), under the budgets of the newest
  PARI snapshot, and **not at all** when the per-sequence check failed for any candidate: a session
  records such a pool because it drew from it, but a sync's snapshot is only a record, and the sequences the
  failed check dropped would show up as arrivals in the next comparison. Like `snapshot_pool`, it logs and
  swallows any failure. The dashboard writes none.
- **One transaction, write lock first.** `db.record_pick_snapshot` compares, inserts the header and rows,
  and prunes inside one `BEGIN IMMEDIATE`, so two writers cannot both decide the pool is new and a crash
  leaves the old state or the new one, never a header without rows.
- **A pool identical to the newest snapshot of its pool is not stored again** (the call returns `None`).
  So not every session has a snapshot: one that drew from a pool nothing had changed since adds no rows.
  `session_id` therefore names the session that *first* saw the pool, and is NULL if a sync or `oeisbot
  snapshot` saw it first, even when a session later draws from the same pool. What the duplicate does do is
  **replace that snapshot's `budgets` and `rules`** (`COALESCE(new, old)`, so a NULL never erases a
  value): they describe the newest session that drew this very pool, and an edit to the rule sources
  that provably changed nothing must not leave the snapshot stamped with a fingerprint the map then
  reports as "the rules changed".
- **An empty pool is stored** (`n` = 0, no rows) like any other, so a later pool that is not empty is
  seen as a change, and the map then compares against that empty baseline: no candidate is in both, so
  every tile is `new`.
- **Retention is per pool**: `config.PICK_SNAPSHOTS_KEPT` = 30 for `pari`, 10 for `model` (the model pool
  is eight times as large). The oldest are deleted in the same transaction that writes a new one. The map
  compares against ONE earlier snapshot, so the rest is history to look back on, not something the view
  needs more of.
- **The tables are created by the writable `connect()` only** (`CREATE TABLE IF NOT EXISTS`, like every
  other table; there are no migrations). A read-only connection cannot create them, so the dashboard
  checks `db.has_pick_snapshots` and treats a database nothing has written to since they were added as one
  with no snapshots: the map still draws, every tile gray, with a note that there is nothing to compare
  with yet.

## Useful queries

```sql
-- what is stopping runs
SELECT failure_mode, COUNT(*) FROM attempts WHERE outcome != 'skipped' GROUP BY 1 ORDER BY 2 DESC;

-- estimator accuracy on finished terms
SELECT a.a_number, p.n, p.cost_unit, p.model, p.predicted_s, p.actual_s, p.actual_s / p.predicted_s AS ratio
FROM predictions p JOIN attempts a ON a.id = p.attempt_id
WHERE p.actual_s IS NOT NULL AND p.predicted_s > 0 ORDER BY ratio DESC;

-- wins and where to read them
SELECT r.id, r.a_number, r.first_new_index, r.last_new_index, r.status, r.artifact_path FROM reviews r ORDER BY r.id DESC;

-- sequences most often attempted without success
SELECT a_number, COUNT(*) FROM attempts WHERE outcome IN ('failed', 'verified') GROUP BY 1 ORDER BY 2 DESC LIMIT 20;
```
