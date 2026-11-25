"""The suite's own walls (tests/conftest.py): no test reaches the real database, mirror or network."""
from __future__ import annotations

import pytest

from oeisbot import config, db
from oeisbot.ingest import bfile, oeisdata

from .conftest import ReachedTheRealProject


def test_the_real_database_cannot_be_opened_for_writing():
    with pytest.raises(ReachedTheRealProject, match="opened the real database"):
        db.connect()
    with pytest.raises(ReachedTheRealProject):
        db.connect(config.DB_PATH)
    with pytest.raises(ReachedTheRealProject):
        db.connect(config.DATA / "." / "oeisbot.sqlite3")          # however the path is spelled


def test_a_database_of_the_tests_own_opens_as_ever(tmp_path):
    conn = db.connect(tmp_path / "t.sqlite3")
    try:
        assert conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 0
    finally:
        conn.close()


def test_git_and_oeis_org_are_out_of_reach():
    with pytest.raises(ReachedTheRealProject, match="git fetch"):
        oeisdata._git("fetch", "--depth", "1", "origin", cwd=config.OEISDATA)
    # an update of the real mirror is stopped one step earlier still, by the product's own guard
    from oeisbot.guard import RealProjectRefused
    with pytest.raises(RealProjectRefused, match="updating the mirror"):
        oeisdata.update(lambda m: None)
    with pytest.raises(ReachedTheRealProject, match="requested https://oeis.org"):
        bfile.http_get("https://oeis.org/A000045/b000045.txt")
    with pytest.raises(ReachedTheRealProject):
        bfile.fetch_entry_text("A000045")


def test_the_command_that_started_this_cannot_run_a_real_night(monkeypatch):
    """What happened on 2026-11-22, replayed: `oeisbot daemon` reached with nothing stubbed. It must stop
    at the first wall (the database) having pulled nothing."""
    from oeisbot import cli, daemon
    monkeypatch.setattr(daemon, "keep_awake", lambda on: pytest.fail("it got as far as starting a night"))
    monkeypatch.setattr(daemon.Daemon, "run", lambda self: pytest.fail("a real night was started"))
    # first door: it is not armed, so it does nothing at all (exit 2) -- no lock, no database
    assert cli.main(["daemon", "--window", "always"]) == 2
    log = lambda: "".join(p.read_text(encoding="utf-8") for p in daemon.daemon_dir().glob("daemon-*.log"))   # noqa: E731
    assert "not started: not armed" in log()
    # second door: even armed (in the test's own directory), the database is refused
    daemon.arm()
    assert cli.main(["daemon", "--window", "always"]) == 1
    assert "not started: the database could not be opened (ReachedTheRealProject: a test opened the real database" in log()
    assert config.DATA not in daemon.daemon_dir().parents        # and that log is not the real one


def test_the_daemons_own_files_are_not_the_real_ones():
    """A stop request written into the real `data/daemon/` by a test would stop the real daemon that
    night. Like the writers' lock, the daemon's directory is the test's own unless the test moved
    `config.DATA` itself."""
    from oeisbot import daemon, lock
    assert config.DATA not in daemon.stop_path().parents
    assert daemon.daemon_dir().parent == lock.directory()
    assert daemon.heartbeat_path().parent == daemon.daemon_dir()
    daemon.request_stop()
    assert daemon.stop_path().exists() and not (config.DATA / "daemon" / "stop").exists()
