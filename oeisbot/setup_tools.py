"""`oeisbot setup`: install the sandbox runtimes under tools/ and grant the sandbox access to them.

The sandbox cannot read the normal Python install (it lives under the user profile), so jobs
use a private embeddable CPython plus a standalone gp.exe, both readable by the container.
"""
from __future__ import annotations

import hashlib
import os
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

    db.connect().close()
    log(f"database: {config.DB_PATH}")
