"""The last line of defence between a test and the real project (item 58).

On 2026-11-22 a mutated copy of `oeisbot daemon`, run from inside a test, opened the real database and
ran a real `git fetch` on the real mirror. The test had moved `config.DATA` and nothing else, and nothing
in the product knew it was being tested. `tests/conftest.py` has walls against that now, but they are
replaced functions in the test's own process: a child process, or a test that reaches the real function
some other way, walks past them.

This module is the same refusal made by the product itself, where it cannot be walked past:

* `refuse_if_real(path, what)`: under a test, anything that would *write* inside this installation's own
  `data/` or `artifacts/` is refused -- opening the database for writing, taking the writers' lock,
  leaving a stop request, arming the daemon, running git on the mirror.
* `refuse_network(what)`: under a test, a request to oeis.org is refused. A test that needs one replaces
  `bfile.http_get`; the real one is never the thing under test.

"Under a test" is pytest's own environment variable, `PYTEST_CURRENT_TEST`, which pytest sets for the
length of each test and which every child process inherits -- so a subprocess started by a test is
covered too. `OEISBOT_UNDER_TEST=1` says the same for a script that is not pytest (a mutation harness, an
experiment).

"This installation's own" is decided from where this file is, never from `config`: a test that points
`config.DATA` at a temporary directory may do what it likes there, and a child process given its own
`OEISBOT_HOME` likewise. What is refused is the one place that is real.

Reading is never refused: the dashboard, `queue` and a read-only connection look at the real data by
design, and a test may too.
"""
from __future__ import annotations

import os
from pathlib import Path

INSTALL_ROOT = Path(__file__).resolve().parent.parent
REAL_DIRS = (INSTALL_ROOT / "data", INSTALL_ROOT / "artifacts")


class RealProjectRefused(RuntimeError):
    """Code running under a test tried to change the real project, or to contact oeis.org."""


def under_test() -> bool:
    """`OEISBOT_UNDER_TEST` set to anything but nothing or `0` counts: a harness that wrote `true` or
    `yes` meant yes, and a safeguard that needs the exact spelling is one typo from being off."""
    return "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("OEISBOT_UNDER_TEST", "").strip() not in ("", "0")


def is_real(path: Path | str) -> bool:
    """Whether `path` is inside this installation's own `data/` or `artifacts/`, however it is spelled:
    relative, in another case, with `..`, as a short name, or with Windows' `\\?\` prefix (which
    `resolve` keeps, and which would otherwise walk straight past the comparison). A path that cannot be
    resolved is taken as real: this is asked only before a write, and when in doubt the answer that
    refuses is the safe one."""
    text = str(path)
    for prefix in ("\\\\?\\UNC\\", "\\\\?\\", "\\\\.\\"):
        if text.startswith(prefix):
            text = ("\\\\" if "UNC" in prefix else "") + text[len(prefix):]
            break
    try:
        resolved = Path(text).resolve()
    except (OSError, ValueError):
        return True
    return any(resolved == real or real in resolved.parents for real in REAL_DIRS)


def refuse_if_real(path: Path | str, what: str) -> None:
    if under_test() and is_real(path):
        raise RealProjectRefused(f"refused under a test: {what} ({path}) is in the real project. Give the test "
                                 "a directory of its own (move config.DATA, or set OEISBOT_HOME for a child process)")


def refuse_network(what: str) -> None:
    if under_test():
        raise RealProjectRefused(f"refused under a test: {what} would contact oeis.org. Replace bfile.http_get "
                                 "in the test")
