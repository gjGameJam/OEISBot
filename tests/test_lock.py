"""The writers' lock (item 58): one process at a time may run programs, sync, or contact oeis.org."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

import pytest

from oeisbot import config, lock


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(lock, "ACQUIRE_PAUSE_S", 0.0)
    monkeypatch.setattr(lock, "PROBE_PAUSE_S", 0.0)
    return tmp_path / "data"


def test_the_lock_is_free_until_taken_and_free_again_after(data):
    assert not lock.held()
    with lock.writer("run"):
        assert lock.held()
        owner = lock.read_owner()
        assert owner["pid"] == os.getpid() and owner["command"] == "run" and owner["started_at"]
    assert not lock.held()
    assert lock.read_owner() is None                     # the description goes when the holder does
    with lock.writer("sync"):                            # and it can be taken again
        assert lock.read_owner()["command"] == "sync"


def test_asking_whether_it_is_held_creates_nothing(data):
    """The dashboard asks, and the dashboard only reads: before anyone has ever taken the lock there is
    no file, no directory, and the answer is no."""
    assert not lock.held()
    assert not data.exists()
    data.mkdir()
    assert not lock.held() and list(data.iterdir()) == []


def test_a_second_writer_is_refused_and_told_who_holds_it(data):
    with lock.writer("daemon"):
        with pytest.raises(lock.Held) as refused:
            with lock.writer("attempt"):
                pytest.fail("two writers at once")
        message = str(refused.value)
        assert "`oeisbot attempt` not started" in message
        assert f"`oeisbot daemon` (pid {os.getpid()}" in message and "local time" in message
        assert "`oeisbot daemon --stop` for the daemon" in message
        assert refused.value.owner["command"] == "daemon"
        assert lock.held()                               # the refusal took nothing from the holder
        assert lock.read_owner()["command"] == "daemon"  # ... not even its description
    assert not lock.held()
    with lock.writer("sync"):                            # the advice to stop the daemon is for the daemon only
        with pytest.raises(lock.Held) as refused:
            with lock.writer("run"):
                pass
        assert "`oeisbot sync` (pid" in str(refused.value) and "--stop" not in str(refused.value)


def test_the_lock_is_released_when_the_body_raises(data):
    with pytest.raises(ZeroDivisionError):
        with lock.writer("run"):
            1 / 0
    assert not lock.held() and lock.read_owner() is None
    with lock.writer("run"):
        pass


def test_a_stale_description_is_not_a_held_lock(data):
    """A killed process leaves its description in the file. Nothing may read that as "held": the lock
    itself is the only evidence, which is why it is an operating-system lock in the first place."""
    data.mkdir(parents=True)
    lock.lock_path().write_text(json.dumps({"pid": 999999, "command": "daemon", "started_at": "long ago"}))
    assert lock.read_owner()["pid"] == 999999
    assert not lock.held()
    with lock.writer("run"):                             # taken over the stale description, which is replaced
        assert lock.read_owner()["pid"] == os.getpid()
    assert lock.read_owner() is None


def test_a_holder_that_cannot_describe_itself_does_not_leave_someone_elses_name(data, monkeypatch):
    """Found by review: the old description stayed when the new one could not be written, so the
    refusal named a process that had died weeks ago and told the user to stop the daemon."""
    data.mkdir(parents=True)
    lock.lock_path().write_text(json.dumps({"pid": 111, "command": "daemon", "started_at": "weeks ago"}))
    real = os.write
    monkeypatch.setattr(os, "write", lambda fd, b: (_ for _ in ()).throw(OSError("disk full")))
    with lock.writer("run"):
        monkeypatch.setattr(os, "write", real)
        assert lock.read_owner() is None and lock.held()
        with pytest.raises(lock.Held, match="another oeisbot command is running") as refused:
            with lock.writer("sync"):
                pass
        assert refused.value.owner is None


@pytest.mark.parametrize("content", ["", "not json", "[1, 2]", '"a string"', "null"])
def test_an_unreadable_description_still_refuses_with_a_plain_message(data, content):
    with lock.writer("daemon"):
        lock.lock_path().write_text(content)
        assert lock.read_owner() is None
        with pytest.raises(lock.Held, match="another oeisbot command is running") as refused:
            with lock.writer("sync"):
                pass
        assert refused.value.owner is None


def test_the_lock_file_can_be_read_while_it_is_held(data):
    """The locked byte is far past the end of the file. A lock on the file's own bytes made it unreadable
    to every other handle, so a copy or backup of `data/` failed on it for as long as the daemon ran."""
    with lock.writer("daemon"):
        assert json.loads(lock.lock_path().read_bytes())["command"] == "daemon"
        assert lock.lock_path().stat().st_size < 200     # nothing was written out at the locked offset


def test_a_writer_waits_out_the_instant_a_probe_takes(data, monkeypatch):
    """`held()` takes the lock for a moment to see whether it can. A command started in that moment must
    get the lock on a later try rather than be told something else is running."""
    real = lock._try_lock
    calls = {"n": 0}

    def busy_twice(fd):
        calls["n"] += 1
        return False if calls["n"] <= 2 else real(fd)

    monkeypatch.setattr(lock, "_try_lock", busy_twice)
    with lock.writer("run"):
        assert calls["n"] == 3
    # and it does give up: a real holder is not waited for
    monkeypatch.setattr(lock, "_try_lock", lambda fd: False)
    with pytest.raises(lock.Held):
        with lock.writer("run"):
            pass


def test_a_probe_that_meets_another_probe_does_not_report_a_holder(data, monkeypatch):
    """Found by review: the lock is per handle, so two probes at the same instant refused each other and
    each answered "held" on an idle machine (about 5% of the time with four dashboard threads)."""
    with lock.writer("run"):
        pass                                             # the file exists now, and nobody holds it
    real = lock._try_lock
    calls = {"n": 0}

    def busy_once(fd):                                   # as if another probe had it for that instant
        calls["n"] += 1
        return False if calls["n"] == 1 else real(fd)

    monkeypatch.setattr(lock, "_try_lock", busy_once)
    assert not lock.held() and calls["n"] == 2
    monkeypatch.setattr(lock, "_try_lock", lambda fd: False)        # a real holder is there every time
    assert lock.held()

    # and with real threads, as the dashboard's request handlers are
    monkeypatch.setattr(lock, "_try_lock", real)
    answers: list[bool] = []

    def probe():
        for _ in range(200):
            answers.append(lock.held())

    threads = [threading.Thread(target=probe) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(answers) == 800 and not any(answers)


HOLD = """
import os, sys, time
from oeisbot import lock
with lock.writer("daemon"):
    print(os.getpid(), flush=True)      # the venv's python.exe is a launcher: its pid is not this one
    time.sleep(300)
"""


def test_a_killed_holder_releases_the_lock(data):
    """The property the whole design rests on: the lock dies with its process, however that process dies.
    A scheduled task is ended by being killed (logoff, a restart, a closed window), and a lock that
    survived that would stop every later night."""
    env = {**os.environ, "OEISBOT_HOME": str(data.parent)}
    child = subprocess.Popen([sys.executable, "-c", HOLD], env=env, stdout=subprocess.PIPE, text=True)
    try:
        holder = int(child.stdout.readline())
        assert lock.held()
        with pytest.raises(lock.Held) as refused:
            with lock.writer("run"):
                pass
        assert refused.value.owner["pid"] == holder and refused.value.owner["command"] == "daemon"
    finally:
        # Killing the launcher ends the interpreter it started (the launcher keeps it in a job that dies
        # with it), which is how a scheduled task's "End" reaches the daemon too. Give it a moment to go
        child.kill()
        child.wait(timeout=30)
        for _ in range(100):
            if not lock.held():
                break
            time.sleep(0.1)
    assert not lock.held()
    assert lock.read_owner()["pid"] == holder            # the description outlives it, and decides nothing
    with lock.writer("run"):
        assert lock.read_owner()["pid"] == os.getpid()


RACE = """
import sys, time
from oeisbot import lock
while time.time() < float(sys.argv[1]):
    pass
try:
    with lock.writer("run"):
        print("held", flush=True)
        time.sleep(1.0)
except lock.Held:
    print("refused", flush=True)
"""


def test_processes_racing_for_a_lock_file_that_does_not_exist_yet(data):
    """Found by review, on the first creation only: each process saw an empty file and wrote a byte into
    it to have something to lock, and the write of a late one failed on the byte an early one had just
    locked -- a raw PermissionError instead of a refusal. Nothing is written there now."""
    env = {**os.environ, "OEISBOT_HOME": str(data.parent)}
    go = str(time.time() + 3.0)                          # all at the same instant, once every one is up
    children = [subprocess.Popen([sys.executable, "-c", RACE, go], env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True) for _ in range(6)]
    results = [c.communicate(timeout=60) for c in children]
    said = [out.strip() for out, _ in results]
    assert all(c.returncode == 0 for c in children), [err[-300:] for _, err in results if err]
    assert said.count("held") == 1 and said.count("refused") == 5, said


# ------------------------------------------------------------------ the commands that take it

EVERY_LOCKED_COMMAND = [["run", "-n", "1"], ["attempt", "A000001"], ["sync", "--no-pull"], ["recheck"],
                        ["recheck", "--release", "1"], ["fetch-bfiles", "--limit", "1"], ["setup"], ["snapshot"]]


def _commands_that_must_not_run(monkeypatch):
    """Replace every command function with one that fails the test, so a refusal that came too late
    (after the command had started) cannot pass."""
    from oeisbot import cli
    for name in ("cmd_run", "cmd_attempt", "cmd_sync", "cmd_recheck", "cmd_fetch_bfiles", "cmd_setup",
                 "cmd_snapshot"):
        monkeypatch.setattr(cli, name, lambda args, name=name: pytest.fail(f"{name} ran while the lock was held"))
    return cli


@pytest.mark.parametrize("argv", EVERY_LOCKED_COMMAND, ids=lambda a: " ".join(a))
def test_a_command_that_writes_or_fetches_is_refused_while_another_runs(data, monkeypatch, argv):
    cli = _commands_that_must_not_run(monkeypatch)
    with lock.writer("daemon"):
        with pytest.raises(SystemExit) as refused:
            cli.main(argv)
    message = str(refused.value)
    assert f"`oeisbot {argv[0]}` not started" in message and "`oeisbot daemon` (pid" in message
    assert not lock.held()


def test_the_locked_commands_are_exactly_the_ones_that_run_fetch_or_rewrite(monkeypatch):
    """A new command is unlocked by default, which is the unsafe default for one that contacts oeis.org
    or runs a program. This pins the list, so adding a command means deciding which kind it is."""
    import argparse

    from oeisbot import cli
    seen: dict = {}
    real = argparse.ArgumentParser.parse_args

    def spy(self, argv=None):
        if self.prog == "oeisbot":
            (sub,) = [a for a in self._actions if isinstance(a, argparse._SubParsersAction)]
            seen["commands"] = set(sub.choices)
        return real(self, argv)

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", spy)
    with pytest.raises(SystemExit):                  # `--help` builds the whole parser, prints, and exits
        cli.main(["--help"])
    assert cli.LOCKED <= seen["commands"]            # no name in LOCKED that is not a command
    assert seen["commands"] - cli.LOCKED == UNLOCKED_COMMANDS


# everything that only reads, plus `daemon`, which takes the lock itself for its whole life
UNLOCKED_COMMANDS = {"stats", "queue", "pick", "model-check", "attempts", "dashboard", "review", "daemon"}


def test_a_reading_command_is_never_refused(data, monkeypatch):
    from oeisbot import cli, db
    conn = db.connect(data.parent / "t.sqlite3")
    monkeypatch.setattr(db, "connect", lambda *a, **k: conn)
    try:
        with lock.writer("daemon"):
            assert cli.main(["attempts"]) == 0
            assert cli.main(["review", "list"]) == 0
    finally:
        conn.close()


def test_a_locked_command_holds_the_lock_while_it_runs_and_lets_go_however_it_ends(data, monkeypatch):
    from oeisbot import cli
    seen: list = []
    monkeypatch.setattr(cli, "cmd_setup", lambda args: seen.append((lock.held(), lock.read_owner()["command"])))
    assert cli.main(["setup"]) == 0
    assert seen == [(True, "setup")] and not lock.held()

    def boom(args):
        raise RuntimeError("git pull failed")

    monkeypatch.setattr(cli, "cmd_sync", boom)
    with pytest.raises(RuntimeError, match="git pull failed"):
        cli.main(["sync"])
    assert not lock.held() and lock.read_owner() is None

    monkeypatch.setattr(cli, "cmd_recheck", lambda args: (_ for _ in ()).throw(SystemExit("1 win(s) still waiting")))
    with pytest.raises(SystemExit, match="still waiting"):
        cli.main(["recheck"])
    assert not lock.held()


def test_only_a_failure_to_take_the_lock_becomes_a_message(data, monkeypatch):
    from oeisbot import cli
    # an OSError the command itself raises stays what it is
    monkeypatch.setattr(cli, "cmd_setup", lambda args: (_ for _ in ()).throw(PermissionError("tools/ is read-only")))
    with pytest.raises(PermissionError, match="read-only"):
        cli.main(["setup"])
    assert not lock.held()
    # a lock file that cannot be opened is a sentence, not a traceback, and the command does not run
    _commands_that_must_not_run(monkeypatch)
    monkeypatch.setattr(config, "DATA", data.parent / "not-a-directory")
    (data.parent / "not-a-directory").write_text("a file where the data directory should be")
    with pytest.raises(SystemExit, match="could not open the writers' lock"):
        cli.main(["run", "-n", "1"])


def test_no_test_takes_the_real_writers_lock():
    """`tests/conftest.py` gives every test that has not moved `config.DATA` a lock directory of its own.
    Without it the command tests would take the lock of the real `data/`, and fail on any night the
    daemon is running. This test moves nothing, so it sees what such a test gets."""
    assert lock.directory() != config.DATA
    assert config.DATA not in lock.lock_path().parents
    with lock.writer("run"):
        assert lock.lock_path().exists() and lock.held()
