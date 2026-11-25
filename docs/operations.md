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
.venv\Scripts\python -m pytest            # 903 tests, about 100 s; confirms the sandbox works on this machine
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
.venv\Scripts\oeisbot sync                         # refresh the oeisdata mirror (about 70 s), then record the PARI pool (about 6 s more)
.venv\Scripts\oeisbot run -n 10                    # pick and attempt 10 PARI-bearing sequences
.venv\Scripts\oeisbot run -n 10 --model            # any candidate; model fallback after PARI
.venv\Scripts\oeisbot run -n 10 --verify-s 600     # a slower second pass: revisits programs that timed out at 60 s
.venv\Scripts\oeisbot attempts --limit 30          # what happened
.venv\Scripts\oeisbot review list                  # wins waiting for review
.venv\Scripts\oeisbot snapshot                     # record the pick pool for the dashboard's Pick map (a session and a sync do too)
.venv\Scripts\oeisbot daemon                       # sessions back to back until the window (22:00-08:00) closes; see "Running unattended"
```

**One of these at a time** (since history item 58). `run`, `attempt`, `sync`, `recheck`, `fetch-bfiles`,
`setup` and `snapshot` take the writers' lock while they run, and `oeisbot daemon` holds it for its whole
window. A second one is refused at once, before it does anything, with a message that names the first:

```
`oeisbot run` not started: `oeisbot daemon` (pid 4242, started 2026-11-23 22:00:01 local time, by the
lock file's account) is running, and only one command that runs programs, syncs or contacts oeis.org
may run at a time. Wait for it, or stop it (`oeisbot daemon --stop` for the daemon)
```

Wait for the other command, or stop it. The lock belongs to the process, so a command that crashed or
was killed does not leave it held, and there is never a lock file to delete. `queue`, `pick`, `stats`,
`attempts`, `model-check`, `review` and the dashboard are never refused. Why these commands:
[daemon](daemon.md#the-writers-lock).

A session runs sequentially in the foreground and prints one line per step:

```
[A246855] known a(1)..a(3): 3 terms from data
[A246855] running pari:print-loop from A246855 %o (PARI) block 1
[A246855] -> verified: extend_budget (extension budget 120 s used); reproduced 3/3, 0 new, 122.8 s, peak 8 MiB
```

With default budgets a program that cannot reproduce its known terms costs at most a minute, but one
that can may then extend for 3 hours, and with `--model` the model stage can follow it (and its own
programs get the same budgets). Long sessions are best left running unattended.

The first line of a session says how many candidates were left out because an attempt could only skip
them (see [pipeline](pipeline.md#2-selection-oeisbot-run--n-n---alpha-a---seed-s---model)). A program that
timed out verifying is not run again at the same or a shorter `--verify-s`: run a session with a longer
one (say `--verify-s 600`) to give those a second, slower pass. Likewise a program that reproduced its
known terms and then used its whole extension without a new term is not run again at the same or a
shorter `--extend-s` (after one unproductive default run that means never at the default 3 h); the
entry's next PARI program runs instead in a later attempt, with its own extension. Once all of them are
dead ends, a longer `--extend-s`, `--model` (the model is asked for a faster program), or more known
terms bring the sequence back.

Stopping a session with Ctrl+C (or closing the window) ends the harness. The sandboxed job is killed
with it by the Job Object's kill-on-close setting (tested for a killed harness). The session row is
closed on Ctrl+C but stays unfinished if the process is killed outright (the next start of
`oeisbot daemon` closes such a row; nothing else does). The interrupted run gets no
attempt row, but every term it produced is already in `data/runs/`. This is `oeisbot run`: the daemon
handles Ctrl+C differently, recording the run in hand as `interrupted` (below).

## Running unattended: `oeisbot daemon`

The full reference is [daemon](daemon.md). **As of 2026-11-23 it has never been run on this machine's
real data and is not armed; do the [first-night checklist](daemon.md#before-the-first-night) before
trusting it with a night**, starting with one `oeisbot sync` by hand.

**Arming: the first step, and yours.** A night runs only on a machine where a person has once run

```
.venv\Scripts\oeisbot daemon --arm        # writes data\daemon\armed and says so; starts nothing
.venv\Scripts\oeisbot daemon --disarm     # takes it back: the next start does nothing
```

Until then every start of the daemon, whoever or whatever makes it (you at a console, the scheduled
task, a script, a coding agent, a test), writes one line to `data/daemon/daemon-YYYYMMDD.log`,
`daemon: not started: not armed. ...`, prints it, and exits with code 2. It takes no lock, opens no
database and writes no heartbeat. Arming stays until you disarm: a finished night, a kill and a
restart of the machine all leave it. `--disarm` does not stop a daemon that is running; `--stop` does.
`--status`, `--stop` and `--task-xml` need no arming. The reasons are in [daemon](daemon.md#arming).

**Running.**

```
.venv\Scripts\oeisbot daemon                         # one window, default 22:00-08:00 local time, then exit
.venv\Scripts\oeisbot daemon --window 23:00-06:30    # another window
.venv\Scripts\oeisbot daemon --window always         # no closing time
.venv\Scripts\oeisbot daemon --no-sync               # do not pull the mirror first
```

Started outside its window it logs that and exits at once. Inside it, it tidies up after any killed
predecessor, syncs the mirror once, then runs PARI sessions of up to 25 picks, starting at 60 s /
1,800 s budgets and moving to longer ones only when nothing is left to draw. It takes no budget flags
and no `--model`. **If another `run`, `attempt`, `sync` or the like is still running when it starts, it
waits**, trying again every minute until the window closes (with `--window always` it gives up at
once); while it waits, `--status` reports no daemon. To have Windows start it each night, write a Task
Scheduler definition and import it yourself ([daemon](daemon.md#the-scheduled-task)); the project
registers nothing:

```
.venv\Scripts\oeisbot daemon --task-xml oeisbot-daemon.xml
schtasks /create /tn "OEISBot daemon" /xml oeisbot-daemon.xml
```

**An imported task on a machine that is not armed does nothing, every night.** It starts the daemon
when the window opens; the daemon appends its `not started: not armed` line to that day's log in
`data/daemon/` and exits with code 2, which Task Scheduler shows as the task's last result. Nothing
else is written. It shows in three places: that log, `oeisbot daemon --status` (a line `not armed: a
start will do nothing until you run `oeisbot daemon --arm``), and the dashboard's line (`Daemon is not
armed, so a start will do nothing`). So the order of importing and arming does not matter, and
`--disarm` is how to keep the task and have it do nothing.

**The first night, in order** (the reference list, with the reasons, is
[daemon](daemon.md#before-the-first-night)): `oeisbot sync` once by hand, with the pull; check the
disk (the daemon pauses under 10 GiB free); `oeisbot daemon --arm`; one short run in the foreground,
watched, then `--status` and `--stop`; restart the dashboard server and look at its line; write and
import the task and check "Allow wake timers". The next morning: `oeisbot daemon --status` and the log.

**Checking.**

```
.venv\Scripts\oeisbot daemon --status
```

says whether one is running, what it is on, when the window closes, and every warning of the night. The
same is one line under the dashboard's header. The record is `data/daemon/daemon-YYYYMMDD.log`, which
holds everything a console session would have printed. `oeisbot attempts` and the dashboard work while
it runs.

**Stopping.**

```
.venv\Scripts\oeisbot daemon --stop
```

or Ctrl+C once in its console, or the window's end. The run in hand is stopped and recorded with stop
reason `interrupted`, which retires nothing, adds no failure penalty and leaves the sequence as
drawable as it was. It usually exits within seconds; longer if it is syncing (a sync is not
interrupted: up to 10 minutes for each git command, then the reading of the mirror) or the stopped run
had just found new terms (its re-check runs first).
Ctrl+C a second time ends it at once without recording the run in hand. If a stop is not obeyed for 20
minutes the daemon ends its own process.

**Closing the console window, logging off, Task Scheduler's "End" and `taskkill` are kills, not stops.**
Nothing is corrupted by one: the lock is released, the sandboxed job dies, and the next start closes
the session row and, once it is six hours old, removes the run's scratch directory. But the run in hand
leaves no attempt row.
Prefer `--stop`.

**After a warning.** Warnings are in `--status`, on the dashboard line and in the log.

| Warning or ending | What it means | What to do |
|---|---|---|
| `sync failed (...); going on with the mirror as it is` | the pull failed or timed out; the night ran on the old data | nothing at once; if it repeats, run `oeisbot sync` by hand and read git's message. While the last pull is over 7 days old the daemon stays at its lowest tier |
| `sync failed and left the mirror unusable (...); no sessions tonight` | the reset failed and the mirror could not be put back: either it was ended half way by the time limit and the repair failed too, or git refused it because another git held the mirror's index (an `index.lock` the daemon leaves alone unless it is 5 minutes old before the sync, or was left by its own timed-out reset) | check that no git is running on `data/oeisdata`, then run `oeisbot sync` by hand before anything else reads the mirror. A sync by hand removes no lock file: if git says `index.lock` exists and no git is running, delete that file |
| `attempt #N (A...) waits for a re-check but its saved result is missing` | a process was killed between recording a win and saving it | the terms are in the run log the attempt names; `oeisbot recheck --release N` frees the sequence ([below](#a-win-whose-re-check-failed-recheck_pending)) |
| `A... raised <Error> outside the sandbox and is held back for 14 days` | a session raised while on that sequence; the traceback is in the log | read the traceback: it is a bug in the pipeline or an entry it cannot read |
| `A...: N new term(s) found before the run was stopped; ... a longer run might find more` | a win was cut short by the window or a stop; its review holds the terms found | review it as any win; a targeted `oeisbot attempt A... --extend-s ...` is not possible while its review is open |
| paused: `... GiB free on the data drive; a run needs 10 GiB` | under 10 GiB free | free disk space; it looks again every 10 minutes |
| paused: `... GiB of RAM free; a run needs 4 GiB` | under 4 GiB of physical RAM free | close applications (Ollama keeps several GB loaded) |
| ended: `5 picks in a row ended as launch_error / disk_cap / harness_error / bfile_error` | the machine or the network, not the programs | find which in `oeisbot attempts`; fix it before the next night |
| ended: `2 sessions in a row raised` | a fault that repeats | read the traceback in the log |
| `Daemon is not running, and its last run did not finish` (dashboard), `did not finish` (`--status`) | it was killed | nothing: the next start recovers. Check the log if it was not you |
| `daemon: not started: not armed` (log, exit code 2), `not armed: a start will do nothing ...` (`--status`), `Daemon is not armed ...` (dashboard) | the daemon was started on a machine where `--arm` has not been run, or after `--disarm`. Nothing ran and nothing was touched but the log | if you want nights to run, `oeisbot daemon --arm`; if not, nothing. If you did not start it, find what did (the scheduled task, a script) |

## Command reference

| Command | Purpose | Options |
|---|---|---|
| `setup` | install sandbox runtimes, grant access, create the database | |
| `sync` | update oeisdata, rebuild `sequences`, then record the PARI pool as a Pick-map snapshot | `--no-pull` (use the current checkout) |
| `stats` | languages present among candidates | `--forms` (classify PARI program shapes) |
| `queue` | the pool `run` would pick from (default budgets), with difficulty and pick probability, and how many were left out as unrunnable | `--alpha A` (1), `--all` (the `run --model` pool: include non-PARI), `--limit N` (40), `--sort difficulty\|weight\|a` |
| `pick` | a weighted random draw from that pool, without attempting | `--alpha`, `--all`, `-k N` (10), `--seed S` |
| `attempt A... ` | attempt specific sequences (no session) | budget flags, `--model`, `--no-recheck` (testing only) |
| `run` | pick and attempt | `-n N` (5; capped at 25, and the session log says so when the cap bites), `--alpha`, `--seed`, `--model`, budget flags |
| `recheck` | retry the oeis.org re-check of wins left as `recheck_pending`; exits with status 1 if any are still pending | `--release <attempt id>`: give up on one pending win whose saved result can no longer be read (refused while it still loads) |
| `model-check` | confirm the model server and model answer | |
| `fetch-bfiles` | look up b-files for the easiest candidates whose status is not `present` or `absent` (so earlier errors are retried); updates b-file facts and the stored difficulty | `--limit N` (100 successful lookups; errors do not count), `--all` |
| `attempts` | recent attempt rows and failure-mode counts | `--limit N` (30), `--failure MODE` |
| `review list` | all reviews | |
| `review set ID STATUS` | change a review's status | `STATUS` = `new`, `reviewing`, `submitted`, `rejected`; `--note TEXT` |
| `snapshot` | store the pool `run` would draw from, with each candidate's effective difficulty, as a snapshot the dashboard's Pick map can compare against later; prints how many candidates it held and whether anything was stored (a pool identical to the newest snapshot adds nothing). Takes about 10 s for PARI, about 30 s more with `--all`. Default budgets | `--all` (also the `run --model` pool) |
| `daemon` | run sessions back to back, unattended, inside a window of local time; one invocation is one window ([daemon](daemon.md)). Takes the writers' lock itself. **Does nothing (one log line, exit code 2) until a person has run `--arm`** | `--window HH:MM-HH:MM` (22:00-08:00) or `always`, `--no-sync`, `--status` (read only), `--stop` (ask the running one to stop), `--arm` (allow nights to run here: writes `data/daemon/armed`, starts nothing), `--disarm` (take that back; does not stop a running daemon), `--task-xml [FILE]` (write a Task Scheduler definition to `FILE` as UTF-16, or print it; registers nothing) |
| `dashboard` | read-only web UI; starts building the Pick map's PARI pool in the background so that tab opens quickly. It answers only to `127.0.0.1`, `localhost`, `::1` and the `--host` given; `--host 0.0.0.0` turns that check off and says so ([dashboard](dashboard.md#safety-properties)) | `--host` (127.0.0.1), `--port` (8765) |

`setup`, `sync`, `attempt`, `run`, `recheck`, `fetch-bfiles` and `snapshot` are refused while another of
them, or the daemon, is running (the writers' lock, above). The rest are never refused.

Budget flags on `attempt` and `run`: `--verify-s` (60), `--extend-s` (10800), `--mem-gib` (6),
`--max-new` (200). Every other limit is a constant in the code:

- the daemon's window default, tiers, cooldown, margins and timeouts: the constants at the top of
  `oeisbot/daemon.py` ([table](daemon.md#constants));

- RAM and disk reserves, scratch cap, over-prediction factor and session cap: `Budgets` in
  `oeisbot/config.py`;
- model generations per sequence: `CODEGEN_ATTEMPTS` in `oeisbot/config.py`;
- PARI programs run per sequence: `MAX_PROGRAMS_PER_SEQUENCE` in `oeisbot/attempt.py`;
- estimator thresholds: the constants at the top of `oeisbot/estimate.py`.

## Reading results

### Stop reasons, and what to do about them

| Stop reason | Usually means | Try |
|---|---|---|
| `verify_timeout` | the program cannot reproduce the known terms in time (common: the last known terms were expensive for their authors too) | a longer `--verify-s`, or accept that the sequence is hard. Until then the program is a dead end: it is not re-run at a `--verify-s` no longer than the time it already ran. Since history item 58 that holds only if the run also had CPU time of at least 80% of the `--verify-s` now asked; a timeout on a machine that slept or was busy does not retire the program, and it runs again |
| `wrong_term` | wrong program, or the program computes a different sequence than the entry's DATA | nothing: recorded as a dead end for this program |
| `bad_index` | the program starts at a different index than the offset | for PARI this points to an entry whose program and offset disagree |
| `crash` / `incomplete` | program error, or it stopped early (often a built-in limit). A gp program that calls a function no one defined prints its error and still exits 0, so it lands on `incomplete`, not `crash` -- though since 2026-09-20 a PARI block calling another entry's helper is rejected before it runs (see [strategies](strategies.md#programs-that-call-another-entrys-helper)) | read `detail`: it ends with the last stderr lines the program wrote (see [verification](verification-and-estimation.md#the-stderr-tail-in-a-detail)); dead end |
| `memory_cap` | job hit its memory cap, or the machine ran low on RAM | raise `--mem-gib` if RAM allows, or close memory-hungry apps (Ollama keeps several GB loaded) |
| `searched_bound` | verified; the entry itself publishes a searched range with no further term in it, and the extension cannot reach the end of that range at the rate just measured while verifying (see [verification](verification-and-estimation.md#the-searched-bound-check)). The bound and the comment it came from are in the attempt's `extra` | nothing, usually: a human has already searched that range. A longer `--extend-s` re-runs it, since the check is judged against the budget. The bound is an **unverified human claim** -- it is only ever used to decline to spend time, never as evidence about a term. `extra.verified_scan_to` records how far this run's own scan actually got, which is the part that is not a claim |
| `infeasible` | verified; the next term's projection exceeds the remaining budget (time, judged only on a trustworthy cost fit since 2026-09-19, or memory: the reasons are in `detail`, and since 2026-09-30 `extra.infeasible_on` names the budget) | a longer `--extend-s` if it ran out of time, a larger `--mem-gib` if memory. Without more of *that* budget the program is a dead end and is not re-run for the same known terms |
| `over_prediction` | verified; a new term ran far past a trusted projection | check the estimator view; the projection may be poor for this sequence. Since 2026-09-18 a projection whose seconds per cost unit are projected to exceed the rate it converted with by more than the kill factor (2 by default) is not trusted, so a likely cause now is a milder climb in that rate, or a term that is simply dearer than the cost fit expects, as at the edge of the known terms (see [known limitations](known-limitations.md#verification-and-estimation)) |
| `extend_budget` | verified; the budget ran out without (more) new terms. Also the usual end when the next term's projection was not trusted, since only a trusted one can kill a term and only a trustworthy cost fit can stop the run before it on time | a longer `--extend-s`; with `--model`, the model is asked for a faster program right away if no new terms were found. Without new terms the program is a dead end at the same or a shorter `--extend-s` (unless the machine was so busy the job got under 80% CPU) |
| `launch_error` | not enough free RAM to start a job | free memory |
| `harness_error` | **our** `on_line` or `on_tick` callback raised inside the sandbox; `detail` names the exception (since 2026-09-30). The program did nothing wrong | fix the harness bug, then re-run: this is deliberately not a dead end |
| `interrupted` | `oeisbot daemon` stopped the run: a stop request, the end of its window, or Ctrl+C (since history item 58). `detail` says how far in and in which phase. The program did nothing wrong | nothing: it is not a dead end, adds no failure penalty, and the sequence can be drawn again the next night. If the run had already found new terms it is a win like any other |

A skip row with reason `daemon_error` (strategy `daemon`) is not a stop: the daemon writes it for the
sequence a session was on when the session raised, so that the same sequence is not drawn again for 14
days. The exception is in `detail` and the traceback in the daemon's log.

Skip reasons are listed in [pipeline](pipeline.md#3-per-sequence-gates-attemptattempt_sequence).

### Where to look

- `oeisbot attempts` for a quick list; the dashboard's Attempts tab for counts and filters.
- `data/runs/<A>-<time>-<sha>.jsonl` for every term a run accepted. A term that failed a check (wrong
  value, wrong index, malformed line) stops the run before it is logged; the attempt's `detail` holds it.
  A run that had no term accepted — a wrong first term counts — writes no such file, and its attempt row
  then has no `extra.log` at all (rows written before 2026-09-20 name a file that was never created).
- `data/runs/<same stem>.py` for model-generated programs that ran, including failed ones, as they ran
  (a `members(work)` program with its driver); the attempt row names it as `extra.program`. Generations
  rejected before running, including a repeat of a program that already failed the same way, are not saved.
- The dashboard's Estimator accuracy tab once there are finished projections.
- The dashboard's Pick map tab for what a session is about to draw and what moved since the last look: a
  sequence that failed turns red, one that was retired or whose program was refused drops out and is listed
  under "Left the pool" with the reason. Every `oeisbot run` that draws from a pool stores a snapshot of it
  first, so the next visit has something to compare with; `oeisbot snapshot` stores one without running.
  **`oeisbot sync` stores one too, after it has refreshed the data** (history item 55): the PARI pool only,
  under the budgets of the newest PARI snapshot, and a new snapshot only if the pool differs from the newest
  one's (if it does not, the newest is re-stamped with the rules fingerprint of the code on disk, as for any
  snapshot call). `oeisbot snapshot` takes no budget flags and stamps the defaults, so run after a session
  with other budgets it puts the defaults back for the syncs and the dashboard that follow. It
  costs about 6 s (5.4 to 5.8 s measured on the real pool) and prints one line, `pick snapshot #N stored (M
  candidates)` or `pick snapshot unchanged (M candidates)`. It cannot fail the sync: if the pool cannot be
  built or stored the line reads `pick snapshot not recorded: ...` and the sync's own work stays committed,
  and a pool for which the per-sequence check failed (a missing or unreadable b-file, say) is not stored at
  all, since the sequences it lacks would show up as arrivals in the next snapshot (the line then says `the
  check failed for N (first: ...)`). The snapshot records the selection rules of the code **on disk**, which
  may differ from the code a running dashboard loaded. The model pool is not recorded by a sync (it takes
  about half a minute to build): `oeisbot snapshot --all` or a `run --model` does that. Up to 30 PARI
  snapshots are kept, and a pool that flips back and forth (A, B, A) is stored each time, because only the
  newest snapshot is compared for equality.

### A win whose re-check failed (`recheck_pending`)

When a run finds new terms, the pipeline records it as `recheck_pending`, saves the full result as
`data/pending/attempt-<id>.json`, and only then asks oeis.org whether the terms are still new. When
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
- **`FileNotFoundError`, `JSONDecodeError`, `ValueError` and similar**: the saved result is missing, or
  can no longer be read. A `ValueError` naming fields that "do not match the code" means the saved win
  predates a change to one of the classes it holds; the new terms are still in the run log. To release
  the sequence, give the win up and attempt the sequence again:

  ```
  .venv\Scripts\oeisbot recheck --release <id>
  ```

  This marks the attempt `verified`, records why and when in its `extra` (`recheck`, `released_at`) and
  renames `data/pending/attempt-<id>.json`, if it exists, to `attempt-<id>.released.json` (a result whose
  fields drifted is still the whole result in readable JSON, and nothing reads that name again). It replaces the `UPDATE attempts SET outcome =
  'verified'` this page used to prescribe (item 57), and it checks what a person at a SQL prompt cannot
  easily check: **it refuses a win whose saved result still loads** (that one is not lost: wait for
  oeis.org, or move the folder that is in the way, and run `oeisbot recheck`), it refuses a saved result
  that exists and cannot be opened (close whatever has the file open), and it refuses a row that is not
  `recheck_pending`. It exits with a message beginning `not released:` in each case and writes nothing.
  **Do not run it while `oeisbot run` is in progress**: a run records its row a moment before it saves
  the result, and a release in that moment would give up a live win. The pipeline never runs it: giving up on new terms is a person's decision. The new terms stay
  in the run log named in the attempt's `extra`; the command prints its path and says so if the file is gone. `verified` counts toward that
  sequence's selection penalty, at most once for its attempt: nothing more if another row of the same
  attempt already counts.

## Reviewing a result

A win appears as a new review (`oeisbot review list`, or the dashboard's Review inbox), with its folder
at `artifacts/<A-number>/attempt-<id>/`. Nothing has been sent anywhere.

**There is one waiting** as of 2026-09-28, the first the project has produced: `#1 A385331
a(25)..a(42) new`, in `artifacts/A385331/attempt-139/` (history items 35, 44 and 49). Reviews #2 and #3
were closed as `rejected` on 2026-09-28 (item 49) and are not waiting on anything.

> **Read this before running anything from the checklist below.** **Steps 2 to 7 are already done**
> (item 44, 2026-09-23; the account and the re-run command are in `data/review1/README.md`), so they do
> not need repeating — in particular do **not** re-run the 775 s independent sweep or re-run A385331
> itself. **Step 7 was re-run on 2026-09-28** (item 49) and still passes: the live entry ends at a(24),
> keyword `more` is present, and all 24 published terms agree with the run. **Step 1 is deliberately not
> done**: the row is left at `new` because its status is the user's own workflow marker. An agent must
> not run `oeisbot review set`, and must never do step 8. What remains is steps 8 and 9, and both are
> the user's alone.
>
> **The step-8 material is assembled in `data/review1/SUBMISSION.md`** (item 49): the DATA line with all
> 42 terms (191 characters, inside the style sheet's 260-character guide, so nothing needs truncating),
> the `%E` extensions line, and **`b385331-submit.txt`** — the artifact b-file plus the trailing blank
> line, to be renamed `b385331.txt` before uploading. Read `program.gp` yourself regardless; that is
> step 3's real purpose and OEIS does not accept programs you do not understand.

Four notes specific to this review, so the checklist below is not misread:

- **Step 5 will look alarming and is fine here.** `timing.csv` does not continue any trend: after
  a(25) at 454 s the costs jump about, 11 of the 18 new terms landing under a millisecond while
  **a(32), a(37) and a(38) cost 66.8 s, 57.7 s and 153 s**. That is not a shortcut. a(n) is the smallest
  prime factor of an integer, so the cost is a property of the *value* — most integers have a small
  factor and a few have none below 10^7 — and it is not a function of n at all. Judge the terms, not the
  shape of the curve. The entry's own `a(3k) = 3` is provable and worth checking by hand: the n-th
  numerator is a sum of n distinct powers of 10, so its digit sum is n and 3 divides it exactly when 3
  divides n. Every new multiple of 3 in the b-file is 3.
- **Step 6 is discharged (2026-09-23, history item 44).** Two scripts do it, and the difference between
  them is the point. `scripts/verify_A385331.py` re-derives `N(n) = sum_{k=1..n} 10^(n!-k!)` from the
  sequence's *name* rather than from the entry's program, so it shares no code with `program.gp` — but
  it tests divisibility with `sum_k 10^((n!-k!) mod (q-1)) mod q`, the **same method** the entry uses,
  so a fault in that arithmetic would show up identically in both. On its own it did **not** discharge
  step 6. `data/review1/indep_A385331.py` does: it never forms `n!-k!` and never reduces modulo `q-1`,
  using modular **inverses** instead (`10^(n!-k!) = 10^(n!) * inv(10^(k!))`, with `10^(k!)` built by
  iterated small-exponent powering), with gmpy2 for arithmetic and sympy for primes. It reproduced all
  23 known terms a(2)..a(24) before being trusted on anything new, then confirmed **all 18 new terms**,
  and bounds `a(43) > 2x10^8`. Two checks beside it: `N(n)` **is** A145571, verified against the live
  entry; and for n = 2..10 the real integer `N(n)` was built and factored by plain trial division with
  no modular arithmetic at all, agreeing every time — up to n = 10, whose `N` has 3,628,800 digits.
  Beyond about n = 11 the integer has tens of millions of digits, so modular arithmetic is unavoidable.
  `data/review1/README.md` has the whole account.
- **Step 2's warnings do not apply**: 24 known terms were reproduced (not weak), the program was not
  rewritten, it is the entry's own PARI program rather than an AI-generated one, and its `forprime(p=3,
  oo, ...)` has no hard-coded bound.
- **Steps 3, 4 and 7 are done too** (item 44). Step 3: the program returns the first prime from 3 upward
  dividing `N(n) = sum_{k=1..n} 10^(n!-k!)`, the n-th numerator of a partial sum of Liouville's
  constant; the `k = n` term is `10^0 = 1` and the rest are positive powers of 10, so `N(n) == 1
  (mod 10)` and skipping 2 and 5 is sound, and `N(n)` is a sum of n *distinct* powers of 10, so its digit
  sum is n — which proves `a(3k) = 3`. Step 4: offset 1, first new index 25, b-file contiguous 1..42.
  Step 7: re-checked live on 2026-09-23 — the entry still ends at a(24), keyword `more` is still there,
  all 24 known terms agree and none of the new terms is published. **You still have to read `program.gp`
  yourself before submitting**: OEIS does not accept programs you do not understand, and that is step 3's
  real purpose.

1. **Claim it**: `oeisbot review set <id> reviewing`. The sequence stays out of future picks while the
   review is new, reviewing or submitted (and, since history item 58, when it is rejected too).
2. **Read `README.md`**, especially the warnings:
   - *Weak verification*: fewer than 10 known terms were checked.
   - *Program was rewritten*: a print loop's bounds were lifted; compare `program.gp` with `executed.gp`
     and ask whether lifting the bound changed the meaning.
   - *AI-generated program*: OEIS does not accept programs you do not understand. Treat the terms as a
     lead and re-derive them with a program you understand.
   - *Numbered by the runner*: the model wrote only the list (`members(work)` in `program.py`); the driver
     at the end of `executed.py` numbers the members from the offset and stops if they do not increase.
   - *Hard-coded bound*: terms beyond that bound may be wrong even though verification passed.
   - *A term lands below a published bound* (since 2026-09-30): a new term sits inside a range the
     entry's own comment reports as searched and empty. Either that search or this program is wrong;
     resolve which before submitting anything.
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
   but check it against those instructions before uploading. Since 2026-09-28 it ends with the trailing
   blank line SubmitB.html requires (item 49); an artifact written before that date does **not**, and the
   rule's stated consequence is that the last data line — the highest new term — may be ignored.
9. **Record the result**: `oeisbot review set <id> submitted --note "..."`, or `rejected` with the reason.
   **Either one keeps the sequence out of every future draw** (since history item 58, see below). For
   review #1 that means: once step 9 is recorded, in either way, A385331 is not picked again by
   `oeisbot run` or the daemon for as long as that row stands. `review set` is not refused while the
   daemon runs.

Marking a second review for the same sequence as `submitted` is refused. `rejected` is a legal status
(`db.py`'s CHECK constraint) and is **not** in `db.OPEN_REVIEW_STATUSES`, so it does not gate a targeted
`oeisbot attempt`. **Until history item 58 it also released the sequence back into the draw**, which
is why rejecting a false win needed a reason to believe the pipeline would not simply pick it again (for
reviews #2 and #3 that reason was `pari.conjectural`, item 47, measured before the close and again
after: the pool stayed at 3,438). **Since item 58 `select.candidates` does not draw a sequence with a
`rejected` review at all.** A win for such a sequence is refused a review anyway (next paragraph), so
drawing it could only spend the run and write an artifact folder nobody is shown, and an unattended
loop would repeat that. The consequences:

- All four statuses now keep a sequence out of the draw, and no command deletes a review row. A
  sequence that has had a review is drawn again only if someone removes the row by hand.
- Rejecting a win because the *run* was wrong (not the sequence) therefore gives up the sequence for
  sessions too. A targeted `oeisbot attempt A...` still runs it.
- For review #1: if A385331's terms are accepted by OEIS, the entry gains them at the next sync and
  nothing is lost by its staying out. If the review is `rejected`, A385331 stays out as well, where
  before it would have been re-run from a(1).

**A `rejected` review also refuses any later review for the same sequence** (2026-09-30, history item
51). A `rejected` row does not gate `attempt_sequence` — only the open statuses do, deliberately, so a
targeted `oeisbot attempt A162762 --model` still runs — but if such a run wins, `db.record_win` records
the attempt as `extended` with its artifact folder and **opens no review**: the console says `review
refused: A162762 already has a rejected review (#2)`, and `attempts.extra.review_refused` names the
prior row. The terms are kept; nothing appears in the inbox. If a result really is different from what
was rejected, reopen the question by changing the old row's status (`oeisbot review set 2 reviewing`),
which lifts the refusal; the pipeline never guesses.

`oeisbot review list` prints each review as three lines — the sequence and its name, then the addition
and where it came from, then the folder and note — the same facts, in the same order, as the
dashboard's inbox:

```
#1    A385331  new        a(1) = 1 and a(n) is the smallest prime factor of n-th numerator of partial sum for Liouville's constant (A145571), for n > 1.
      18 new terms, a(25)..a(42), from A385331 %o (PARI) block 1, attempt #139
      artifacts\A385331\attempt-139
```

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
- **The Pick map says "The PARI pool could not be built: ..."** The reason after the colon is the
  exception's type and message. The full traceback is in the terminal that runs `oeisbot dashboard`
  (logger `oeisbot.dashboard`). Nothing is cached for a failure, so **Try again** asks for a fresh build.
  The last map that loaded stays on screen, labelled as such. This path has been exercised by tests that
  make the pool build raise, not by a failure met in use, so the reason on screen and the traceback are the
  only evidence of what went wrong; a failure that repeats is worth running `oeisbot queue` against, which
  builds the same pool from the command line.
- **The Pick map is slow to open.** It draws from the pool a session would, which is built when asked for
  (6 to 12 s for either pool, 25 s for a first build on a cold disk) and kept until the database file changes. Anything
  that commits invalidates it, so **while a session is running every visit rebuilds the pool**; the tab
  says "Building the pool" meanwhile. `oeisbot dashboard` builds the PARI one at start-up, in a background
  thread, so only the first visit after a database change waits. **Rebuild now** forces a rebuild.
- **The Pick map says there is nothing to compare with.** No snapshot of that pool is stored (a new
  database, or the model pool before a `run --model` or `oeisbot snapshot --all`), or every stored
  snapshot equals the live pool. Run `oeisbot snapshot`, change something (a session, a `sync`), and
  reload; every tile is gray until then, but the areas are still right.

## Maintenance

- **Which gp produced a result.** `oeisbot setup` and every `oeisbot run` record the runtime versions.
  The current ones are in `meta`, and each session carries a short token of its own:

  ```sql
  SELECT key, value FROM meta WHERE key IN ('gp_version', 'sandbox_python_version');
  SELECT id, started_at, note FROM sessions ORDER BY id DESC LIMIT 5;   -- note ends with gp=2.17.4/GMP-6.1.2
  ```

  `unknown` means the probe could not be trusted — **not** that gp failed to run the session. Four
  causes: the binary is missing or the probe timed out (10 s); a non-zero exit; no output; or exit 0
  from something whose banner does not say `GP/PARI`, which includes a real gp behind a wrapper whose
  preamble runs past the 300-character cap. If `gp --version` works by hand but the row says `unknown`,
  it is one of the last two. The session token is the one that survives a gp upgrade; see
  [data and schema](data-and-schema.md#meta) and
  [known limitations](known-limitations.md#runtime-provenance).
- **Refresh the mirror** with `oeisbot sync` before sessions. Sequences that lost `more` drop out of the
  pool. `oeisbot daemon` does this itself at each start, under a 10-minute limit per git command.
- **Disk growth**: `data/runs/` (logs and generated programs) and `data/bfiles/` are never pruned. Both
  are safe to delete, but deleting run logs loses the term records of past runs. The daemon's logs in
  `data/daemon/` are never pruned either and are safe to delete while it is not running. The database's pick
  snapshots **are** pruned, in the transaction that writes a new one: the 30 newest of the PARI pool
  (about 3,400 rows each) and the 10 newest of the model pool (about 26,700 rows each), set by
  `config.PICK_SNAPSHOTS_KEPT`. At those numbers they are a few tens of megabytes at most.
  See [data and schema](data-and-schema.md#pick_snapshots-and-pick_snapshot_rows-the-pool-a-session-drew-from-history-item-54).
- **Starting over**: stop any session, the daemon and the dashboard, then delete `data/oeisbot.sqlite3*` and run
  `oeisbot setup` and `oeisbot sync`. This deletes all attempt and review history, including which
  sequences were already submitted.
