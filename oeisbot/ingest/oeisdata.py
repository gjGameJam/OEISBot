"""Local mirror of github.com/oeis/oeisdata and the candidate table built from it (build step 5)."""
from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Iterator

from .. import config, db, estimate
from .seqfile import Entry, parse_file

_KEYWORDS = re.compile(r"^%K A\d{6} (.*)$", re.MULTILINE)
# 'more' entries we never try: every term already shown, or not a real sequence.
# `fini` (the sequence is finite) is not excluded: a `fini,more` entry is finite but still missing terms.
EXCLUDED_KEYWORDS = {"dead", "full", "allocated", "recycled", "dumb"}


def _git(*args: str, cwd: Path | None = None) -> str:
    ssl = ["-c", "http.sslBackend=schannel"] if sys.platform == "win32" else []  # trust the OS certificate store
    out = subprocess.run(["git", *ssl, *args], cwd=cwd, check=True, capture_output=True, text=True)
    return out.stdout.strip()


def update(log: Callable[[str], None] = print) -> str:
    """Clone on first use, otherwise fetch the latest snapshot. Returns the commit hash."""
    repo = config.OEISDATA
    if not (repo / ".git").exists():
        log(f"cloning {config.OEISDATA_GIT} (shallow) into {repo} ...")
        repo.parent.mkdir(parents=True, exist_ok=True)
        _git("clone", "--depth", "1", "--single-branch", config.OEISDATA_GIT, str(repo))
    else:
        log("fetching latest oeisdata ...")
        _git("fetch", "--depth", "1", "origin", cwd=repo)
        _git("reset", "--hard", "FETCH_HEAD", cwd=repo)   # a read-only mirror: no local changes to keep
    return _git("rev-parse", "HEAD", cwd=repo)


def seq_path(a_number: str) -> Path:
    return config.OEISDATA / "seq" / a_number[:4] / f"{a_number}.seq"


def load_entry(a_number: str) -> Entry | None:
    path = seq_path(a_number)
    return parse_file(path) if path.exists() else None


def iter_more_entries() -> Iterator[Entry]:
    for path in sorted((config.OEISDATA / "seq").glob("A*/A*.seq")):
        text = path.read_text(encoding="utf-8", errors="replace")
        m = _KEYWORDS.search(text)
        if not m:
            continue
        kws = {k.strip() for k in m.group(1).split(",")}
        if "more" not in kws or kws & EXCLUDED_KEYWORDS:
            continue
        entry = parse_file(path)
        if entry is not None and entry.data:
            yield entry


def sequence_row(entry: Entry) -> db.SequenceRow:
    last = entry.data[-1] if entry.data else None
    return db.SequenceRow(
        a_number=entry.a_number,
        name=entry.name,
        offset=entry.offset,
        keywords=",".join(entry.keywords),
        data_terms=len(entry.data),
        data_last_digits=len(str(abs(last))) if last is not None else None,
        program_langs=",".join(entry.languages),
        more_credits=entry.more_credits,
        value_dependent=estimate.name_suggests_search(entry.name),
    )


def sync(conn, log: Callable[[str], None] = print, *, pull: bool = True) -> dict:
    from ..select import difficulty

    commit = update(log) if pull else _git("rev-parse", "HEAD", cwd=config.OEISDATA)
    rows = []
    for entry in iter_more_entries():
        row = sequence_row(entry)
        row.difficulty = difficulty(row)
        rows.append(row)
    db.upsert_sequences(conn, rows)
    gone = db.mark_not_in_more(conn, {r.a_number for r in rows})
    db.set_meta(conn, "oeisdata_commit", commit)
    db.set_meta(conn, "synced_at", db.now())
    log(f"oeisdata {commit[:10]}: {len(rows)} candidates with keyword 'more'; {gone} no longer 'more'")
    return {"commit": commit, "candidates": len(rows), "gone": gone}


def program_stats(conn) -> Counter:
    """How many 'more' candidates carry each program language (to decide what to support next)."""
    counts: Counter = Counter()
    total = 0
    for (langs,) in conn.execute("SELECT program_langs FROM sequences WHERE in_more = 1"):
        total += 1
        ls = [l for l in langs.split(",") if l]
        counts.update(ls)
        if not ls:
            counts["(none)"] += 1
    counts["(total)"] = total
    return counts
