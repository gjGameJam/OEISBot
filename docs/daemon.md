# The daemon: `oeisbot daemon`

`oeisbot daemon` runs sessions back to back, unattended, inside a nightly window of local time. It is
`oeisbot/daemon.py` (history item 58, built 2026-11-22 and 23), with the writers' lock in
`oeisbot/lock.py` and the Task Scheduler definition in `oeisbot/schedule.py`.

**State on 2026-11-23: built and tested, never run against the real project, and not armed.**
`data/daemon/` and `data/writer.lock` do not exist yet, the scheduled task has not been imported, and
the dashboard's line has not been seen in a browser. **A start does nothing here until the user has run
`oeisbot daemon --arm`** ([arming](#arming)); that step is the user's alone. Read
[before the first night](#before-the-first-night) first.

## What it is, and what it is not

It supplies what a person at the console supplied for `oeisbot run`: when to start and stop, which
budgets to run at, not drawing the same undecided sequence night after night, syncing the mirror,
noticing a full disk, and tidying up after a process that was killed.

- **It adds no selection rule and no verification rule.** Every pick is drawn from
  `attempt.session_pool` and goes through `attempt.run_session` and `attempt.attempt_sequence`, as a
  pick of `oeisbot run` does. The [cooldown](#the-cooldown) only withholds pool members from a night's
  draw; it retires nothing and changes no row.
- **It submits nothing.** It contacts oeis.org only through the calls a session already makes (a b-file
  download, a win's re-check), all GETs through `ingest.bfile.http_get`.
  [Invariant 1](development.md#invariants) is unchanged.
- **It runs PARI sessions only.** `Daemon.pool` and `Daemon.run_session` pass no model, so the `--model`
  pool is never drawn from.
- **It registers nothing.** `--task-xml` writes (or prints) a Task Scheduler definition; importing it
  is the user's step.
- **Being started is not enough to run.** A night runs only where a person has run
  `oeisbot daemon --arm` once ([arming](#arming)). Until then every start, by whatever started it,
  writes one line to its log and exits with code 2.

## The command

```
.venv\Scripts\oeisbot daemon                      # run one window (default 22:00-08:00), then exit
.venv\Scripts\oeisbot daemon --window 23:30-06:00
.venv\Scripts\oeisbot daemon --window always      # no closing time: until stopped or out of work
.venv\Scripts\oeisbot daemon --no-sync            # do not pull the mirror first
.venv\Scripts\oeisbot daemon --status             # is one running, and what is it doing
.venv\Scripts\oeisbot daemon --stop               # ask the running one to stop
.venv\Scripts\oeisbot daemon --arm                # allow nights to run here (the user's step, once)
.venv\Scripts\oeisbot daemon --disarm             # take that back: the next start does nothing
.venv\Scripts\oeisbot daemon --task-xml task.xml  # write the Task Scheduler definition to a file
```

| Flag | Effect |
|---|---|
| `--window HH:MM-HH:MM` | local hours it may run in; default `22:00-08:00` (`daemon.DEFAULT_WINDOW`), or `always` |
| `--no-sync` | skip the sync of the mirror at the start |
| `--status` | print `daemon.describe(daemon.status())` and exit 0. Reads only: the lock is probed, the heartbeat file is read, the database is not opened |
| `--stop` | if a daemon is running, write the stop request `data/daemon/stop` and exit 0; if none is, print `no daemon is running; nothing to stop` and write nothing |
| `--arm` | write `data/daemon/armed`, print where it is and how to take it back, and exit 0. Starts nothing ([arming](#arming)) |
| `--disarm` | delete `data/daemon/armed` and exit 0; says `(it was not armed)` when there was none, and that a running daemon is not stopped by this when one is running |
| `--task-xml [FILE]` | write the scheduled-task definition for `--window` to `FILE` (UTF-16, as the definition declares) and exit 0; without `FILE`, print it. Starts and registers nothing; refused for `always` |

`daemon.command` looks at `--status` first, then for a marker left by a killed mutation run
([arming](#arming), last paragraph), then at `--arm`, `--disarm` and `--stop`, then parses
`--window`, then `--task-xml`; the first of them that is given is the only one acted on. So `--status`,
`--arm`, `--disarm` and `--stop` never read the window, and they work while a daemon holds the writers'
lock: `daemon` is not in `cli.LOCKED`, because the running daemon takes the lock itself, under the name
`daemon`, for its whole window. Only when none of the five is given does the command go on to start a
night, and the first thing it then asks is whether it is armed.

One invocation is one window. Nothing in the daemon waits for the next night: it exits when the window
closes, and the scheduled task (or a person) starts it again.

## Arming

Built 2026-11-23 (history item 58, section F), after two incidents in which a test started more than it
meant to ([development](development.md#the-products-own-guard)).

**What it is.** A file, `data/daemon/armed` (`daemon.armed_path`). `oeisbot daemon` runs a night only
when that file exists (`daemon.is_armed`). Its contents are the local time it was written and decide
nothing; only its existence is asked.

**Why.** The daemon is the one command here that works for hours with nobody watching, and nothing
about being started shows that anyone meant it: a scheduled task imported and forgotten, a script, a
coding agent, and a test that falls through its stubs (2026-11-22) all start it the same way. So
starting is not enough. Arming is a separate act that only `--arm` performs.

```
.venv\Scripts\oeisbot daemon --arm       # prints: armed (<path>): `oeisbot daemon` will now run a night when it
                                         #         is started inside its window. Take it back with `oeisbot daemon --disarm`.
.venv\Scripts\oeisbot daemon --disarm    # prints: disarmed: a start will now do nothing
```

**Arming is the user's step, never an agent's.** It is the standing permission for unattended nights
on this machine, in the same class as closing a review. Nothing in the project arms itself, and a
coding agent must not run `--arm` (`CLAUDE.md`).

**What an unarmed start does** (`daemon.command`). It parses `--window` (a window that cannot be read
is still refused first, with its own message and code 1), then asks `is_armed`, **before the writers'
lock, the database and everything else**. Unarmed, it:

- appends one line to `data/daemon/daemon-YYYYMMDD.log`, creating `data/daemon/` if it does not exist,
  and prints the same line:
  `daemon: not started: not armed. A night runs here only after `oeisbot daemon --arm` (see
  `docs/daemon.md`); this start did nothing`;
- exits with **code 2**.

It does not take or create the writers' lock (`data/writer.lock` is not created), does not open the
database, does not write or replace the heartbeat, does not look at whether the window is open (the
answer is the same by day and by night), and runs no recovery, no sync and no session
(`tests/test_daemon.py::test_an_unarmed_start_does_nothing_at_all`). The log line is the only trace.

**The same rule one level down.** `Daemon.run` asks again and raises `daemon.NotArmed` when the file
is not there, so a script that builds a `Daemon` itself and calls `run()` is refused as the command
is. Inside the command it covers arming taken away between the first check and the night, a gap of
the wait for the lock at most. **That is a refusal, not a fault**: `daemon.command` catches `NotArmed`
(and the guard's `RealProjectRefused`) from the night before its handler for a night's faults, logs
`daemon: not started: the daemon is not armed: a night runs here only after `oeisbot daemon --arm``,
writes no heartbeat, and exits with code 2, as an unarmed start does
(`tests/test_daemon.py::test_a_refusal_at_the_last_moment_is_a_refusal_not_a_fault`). (The first
version let the faults' handler catch it: "ended by a fault", a `stopped` heartbeat, code 1. Found by
the documentation pass on 2026-11-23 and fixed the same day.)

**What needs no arming.** `--status`, `--stop`, `--task-xml`, `--arm` and `--disarm`: none of them
starts anything.

**Nothing the daemon does removes it.** Arming is a standing permission, not a one-night token: a
finished night, a kill and the next start's recovery all leave the file
(`test_arming_survives_a_night_and_a_kill`). Only `--disarm` (`daemon.disarm`) deletes it. `--disarm`
is also the way to make an imported scheduled task do nothing without removing the task. **It does not
stop a daemon that is already running** (`--stop` does that, and `--disarm` says so when one is
running): it is the next start that does nothing.

**Where it shows.** When no daemon is running and it is not armed, `--status` adds the line
`not armed: a start will do nothing until you run `oeisbot daemon --arm` (that is how a night is allowed
to run here)`, and the dashboard line reads `Daemon is not armed, so a start will do nothing (oeisbot
daemon --arm allows it)`. `daemon.status()` carries it as `armed` (true or false); `daemon.describe`
reads an answer without the field as not armed, while the dashboard's `daemonLine` reads only an
explicit `false` so (an older server's answer is left as it was). While a daemon is
running neither says anything about arming: disarming in the middle of a night changes nothing on
screen until that night ends.

**What it is not.** It is a file that anyone, or any program, with access to `data/daemon/` can create
or delete. It guards against accident, not against intent, and it guards only the daemon: `oeisbot
run`, `attempt` and `sync` start as before. Code running under a test (pytest, or a script with
`OEISBOT_UNDER_TEST=1` in its environment) cannot arm the real project by calling `daemon.arm()`: the
[product's own guard](development.md#the-products-own-guard) refuses that, and `request_stop`,
`disarm`, the daemon's log, its heartbeat and `Daemon.run` likewise; a script that sets nothing is
not refused. See
[known limitations](known-limitations.md#the-safeguards-against-reaching-the-real-project).

**A mutation run that was killed stops the daemon too** (`daemon._mutant_left_in_tree`). While
`MUTANT_IN_TREE.json` exists in the project root (`config.ROOT`; `daemon.MUTANT_SENTINEL`; written by
`data/item58/mutate.py` while one of its mutants is in the code, and left behind only if the harness
was killed) and the process's `OEISBOT_MUTATING` is not `1` (the harness's own test runs carry that
variable, so the marker it wrote itself is not an alarm to them), `oeisbot daemon` refuses everything
but `--status`
(`test_a_mutant_left_in_the_code_stops_the_daemon_from_doing_anything`): it exits with the message `` `oeisbot daemon` refused: ... says a mutation run was
interrupted and left a changed file in the code. Restore it as that file says, then delete it `` and
code 1, having started, armed, disarmed and stopped nothing. The code that would run is then not the
code, and the changed line may be a safeguard
([development](development.md#mutation-sets-for-item-58)).

## The window

`Window.parse` reads `HH:MM-HH:MM` as two local wall-clock times.

- The start hour is 0 to 23, the end hour 0 to 24, minutes 0 to 59, and the end may be at most `24:00`.
  Single-digit hours are read (`9:30-17:05`); the window prints with two digits.
- A start later than the end is a window over midnight (`22:00-08:00`).
- **The two times must differ.** `22:00-22:00` is rejected rather than guessed at.
- `always` (any case) and `00:00-24:00` both mean no closing time.
- Anything else is refused with `window '<text>': expected HH:MM-HH:MM in local time with two different
  times (e.g. 22:00-08:00), or `always``, and the command exits without taking the lock.

**How it closes.** At start-up `Daemon.run` asks `Window.ends_at(now)` once for the closing time of the
window that contains the present moment, and keeps it (`window_end`). If the present moment is outside
the window, the daemon logs `daemon: outside the window ...; nothing started` and exits 0: no recovery,
no sync, no session. It says so in the log only and leaves the heartbeat file alone, so a start by day
(the task catching up after the machine was off, or someone pressing Run) does not replace last
night's result and warnings. Otherwise the closing time is checked every second
(`poll`), and reaching it is a [stop](#stopping): the run in hand is interrupted.

**Daylight saving.** The closing time is a wall-clock time, and the seconds left are computed through
real timestamps (`daemon.seconds_until`), so the night the clocks change is an hour shorter or longer in
seconds, as it is on the machine: `22:00-08:00` is nine hours on the spring night and eleven on the
autumn one (`tests/test_daemon.py::test_a_night_with_a_clock_change_is_measured_in_real_seconds`). A
window whose **end** falls inside the hour the clocks skip or repeat ends an hour off by the wall clock
on that one night (stated in `Window.ends_at`, not tested); the default window does not.

## One night, in order

1. **Start** (`daemon.command`). stdout and stderr are set to escape what they cannot encode; the log
   is opened; **arming is checked, before anything else is touched**: unarmed, the start logs
   `daemon: not started: not armed. ...` and exits with code 2, having taken no lock and opened no
   database ([arming](#arming)). Armed, the writers' lock is taken as `daemon`. **If another command holds it, the daemon waits**
   (`daemon._take_the_lock`): it logs the refusal once and tries again every 60 s (`LOCK_RETRY_S`) for
   as long as the window is open, because the scheduled task fires once a day and an `oeisbot attempt`
   still running at 22:00 would otherwise cost the night. If the window closes first it logs
   `daemon: not started: the writers' lock is held and the window has closed` and exits with code 1.
   With `--window always`, or when started outside the window, it does not wait: one refusal ends it
   (`... the writers' lock is held`, or `... is held and the window is not open`), code 1. While it
   waits it holds nothing and writes no heartbeat, so `--status` reports no daemon (and names the other
   command), and `--stop` finds nothing to stop. Then the database is opened (a failure is logged and
   the exit code is 1); handlers for Ctrl-C and Ctrl-Break (and `SIGTERM`) are installed; Windows is asked not to
   idle-sleep (`keep_awake`).
2. **Window.** Outside it, exit as above.
3. **Recover** from a process that was killed ([recovery](#recovery)). Then one log line counts the
   reviews at `new` or `reviewing`, when there are any
   (`daemon: N review(s) waiting for a person (`oeisbot review list`)`), and the count goes into the
   heartbeat as `reviews_waiting`: each such review keeps its sequence out of the draw until the user
   decides.
4. **Sync** the mirror once, unless `--no-sync` ([the sync](#the-sync)).
5. **Sessions**, one after another, each of up to 25 picks (`Budgets.session_attempt_cap`), at the
   lowest tier of [the ladder](#the-budget-ladder) that has something to draw after
   [the cooldown](#the-cooldown). Before each session and each pick: [the start
   gate](#the-start-gate) and [the machine checks](#machine-checks-and-pauses); before each pick also
   [the circuit breaker](#the-circuit-breaker).
6. **Finish**: the reason is logged as `daemon: finished: <reason>` and left in the heartbeat as
   `state: stopped` with the reason as `detail`. The night ends when the window closes, on
   `--stop`, on Ctrl-C, when no tier has anything to draw, when too little of the window is left to
   verify a pick, or on one of the faults below.

Each session is an ordinary `sessions` row. Its note ends `daemon=1 tier=<name>`, after the budgets that
every session's note now carries, for example
`count=25 alpha=1.0 seed=None model=None verify_s=60 extend_s=1800 gp=2.17.4/GMP-6.1.2 daemon=1 tier=base`.
The draw is not seeded.

Before a session is started the daemon builds the tier's pool and the cooldown itself. A tier with
nothing to draw therefore costs a pool build and **no session row**.

**Pick-map snapshots.** The sync stores one if the pool changed (`attempt.snapshot_after_sync`, as
`oeisbot sync` does). Of the sessions, only one at the lowest tier may store one, and only until a
session at that tier has returned: normally the first of the night, or the next if that one raised
(`run_session(snapshot=...)`); every other session passes `snapshot=False`. The snapshot is the whole
pool, not the pool minus the cooldown.

## Recovery

A scheduled task is usually ended by being killed, so every start inside the window begins with
`Daemon.recover`. It is safe because the daemon holds the writers' lock: no session can be running, so
every open session row is an orphan. It does four things.

1. **A stop request left behind.** `data/daemon/stop` is deleted if its modification time is earlier
   than the moment just before this daemon took the lock. A request made after that is for this daemon
   and is honoured.
2. **Session rows left open** (`finished_at` NULL). Each is closed with `db.finish_session` (which fills
   `attempts`, `wins` and `machine_s`), its `finished_at` is then set to the latest `finished_at` (or
   `started_at`) among its attempt rows, or to its own `started_at` when it has none, and its note gains
   ` (closed by recovery: its process ended mid-session)`. The run that process was on, if any, has no
   attempt row and is not reconstructed.
3. **Run directories left in `data/scratch`** (`sweep_scratch`). Removed only when the entry is a
   directory, its whole name matches `A\d{6}-[a-z]+-[0-9a-f]{8}` (what the harness names a run's
   directory, e.g. `A123456-gp-1a2b3c4d`), and it was last modified more than 6 hours ago
   (`SCRATCH_ORPHAN_AGE_S`; longer than any pick can last). Everything else is left: the lock does not
   cover the test suite, which runs sandboxed programs in the same directory. On 2026-11-23
   `data/scratch` holds 34 directories, 2 of which match (both `A000079-python-...`, from 2026-09-19);
   counted with `ls`, the same before and after a run of the whole test suite.
4. **A pending win without its saved result.** For each `recheck_pending` attempt whose
   `data/pending/attempt-<id>.json` is missing, a warning goes to the log and the heartbeat. The
   sequence stays blocked until a person runs `oeisbot recheck --release <id>`
   ([operations](operations.md#a-win-whose-re-check-failed-recheck_pending)); the daemon never does.

## The sync

`Daemon.sync_mirror` calls `oeisdata.sync(pull=True, timeout=SYNC_TIMEOUT_S)` and then
`attempt.snapshot_after_sync`: the same work as `oeisbot sync`, with a time limit. It runs **once per
start**, so with `--window always` it runs once for the whole run.

- **Timeout.** Each git command gets 600 s (`SYNC_TIMEOUT_S`). One that has not finished is ended
  together with the helpers it started (`taskkill /T /F` on Windows, then `Popen.kill`) and
  `oeisdata.GitTimeout` is raised. `oeisbot sync` at a console passes no timeout and waits for ever, as
  before.
- **Stale lock files.** Before a timed fetch, `index.lock`, `shallow.lock`, `HEAD.lock` and
  `packed-refs.lock` in `data/oeisdata/.git` are removed when at least 300 s old
  (`oeisdata.STALE_GIT_LOCK_S`). A younger one is left, since it may belong to a git that is still
  running, and git's own error then fails that sync: at the fetch for a `shallow.lock` (a warning, and
  the night goes on), at the reset for an `index.lock` (no sessions that night, see the next two
  points).
- **Repair after a failed reset.** If `git reset --hard FETCH_HEAD` fails or is ended, the working tree
  may be part old and part new. `oeisdata.update` then runs `git reset --hard HEAD` (no network) before
  reporting the original failure. It removes `index.lock` first **only when the reset was ended by the
  time limit** (`GitTimeout`): that lock is the one this call's own reset left. A reset that git itself
  refused (another git holds the index, or a lock under 300 s old was left in place above) leaves the
  lock alone, so the repair fails on the same lock.
- **`MirrorUnusable`.** If that repair fails too, `oeisdata.MirrorUnusable` is raised. The daemon then
  warns `sync failed and left the mirror unusable (...); no sessions tonight. Run `oeisbot sync` by
  hand` and ends the night: an entry file cut short would parse as an entry with a wrong term, and a
  correct program would be retired for it. A reset refused because of someone else's `index.lock` ends
  here too, though the tree was not touched: something else may be rewriting the mirror. `oeisbot sync`
  at a console removes no lock file; if git then says `index.lock` exists and no git is running, the
  file is deleted by hand.
- **Any other failure** (no network, a fetch that timed out, a repaired reset) is a warning in the log
  and the heartbeat, `sync failed (...); going on with the mirror as it is (last pulled ...)`, and the
  night goes on with the data it has.
- **When the mirror was last pulled** is its own `meta` key since item 58: `pulled_at`, written by any
  sync that pulled (`oeisdata.sync`), the daemon's or `oeisbot sync`'s. `synced_at` is not that:
  `oeisbot sync --no-pull` moves it too, and rebuilding the table from an old mirror does not make the
  mirror new. The daemon reads `daemon.pulled_at(conn)`: `meta.pulled_at`, or `synced_at` where the
  database's last sync predates the key. The live database has no `pulled_at` yet (read 2026-11-23), so
  until the next pull the daemon goes by `synced_at`, `2026-09-17T18:31:41+00:00`.
- **No console windows.** git, `taskkill` and the runtime version probes are started with
  `CREATE_NO_WINDOW` (`oeisdata.NO_WINDOW`, `setup_tools._probe_version`). Under `pythonw.exe`, which
  has no console, Windows would otherwise give each of them a visible one, and closing a git window
  kills git in the middle of a reset.

Two limits. The sync does not look at a stop request at all: each of its git commands (the fetch, the
reset, a repair) runs up to its 600 s, and reading the mirror afterwards (about 70 s for a whole sync by
[pipeline](pipeline.md#1-sync-oeisbot-sync---no-pull)) is not interruptible either. And a first clone (no `data/oeisdata/.git`)
would run under the same 600 s per command, which is not sized for a 2.3 GB clone: make the first clone
with `oeisbot sync` by hand.

## The budget ladder

`daemon.TIERS`, lowest first. Each is `config.DEFAULT_BUDGETS` with two times replaced (`Tier.budgets`);
there is no `Budgets` field for the tier.

| Tier | `verify_wall_s` | `extend_wall_s` | Pool on 2026-11-23 | Left out as `all_programs_dead_ends` |
|---|---|---|---|---|
| `base` | 60 s | 1,800 s | 3,336 | 164 |
| `verify600` | 600 s | 1,800 s | 3,548 | 50 |
| `long` | 600 s | 10,800 s (3 h) | 3,571 | 27 |

The pool column is `data/item58/measure_pool.py` (read-only, the real `attempt.session_pool`) run on
2026-11-23 against the live database, before any cooldown; `no_supported_program` is 1,430 at every
tier and `verify_out_of_reach` is 383 at 60 s and 285 at 600 s.

- **Every start begins at `base`.**
- **It climbs** to the next tier only when the current tier's pool, after the cooldown, has nothing to
  draw. Within one start it never goes back down.
- **At the top tier with nothing to draw** the night ends: `nothing left to draw at any tier`.
- **The stale-mirror rule.** It does not climb when the mirror's last pull (`daemon.pulled_at`, see
  [the sync](#the-sync)) is more than 7 days old (`STALE_SYNC_DAYS`) or cannot be read; the night ends
  instead, saying so. A higher tier spends hours
  per pick, and spending them on entries that may have been extended since is what a sync prevents.
- **Why `base` is 60 s / 1,800 s** and not the 3-hour default extension: every session from 7 to 12
  ran with the 30-minute extension, and sessions 8 to 12 at exactly 60 s / 1,800 s (session 7 verified
  at 600 s; from each attempt row's `extra.extend_wall_s` and the run times of the `verify_timeout`
  rows, queried 2026-11-23), so the pool it starts from and the time a pass takes are the ones those
  sessions measured. `verify600` is session 7's setting; `long` adds the default extension. (The
  comment above `daemon.TIERS` says sessions 7 to 12 for `base`, which is true of the extension only.)

What makes the tiers differ is `db.is_dead_end`, which judges a program at the budgets asked: a program
that timed out at 60 s is a dead end at `base` and not at `verify600`.

## The start gate

A pick is started only while enough of the window is left to **verify** it:
`daemon.start_gate_s(budgets)` = `MAX_PROGRAMS_PER_SEQUENCE` (3) x `verify_wall_s` + `PICK_SLACK_S`
(300 s). That is 480 s (8 min) at `base` and 2,100 s (35 min) at `verify600` and `long`. With
`--window always` there is no gate.

The extension is deliberately not counted. If the window closes during an extension the run is
interrupted, which retires nothing, adds no failure penalty and is not cooled. (The first design
counted the extension and left about a third of every `long` night unused.) What it costs: a run in
its extension when the window closes loses the searching it had done, and one that had already found
new terms opens its review with those terms only; the heartbeat then carries a warning naming the
sequence (`Daemon._note_wins_cut_short`).

The gate is asked at the top of each session and before each pick. When it fails the night ends with
`N min left in the window ..., and a pick at tier T needs M to be verified`.

## The cooldown

`daemon.Cooldown`, built before each session for the tier about to run. A pool member is **held back**
when its most recent attempt, in the last 14 days (`COOLDOWN_DAYS`, by `started_at`), changed nothing
about what an attempt at these budgets would do. "Most recent attempt" is the rows of the sequence's
newest `attempt_sequence` call (rows sharing `extra.attempt_call`; a row without the key stands alone).

A sequence with a recent attempt is **still drawn** in these cases, checked in this order. The second
is the whole test for an attempt that recorded only a skip; the last three apply to an attempt that ran
a program:

| Rule | Reason |
|---|---|
| One of the attempt's rows is `interrupted` | the attempt was cut short by the daemon's own stop; a program of it may never have run |
| It recorded only a skip (no row has a `program_sha`), the skip is not `daemon_error`, and the mirror's last pull (`daemon.pulled_at`) is later than the skip | the cause was the network or the data of that day (a b-file that could not be fetched, inconsistent terms); a sync may have changed it |
| None of its runs was at budgets at least as large as this tier's (`extra.verify_wall_s`, `extra.extend_wall_s`) | a timeout at 60 s says nothing about 600 s; that sequence is what the next tier is for. A figure a row does not record is taken as large enough |
| One of its runs (at such budgets) is a dead end at this tier's budgets (`db.is_dead_end`) | it made progress: a program was retired, and the next attempt runs something else |
| The number of known terms an attempt would see now (`attempt.offline_known_terms`) is not among the counts those runs saw | the entry changed |

Otherwise it is held. The two cases that hold are therefore:

- **a run that retired nothing**: `searched_bound`, `over_prediction`, `memory_cap`, a verified run cut
  off by a smaller extension than a dead end needs, and the like, at budgets no smaller than the
  tier's, with the entry unchanged. Such a sequence stays in the pool exactly as it was, and a loop
  would meet it every night;
- **a skip with no pull of the mirror since**, and a `daemon_error` skip for the whole 14 days whatever syncs, so one
  entry that makes a session raise does not end every night.

The cooldown is a `keep` filter passed to `run_session`. It does not change the pool that is stored for
the Pick map, so the map's chances are those of the whole pool and not exactly the daemon's.

`extra.verify_wall_s` is recorded from item 58 on. All 280 attempt rows in the live database predate it
(counted by query, 2026-11-23: 0 rows carry the key), so they would be judged as having had any budget;
none is inside the 14 days (the newest started 2026-09-30).

## Machine checks and pauses

`Daemon.machine_problem` is asked at the top of each session and before each pick:

- free space on the drive holding `data/` under `reserve_disk_bytes` + `DISK_MARGIN_BYTES` = 8 + 2 =
  **10 GiB**: state `paused_disk`;
- free physical RAM under `reserve_phys_bytes` + `RAM_MARGIN_BYTES` = 3 + 1 = **4 GiB**: state
  `paused_ram`.

The margins exist because at the reserve itself the sandbox ends a run as `disk_cap` or refuses to
launch it, and each such pick is a `failed` row that doubles the sequence's failure penalty.

At the top of a session the daemon waits while the problem lasts, looking again every 600 s
(`PAUSE_S`), in one-second slices so that a stop or Ctrl-C ends the wait at once. A machine that never
recovers is waited on until the window closes. When the check fails before a pick, the session ends
with its remaining picks unrun, and the daemon then takes **one pause even if the machine looks fine
again** (state `paused_machine`), so that memory hovering at the threshold does not start a session per
look.

## The circuit breaker

Before each pick, `Daemon.machine_failures_in_a_row` counts the newest picks **since this daemon
started** whose last rows ended in `launch_error`, `disk_cap`, `harness_error` or `bfile_error`
(`MACHINE_FAILURES`): stops that are the machine's or the network's doing. It counts picks
(`extra.attempt_call`), not rows, across sessions. At 5 in a row (`BREAKER_RUN`) the night ends:
`5 picks in a row ended as launch_error / disk_cap / harness_error / bfile_error: the machine or the
network, not the programs. Stopped rather than spend the pool on it`. None of those stops retires a
program, but each `failed` row among them counts in the failure penalty.

## Sessions that raise

An exception out of a session (or out of the pool build before it) is caught.

- The traceback goes to the daemon's log: a scheduled task has no console.
- If a pick was in hand (`Daemon.in_hand`, set as the pick starts and cleared when the session asks
  about the next one), that sequence gets a skip row written by the daemon: `strategy` `daemon`,
  `failure_mode` `daemon_error`, the exception in `detail` (500 characters at most), no session id. The
  cooldown then holds it for 14 days, and a heartbeat warning names it. A fault between picks is charged
  to no sequence.
- The night goes on with a new session. **Two in a row** (`ERROR_RUN`) end it:
  `2 sessions in a row raised (...); stopped rather than go on. The traceback is in the daemon's log`.

A session that returns having started nothing, for no reason the daemon gave it, also ends the night
(`session N had K candidate(s) to draw and started none; stopping rather than loop`).

Anything raised outside that (in recovery, say) is caught in `daemon.command`: traceback to the log,
heartbeat `stopped` with `ended by a fault: ...`, exit code 1. A database that cannot be opened is
logged (`daemon: not started: the database could not be opened (...)`) with the same exit code, and
leaves the heartbeat as it was.

## Stopping

Three things stop a running daemon gracefully. Each sets one flag (`Daemon.stop`; the first reason given
is the one reported), which the run in hand reads on every tick.

| How | Seen by | Reason logged |
|---|---|---|
| `oeisbot daemon --stop` | the file `data/daemon/stop`, looked for every second (`POLL_S`) by a second thread | `stop requested (`oeisbot daemon --stop`)` |
| the window's end | the same thread | `the window 22:00-08:00 closed` |
| Ctrl-C or Ctrl-Break in its console, once | the signal handler | `interrupted from the console` |

What then happens:

- **The run in hand is interrupted.** `verify.Harness.on_tick` asks first, before any budget, and halts
  the run with stop `interrupted` (`Stop.INTERRUPTED`), detail
  `stopped on request N s into the run, during verification` or `... during the extension`.
- **`interrupted` retires nothing.** The row is `failed` (stopped while verifying) or `verified`
  (stopped in the extension with no new term) with `failure_mode = 'interrupted'`. No clause of
  `db.is_dead_end` matches it, it is outside `db.DETERMINISTIC_FAILURES`, `select.candidates` leaves it
  out of the failure penalty, and the cooldown does not hold its sequence. The sequence is exactly as
  drawable the next night as it was.
- **New terms found before the stop are kept.** Such a run is a win like any other: recorded as
  `recheck_pending`, re-checked against oeis.org, and given an artifact and a review. So a stop can take
  as long as a re-check: in network trouble, three tries of two requests with a 60 s timeout each, plus
  the waits of 30 s and 120 s, about nine minutes. The window can be overrun by that much.
- **No further program or pick is started.** A stop that lands between two programs of one pick starts
  no other; a model stage is not involved (the daemon runs none).
- The session row is closed, the reason is logged, an honoured stop request is deleted, and the
  heartbeat is left as `stopped`. The process exits 0.

**Ctrl-C twice** ends at once: the second press raises `KeyboardInterrupt` in the main thread. The log
says `ended at once from the console; the run in hand, if any, was not recorded`, the heartbeat is set
to `stopped`, and the exit code is 130.

**The 20-minute last resort.** If the main thread has not come back `STOP_GRACE_S` (1,200 s) after a
stop was asked for, the second thread ends the process (`Daemon.hard_exit`, `os._exit(3)`), ending the
git command of a sync first (`oeisdata.end_running_git`) so that it does not go on rewriting the mirror
after the lock is released. The honest long waits are a re-check in network trouble and a sync in hand.
This is a kill from inside: what it leaves is the same as below.

`--stop` during a sync is not acted on until the sync is over: the git commands still to run (600 s
each at most) and the reading of the mirror. The 20-minute last resort is what bounds it.

## What a kill leaves

Closing the console window, logging off, Task Scheduler's "End", `taskkill` and a power loss end the
process without running any handler. **Only `--stop`, the window's end and Ctrl-C are graceful.**
After a kill:

| Left behind | What deals with it |
|---|---|
| the writers' lock | nothing to do: the operating system releases it with the process |
| the sandboxed job | killed with the process by the Job Object's kill-on-close ([sandbox](sandbox.md)) |
| the run in hand | **no attempt row**: a run is recorded after it ends. The terms it had accepted are in its `data/runs/` log |
| an open `sessions` row | closed at the next start's [recovery](#recovery) |
| the run's directory in `data/scratch` | swept by recovery once it is 6 hours old |
| a heartbeat that does not say `stopped` | `--status` and the dashboard say the last run did not finish |
| a git child of the sync, for a moment, and its lock files | lock files at least 5 minutes old are removed by the next timed sync |
| a win recorded as `recheck_pending` whose result was not yet saved | a warning at the next start; `oeisbot recheck --release <id>` by hand |

Recovery runs only when a daemon next starts inside its window. `oeisbot run` does not run it.

## The heartbeat file and `--status`

`data/daemon/heartbeat.json` is rewritten by the daemon whenever its state changes and at least every
30 s (`HEARTBEAT_S`), through `heartbeat.part` and a rename (retried 5 times, since on Windows a rename
fails while another program has the file open). A write that fails is logged once per streak and costs
nothing else. It is a file and not a `meta` row because every write to `meta` discards the dashboard's
cached Pick-map pool.

**It does not say whether a daemon is running.** A killed daemon leaves a fresh-looking file. Liveness
comes from the writers' lock.

| Field | Meaning |
|---|---|
| `state` | `starting`, `sync`, `running`, `paused_disk`, `paused_ram`, `paused_machine` or `stopped` |
| `detail` | `building the pool` between sessions; what is short while paused; why it ended when `stopped`; otherwise null |
| `a_number` | the sequence being attempted, or null |
| `tier` | the tier of the session in hand |
| `session` | written as null and never set to a session id in this version |
| `synced_at` | when the mirror was last pulled (`daemon.pulled_at`: `meta.pulled_at`, else `meta.synced_at`), copied each time a pick starts; absent until the first pick |
| `reviews_waiting` | how many reviews were at `new` or `reviewing` when this daemon started |
| `warnings` | text the user should see without reading the log, kept for the night: a failed sync, a pending win without its file, a sequence held for `daemon_error`, a win cut short |
| `progress_at` | UTC time of the main loop's last step. Only the main loop moves it |
| `at` | UTC time the file was written. The second thread moves it too, so `at` fresh and `progress_at` old means the main loop is inside one long call |
| `pid` | the daemon's process id |
| `window` | the window as text |
| `window_ends` | the closing time, local, to the minute; null for `always` |
| `stop_reason` | the first stop reason, or null |
| `stopping_for_s` | whole seconds since the stop was asked for, or null |

`daemon.status()` returns `running`, `other_command`, `heartbeat` and `armed`. `running` is true when the lock
is held and its description names `daemon`; when the lock is held and has no readable description, it
is true if the heartbeat exists and is not `stopped`. `other_command` names a different command that
holds the lock. `armed` is whether `data/daemon/armed` exists ([arming](#arming)). `oeisbot daemon --status` prints that as text, for example:

```
daemon is running (pid 4242): running A123456 at tier base
window 22:00-08:00, closes 2026-11-24T08:00 local time; mirror last synced 2026-11-23T03:01:10+00:00
last step 2026-11-24T03:12:40+00:00 UTC; heartbeat 2026-11-24T03:13:05+00:00 UTC
```

(an illustration of the format in `daemon.describe`, not captured output). While stopping, a line
`stop asked for N s ago (...); still finishing` comes directly after the first; one `warning:` line per
warning comes at the end. When
none is running it says `daemon is not running`, names any other command holding the lock, and gives
the last daemon's end: `stopped at ... UTC (<reason>)`, or `did not finish; it was <state> at ... UTC
when its process ended. The next start tidies up after it`. **When none is running and it is not
armed**, a line of its own comes directly after the first. On this machine on 2026-11-23, where no
daemon has run and none is armed, `daemon.describe` gives (read from the code; the command was not
run for this page):

```
daemon is not running
not armed: a start will do nothing until you run `oeisbot daemon --arm` (that is how a night is allowed to run here)
no daemon has run here yet
```

While a daemon is running the text says nothing about arming.

## The log

`data/daemon/daemon-YYYYMMDD.log`, one file per local calendar day (a night over midnight writes two),
appended, UTF-8, each line prefixed `HH:MM:SS`. It holds the daemon's own lines (prefixed `daemon:`) and
everything a session prints, since the same function is the sessions' log. The file is written first
and the console second, and neither can raise: under the scheduled task there is no console at all.
Nothing prunes these files.

## The writers' lock

Since item 58 one lock covers every command that runs programs, rewrites the mirror or the runtimes,
stores a pool, or contacts oeis.org. A command that arrives second is refused at once. Only the daemon
waits for the lock, and only while its window is open ([one night](#one-night-in-order), step 1).

**Which commands** (`cli.LOCKED`): `run`, `attempt`, `sync`, `recheck` (with `--release` too),
`fetch-bfiles`, `setup`, `snapshot`. The daemon takes the same lock itself. Never refused: `stats`,
`queue`, `pick`, `attempts`, `model-check`, `review list`, `review set`, `dashboard`, and
`daemon --status`, `--stop`, `--arm`, `--disarm` and `--task-xml`.

**Why.** Three things break when two such processes overlap:

- the 1 request per second limit on oeis.org is a per-process global (`ingest.bfile._throttle`), so two
  processes each keep to it and together do not;
- `oeisbot recheck` and a session's own retry of pending re-checks would resolve the same win twice;
- `oeisbot sync` runs `git reset --hard` on the mirror under a session that is reading it, and
  `oeisbot setup` rewrites the runtimes and grants under a sandbox that is using them.

`snapshot` runs nothing but stores a pool, and one built while `sync` is half way through rewriting the
mirror would be kept.

**The refusal** is the command's exit message, for example:

```
`oeisbot run` not started: `oeisbot daemon` (pid 4242, started 2026-11-23 22:00:01 local time, by the
lock file's account) is running, and only one command that runs programs, syncs or contacts oeis.org
may run at a time. Wait for it, or stop it (`oeisbot daemon --stop` for the daemon)
```

**How it is implemented** (`oeisbot/lock.py`). An operating-system lock on `data/writer.lock`, held for
as long as the file is open: `msvcrt.locking` on Windows, on one byte at offset 2^30 (`LOCK_OFFSET`),
far past the end of the file, so the file itself stays readable; `fcntl.flock` elsewhere. Because the
operating system holds it, a process that ends in any way releases it: there is no stale lock and no
process id to guess about. The holder writes a description into the same file (`pid`, `command`,
`started_at` in local time) and empties it on the way out. The description decides nothing: it can be
stale or empty, and `lock.held()` asks the lock instead, by taking it for an instant and giving it
back. `held()` creates no file, which is what lets the read-only dashboard call it. `lock.writer` tries
5 times 0.05 s apart before refusing and `held()` looks 3 times 0.02 s apart before saying yes, because
a probe holds the lock for that instant.

**Its two limits.**

- It is taken by the commands, not by the library. A script that calls `attempt.run_session`,
  `verify.run_attempt` or `bfile.fetch` directly bypasses it unless it takes `lock.writer` itself.
- It covers the process, not its children: a `git` started by a `sync` that is then killed can outlive
  it for a moment while the next command starts.

Both are in [known limitations](known-limitations.md#the-daemon-and-the-writers-lock).

## The scheduled task

`oeisbot daemon --task-xml FILE [--window ...]` writes a Task Scheduler definition to `FILE`
(`schedule.write_task`, from `schedule.task_xml`) and prints the `schtasks` line that imports it.
**Nothing in the project registers, changes or removes a scheduled task.** To import it:

```
.venv\Scripts\oeisbot daemon --task-xml oeisbot-daemon.xml
schtasks /create /tn "OEISBot daemon" /xml oeisbot-daemon.xml
```

Give it a file name. The definition's first line declares `encoding="UTF-16"`, and `write_task` writes
exactly that (UTF-16 with a byte-order mark, CRLF line ends). Without a file name the definition is
printed, and a redirect then writes the bytes of the shell's own code page under a declaration that
says otherwise; only Windows PowerShell 5.1's `>` happens to produce UTF-16.

The task starts `pythonw.exe` (beside the interpreter that wrote the definition; its path is quoted when
it contains a space) with
`-m oeisbot.cli daemon --window <window>`, in the project root, every day at the window's opening time,
as the current user. The settings that are not Task Scheduler's defaults:

| Setting | Value | Why |
|---|---|---|
| `WakeToRun` | true | the machine is woken from sleep to run it (the user's choice, 2026-11-22) |
| `StartWhenAvailable` | true | a start missed because the machine was off happens when it comes back; the daemon ends at once if that is outside the window |
| `ExecutionTimeLimit` | `PT0S` (none) | the task's "End" is a kill that no handler sees. The daemon ends itself when the window closes |
| `DisallowStartIfOnBatteries`, `StopIfGoingOnBatteries` | false | it starts on battery and keeps going |
| `LogonType` | `InteractiveToken` | only while the user is logged on, in their own session: the sandbox's AppContainer profile and grants have only ever been used that way |
| `MultipleInstancesPolicy` | `IgnoreNew` | a second start while one runs does nothing (the writers' lock would refuse it anyway) |
| the program | `pythonw.exe` | no console window to close by accident. The record is the log, and `--status` says what it is doing |

Also set: `RunOnlyIfIdle` false, `RunOnlyIfNetworkAvailable` false, run level least privilege,
priority 7.

Notes:

- **"Allow wake timers".** Windows honours `WakeToRun` only where wake timers are allowed in the
  active power plan (Power Options, Sleep, Allow wake timers).
- `keep_awake` asks Windows not to idle-sleep while the daemon runs
  (`SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)`). It does not stop a closed lid, the
  power button or a scheduled hibernate. A verification the machine slept through is handled where it
  is judged: `db.is_dead_end` needs the CPU time, not only the wall time
  ([verification](verification-and-estimation.md#stop-reasons)).
- `--task-xml` with `--window always` is refused: a task needs an opening time.
- **An imported task does nothing until the daemon is armed.** Each night it starts the daemon, which
  appends its `not started: not armed` line to `data/daemon/daemon-YYYYMMDD.log` and exits with code 2
  (Task Scheduler shows that as the task's last result; `pythonw` has no console to show the line on).
  So the task may be imported before or after arming, and `--disarm` silences it without removing it
  ([arming](#arming)).
- If another locked command is still running when the task fires, the daemon waits for it, trying
  every minute until the window closes ([one night](#one-night-in-order), step 1).
- **Not tried.** The task has never been imported on this machine, so `schtasks` has not been seen to
  accept the file, and the sandbox has not been run under the task.

## The dashboard line

`GET /api/daemon` returns `daemon.status()`: the lock is probed and the heartbeat file read; the
database is not opened. The page shows one line under the header on every tab (`DaemonStrip` in
`dashboard/src/main.tsx`), polled like the rest, with the words decided by `daemonLine` in
`dashboard/src/daemonline.ts`. Details and tones are in [dashboard](dashboard.md#the-daemon-line).
The answer carries `armed`; when no daemon is running and it is false, the line says `Daemon is not
armed, so a start will do nothing (oeisbot daemon --arm allows it)` before anything else it would have
said, with `; last night: <why it ended>` added when the last heartbeat is `stopped`.
**It has not been seen in a browser** (2026-11-23); its logic has 12 node tests (the `test(` calls
at the start of a line in `dashboard/test/daemonline.test.ts`, counted 2026-11-23).

## Exit codes

| Code | When |
|---|---|
| 0 | the window's work ended for any reason the daemon logs (window closed, `--stop`, one Ctrl-C, nothing to draw, breaker, unusable mirror, two sessions raising, outside the window); also `--status`, `--stop`, `--arm`, `--disarm`, `--task-xml` |
| 2 | not started: not armed ([arming](#arming)). Said in the log and on the console; no lock taken, no database opened, no heartbeat written. Also arming taken away between that check and the night (`NotArmed` from `Daemon.run`), and a start refused by the product's own guard because the process is under a test (`RealProjectRefused`, at the writers' lock or from the night): each logged as `daemon: not started: ...`, with no heartbeat. A command line argparse cannot read exits with 2 as well, with a usage message and no log line |
| 1, with a message | not started: a window that cannot be read, `--task-xml` with `always`, a marker left by a killed mutation run, or the lock file or data directory could not be opened (that last one is also logged) |
| 1 | not started: the writers' lock was held by another command until the window closed (at once with `always` or outside the window), or the database could not be opened; said in the log |
| 1 | ended by a fault caught in `daemon.command`; the traceback is in the log |
| 130 | ended at once by a second Ctrl-C |
| 3 | the last resort: a stop not obeyed for 20 minutes (`os._exit`) |

A kill has whatever code the killer gives it.

## Before the first night

None of these has been done (2026-11-23). Each is the user's call, and **step 3, arming, is the
user's alone**: an agent does not run it even when asked to "start the daemon" in passing; it asks.
The same steps, with the commit decision and the other things that wait on the user, are one ordered
list in [status](status.md#the-users-next-steps-in-order).

1. **Run `oeisbot sync` once by hand.** The mirror was last synced 2026-09-17 (`meta.synced_at`
   `2026-09-17T18:31:41+00:00`, commit `9566689`; read from the database and `git rev-parse` on
   2026-11-23), and by the build notes (`data/item58/slice3.md`) the fetch-and-reset path has never
   run on this mirror. Doing the first one at a console means a person sees it. Run it with the pull,
   not `--no-pull`: only a pull writes `meta.pulled_at`, and until that key exists a `--no-pull` sync
   moves `synced_at` and would make the old mirror look fresh to the daemon. Until a pull succeeds,
   the stale-mirror rule also keeps the daemon at `base`.
2. **Check the disk.** The daemon pauses under 10 GiB free on the data drive. `C:` had 31 GB free on
   2026-11-23 (`df`); on 2026-11-18 it was under the sandbox's own 8 GiB reserve.
3. **Arm it: `.venv\Scripts\oeisbot daemon --arm`.** Until this is done every start below, and every
   start by the scheduled task, logs `not started: not armed` and exits with code 2
   ([arming](#arming)). It prints `armed (...\data\daemon\armed): ...`, and `--status` then no longer
   has its `not armed` line. `--disarm` takes it back at any time.
4. **Run it once in the foreground** for a short window and watch it:
   `.venv\Scripts\oeisbot daemon --window HH:MM-HH:MM`, then `--status` from a second prompt, then
   `--stop`. Check the log in `data/daemon/` and that the stopped run's row says `interrupted`.
5. **Restart the dashboard server** (port 8765) so that it has `/api/daemon`, and look at the line.
   Against a server started before item 58 the line reads `Daemon status unavailable`.
6. **Write and import the task** as above and check "Allow wake timers". The sandbox has only ever been used
   from an interactive session; the plan (`data/item58/plan.md`, A5) is to run `tests/test_sandbox.py`
   under the task before trusting it, and that has not been done. The task may be imported before
   step 3: unarmed, it only writes its one log line a night.
7. Know that the first night's Pick-map snapshot is taken at `base` budgets (60 s / 1,800 s) while
   snapshot #1 was taken at the defaults (60 s / 10,800 s), so the map shows its budget-change notice
   once.

## Constants

All in `oeisbot/daemon.py` unless another module is named. Values read from the code on 2026-11-23.

| Constant | Value | What it sets |
|---|---|---|
| `TIERS` | `base` 60 / 1800, `verify600` 600 / 1800, `long` 600 / 10800 | the ladder, verify / extend seconds |
| `DEFAULT_WINDOW` | `22:00-08:00` | the window when none is given |
| `COOLDOWN_DAYS` | 14 | how far back the cooldown looks |
| `STALE_SYNC_DAYS` | 7 | mirror age past which it does not climb |
| `SESSION_PICKS` | 25 (`Budgets.session_attempt_cap`) | picks per session |
| `DISK_MARGIN_BYTES` | 2 GiB | free disk kept beyond the sandbox's 8 GiB reserve |
| `RAM_MARGIN_BYTES` | 1 GiB | free RAM kept beyond the sandbox's 3 GiB reserve |
| `PAUSE_S` | 600 s | between looks at a machine that is short |
| `MACHINE_FAILURES` | `launch_error`, `disk_cap`, `harness_error`, `bfile_error` | what the breaker counts |
| `BREAKER_RUN` | 5 | such picks in a row that end the night |
| `ERROR_RUN` | 2 | sessions raising in a row that end the night |
| `DAEMON_ERROR` | `daemon_error` | the skip reason for a pick whose session raised |
| `POLL_S` | 1 s | how often the stop request and the window are looked at |
| `HEARTBEAT_S` | 30 s | the longest gap between heartbeat writes |
| `PICK_SLACK_S` | 300 s | added to three verify budgets in the start gate |
| `SYNC_TIMEOUT_S` | 600 s | each git command of the sync |
| `STOP_GRACE_S` | 1,200 s | after a stop, before the process ends itself |
| `SCRATCH_ORPHAN_AGE_S` | 21,600 s (6 h) | age at which a run directory is swept |
| `oeisdata.STALE_GIT_LOCK_S` | 300 s | age at which a git lock file is removed |
| `LOCK_RETRY_S` | 60 s | between the daemon's tries for the lock while another command holds it |
| `lock.ACQUIRE_TRIES`, `ACQUIRE_PAUSE_S` | 5, 0.05 s | tries before a command is refused |
| `lock.PROBE_TRIES`, `PROBE_PAUSE_S` | 3, 0.02 s | looks before `held()` says yes |
| `lock.LOCK_OFFSET` | 2^30 | the byte locked on Windows |
| `daemonline.NO_STEP_MS` | 4.5 h | no step of the main loop for this long: the dashboard line warns |
| `daemonline.NO_BEAT_MS` | 5 min | a running daemon's heartbeat this old: the dashboard line warns that it may not be current |
