from __future__ import annotations

import os

# Before anything of oeisbot is imported: pytest sets PYTEST_CURRENT_TEST only while a test runs, so code
# at import or collection time (a module-level call in a test file, a parametrize list built by calling
# the library) ran with neither the walls below nor the product's own guard. This covers the whole
# session, and every child process inherits it.
os.environ["OEISBOT_UNDER_TEST"] = "1"

import pathlib  # noqa: E402

import pytest  # noqa: E402

_SENTINEL = pathlib.Path(__file__).resolve().parent.parent / "MUTANT_IN_TREE.json"
if _SENTINEL.exists() and os.environ.get("OEISBOT_MUTATING") != "1":
    # data/item58/mutate.py was killed between changing a file and restoring it. The code under test is
    # then not the code, and the changed line may be a safeguard: nothing runs until it is put back.
    raise pytest.UsageError(f"{_SENTINEL} exists: a mutation run was interrupted and left a changed file in the "
                            f"code. Restore it as that file says, delete it, and run again.\n{_SENTINEL.read_text()}")

from oeisbot import db as _db  # noqa: E402
from oeisbot.ingest import bfile as _bfile  # noqa: E402
from oeisbot.ingest import oeisdata as _oeisdata  # noqa: E402

_REAL_GIT = _oeisdata._git
_REAL_CONNECT = _db.connect
_REAL_HTTP_GET = _bfile.http_get


@pytest.fixture(autouse=True)
def _dashboard_answers_the_test_client(monkeypatch):
    """Starlette's TestClient addresses the app as `testserver`, a name the dashboard refuses in real use
    (dashboard.app.ALLOWED_HOSTS). Each test gets its own copy of the set with that name added, so a test may
    also change the set freely."""
    try:
        from oeisbot.dashboard import app as dashboard
    except ImportError:         # the dashboard extra is not installed; its tests skip themselves
        return
    # what a real server starts with. Asserted here because every test below runs with a replaced set, so
    # nothing else would notice the real one being loosened; it also catches a test that leaked its own.
    assert dashboard.ALLOWED_HOSTS == {"127.0.0.1", "localhost", "::1"}
    monkeypatch.setattr(dashboard, "ALLOWED_HOSTS", set(dashboard.ALLOWED_HOSTS) | {"testserver"})


@pytest.fixture(autouse=True)
def _no_test_takes_the_real_writers_lock(monkeypatch, tmp_path_factory):
    """The writers' lock (oeisbot.lock, item 58) lives in the data directory, and several command tests
    run `cli.main` without pointing `config.DATA` anywhere else. Left alone they would take the lock of the
    real `data/` -- and fail whenever `oeisbot daemon` is running, which is every night. A test that has
    moved `config.DATA` keeps its own directory (so a child process given the same OEISBOT_HOME shares the
    lock with it); every other test gets a directory of its own, made only if the lock is touched."""
    from oeisbot import config, lock
    real = config.DATA
    own: list = []

    def directory():
        if config.DATA != real:
            return config.DATA
        if not own:
            own.append(tmp_path_factory.mktemp("writers-lock"))
        return own[0]

    monkeypatch.setattr(lock, "directory", directory)
    # the same for the daemon's own files: a stop request written by a test into the real `data/daemon/`
    # would stop the real daemon that night
    from oeisbot import daemon
    monkeypatch.setattr(daemon, "daemon_dir", lambda: directory() / "daemon")


@pytest.fixture
def real_git():
    """`oeisdata._git` as it really is, for a test of the function itself. The autouse wall below replaces
    the module's name for it; such a test must point it at a command of its own, never at the mirror."""
    return _REAL_GIT


@pytest.fixture
def real_connect():
    """`db.connect` as it really is, past the wall below: for `tests/test_guard.py`, which tests the
    refusal the product itself makes. Anything else that uses it must pass a path of its own."""
    return _REAL_CONNECT


@pytest.fixture
def real_http_get():
    """`bfile.http_get` as it really is, for `tests/test_guard.py` only."""
    return _REAL_HTTP_GET


class ReachedTheRealProject(AssertionError):
    """A test reached for the real database, the real mirror or the network."""


@pytest.fixture(autouse=True)
def _no_test_reaches_the_real_project(monkeypatch):
    """Three doors out of a test, each shut unless the test opens its own.

    Item 58 opened them: `oeisbot daemon` is a command that, run for real, pulls the mirror and writes
    the database, and on 2026-11-22 a mutated copy of it did exactly that from inside a test -- it
    fetched from GitHub and left a lock file in `data/oeisdata/.git` -- because the test had moved
    `config.DATA` and nothing else. `db.connect`'s default path is bound when the module loads, so
    moving `config` does not move it.

    * the database: `db.connect()` of the real file read-write raises. (Read-only is allowed; nothing
      does it today.) A test passes its own path, or replaces `db.connect`.
    * the mirror: `oeisdata._git` raises. A test that syncs replaces it, as the `mirror` fixtures do.
    * oeis.org: `bfile.http_get` raises. A test that fetches replaces it."""
    from oeisbot import config, db
    from oeisbot.ingest import bfile, oeisdata
    real_db, real_connect = config.DB_PATH.resolve(), db.connect

    def connect(path=config.DB_PATH, *, readonly=False):
        if not readonly and path.resolve() == real_db:
            raise ReachedTheRealProject(f"a test opened the real database {real_db} for writing; give it a "
                                        "path of its own, or replace db.connect")
        return real_connect(path, readonly=readonly)

    def git(*args, **kwargs):
        raise ReachedTheRealProject(f"a test ran `git {' '.join(args)}` on the mirror; replace oeisdata._git")

    def http_get(url, *args, **kwargs):
        raise ReachedTheRealProject(f"a test requested {url}; replace bfile.http_get")

    monkeypatch.setattr(db, "connect", connect)
    monkeypatch.setattr(oeisdata, "_git", git)
    monkeypatch.setattr(bfile, "http_get", http_get)
