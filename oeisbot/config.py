"""Paths and budgets. Everything lives under the project root unless OEISBOT_HOME is set."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(os.environ.get("OEISBOT_HOME", Path(__file__).resolve().parent.parent))

DATA = ROOT / "data"
TOOLS = ROOT / "tools"
ARTIFACTS = ROOT / "artifacts"

OEISDATA = DATA / "oeisdata"          # git clone of github.com/oeis/oeisdata
BFILE_CACHE = DATA / "bfiles"         # permanent b-file cache (b-files are not in the git repo)
SCRATCH = DATA / "scratch"            # per-run sandbox working directories
DB_PATH = DATA / "oeisbot.sqlite3"

SANDBOX_PYTHON_DIR = TOOLS / "python"  # embeddable CPython, readable by the sandbox
SANDBOX_PYTHON = SANDBOX_PYTHON_DIR / "python.exe"
PARI_DIR = TOOLS / "pari"
GP = PARI_DIR / "gp.exe"

OEIS_URL = "https://oeis.org"
OEISDATA_GIT = "https://github.com/oeis/oeisdata.git"
USER_AGENT = "OEISBot-triage/0.1 (local, single-user, rate-limited to 1 req/s)"
HTTP_MIN_INTERVAL_S = 1.0

# local code model (step 7): Ollama by default; any OpenAI-compatible server also works
MODEL_API = os.environ.get("OEISBOT_MODEL_API", "ollama")            # 'ollama' | 'openai'
MODEL_URL = os.environ.get("OEISBOT_MODEL_URL", "http://127.0.0.1:11434")
MODEL_NAME = os.environ.get("OEISBOT_MODEL", "qwen2.5-coder:14b")
MODEL_CONTEXT = int(os.environ.get("OEISBOT_MODEL_CONTEXT", "8192"))   # 14B weights + 8k KV cache fit in 12 GB VRAM
CODEGEN_ATTEMPTS = 3
CODEGEN_HELD_OUT_MIN = 2                                  # known terms always hidden from the model
CODEGEN_MIN_KNOWN_TERMS = CODEGEN_HELD_OUT_MIN + 1        # fewer known terms: no model generation

GiB = 1 << 30
MiB = 1 << 20


@dataclass(frozen=True)
class Budgets:
    verify_wall_s: float = 600.0            # reproduce every known term within this
    extend_wall_s: float = 3 * 3600.0       # then keep going for new terms up to this
    session_attempt_cap: int = 25
    mem_bytes: int = 6 * GiB                # hard commit cap for a job
    reserve_phys_bytes: int = 3 * GiB       # keep this much physical RAM free: never page
    disk_bytes: int = 512 * MiB             # scratch dir cap
    reserve_disk_bytes: int = 8 * GiB       # stop any job if free disk drops below this
    over_prediction_factor: float = 2.0     # kill a term running this far past its projection
    max_new_terms: int = 200


DEFAULT_BUDGETS = Budgets()
