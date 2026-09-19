"""B-files: fetched from oeis.org (they are not in the git repo), cached permanently, rate-limited.

The b-file is the source of truth for known terms; the DATA line shows only the first few.
A 404 means the sequence has no b-file, which is normal, and is cached too.
"""
from __future__ import annotations

import hashlib
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .. import config
from ..terms import KnownTerms
from .seqfile import Entry

sys.set_int_max_str_digits(0)

_lock = threading.Lock()
_last_request = 0.0


def _throttle() -> None:
    global _last_request
    with _lock:
        wait = _last_request + config.HTTP_MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


class UnexpectedResponse(RuntimeError):
    """oeis.org answered, but not with what was asked for (e.g. an HTML error page)."""


def http_get(url: str, timeout: float = 60) -> bytes | None:
    """GET with the global 1 request/second limit. Returns None on 404."""
    _throttle()
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def number(a_number: str) -> str:
    return a_number[1:]


def bfile_url(a_number: str) -> str:
    return f"{config.OEIS_URL}/{a_number}/b{number(a_number)}.txt"


def cache_path(a_number: str) -> Path:
    return config.BFILE_CACHE / a_number[:4] / f"b{number(a_number)}.txt"


@dataclass
class BFile:
    a_number: str
    values: dict[int, int]
    malformed: list[str] = field(default_factory=list)
    duplicates: list[int] = field(default_factory=list)

    @property
    def last_index(self) -> int:
        return max(self.values)


def parse_bfile(a_number: str, text: str) -> BFile:
    values: dict[int, int] = {}
    b = BFile(a_number, values)
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        try:
            n, v = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            b.malformed.append(line[:120])
            continue
        if len(parts) > 2 and not parts[2].startswith("#"):
            b.malformed.append(line[:120])
        if n in values:
            b.duplicates.append(n)
        values[n] = v
    return b


@dataclass(frozen=True)
class LfsPointer:
    sha256: str
    size: int


def lfs_pointer(a_number: str) -> LfsPointer | None | bool:
    """oeisdata keeps a Git LFS pointer (hash and size) for every supporting file, b-files included.
    Returns the pointer, None if the snapshot has no b-file, or False if there is no snapshot."""
    if not (config.OEISDATA / "files").is_dir():
        return False
    path = config.OEISDATA / "files" / a_number[:4] / f"b{number(a_number)}.txt"
    if not path.exists():
        return None
    fields = dict(line.split(" ", 1) for line in path.read_text().splitlines() if " " in line)
    return LfsPointer(fields["oid"].removeprefix("sha256:"), int(fields["size"]))


def cached(a_number: str) -> tuple[bool, BFile | None]:
    """What `fetch` (without `refresh`) returns, when that is decided without a request: (True, the b-file or
    None). (False, None) when only a download could tell. `fetch` uses this, so the two cannot disagree."""
    pointer = lfs_pointer(a_number)
    if pointer is None:
        return True, None
    path = cache_path(a_number)
    if path.exists() and (pointer is False or hashlib.sha256(path.read_bytes()).hexdigest() == pointer.sha256):
        return True, parse_bfile(a_number, path.read_text(encoding="utf-8", errors="replace"))
    if pointer is False and not path.exists() and path.with_suffix(".absent").exists():
        return True, None
    return False, None


def fetch(a_number: str, *, refresh: bool = False) -> BFile | None:
    """The b-file from cache, or from oeis.org. None if the sequence has no b-file.

    Without `refresh`, the oeisdata LFS pointer decides: no pointer means no b-file (no request);
    a cached copy is reused only while its sha256 matches the pointer. With `refresh`, always asks
    oeis.org (the snapshot can lag the live site)."""
    if not refresh:
        decided, bf = cached(a_number)
        if decided:
            return bf
    path = cache_path(a_number)
    absent = path.with_suffix(".absent")
    body = http_get(bfile_url(a_number))
    path.parent.mkdir(parents=True, exist_ok=True)
    if body is None:
        absent.touch()
        path.unlink(missing_ok=True)
        return None
    text = body.decode("utf-8", errors="replace")
    if "<html" in text[:500].lower():
        raise UnexpectedResponse(f"{a_number}: got an HTML page instead of a b-file")
    tmp = path.with_suffix(".part")
    tmp.write_bytes(body)          # exact bytes, so the sha256 can be compared with the LFS pointer
    tmp.replace(path)
    absent.unlink(missing_ok=True)
    return parse_bfile(a_number, text)


def fetch_entry_text(a_number: str) -> str | None:
    """Current internal-format entry from oeis.org (for the re-check just before acting)."""
    body = http_get(f"{config.OEIS_URL}/search?q=id:{a_number}&fmt=text")
    return body.decode("utf-8", errors="replace") if body else None


class InconsistentTerms(Exception):
    pass


def known_terms(entry: Entry, bfile: BFile | None) -> KnownTerms:
    """Known terms as (index, value): the b-file when there is one, cross-checked against DATA."""
    data = entry.data_values
    if not data:
        raise InconsistentTerms(f"{entry.a_number}: no DATA terms")
    if bfile is None or not bfile.values:
        return KnownTerms(entry.a_number, entry.offset, data, "data")

    notes = []
    values = dict(bfile.values)
    conflicts = [n for n, v in data.items() if n in values and values[n] != v]
    if conflicts:
        n = conflicts[0]
        raise InconsistentTerms(f"{entry.a_number}: DATA and b-file disagree at a({n})")
    if min(values) != entry.offset:
        if min(values) > entry.offset and all(n in data for n in range(entry.offset, min(values))):
            notes.append(f"b-file starts at {min(values)}, offset {entry.offset}; filled from DATA")
        else:
            raise InconsistentTerms(f"{entry.a_number}: b-file starts at n={min(values)} but offset is {entry.offset}")
    extra = {n: v for n, v in data.items() if n not in values}
    if extra:
        notes.append(f"{len(extra)} DATA terms beyond the b-file merged")
        values.update(extra)
    gaps = [n for n in range(min(values), max(values) + 1) if n not in values]
    if gaps:
        raise InconsistentTerms(f"{entry.a_number}: known terms have {len(gaps)} gaps, first at n={gaps[0]}")
    if bfile.malformed:
        notes.append(f"{len(bfile.malformed)} malformed b-file lines ignored")
    if bfile.duplicates:
        raise InconsistentTerms(f"{entry.a_number}: b-file repeats index {bfile.duplicates[0]}")
    return KnownTerms(entry.a_number, entry.offset, values, "bfile", notes)
