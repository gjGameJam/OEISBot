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
| `data/runs/<A>-<YYYYmmdd-HHMMSS>-<sha8>.jsonl` | verification harness | every term a run emitted, one JSON object per line, as it arrived (a new term later voided by a list program's contract error stays `new` here; the attempt row counts it out) |
| `data/runs/<same stem>.py` | orchestrator | every Python (model-generated) program that ran, as it ran: for a `members(work)` program, with the driver that numbers its members (so its sha256 prefix is the attempt's `program_sha`) |
| `data/scratch/<A>-<lang>-<hex>/` | harness | a run's sandbox working directory; deleted after the run |
| `data/pending/attempt-<id>.pickle` | orchestrator | the full in-memory result of a win whose re-check could not reach oeis.org (outcome `recheck_pending`); deleted once a later re-check resolves it |
| `tools/python/` | `oeisbot setup` | embeddable CPython 3.11.9 with gmpy2 and sympy (about 110 MB) |
| `tools/pari/gp.exe` | `oeisbot setup` | standalone PARI/GP 2.17.4 |
| `tools/downloads/` | `oeisbot setup` | the downloaded Python zip |
| `artifacts/<A>/attempt-<id>/` | orchestrator | review folders for wins |
| `oeisbot/dashboard/static/` | `npm run build` | built dashboard frontend |

Nothing cleans up `data/runs/` or `data/bfiles/`; they grow with use.

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
| `b123456.txt` | OEIS b-file format (`n value` per line): all known terms plus the new ones |
| `program.gp` / `program.py` | the program as a human should read it: the entry's statements that were kept (for print loops, the original block), or the generated code |
| `executed.gp` / `executed.py` | exactly what ran, drivers included |
| `verification.md` | known-term source and range, offset and first emitted index, reproduced count, notes on the known terms, program origin, sha256 prefix, time to verify, the live re-check result |
| `timing.csv` | per term: `n, kind, digits, wall_s, cpu_s, work, peak_mem_bytes, arrived_at_s` |
| `predictions.csv` | per projected term: unit, model, trustworthy, feasible, predicted point/low/high seconds, predicted memory, actual seconds and memory, censored seconds, the estimator's reasons |
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
existing database needs a manual `ALTER TABLE`.

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
| `difficulty` | written by `sync` from DATA-line features, and by `fetch-bfiles` including b-file facts; the next sync overwrites it again. Informational: selection recomputes difficulty |
| `in_more` | 1 if the entry had `more` (and no excluded keyword) at the last sync |
| `synced_at` | last sync that saw this row |

### `sessions`

One row per `oeisbot run`: `id`, `started_at`, `finished_at` (NULL while running or if the process was
killed), `attempts` (all attempt rows in the session, skips included), `wins` (rows with outcome
`extended`), `machine_s` (sum of `attempts.runtime_s`), `note` (count, alpha, seed, model). The counts
are computed once, when the session ends, so a `recheck_pending` win resolved later is not added to its
session's `wins`.

### `attempts`: one row per program run or per skip

| Column | Meaning |
|---|---|
| `id` | attempt id (also the artifact folder suffix) |
| `session_id` | NULL for `oeisbot attempt` |
| `a_number` | sequence |
| `strategy` | `pari:a(n)`, `pari:predicate`, `pari:print-loop`, `python:model`; skip rows use `pari`, except the model-stage skips (`too_few_known_terms`, `model_skip`, `model_no_runnable_code`), which use `python:model` |
| `program_origin` | e.g. `A123456 %o (PARI) block 2`, `model qwen2.5-coder:14b, generation 1 (AI-generated)` |
| `program_sha` | first 16 hex digits of the sha256 of the executed script |
| `started_at`, `finished_at` | UTC ISO timestamps |
| `verified` | 1 if every known term was reproduced |
| `known_terms`, `known_source` | count and source (`bfile` or `data`) of known terms |
| `reproduced`, `new_terms` | counts |
| `runtime_s`, `cpu_s` | sandbox wall time and job CPU time (for a `verify_timeout` row, `runtime_s` is what the dead-end check compares with the next run's `verify_wall_s`) |
| `peak_mem_bytes` | clamped job peak (Python) or largest reported stack figure (gp) |
| `cost_unit` | `work` or `cpu` |
| `projected_next_s_low/high`, `projected_next_mem` | the last projection made in the run |
| `outcome` | `extended`, `verified`, `failed`, `superseded`, `recheck_pending` (new terms found, re-check not finished), `skipped` |
| `failure_mode` | why it stopped: a [stop reason](verification-and-estimation.md#stop-reasons) for runs, or a skip reason (below) |
| `detail` | human-readable detail |
| `extra` | JSON: `log` (run log path), `form` (`a(n)`, `predicate`, `print-loop`, `model`), `rewrites` (program notes), `weak_verification`, `extend_wall_s` and `mem_bytes` (the run's budgets, used by the dead-end check; absent on older rows, which therefore never count as `infeasible` or `extend_budget` dead ends), `attempt_call` (a key shared by every row of one `attempt_sequence` call, so the selection's failure penalty counts attempts, not rows: a random hex string, or `legacy-<first row id of the attempt>` on the 108 run rows written before 2026-09-19, set once from their grouping; skips have no `extra`), and `recheck` (only when new terms were found: the re-check note; while `recheck_pending`, `not done yet` or, after a failed re-check, `not done: <ErrorType>: <message>`) |
| `artifact_path` | set for wins, relative to the project root |

Skip reasons: `not_in_oeisdata`, `no_more_keyword`, `open_review`, `recheck_pending`, `bfile_error`,
`inconsistent_known_terms`, `no_supported_program`, `all_programs_dead_ends`, `verify_out_of_reach` (every
PARI program is a predicate search too long for the verify budget; since 2026-09-18), `too_few_known_terms`,
`model_skip`, `model_no_runnable_code`. Sessions no longer pick sequences that would get one of
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
nor a censored time, since its term never started. The estimator's `risky` flag and next-term bit bound
are not stored.

### `reviews`: the human queue

`id`, `a_number`, `attempt_id` (unique), `artifact_path`, `first_new_index`, `last_new_index`, `status`
(`new`, `reviewing`, `submitted`, `rejected`; enforced by a CHECK constraint), `note`, `created_at`,
`updated_at`.

- A review in `new`, `reviewing` or `submitted` blocks that sequence from being picked or attempted. So
  does an attempt with outcome `recheck_pending`.
- `db.set_review_status` refuses to mark a review `submitted` when another review for the same A-number
  is already `submitted`.

### `meta`

`schema_version`, `oeisdata_commit`, `synced_at`.

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
