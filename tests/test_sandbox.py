"""Adversarial checks: each test tries to break one guarantee the rest of the system relies on."""
from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from oeisbot import config, sandbox
from oeisbot.sandbox import Limits, Status

pytestmark = [
    pytest.mark.sandbox,
    pytest.mark.skipif(bool(sandbox.runtime_problems()), reason="; ".join(sandbox.runtime_problems())),
]

MiB = 1 << 20


_made: list[Path] = []


@pytest.fixture(autouse=True)
def _cleanup_scratch():
    yield
    while _made:
        shutil.rmtree(_made.pop(), ignore_errors=True)


def scratch(label: str) -> Path:
    d = sandbox.new_scratch_dir(label)
    _made.append(d)
    return d


def run_py(code: str, limits: Limits, **kw):
    d = scratch("test")
    (d / "prog.py").write_text(textwrap.dedent(code))
    lines: list[str] = []
    on_line = kw.pop("on_line", None) or (lambda line, t: lines.append(line))
    res = sandbox.run([config.SANDBOX_PYTHON, "-B", "-u", "prog.py"], cwd=d, limits=limits, on_line=on_line, **kw)
    return res, lines, d


def test_clean_exit_and_accounting():
    res, lines, _ = run_py("print('hi'); x = bytearray(50 * 2**20); print(len(x))", Limits(wall_s=30))
    assert res.status is Status.EXITED and res.exit_code == 0
    assert lines == ["hi", str(50 * MiB)]
    assert res.peak_mem_bytes > 50 * MiB


def test_memory_cap_is_hard():
    code = """
        chunks = []
        while True:
            chunks.append(bytearray(16 * 2**20))
    """
    t0 = time.perf_counter()
    res, _, _ = run_py(code, Limits(wall_s=60, mem_bytes=256 * MiB))
    assert res.status is Status.MEMORY_CAP, res
    assert res.peak_mem_bytes <= 256 * MiB * 1.1  # kernel peak accounting can overshoot the cap slightly
    assert time.perf_counter() - t0 < 20


def test_single_huge_allocation_is_refused():
    code = """
        try:
            x = bytearray(16 << 30)
            print("ALLOCATED")
        except MemoryError:
            print("MEMORYERROR")
    """
    res, lines, _ = run_py(code, Limits(wall_s=60, mem_bytes=512 * MiB))
    assert res.status is Status.MEMORY_CAP, res
    assert "ALLOCATED" not in lines
    assert res.peak_mem_bytes <= res.mem_cap_bytes     # the refused 16 GiB request is not reported as used


def test_memory_cap_even_if_program_swallows_memoryerror():
    code = """
        import time
        chunks = []
        while True:
            try:
                chunks.append(bytearray(16 * 2**20))
            except MemoryError:
                time.sleep(0.01)
    """
    res, _, _ = run_py(code, Limits(wall_s=60, mem_bytes=256 * MiB))
    assert res.status is Status.MEMORY_CAP, res
    assert res.wall_s < 10


def test_wall_timeout():
    res, _, _ = run_py("while True: pass", Limits(wall_s=1.5))
    assert res.status is Status.TIMEOUT
    assert 1.4 < res.wall_s < 4


def test_cpu_cap():
    res, _, _ = run_py("while True: pass", Limits(wall_s=30, cpu_s=1.0))
    assert res.status is Status.CPU_CAP, res
    assert res.wall_s < 10


def test_cannot_start_child_processes():
    code = """
        import subprocess
        try:
            out = subprocess.run(["cmd.exe", "/c", "echo escaped"], capture_output=True, text=True, timeout=10)
            print("RAN", out.stdout.strip())
        except Exception as e:
            print("BLOCKED", type(e).__name__)
    """
    res, lines, _ = run_py(code, Limits(wall_s=30))
    assert any(l.startswith("BLOCKED") for l in lines), (lines, res)
    assert not any("escaped" in l for l in lines)


def test_no_network():
    # a listener on the host loopback, plus the public internet and DNS
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    accepted = []

    def accept():
        try:
            accepted.append(srv.accept())
        except OSError:
            pass  # listener closed at the end of the test

    threading.Thread(target=accept, daemon=True).start()
    code = f"""
        import socket
        for target in [("127.0.0.1", {port}), ("1.1.1.1", 443), ("oeis.org", 443)]:
            try:
                socket.create_connection(target, timeout=3).close()
                print("CONNECTED", target)
            except Exception as e:
                print("BLOCKED", target, type(e).__name__)
    """
    try:
        res, lines, _ = run_py(code, Limits(wall_s=60))
    finally:
        srv.close()
    assert not any(l.startswith("CONNECTED") for l in lines), lines
    assert sum(l.startswith("BLOCKED") for l in lines) == 3, (lines, res)
    assert not accepted


def test_filesystem_confined(tmp_path: Path):
    secret = tmp_path / "secret.txt"          # under the user profile temp dir
    secret.write_text("top secret")
    outside = config.ROOT / "pwned.txt"       # project root, writable by the user
    code = f"""
        from pathlib import Path
        def attempt(label, fn):
            try:
                fn(); print("ALLOWED", label)
            except Exception as e:
                print("DENIED", label, type(e).__name__)
        attempt("read_secret", lambda: Path(r"{secret}").read_text())
        attempt("write_root", lambda: Path(r"{outside}").write_text("x"))
        attempt("write_python_dir", lambda: Path(r"{config.SANDBOX_PYTHON_DIR / 'pwned.txt'}").write_text("x"))
        attempt("read_home", lambda: list(Path(r"{Path.home()}").iterdir()))
        attempt("write_scratch", lambda: Path("ok.txt").write_text("fine"))
    """
    res, lines, d = run_py(code, Limits(wall_s=30))
    status = {l.split()[1]: l.split()[0] for l in lines}
    assert status == {"read_secret": "DENIED", "write_root": "DENIED", "write_python_dir": "DENIED",
                      "read_home": "DENIED", "write_scratch": "ALLOWED"}, (lines, res.stderr_tail)
    assert not outside.exists()
    assert (d / "ok.txt").read_text() == "fine"


def test_output_flood():
    res, _, _ = run_py("while True: print('x' * 1000)", Limits(wall_s=60, output_bytes=2 * MiB))
    assert res.status is Status.OUTPUT_CAP, res


def test_disk_cap():
    code = """
        import time
        with open("big.bin", "wb") as f:
            while True:
                f.write(b"\\0" * 2**20); f.flush(); time.sleep(0.005)
    """
    res, _, d = run_py(code, Limits(wall_s=60, disk_bytes=20 * MiB))
    assert res.status is Status.DISK_CAP, res
    assert (d / "big.bin").stat().st_size < 1024 * MiB


def test_caller_can_stop_on_a_line():
    seen = []

    def on_line(line, t):
        seen.append(line)
        return "enough" if line == "3" else None

    res, _, _ = run_py("import itertools\nfor i in itertools.count(): print(i)", Limits(wall_s=30), on_line=on_line)
    assert res.status is Status.STOPPED and res.stop_reason == "enough"
    assert seen[:4] == ["0", "1", "2", "3"]


def test_on_tick_can_stop():
    res, _, _ = run_py("while True: pass", Limits(wall_s=30), on_tick=lambda t: "tick-stop" if t > 0.5 else None)
    assert res.status is Status.STOPPED and res.stop_reason == "tick-stop"
    assert res.wall_s < 3


def test_job_dies_with_harness(tmp_path: Path):
    """If the harness process is killed, the kill-on-close job takes the sandboxed program with it."""
    pidfile = scratch("orphan") / "pid.txt"
    harness = tmp_path / "harness.py"
    harness.write_text(textwrap.dedent(f"""
        from pathlib import Path
        from oeisbot import config, sandbox
        d = Path(r"{pidfile.parent}")
        (d / "p.py").write_text("import os, time\\nopen('pid.txt','w').write(str(os.getpid()))\\nwhile True: time.sleep(1)\\n")
        sandbox.run([config.SANDBOX_PYTHON, "-B", "p.py"], cwd=d, limits=sandbox.Limits(wall_s=600))
    """))
    proc = subprocess.Popen([sys.executable, str(harness)], cwd=config.ROOT)
    try:
        for _ in range(100):
            if pidfile.exists() and pidfile.read_text():
                break
            time.sleep(0.1)
        child_pid = int(pidfile.read_text())
        assert _pid_alive(child_pid)
    finally:
        proc.kill()
        proc.wait()
    for _ in range(50):
        if not _pid_alive(child_pid):
            break
        time.sleep(0.1)
    assert not _pid_alive(child_pid)


def _pid_alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def test_gp_runs_sandboxed():
    d = scratch("gp")
    (d / "s.gp").write_text('print(factor(2^64+1));\nquit\n')
    lines = []
    res = sandbox.run([config.GP, "-q", "-f", "s.gp"], cwd=d, limits=Limits(wall_s=30),
                      on_line=lambda l, t: lines.append(l))
    assert res.ok, res
    assert lines == ["[274177, 1; 67280421310721, 1]"]


def test_gp_cannot_shell_out():
    d = scratch("gp")
    (d / "s.gp").write_text('print(externstr("cmd /c echo escaped"));\nquit\n')
    lines = []
    res = sandbox.run([config.GP, "-q", "-f", "s.gp"], cwd=d, limits=Limits(wall_s=30),
                      on_line=lambda l, t: lines.append(l))
    assert not any("escaped" in l for l in lines), (lines, res)
