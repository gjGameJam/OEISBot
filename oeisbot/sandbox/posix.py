"""POSIX sandbox backend (Linux/WSL): setrlimit + process group + optional network namespace.

NOTE: written for portability but not exercised on the development machine (Windows).
Run tests/test_sandbox.py on Linux before trusting it.

Isolation here is weaker than the Windows AppContainer backend: rlimits do not cover the
filesystem or network. If `unshare` can create an unprivileged user+network namespace we
use it (no network); filesystem confinement still needs a dedicated low-privilege user or
a container.
"""
from __future__ import annotations

import os
import resource
import shutil
import signal
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from .types import LineCallback, Limits, RunResult, Status, TickCallback

MAX_LINE = 1 << 20


def avail_phys_bytes() -> int:
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    return 0


def _netns_prefix() -> list[str]:
    unshare = shutil.which("unshare")
    if unshare and subprocess.run([unshare, "-rn", "true"], capture_output=True).returncode == 0:
        return [unshare, "-rn"]
    return []


def _dir_size(root: Path) -> int:
    total = 0
    for dirpath, _, files in os.walk(root):
        for name in files:
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                pass
    return total


def run(argv: list[str], *, cwd: Path, limits: Limits, env: dict[str, str] | None = None,
        on_line: LineCallback | None = None, on_tick: TickCallback | None = None,
        tick_s: float = 0.25) -> RunResult:
    cwd = Path(cwd).resolve()
    avail = avail_phys_bytes()
    mem_cap = min(limits.mem_bytes, avail - limits.reserve_phys_bytes)
    if mem_cap < (256 << 20):
        return RunResult(Status.LAUNCH_ERROR, None, 0.0, 0.0, 0, max(mem_cap, 0), "not enough free RAM")

    def preexec():
        resource.setrlimit(resource.RLIMIT_AS, (mem_cap, mem_cap))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (limits.disk_bytes, limits.disk_bytes))
        if limits.cpu_s:
            c = int(limits.cpu_s) + 1
            resource.setrlimit(resource.RLIMIT_CPU, (c, c))
        if limits.low_priority:
            os.nice(10)

    full_env = {"PATH": "/usr/bin:/bin", "HOME": str(cwd), "TMPDIR": str(cwd), "LANG": "C.UTF-8"}
    full_env.update(env or {})
    prefix = _netns_prefix() if limits.isolate else []
    proc = subprocess.Popen(prefix + [str(a) for a in argv], cwd=cwd, env=full_env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=preexec,
                            start_new_session=True)
    t0 = time.perf_counter()
    lock = threading.Lock()
    cb_lock = threading.Lock()
    state: dict = {"status": None, "reason": None}
    stdout_tail: deque[str] = deque(maxlen=200)
    stderr_buf = bytearray()

    def request(status: Status, reason: str):
        with lock:
            if state["status"] is None:
                state["status"], state["reason"] = status, reason

    def read_stdout():
        total = 0
        for chunk in iter(lambda: proc.stdout.readline(MAX_LINE), b""):
            total += len(chunk)
            if state["status"] is not None:
                continue
            if total > limits.output_bytes:
                request(Status.OUTPUT_CAP, "stdout too large")
                continue
            line = chunk.decode("utf-8", "replace").rstrip("\r\n")
            stdout_tail.append(line[:2000])
            if on_line:
                with cb_lock:
                    reason = on_line(line, time.perf_counter() - t0)
                if reason:
                    request(Status.STOPPED, reason)

    def read_stderr():
        for chunk in iter(lambda: proc.stderr.read1(1 << 16), b""):
            stderr_buf.extend(chunk)
            if len(stderr_buf) > (128 << 10):
                del stderr_buf[: len(stderr_buf) - (64 << 10)]

    readers = [threading.Thread(target=read_stdout, daemon=True), threading.Thread(target=read_stderr, daemon=True)]
    for r in readers:
        r.start()

    next_disk = 0.0
    next_tick = 0.0
    rusage = None
    while True:
        pid, status_word, ru = os.wait4(proc.pid, os.WNOHANG)
        if pid:
            rusage = ru
            proc.returncode = os.waitstatus_to_exitcode(status_word)
            break
        elapsed = time.perf_counter() - t0
        if state["status"] is None:
            if elapsed >= limits.wall_s:
                request(Status.TIMEOUT, f"wall clock reached {limits.wall_s:g} s")
            elif elapsed >= next_disk:
                next_disk = elapsed + 1.0
                if _dir_size(cwd) > limits.disk_bytes:
                    request(Status.DISK_CAP, "scratch too large")
                elif shutil.disk_usage(cwd).free < limits.reserve_disk_bytes:
                    request(Status.DISK_CAP, "free disk too low")
                elif avail_phys_bytes() < limits.reserve_phys_bytes // 2:
                    request(Status.MEMORY_CAP, "system physical RAM running low")
            if on_tick and elapsed >= next_tick and state["status"] is None:
                next_tick = elapsed + tick_s
                with cb_lock:
                    reason = on_tick(elapsed)
                if reason:
                    request(Status.STOPPED, reason)
        if state["status"] is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(0.05)

    wall = time.perf_counter() - t0
    try:
        os.killpg(proc.pid, signal.SIGKILL)  # stragglers in the group
    except ProcessLookupError:
        pass
    for r in readers:
        r.join(timeout=10)
    peak = (rusage.ru_maxrss * 1024) if rusage else 0
    cpu = (rusage.ru_utime + rusage.ru_stime) if rusage else 0.0
    status = state["status"]
    if status is None:
        status = Status.EXITED
        if proc.returncode == -signal.SIGXCPU or (limits.cpu_s and cpu >= limits.cpu_s):
            status = Status.CPU_CAP
        elif proc.returncode != 0 and peak >= 0.9 * mem_cap:
            status = Status.MEMORY_CAP
    return RunResult(status, proc.returncode, wall, cpu, peak, mem_cap, state["reason"], list(stdout_tail),
                     stderr_buf.decode("utf-8", "replace"))
