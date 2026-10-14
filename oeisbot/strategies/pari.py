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

Rejected as unrunnable whatever their shape: blocks that call or index an A-number the block never
defines (`undefined_a_numbers`). Those helpers live in another OEIS entry, and gp errors as soon as
such a call is reached, so the program can only waste a pick.

Top-level driver statements in the entry (for(...), print(...), lista(1000), ...) are dropped for the
function forms; only definitions, assignments and precision defaults are kept.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..ingest.seqfile import Entry, split_signed_programs
from ..terms import KnownTerms, Program

_NAME = re.compile(r"\b[A-Za-z_]\w*")
_AFTER_DEF = re.compile(r"\s*=(?!=)")          # `name(params) = body`, `name = value`; never `==`
_AFTER_LAMBDA = re.compile(r"\s*->")           # `(params) -> body`
_ASSIGN = re.compile(r"^[A-Za-z_]\w*\s*=(?!=)")
_KEEP_CALL = re.compile(r"^(default\s*\(|\\p\b|\\ps\b)")
_LIST_NAMES = re.compile(r"^(lista|list|upto|seq|A\d{6}_?list)$", re.IGNORECASE)
_LOOP_HEAD = re.compile(r"^(for|forprime|forstep|forcomposite|forsquarefree|while|until)\s*\(")
_BOUNDED_LOOP = re.compile(r"\b(for|forprime|forstep|forcomposite|forsquarefree)\s*\(")
_PRINT = re.compile(r"\bprint1?\s*\(")
_LITERAL_BOUND = re.compile(r"^\s*\d+(\s*[*^]\s*\d+)*\s*$")
_STRING = re.compile(r'^\s*"[^"]*"\s*$')
SEARCH_BOUND = 1000

# A program that describes ITSELF as conjectural or heuristic. Conditional on a conjecture published
# in OEIS, agreement with the known terms carries almost no information: the closed form reproduces
# every one of them by construction, so the verification gate -- the whole basis on which this project
# believes a term -- learns nothing, and the run then emits values without limit until max_new_terms
# stops it. Session 10 did exactly that twice, 200 values each for A162762 and A162764, and opened two
# review rows that must never be submitted (history item 45).
#
# This is NOT the kind of static check item 46 measured and threw away (data/item46/classify_m1.py,
# wrong on 5 of 32 blocks): that one INFERRED a semantic fact the text never stated. This one reads an
# explicit human declaration, and it is the only thing that tells the three conjectural A16276x
# siblings from A162761, whose closed form is proved and which carries no disclaimer.
#
# Invariant 10's frame (docs/development.md#invariants): an author's unverified prose may stop us
# spending time and must never be evidence about a term's value. This only ever stops a run.
# The `[a-z]*` tails only widen what `m.group(0)` REPORTS -- "conjectured", "conjecturally",
# "heuristics" rather than the bare stem -- and cannot change whether a part matches: a stem that
# matches makes the tailed form match at the same position, and because every GP comment or string
# delimiter (`\\`, `/*`, `"`) is outside [a-z], such a run can never straddle a code/non-code boundary
# and so can never swallow text that would have hidden a later non-code match from `finditer`. Verified
# over all 5,781 parts: identical verdicts, the same 7 flagged.
#
# LETTERS ONLY, not `\w*`, and that is not cosmetic. `\w` includes digits and `_`, so `\\ conjectured86`
# reported `conjectured86` and a 40-digit run came through whole -- putting digits from a comment into
# `Rejected.reason`, which is exactly what naming the word rather than the line exists to prevent, and
# 86 is a real known term of A162762. `re.I` already covers upper case, so [a-z] loses nothing.
_CONJECTURAL = re.compile(r"conjectur[a-z]*|heuristic[a-z]*|unproved|unproven|not proved", re.I)

# A name carrying an OEIS A-number, used as a function or a vector: A007947(n), a147798[n], and -- since
# 2026-09-30 (item 51) -- helpers named around one, is_A178751(n) and a375301_row(n), which live in
# another entry just as often. The WHOLE identifier is captured and compared against the block's own
# definitions: capturing only the A-number would flag `is_A034293` in `is_A034293(n) = ...`, a program
# that verified in session 11 (item 50). 6 digits is the OEIS form; entries also abbreviate, A1969 for
# A001969
_ANAME_USE = re.compile(r"\b(\w*[Aa]\d{4,7}\w*)\s*[(\[]")
_LEADING_NAME = re.compile(r"\s*&?\s*([A-Za-z_]\w*)")                   # a parameter, maybe by reference


def _is_a_name(name: str, a_number: str) -> bool:
    return name == "a" or name.lower() in (a_number.lower(), "a" + a_number[1:])


def _is_predicate_name(name: str, a_number: str) -> bool:
    n = name.lower()
    return n in ("is", "isok", "ok", "isa", "is_a", "is_ok", "isok1") or n in (f"is{a_number.lower()}", f"is_{a_number.lower()}")


def _bulk_printer(stmt: "Statement") -> bool:
    """A def whose ONLY parameter carries a default is not a term function. The parameter is a search
    bound -- `a373945(upto=10^8)`, `a368129(rmax=235)` -- and calling it with an index runs the whole
    search up to that index and prints a list, so the driver's `@T` lines land on the program's own
    output and the run is a plain timeout with nothing in the row to say why (session 11's A373945;
    session 7's A368129). Measured 2026-09-30: 4 defs of this shape in the corpus, all four bulk
    printers, two in the pool; the user chose the refusal (item 53). Re-measure at a sync before
    trusting the shape again."""
    return len(stmt.params) == 1 and bool(stmt.defaults[0])


def _drivable(stmt: "Statement") -> bool:
    """Can A_DRIVER or PREDICATE_DRIVER call this def, which they do with exactly one argument?

    It needs a parameter to take the index or the candidate, and it must not need a *second*: gp does
    not refuse a call that omits an argument, it binds the parameter to 0 and carries on, so the run
    silently computes something else. A366832's `isok(k, b)` -- its own loop supplied b = 9 -- reached
    `digits(k, 0)` and was recorded as `incomplete`, and a search bound left at 0 simply searches
    nothing. A parameter with a default is fine: gp uses the default.

    Every parameter after the first must have one, which is not the same as counting those that lack
    one: gp fills omitted arguments from the left, so `f(a=1, b)` lacks exactly one default and is
    still broken -- `f(a=1,b)=[a,b]; f(7)` gives [7, 0] on this machine's gp 2.17.4. No entry in the
    corpus is that shape today, so this half is a guard against a `sync`, not a live fix.
    """
    return len(stmt.params) >= 1 and all(stmt.defaults[1:])


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
    defaults: list[bool] = field(default_factory=list)   # per parameter, whether it carries a default.
                              # gp binds a missing argument to 0 silently (`f(a,b)=a+b; f(1)` prints 1),
                              # so a def the drivers call with one argument must not need a second.
                              # Per parameter, not a count: `f(a=1, b)` has one parameter without a
                              # default and is still broken, because the one without it is not the first
                              # (gp 2.17.4: `f(a=1,b)=[a,b]; f(7)` gives [7, 0]). See _drivable.


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


def _declared(parts: list[str]) -> set[str]:
    """The names a parameter list declares -- the name each entry starts with, `&` and a default value
    aside: `f(n, p = A000043[n])` declares `n` and `p`, and *uses* `A000043`."""
    return {m.group(1) for p in parts if (m := _LEADING_NAME.match(p))}


def _skip_blanks(text: str, i: int) -> int:
    while i < len(text) and text[i] in " \t":
        i += 1
    return i


def _def_head(head: str) -> tuple[str, str] | None:
    """`(name, raw parameter list)` when `head` opens a def `name(params) = ...` or a closure
    `name = (params) -> ...`, the parameter list read to its *balanced* close.

    `A122172_row(n, p=part(n)) = {...}` has a call inside a default. The `[^()]*` regexes this replaced
    could not cross it: the statement was classified as a call and dropped from the kept source, the
    block yielded nothing, and the helper check then reported the block's *own* function as undefined.
    Item 46 measured the shape at 40 statements in 36 blocks and deferred it; item 51 built it."""
    mask = code_mask(head)
    m = _NAME.match(head)
    if not m:
        return None
    i = _skip_blanks(head, m.end())
    if i < len(head) and head[i] == "(":
        parsed = call_args(head, i, mask)
        if parsed is not None and _AFTER_DEF.match(head, parsed[1] + 1):
            return m.group(0), head[i + 1: parsed[1]]
        return None
    if i < len(head) and head[i] == "=" and not head.startswith("==", i):
        j = _skip_blanks(head, i + 1)
        if j < len(head) and head[j] == "(":
            parsed = call_args(head, j, mask)
            if parsed is not None and _AFTER_LAMBDA.match(head, parsed[1] + 1):
                return m.group(0), head[j + 1: parsed[1]]
    return None


def _defined_names(code: str, mask: list[bool]) -> set[str]:
    """Every name this code could bind, read generously: a wrongly undefined name would reject a program
    that runs, while a name counted as defined only costs the pick it would have cost anyway.

    Read with balanced parentheses, like `_def_head`: `f(n, p = g(n)) = ...` defines `f`, `n` and `p`.
    A def's parameters, a closure's parameters and any `x = ...` (a loop variable, a `my(x = ...)`)
    all count. A `my(x)`/`local(x)` with no value is deliberately not a definition. It is the one
    declaration gp still errors on when the name is then called or indexed, so counting it would only
    suppress a correct rejection."""
    names: set[str] = set()
    for m in _NAME.finditer(code):
        if not mask[m.start()]:
            continue
        j = _skip_blanks(code, m.end())
        if j < len(code) and code[j] == "(":
            parsed = call_args(code, j, mask)
            if parsed is not None and _AFTER_DEF.match(code, parsed[1] + 1):
                names.add(m.group(0))
                names |= _declared([code[a:b] for a, b in parsed[0]])
        elif j < len(code) and code[j] == "=" and not code.startswith("==", j):
            names.add(m.group(0))
    # a closure's parameters, wherever its parenthesis sits: `g = (x, y) -> ...`, `apply((x) -> ..., v)`
    for i, c in enumerate(code):
        if c == "(" and mask[i]:
            parsed = call_args(code, i, mask)
            if parsed is not None and _AFTER_LAMBDA.match(code, parsed[1] + 1):
                names |= _declared([code[a:b] for a, b in parsed[0]])
    return names


def undefined_a_numbers(code: str) -> list[str]:
    """Names carrying an A-number that this code calls or indexes without ever defining them.

    An OEIS `%o` block may use a helper that lives in a *different* entry (`A147803(n) = ... A007947(n) ...`,
    `A147805` reads `a147798[n]`, A274003's predicate calls `is_A178751(n)`). gp accepts such a program and
    runs it, then errors as soon as it reaches one -- "not a function in function call", or an incorrect
    type. The whole identifier is compared, so a block's own `is_A034293(n) = ...` is never flagged for
    the A-number inside its name (item 51).

    This over-approximates, deliberately: gp only errors on a use it *reaches*, so a helper called from a
    branch the known terms never take, or from a function nothing calls, would be rejected although the
    program might have run. No entry in the corpus is such a case, while 65 are genuinely broken.

    A *bare* mention is not checked: gp leaves an unknown name as a polynomial variable and carries on, so
    `n + A007947` prints the expression unevaluated and `#A007947` returns 2 rather than failing."""
    mask = code_mask(code)
    defined = _defined_names(code, mask)
    return sorted({m.group(1) for m in _ANAME_USE.finditer(code)
                   if mask[m.start()] and m.group(1) not in defined})


def conjectural(text: str) -> str | None:
    """The word with which this program text disclaims itself, or None.

    Matched in a comment or a string literal, never in live code: the signal is the author's own prose,
    and a GP identifier named `heuristic` or `conjecture` would be a false positive a future `sync`
    could introduce. Measured over all 5,781 PARI parts on 2026-09-26: of the 20 matches at any width,
    **none** sits in code and none inside a string literal, so the restriction costs nothing today and
    is what keeps the rejection's reason from ever being a lie.

    Deliberately narrow. `upper bound`, `lower bound` and `assuming` were measured and left out: they
    match optional *parameters named that* (A002071, A217016, A340630) and the "assuming the vector
    A002975 holds enough terms" shape (A258885, A273815, A275493, A321995, A376243), which is a
    different failure. Do not widen without redoing that measurement --
    tests/test_pari.py pins this."""
    mask = code_mask(text)
    m = next((m for m in _CONJECTURAL.finditer(text) if not mask[m.start()]), None)
    return m.group(0).lower() if m else None


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
    if (d := _def_head(head)) is not None:
        name, raw_params = d
        # split_top_level, not a plain split: `f(n, v=[1,2])` must not break into three parameters
        raw = [p.strip() for p in split_top_level(raw_params, ",") if p.strip()]
        params = [p.split("=")[0].strip() for p in raw]
        return Statement(text, "def", name, params, ["=" in p for p in raw])
    if _ASSIGN.match(head):
        # `a=13; for(n=0, 1500, ...)` is a driver that starts with an assignment
        if any(_LOOP_HEAD.match(p.strip()) or _PRINT.match(p.strip()) for p in split_top_level(head)[1:]):
            return Statement(text, "call")
        return Statement(text, "assign")
    if _KEEP_CALL.match(head):
        return Statement(text, "keep")
    return Statement(text, "call")


# ------------------------------------------------------------------ print-loop rewrite

_LOOP_VAR = re.compile(r"\s*([A-Za-z_]\w*)\s*=\s*(.*?)\s*$", re.S)


def _once_per_iteration(loop: str, mask: list[bool], body: list[tuple[int, int]], print_at: int) -> bool:
    """Is the print at `print_at` a top-level statement of the outer loop's body -- executed exactly once
    per iteration -- rather than inside an `if(...)`, an inner loop's parentheses, or behind a `&&`/`||`
    guard? `body` is the outer loop's argument spans after the bound. A print that is not once per
    iteration makes the loop a FILTER: what it emits is the iterations that pass, and the loop variable
    is a candidate value, not an index."""
    for a, b in body:
        if a <= print_at < b:
            depth = 0
            for i in range(a, print_at):
                if not mask[i]:
                    continue
                c = loop[i]
                if c in "([{":
                    depth += 1
                elif c in ")]}":
                    depth -= 1
                elif depth == 0 and loop.startswith(("&&", "||"), i):
                    return False
            return depth == 0
    return False


@dataclass(frozen=True)
class LoopFacts:
    """What the outermost loop of a rewritten print loop says about where its terms start.

    `conditional` is whether the print is NOT a top-level statement of the outer loop's body -- it sits
    inside an `if(...)`, inside an inner loop, or behind a `&&`/`||` guard -- which makes the loop a
    filter, whose emitted count is not tied to the loop variable, as opposed to an index loop that
    prints once per iteration (an inner loop that only *computes* the value, followed by a top-level
    print, is still an index loop). `prints_var` is whether the printed expression is the loop variable
    itself. `start` is the loop's start expression as written (a literal or not)."""
    kind: str
    var: str
    start: str
    prints_var: bool
    conditional: bool


def loop_start_problem(f: LoopFacts, known: KnownTerms) -> str | None:
    """Why the rewritten loop would emit the wrong terms from its very first line, or None.

    The emitter numbers from `known.first_index` whatever the loop does (`_EMIT`), so an INDEX loop that
    starts anywhere else numbers every term from the wrong index -- A290024's `for(n=1, 7, ...)` under
    `%O 0` emitted a(2) as a(1), and a *correct* program was retired `wrong_term` (session 11). A FILTER
    loop that prints its own variable and starts above the first known term never emits that term --
    A215906's `for(i=2, ...)` under `%S 0,6,...` emitted 6 as a(1) (session 12). Both shapes were
    measured over the pool on 2026-09-30 (26 index loops off the offset, 20 filter loops above the first
    term, 44 pool sequences) and the user chose to refuse them rather than renumber: a refusal costs a
    candidate, a wrong renumbering costs a sequence. Only literal starts are judged; a filter loop that
    prints an expression, or a `forprime`/`forstep` index loop whose variable is not the index, is left
    to the gate (item 53)."""
    if not re.fullmatch(r"-?\d+", f.start.strip()):
        return None
    start = int(f.start)
    if not f.conditional and f.kind == "for":
        if start != known.first_index:
            return (f"the loop starts at {f.var} = {start} while the offset is {known.first_index}: every term "
                    f"would be numbered from the wrong index")
    elif f.conditional and f.prints_var:
        first = known.values[known.first_index]
        if start > first:
            return (f"the loop starts at {f.var} = {start} and would never reach the first known term "
                    f"a({known.first_index}) = {first}")
    return None


def rewrite_print_loop(stmts: list[Statement]) -> tuple[str, str, list[str], LoopFacts] | None:
    """For programs whose only driver is one loop printing each term, return
    (kept program text, rewritten loop, notes, facts about the outermost loop), or None when the shape
    is not recognised."""
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
    facts: LoopFacts | None = None
    for lm in _BOUNDED_LOOP.finditer(loop):
        if not mask[lm.start()]:
            continue
        parsed = call_args(loop, lm.end() - 1, mask)
        if parsed is None or len(parsed[0]) < 3:
            return None
        if outermost:
            head = loop[parsed[0][0][0]:parsed[0][0][1]]                 # `v = START`
            hm = _LOOP_VAR.match(head)
            facts = LoopFacts(kind=lm.group(1), var=hm.group(1) if hm else "", start=hm.group(2) if hm else "",
                              prints_var=bool(hm) and expr.strip() == hm.group(1),
                              conditional=not _once_per_iteration(loop, mask, parsed[0][2:], m.start()))
        a, b = parsed[0][1]
        bound = loop[a:b]
        if _LITERAL_BOUND.match(bound):
            if outermost or literal_value(bound) >= SEARCH_BOUND:
                edits.append((a, b, " +oo"))
                notes.append(f"`{lm.group(1)}` bound {bound.strip()} lifted to +oo")
        elif outermost:
            return None      # outer bound is a variable: cannot run it longer without guessing
        outermost = False
    if len(notes) == 1 or facts is None:
        return None                      # nothing lifted: it could not run any longer than before
    for a, b, rep in sorted(edits, reverse=True):
        loop = loop[:a] + rep + loop[b:]
    kept = [s.text for s in stmts if s.kind in ("def", "assign", "keep", "comment")]
    if pre:
        kept.append(pre + ";")
    return "\n".join(kept), loop, notes, facts


# ------------------------------------------------------------------ candidates

@dataclass
class Candidate:
    program: Program
    form: str                   # 'a(n)' | 'predicate' | 'print-loop'
    search_start: int | None = None   # predicate form: the first k its driver tests


# The predicate driver cannot test candidates faster than this. Measured in the sandbox on this project's
# machine, the cheapest predicate there is (a single comparison, `k >= L`) runs at about 5.8e6 calls/s;
# the constant leaves over 3x headroom for faster machines. tests/test_pari.py times it and fails if the
# measured rate ever comes within 1.5x of the constant.
PREDICATE_MAX_RATE = 2e7


def _approx(n: int) -> str:
    return f"{n:.3g}" if n < 10**15 else f"about 10^{len(str(n)) - 1}"


def out_of_reach(cand: Candidate, known: KnownTerms, verify_wall_s: float) -> str | None:
    """Why `cand` provably cannot reproduce the known terms within `verify_wall_s`, or None. Only the
    predicate form has such a bound: its driver calls the predicate once for every k from `search_start` up
    to the last known term, however cheap the predicate is. Other forms' cost is not tied to the values."""
    if cand.search_start is None:
        return None
    last = known.values[known.last_index]
    calls = last - cand.search_start + 1
    if calls <= PREDICATE_MAX_RATE * verify_wall_s:
        return None
    return (f"reaching a({known.last_index}) = {_approx(last)} takes {_approx(calls)} predicate calls, more than "
            f"{PREDICATE_MAX_RATE:.0e} calls/s can make in {verify_wall_s:g} s")


@dataclass
class Rejected:
    block: int
    reason: str


# The prefix of the reason `conjectural` produces. Callers key on this rather than on the sentence:
# the wording has already been changed once (it read "the program describes itself as ..." until an
# audit found it rendered ungrammatically for A393125), and two call sites were matching the old text.
CONJECTURAL_REASON = "a comment calls it"


def rejected_as_conjectural(rejected: list[Rejected]) -> bool:
    """Was any part of this entry refused for its author's own disclaimer?

    True only when that is why the part yielded nothing -- an entry with a conjectural part *and* a
    clean runnable one never reaches a caller of this, because the clean candidate is built."""
    return any(r.reason.startswith(CONJECTURAL_REASON) for r in rejected)


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

# Progress heartbeats. The driver used to print only when the predicate was TRUE, so a run killed
# mid-scan had emitted nothing since its last term and where its scan reached was unrecoverable -- the
# 49 predicate runs that ended at `verify_timeout` or `extend_budget` threw away 30,312 s of scan
# position between them. Only 21,002 s of that (14 runs, 13 sequences) could ever be resumed *above* the
# known terms: the 35 `verify_timeout` runs never reproduced them, so their frontier lies below the last
# known value. The scan now runs in blocks and prints `@P k tested cpu_us` after each one.
#
# The block is sized in TIME, not in k: it doubles while a block comes in under HEARTBEAT_TARGET_MS and
# halves when one overruns it fourfold, so the cadence holds whether a predicate costs 0.2 us or 10 ms.
# A block fixed in k cannot do that -- this project has measured per-term cost swinging from under a
# millisecond to 153 s within one sequence -- and a block that only grew could swallow hours in a single
# step, losing exactly the progress the heartbeat exists to keep.
#
# It is never free. Measured in the sandbox on the cheapest predicate there is, the blocked loop costs
# about 4% of scan throughput, of which about 2.1% is a floor no block size can remove: that is what a
# finite loop bound alone costs against the unbounded `+oo` loop this replaced. (For scale, a hand-rolled
# `while` with `k++` costs 43.9%.) Whether the remaining ~2% is per-iteration or per-block is NOT
# settled -- the block-size sweep sits inside a +-2% noise floor -- so a larger block may or may not buy
# it back, and block size is chosen for cadence because nothing measured argues otherwise. See
# docs/known-limitations.md for what was and was not established, and re-measure before tuning these.
# The printing happens AFTER the block, so the frontier can never name a k the driver has not tested.
HEARTBEAT_BLOCK0 = 10**4       # also the floor; the regime below it has never been timed
HEARTBEAT_BLOCK_MAX = 10**9
# getabstime() is CPU ms while every kill in the harness is in wall seconds, so on a starved machine a
# block's CPU time under-counts its wall duration and the driver GROWS the block -- the cadence stretches
# in wall time by roughly 1/cpu_share, and the shrink rule does not compensate. Bounded and harmless: a
# block is at most ~1 s of CPU at this target, so ~10 s of wall at a 10% share, and a kill still loses at
# most one block
HEARTBEAT_TARGET_MS = 250

PREDICATE_DRIVER = """
\\\\ ---- OEISBot driver: terms are the k >= {start} with {fn}(k) true, indexed from {first} ----
default(debugmem, 0);
{{
  my(oeisbot_i = {first}, oeisbot_tested = 0, oeisbot_base = {start},
     oeisbot_blk = {block0}, oeisbot_last = getabstime(), oeisbot_now = 0);
  while(1,
    for(oeisbot_k = oeisbot_base, oeisbot_base + oeisbot_blk - 1,
      oeisbot_tested++;
      if({fn}(oeisbot_k),
        print("@T ", oeisbot_i, " ", oeisbot_k, " ", getabstime() * 1000, " ", oeisbot_tested, " ", default(parisize) + 8 * getheap()[2]);
        oeisbot_i++));
    oeisbot_base += oeisbot_blk;
    oeisbot_now = getabstime();
    print("@P ", oeisbot_base - 1, " ", oeisbot_tested, " ", oeisbot_now * 1000);
    if(oeisbot_now - oeisbot_last < {target_ms},
      if(oeisbot_blk < {block_max}, oeisbot_blk *= 2),
      if(oeisbot_now - oeisbot_last > 4 * {target_ms} && oeisbot_blk > {block0}, oeisbot_blk /= 2));
    oeisbot_last = oeisbot_now);
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
            # Checked on the raw part text, before anything is built, and it condemns EVERY form the
            # part could yield -- unlike item 46's per-form rejections, because a disclaimer is about
            # the arithmetic, which every driver shares. The raw text and not a candidate's script:
            # top-level driver statements are dropped for the function forms, so a disclaimer written
            # as a trailing comment on the entry's own loop would be carried away with it and the
            # check would miss the very block it exists for (A393125 is such a part).
            #
            # The reason names the matched WORD and never the surrounding line. A quoted comment could
            # carry a term value ("conjectured that a(20) = ..."), and this reason reaches `say()` and
            # `db.record_skip`'s detail. No path takes it to a model prompt today. Note what the word
            # form does and does not buy: with `[a-z]*` tails the reason cannot contain a digit at all,
            # which is a property of the pattern, not of the corpus -- but it was `\w*` until an audit
            # showed `\\ conjectured86` reporting `conjectured86`, so this is a bound that has to be
            # maintained deliberately, not one that holds by itself.
            if (word := conjectural(code)) is not None:
                # "a comment calls it X", not "describes itself as X": the matched word is whatever
                # form the author wrote, so A393125's "conjecturally" made the second phrasing
                # ungrammatical, and the first is also the more accurate claim -- a comment near the
                # program is not always a statement about the program (A393125's is about what its "?"
                # outputs mean). The rejection is deliberately the same either way.
                rejected.append(Rejected(bi, f"{CONJECTURAL_REASON} {word}: "
                                             f"a conjectural program cannot extend the sequence"))
                continue
            stmts = split_statements(code)
            kept = [s for s in stmts if s.kind in ("def", "assign", "keep", "comment")]
            defs = {s.name: s for s in stmts if s.kind == "def"}
            source = "\n".join(s.text for s in kept)
            named = {n: s for n, s in defs.items()
                     if (_is_a_name(n, entry.a_number) or _is_predicate_name(n, entry.a_number)) and _drivable(s)}
            bulk = [n for n, s in named.items() if _bulk_printer(s)]
            a_fn = next((n for n, s in named.items() if _is_a_name(n, entry.a_number) and n not in bulk), None)
            pred_fn = next((n for n, s in named.items() if _is_predicate_name(n, entry.a_number) and n not in bulk), None)
            # (form, program source, script, search_start, notes) -- a block can yield more than one.
            builds: list[tuple[str, str, str, int | None, list[str]]] = []
            # A Rejected explains a block that yielded nothing, and a block yields at most one candidate
            # per form. Now that one block can offer two, a form that cannot be built is only worth
            # reporting if the *block* came to nothing: a print loop calling another entry's helper says
            # nothing about the a(n) form beside it, whose script never contains that call.
            block_rejects: list[Rejected] = []
            if a_fn:
                builds.append(("a(n)", source,
                               source + "\n" + A_DRIVER.format(first=known.first_index, fn=a_fn), None, []))
            elif pred_fn:
                if not increasing:
                    block_rejects.append(
                        Rejected(bi, f"predicate {pred_fn}() but known terms are not strictly increasing"))
                else:
                    start = 1 if vals[0] >= 1 else vals[0]
                    builds.append(("predicate", source,
                                   source + "\n" + PREDICATE_DRIVER.format(
                                       first=known.first_index, start=start, fn=pred_fn, block0=HEARTBEAT_BLOCK0,
                                       block_max=HEARTBEAT_BLOCK_MAX, target_ms=HEARTBEAT_TARGET_MS),
                                   start, []))
            # The entry's own loop is built *as well as* the def form, not instead of it. The generic
            # drivers scan every index or every k from the start and emit the bare value, so where the
            # loop restricts the domain (forprime, forcomposite, forstep), transforms what it prints
            # (2*n, n^3, a(6*n-3)/2), or supplies an argument the driver does not pass (a(n, 12)), the
            # def form computes a different sequence than the entry defines. Which of the two is right
            # is not decidable from the text -- it was tried as a static check and was wrong on 5 of 32
            # real blocks -- so both are offered and the gate decides: the def form runs first, and a
            # run that fails to verify leaves attempt_sequence's loop free to reach the loop form.
            if (rw := rewrite_print_loop(stmts)) is not None:
                kept_text, loop, loop_notes, facts = rw
                if (problem := loop_start_problem(facts, known)) is not None:
                    block_rejects.append(Rejected(bi, f"print loop refused: {problem}"))
                else:
                    builds.append(("print-loop", code.strip(), "\n".join([
                        kept_text,
                        "\\\\ ---- OEISBot driver: the program's own loop, printing through the emitter ----",
                        "default(debugmem, 0);",
                        _EMIT.format(name="oeisbot_i", first=known.first_index, work=0),
                        loop.replace("\n", " ") + ";",
                        "quit",
                    ]), None, loop_notes))
            if not builds and not block_rejects and bulk:
                block_rejects.append(Rejected(bi, f"{', '.join(bulk)} takes a single parameter with a default -- a "
                                                  "search bound, not an index: a bulk printer, not a term function"))
            if not builds and not block_rejects:
                names = ", ".join(defs) or "none"
                if any(_LIST_NAMES.match(n) for n in defs):
                    block_rejects.append(Rejected(bi, f"list-printing form not supported (defines {names})"))
                else:
                    block_rejects.append(Rejected(bi, f"no a(n), predicate, or single print loop (defines {names})"))
            made = False
            for form, src, script, start, notes in builds:
                # checked on the script, the text that actually runs: a driver statement calling another
                # entry's helper is dropped for the function forms and must not count against the block
                if missing := undefined_a_numbers(script):
                    block_rejects.append(Rejected(bi, f"uses {', '.join(missing)}, defined in another OEIS entry "
                                                     f"and not in this program"))
                    continue
                if script in seen:
                    continue
                seen.add(script)
                prog = Program("gp", src, origin=label, strategy=f"pari:{form}", script=script, notes=notes)
                buckets[form].append(Candidate(prog, form, search_start=start))
                made = True
            if not made:
                rejected.extend(block_rejects)
    # later programs in an entry are more often the faster rewrites; prefer them, function forms first
    return [c for form in ("a(n)", "predicate", "print-loop") for c in reversed(buckets[form])], rejected
