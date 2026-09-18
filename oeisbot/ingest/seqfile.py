"""Parse OEIS internal-format entries (the .seq files in oeisdata, or fmt=text from oeis.org)."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.set_int_max_str_digits(0)

_LINE = re.compile(r"^%(\w)\s+(A\d{6})\s?(.*)$")
_LANG_TAG = re.compile(r"^\(([A-Z][A-Za-z0-9+#./ -]{0,30})\)\s*(.*)$")
_SIGNATURE = re.compile(r"\\\\\s*_[^_]+_\s*,\s*[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4}\s*$")
_CREDIT = re.compile(
    r"\b(more terms|additional terms|further terms|extended by|terms? extended|b-file extended"
    r"|a\(\d+\)\s*(-|\.\.|to|through)\s*a\(\d+\)\s*from)\b", re.IGNORECASE)

LANG_ALIASES = {"pari": "pari", "pari/gp": "pari", "gp": "pari", "python": "python", "python 3": "python",
                "python3": "python", "sage": "sage", "sagemath": "sage", "magma": "magma", "gap": "gap",
                "haskell": "haskell", "maxima": "maxima", "julia": "julia", "c": "c", "c++": "c++", "java": "java"}


@dataclass
class ProgramBlock:
    language: str      # normalized: pari, python, mathematica, maple, ...
    tag: str           # as written, e.g. 'PARI', 'Python 3'
    code: str


@dataclass
class Entry:
    a_number: str
    name: str
    offset: int
    keywords: list[str]
    data: list[int]                          # DATA terms, signed if %V/%W/%X present
    programs: list[ProgramBlock] = field(default_factory=list)
    extensions: list[str] = field(default_factory=list)   # %E lines
    links: list[str] = field(default_factory=list)        # %H lines
    comments: list[str] = field(default_factory=list)
    formulas: list[str] = field(default_factory=list)

    @property
    def data_values(self) -> dict[int, int]:
        return {self.offset + i: v for i, v in enumerate(self.data)}

    @property
    def languages(self) -> list[str]:
        return sorted({p.language for p in self.programs})

    def programs_in(self, language: str) -> list[ProgramBlock]:
        return [p for p in self.programs if p.language == language]

    @property
    def more_credits(self) -> int:
        return sum(1 for e in self.extensions if _CREDIT.search(e))

    def has_keyword(self, k: str) -> bool:
        return k in self.keywords


def _norm_lang(tag: str) -> str:
    t = tag.strip().lower()
    return LANG_ALIASES.get(t, t)


def _terms(text: str) -> list[int]:
    return [int(x) for x in text.replace(" ", "").split(",") if x]


def parse(text: str) -> Entry | None:
    fields: dict[str, list[str]] = {}
    a_number = None
    for raw in text.splitlines():
        m = _LINE.match(raw.rstrip("\r"))
        if not m:
            continue
        key, a, rest = m.groups()
        if a_number is None:
            a_number = a
        elif a != a_number:
            break  # a second entry (fmt=text can contain several); stop at the first
        fields.setdefault(key, []).append(rest)
    if a_number is None or "N" not in fields:
        return None

    signed = "".join(fields.get("V", []) + fields.get("W", []) + fields.get("X", []))
    unsigned = "".join(fields.get("S", []) + fields.get("T", []) + fields.get("U", []))
    try:
        data = _terms(signed or unsigned)
    except ValueError:
        data = []
    offset_text = (fields.get("O") or ["0"])[0]
    try:
        offset = int(offset_text.split(",")[0])
    except ValueError:
        offset = 0

    programs: list[ProgramBlock] = []
    for key, default_lang in (("p", "maple"), ("t", "mathematica")):
        if key in fields:
            programs.append(ProgramBlock(default_lang, default_lang.capitalize(), "\n".join(fields[key])))
    current: ProgramBlock | None = None
    for line in fields.get("o", []):
        tag = _LANG_TAG.match(line)
        if tag:
            current = ProgramBlock(_norm_lang(tag.group(1)), tag.group(1), tag.group(2))
            programs.append(current)
        elif current is not None:
            current.code += "\n" + line
    for p in programs:
        p.code = p.code.strip("\n")

    return Entry(
        a_number=a_number,
        name=" ".join(fields["N"]),
        offset=offset,
        keywords=[k.strip() for k in (fields.get("K") or [""])[0].split(",") if k.strip()],
        data=data,
        programs=programs,
        extensions=fields.get("E", []),
        links=fields.get("H", []),
        comments=fields.get("C", []),
        formulas=fields.get("F", []),
    )


def parse_file(path: Path) -> Entry | None:
    return parse(path.read_text(encoding="utf-8", errors="replace"))


def split_signed_programs(code: str) -> list[str]:
    """Split a program block holding several programs, each ending with a '\\\\ _Author_, Mon DD YYYY' line."""
    parts, current = [], []
    for line in code.splitlines():
        current.append(line)
        if _SIGNATURE.search(line):
            parts.append("\n".join(current))
            current = []
    tail = "\n".join(current).strip()
    if tail:
        if parts and not any(ch.isalnum() for ch in tail):
            parts[-1] += "\n" + tail
        else:
            parts.append(tail)
    return [p for p in parts if p.strip()]
