# Operations guide

How to install, run, read results, review a win, and fix common problems. Commands assume a PowerShell
or Git Bash prompt in the project root.

## Requirements

| Need | Version used | Notes |
|---|---|---|
| Windows 10/11 x64 | Windows 11 Pro | The sandbox is Windows-only (Job Objects + AppContainer). No admin rights needed. |
| Python | 3.11.9 | Host interpreter for the harness; the sandbox gets its own copy |
| uv | 0.12 | Creates the venv and installs sandbox packages (pip works as a fallback) |
| git | Git for Windows | For the oeisdata mirror |
| Node.js | 24 | Only to build the dashboard frontend |
| Ollama + `qwen2.5-coder:14b` | Ollama 0.34.1 | Only for `--model`. About 8.4 GB of model files; fits a 12 GB GPU with an 8k context |

Disk: about 2.3 GB for the oeisdata checkout, 130 MB for sandbox runtimes, plus logs, b-files and
artifacts. By default the sandbox stops any job if free disk drops below 8 GiB, so keep more than that
free.

## First-time setup

```
uv venv .venv --python 3.11
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
.venv\Scripts\oeisbot setup
.venv\Scripts\oeisbot sync
.venv\Scripts\python -m pytest            # 145 tests, about 25 s; confirms the sandbox works on this machine
```

Optional dashboard: see [dashboard](dashboard.md#running-it).

Optional local model:

```
winget install --id Ollama.Ollama --exact --source winget
ollama pull qwen2.5-coder:14b
.venv\Scripts\oeisbot model-check        # first call loads the model (about a minute)
ollama ps                                # PROCESSOR should read 100% GPU
```

## Everyday use

```
.venv\Scripts\oeisbot sync                         # refresh the oeisdata mirror (about 70 s)
.venv\Scripts\oeisbot run -n 10                    # pick and attempt 10 PARI-bearing sequences
.venv\Scripts\oeisbot run -n 10 --model            # any candidate; model fallback after PARI
.venv\Scripts\oeisbot attempts --limit 30          # what happened
.venv\Scripts\oeisbot review list                  # wins waiting for review
```

A session runs sequentially in the foreground and prints one line per step:

```
[A246855] known a(1)..a(3): 3 terms from data
[A246855] running pari:print-loop from A246855 %o (PARI) block 1
[A246855] -> verified: extend_budget (extension budget 120 s used); reproduced 3/3, 0 new, 122.8 s, peak 8 MiB
```

With default budgets one sequence can take over 3 hours (10 min to verify, 3 h to extend, up to 3
programs), so long sessions are best left running unattended.

Stopping a session with Ctrl+C (or closing the window) ends the harness. The sandboxed job is killed
with it by the Job Object's kill-on-close setting (tested for a killed harness). The session row is
closed on Ctrl+C but stays unfinished if the process is killed outright. The interrupted run gets no
attempt row, but every term it produced is already in `data/runs/`.

## Command reference

| Command | Purpose | Options |
|---|---|---|
| `setup` | install sandbox runtimes, grant access, create the database | |
| `sync` | update oeisdata and rebuild `sequences` | `--no-pull` (use the current checkout) |
| `stats` | languages present among candidates | `--forms` (classify PARI program shapes) |
| `queue` | candidates with difficulty and pick probability | `--alpha A` (1), `--all` (include non-PARI), `--limit N` (40), `--sort difficulty\|weight\|a` |
| `pick` | a weighted random draw, without attempting | `--alpha`, `--all`, `-k N` (10), `--seed S` |
| `attempt A... ` | attempt specific sequences (no session) | budget flags, `--model`, `--no-recheck` (testing only) |
| `run` | pick and attempt | `-n N` (5; silently capped at 25), `--alpha`, `--seed`, `--model`, budget flags |
| `recheck` | retry the oeis.org re-check of wins left as `recheck_pending`; exits with status 1 if any are still pending | |
| `model-check` | confirm the model server and model answer | |
| `fetch-bfiles` | look up b-files for the easiest candidates whose status is not `present` or `absent` (so earlier errors are retried); updates b-file facts and the stored difficulty | `--limit N` (100 successful lookups; errors do not count), `--all` |
| `attempts` | recent attempt rows and failure-mode counts | `--limit N` (30), `--failure MODE` |
| `review list` | all reviews | |
| `review set ID STATUS` | change a review's status | `STATUS` = `new`, `reviewing`, `submitted`, `rejected`; `--note TEXT` |
| `dashboard` | read-only web UI | `--host` (127.0.0.1), `--port` (8765) |

Budget flags on `attempt` and `run`: `--verify-s` (600), `--extend-s` (10800), `--mem-gib` (6),
`--max-new` (200). Every other limit is a constant in the code:

- RAM and disk reserves, scratch cap, over-prediction factor and session cap: `Budgets` in
  `oeisbot/config.py`;
- model generations per sequence: `CODEGEN_ATTEMPTS` in `oeisbot/config.py`;
- PARI programs run per sequence: `MAX_PROGRAMS_PER_SEQUENCE` in `oeisbot/attempt.py`;
- estimator thresholds: the constants at the top of `oeisbot/estimate.py`.

## Reading results

### Stop reasons, and what to do about them

| Stop reason | Usually means | Try |
|---|---|---|
| `verify_timeout` | the program cannot reproduce the known terms in time (common: the last known terms were expensive for their authors too) | a longer `--verify-s`, or accept that the sequence is hard |
| `wrong_term` | wrong program, or the program computes a different sequence than the entry's DATA | nothing: recorded as a dead end for this program |
| `bad_index` | the program starts at a different index than the offset | for PARI this points to an entry whose program and offset disagree |
| `crash` / `incomplete` | program error, or it stopped early (often a built-in limit) | read `detail`; dead end |
| `memory_cap` | job hit its memory cap, or the machine ran low on RAM | raise `--mem-gib` if RAM allows, or close memory-hungry apps (Ollama keeps several GB loaded) |
| `infeasible` | verified; the next term's projection exceeds the remaining budget (time, or memory: the reasons are in `detail`) | a longer `--extend-s` or a larger `--mem-gib`. Without a larger budget the program is a dead end and is not re-run for the same known terms |
| `over_prediction` | verified; a new term ran far past its projection | check the estimator view; the projection may be poor for this sequence |
| `extend_budget` | verified; the budget ran out without (more) new terms | a longer `--extend-s` |
| `launch_error` | not enough free RAM to start a job | free memory |

Skip reasons are listed in [pipeline](pipeline.md#3-per-sequence-gates-attemptattempt_sequence).

### Where to look

- `oeisbot attempts` for a quick list; the dashboard's Attempts tab for counts and filters.
- `data/runs/<A>-<time>-<sha>.jsonl` for every term a run accepted. A term that failed a check (wrong
  value, wrong index, malformed line) stops the run before it is logged; the attempt's `detail` holds it.
- `data/runs/<same stem>.py` for model-generated programs that ran, including failed ones. Generations
  rejected before running are not saved.
- The dashboard's Estimator accuracy tab once there are finished projections.

### A win whose re-check failed (`recheck_pending`)

When a run finds new terms, the pipeline records it as `recheck_pending`, saves the full result as
`data/pending/attempt-<id>.pickle`, and only then asks oeis.org whether the terms are still new. When
that finishes, the run becomes a win (artifact and review) or `superseded`. It stays `recheck_pending`
when the re-check does not finish:

- oeis.org could not be reached three times (network or HTTP errors, with pauses of 30 s and 120 s);
- the re-check raised some other error (not retried);
- the process was stopped (Ctrl+C, closed window) during the re-check.

After a failure the log says `kept as recheck_pending (attempt #<id>)`, and the attempt's
`extra.recheck` holds the error (`not done: <ErrorType>: <message>`; `not done yet` after an interrupted
run). No artifact or review exists yet, and the sequence is neither picked nor attempted (skip reason
`recheck_pending`) until it is resolved. The new terms are also in the run log, as for every run.

Every `oeisbot run` retries pending re-checks before picking sequences. To retry by hand, run
`oeisbot recheck` (exit status 1 while any remain). A retry that fails logs
`still pending (<ErrorType>: <message>)` and moves on; it never stops the session.

If one stays pending, the logged error type says why:

- **A network error type** (`URLError`, `TimeoutError`, ...): wait until oeis.org is reachable.
- **`FileExistsError`**: a folder `artifacts/<A-number>/attempt-<id>/` already exists and is not this
  win's unfinished folder, for example one kept from a database that was deleted. Move that folder
  elsewhere and run `oeisbot recheck` again.
- **`FileNotFoundError`, `UnpicklingError`, `AttributeError` and similar**: the saved result is missing,
  or can no longer be loaded after a code change. To release the sequence, mark the attempt by hand and
  attempt it again:

  ```sql
  UPDATE attempts SET outcome = 'verified' WHERE id = <id>;
  ```

  Then delete `data/pending/attempt-<id>.pickle` if it exists. The new terms stay in the run log named in
  the attempt's `extra`. `verified` counts once toward that sequence's selection penalty.

## Reviewing a result

A win appears as a new review (`oeisbot review list`, or the dashboard's Review inbox), with its folder
at `artifacts/<A-number>/attempt-<id>/`. Nothing has been sent anywhere.

1. **Claim it**: `oeisbot review set <id> reviewing`. The sequence stays out of future picks while the
   review is new, reviewing or submitted.
2. **Read `README.md`**, especially the warnings:
   - *Weak verification*: fewer than 10 known terms were checked.
   - *Program was rewritten*: a print loop's bounds were lifted; compare `program.gp` with `executed.gp`
     and ask whether lifting the bound changed the meaning.
   - *AI-generated program*: OEIS does not accept programs you do not understand. Treat the terms as a
     lead and re-derive them with a program you understand.
   - *Hard-coded bound*: terms beyond that bound may be wrong even though verification passed.
3. **Understand the program** (`program.gp` or `program.py`) well enough to explain why it computes this
   sequence. This is required, not optional.
4. **Check the index convention**: the entry's offset, and the first new index in the README.
5. **Look at `timing.csv`**: do the new terms' costs continue the trend of the known ones? A sudden drop
   can mean the program took a shortcut that is not valid.
6. **Check independently** with a second program or method.
7. **Re-open `https://oeis.org/<A-number>`** to confirm nobody has extended it since the pipeline's
   re-check (its note is in `verification.md`; for a win that was `recheck_pending`, the check that
   counted ran later than the run itself).
8. **Submit by hand**, one sequence at a time, following OEIS's own instructions: b-files are described
   at https://oeis.org/SubmitB.html, contributions at https://oeis.org/Submit.html, and formatting in the
   style sheet at https://oeis.org/wiki/Style_Sheet. The artifact's `b<number>.txt` is in b-file format,
   but check it against those instructions before uploading.
9. **Record the result**: `oeisbot review set <id> submitted --note "..."`, or `rejected` with the reason.

Marking a second review for the same sequence as `submitted` is refused.

## Troubleshooting

### TLS errors on downloads

Some antivirus products and corporate proxies intercept HTTPS with their own certificate. Tools with
their own certificate bundles then fail, while tools using the Windows certificate store work.

- **uv** (`invalid peer certificate: UnknownIssuer`): set `UV_SYSTEM_CERTS=1`. `oeisbot setup` sets it for
  its own uv call.
- **git** (`unable to get local issuer certificate`): `git -c http.sslBackend=schannel ...`.
  `oeisbot sync` does this automatically on Windows.
- **npm**: set `NODE_USE_SYSTEM_CA=1` (supported by recent Node releases; it worked with Node 24).
- **winget** (`0x8a15005e` on the msstore source): add `--source winget`.

### Sandbox

- **Sandbox tests fail with access-denied errors after moving or copying the project**: the AppContainer
  grants are path-based. Run `oeisbot setup` again.
- **`PermissionError` importing gmpy2 or sympy inside the sandbox**: the packages were installed as hard
  links (they keep uv's cache ACL). Delete them from `tools/python/Lib/site-packages` and run
  `oeisbot setup`, which reinstalls them as copies.
- **Every run ends in `launch_error`**: less than 3 GiB + 256 MiB of physical RAM is free. Close
  applications or unload the model (`ollama stop qwen2.5-coder:14b`).
- **`runtime_problems` / tests skipped**: `tools/python/python.exe`, `tools/pari/gp.exe` or
  `data/scratch` is missing; run `oeisbot setup`.

### Model

- **`--model: no model server at ...`**: start the Ollama app (it runs the server on port 11434).
- **`model 'qwen2.5-coder:14b' not found`**: `ollama pull qwen2.5-coder:14b`, or set `OEISBOT_MODEL`.
- **Generation is very slow**: `ollama ps` shows a CPU/GPU split; lower `OEISBOT_MODEL_CONTEXT` or use a
  smaller model.

### Dashboard

- **"dashboard not built"**: run `npm install` and `npm run build` in `dashboard/`.
- **503 from the API**: the database does not exist yet; run `oeisbot setup` and `oeisbot sync`.

## Maintenance

- **Refresh the mirror** with `oeisbot sync` before sessions. Sequences that lost `more` drop out of the
  pool.
- **Disk growth**: `data/runs/` (logs and generated programs) and `data/bfiles/` are never pruned. Both
  are safe to delete, but deleting run logs loses the term records of past runs.
- **Starting over**: stop any session and the dashboard, then delete `data/oeisbot.sqlite3*` and run
  `oeisbot setup` and `oeisbot sync`. This deletes all attempt and review history, including which
  sequences were already submitted.
