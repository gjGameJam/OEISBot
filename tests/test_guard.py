"""The product's own guard (oeisbot.guard, item 58): under a test, the real project is refused.

These tests call the *real* functions, past the replacements `tests/conftest.py` puts in front of them,
because the guard is what is left when those are walked past.

**No test here aims at the real project.** Each one tells the guard that a temporary directory is "real"
(`guard.REAL_DIRS`) and points the function at that. If the guard is ever removed or broken -- as a
mutant of it is, on purpose -- the function writes into the temporary directory and the test fails on
what it finds there. The first version of this file aimed at the real paths and promised to stub every
dangerous call first; on 2026-11-23 one test had not, and a mutant left a real `data/daemon/stop`.
A list of stubs is only as good as its last entry. Only `is_real` itself, which writes nothing, is
asked about the true installation.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from oeisbot import artifact, attempt, config, daemon, db, guard, lock
from oeisbot.guard import RealProjectRefused
from oeisbot.ingest import bfile, oeisdata


@pytest.fixture
def fake_real(tmp_path, monkeypatch):
    """A stand-in for the real project: the guard treats `tmp/data` and `tmp/artifacts` as the
    installation's own, and `config` points there too, as it does in real use."""
    data, artifacts = tmp_path / "data", tmp_path / "artifacts"
    monkeypatch.setattr(guard, "REAL_DIRS", (data, artifacts))
    monkeypatch.setattr(config, "DATA", data)
    monkeypatch.setattr(config, "ARTIFACTS", artifacts)
    monkeypatch.setattr(config, "SCRATCH", data / "scratch")
    monkeypatch.setattr(config, "OEISDATA", data / "oeisdata")
    monkeypatch.setattr(config, "DB_PATH", data / "oeisbot.sqlite3")
    monkeypatch.setattr(lock, "directory", lambda: data)
    monkeypatch.setattr(daemon, "daemon_dir", lambda: data / "daemon")
    return tmp_path


def nothing_was_written(root: Path) -> bool:
    return not (root / "data").exists() and not (root / "artifacts").exists()


def test_a_test_is_known_to_be_a_test(monkeypatch):
    assert guard.under_test()
    assert "PYTEST_CURRENT_TEST" in os.environ                   # pytest's own, for the length of this test
    assert os.environ.get("OEISBOT_UNDER_TEST") == "1"           # the suite's, from conftest's first line on
    # either is enough: the suite's covers import and collection time, when pytest's is not set, and
    # pytest's covers a test whose environment lost the suite's
    monkeypatch.delenv("OEISBOT_UNDER_TEST")
    assert guard.under_test()
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    assert not guard.under_test()
    monkeypatch.setenv("OEISBOT_UNDER_TEST", "1")
    assert guard.under_test()
    for value, expected in (("1", True), ("true", True), ("yes", True), (" 1 ", True), ("0", False), ("", False),
                            (" 0 ", False)):
        monkeypatch.setenv("OEISBOT_UNDER_TEST", value)          # anything but nothing or 0 means yes
        assert guard.under_test() is expected, value


def test_what_counts_as_the_real_project(tmp_path, monkeypatch):
    """The one test that asks about the true installation; `is_real` only resolves a path."""
    root = guard.INSTALL_ROOT
    assert root == config.ROOT and guard.REAL_DIRS == (root / "data", root / "artifacts")
    real = root / "data" / "oeisbot.sqlite3"
    assert guard.is_real(real) and guard.is_real(root / "data") and guard.is_real(root / "data" / "daemon" / "stop")
    assert guard.is_real(root / "artifacts" / "A385331")
    assert guard.is_real(root / "data" / "oeisdata" / ".." / "oeisbot.sqlite3")
    assert not guard.is_real(tmp_path / "data" / "oeisbot.sqlite3")
    assert not guard.is_real(root / "oeisbot" / "db.py")         # code is not data
    assert not guard.is_real(root / "database")                  # a name that only starts like it
    # judged by where it leads, not by how it is written
    monkeypatch.chdir(root)
    assert guard.is_real("data/oeisbot.sqlite3") and guard.is_real(Path("data") / "daemon" / "armed")
    monkeypatch.chdir(tmp_path)
    assert not guard.is_real("data/oeisbot.sqlite3")
    if sys.platform == "win32":
        text = str(real)
        assert guard.is_real(text.upper()) and guard.is_real(text.lower())
        assert guard.is_real("\\\\?\\" + text)                   # the prefix `resolve` keeps, which walked past
        assert guard.is_real("\\\\.\\" + text)
        assert not guard.is_real("\\\\?\\" + str(tmp_path / "data" / "x"))
    # decided from where the package is, never from config: moving config does not move what is real
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    assert guard.is_real(real)
    # and a path that cannot be resolved is taken as real: the safe answer before a write
    monkeypatch.setattr(guard.Path, "resolve", lambda self: (_ for _ in ()).throw(OSError("no such device")))
    assert guard.is_real("Q:\\nowhere\\x")


def test_outside_a_test_nothing_is_refused(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    monkeypatch.delenv("OEISBOT_UNDER_TEST")
    assert not guard.under_test()
    guard.refuse_if_real(config.DB_PATH, "x")                    # no exception: this is how real use works
    guard.refuse_network("x")
    monkeypatch.setenv("OEISBOT_UNDER_TEST", "1")                # a harness that is not pytest says so itself
    with pytest.raises(RealProjectRefused, match="refused under a test: x"):
        guard.refuse_if_real(config.DB_PATH, "x")
    with pytest.raises(RealProjectRefused, match="would contact oeis.org"):
        guard.refuse_network("x")


def test_the_database_is_refused_for_writing_and_read_only_is_not(real_connect, fake_real):
    # Always with an explicit path here. `real_connect()` with none means the TRUE database, which this
    # fixture has just told the guard is not real: the first draft of this test made that call, and it
    # opened the real database for writing (nothing in it changed). The next test covers the default.
    with pytest.raises(RealProjectRefused, match="opening the database for writing"):
        real_connect(config.DB_PATH)
    assert nothing_was_written(fake_real)
    other = fake_real / "elsewhere" / "t.sqlite3"                # a database of the test's own opens as ever
    conn = real_connect(other)
    conn.close()
    # reading is never refused: with the stand-in made to exist, a read-only connection opens it
    (fake_real / "data").mkdir()
    other.replace(config.DB_PATH)
    real_connect(config.DB_PATH, readonly=True).close()


def test_the_default_database_path_is_refused_whatever_config_says(real_connect, monkeypatch):
    """`db.connect()` with no path means the true database, bound when the module loaded. The guard's
    answer for it does not depend on a stand-in: here `sqlite3.connect` itself is made to fail the test,
    which is the one stub in this file, on the one call that has no path to redirect."""
    monkeypatch.setattr(db.sqlite3, "connect", lambda *a, **k: pytest.fail("the real database was about to be opened"))
    with pytest.raises(RealProjectRefused, match="opening the database for writing"):
        real_connect()


def test_the_mirror_is_refused_to_git_and_to_an_update(real_git, fake_real, monkeypatch):
    ran: list = []
    monkeypatch.setattr(oeisdata.subprocess, "run", lambda *a, **k: ran.append(a) or pytest.fail("git ran"))
    monkeypatch.setattr(oeisdata.subprocess, "Popen", lambda *a, **k: ran.append(a) or pytest.fail("git ran"))
    with pytest.raises(RealProjectRefused, match="running `git fetch --depth` on the mirror"):
        real_git("fetch", "--depth", "1", "origin", cwd=config.OEISDATA, timeout=5)
    with pytest.raises(RealProjectRefused):                      # a clone, which has no cwd: the target is the mirror
        real_git("clone", "--depth", "1", "x", str(config.OEISDATA))
    # the update removes old lock files before it reaches git: it is refused before that, not after
    git = config.OEISDATA / ".git"
    git.mkdir(parents=True)
    stale = git / "index.lock"
    stale.write_text("")
    old = stale.stat().st_mtime - 10 * oeisdata.STALE_GIT_LOCK_S
    os.utime(stale, (old, old))
    monkeypatch.setattr(oeisdata, "_git", real_git)
    with pytest.raises(RealProjectRefused, match="updating the mirror"):
        oeisdata.update(lambda m: None, timeout=600)
    assert stale.exists() and ran == []


def test_oeis_org_is_refused(real_http_get, monkeypatch):
    monkeypatch.setattr(bfile.urllib.request, "urlopen", lambda *a, **k: pytest.fail("a request was about to be made"))
    with pytest.raises(RealProjectRefused, match="would contact oeis.org"):
        real_http_get("https://oeis.org/A000045/b000045.txt")


def test_the_lock_and_the_daemons_files_are_refused(fake_real):
    with pytest.raises(RealProjectRefused, match="taking the writers' lock"):
        with lock.writer("run"):
            pass
    for act, what in ((daemon.request_stop, "leaving a stop request"), (daemon.arm, "arming the daemon"),
                      (daemon.disarm, "disarming the daemon"),
                      (lambda: daemon.log_to(daemon.daemon_dir()), "writing the daemon's log")):
        with pytest.raises(RealProjectRefused, match=what):
            act()
    assert nothing_was_written(fake_real)


def test_a_daemon_night_is_refused_before_it_writes_anything(fake_real, real_connect):
    conn = real_connect(fake_real / "elsewhere" / "t.sqlite3")
    try:
        night = daemon.Daemon(conn, daemon.Window.parse("always"), log=lambda m: None, sync=False)
        with pytest.raises(RealProjectRefused, match="running a daemon night"):
            night.run()
        with pytest.raises(RealProjectRefused, match="writing the daemon's heartbeat"):
            night.beat(state="running")
        (config.SCRATCH / "A123456-gp-0a1b2c3d").mkdir(parents=True)
        old = (config.SCRATCH / "A123456-gp-0a1b2c3d").stat().st_mtime - 2 * daemon.SCRATCH_ORPHAN_AGE_S
        os.utime(config.SCRATCH / "A123456-gp-0a1b2c3d", (old, old))
        with pytest.raises(RealProjectRefused, match="sweeping old run directories"):
            night.sweep_scratch()
        assert (config.SCRATCH / "A123456-gp-0a1b2c3d").exists()
    finally:
        conn.close()
    assert not (fake_real / "data" / "daemon").exists()


def test_what_a_session_writes_is_refused(fake_real):
    """Run logs, a pending win, an artifact folder: each goes through `config`, which every test that
    runs a session moves. If one ever does not, the write is refused here rather than made."""
    with pytest.raises(RealProjectRefused, match="saving a pending win"):
        attempt._save_pending(1, None, "x", config.DEFAULT_BUDGETS)

    class Result:
        class known:
            a_number = "A000045"

    with pytest.raises(RealProjectRefused, match="writing an artifact folder"):
        artifact.write(Result, 1, "x", config.DEFAULT_BUDGETS, "note")
    with pytest.raises(RealProjectRefused, match="writing a run log"):
        attempt._Attempter(None, None, Result.known, config.DEFAULT_BUDGETS, None, None, lambda m: None, True).run(
            type("P", (), {"language": "gp", "sha": "0" * 16})(), "a(n)")
    assert nothing_was_written(fake_real)


CHILD = """
import sys
from pathlib import Path
from oeisbot import config, db, guard
assert guard.under_test(), "the child did not inherit the test's environment"
home = Path(sys.argv[1])
assert config.DATA == home / "data", "the child is not in the home it was given"
guard.REAL_DIRS = (home / "data", home / "artifacts")      # its own home stands in for the real project
try:
    db.connect()
except guard.RealProjectRefused as e:
    print("refused:", e)
    sys.exit(0)
sys.exit("the child opened the database")
"""


def test_a_child_process_started_by_a_test_is_refused_too(tmp_path):
    """What the walls in `tests/conftest.py` cannot do: they are replaced functions in this process, and
    a child imports the real ones. The guard goes with the environment the child inherits. The child is
    given a home of its own and told that *that* is real, so that a guard which failed would create a
    database in a temporary directory and nothing else."""
    done = subprocess.run([sys.executable, "-c", CHILD, str(tmp_path)], capture_output=True, text=True, timeout=120,
                          env={**os.environ, "OEISBOT_HOME": str(tmp_path)})
    assert done.returncode == 0, done.stderr[-500:]
    assert "refused: refused under a test: opening the database for writing" in done.stdout
    assert not (tmp_path / "data").exists()


def test_a_child_process_given_its_own_home_is_not_refused(tmp_path):
    """The other half: refusing is about the one real place, not about being a child of a test."""
    code = "from oeisbot import db; c = db.connect(); print(c.execute('select count(*) from attempts').fetchone()[0])"
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
                          env={**os.environ, "OEISBOT_HOME": str(tmp_path)})
    assert done.returncode == 0 and done.stdout.strip() == "0", done.stderr[-500:]
    assert (tmp_path / "data" / "oeisbot.sqlite3").exists()
