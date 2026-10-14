"""Runtime provenance (history item 43): `setup_tools.runtime_versions` and the session-note token.

The probes shell out, so the fakes here are `[sys.executable, "-c", ...]` shims rather than shell
scripts: `config.GP` is a Windows path and a `.sh` would not be executable. `_probe_version` takes its
argv, so a shim can stand in for gp without a fake binary on disk.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from oeisbot import db, setup_tools
from oeisbot.setup_tools import UNKNOWN_VERSION, _probe_version, gp_session_token, runtime_versions

# Real newlines, and it matters: written with a literal backslash-n this fixture is one line already,
# every "collapsed to one line" assertion below is true before the code runs, and a driver keeping only
# the first three banner lines passes the whole suite. That is exactly what happened here until the
# audit caught it -- so if this ever stops containing "\n" characters, the tests stop testing anything.
GP_BANNER = ("                  GP/PARI CALCULATOR Version 2.17.4 (released)\n"
             "          amd64 running mingw (x86-64/GMP-6.1.2 kernel) 64-bit version\n"
             "               compiled: Jun 20 2026, gcc version 14-posix (GCC)\n"
             "               threading engine: single\n"
             "               (readline not compiled in, extended help enabled)")


def test_the_banner_fixture_really_is_multi_line():
    """Guards the guard: every assertion about collapsing depends on this, and the failure is silent."""
    assert GP_BANNER.count("\n") == 4 and "\\n" not in GP_BANNER


def shim(*, stdout: str = "", stderr: str = "", code: int = 0) -> list[str]:
    """argv for a fake runtime writing the given text to each stream and exiting with `code`."""
    return [sys.executable, "-c",
            f"import sys; sys.stdout.write({stdout!r}); sys.stderr.write({stderr!r}); sys.exit({code})"]


def test_the_gp_probe_reads_stderr_not_stdout():
    """gp writes `--version` to stderr. A probe reading stdout records an empty string and nothing says
    so, which is the single most likely defect in this item -- so both directions are pinned."""
    assert "GP/PARI" in _probe_version(shim(stderr=GP_BANNER), stderr=True, must_contain="GP/PARI")
    # the same banner on stdout only: a stderr-reading probe must find nothing
    assert _probe_version(shim(stdout=GP_BANNER), stderr=True, must_contain="GP/PARI") == UNKNOWN_VERSION
    # ...and a stdout-reading probe must not be fooled by stderr either
    assert _probe_version(shim(stderr=GP_BANNER), stderr=False, must_contain="GP/PARI") == UNKNOWN_VERSION


def test_the_whole_banner_is_kept_on_one_line():
    """Not the first two lines: `compiled:` is the only thing that tells two builds of one version on one
    GMP apart, and a fixed line count would record the wrong half if the banner were ever reordered."""
    got = _probe_version(shim(stderr=GP_BANNER), stderr=True, must_contain="GP/PARI")
    assert "\n" not in got and "  " not in got            # collapsed to a single line, no runs of spaces
    assert "Version 2.17.4" in got                        # line 1
    assert "GMP-6.1.2" in got                             # line 2: the kernel, which is the point
    assert "compiled: Jun 20 2026" in got                 # line 3
    assert "extended help enabled" in got                 # line 5


@pytest.mark.parametrize("argv, why", [
    (shim(stderr=GP_BANNER, code=1), "a non-zero exit"),
    (shim(stdout="", stderr=""), "no output at all"),
    (shim(stderr="bash: gp: command not found"), "exit 0 with text that is not a gp banner"),
    (shim(stderr="Sage Version 10.4, Release Date: 2024-07-19"), "exit 0 from something else entirely"),
    ([str(sys.executable) + "-does-not-exist", "--version"], "a missing binary"),
])
def test_a_probe_that_cannot_be_trusted_yields_unknown(argv, why):
    """The dangerous case is not a probe that fails -- that is discarded -- but one that exits 0 with the
    wrong text, which would be written to the database as provenance."""
    assert _probe_version(argv, stderr=True, must_contain="GP/PARI") == UNKNOWN_VERSION, why


def test_the_last_shim_case_really_is_exit_zero():
    """The `must_contain` guard is what rejects it, not the exit code -- otherwise the case above would
    pass for the wrong reason (history item 41: an over-long-line test passed on the rate ceiling)."""
    res = subprocess.run(shim(stderr="bash: gp: command not found"), capture_output=True, text=True)
    assert res.returncode == 0 and "GP/PARI" not in res.stderr


def test_no_probe_failure_ever_raises(monkeypatch):
    """`run_session` builds its note before its own try/finally, so an exception here kills `oeisbot run`
    having done nothing. Every failure shape is one non-event -- a list of the errors imagined in advance
    would miss the antivirus file lock and the decode failure, so the catch is `except Exception`."""
    for boom in (subprocess.TimeoutExpired(cmd="gp", timeout=10), PermissionError(13, "locked"),
                 OSError("antivirus"), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"), MemoryError()):
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(boom))
        assert _probe_version(["gp"], stderr=True, must_contain="GP/PARI") == UNKNOWN_VERSION


def test_ctrl_c_during_a_probe_still_stops_the_command(monkeypatch):
    """The other half of the rule above, and the reason the catch is `except Exception` rather than
    `except BaseException`: a provenance probe must swallow every *error*, and must not swallow the
    user's Ctrl-C. Swallowing it would make `oeisbot run` unstoppable during the probe."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        _probe_version(["gp"], stderr=True, must_contain="GP/PARI")


def test_a_wrapper_that_prints_a_warning_first_is_still_accepted():
    """The `must_contain` guard is a sanity check, not authentication: a real gp behind a wrapper that
    writes a line of its own still records its version, which is the wanted behaviour."""
    got = _probe_version(shim(stderr="WARNING: using a wrapper\n" + GP_BANNER),
                         stderr=True, must_contain="GP/PARI")
    assert "Version 2.17.4" in got and "GMP-6.1.2" in got


def test_the_value_is_capped_before_it_is_written():
    cap = setup_tools.RUNTIME_VERSION_CHARS
    got = _probe_version(shim(stderr="GP/PARI " + "word " * cap), stderr=True, must_contain="GP/PARI")
    assert 0 < len(got) <= cap
    # ends on a whole word. `assert not got.endswith("wor")` would pass without the cut too -- the naive
    # 300-character slice of this fixture ends "word wo" -- so it has to name the word itself
    assert got.endswith("word") and len(got) == 297


def test_a_word_that_fits_exactly_is_not_thrown_away():
    """The cut asks whether it actually split a word. Without that test it fires whenever the text is
    over the cap, discarding a complete final word -- losing the GMP kernel from roughly one over-cap
    banner in seven, for nothing."""
    cap = setup_tools.RUNTIME_VERSION_CHARS
    head = "GP/PARI " + "y" * (cap - len("GP/PARI ") - len("GMP-6.1.2") - 1) + " GMP-6.1.2"
    assert len(head) == cap                      # ...so the next character is the space before the tail
    got = _probe_version(shim(stderr=head + " and more text past the cap"), stderr=True,
                         must_contain="GP/PARI")
    assert got.endswith("GMP-6.1.2") and len(got) == cap


def test_the_cap_never_writes_a_truncated_version_into_a_session_note():
    """`gp_session_token` parses the *stored* value, and a note is never rewritten -- so a version
    number cut in half by the cap would become a plausible, wrong, permanent record. Dropping the
    straddling word makes it an honest `unknown` instead."""
    cap = setup_tools.RUNTIME_VERSION_CHARS
    # pad so that `2.17.4` straddles the limit exactly
    head = "GP/PARI " + "p" * (cap - len("GP/PARI  Version 2.17") - 1) + " Version 2.17.4 (released)"
    assert head.index("2.17.4") < cap < head.index("2.17.4") + len("2.17.4")
    got = _probe_version(shim(stderr=head), stderr=True, must_contain="GP/PARI")
    assert "2.17" not in got, got[-40:]
    assert gp_session_token(got) == "gp=unknown"


def test_a_wrapper_whose_preamble_runs_past_the_cap_is_not_recorded_as_gp():
    """The guard must be checked on the value that is STORED. Checking the full text would let 300
    characters of a wrapper's own output into `meta` as `gp_version` while the session note, parsed
    from the same value, said `gp=unknown` -- the two records disagreeing about the same run."""
    preamble = "WARNING: managed PARI build, see the intranet page. " * 8
    assert len(preamble) > setup_tools.RUNTIME_VERSION_CHARS
    got = _probe_version(shim(stderr=preamble + "GP/PARI CALCULATOR Version 2.17.4"),
                         stderr=True, must_contain="GP/PARI")
    assert got == UNKNOWN_VERSION


def test_runtime_versions_probes_the_configured_binaries(monkeypatch):
    """Always `config.GP` and `config.SANDBOX_PYTHON`, never a PATH lookup: the recorded version must be
    the binary the harness invokes. `-f` mirrors `verify.Harness.argv`, so a broken gprc cannot reach it."""
    seen = []

    def fake_run(argv, **kwargs):
        seen.append((argv, kwargs))
        text = GP_BANNER if "--version" in argv else "Python 3.11.9 (main) [MSC v.1938 64 bit (AMD64)]"
        stream = "stderr" if "--version" in argv else "stdout"
        return subprocess.CompletedProcess(argv, 0, **{stream: text, ("stdout" if stream == "stderr" else "stderr"): ""})

    monkeypatch.setattr(subprocess, "run", fake_run)
    got = runtime_versions()
    assert set(got) == {"gp_version", "sandbox_python_version"}
    assert "GMP-6.1.2" in got["gp_version"] and "Python 3.11.9" in got["sandbox_python_version"]

    gp_argv, gp_kwargs = seen[0]
    assert gp_argv[0] == str(setup_tools.config.GP) and "-f" in gp_argv and "--version" in gp_argv
    assert seen[1][0] == [str(setup_tools.config.SANDBOX_PYTHON), "-VV"]
    for _argv, kwargs in seen:
        assert kwargs["stdin"] is subprocess.DEVNULL      # gp is a REPL: never let it read a tty
        assert kwargs["encoding"] == "utf-8"              # not the ANSI codepage subprocess defaults to
        assert kwargs["check"] is False
        assert kwargs["timeout"] == setup_tools.RUNTIME_PROBE_TIMEOUT_S


@pytest.mark.parametrize("banner, token", [
    (GP_BANNER, "gp=2.17.4/GMP-6.1.2"),
    ("GP/PARI CALCULATOR Version 2.17.4 (released) amd64 (x86-64 kernel)", "gp=2.17.4"),   # a non-GMP build
    (UNKNOWN_VERSION, "gp=unknown"),
    ("", "gp=unknown"),
])
def test_the_session_token_is_short_and_says_which_kernel(banner, token):
    """The whole banner would swamp the dashboard's Settings column, which renders `sessions.note`."""
    assert gp_session_token(banner) == token
    assert len(gp_session_token(banner)) <= 40


def test_a_real_gp_banner_round_trips():
    """The fixture above is a copy; this pins it against the shape the parser actually has to handle."""
    assert gp_session_token(_probe_version(shim(stderr=GP_BANNER), stderr=True,
                                           must_contain="GP/PARI")) == "gp=2.17.4/GMP-6.1.2"


def test_setup_records_the_versions_it_installed(tmp_path, monkeypatch):
    """`oeisbot setup` is the other place the versions are written, and the one that runs on a fresh
    machine. The installers are stubbed out: this is about the provenance write, not the downloads.
    (Found by mutation -- removing this write was the one change in the item nothing caught.)"""
    for name in ("install_python", "install_gp", "grant_access"):
        monkeypatch.setattr(setup_tools, name, lambda log=None: None)
    for name in ("DATA", "TOOLS", "ARTIFACTS", "BFILE_CACHE", "SCRATCH"):
        monkeypatch.setattr(setup_tools.config, name, tmp_path / name.lower())
    monkeypatch.setattr(setup_tools, "runtime_versions",
                        lambda: {"gp_version": "GP/PARI CALCULATOR Version 8.8.8",
                                 "sandbox_python_version": "Python 8.8.8"})
    # `db.connect`'s path is a default argument, evaluated at import: patching config.DB_PATH is too late
    db_path = tmp_path / "t.sqlite3"
    real_connect = db.connect          # captured before the patch, or the replacement calls itself
    monkeypatch.setattr(setup_tools_db(), "connect", lambda *a, **k: real_connect(db_path))

    lines: list[str] = []
    setup_tools.setup(log=lines.append)

    conn = db.connect(db_path)
    assert db.get_meta(conn, "gp_version") == "GP/PARI CALCULATOR Version 8.8.8"
    assert db.get_meta(conn, "sandbox_python_version") == "Python 8.8.8"
    conn.close()
    assert any("gp_version" in line for line in lines)      # and says so, so a fresh setup is checkable


def setup_tools_db():
    """`setup_tools.setup` imports `db` lazily inside the function, so the name to patch is the module
    itself, not an attribute of `setup_tools`."""
    from oeisbot import db as db_module
    return db_module


def test_meta_round_trips_a_version_string(tmp_path):
    """`meta` had no direct test before this item, though `sync` has written to it since session 1."""
    conn = db.connect(tmp_path / "t.sqlite3")
    banner = _probe_version(shim(stderr=GP_BANNER), stderr=True, must_contain="GP/PARI")
    db.set_meta(conn, "gp_version", banner)
    assert db.get_meta(conn, "gp_version") == banner
    db.set_meta(conn, "gp_version", UNKNOWN_VERSION)            # upgraded, or the probe stopped working
    assert db.get_meta(conn, "gp_version") == UNKNOWN_VERSION   # overwritten, not duplicated
    assert db.get_meta(conn, "never_written") is None
    conn.close()
