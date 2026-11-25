"""Local mirror of github.com/oeis/oeisdata and the candidate table built from it (build step 5)."""
from __future__ import annotations

import re
import subprocess
import time
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Iterator

from .. import config, db, estimate, guard
from .seqfile import Entry, parse_file

_KEYWORDS = re.compile(r"^%K A\d{6} (.*)$", re.MULTILINE)
# 'more' entries we never try: every term already shown, or not a real sequence.
# `fini` (the sequence is finite) is not excluded: a `fini,more` entry is finite but still missing terms.
EXCLUDED_KEYWORDS = {"dead", "full", "allocated", "recycled", "dumb"}


# Under `pythonw` (the scheduled daemon) there is no console, and Windows gives every console program a
# new, visible one: a git window on the desktop for the length of the fetch, which someone closes -- and
# closing it kills git in the middle of a reset. This flag starts the child with no window at all.
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class GitTimeout(RuntimeError):
    """A git command on the mirror did not finish in the time it was given, and was ended."""


class MirrorUnusable(RuntimeError):
    """The mirror's working tree was left half rewritten and could not be put back. Nothing may read
    entries from it until a sync succeeds: a file cut off mid-write parses as an entry with a wrong or
    missing term."""


# A lock file git leaves when it is killed is removed only when it is at least this old. A younger one
# may belong to a git that is still running: one orphaned by a killed daemon, or a person's own.
STALE_GIT_LOCK_S = 300.0
_GIT_LOCKS = ("index.lock", "shallow.lock", "HEAD.lock", "packed-refs.lock")
_running: "subprocess.Popen | None" = None       # the git a timed sync is waiting on, for end_running_git


def end_running_git() -> None:
    """End the git command a timed `_git` is waiting on, with everything it started. For a caller that
    is about to end the process from another thread (`daemon.Daemon.hard_exit`). Never raises."""
    proc = _running
    if proc is not None:
        try:
            _end_tree(proc)
        except Exception:       # noqa: BLE001
            pass


def _git(*args: str, cwd: Path | None = None, timeout: float | None = None) -> str:
    """Run git on the mirror and return what it printed. With `timeout` (seconds), a git that has not
    finished by then is ended together with the helpers it started (`git-remote-https`, the LFS filter)
    and `GitTimeout` is raised. Without one it waits for ever, as it always did: a person at a console
    can see that and press Ctrl-C; `oeisbot daemon` cannot, and a stalled fetch would otherwise hold the
    writers' lock into the next day (item 58)."""
    # never from a test (oeisbot.guard): the mirror a command works in, or the one a clone would make
    guard.refuse_if_real(cwd if cwd is not None else config.OEISDATA, f"running `git {' '.join(args[:2])}` on the mirror")
    ssl = ["-c", "http.sslBackend=schannel"] if sys.platform == "win32" else []  # trust the OS certificate store
    argv = ["git", *ssl, *args]
    if timeout is None:
        out = subprocess.run(argv, cwd=cwd, check=True, capture_output=True, text=True, creationflags=NO_WINDOW)
        return out.stdout.strip()
    global _running
    proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            creationflags=NO_WINDOW)
    _running = proc
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _end_tree(proc)
        raise GitTimeout(f"`git {' '.join(args)}` did not finish in {timeout:g} s and was ended") from None
    finally:
        _running = None
    if proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, argv, stdout, stderr)
    return stdout.strip()


def _end_tree(proc: subprocess.Popen) -> None:
    """End a process and everything it started. `Popen.kill` ends git alone; the helper holding the
    connection would live on with the pipes open, and waiting for those pipes would hang in turn."""
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=60,
                           creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        proc.kill()             # also after taskkill: if that failed or is missing, git itself still goes
    except OSError:
        pass
    try:
        proc.communicate(timeout=30)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass        # a helper kept a pipe open: the process is gone, and that is what was asked for


def update(log: Callable[[str], None] = print, *, timeout: float | None = None) -> str:
    """Clone on first use, otherwise fetch the latest snapshot. Returns the commit hash. `timeout` is
    for each git command on its own (see `_git`), and turns on what an unattended caller needs:

    * A git that was killed leaves lock files (`index.lock` from a reset, `shallow.lock` from a shallow
      fetch) that make every later sync fail. Ones at least `STALE_GIT_LOCK_S` old are removed first. A
      younger one is left, and git's own error then ends this sync: it may belong to a git that is still
      running -- the writers' lock covers oeisbot's commands, not an orphan or a person at a prompt.
    * A reset that fails or is ended half way leaves the working tree part old and part new, with the
      file it was writing possibly cut short. The tree is put back to the commit it was on
      (`git reset --hard HEAD`, no network) before the error goes on to the caller; if that cannot be
      done either, `MirrorUnusable` is raised instead, and nothing may read entries until a sync works."""
    repo = config.OEISDATA
    guard.refuse_if_real(repo, "updating the mirror")       # before the lock files below, not only at git
    if not (repo / ".git").exists():
        log(f"cloning {config.OEISDATA_GIT} (shallow) into {repo} ...")
        repo.parent.mkdir(parents=True, exist_ok=True)
        _git("clone", "--depth", "1", "--single-branch", config.OEISDATA_GIT, str(repo), timeout=timeout)
        return _git("rev-parse", "HEAD", cwd=repo, timeout=timeout)
    if timeout is not None:
        for name in _GIT_LOCKS:
            stale = repo / ".git" / name
            try:
                if stale.exists() and time.time() - stale.stat().st_mtime >= STALE_GIT_LOCK_S:
                    log(f"removing {stale}, left by a git command that was ended")
                    stale.unlink()
            except OSError as e:
                log(f"could not remove {stale} ({e})")
    log("fetching latest oeisdata ...")
    _git("fetch", "--depth", "1", "origin", cwd=repo, timeout=timeout)
    try:
        _git("reset", "--hard", "FETCH_HEAD", cwd=repo, timeout=timeout)   # a read-only mirror: no local changes to keep
    except Exception as failed:     # noqa: BLE001 -- whatever it was, the tree may be half rewritten
        if timeout is None:
            raise                   # a person at the console sees git's message and decides
        log(f"the reset failed ({type(failed).__name__}: {failed}); putting the mirror back as it was ...")
        try:
            lock = repo / ".git" / "index.lock"
            if isinstance(failed, GitTimeout) and lock.exists():
                # Ours: the reset this call started was ended by the clock, and left it. Only then. A
                # reset that git itself refused -- "index.lock exists", most likely -- met a lock that
                # was deliberately left alone above because another git may be using the mirror right
                # now; removing it here would undo that. The repair below then fails on the same lock,
                # and the mirror is rightly reported unusable for tonight: someone is rewriting it
                lock.unlink()
            _git("reset", "--hard", "HEAD", cwd=repo, timeout=timeout)
        except Exception as again:  # noqa: BLE001
            raise MirrorUnusable(f"the reset failed ({type(failed).__name__}: {failed}) and so did putting the "
                                 f"mirror back ({type(again).__name__}: {again})") from failed
        raise
    return _git("rev-parse", "HEAD", cwd=repo, timeout=timeout)


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


def sync(conn, log: Callable[[str], None] = print, *, pull: bool = True, timeout: float | None = None) -> dict:
    from ..select import difficulty

    commit = update(log, timeout=timeout) if pull else _git("rev-parse", "HEAD", cwd=config.OEISDATA)
    rows = []
    for entry in iter_more_entries():
        row = sequence_row(entry)
        row.difficulty = difficulty(row)
        rows.append(row)
    db.upsert_sequences(conn, rows)
    # the rows above were built from the entry alone, so their difficulty knows nothing of the b-file
    # facts `fetch-bfiles` stored; recompute from the stored rows, which carry them
    db.refresh_difficulty(conn, difficulty)
    gone = db.mark_not_in_more(conn, {r.a_number for r in rows})
    db.set_meta(conn, "oeisdata_commit", commit)
    db.set_meta(conn, "synced_at", db.now())
    if pull:
        # apart from `synced_at`, which `sync --no-pull` moves too: the daemon asks how old the *data* is
        # before it spends hours a pick on it, and rebuilding the table from an old mirror does not make
        # the mirror new (item 58)
        db.set_meta(conn, "pulled_at", db.now())
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
