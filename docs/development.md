# Development guide

For people and coding agents changing OEISBot. Read [pipeline](pipeline.md) first for the runtime flow.

## Environment

```
uv venv .venv --python 3.11
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"     # UV_SYSTEM_CERTS=1 behind TLS inspection
.venv\Scripts\oeisbot setup                                      # sandbox runtimes (needed by most tests)
.venv\Scripts\python -m pytest
```

The core package uses only the standard library. The `dashboard` extra adds `fastapi` and `uvicorn`;
`dev` adds those plus `pytest` and `httpx`. Inside the sandbox, programs can import `gmpy2` and `sympy`
(installed into `tools/python` by setup).

## Module map

| Module | Responsibility | Depends on |
|---|---|---|
| `config.py` | paths (`ROOT`, `OEISBOT_HOME`), URLs, model settings, `Budgets` | |
| `cli.py` | argparse commands; imports lazily per command | most modules |
| `setup_tools.py` | download sandbox runtimes, AppContainer grants, create database | `sandbox.windows`, `db` |
| `sandbox/types.py` | `Limits`, `RunResult`, `Status`, callback types | `config` |
| `sandbox/windows.py` | Job Object + AppContainer runner (in use) | `ctypes` |
| `sandbox/posix.py` | `setrlimit` runner (never run) | |
| `sandbox/__init__.py` | picks the backend; `new_scratch_dir`, `runtime_problems` | |
| `runners/py_runner.py` | sandbox-side driver for Python programs (copied into scratch; must stay stdlib-only and self-contained) | |
| `terms.py` | `KnownTerms`, `Program`, b-file formatting | |
| `verify.py` | verification harness: protocol, checks, stop reasons, projections, run log | `sandbox`, `estimate`, `terms` |
| `estimate.py` | cost/memory projection and feasibility (pure functions) | |
| `db.py` | schema, connections, all writes, dead-end and review queries | `config` |
| `ingest/seqfile.py` | parse internal-format entries | |
| `ingest/bfile.py` | b-file fetch/cache/parse, rate-limited HTTP, `known_terms` | `config`, `terms` |
| `ingest/oeisdata.py` | git mirror, candidate sync, program stats | `db`, `estimate`, `seqfile` |
| `select.py` | difficulty, sum tree, candidate pool (with an optional keep-check), weighted pick | `db` |
| `strategies/pari.py` | GP statement parsing, program forms, drivers, the predicate reach bound | `seqfile`, `terms` |
| `strategies/codegen.py` | prompts (classify, the list-or-function question, the `terms(work)` and `members(work)` contracts), the members driver, static checks, generation loop (repeats not run) | `model`, `verify`, `terms`, `db` (which failures repeat) |
| `model.py` | Ollama / OpenAI-compatible client | `config` |
| `attempt.py` | per-sequence orchestration (`pari_plan`), re-check (with retries and pending re-checks), the selection check (`Runnable`), sessions | everything above |
| `artifact.py` | review folders | `verify`, `terms`, `strategies.codegen` (one note prefix) |
| `lock.py` | the writers' lock (history item 58): an operating-system lock on `data/writer.lock` that the commands in `cli.LOCKED` and the daemon hold while they run. `writer` (the context manager; raises `Held` at once), `held` (a probe that creates nothing), `read_owner` (the holder's description, which decides nothing). See [daemon](daemon.md#the-writers-lock) | `config` |
| `daemon.py` | `oeisbot daemon` (history item 58): `Window`, `Tier` and `TIERS`, `start_gate_s`, `Cooldown`, `Daemon` (recovery, the sync, the session loop, machine checks, the circuit breaker, the heartbeat file, stopping), `status` and `describe`, `keep_awake`, `command`. Everything that touches the clock, the disk or the machine is a method of `Daemon` that a test replaces. See [daemon](daemon.md) | `config`, `db`, `lock`, `sandbox`, `select`; `attempt`, `ingest.oeisdata` and `schedule` imported where used |
| `schedule.py` | `task_xml` and `write_task`: the Task Scheduler definition `oeisbot daemon --task-xml` writes to a file as UTF-16, or prints (history item 58). Registers nothing | `config` |
| `guard.py` | the product's own refusal to change the real project, or to contact oeis.org, while it is running under a test (history item 58, section F): `under_test`, `is_real`, `refuse_if_real`, `refuse_network`, `RealProjectRefused`. Called from 15 places, each before a write: `db.connect` (read-write), `lock.writer`, `oeisdata._git` and `update`, `bfile.http_get`, `attempt._save_pending` and `_Attempter.run`, `artifact.write`, and in `daemon.py` `request_stop`, `arm`, `disarm`, `log_to`, `Daemon.run`, `_write_beat` and `sweep_scratch` (counted with `grep "guard\.refuse"` on 2026-11-23). See [the product's own guard](#the-products-own-guard) | the standard library only (not even `config`, on purpose) |
| `pickmap.py` | the Pick map's arithmetic, pure functions: a pick chance (`chances`, the first-draw share `d ** -alpha / Σ`, built from `select.weight`), a difficulty band (`band_of`), the change since a baseline snapshot (`compare`, `baseline`), and why a sequence left the pool (`departure_reason`) | `select` |
| `dashboard/app.py` | read-only API (the Pick map's `/api/pickmap` and its cached live pool included, and `/api/daemon`), serves the built frontend | `db`, `select`, `attempt` (the session pool and the rules fingerprint), `pickmap`, `daemon` (its `status`) |
| `dashboard/` (repo root) | React frontend (Vite + TypeScript); the Pick map is `src/pickmap.tsx` (the page) over `src/treemap.ts` (the layout and colour arithmetic, no React), with its tests in `dashboard/test/` | |

## Invariants

Changes must preserve these. Most have tests.

1. **Nothing submits.** The only oeis.org traffic is GET requests for b-files and entry text, all through
   `ingest.bfile.http_get`, which enforces the 1 request/second limit. Do not add another HTTP path to
   oeis.org.
2. **Untrusted code runs only through `sandbox.run` with `isolate=True`.** That covers every program from
   an entry or a model, in any language. `sandbox.run` reports program misbehavior through
   `RunResult.status` and does not raise for it.
3. **Verification is on (index, value) pairs.** The first emitted index is the first known index,
   indices are consecutive, and no term beyond the known range counts until every known term matched.
4. **Known terms are trustworthy or the sequence is skipped.** The b-file is the source of truth, merged
   with DATA; disagreements, gaps and duplicates raise `InconsistentTerms`.
5. **Held-out known terms stay hidden from the model.** `shown_indices` shows the first
   `min(30, max(3, ⌊0.6 × count⌋), count − 2)` known terms, so at least 2
   (`config.CODEGEN_HELD_OUT_MIN`) are always held out. Sequences with fewer than 3 known terms
   (`config.CODEGEN_MIN_KNOWN_TERMS`) never reach the model. Keep the literal check against all known
   terms and the redaction of held-out values in `describe_failure`: the correct value at a held-out
   index, any program value (in a `wrong_term` or a `bad_index` detail) that equals a held-out term not
   also shown, either sign, and under the list contract any program value at a held-out index or past
   the last shown term. Keep values out of the members driver's errors. A crash's own message and
   stderr tail are not scrubbed (a known limitation), and since 2026-09-25 neither is a `protocol`
   detail, which carries the raw term line: an index longer than `verify.MAX_TERM_FIELD_DIGITS` is now
   refused before the index check, so a program putting a held-out value where the index belongs reaches
   `protocol` rather than the scrubbed `bad_index`. Measured exposure and the reason it was recorded
   rather than fixed are in
   [known limitations](known-limitations.md#term-lines-from-an-untrusted-program).
6. **Every run is recorded** (attempt row + predictions). Every generated program that runs is saved in
   `data/runs/` as it ran (driver included), and every accepted term is logged as it arrives.
7. **A win is re-checked against oeis.org before an artifact or review is created, and is never lost to
   a failed re-check.** A run with new terms is recorded as `recheck_pending` and its result saved to
   `data/pending/` before the re-check starts; only a finished re-check changes that outcome. The sequence
   is blocked while pending. `retry_pending_rechecks` never raises for a single attempt, and resolving an
   attempt must stay safe to repeat (the `.incomplete` marker, `db.record_win`'s single transaction).
8. **The dashboard never writes.** It uses `db.connect(readonly=True)`, and review status changes go
   through the CLI.
9. **Artifacts carry their warnings**: weak verification, rewrites, AI-generated, numbered by the runner
   (a `members(work)` program), hard-coded bounds, and for a model program written after the entry's own
   program verified, a pointer to compare with it. The dashboard's Review inbox repeats them. The
   AI-generated warning depends on the exact strategy string `python:model`: keep it for every model
   program, whatever its contract.
10. **A bound published in an entry's comments is never evidence about a term.** `bounds.applicable`
    reads an unverified human claim. It may be used to stop spending time — that is the whole of the
    [searched-bound check](verification-and-estimation.md#the-searched-bound-check) — and never to decide
    a term's value, to decide its index, or to let a term be reported as new. This is why the check runs
    *after* verification rather than in place of any part of it, why nothing resumes a scan past a
    published bound (`extra.verified_scan_to` records the part that was actually measured), and why the
    check is confined to the predicate form, where a value bound really is a work bound. The stop's
    `detail` must also stay free of any term value: it reaches the model through
    `codegen.slow_program_note`, so naming the rate and the margin beside the bound would let a held-out
    term be recovered by arithmetic (invariant 5).
11. **One writer at a time** (history item 58). Every command that runs programs, rewrites the mirror or
    the runtimes, stores a pool or contacts oeis.org is in `cli.LOCKED`, and `cli.main` takes the
    writers' lock (`lock.writer`) around it; `oeisbot daemon` takes the same lock for its whole window.
    Invariant 1's one request per second is a per-process limit, so it holds across processes only
    because of this. **A new command must be classified**: `tests/test_lock.py` lists every subcommand
    as locked or not and fails when one is in neither list. The lock is the commands', not the
    library's: a script that calls `attempt.run_session`, `verify.run_attempt` or `bfile.fetch` directly
    must take `lock.writer` itself ([known limitations](known-limitations.md#the-daemon-and-the-writers-lock)).
12. **A run its caller interrupted retires nothing** (history item 58). `verify.Stop.INTERRUPTED`
    (`db.INTERRUPTED`) is outside `db.DETERMINISTIC_FAILURES`, is matched by no clause of
    `db.is_dead_end`, is left out of `select.candidates`' failure penalty, and is not held back by the
    daemon's cooldown. An unattended loop stops runs every night for reasons of the clock; if any of
    those four ever counted such a row, the daemon would wear down its own pool. Tested in
    `test_db.py`, `test_attempt.py` and `test_daemon.py`.
13. **No test reaches the real database, the real mirror or the network** (history item 58). Two
    layers enforce it, and it holds exactly as far as they reach. **The wall** (`tests/conftest.py`):
    in every test, in the test's own process, `db.connect()` of the real database file for writing,
    `oeisdata._git` and `bfile.http_get` raise `ReachedTheRealProject`, and the writers' lock and the
    daemon's directory are moved away from the real `data/`. A test that needs one of them replaces it
    with its own. **The guard** (`oeisbot/guard.py`, section F of the item): the real functions
    themselves, in any process whose environment has `PYTEST_CURRENT_TEST`, or `OEISBOT_UNDER_TEST`
    set to anything but nothing or `0` (`tests/conftest.py` sets it to `1` on its first lines, so it
    covers import and collection time too, and every child process inherits both), raise
    `RealProjectRefused` before writing inside this installation's `data/` or `artifacts/` through any
    of the 15 guarded calls (the database opened for writing, the writers' lock, git on the mirror and
    the mirror's update, a stop request, arming and disarming, a daemon night with its log, heartbeat
    and scratch sweep, a run log, a pending win, an artifact folder) and before any request through
    `bfile.http_get`. Do not bypass either layer, and do not remove either variable from a test's
    environment; `tests/test_isolation.py` tests the wall and `tests/test_guard.py` the guard. See
    [the test wall](#the-test-wall) and [the product's own guard](#the-products-own-guard).
    **Outside both, and kept out of the real project only by how the tests are written**: a direct
    `sqlite3.connect`, `urllib`, `subprocess` or file call that goes through none of the guarded
    functions; the b-file cache and anything else under `data/` not named above; the model server;
    `tools/`, which is not `data/`; `data/scratch`, which sandbox tests use on purpose; and reading,
    which neither layer refuses. The list is in
    [known limitations](known-limitations.md#the-safeguards-against-reaching-the-real-project).

## Tests

**The numbers on this page are checked by `tests/test_docs.py`, not maintained by hand.** The test
total, this table's "Test functions" column and the collected-counts paragraph below are all compared
against what pytest collected in the same run, so adding a test fails the suite until the docs catch up.
Get the new values from `python -m pytest --collect-only -q` rather than editing them by guess. The same
holds for `check_docs.py`'s expected-hits count, which it now checks itself.

`python -m pytest` runs 903 tests in about 100 s. Tests that need the sandbox runtimes are marked
`sandbox` and are skipped automatically when `oeisbot setup` has not been run (`runtime_problems()`).
The `network` marker is declared but unused: tests stub out network calls.

### The test wall

`tests/conftest.py` does two things before it imports anything from `oeisbot` (section F of item 58):
it sets `OEISBOT_UNDER_TEST=1` in the environment, because pytest's own `PYTEST_CURRENT_TEST` exists
only while a test runs and code at import or collection time (a module-level call in a test file, a
parametrize list built by calling the library) would otherwise run with neither the wall nor the
guard; and it refuses to run the suite at all (`pytest.UsageError`) while `MUTANT_IN_TREE.json` exists
at the repository root, unless `OEISBOT_MUTATING=1` says this run is the mutation harness's own
([below](#mutation-sets-for-item-58)).

It then has three autouse fixtures. One lets Starlette's test client through the
dashboard's Host check. The other two are history item 58's, and exist because `oeisbot daemon` is a
command that, run for real, pulls the mirror and writes the database:

- **`_no_test_reaches_the_real_project`**: in every test, `db.connect()` raises `ReachedTheRealProject`
  when asked to open the real database file read-write (however its path is spelled; read-only is
  allowed, and nothing does it), `oeisdata._git` raises it for any call, and `bfile.http_get` raises it
  for any URL. A test that needs a database passes its own path or replaces `db.connect`; one that
  syncs replaces `oeisdata._git`; one that fetches replaces `bfile.http_get`. Moving `config.DATA` or
  `config.DB_PATH` alone was never enough, because `db.connect`'s default path is bound when the module
  loads. That gap is what the incident of 2026-11-22 went through
  ([status](status.md#history-condensed), item 58).
- **`_no_test_takes_the_real_writers_lock`**: `lock.directory` and `daemon.daemon_dir` point at a
  temporary directory unless the test has moved `config.DATA` itself, in which case they follow it. So
  no test takes, or is refused by, the real `data/writer.lock`, and no test can leave a stop request in
  the real `data/daemon/`.
- **The `real_git` fixture** (not autouse) hands a test `oeisdata._git` as it really is, for testing
  the function itself (the time limit, ending the helpers). Such a test must point it at a command of
  its own, never at the mirror: the four that use it in `test_ingest.py` replace `git` with a stand-in program.
- **The `real_connect` and `real_http_get` fixtures** (not autouse) hand a test `db.connect` and
  `bfile.http_get` as they really are, past the wall. They exist for `tests/test_guard.py` alone,
  which uses them and `real_git` to test the refusal the product itself makes
  ([below](#the-products-own-guard)). **`real_connect` must always be given a path**: with none it
  means the true database (the default is bound when the module loads), whatever `config` or
  `guard.REAL_DIRS` have been set to. The one test that calls it bare stubs `sqlite3.connect` first.

`tests/test_isolation.py` tests the wall itself, including a replay of the incident: `oeisbot daemon
--window always` with nothing stubbed must first do nothing at all because it is not armed (exit
code 2, `not started: not armed` in its log), and then, armed in the test's own directory, stop at the
database wall (the refusal in its log, exit code 1) without starting a night. **Do not
weaken or bypass these fixtures to make a test pass.**

### The product's own guard

`oeisbot/guard.py` (history item 58, section F, 2026-11-23) is the same refusal as the wall, made by
the product itself. The wall is replaced functions in the test's own process, so a child process, or
a test that reaches the real function some other way, walks past it. The guard is inside the real
functions and goes wherever they are called.

**"Under a test"** (`guard.under_test`) is true when the environment has `PYTEST_CURRENT_TEST`, which
pytest sets for the length of each test and every child process inherits, or when `OEISBOT_UNDER_TEST`
is set to anything other than nothing or `0`, spaces around it ignored (`1`, `true` and `yes` all
count: a safeguard that needed the exact spelling would be one typo from being off). The second is
for whatever is not inside a running test: the suite at import and collection time (`conftest.py`
sets it), a mutation harness (`mutate.py` passes it to its test runs), an experiment, a reviewer's
probe. Either one alone is enough.

**"Real"** (`guard.is_real`) is a path that, once resolved, is this installation's own `data/` or
`artifacts/` or anything inside either (`guard.REAL_DIRS`). **It is decided from where the package is**
(`guard.INSTALL_ROOT`, the parent of the `oeisbot/` directory `guard.py` is in), **never from
`config`**: a test that points `config.DATA` at a temporary directory, and a child process given its
own `OEISBOT_HOME`, write where they like, and moving `config` does not move what is real. A relative
path is judged by where it leads; another letter case, `..` and a Windows `\\?\` or `\\.\` prefix
(which `resolve` keeps) are seen through. **A path that cannot be resolved is taken as real**: the
question is asked only before a write, and the answer that refuses is the safe one.

**What is guarded.** Fifteen calls, each before the step that would change something (read from the
code on 2026-11-23, `grep "guard\.refuse" oeisbot`):

| Function | Refused under a test when | What it says it refused |
|---|---|---|
| `db.connect` (not `readonly=True`) | the database path is real | `opening the database for writing` |
| `lock.writer` | the lock file's path is real | `taking the writers' lock` |
| `oeisdata._git` | its `cwd` is real, or with no `cwd` (a clone) `config.OEISDATA` is | ``running `git <first two arguments>` on the mirror`` |
| `oeisdata.update` | `config.OEISDATA` is real; asked before it removes old git lock files, not only at git | `updating the mirror` |
| `attempt._save_pending` | the pending file's path is real | `saving a pending win` |
| `attempt._Attempter.run` | `config.DATA / "runs"` is real; asked before the directory is made | `writing a run log` |
| `artifact.write` | the artifact folder is real | `writing an artifact folder` |
| `daemon.request_stop` | the stop file's path is real | `leaving a stop request for the daemon` |
| `daemon.arm`, `daemon.disarm` | the armed file's path is real | `arming the daemon`, `disarming the daemon` |
| `daemon.log_to` | the log's directory is real; asked once, when the logger is made | `writing the daemon's log` |
| `Daemon.run` | the daemon's directory is real; asked first, before arming is | `running a daemon night` |
| `Daemon._write_beat` | the heartbeat's path is real | `writing the daemon's heartbeat` |
| `Daemon.sweep_scratch` | `config.SCRATCH` is real (and exists) | `sweeping old run directories` |
| `bfile.http_get` | always (`guard.refuse_network`: no path is asked) | `a request for <url> would contact oeis.org` |

Each raises `guard.RealProjectRefused` (a `RuntimeError`), whose message names the path and says to
give the test a directory of its own. **Reading is never refused**: `db.connect(readonly=True)`,
`lock.held`, `daemon.status` and `read_heartbeat` look at the real project under a test as they do
outside one. Outside a test nothing is refused at all: the two functions return at once, which is how
real use works. In `daemon.command`, as the code reads: a refusal at the writers' lock or from the
night itself is logged as `daemon: not started: ...` with exit code 2 and no heartbeat; one at the database is logged as `the database could
not be opened (RealProjectRefused: ...)` with code 1; and one from `log_to` itself, which is made
before either, is a traceback.

**In an experiment that is not pytest**, set both variables before anything from `oeisbot` is
imported: `OEISBOT_UNDER_TEST=1`, and `OEISBOT_HOME` pointing at a fresh directory. The first makes
the real project refuse; the second gives the experiment somewhere of its own to write. **The reverse
also holds**: a real command run from a shell that still has `OEISBOT_UNDER_TEST` set is refused with
`refused under a test: ...`; unset it, or set it to `0`.

**The two layers, and what each covers that the other does not.**

| | The wall (`tests/conftest.py`) | The guard (`oeisbot/guard.py`) |
|---|---|---|
| Where it is | replaced module attributes (`db.connect`, `oeisdata._git`, `bfile.http_get`) and two redirected directories, in the pytest process, for the length of each test | inside the real functions, in every process whose environment says it is under a test |
| Import and collection time, before any test runs | not covered: the fixtures are not yet in place | covered, through the `OEISBOT_UNDER_TEST=1` that `conftest.py` sets first |
| A child process started by a test | not covered: the child imports the real functions | covered, through the inherited environment |
| The real function reached past the replacement (a reference taken before the test, the `real_*` fixtures) | not covered | covered |
| A script that is not pytest | not covered | covered only if `OEISBOT_UNDER_TEST` is set for it |
| The database | only the real database file itself, opened for writing | any database path inside the real `data/` or `artifacts/`, opened for writing |
| git | **every** call, wherever it would run, so a test cannot fetch from GitHub into a directory of its own either | only a call whose directory is real; git in a temporary directory runs |
| The writers' lock and the daemon's files | moved to a temporary directory, so commands under test work and never meet the real lock | refused if they would be the real ones; nothing is moved |
| Run logs, pending wins, artifact folders, the daemon's log, heartbeat and scratch sweep | not covered | refused if they would be the real ones |
| `bfile.http_get` | every call | every call |

So the wall alone is why a test cannot run a real `git` anywhere, and why a command test that has not
moved `config.DATA` can take a lock at all; the guard alone is what stands at import time, in a child
process, behind a `real_*` fixture, and in front of the files a session and a night write. Neither
covers a write that goes through none of the guarded functions
([known limitations](known-limitations.md#the-safeguards-against-reaching-the-real-project)).

**The rule for a test of a safeguard: never aim it at the real project.** A test that checks a refusal
calls the real function, and if the refusal is ever removed (by a mutant, or by a change) the function
goes on to do the thing. So the thing must be harmless. `tests/test_guard.py` does it with its
`fake_real` fixture: it tells the guard that a temporary directory is "real" (`guard.REAL_DIRS`),
points `config`, the lock's directory and the daemon's directory there, and calls the function at
that; a removed guard then writes into the temporary directory, and the test fails on finding the
file. Only `is_real`, which writes nothing, is asked about the true installation. Where a call has no
path to redirect (`db.connect()` with no argument, `bfile.http_get`, git itself), the dangerous step
is replaced with one that fails the test (`sqlite3.connect`, `urlopen`, `subprocess.run` and
`Popen`) **before** the call.

**Why, three times over** (all 2026-11-22 and 23; the second and third by the build's own note,
`data/item58/safeguards.md`, and the comments in `test_guard.py`). A test that moved `config.DATA`
and nothing else let a mutant start a real night. The first `test_guard.py` aimed at the real paths
behind a list of stubs, one test's list had a gap, and a mutant with a guard call removed wrote a real
`data/daemon/stop` (and, by the order of the mutants, a real `armed`, deleted by the next). And the
first draft of the rewrite declared a temporary directory real and then called `db.connect()` with no
path, which is the true database and which the guard, as told, no longer refused: it was opened for
writing once (nothing in it changed). A list of stubs is only as good as its last entry, and a
stand-in is only as good as every path being pointed at it. The account is in
[status](status.md#history-condensed), item 58, section F.

`tests/test_guard.py` (12 tests) covers: a test is known to be one, by either variable, and which
values of `OEISBOT_UNDER_TEST` count; what counts as real (`..`, relative, letter case, the Windows
prefixes, a sibling name such as `database`, code not being data, `config` moved, an unresolvable
path); nothing refused outside a test; the database refused for writing and not for reading; the
default database path refused whatever `config` says; git (a fetch in the mirror and a clone into it)
and the mirror's update, refused before a stale lock file is removed; oeis.org; the lock, the stop
request, arming, disarming and the daemon's log; a daemon night, its heartbeat and its scratch sweep;
a pending win, an artifact folder and a run log; a child process started by a test refused in a home
of its own that it is told is real; and a child given its own `OEISBOT_HOME` not refused.

### Mutation sets for item 58

`data/item58/mutate.py` (local state, not in git) holds the mutation checks for the daemon work: each
mutant changes one condition, runs the tests named for it, and is restored from the bytes read before
the change, also on Ctrl-C. A mutant survives when those tests still pass.

```
.venv\Scripts\python data\item58\mutate.py slice1          # the stop hooks and selection rules: 29 mutants
.venv\Scripts\python data\item58\mutate.py slice2          # the writers' lock: 16
.venv\Scripts\python data\item58\mutate.py slice3          # the daemon and the git time limit: 107 (data\item58\mutants3.py)
.venv\Scripts\python data\item58\mutate.py slice3 cooldown # only mutants with that word in their name
.venv\Scripts\python data\item58\mutate.py slice4          # the guard and arming: 44 (data\item58\mutants4.py)
```

The runs are in `data/item58/mutation_slice1.txt`, `mutation_slice2.txt` and `mutation_slice3.txt`:
29, 16 and 107 mutants, none surviving (the sets counted from the two files on 2026-11-23, the results
read from the three outputs). Each file is a single run of its whole set; slice 3's is the clean run
of all 107 made after the last fix (the run before it had 2 of 106 not killed: a test the wrong call
could satisfy, and a mutant whose text had come to occur three times and so was not applied; both
were put right first).

**`slice4` is the safeguards' own set** (`mutants4.py`, 44 mutants: `len(SLICE4)` after importing the list, and each name read, 2026-11-23):
14 mutants of `guard.py` (nothing under test, each variable not read, only the exact `1` counting, a
`0` counting, nothing or everything real, `artifacts/` left out, a path not resolved, an unresolvable
path let through, the Windows prefix walking past, each refusal made outside tests too or never), 17
"doors" (each of the guarded calls with its refusal removed, plus a read-only connection refused and
a clone into the mirror not seen), and 13 of arming and the marker in `daemon.py`: 10 of arming (an
unarmed daemon starting from the command, or when built directly, reporting success or not logging,
always armed, arming writing nothing, disarming removing nothing, `status` not saying, an answer that
does not say read as armed, `--arm` going on to start a night), 2 of the marker (a mutant left in the
tree not stopping the daemon, the harness's own marker alarming its own test runs) and 1 of the
last-moment refusal reported as a fault. Every mutant in it
removes or weakens a safeguard, which is safe to run only because the tests named for it never aim at
the real project ([above](#the-products-own-guard)). No mutant in it touches `tests/conftest.py`.
Its run is `mutation_slice4.txt` (dated 2026-11-23 11:55): 44 lines of `killed`, last line `44 mutants,
0 not killed; the real project is as it was`.

**All four sets were run once more on 2026-11-23 under the harness as it now is** (the marker, and the
check of the real project after every mutant): `mutation_slice1.txt` 29, `mutation_slice2.txt` 16,
`mutation_slice3.txt` 107, `mutation_slice4.txt` 44, **196 mutants in all, none surviving**, each file
ending `... 0 not killed; the real project is as it was` (the last line of each read, and the lines
beginning `killed` counted, for this page; the runs themselves were not made by it).

**The harness checks the real project itself** (the function "real_state" in `mutate.py`). Before the first mutant it
records: the size and modification time of `data/oeisbot.sqlite3` and of its `-wal` file; read
through a read-only connection, the row count and highest id of `attempts`, `sessions`, `reviews` and
`pick_snapshots`, every `meta` row and the schema; whether `data/writer.lock` exists; the name, size
and time of everything in `data/daemon/`, `data/pending/`, `data/scratch/` and `artifacts/` (the top
level of each); the number of files in `data/runs/` and that directory's time; and in the mirror's
`.git` the names of the `*.lock` files, the text of `HEAD`, and the times of `FETCH_HEAD`, `shallow`
and `index`. It compares all of it again after every mutant, and at the first difference prints
`STOPPED: THE REAL PROJECT CHANGED during the mutant '<name>'` with what changed, before and now, and
runs no further mutant. A clean run ends `... the real project is as it was`. It does not look at
`predictions` or the pick-snapshot rows, at `data/bfiles/`, below the top level of `artifacts/`, at
`tools/`, or at the network; and it reports a change after the fact, it does not prevent one.

**A killed run leaves a marker** (the same section F). Before it changes a file, `mutate.py` writes a
copy beside it (`<file>.orig`) and `MUTANT_IN_TREE.json` at the repository root, naming the file, the
copy, the mutant and the original's SHA-256; it removes both after putting the file back. Its test
runs carry `OEISBOT_UNDER_TEST=1` and `OEISBOT_MUTATING=1`. If the harness is killed in between, the
mutant stays in the code, and with items 57 and 58 uncommitted `git diff` cannot single it out. While
the marker exists: `mutate.py` refuses to start (`REFUSED: ... exists`), `tests/conftest.py` refuses
to run the suite, and `oeisbot daemon` refuses everything except `--status`
(`daemon._mutant_left_in_tree`: no start, no `--arm`, no `--disarm`, no `--stop`). To recover, restore
the named file from its `.orig` copy, check it against the SHA-256, and delete both. Neither file is
in `.gitignore`. It no longer runs `taskkill /IM pytest.exe` on a slow mutant, which ended every
pytest on the machine; a mutant whose tests have not finished in 240 s is counted as killed.
Unlike item 57's harness, **this one mutates the working tree
itself**, so while it runs **nothing else may read, run or edit the code**: no test run, no `oeisbot`
command, no dashboard server reload, no editor saving a file. A process that imports a mutated module
runs the mutant, and an edit made meanwhile is overwritten when the mutant is restored. No slice-3
mutant touches `tests/conftest.py` (one slice-2 mutant changes its lock-directory fixture, not the
wall), and that wall is what makes running a mutated daemon safe: on 2026-11-22,
before the wall existed, a reviewer's mutant of the daemon's command started a real night from inside
its own test (status, item 58). A mutant whose
tests have not finished in 240 s is counted as killed.

Real timings on this machine are noisy, so tests do not assert on sub-second timings. In 210 runs of a
doubling program through the sandbox (2026-09-19), 64 had a term of 1-140 ms that took 0.2-0.4 s more wall
time than CPU time, and on terms of 0.3-0.8 s wall time was about 1.5× CPU time at the median. A test that
ran the extension on such terms and checked its projections failed about one run in six; the extension's
infeasible stop is now tested in memory with controlled times
(`test_estimate.py::test_extension_stops_when_next_term_is_projected_infeasible`), and in the sandbox only
with no extension time, which no timing can meet (`test_verify.py::test_infeasible_stop_ends_the_sandboxed_run`).
The sandbox tests that check kill thresholds are timing-sensitive but have passed repeatedly on an otherwise
idle machine. Under full CPU load, `test_on_tick_can_stop` (wall time under 3 s) and `test_wall_timeout`
(between 1.4 and 4 s) would likely fail: there a sandboxed run took 2.4-5.2 s from the stop to its end.

Counts are test functions; parametrized cases bring `test_pari.py` to 49, `test_codegen.py` to 89,
`test_attempt.py` to 115, `test_estimate.py` to 29, `test_model.py` to 10, `test_recheck.py` to 39,
`test_replay.py` to 12, `test_heartbeat.py` to 27, `test_runtimes.py` to 24, `test_pickmap.py` to 128,
`test_bounds.py` to 63, `test_dashboard.py` to 61, `test_daemon.py` to 101 and `test_lock.py` to 29
collected tests.

| File | Test functions | Covers |
|---|---|---|
| `test_sandbox.py` | 18 | each sandbox guarantee attacked directly: memory cap (gradual, single huge allocation, swallowed `MemoryError`), wall and CPU caps, child processes, network, filesystem, output flood, disk cap, stop callbacks, kill-on-close, gp inside the sandbox and gp shell-out |
| `test_verify.py` | 36 | the gate through the real sandbox: correct/extended, verify-only, offset error, shifted values, late wrong term, skipped index, crash, float values, early end, verify timeout, gmpy2 values, an infeasible stop ending the sandboxed run (no extension time, so no timing dependence; no new term, no censored time), over-prediction kill on a trusted projection, no kill on an untrustworthy one (where the old rule would have killed), no kill when the seconds per work unit climb 3× per term under a trustworthy cost fit (the rule before offer A would have killed), gp program; and the stderr tail in a detail (`_stderr_tail` keeping the last three lines that say something and dropping gp's caret rule, a line capped at `STDERR_LINE_CHARS`, `brief_detail`'s cut, a `crash` from a non-zero exit including the bare `: ` when stderr is empty, an `incomplete` with and without stderr, a real gp program calling an undefined function end to end, a stop reached with no terms keeping the tail, and a stop outside `_TAIL_STOPS` and one inside it with terms both keeping their detail); the guard at the last known index that no stream can reach, driven by hand, so a run that missed a known term can never be treated as verified; and (item 58) a stop request ending a run as `interrupted` in either phase, winning over a budget that ran out on the same tick, a first stop not overwritten by a later request, no line read once the harness has halted, a real run interrupted through the sandbox, and a `should_stop` that raises ending the run as `harness_error` |
| `test_estimate.py` | 25 | synthetic cost curves: exponential, polynomial, factorial (climbing ratio), odd/even alternation, disagreement, too few points, seconds conversion and budget, memory, search names, open search, int64 bound, cheap sequences; the kill threshold (both sides of its 10 s floor, none on disagreement or on too few points, a trustworthy climbing projection still killed from its high estimate) and session 5's recorded A277532 and A390295 points replayed to their recorded estimates with no kill; the rate drift (A377248's real points: a trustworthy cost fit withdrawn by an 11× drift, the stored flag and its reason; the exact definition and both sides of the factor; exactly the last five fitted points counted, against an independent fit; the CPU unit, steady and starved; the harness, driven in memory, using its budget's kill factor for both the stored flag and the kill); the infeasibility check on time (four untrustworthy projections from the offer-F replay, A274508's a(16), A350878's a(14) and a(15), A265390's a(8), never infeasible at budgets from 1 s to 3 h, each with the reviewer's note when over the budget and a search with none; a trustworthy one, A274508's a(17), still infeasible on its high end with its low end inside the budget, and feasible at a budget equal to the high end; A377248's drift-withdrawn fit still judged on its high end; the harness, driven in memory, running on past an untrustworthy projection and keeping the new term); the extension's infeasible stop, through `run_attempt` with the sandbox replaced by a replay at controlled times (the doubling program's terms each projected exactly, the stop on the line of the last term that fits, at a term the test computes itself, before the next starts, and no censored time); a stored prediction carrying the statistics its verdict was made from: a sound cost fit withdrawn from the kill by the rate drift reading `trustworthy = 0` with `fit_trustworthy = 1`, the disagreement pinned on a series whose newest point disagrees (a perfect exponential has a disagreement of exactly 1.0, so asserting against one would hold for any constant), a climbing fit, and all five values NULL when nothing could be fitted |
| `test_pari.py` | 41 | statement splitting, each program form and rewrite, rejected shapes, programs calling a helper from another OEIS entry (calls and indexes found, bare mentions left alone, every way a name can be defined, strings and comments ignored, the `a(n)` and predicate forms rejected, a helper the block defines itself kept, a call in a dropped driver statement not counted, one rejected block leaving another runnable), all three forms verified and extended in the sandbox, predicate work counts, syntax error, `search_start` equal to the driver's start, the out-of-reach bound (boundary, other forms never bounded, huge values), the real driver's rate on a do-nothing predicate staying below `PREDICATE_MAX_RATE` |
| `test_heartbeat.py` | 20 | the predicate driver's progress heartbeats and what the harness will believe: a frontier that moves on a good line and never halts a run on a bad one; the refusals, each of which would otherwise let a later run skip a range that was never scanned -- no caller gate (a model program printing `@P`), a malformed or over-long line, a position that does not match the work claimed for it, a frontier that moves backwards or stands still or falls behind a term already emitted, and a rate no predicate could be tested at; the ignored count and the first bad line kept so a mangled driver is a number rather than silence; then the real driver in the sandbox -- heartbeats accepted with the block adapting upward, terms byte-identical across block seams at a forced tiny block (the one place the rewrite could duplicate or skip a k), and a frontier that never names a k the driver has not tested; and (item 57) the same identity on a predicate driver's term line: kept, it is a term; broken either way or with no work claimed, a `protocol` stop whose detail holds no digit, decided before the value is compared and measured from the scan's own start; never applied without the caller's gate |
| `test_bounds.py` | 35 | searched bounds in `%C` comments and the skip they trigger, all driven in memory: exact parsing for every base (`Decimal ** int` rounds at 28 digits, so 2^200 and 3^100 were wrong while 2^63 passed), OEIS's notations including `10 billion` and an absurd exponent refused; which claims count (an unindexed bound below the last known term is stale, an indexed one counts only for the next unknown index, one beyond it is not used); the two guards that cost the census its only wrong skips (a bound borrowed from another entry's sentence, a claim qualified to a subset of terms) with the entry's own A-number not tripping the first; the six phrasings that were being missed; an interjection forbidden from bridging two clauses; the loose `searched to` pattern deliberately absent; and the check itself -- fires out of reach, does not fire inside it, and can never fire on a zero work count (the a(n)/print-loop drivers hard-code `work` to 0), a zero extension budget, a collapsed measurement window or a stale bound; then what the stop means downstream: a verified run with no new terms, not a dead end, a detail that leaks no held-out term value, and a 10^5000 bound surviving JSON and the detail; and (item 57) factorials (`31!`, never `!=`, `!!` or a divided one, capped at `10000!`, and a factorial mark that must not end the sentence for the borrowed-bound guard), every number word from `thousand` to `decillion`, `are the only terms [known] up to X` in its strict form alone (no verb, a word before the connective, a qualifier after the number, a number from the next sentence and run-together words all refused), and the measured false-positive shapes (`checked up to`, `none found up to`, primorials) pinned as unread |
| `test_codegen.py` | 48 | a run that produced no term naming the program it ran and no run log; code extraction, plan parsing, static checks, holdout in the prompt, at least 2 terms held out at every size, copied-term rejection, fixed-bound flags, redaction of held-out values, retry with the real error then success (scripted fake model, asserting the stop-specific guidance reaches the model), guidance per failure type, host conditions not blamed on the program, every retryable `Stop` classified, `API_HINTS` names checked against the sandbox interpreter, generation cap, too few known terms never reach the model, no runnable code, an unreachable model, model skip; the list contract (the form question asked only for strictly increasing known terms, its parse defaulting to function, `members(work)` only for a list whose terms increase, the classify and `terms(work)` prompts unchanged, the static check and extraction per contract (the name `terms` refused at module level in 13 forms, a local of that name allowed, an unfenced program still extracted), the prompts for a function word for word the old ones, constant expressions such as `10**7` or `10**4 - 1` as fixed bounds, code too deep to parse rejected and a deep expression unable to crash the stage, no held-out value in any list prompt (a program value past the last shown term included, in retries and repeat messages), the driver numbering from offsets -2, 0, 1 and 5 and ending a lower, equal or paired value as `protocol` without naming a value, every new term voided when members arrive out of order after verification (and standing after any other error), a value too long to print never shown, and a `members(work)` win end to end: `python:model`, the AI-generated and numbered-by-the-runner warnings, `executed.py` and the run file holding the driver, the run file's bytes hashing to `program_sha`); repeats (not run after each deterministic failure or a `verify_timeout`, caught with comments and layout changed, when not the latest and when it first failed in generation 2, counted as a generation, the message and both guidance texts reaching the model; run again after each other failure); no retry showing a program value that is a held-out term, under `terms(work)` too (a shown and a held-out index, a `bad_index` index, the sign flipped as in attempt #105 under both contracts, long values matched as printed, a value that is also shown kept, through the loop); and (item 58) an interrupted run ending the model stage without a retry, and the stage asking the caller before each model call and before each run |
| `test_ingest.py` | 23 | entry parsing, signed data, program splitting, b-file parsing, known-term merging and conflicts, LFS-pointer cache logic (and `bfile.cached` agreeing with it offline, with and without a mirror), an HTML page instead of a b-file, keyword filtering (`fini,more` kept, `full`/`dead`/`dumb`/non-`more`/no-DATA dropped), `sync` writing candidates and clearing `in_more`, sum tree sampling, weighted pick, difficulty features, `sync` keeping the difficulty the stored b-file facts imply (and not falling back to the entry-only score); and (item 58) git under a time limit, with a stand-in program for `git` (the `real_git` fixture): a stalled git ended together with the helper it started, output and a failing exit still reported, a git in hand ended from another thread; `update` passing the limit on and removing only lock files old enough, a failed reset undone before its error goes on, and a mirror that cannot be put back raising `MirrorUnusable` (never for a sync without a time limit); git started without a console window; and only a sync that pulled writing `meta.pulled_at` |
| `test_model.py` | 5 | the model client with a stubbed server: the Ollama and OpenAI request/response shapes, `ModelUnavailable` when nothing answers, and `available()` against a model listing (exact name, name before the tag, missing model, empty listing, dead server) |
| `test_db.py` | 25 | WAL + read-only reader, attempt and prediction rows, dead ends, infeasible dead ends only without a bigger budget, a used-up extension as a dead end only without more time (never with new terms, without stored budgets, on a starved CPU or for `over_prediction`; memory not compared), verify timeouts as dead ends up to the time already spent (the sandbox's `timeout` never), `record_win` rolls back as a whole, pool leaves out sequences only the model could attempt but would refuse, the failure penalty counting attempts, not rows (one attempt's rows once; a verified row alone; attempts with only wins, superseded runs or skips not at all; a row without a key, or with an unreadable `extra`, on its own; the ×64 cap), a run squeezed for memory not retired (the infeasible dead end keys on the cap the run was judged against, not the one it asked for; and a row with budgets but no stored cap -- the shape of every row written before 2026-09-20 -- never counting), `refresh_difficulty` rescoring every row including one that has left `more`, double-submit guard, session roll-up, the cost fit's statistics stored as written and all five NULL together when there was no fit (so `int(None)` can never raise and a missing fit can never read as a negative verdict); and (item 58) a `verify_timeout` starved of CPU not a dead end (judged against the verify budget asked now), an interrupted run never a dead end and adding no failure penalty, and a sequence with a rejected review not drawn |
| `test_attempt.py` | 99 | orchestration with stubbed network: win with artifact and review (and stored budgets), superseded run, dead end not repeated, a used-up extension not run again without more time (end to end through the sandbox, the selection check agreeing) and not holding back the entry's other programs (in a later attempt the others run in order, a failing one not stopping the next, and one wins; the sequence stays in the PARI-only pool; for an `infeasible` dead end too), nor does a program broken after verifying, each per-sequence gate recording a skip and running nothing (entry missing, `more` gone, b-file lookup failing, b-file disagreeing with DATA), an infeasible dead end run again under a bigger budget, `too_few_known_terms` recorded after a failed PARI run, re-check error retried in place, unreachable re-check kept pending (blocked from attempts and picks) and later resolved as a win or as superseded, Ctrl+C during the re-check leaves a resolvable pending win, non-network errors not retried, a win surviving a failed save, pending retries surviving an unreadable saved result (inside a session too), a foreign artifact folder and a failed database write; an out-of-reach predicate never run (and still handed to the model), dead ends checked before reach and the skip reason each combination records, a verified PARI program or a win stopping the other PARI programs while a failed one does not, the model tried after a verified-but-unproductive PARI run in this attempt (its note surviving truncation and retries, no held-out value in any prompt, the reviewer warning on the winning generation's README) or in an earlier one now a dead end (infeasible or a used-up extension; and never from a dead end that did not verify or that found new terms, so no held-out value can reach the prompt), a verified run with too few terms for the model, an empty b-file falling back to DATA, new PARI terms keeping the model away whatever the re-check says, and the selection check (leaves out each unrunnable kind, keeps them for the model or names `too_few_known_terms`, uses the cached b-file, keeps what the attempt's gates decide, leaves out and reports what would stop a session, uses the session's own budgets, `queue`/`pick` showing the session pool); every row of an attempt carrying one `attempt_call` (a failed PARI run and a model generation counted as one attempt, a second attempt as another; the key on a win's row from `recheck_pending` to `extended`, and surviving `retry_pending_rechecks`); a session saying when `-n` is capped (picked or listed) and staying quiet when it is not; a run held below its memory budget by free RAM recording the cap it got; a pending win counting how often it has failed the same way, the count reset by a different error, the counter's own database failure not costing the win, and six shapes of a hand-edited `extra` (an array, a string, a number, unparseable text, NULL, and an object whose counter cannot be added to) each leaving the session running and the win pending; a session recording which gp produced its rows (the short token in `sessions.note` beside the settings it already carried, the full banner in `meta`) and still running, and still finishing its session row, when the version probe raises; and the pool snapshot a session stores for the [Pick map](dashboard.md#pick-map): the pool it drew from already stored when the first pick starts (with the session, the budgets and the rules fingerprint it was built under), an unchanged pool storing nothing new, a session given its own list of sequences storing none, the model pool kept apart from the PARI one and holding what only the model can take (an empty pool stored as a pool), the pool built once and that same pool stored, the stored rows being exactly the `(a_number, difficulty)` pairs of the pool the session drew from and never the weights, `session_pool` weighing every candidate by its difficulty to the power of minus alpha at alphas 0, 1 and 2 with `run_session` passing its own alpha on, a snapshot that cannot be written or whose write raises (a disk error, a refused transaction, an unknown pool, an integrity error) costing the session nothing and logging one line, `snapshot_pool` reporting `None` for an unchanged pool, and `oeisbot snapshot` storing the PARI pool, with `--all` the model's too, and naming the right pool in each message; and (item 58) stopping on request: an interrupted extension recorded and retiring nothing, a stop between two programs starting no other and recording no skip, a stop keeping the model stage from starting (after the last PARI program too) and one during it recording no skip, an attempt that was already complete not called interrupted, a model that goes away while stopping recording no false skip, an interrupted run starting no other even if the request is withdrawn, new terms found before a stop still a win; the session's hooks: the note naming its budgets and the caller's note, `keep` holding candidates back while the whole pool is stored (and not asked about a caller's own list), `may_start` and `should_stop` asked before each pick in that order with the unstarted picks counted, `before_attempt` called before each pick with any fault in it survived but Ctrl+C not swallowed, a callback that raises still closing the session, `snapshot=False` storing none; `offline_known_terms` being what selection uses; and two tests that drive the real daemon through the real sandbox: sessions end to end, and a real run interrupted when asked |
| `test_recheck.py` | 17 | the re-check verdicts against a stubbed oeis.org (still new, `more` removed, overlapping terms, a disagreeing value, a live b-file that already has them, an unreadable entry, an entry without terms), and `oeisbot recheck` (nothing pending, then a pending win it cannot load: message and non-zero exit); the saved pending win as JSON: a round trip keeping the program sha, both enums, int-keyed known terms and a 1268-digit term, an artifact rebuilt from the reloaded result byte for byte, the file written as bytes with a `format` version, and a loud error for every field that no longer matches the code; and the artifact's own files: `predictions.csv`'s header lining up with its rows, and the b-file ending with the blank line OEIS requires while the README's new-terms fence does not; and (item 57) `oeisbot recheck --release`: a win whose saved result is gone or drifted is released to `verified` with the reason and time recorded and the file kept under another name, a win that still loads or whose file cannot be opened is refused with nothing written, a row that is not pending is refused in the code and in the UPDATE itself, an `extra` of any shape survives, and the run log is not promised unseen |
| `test_docs.py` | 3 | The documentation's own numbers against this run's collection: the test total in its eight places, the per-file table's function counts, and the collected-count paragraph (including that a parametrized file is not missing from it). Skips on a partial collection, and fails loudly if a sentence it checks is reworded away rather than going quietly dead. `status.md`'s history section is excluded: a number inside a history item is that session's own record |
| `test_replay.py` | 5 | `scripts/replay_predictions.py` against a synthetic database whose `predictions` predates the fit columns: a clean replay backfills, the write is idempotent (turning on a row with no cost fit, where all-NULL is both the correct answer and indistinguishable from unwritten), a disagreement blocks it, a failure part way takes the `ALTER` with it, and each of eight ways a row can fail to replay -- missing log, unreadable or non-object `extra`, no `sequences` row, wrong program sha, wrong known-term count, a log truncated past the projection's own term, and one log named by two attempts -- is reported, counted apart from the rows that reproduced, and refuses the write |
| `test_dashboard.py` | 24 | every endpoint, artifact file confinement, API never writes (every database connection an endpoint opens is read-only, `/api/pickmap` for both pools included, and the file's mtime does not move); since item 56 also what a win is (a rejected and a refused win counted nowhere: summary, per-day, per-session, the attempts flag), the bounds on `alpha`, the limits and the review id, attempts' `total` and the `none` reason, the estimator's `finished` flag, a row whose `extra` is not JSON, the page served at `/` only, the Host header (parsing, refusal, what `oeisbot dashboard --host` allows and a wildcard turning the check off), other pages' requests refused, and `nosniff` on every response, a 500 included; and (item 57) the estimator sends the cost fit's own verdict and the rate drift, and the attempts table says which review refused a run, whatever shape the record has (a JSON `true` is not review #1), never for a run that is not `extended`, and with an `extra` that is not JSON; and (item 58) `/api/daemon`: answering from the lock and the heartbeat (nothing, a killed daemon's leftovers, a running daemon, another command), writing nothing, needing no database, and keeping the host and other-page refusals |
| `test_pickmap.py` | 101 | (Item 58 added: a rejected review explaining a departure as an open one does, an interrupted run never named as why a sequence left, and one that had found terms still named.) The Pick map, in three layers. The pure comparison (`oeisbot/pickmap.py`): a difficulty on a band edge in the band above, chances that are first-draw shares agreeing with what the session draws with, the baseline being the newest snapshot that is not the live pool, the ratio being a candidate's share among the sequences common to both pools (one failure showing as about a half and everyone else about one, a newcomer not moving the survivors against each other, `p / p0` equal to the ratio, the masses summed exactly wherever the set of common names puts a big share, the ratio independent of the order the pool was listed in), a row in the band of its difficulty now, those who left listed heaviest first, a chance that underflows giving no ratio instead of dividing by zero, and `departure_reason` in its fixed order. The snapshot tables (`db.record_pick_snapshot`): a snapshot with its rows and what built it, the digest ignoring order and seeing the last bit of a difficulty, an equal pool refreshing the stamp and storing nothing, retention per pool from the config, a failed write leaving the old state, the write lock taken before the pool is compared, writers racing, a connection already in a transaction refused, a database from before the tables gaining them at its next write open, a reader saying so when they are missing, cascade delete; the budgets JSON and the rules fingerprint (stable, `unknown` rather than raising, moving with the source of each function, class, module and constant it is made from, and not with a checkout's line endings). `/api/pickmap`: every candidate largest first, alpha validated and the frontend's limit equal to the server's, the pools separate, the map answering without the snapshot tables and not creating them, the baseline and "nothing to compare with", new candidates and departures with the reason the database gives and only the ten largest listed, names cut, a pool built under other budgets or rules said so, the live pool built once until the database moves or a rebuild is asked for (its time to live, the budgets it is asked under, the generation counter, concurrent requests sharing one build, a build that failed an error and not a stale map, the stamp of what the build read), the warm-up, and the whole thing over the real session pool |
| `test_daemon.py` | 86 | (Section F added five, the fifth being a refusal at the last moment, disarmed between the command's check and the night or refused by the guard, reported as a refusal with exit code 2 and no heartbeat, not as a fault; the other four: an unarmed start doing nothing at all, exit code 2, one log line, no lock, no database and no heartbeat, with `--status` and `--stop` needing no arming; arming as one command that starts nothing and can be taken back, `--disarm` saying when it was not armed and that it does not stop a running daemon; arming outliving a night and a recovery; and a mutant left in the code stopping the daemon from starting, arming or disarming while `--status` still answers. The `home` fixture arms, as the user must.) `oeisbot daemon`, in memory with a fake clock, machine, pool and session (history item 58): the window (parsing, what is refused, closing over midnight and inside a day, real seconds on a night the clocks change), the start gate and the tiers; the cooldown rule by rule (never attempted, retired nothing, retired a program, smaller budgets, a row with no budget, only the most recent attempt, a changed entry, cut short, a skip until the next sync, a `daemon_error` skip whatever syncs, rows of any shape); a night (outside the window, one sync then sessions, a failed sync, an unusable mirror, a stop request and a stale one, the window closing during a pick, `always`, an exhausted tier costing no session row, no climbing on a stale mirror, a rebuild of the table from an old mirror not making the mirror new, the count of reviews waiting said in the log and the heartbeat, the pool and cooldown built for the tier being run); the machine (disk and RAM pauses, the one pause after a session cut short, the breaker counting picks across sessions since this start, an ordinary failure breaking the streak); sessions that raise (one sequence charged, a fault between picks charged to nobody, two in a row ending the night, a session that starts nothing); a win cut short said in the heartbeat; recovery (orphan sessions closed at their last row's time, only old harness-named run directories swept, an unreadable scratch directory survived, a pending win without its file); the heartbeat (contents, `progress_at` moved only by the main loop, a failed write said once per streak, one writer at a time, two threads never leaving a broken file); `status` asking the lock, `describe` in each state; the watcher thread (seeing a stop by itself, keeping the heartbeat moving, ending the process after an unobeyed stop and ending git first, outliving a fault); and the command (`--stop` and `--status` only asking, one window under the writers' lock, Ctrl+C once and twice, a fault's traceback in the log with exit code 1, a bad window refused, a start that finds the lock held waiting while the window is open and saying so in the log when it cannot get it, a database that cannot be opened said in the log, a log line the console cannot show, the CLI not locking around it, `keep_awake` asking for the system only) |
| `test_lock.py` | 18 | the writers' lock (history item 58): free until taken and after; a probe creating nothing; a second writer refused and told who holds it; released when the body raises; a stale description not a held lock; a holder that cannot describe itself not leaving another's name; an unreadable description still refusing with a plain message; the file readable while held; a writer waiting out the instant a probe takes, and two probes not reporting a holder; **in real processes**, a killed holder releasing the lock and processes racing for a lock file that does not exist yet; every locked command refused before it starts while another runs; the locked and unlocked command lists together being every subcommand; a reading command never refused; the lock let go however the command ends; only a failure to take the lock becoming a message; and no test taking the real lock |
| `test_schedule.py` | 5 | the Task Scheduler definition (history item 58): it wakes the machine and sets no time limit, starts when the window opens whatever the window, points at this installation by default, is printed with nothing started, and names a command that exists |
| `test_isolation.py` | 5 | the test wall in `tests/conftest.py` (history item 58): the real database cannot be opened for writing however its path is spelled, a test's own database opens as ever, git and oeis.org are out of reach, `oeisbot daemon` with nothing stubbed does nothing while unarmed (exit code 2) and, once armed in the test's own directory, stops at the database wall (the 2026-11-22 incident replayed), and the daemon's own files are not the real ones |
| `test_guard.py` | 12 | the product's own guard, `oeisbot/guard.py` (history item 58, section F), called through the real functions past the wall and never aimed at the real project: a temporary directory is declared "real" and each function pointed there, so a removed guard writes into it and the test fails on what it finds. A test known to be one by either variable; what counts as the real project, decided from the package's place and not from `config`, however the path is spelled; nothing refused outside a test; the database refused for writing and not for reading, and the default path refused whatever `config` says; git and the mirror's update; oeis.org; the lock and the daemon's stop request, arming, disarming and log; a daemon night, its heartbeat and its scratch sweep; a pending win, an artifact folder and a run log; a child process started by a test refused too; and a child given its own `OEISBOT_HOME` not refused |
| `test_runtimes.py` | 17 | runtime provenance (`setup_tools.runtime_versions`): the gp probe reading **stderr** and not stdout (both directions, because reading stdout records an empty string and nothing says so), the whole banner kept on one line rather than a fixed number of lines (so the `compiled:` line, the only thing telling two builds of one version apart, survives a reordering), and every way a probe can fail to be trustworthy -- a non-zero exit, no output, exit 0 from something that is not gp, a missing binary -- yielding `unknown`, with the exit-zero case proved to be exit zero so it cannot pass on the wrong reason; every error shape swallowed but Ctrl+C deliberately not (`except Exception`, so `oeisbot run` stays interruptible during the probe); a wrapper printing a warning before a real banner accepted, but one whose preamble runs past the cap **not** accepted, because the guard is checked on the value that is stored and not on the full text; the cap cutting at a word boundary, so a version number straddling the limit becomes an honest `unknown` rather than a truncated, plausible, permanent one in a session note; the configured binaries probed rather than a PATH lookup, with `-f`, `stdin=DEVNULL`, an explicit encoding and the timeout all pinned; the short `gp=2.17.4/GMP-6.1.2` session token including a non-GMP build and both unknown forms; a `meta` round trip, which nothing had tested before; and the banner fixture asserting its own shape, because written with a literal backslash-n it is one line, every collapsing assertion holds vacuously, and a "first three lines" driver passes the whole file -- which is what happened until the audit caught it |

**The frontend has two checks of its own, and `pytest` runs neither.** `npm run build` type-checks `src/`
(`tsc --noEmit`) and nothing runs the code. `cd dashboard && npm test` (`node --test "test/*.test.ts"`,
about a second) runs 92 tests in five files (history item 56 added two, item 57 the fourth, item 58 the
fifth; the 92 is the count of `test(` calls at the start of a line in the five files on 2026-11-23, 80 before item 58;
item 58's final audit records 91 passing, `data/item58/final_audit.md`, and the 92nd, the not-armed line, was added after it: `data/item58/safeguards.md` lists "92 node tests" under its checks, and the node tests were not run for this page): 12 in `test/daemonline.test.ts` against `src/daemonline.ts` (what the
daemon's line under the header says and in which tone, and that not armed is said first), 12 in
`test/tabs.test.ts` against `src/tabs.ts` (the arrow keys along a row of tabs, the two-tap rule on a touch
screen, the label of a run that is not a win, the three levels of trust), 38 in `test/treemap.test.ts` against
`src/treemap.ts`, 16 in `test/scale.test.ts` against `src/scale.ts` (the chart axes: the time ladder, a domain
that holds every value, the 2× band, label thinning, the day columns of the history charts, including under
four time zones) and 14 in `test/format.test.ts` against `src/format.ts` (durations that never come out in
exponent notation, shares, the year in a timestamp, failed requests described). All five modules are
written without React and without imports for that reason: Node 24 runs the
TypeScript directly, so the suite needs no new dependency. The treemap tests cover the squarified layout (areas
proportional, nothing outside or overlapping, tiles reasonably square), the grouped layout (leaves inside
their group, the small-leaf lump holding exactly the members left out, a lone small leaf drawn as itself, a
tile marked "keep" drawn alone, equal chances at alpha 0, the header only where it fits, **one unit of
chance being the same area in every band drawn to scale at every integer width from 200 to 1198 px, for the
band sizes of both real pools**, the tightest band setting the scale and the others leaving the difference
empty along their longer side, a group with no room neither setting the scale nor counting as drawn to it, a
band too dense for tiles being one lump a keyboard can reach, and empty groups and zero values giving finite
rects that still tile), the seven colour
classes (their edges where the legend says, monotone, one failed attempt far from an edge) and the formatting
and URL helpers (a change never written as the next colour class); since item 55 also `undrawn` (which bands are too small to draw), `focusOrder` and
`neighbour` (what the arrow keys reach and where they go, including that every walk ends and that the keys
together reach every listed tile) and `failureReason` (the reason out of the text `useApi` keeps for a 503).
**They are not type-checked** (`tsconfig.json` has `include: ["src"]`), and **the page
itself, `src/pickmap.tsx`, has no test**: item 54's version was looked at in a browser while it was built
(the map, a band's tab, the tooltip, a rebuild, and a narrow-width view in an iframe), which is the only
place the frame, the labels and the tooltip can be seen. **Item 55's changes to it (keyboard focus and
tooltip, the "Too small to draw here" chips, the failure message and Try again) have never been seen in a
browser**; they were checked by `tsc`, `vite build` and two readings of the code. The Python mutation check
of item 54 and the TypeScript one (21 of 21 mutants of `treemap.ts` killed) are recorded in
[status.md](status.md#history-condensed), item 54; item 55's (Python 45 mutants, TypeScript 71 of 71
killed, none survived) in item 55.

Real-model behavior is not covered by the suite (it needs a GPU and minutes per sequence). To check it by
hand, run `oeisbot attempt <A-number> --model` with short budgets, or call
`strategies.codegen.generate_and_verify` directly on well-known sequences.

## Extending

### Adding a strategy

1. Produce `terms.Program` objects:
   - `language`: `python` or `gp` (see below for a new language);
   - `source`: what a human should read;
   - `script`: what actually runs, if a driver wraps `source`;
   - `origin`: where it came from;
   - `strategy`: `<language>:<form>`;
   - `notes`: anything a reviewer must know. The artifact and the dashboard label notes from any
     strategy other than exactly `python:model` as "Program was rewritten". A new strategy with other
     kinds of notes needs its own label in `artifact.write` and `dashboard/src/views.tsx`.
2. Run each program with `_Attempter.run(program, form)` inside `attempt.attempt_sequence`, so recording,
   the run log, the re-check and artifacts all happen. Respect `runner.found_new` (stop everything) and
   `runner.verified` (a program already reproduced the known terms), and decide where the
   strategy sits in the order relative to PARI and the model.
3. For deterministic programs (same script every time), check `db.is_dead_end` (with the session's
   budgets) before running.
4. Record new skip reasons with `db.record_skip` and add them to [pipeline](pipeline.md) and
   [data and schema](data-and-schema.md).
5. Tests: program construction without the sandbox, and one sandboxed test that verifies and extends a
   well-known sequence.

### Adding a language (runtime)

1. Install the runtime under `tools/` in `setup_tools.py`, as copies rather than hard links.
2. Grant the AppContainer read/execute on its directory in `setup_tools.grant_access`.
3. Add a case to `verify.Harness.argv` that writes the program into the scratch directory and returns the
   command line.
4. Emit the `@T` protocol (a driver or runner, as `runners/py_runner.py` does for Python).
5. Add the file extension to `artifact.EXT`, and to `TEXT_SUFFIXES` in `oeisbot/dashboard/app.py` so the
   Review inbox lists and serves the program files.
6. Add sandbox tests showing the runtime works inside the container and cannot escape it.

### Adding a command

Decide whether it is a writer (invariant 11). If it runs a program, calls `git` on the mirror, rewrites
`tools/`, stores a pool or makes a request to oeis.org, add its name to `cli.LOCKED`; otherwise add it
to `UNLOCKED_COMMANDS` in `tests/test_lock.py`. That test fails until the command is in one of the two.
A new stop reason or skip reason must also be placed with respect to the daemon: whether its rows should
cool a sequence (`daemon.Cooldown`) and whether it is the machine's doing (`daemon.MACHINE_FAILURES`).

### Changing the database

Edit `db.SCHEMA` and the write functions. There are no migrations: existing databases need a manual
`ALTER TABLE` (or a fresh database, losing history). Update [data and schema](data-and-schema.md) and any
dashboard endpoint that reads the table.

### Changing the estimator

`estimate.py` is pure and fast to test. Extend `tests/test_estimate.py` with a synthetic cost curve for
the behavior, and check real accuracy afterwards in the dashboard's Estimator accuracy view.

### Changing the dashboard

Run `oeisbot dashboard` and `npm run dev` together (Vite proxies `/api`). `npm run build` type-checks
(`tsc --noEmit`) and writes `oeisbot/dashboard/static/`, which is not committed. Keep endpoints read-only
and extend `tests/test_dashboard.py` for new endpoints (`tests/test_pickmap.py` for the Pick map's). Arithmetic
the page depends on belongs in a module with no React and no imports in it, as `src/treemap.ts`, `src/scale.ts`,
`src/format.ts`, `src/tabs.ts` and (item 58) `src/daemonline.ts` are, so that `npm test` can run it; then add the test to `dashboard/test/`.
`/api/daemon` is the one endpoint that opens no database; it must go on writing nothing (`lock.held`
creates no file) and its tests are in `tests/test_dashboard.py`.
`tests/conftest.py` lets Starlette's test client through the dashboard's Host check (it addresses the app as
`testserver`) and first asserts that the set a real server starts with is the three loopback names.

## Helper scripts

Run from the project root with the venv's Python.

| Script | Purpose |
|---|---|
| `scripts/model_smoke.py [A-numbers...]` | End-to-end check of the real local model (classify, generate, static checks, sandboxed verification) on well-known sequences, using DATA terms and short budgets. Writes nothing to the database or `artifacts/`. Defaults to A000005, A001358, A000108 |
| `scripts/make_demo_db.py` | Builds a synthetic database and review folders so every dashboard view has data. Deletes `data/` and `artifacts/` under `OEISBOT_HOME` first, and refuses to run unless `OEISBOT_HOME` is set to a directory other than the project root. Serve it with `oeisbot dashboard --port 8766` under the same `OEISBOT_HOME` |
| `scripts/check_docs.py` | Fails if a doc link or heading anchor does not resolve. Also lists backticked code names from the docs that are not found in `oeisbot/`, `tests/`, `scripts/` or `dashboard/src/`. There are 5 expected hits and they are all legitimate: an illustrative function name, a PARI type name, a gmpy2 function that does not exist and is cited as not existing, a helper belonging to an OEIS entry's own program, and the JSON key the offer (a) backfill stamped on the 48 attempt rows it rewrote on 2026-09-30 (history item 52) -- written by a one-off script under `data/`, which this scan does not cover, and documented in data-and-schema.md as a live `extra` key. (It was 6 until 2026-11-23: the sixth was the process-creation flag the sandbox deliberately does not use, which sandbox.md names; history item 58 then started git and the runtime version probes with that flag, so that no console window appears under the scheduled task, and the docs' mention resolves to real code. The sandbox still does not use it. It was 5 for a few hours on 2026-09-30, and 10 from 2026-09-29 to 2026-09-30: session 11, history item 50, had added three names from OEIS entries' own PARI programs — A274003's predicate, the A178751 helper it calls, and A034293's predicate — cited in `CLAUDE.md` and `docs/status.md` as that session's program-selection misreads, five hits over the two files, until item 51's parser tests took all three as fixtures and they resolved to real code; 5 until 2026-09-29; 8 until 2026-09-21, when the column data-and-schema.md had only proposed was built; 7 until 2026-09-22, when the second built-in stopped being a miss because `bounds.parse_number` now catches it; and 6 until 2026-09-23, when the last Python built-in stopped being one too — item 43's probe tests name it, so the docs' mention of it resolves to real code.) Naming them in backticks here would add them to the list, so they are described rather than quoted. **The count is checked against the run**: an extra hit, one that becomes real code, or this sentence being reworded away is reported as a problem and exits non-zero, so the list cannot quietly stop being judged |
| `scripts/replay_predictions.py` | Rebuilds every stored prediction from its attempt's term log and reports any disagreement with the stored row; `--write` adds the cost fit's columns and backfills rows that have none. Read-only otherwise. What makes it trustworthy is that it re-derives values that *are* stored — `model`, the three predicted seconds, `predicted_mem`, `value_dependent`, `trustworthy`, and `feasible` for attempts that recorded both budgets — from the same `estimate.assess` call that produces the unstored ones: 45 of 45 replayed rows reproduce exactly. `trustworthy` is in that list because it is `fit_trustworthy and rate_drift <= the kill factor`, making it the only stored column that constrains a replayed `rate_drift` at all. A row it cannot replay — no term log, a pruned or truncated one, a log holding two runs, one belonging to a different run (wrong program sha, wrong known-term count, or named by two attempts at once), a sequence no longer in `sequences`, an unreadable `extra` — is counted and named separately, never among the rows that reproduced, and it makes the exit code non-zero and blocks `--write`. `--write` only ever fills rows where all five columns are NULL, so a replayed value can never overwrite one a run recorded itself (the two can differ, for instance once `oeisbot sync` has changed a sequence's name, which feeds `value_dependent`) |
| `scripts/verify_A385331.py` | Re-derivation of the first win's terms from the sequence's *name*, sharing no code with the entry's PARI program — but **not** step 6 of the review checklist, because it uses the same *method*: trial division with the exponent reduced by Fermat, so a fault in that arithmetic path would show up identically in it and in `program.gp`. Its own docstring says so. `--bound 1000000` settles 37 of 41 terms in about 13 s; the default 2e8 settles all 41 in ~19 min and bounds a(43), the term the `infeasible` stop was made about. Writes nothing. Its default input is inside gitignored `artifacts/`, so on any other machine it needs an explicit `--bfile` |

**Step 6 of the [review checklist](operations.md#reviewing-a-result) is discharged by a different
script**, `data/review1/indep_A385331.py` (history item 44, 2026-09-23). It is not in `scripts/` because
it needs gmpy2 and sympy, which live in the **sandbox runtime** rather than the venv — run it as
`tools\python\python.exe data\review1\indep_A385331.py`. It never forms `n!-k!` and never reduces modulo
`q-1`, using modular inverses instead, so it shares no arithmetic with either `program.gp` or
`verify_A385331.py`. `--bound 100000` validates it against the 24 known terms in about a second; the
default 2e8 took 775 s and settled every term. `data/review1/README.md` has the full account and the
state of every checklist step. `data/` is gitignored, so it exists only on this machine.

## Windows development notes

- **Shell heredocs corrupt backslashes.** GP comments (`\\`), Windows paths and regex escapes are easy to
  mangle when a file is edited through `cat <<EOF` or `sed`. Edit such files with an editor or a
  file-writing tool, then run `python -m py_compile` on the result.
- **Moving the project directory** invalidates the AppContainer grants; run `oeisbot setup` again.
- **Large integers.** Modules that parse or print terms call `sys.set_int_max_str_digits(0)`, since terms
  can exceed Python's default 4,300-digit conversion limit.
- **Checking the dashboard with browser automation.** Chrome cannot screenshot a tab whose window is
  hidden or minimized (the capture times out while the page itself is fine). Check the DOM with
  JavaScript, or bring the window to the front.
