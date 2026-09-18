# Sandbox and safety model

Every program the pipeline runs, whether copied from an OEIS entry or written by the local model, is
treated as untrusted code on a personal machine. `oeisbot.sandbox.run` is the only way the pipeline
starts one, and everything else (verification, budgets, estimates) assumes it holds.

## What it guarantees

| Guarantee | Mechanism | Test (`tests/test_sandbox.py`) |
|---|---|---|
| A job cannot commit more memory than its cap | Job Object `JobMemoryLimit`; the harness also kills the job as soon as Windows reports the limit | `test_memory_cap_is_hard`, `test_single_huge_allocation_is_refused`, `test_memory_cap_even_if_program_swallows_memoryerror` |
| The machine never pages because of a job | Cap = min(6 GiB, free RAM − 3 GiB) at launch; job stopped if free RAM < 1.5 GiB | (arithmetic; not simulated) |
| A job cannot run forever | Wall-clock limit enforced by the harness; optional CPU-time limit in the job | `test_wall_timeout`, `test_cpu_cap` |
| A job cannot start other processes | Job `ActiveProcessLimit = 1` and the child-process-restricted creation policy | `test_cannot_start_child_processes`, `test_gp_cannot_shell_out` |
| No network, loopback included | AppContainer token with zero capabilities | `test_no_network` (host loopback listener, 1.1.1.1:443, oeis.org) |
| No access to user files | AppContainer: only paths granted to the container SID or to all app packages | `test_filesystem_confined` (secret in the user temp dir, project root, sandbox Python dir, home dir) |
| Disk use is bounded | Scratch size polled every second; job stopped if free disk falls below a reserve | `test_disk_cap` |
| Output floods cannot exhaust the harness | Per-line and total stdout caps; pipes are always drained | `test_output_flood` |
| If the harness dies, the job dies | Job Object kill-on-close | `test_job_dies_with_harness` |
| The caller can stop a job at any moment | `on_line` / `on_tick` callbacks returning a reason | `test_caller_can_stop_on_a_line`, `test_on_tick_can_stop` |

## Windows backend (`oeisbot/sandbox/windows.py`)

This is the backend the project runs on. It uses `ctypes` only (no pywin32).

### Launch

1. **Memory cap.** `mem_cap = min(Limits.mem_bytes, available physical RAM − Limits.reserve_phys_bytes)`.
   If that is below 256 MiB the run returns `launch_error` without starting anything.
2. **Job Object** with:
   - `KILL_ON_JOB_CLOSE`: closing the harness's handle (including the harness crashing) kills the job;
   - `DIE_ON_UNHANDLED_EXCEPTION`: no Windows Error Reporting dialogs;
   - `JOB_MEMORY = mem_cap`: a hard cap on committed memory for the whole job;
   - `ACTIVE_PROCESS = 1`;
   - `JOB_TIME` when `Limits.cpu_s` is set (the pipeline never sets it);
   - below-normal priority when `Limits.low_priority` (the default);
   - all UI restrictions;
   - an I/O completion port for limit notifications.
3. **Pipes.** stdin (write end closed immediately, so the program sees end-of-file), stdout and stderr.
   A handle list ensures the child inherits only these three handles.
4. **Process attributes.** The process is created inside the job (`PROC_THREAD_ATTRIBUTE_JOB_LIST`) with
   child processes restricted, and, when `Limits.isolate` (the default), with the AppContainer's security
   capabilities and no capability SIDs.
5. **CreateProcessW**, suspended and `DETACHED_PROCESS`. With no console there is no `conhost.exe`, which
   would otherwise count against the one-process limit. The environment block is built from scratch:
   `SystemRoot`, `windir`, `SystemDrive`, `PATH` (the executable's directory and System32), `TEMP`,
   `TMP`, `HOME` and `USERPROFILE` pointing at the scratch directory, and `LOCALAPPDATA`. Windows requires
   `LOCALAPPDATA` when launching into an AppContainer (without it `CreateProcess` fails with error 203) and
   then rewrites it, `TEMP` and `TMP` to the container's own folder.
6. Reader threads start, then the main thread is resumed.

### Monitoring loop (about every 100 ms)

- **Job notifications**: memory limit → stop as `memory_cap`; job or process CPU time → `cpu_cap`;
  active-process limit → `stopped` ("tried to start a child process").
- **Caller stop**: a reason returned from `on_line` or `on_tick` → `stopped`. The callbacks are
  serialized under one lock, so callers need no locking.
- **Wall clock** ≥ `Limits.wall_s` → `timeout`.
- **Every second**:
  - scratch size plus growth of the container's own profile folder > `Limits.disk_bytes` → `disk_cap`;
  - free space on the scratch drive < `Limits.reserve_disk_bytes` → `disk_cap`;
  - available physical RAM < half of `Limits.reserve_phys_bytes` → `memory_cap`.
- **`on_tick`** every 0.25 s.

The first stop request wins; the job is then terminated with `TerminateJobObject`.

### Output handling

- stdout is read line by line with a 1 MiB line limit. A longer line, or more than 256 MiB in total, stops
  the job as `output_cap`.
- After a stop the reader keeps draining the pipe (discarding), so the child can never block on a full
  pipe while the harness is tearing it down.
- The last 200 stdout lines (each cut to 2,000 characters) and the last 64 KiB of stderr are returned for
  diagnostics.

### After exit

- Late job notifications are drained, so a program that catches its `MemoryError` and exits still reports
  `memory_cap`.
- CPU time is the job's total user + kernel time.
- Peak memory is `min(PeakJobMemoryUsed, mem_cap)`: Windows counts a *refused* commit in the job's peak (a
  single 16 GiB request against a 6 GiB cap reports a 16 GiB peak without that memory ever being granted).
- The container's `Temp` folder is emptied, and every handle is closed, the job last.

### Result

`RunResult(status, exit_code, wall_s, cpu_s, peak_mem_bytes, mem_cap_bytes, stop_reason, stdout_tail,
stderr_tail)` where `status` is one of `exited`, `timeout`, `cpu_cap`, `memory_cap`, `disk_cap`,
`output_cap`, `stopped`, `launch_error`.

## Filesystem and network access in practice

An AppContainer token can open an object only if its ACL grants the container SID (or the "ALL
APPLICATION PACKAGES" group, which Windows grants on system directories). In this project:

| Path | Access | How |
|---|---|---|
| `tools/python/` (embeddable Python + gmpy2 + sympy) | read, execute | `oeisbot setup` |
| `tools/pari/gp.exe` | read, execute | `oeisbot setup` |
| `data/scratch/` (each run gets its own subdirectory) | modify | `oeisbot setup` |
| `%LOCALAPPDATA%\Packages\oeisbot.sandbox\AC\` (container profile) | modify | Windows, always; `Temp` emptied after each run and growth counted toward the disk cap |
| System directories (System32 and so on) | read | Windows |
| Everything else: user profile, project directory, other data | none | |

Grants are inherited by new files. **Moving the project directory breaks them**: run `oeisbot setup`
again afterwards.

There are no network capabilities, so outbound connections, DNS and loopback all fail.

## Why the sandbox uses its own runtimes

- **Embeddable Python.** The normal Python install lives under the user profile, which the container
  cannot read. A private copy lives in `tools/python/`.
- **`--link-mode copy`.** uv installs packages as hard links into its cache by default, and hard links
  keep the cache's ACL (no container grant). Copies inherit the directory's grant.
- **Precompiling.** The sandbox cannot write `__pycache__`, so importing sympy would recompile it on every
  run (about 2.5 s). When `setup` installs missing packages, it compiles them with the host Python
  (`sys.executable`). The bytecode is only reused if the host is also Python 3.11 (checked here: 3.11.9
  on both), and nothing verifies that.
- **Standalone `gp.exe`.** The PARI installer is not needed; the single executable runs in the container.

## Windows behaviors this backend works around

These were found by the tests or by real runs:

1. **`LOCALAPPDATA` is mandatory** in a custom environment block for AppContainer launches (error 203,
   `ERROR_ENVVAR_NOT_FOUND`).
2. **Directory listings report stale sizes** for files still open for writing, so the disk check uses
   `os.stat` per file. Before this fix, two runs of the disk-cap test each wrote about 10 GB before the
   wall clock stopped them.
3. **Refused commits inflate `PeakJobMemoryUsed`**; the reported peak is clamped to the cap.
4. **This gp build commits its whole `parisizemax` at startup.** Its job peak therefore always equals
   the stack cap, so for gp programs the pipeline reports the stack size the driver prints instead (see
   [verification](verification-and-estimation.md#term-protocol)). Committed but untouched pages do not
   use physical RAM, so this does not cause paging.
5. **`DETACHED_PROCESS` rather than `CREATE_NO_WINDOW`**, so no console host joins the job.

## Caveats and gaps

- **No CPU cap in the pipeline.** `Limits.cpu_s` works (tested) but the verification harness never sets
  it; wall clock is the only time limit.
- **Disk polling interval.** A program can write for up to about a second beyond the cap before it is
  stopped. The free-disk reserve (8 GiB) is the backstop.
- **Only committed memory is capped.** Memory that is not commit-charged (for example mapped views of
  files) is not counted.
- **Reads of system files are allowed**, as for any AppContainer. The tests cover user files and the
  project directory, not every object a container might reach (named pipes or RPC endpoints that accept
  app containers were not audited).
- **POSIX backend (`sandbox/posix.py`) is untested and not usable end to end.** It applies
  `RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_FSIZE` and `RLIMIT_CORE`, `nice`, a process group killed on stop,
  and `unshare -rn` for no network when available. It has no filesystem confinement. The rest of the
  project is Windows-specific: `config.py` hard-codes `python.exe` and `gp.exe`, and `setup` downloads
  Windows binaries.

## Changing the sandbox

- Keep `tests/test_sandbox.py` passing, and add a test for any new guarantee: every test there attacks
  one guarantee directly.
- The harness assumes `run` never raises for program misbehavior. Problems belong in `RunResult.status`;
  only setup failures (Windows API errors while creating the job) raise.
- If you add a runtime (a new language), grant the container read/execute on its directory in
  `setup_tools.grant_access`, and make sure package files are copies, not hard links.
