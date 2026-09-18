"""PARI/GP strategy (build step 6): run the entry's own PARI program further.

OEIS PARI programs come in a few shapes. Supported:
  * a(n) = ...        (also A123456(n), a=(n)->...)   -> evaluate a(n) for n = offset, offset+1, ...
  * isok(k) = ...     (is, ok, isA123456, ...)         -> search k upward; each hit is the next term;
                                                          the number of k tested is the work count
  * print loop        for(n=1, 10^6, if(cond(n), print1(n, ", ")))
                      -> the single print becomes our term emitter, literal loop bounds are lifted to
                         +oo (the outermost loop always, inner loops when >= 1000, i.e. search limits).
                         Every rewrite is recorded in Program.notes and shown in the review artifact.
Not yet supported (reported, so their frequency can be measured): list printers such as lista(nn),
first(n) vector builders, triangle rows.

Top-level driver statements in the entry (for(...), print(...), lista(1000), ...) are dropped for the
function forms; only definitions, assignments and precision defaults are kept.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..ingest.seqfile import Entry, split_signed_programs
from ..terms import KnownTerms, Program

_DEF = re.compile(r"^([A-Za-z_]\w*)\s*\(([^()]*)\)\s*=(?!=)")
_CLOSURE = re.compile(r"^([A-Za-z_]\w*)\s*=\s*\(([^()]*)\)\s*->")
_ASSIGN = re.compile(r"^[A-Za-z_]\w*\s*=(?!=)")
_KEEP_CALL = re.compile(r"^(default\s*\(|\\p\b|\\ps\b)")
_LIST_NAMES = re.compile(r"^(lista|list|upto|seq|A\d{6}_?list)$", re.IGNORECASE)
_LOOP_HEAD = re.compile(r"^(for|forprime|forstep|forcomposite|forsquarefree|while|until)\s*\(")
_BOUNDED_LOOP = re.compile(r"\b(for|forprime|forstep|forcomposite|forsquarefree)\s*\(")
_PRINT = re.compile(r"\bprint1?\s*\(")
_LITERAL_BOUND = re.compile(r"^\s*\d+(\s*[*^]\s*\d+)*\s*$")
_STRING = re.compile(r'^\s*"[^"]*"\s*$')
SEARCH_BOUND = 1000


def _is_a_name(name: str, a_number: str) -> bool:
    return name == "a" or name.lower() in (a_number.lower(), "a" + a_number[1:])


def _is_predicate_name(name: str, a_number: str) -> bool:
    n = name.lower()
    return n in ("is", "isok", "ok", "isa", "is_a", "is_ok", "isok1") or n in (f"is{a_number.lower()}", f"is_{a_number.lower()}")


# ------------------------------------------------------------------ scanning GP text

def code_mask(text: str) -> list[bool]:
    """True where a character is code (not inside a string or comment)."""
    mask = [True] * len(text)
    i = 0
    while i < len(text):
        c, nxt = text[i], text[i + 1: i + 2]
        if c == '"':
            j = i + 1
            while j < len(text) and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            end = min(j + 1, len(text))
        elif c == "\\" and nxt == "\\":
            j = text.find("\n", i)
            end = len(text) if j < 0 else j
        elif c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            end = len(text) if j < 0 else j + 2
        else:
            i += 1
            continue
        for k in range(i, end):
            mask[k] = False
        i = end
    return mask


def call_args(text: str, open_paren: int, mask: list[bool]) -> tuple[list[tuple[int, int]], int] | None:
    """Spans of the top-level arguments of the call whose '(' is at open_paren, and the ')' index."""
    depth = 0
    start = open_paren + 1
    spans = []
    for i in range(open_paren, len(text)):
        if not mask[i]:
            continue
        c = text[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                spans.append((start, i))
                return spans, i
        elif c == "," and depth == 1:
            spans.append((start, i))
            start = i + 1
    return None


def split_top_level(text: str, sep: str = ";") -> list[str]:
    mask = code_mask(text)
    parts, depth, start = [], 0, 0
    for i, c in enumerate(text):
        if not mask[i]:
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p for p in parts if p.strip()]


@dataclass
class Statement:
    text: str
    kind: str                 # def | assign | keep | call | comment
    name: str | None = None
    params: list[str] = field(default_factory=list)


def split_statements(code: str) -> list[Statement]:
    """Top-level GP statements. A newline ends a statement unless inside braces, a string, a block
    comment, or open parentheses/brackets (joined, to tolerate programs wrapped across %o lines)."""
    mask = code_mask(code)
    out: list[Statement] = []
    buf: list[str] = []
    brace = paren = 0

    def flush():
        text = "".join(buf).strip()
        buf.clear()
        if text:
            out.append(_classify(text))

    for i, c in enumerate(code):
        if not mask[i]:
            buf.append(c)
            continue
        if c == "\n":
            joined = "".join(buf).rstrip()
            if brace > 0:
                buf.append(c)
            elif paren > 0 or (joined.endswith("\\") and not joined.endswith("\\\\")):
                buf.append(" ")
            else:
                flush()
            continue
        if c == "{":
            brace += 1
        elif c == "}":
            brace = max(0, brace - 1)
        elif c in "([":
            paren += 1
        elif c in ")]":
            paren = max(0, paren - 1)
        buf.append(c)
    flush()
    return out


def strip_comments(text: str) -> str:
    """Remove \\\\ and /* */ comments, keeping string literals intact."""
    out, i = [], 0
    while i < len(text):
        c, nxt = text[i], text[i + 1: i + 2]
        if c == '"':
            j = i + 1
            while j < len(text) and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif c == "\\" and nxt == "\\":
            j = text.find("\n", i)
            i = len(text) if j < 0 else j
        elif c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            i = len(text) if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    return "".join(out).strip()


def literal_value(bound: str) -> float:
    """Value of a bound written with digits, * and ^ (e.g. 2*10^6), without evaluating huge powers."""
    total = 1.0
    for factor in bound.replace(" ", "").split("*"):
        pieces = factor.split("^")
        if len(pieces) == 1:
            total *= int(pieces[0])
        elif len(pieces) == 2 and int(pieces[1]) <= 64:
            total *= float(int(pieces[0]) ** int(pieces[1]))
        else:
            return float("inf")
    return total


def _classify(text: str) -> Statement:
    body = strip_comments(text)
    if not body:
        return Statement(text, "comment")
    head = body.lstrip("{").lstrip()
    for rx in (_DEF, _CLOSURE):
        m = rx.match(head)
        if m:
            params = [p.split("=")[0].strip() for p in m.group(2).split(",") if p.strip()]
            return Statement(text, "def", m.group(1), params)
    if _ASSIGN.match(head):
        # `a=13; for(n=0, 1500, ...)` is a driver that starts with an assignment
        if any(_LOOP_HEAD.match(p.strip()) or _PRINT.match(p.strip()) for p in split_top_level(head)[1:]):
            return Statement(text, "call")
        return Statement(text, "assign")
    if _KEEP_CALL.match(head):
        return Statement(text, "keep")
    return Statement(text, "call")


# ------------------------------------------------------------------ print-loop rewrite

def rewrite_print_loop(stmts: list[Statement]) -> tuple[str, str, list[str]] | None:
    """For programs whose only driver is one loop printing each term, return
    (kept program text, rewritten loop, notes), or None when the shape is not recognised."""
    calls = [s for s in stmts if s.kind == "call"]
    if len(calls) != 1:
        return None
    all_code = "\n".join(strip_comments(s.text) for s in stmts)
    if len(_PRINT.findall(all_code)) != 1:
        return None
    parts = [p.strip() for p in split_top_level(strip_comments(calls[0].text))]
    loop_at = next((i for i, p in enumerate(parts) if _LOOP_HEAD.match(p.lstrip("{").lstrip())), None)
    if loop_at is None or loop_at != len(parts) - 1:
        return None
    if not all(_ASSIGN.match(p) for p in parts[:loop_at]):
        return None
    pre = "; ".join(parts[:loop_at])
    loop = parts[loop_at]
    if loop.startswith("{") and loop.endswith("}"):
        loop = loop[1:-1].strip()
    if not _BOUNDED_LOOP.match(loop):
        return None                      # while/until: no literal bound we could lift

    mask = code_mask(loop)
    m = next((m for m in _PRINT.finditer(loop) if mask[m.start()]), None)
    if m is None:
        return None
    parsed = call_args(loop, m.end() - 1, mask)
    if parsed is None:
        return None
    spans, close = parsed
    args = [loop[a:b].strip() for a, b in spans]
    if len(args) == 2 and _STRING.match(args[1]):
        expr = args[0]
    elif len(args) == 1:
        expr = re.sub(r'\s*"[^"]*"\s*$', "", args[0])     # print1(n", ")
    else:
        return None
    if not expr or '"' in expr:
        return None
    notes = [f"print call `{loop[m.start():close + 1]}` replaced by the term emitter"]
    edits = [(m.start(), close + 1, f"oeisbot_emit({expr})")]

    outermost = True
    for lm in _BOUNDED_LOOP.finditer(loop):
        if not mask[lm.start()]:
            continue
        parsed = call_args(loop, lm.end() - 1, mask)
        if parsed is None or len(parsed[0]) < 3:
            return None
        a, b = parsed[0][1]
        bound = loop[a:b]
        if _LITERAL_BOUND.match(bound):
            if outermost or literal_value(bound) >= SEARCH_BOUND:
                edits.append((a, b, " +oo"))
                notes.append(f"`{lm.group(1)}` bound {bound.strip()} lifted to +oo")
        elif outermost:
            return None      # outer bound is a variable: cannot run it longer without guessing
        outermost = False
    if len(notes) == 1:
        return None                      # nothing lifted: it could not run any longer than before
    for a, b, rep in sorted(edits, reverse=True):
        loop = loop[:a] + rep + loop[b:]
    kept = [s.text for s in stmts if s.kind in ("def", "assign", "keep", "comment")]
    if pre:
        kept.append(pre + ";")
    return "\n".join(kept), loop, notes


# ------------------------------------------------------------------ candidates

@dataclass
class Candidate:
    program: Program
    form: str                   # 'a(n)' | 'predicate' | 'print-loop'


@dataclass
class Rejected:
    block: int
    reason: str


_EMIT = """{name} = {first};
oeisbot_emit(v) = {{
  if(type(v) != "t_INT", error("emitted value is not an integer: ", type(v)));
  print("@T ", {name}, " ", v, " ", getabstime() * 1000, " {work} ", default(parisize) + 8 * getheap()[2]);
  {name}++;
}}"""

A_DRIVER = """
\\\\ ---- OEISBot driver: a(n) for n = {first}, {first}+1, ... ----
default(debugmem, 0);
{{
  for(oeisbot_n = {first}, +oo,
    my(oeisbot_v = {fn}(oeisbot_n));
    if(type(oeisbot_v) != "t_INT", error("{fn}(", oeisbot_n, ") is not an integer: ", type(oeisbot_v)));
    print("@T ", oeisbot_n, " ", oeisbot_v, " ", getabstime() * 1000, " 0 ", default(parisize) + 8 * getheap()[2]));
}}
quit
"""

PREDICATE_DRIVER = """
\\\\ ---- OEISBot driver: terms are the k >= {start} with {fn}(k) true, indexed from {first} ----
default(debugmem, 0);
{{
  my(oeisbot_i = {first}, oeisbot_tested = 0);
  for(oeisbot_k = {start}, +oo,
    oeisbot_tested++;
    if({fn}(oeisbot_k),
      print("@T ", oeisbot_i, " ", oeisbot_k, " ", getabstime() * 1000, " ", oeisbot_tested, " ", default(parisize) + 8 * getheap()[2]);
      oeisbot_i++));
}}
quit
"""


def build_candidates(entry: Entry, known: KnownTerms) -> tuple[list[Candidate], list[Rejected]]:
    buckets: dict[str, list[Candidate]] = {"a(n)": [], "predicate": [], "print-loop": []}
    rejected: list[Rejected] = []
    seen: set[str] = set()
    vals = [known.values[n] for n in sorted(known.values)]
    increasing = all(b > a for a, b in zip(vals, vals[1:]))
    blocks = [b for b in entry.programs if b.language == "pari"]
    for bi, block in enumerate(blocks, 1):
        for si, code in enumerate(split_signed_programs(block.code), 1):
            label = f"{entry.a_number} %o (PARI) block {bi}" + (f" part {si}" if si > 1 else "")
            stmts = split_statements(code)
            kept = [s for s in stmts if s.kind in ("def", "assign", "keep", "comment")]
            defs = {s.name: s for s in stmts if s.kind == "def"}
            source = "\n".join(s.text for s in kept)
            a_fn = next((n for n, s in defs.items() if _is_a_name(n, entry.a_number) and len(s.params) >= 1), None)
            pred_fn = next((n for n, s in defs.items() if _is_predicate_name(n, entry.a_number) and len(s.params) >= 1), None)
            notes: list[str] = []
            if a_fn:
                script = source + "\n" + A_DRIVER.format(first=known.first_index, fn=a_fn)
                form = "a(n)"
            elif pred_fn:
                if not increasing:
                    rejected.append(Rejected(bi, f"predicate {pred_fn}() but known terms are not strictly increasing"))
                    continue
                start = 1 if vals[0] >= 1 else vals[0]
                script = source + "\n" + PREDICATE_DRIVER.format(first=known.first_index, start=start, fn=pred_fn)
                form = "predicate"
            elif (rw := rewrite_print_loop(stmts)) is not None:
                kept_text, loop, notes = rw
                source = code.strip()
                script = "\n".join([
                    kept_text,
                    "\\\\ ---- OEISBot driver: the program's own loop, printing through the emitter ----",
                    "default(debugmem, 0);",
                    _EMIT.format(name="oeisbot_i", first=known.first_index, work=0),
                    loop.replace("\n", " ") + ";",
                    "quit",
                ])
                form = "print-loop"
            else:
                names = ", ".join(defs) or "none"
                if any(_LIST_NAMES.match(n) for n in defs):
                    rejected.append(Rejected(bi, f"list-printing form not supported (defines {names})"))
                else:
                    rejected.append(Rejected(bi, f"no a(n), predicate, or single print loop (defines {names})"))
                continue
            if script in seen:
                continue
            seen.add(script)
            prog = Program("gp", source, origin=label, strategy=f"pari:{form}", script=script, notes=notes)
            buckets[form].append(Candidate(prog, form))
    # later programs in an entry are more often the faster rewrites; prefer them, function forms first
    return [c for form in ("a(n)", "predicate", "print-loop") for c in reversed(buckets[form])], rejected
