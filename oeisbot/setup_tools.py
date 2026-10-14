"""`oeisbot setup`: install the sandbox runtimes under tools/ and grant the sandbox access to them.

The sandbox cannot read the normal Python install (it lives under the user profile), so jobs
use a private embeddable CPython plus a standalone gp.exe, both readable by the container.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from . import config

PYTHON_EMBED_URL = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
GP_URL = "https://pari.math.u-bordeaux.fr/pub/pari/windows/gp64-2-17-4.exe"
SANDBOX_PACKAGES = ["gmpy2", "sympy"]


def _download(url: str, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as f:
        while chunk := resp.read(1 << 20):
            h.update(chunk)
            f.write(chunk)
    tmp.replace(dest)
    return h.hexdigest()


def install_python(log=print) -> None:
    target = config.SANDBOX_PYTHON_DIR
    if not config.SANDBOX_PYTHON.exists():
        zpath = config.TOOLS / "downloads" / Path(PYTHON_EMBED_URL).name
        digest = _download(PYTHON_EMBED_URL, zpath)
        log(f"downloaded {zpath.name} sha256={digest}")
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(target)
    # the ._pth file fixes sys.path; add site-packages for gmpy2
    pth = next(target.glob("python*._pth"))
    lines = pth.read_text().splitlines()
    if "Lib\\site-packages" not in lines:
        lines.insert(2, "Lib\\site-packages")
        pth.write_text("\n".join(lines) + "\n")
    site = target / "Lib" / "site-packages"
    missing = [p for p in SANDBOX_PACKAGES if not (site / p).exists()]
    if missing:
        site.mkdir(parents=True, exist_ok=True)
        uv = shutil.which("uv")
        if uv:
            cmd = [uv, "pip", "install", "--target", str(site), "--python-version", "3.11",
                   "--python-platform", "x86_64-pc-windows-msvc", "--only-binary", ":all:",
                   "--link-mode", "copy", *missing]  # copies inherit the directory ACL; hardlinks keep the cache's
        else:
            cmd = [sys.executable, "-m", "pip", "install", "--target", str(site), "--only-binary=:all:",
                   "--platform", "win_amd64", "--python-version", "3.11", *missing]
        # UV_SYSTEM_CERTS: trust the Windows certificate store (TLS-inspecting antivirus/proxies)
        subprocess.run(cmd, check=True, env={**os.environ, "UV_SYSTEM_CERTS": "1"})
        # the sandbox cannot write __pycache__, so compile once here (host and sandbox are both 3.11)
        subprocess.run([sys.executable, "-m", "compileall", "-q", str(site)], check=False)
    log(f"sandbox python: {target} with {', '.join(SANDBOX_PACKAGES)}")


def install_gp(log=print) -> None:
    if config.GP.exists():
        log(f"gp: present at {config.GP}")
        return
    digest = _download(GP_URL, config.GP)
    log(f"gp: downloaded {GP_URL} sha256={digest}")


# ------------------------------------------------------------------ runtime provenance
#
# `attempts.program_sha` hashes `Program.executed`, so the program text -- driver and all -- is pinned
# for free. The *runtime* that ran it is not: "which gp produced this result" cannot be recovered
# afterwards, and it matters, because `ispseudoprime` and the precision defaults live in the GMP kernel
# rather than in the program. Recorded from 2026-09-23 (history item 43); rows written before then are
# genuinely unattributable and are deliberately not backfilled -- inventing a version would be worse
# than the gap.
RUNTIME_VERSION_CHARS = 300        # the collapsed gp banner is ~230; the cap applies before the write
RUNTIME_PROBE_TIMEOUT_S = 10
UNKNOWN_VERSION = "unknown"
_GP_VERSION_RE = re.compile(r"Version\s+([\w.]+)")
_GP_KERNEL_RE = re.compile(r"(GMP-[\w.]+)")


def _probe_version(argv: list[str], *, stderr: bool, must_contain: str) -> str:
    """One runtime's version banner as a single capped line, or `UNKNOWN_VERSION`.

    **Never raises.** `oeisbot setup` and `oeisbot run` must not abort because a provenance probe
    failed: `run_session` builds its session note *before* its own try/finally, so an exception here
    would kill the command having done nothing at all. `except Exception` rather than a list of the
    errors imagined in advance, as `attempt._note_failure` and `_discard_pending` do for the same
    reason -- a locked file, an AppContainer ACL or a decode failure are all the same non-event here.

    `must_contain` is the point of the function, not decoration: the dangerous case is not a probe that
    fails, which is discarded, but one that **exits 0 with the wrong text** -- `config.GP` pointing at a
    shim, or a wrapper printing a warning first. Without it a plausible-looking string is written to the
    database as provenance and nothing ever says otherwise."""
    try:
        res = subprocess.run(argv, capture_output=True, timeout=RUNTIME_PROBE_TIMEOUT_S,
                             stdin=subprocess.DEVNULL,        # gp is a REPL: never let it read a tty
                             encoding="utf-8", errors="replace",   # not the ANSI codepage subprocess defaults to
                             check=False)
    except Exception:
        return UNKNOWN_VERSION
    if res.returncode != 0:
        return UNKNOWN_VERSION
    # every line, not the first two: the `compiled:` line is the only thing that tells two builds of one
    # version on one GMP apart, and keeping a fixed number of lines would silently record the wrong half
    # if a future banner were reordered
    text = " ".join((res.stderr if stderr else res.stdout).split())
    value = text[:RUNTIME_VERSION_CHARS]
    if len(text) > RUNTIME_VERSION_CHARS and text[RUNTIME_VERSION_CHARS] != " ":
        # The cut landed inside a word, so drop that word: `gp_session_token` parses this value, and
        # `Version 2.17.4` truncated to `Version 2.17` would write a plausible, WRONG version into a
        # session note that is never rewritten -- an honest `unknown` is worth more. The `!= " "` asks
        # whether a word was actually split; without it a complete word that fitted exactly would be
        # thrown away too. Conditional on there being a space at all: a space-free blob longer than the
        # cap is still truncated mid-token, which no gp banner can be (`" ".join(...split())` above).
        value = value.rsplit(" ", 1)[0]
    # checked on the value that is STORED, not on the full text: a wrapper whose preamble ran past the
    # cap would otherwise pass the check and write 300 characters of its own output in as provenance
    return value if must_contain in value else UNKNOWN_VERSION


def runtime_versions() -> dict[str, str]:
    """The versions of the two runtimes the sandbox actually runs, for `meta`.

    Always `config.GP` and `config.SANDBOX_PYTHON`, never a PATH lookup: the recorded version has to be
    the binary `verify.Harness.argv` invokes, and a `shutil.which("gp")` would record a different one's
    version as fact. `-f` mirrors `Harness.argv`, so a broken gprc cannot reach the probe either."""
    return {
        "gp_version": _probe_version([str(config.GP), "-f", "--version"], stderr=True, must_contain="GP/PARI"),
        "sandbox_python_version": _probe_version([str(config.SANDBOX_PYTHON), "-VV"], stderr=False,
                                                 must_contain="Python "),
    }


def gp_session_token(gp_version: str) -> str:
    """`gp=2.17.4/GMP-6.1.2` for a session note: the whole banner would swamp the dashboard's Settings
    column (`dashboard/src/views.tsx`), which renders `sessions.note` verbatim. The note is the half of
    this that lasts -- `meta` is overwritten the next time gp changes, so after an upgrade it describes
    no historical row at all, while a note is written once and never touched again."""
    version = _GP_VERSION_RE.search(gp_version)
    kernel = _GP_KERNEL_RE.search(gp_version)
    if version is None:
        return f"gp={UNKNOWN_VERSION}"
    return f"gp={version.group(1)}" + (f"/{kernel.group(1)}" if kernel else "")


def grant_access(log=print) -> None:
    config.SCRATCH.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        log("non-Windows: no AppContainer ACLs to set")
        return
    from .sandbox import windows

    _, sid = windows.appcontainer_sid()
    windows.grant(config.SANDBOX_PYTHON_DIR, "RX")
    windows.grant(config.PARI_DIR, "RX")
    windows.grant(config.SCRATCH, "M")
    log(f"AppContainer {windows.APPCONTAINER_NAME} ({sid}): read {config.SANDBOX_PYTHON_DIR}, {config.PARI_DIR}; modify {config.SCRATCH}")


def setup(log=print) -> None:
    for d in (config.DATA, config.TOOLS, config.ARTIFACTS, config.BFILE_CACHE, config.SCRATCH):
        d.mkdir(parents=True, exist_ok=True)
    install_python(log)
    install_gp(log)
    grant_access(log)
    from . import db

    # probed before the connection is opened, so `versions` cannot be read unbound if this block ever
    # grows an `except`, and written as ONE transaction, so a crash cannot leave a fresh gp version
    # beside a stale Python one
    versions = runtime_versions()
    conn = db.connect()
    try:
        db.set_meta_many(conn, versions)
    finally:
        conn.close()
    log(f"database: {config.DB_PATH}")
    for key, value in versions.items():
        log(f"{key}: {value}")
