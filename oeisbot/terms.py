"""Known terms as (index, value) pairs, never bare lists: offset errors are the most common silent failure."""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field

sys.set_int_max_str_digits(0)


@dataclass
class KnownTerms:
    a_number: str
    offset: int                 # from the %O line
    values: dict[int, int]      # index -> value
    source: str                 # 'bfile' or 'data'
    notes: list[str] = field(default_factory=list)

    @property
    def first_index(self) -> int:
        return min(self.values)

    @property
    def last_index(self) -> int:
        return max(self.values)

    @property
    def count(self) -> int:
        return len(self.values)

    def gaps(self) -> list[int]:
        return [n for n in range(self.first_index, self.last_index + 1) if n not in self.values]

    def describe(self) -> str:
        return f"a({self.first_index})..a({self.last_index}): {self.count} terms from {self.source}"


@dataclass
class Program:
    language: str               # 'python' | 'gp'
    source: str                 # the program a human reviews
    origin: str                 # where it came from, e.g. "oeis A000045 %o (PARI) block 1"
    strategy: str               # e.g. 'pari:a(n)', 'python:model'
    script: str | None = None   # full file actually executed, when a driver wraps `source`
    notes: list[str] = field(default_factory=list)   # e.g. rewrites applied to the original program

    @property
    def executed(self) -> str:
        return self.script if self.script is not None else self.source

    @property
    def sha(self) -> str:
        return hashlib.sha256(self.executed.encode()).hexdigest()[:16]


def format_bfile(values: dict[int, int]) -> str:
    """OEIS b-file body: one 'n a(n)' per line, contiguous indices."""
    return "".join(f"{n} {values[n]}\n" for n in sorted(values))
