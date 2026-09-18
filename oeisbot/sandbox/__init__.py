"""Run untrusted programs under hard resource limits. Every other safeguard assumes this works.

    result = sandbox.run([exe, *args], cwd=scratch_dir, limits=Limits(wall_s=60), on_line=cb)
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

from .. import config
from .types import Limits, RunResult, Status

if sys.platform == "win32":
    from .windows import avail_phys_bytes, run
else:
    from .posix import avail_phys_bytes, run

__all__ = ["Limits", "RunResult", "Status", "run", "avail_phys_bytes", "new_scratch_dir", "runtime_problems"]


def new_scratch_dir(label: str) -> Path:
    """A fresh working directory under the (sandbox-writable) scratch root."""
    d = config.SCRATCH / f"{label}-{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True)
    return d


def runtime_problems() -> list[str]:
    """What is missing before sandboxed runs can work (empty list = ready)."""
    problems = []
    if not config.SANDBOX_PYTHON.exists():
        problems.append(f"sandbox Python missing at {config.SANDBOX_PYTHON} (run `oeisbot setup`)")
    if not config.GP.exists():
        problems.append(f"PARI/GP missing at {config.GP} (run `oeisbot setup`)")
    if not config.SCRATCH.exists():
        problems.append(f"scratch root missing at {config.SCRATCH} (run `oeisbot setup`)")
    return problems
