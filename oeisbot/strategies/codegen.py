"""Local-model code generation (build step 7).

  1. classify: ask the model which approach fits (brute force, search, DP / transfer matrix, formula)
     or whether to skip; when the known terms strictly increase, also whether the sequence is a list of
     numbers with a property or a(n) as a function of n (FORM)
  2. generate one Python function with a fixed contract: `terms(work)` yielding (n, a(n)) pairs (see
     runners/py_runner.py), or, for a list with strictly increasing known terms, `members(work)` yielding
     the members themselves, which a driver numbers from the offset (MEMBERS_DRIVER)
  3. static checks (defense in depth; the sandbox is the real boundary)
  4. run through the verification harness; on failure, retry with the actual error text
     (at most config.CODEGEN_ATTEMPTS generations; a program that already failed in the stage in a way
     that would recur there, REPEATS_IN_STAGE, is not run again)

Generated programs are marked as AI-generated everywhere they appear. OEIS policy forbids submitting
programs the submitter does not understand; the review artifact is where that understanding happens.
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Callable

from .. import config, db
from ..ingest.seqfile import Entry
from ..model import ModelClient
from ..terms import KnownTerms, Program
from ..verify import AttemptResult, Stop, _short

ALLOWED_IMPORTS = {"math", "itertools", "functools", "collections", "heapq", "bisect", "fractions", "operator",
                   "array", "gmpy2", "sympy", "numbers", "decimal"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals", "vars"}
APPROACHES = ("brute_force", "search", "dp_or_transfer_matrix", "formula", "skip")

SYSTEM = ("You are an expert in combinatorics, number theory and efficient Python. "
          "You write programs that compute integer sequences from the OEIS exactly.")


SHOWN_MAX = 30          # never show the model more known terms than this
SHOWN_FRACTION = 0.6   # ...nor more than this share: the rest are held out, so copied terms fail verification
HARDCODE_LIMIT = 6     # this many distinct known values (|v| >= 10) appearing as literals = copied, not computed


def shown_indices(known: KnownTerms) -> list[int]:
    """The known terms the model sees; always at least config.CODEGEN_HELD_OUT_MIN fewer than all of them."""
    ns = sorted(known.values)
    return ns[: max(0, min(SHOWN_MAX, max(3, int(len(ns) * SHOWN_FRACTION)), len(ns) - config.CODEGEN_HELD_OUT_MIN))]


# starts the reviewer note; artifact.write and the dashboard's Review inbox look for it
ENTRY_PROGRAM_NOTE = "the entry's own program"


@dataclass
class VerifiedRun:
    """A run of the entry's own program that reproduced every known term but found no new one: in this
    attempt, or in an earlier one that is now a dead end (then `verified_s` is not known)."""
    origin: str
    known_count: int
    stop: str
    detail: str
    attempt_id: int
    verified_s: float | None = None

    def describe(self) -> str:
        when = f"in {self.verified_s:.1f} s, " if self.verified_s is not None else ""
        return f"{self.origin}, {when}attempt #{self.attempt_id}"


def slow_program_note(v: VerifiedRun) -> str:
    """For the model, when the entry's own program already verified but found nothing new. Timing and the
    stop reason only, never a term value."""
    head = f"The entry's own program ({v.describe()}) already reproduces all {v.known_count} known terms"
    if v.stop == Stop.FINISHED.value:
        # it ended by itself: it may only cover the known range (a table, a fixed search limit)
        return (f"{head}, but then ended without a further term ({v.stop}: {v.detail}). It may only cover the "
                "known range: write a program that keeps going, using a fast method.")
    return (f"{head}, but then found no new term ({v.stop}: {v.detail}). A Python translation of it will be no "
            "faster: the goal is a fundamentally faster method.")


def _context(entry: Entry, known: KnownTerms, limit: int = 2500, note: str | None = None) -> str:
    shown = shown_indices(known)
    held = known.count - len(shown)
    parts = [f"Sequence {entry.a_number}: {entry.name}",
             *([note] if note else []),      # near the top: the truncation below cuts from the end
             f"Offset: the first term has index n = {known.first_index}.",
             f"Known terms: the first {len(shown)} of {known.count} are shown."
             f" Your program is checked against all {known.count}, including {held} you cannot see, so it must"
             " compute every term; hardcoded terms fail.",
             "\n".join(f"  a({n}) = {known.values[n]}" for n in shown)]
    if entry.formulas:
        parts.append("Formulas:\n" + "\n".join(f"  {f}" for f in entry.formulas[:8]))
    if entry.comments:
        parts.append("Comments:\n" + "\n".join(f"  {c}" for c in entry.comments[:8]))
    progs = [p for p in entry.programs if p.language in ("pari", "mathematica", "maple", "python", "magma", "sage")]
    if progs:
        parts.append("Existing programs (correct, possibly slow):\n" + "\n".join(
            f"  ({p.tag}) {p.code[:600]}" for p in progs[:4]))
    text = "\n".join(parts)
    return text if len(text) <= limit * 4 else text[: limit * 4] + "\n  [truncated]"


CLASSIFY = """{context}

Decide how to compute further terms of this sequence on a single desktop computer.
Answer with one JSON object and nothing else:
{{"approach": one of {approaches}, "reason": "<one sentence>", "plan": "<two or three sentences on the algorithm>"}}
Use "skip" when further terms clearly need a research breakthrough or huge computation."""

# Asked on its own, only when the known terms strictly increase. Folded into CLASSIFY, the model called two
# real lists (A129250, A057246) functions 4 times out of 4; asked alone, lists 4 times out of 4, and it
# matched the label on all 44 sequences it was tried on.
FORM = """{context}

Is this sequence a list of numbers that have some property, in increasing order (like "Numbers k such that
k^2 + 1 is prime" or "Primes p such that p + 2 is also prime"), or is a(n) a function of n (like "Number of
graphs on n nodes" or "Smallest prime with n digits")?
Answer with one JSON object and nothing else: {{"form": "list" or "function", "reason": "<one sentence>"}}"""

GENERATE = """{context}

Approach: {approach}. {plan}

{contract}
- Do not stop after the known terms; keep yielding until the process is killed.
- Call work(k) to report k units of real work (candidates tested, nodes visited, states expanded),
  batched, e.g. work(1000) once per 1000 inner-loop steps.
- Compute every term. Never copy known terms into the program.
- No fixed search limits (like limit = 1000): grow any sieve or search range as n increases.
- Reuse work between terms where possible instead of recomputing each a(n) from scratch.
- Prefer memory-lean methods: generators, DFS/backtracking rather than BFS, no huge lists.
- Allowed imports: {imports}. No file, network or subprocess access. Do not print anything.
Output a single ```python code block and nothing else."""

RETRY = """Your last program did not get through verification:

{failure}

{guidance}

{keep}
Output a single ```python code block and nothing else."""


@dataclass(frozen=True)
class Contract:
    """What the model is asked to write. `spec` opens the generation prompt's rules; `keep` closes a retry."""
    function: str
    spec: str
    keep: str


TERMS = Contract("terms", """Write Python 3.11 code defining exactly this generator:

def terms(work):
    # yields (n, a(n)) for n = {first}, {first}+1, {first}+2, ... in order, forever

Rules:
- Yield tuples (n, value) where value is a Python int or gmpy2.mpz. Start at n = {first}. Never skip an index.""",
                 "Keep the same contract (def terms(work) yielding (n, a(n)) from n = {first}).")

# For a list of numbers with a property. Mixing up the index n with the candidate k caused every bad_index
# failure the model had on such sequences (17 of 45 generations), so here the runner does the numbering.
MEMBERS = Contract("members", """This sequence is a list of numbers, in increasing order. Write Python 3.11 code defining exactly
this generator:

def members(work):
    # yields the members of the sequence themselves, smallest first, in increasing order, forever

The runner numbers what you yield: your first value becomes a({first}), the second a({second}), and so on.
Rules:
- Yield each member itself (for "Numbers k such that ...", yield k; for "Primes p such that ...", yield p),
  as a Python int or gmpy2.mpz: never a pair, never an index. Start from the smallest member, never skip
  one, and make each value larger than the one before.""",
                   "Keep the same contract (def members(work) yielding the members themselves, in increasing "
                   "order; the runner numbers them from a({first})).")

# appended to a `members` program; `terms` is the entry point py_runner calls. Its errors are
# verify.CONTRACT_ERROR (a test holds the two names together), which ends the run as `protocol` and, after
# verification, voids the run's new terms: a value arriving late means earlier ones may be misplaced. They
# name positions only, never a value: a value the program got right at a held-out index must not reach a
# retry prompt.
MEMBERS_DRIVER = """

# ---- OEISBot driver (not model-written): numbers the members from the offset ----
class OEISBotContractError(Exception):
    pass


def terms(work):
    index, previous = {first}, None
    for value in members(work):
        if isinstance(value, tuple):
            raise OEISBotContractError("members() must yield the members themselves, not (index, value) pairs")
        if previous is not None and not value > previous:
            raise OEISBotContractError(f"members() must yield increasing values: the value after a({{index - 1}}) "
                                       "was not larger than it")
        yield index, value
        index, previous = index + 1, value
"""
# starts the reviewer note on a `members` program; artifact.write and the dashboard's Review inbox look for it
MEMBERS_NOTE = "list contract"

# Named when a program crashes on an API that does not exist. These are the useful ones, not the full
# modules; `tests/test_codegen.py` checks every name against the sandbox runtime, because a hint list that
# invents a name is the very bug it exists to fix. `gmpy2.prime_range` is called out by name: the model
# invented it in three generations running, and the prime iterator actually lives in sympy.
API_NAMES = {
    "gmpy2": ["mpz", "mpq", "is_prime", "next_prime", "prev_prime", "gcd", "lcm", "isqrt", "iroot",
              "is_square", "fac", "bincoef", "comb", "divm", "powmod", "invert", "fib", "lucas",
              "popcount", "num_digits"],
    "sympy": ["primerange", "prime", "primepi", "isprime", "nextprime", "prevprime", "factorint",
              "divisors", "divisor_count", "totient", "mobius", "binomial", "factorial", "catalan",
              "fibonacci", "npartitions", "sieve"],
    "math": ["isqrt", "comb", "perm", "factorial", "gcd", "lcm", "prod"],
}
API_HINTS = ("Useful functions that do exist:\n"
             + "\n".join(f"  {mod}: {', '.join(names)}" for mod, names in API_NAMES.items())
             + "\nThere is no gmpy2.prime_range: to iterate primes use sympy.primerange.")

DEFINITION_GUIDANCE = ("Re-read the sequence definition and the first known terms, find where your "
                       "program's reading of the definition differs, and fix it.")
REPEAT_GUIDANCE = ("It was not run again: it would fail the same way every time. Change the program where the "
                   "failure points.")
# failures that recur if the same program runs again in one model stage: the deterministic ones, and a
# verify_timeout, since every generation of a stage runs under the same verify budget (db.is_dead_end
# treats a verify_timeout the same way across attempts, for verify budgets up to the time it ran)
REPEATS_IN_STAGE = (*db.DETERMINISTIC_FAILURES, Stop.VERIFY_TIMEOUT.value)


@dataclass
class Plan:
    approach: str
    reason: str
    plan: str
    form: str = "function"      # 'list' | 'function': the answer to FORM, asked after the plan


@dataclass
class CodegenOutcome:
    plan: Plan | None
    attempts: list[AttemptResult] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)    # static-check or extraction failures
    skipped: str | None = None

    @property
    def success(self) -> AttemptResult | None:
        return next((r for r in self.attempts if r.verified), None)


def parse_plan(text: str) -> Plan:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        data = {}
    approach = str(data.get("approach", "brute_force")).strip().lower()
    if approach not in APPROACHES:
        approach = "brute_force"
    return Plan(approach, str(data.get("reason", "")), str(data.get("plan", "")))


def parse_form(text: str) -> str:
    """The answer to FORM: 'list' only when the reply says so plainly, 'function' otherwise."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        data = {}
    return "list" if isinstance(data, dict) and str(data.get("form", "")).strip().lower() == "list" else "function"


def strictly_increasing(known: KnownTerms) -> bool:
    values = [known.values[n] for n in sorted(known.values)]
    return all(b > a for a, b in zip(values, values[1:]))


def contract_for(form: str, known: KnownTerms) -> Contract:
    """`members` only for a list whose known terms strictly increase, as a list's members must."""
    return MEMBERS if form == "list" and strictly_increasing(known) else TERMS


def extract_code(text: str, function: str = "terms") -> str | None:
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    return text.strip() + "\n" if f"def {function}" in text else None


def _literal_ints(tree: ast.AST) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if type(node.value) is int:
                found.add(abs(node.value))
            elif isinstance(node.value, str):
                found.update(abs(int(x)) for x in re.findall(r"\d+", node.value)[:10000])
    return found


def copied_terms(code: str, known_values) -> int:
    """How many distinct known term values (|v| >= 10) appear in the program as literals."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0
    big = {abs(v) for v in known_values if abs(v) >= 10}
    return len(big & _literal_ints(tree))


def _int_value(node: ast.AST, depth: int = 0) -> int | None:
    """An integer literal, or a constant expression of them such as 10**7 or 2*10**6; otherwise None.
    Expressions nested deeper than 32 levels are not evaluated (the recursion must stay bounded)."""
    if isinstance(node, ast.Constant):
        return node.value if type(node.value) is int else None
    if depth < 32 and isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Pow, ast.Mult, ast.Add, ast.Sub, ast.LShift)):
        a, b = _int_value(node.left, depth + 1), _int_value(node.right, depth + 1)
        if a is None or b is None:
            return None
        if isinstance(node.op, ast.Pow):
            return a ** b if 0 <= b <= 64 and abs(a) <= 10**6 else None
        if isinstance(node.op, ast.LShift):
            return a << b if 0 <= b <= 256 else None
        return a * b if isinstance(node.op, ast.Mult) else a + b if isinstance(node.op, ast.Add) else a - b
    return None


def fixed_bounds(code: str) -> list[str]:
    """Hard-coded limits that verification cannot see past: new terms beyond them may be silently wrong."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and (v := _int_value(node.value)) is not None and v >= 100:
            for t in node.targets:
                if isinstance(t, ast.Name) and re.search(r"limit|max|bound|upper|size|cap|sieve|^n$", t.id, re.I):
                    found.append(f"{t.id} = {v}")
        elif isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            if name in ("range", "primerange", "sieve", "primepi", "divisors_up_to"):
                for arg in node.args:
                    if (v := _int_value(arg)) is not None and v >= 1000:
                        found.append(f"{name}(..., {v})")
    return sorted(set(found))


def _binds_global(tree: ast.Module, name: str) -> bool:
    """Whether the module binds `name` at module level (a def, class, assignment, import or loop target, or
    a `global` declaration anywhere); names local to a function or class body do not count."""
    if any(isinstance(n, ast.Global) and name in n.names for n in ast.walk(tree)):
        return True
    stack: list[ast.AST] = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return True
            # the body is another scope; decorators and defaults are evaluated at module level
            stack.extend(node.decorator_list + node.args.defaults + [d for d in node.args.kw_defaults if d])
            continue
        if isinstance(node, ast.ClassDef):
            if node.name == name:
                return True
            stack.extend(node.decorator_list + node.bases + node.keywords)
            continue
        if isinstance(node, ast.Lambda):
            continue
        if isinstance(node, ast.alias) and (node.asname or node.name.split(".")[0]) == name:
            return True
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del)):
            return True
        if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name == name:
            return True
        if isinstance(node, ast.MatchMapping) and node.rest == name:
            return True
        stack.extend(ast.iter_child_nodes(node))
    return False


def static_check(code: str, known_values=(), function: str = "terms") -> str | None:
    """None if acceptable, otherwise why not. `function` is the contract's generator (`terms` or `members`)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"
    except (ValueError, RecursionError, MemoryError) as e:      # a null byte, or nesting too deep to parse
        return f"the program cannot be parsed ({type(e).__name__})"
    copied = copied_terms(code, known_values)
    if copied >= HARDCODE_LIMIT:
        return (f"the program contains {copied} known term values as literals; it must compute the terms, "
                "not copy them (it is checked against terms you have not seen)")
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function), None)
    if fn is None:
        return f"no top-level function `{function}` defined"
    if len(fn.args.args) != 1:
        return f"`{function}` must take exactly one argument (work)"
    if function != "terms" and _binds_global(tree, "terms"):
        # the driver defines `terms`, replacing whatever the program bound to that name: a reviewer would
        # read code that never ran, and the program would break in a way it cannot see
        return (f"do not use the name `terms` at module level: the runner supplies `terms` and numbers the "
                f"members itself; define only `{function}(work)` and helpers with other names")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bad = [a.name for a in node.names if a.name.split(".")[0] not in ALLOWED_IMPORTS]
            if bad:
                return f"import not allowed: {', '.join(bad)}"
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                return f"import not allowed: {node.module}"
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return f"use of `{node.id}` is not allowed"
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr not in ("__init__", "__name__"):
            return f"dunder attribute access `{node.attr}` is not allowed"
    return None


def _at_most(shown: str, bound: int) -> bool:
    """Whether a value as the harness printed it (long ones abbreviated, so unreadable) is at most `bound`."""
    try:
        return int(shown) <= bound
    except ValueError:
        return False


def _held_out_forms(known: KnownTerms, shown_last_index: int) -> set[str]:
    """Every way a failure detail could print a held-out known term the prompt does not also show: either
    sign, abbreviated as the harness abbreviates long values (verify._short) or in full."""
    shown = {v for n, v in known.values.items() if n <= shown_last_index}
    return {form for n, v in known.values.items() if n > shown_last_index and v not in shown
            for form in (_short(v), _short(-v), str(v), str(-v))}


def describe_failure(r: AttemptResult, shown_last_index: int | None = None, contract: Contract = TERMS) -> str:
    detail = r.detail
    # a program's own value can happen to be a held-out term (an off-by-one program), or one with its sign
    # flipped; the retry must not carry it (CLAUDE.md), so such a value is left out under either contract
    held = _held_out_forms(r.known, shown_last_index) if shown_last_index is not None else set()
    m = re.match(r"a\((-?\d+)\) = (.*?), known value ", detail)
    if r.stop is Stop.WRONG_TERM and m and shown_last_index is not None and int(m.group(1)) > shown_last_index:
        # a held-out term: never reveal its value, or the next program could special-case it. For a list, not
        # the program's value either: that would say the number is not in the list, and it could be excluded
        if contract is MEMBERS or m.group(2) in held:
            detail = f"a({m.group(1)}) is wrong (neither your value nor the correct one is shown; fix the computation)"
        else:
            detail = f"a({m.group(1)}) = {m.group(2)} is wrong (the correct value is not shown; fix the computation)"
    elif r.stop is Stop.WRONG_TERM and m and shown_last_index is not None and (
            (contract is MEMBERS and not _at_most(m.group(2), r.known.values[shown_last_index])) or m.group(2) in held):
        # a shown index, but the program's value is a held-out term, or (for a list) lies past the last term
        # shown, where it may be a held-out member: the correct value is in the prompt anyway
        detail = f"a({m.group(1)}) is wrong: it is {detail.split('known value ', 1)[1]} (your value is not shown)"
    b = re.match(r"program emitted n=(-?\d+), (expected n=.*)", detail)
    if r.stop is Stop.BAD_INDEX and b and b.group(1) in held:
        # the program put a value where the index belongs, and that value is a held-out term (saying so
        # would say it is a term)
        detail = f"program emitted a wrong index (not shown), {b.group(2)}"
    lines = [f"{r.stop.value}: {detail}"]
    if r.stop is Stop.BAD_INDEX:
        lines.append(f"The first yielded index must be n = {r.known.first_index}, then n+1, n+2, ...")
    if r.stop in (Stop.CRASH, Stop.INCOMPLETE) and r.run.stderr_tail.strip():
        lines.append("stderr (last lines):\n" + "\n".join(r.run.stderr_tail.strip().splitlines()[-12:]))
    # what to do about a slow or memory-hungry program is said once, by retry_guidance; state only the fact
    if r.stop in (Stop.VERIFY_TIMEOUT, Stop.TIMEOUT):
        lines.append(f"It reproduced {r.reproduced} of {r.known.count} known terms before the time limit.")
    if r.records and r.stop is Stop.WRONG_TERM:
        lines.append(f"Terms before that were correct: a({r.records[0].n})..a({r.records[-1].n}).")
    return "\n".join(lines)


def retry_guidance(stop: Stop | None) -> str:
    """What to tell the model to look at next. The failure type decides: pointing it at the sequence
    definition is right for a wrong value and misleading for a crash or a slow program, which is how one
    program failed three generations running with the same missing-API error. `stop` is None when the
    program never ran (no code block, or a static check).

    Every stop that can reach a retry is handled explicitly. The fall-through is deliberately last:
    a stop that lands there gets definition advice, so anything new added to `Stop` should be classified
    here rather than left to inherit it."""
    if stop is None:
        return "Fix that and send the program again."
    if stop is Stop.CRASH:
        return ("Your program raised an error. Fix the error itself: the reading of the definition is not "
                "in question unless the traceback shows that it is.\n\n" + API_HINTS)
    if stop in (Stop.BAD_INDEX, Stop.PROTOCOL):
        return ("This is an output-protocol error, not a mathematical one. Keep the algorithm as it is "
                "and fix what the generator yields.")
    if stop in (Stop.VERIFY_TIMEOUT, Stop.TIMEOUT, Stop.CPU_CAP):
        return ("The program was too slow, not wrong: its terms were right as far as it got. Keep your "
                "reading of the definition and use a fundamentally faster algorithm -- reuse work between "
                "terms, sieve or build up state once, and never recompute a(n) from scratch.")
    if stop is Stop.MEMORY_CAP:
        return ("The program ran out of memory, not out of logic. Keep your reading of the definition and "
                "use a memory-lean method: generators and DFS/backtracking rather than large lists or BFS.")
    if stop is Stop.INCOMPLETE:
        return ("Your generator stopped by itself before all the known terms were reproduced. It must keep "
                "yielding until the process is killed: remove any bound on the loop, and grow any sieve or "
                "search range as n increases. If no bound was the cause, re-read the definition.")
    # host conditions: the program is not at fault and a rewrite cannot help (see sandbox.windows)
    if stop is Stop.LAUNCH_ERROR:
        return ("The run never started, for a reason on this machine rather than in your program. Send your "
                "best program again, changed only if you can see a real fault in it.")
    if stop is Stop.DISK_CAP:
        return ("The run used too much disk. Generated programs must not write files at all: keep state in "
                "memory and keep it small.")
    if stop is Stop.OUTPUT_CAP:
        return ("Your program wrote far too much to stdout. Emit only the terms the contract asks for and "
                "print nothing else.")
    return DEFINITION_GUIDANCE


def generate_and_verify(entry: Entry, known: KnownTerms, model: ModelClient,
                        runner: Callable[[Program], AttemptResult], *,
                        log: Callable[[str], None] = print,
                        max_generations: int = config.CODEGEN_ATTEMPTS,
                        verified_elsewhere: VerifiedRun | None = None) -> CodegenOutcome:
    """runner(program) runs one program through the verification harness (and records it).
    `verified_elsewhere`: a run of the entry's own program that reproduced every known term but found no new
    one. The model is told so, and each generated program carries it as a note for the reviewer."""
    if known.count < config.CODEGEN_MIN_KNOWN_TERMS:
        raise ValueError(f"{known.a_number}: {known.count} known terms; at least {config.CODEGEN_MIN_KNOWN_TERMS} "
                         f"are needed to hold {config.CODEGEN_HELD_OUT_MIN} out from the model")
    context = _context(entry, known, note=slow_program_note(verified_elsewhere) if verified_elsewhere else None)
    plan = parse_plan(model.chat([{"role": "system", "content": SYSTEM},
                                  {"role": "user", "content": CLASSIFY.format(context=context, approaches=list(APPROACHES))}],
                                 max_tokens=400))
    out = CodegenOutcome(plan)
    log(f"model plan: {plan.approach}: {plan.reason}")
    if plan.approach == "skip":
        out.skipped = f"model judged infeasible: {plan.reason}"
        return out
    if strictly_increasing(known):
        plan.form = parse_form(model.chat([{"role": "system", "content": SYSTEM},
                                           {"role": "user", "content": FORM.format(context=context)}],
                                          temperature=0.2, max_tokens=200))
        log(f"model form: {plan.form}")
    contract = contract_for(plan.form, known)
    if contract is MEMBERS:
        log("asking for members(work), numbered by the runner")
    first = known.first_index
    keep = contract.keep.format(first=first)

    base = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": GENERATE.format(context=context, approach=plan.approach, plan=plan.plan,
                                                        contract=contract.spec.format(first=first, second=first + 1),
                                                        imports=", ".join(sorted(ALLOWED_IMPORTS)))}]
    messages = list(base)
    shown_last = shown_indices(known)[-1]
    # programs that ran and failed in a way that would repeat in this stage (REPEATS_IN_STAGE), by their syntax
    # tree (comments and layout aside): the model often sends the same program back, and running it again
    # cannot help
    failed_before: dict[str, tuple[int, AttemptResult]] = {}
    for gen in range(1, max_generations + 1):
        # retries at the same low temperature tend to repeat the same mistake
        reply = model.chat(messages, temperature=min(0.2 + 0.3 * (gen - 1), 0.9), max_tokens=2048)
        code = extract_code(reply, contract.function)
        problem = ("no ```python code block in the reply" if code is None
                   else static_check(code, known.values.values(), contract.function))
        # retries carry only the latest attempt and its failure, so the prompt stays inside the context window
        messages = base + [{"role": "assistant", "content": reply}]
        if problem:
            out.rejected.append(problem)
            log(f"generation {gen}: rejected before running: {problem}")
            messages.append({"role": "user", "content": RETRY.format(failure=problem, keep=keep,
                                                                     guidance=retry_guidance(None))})
            continue
        try:
            shape = ast.dump(ast.parse(code))
        except RecursionError:          # ast.dump recurses; a deep expression still parses
            shape = code
        if shape in failed_before:
            g, earlier = failed_before[shape]
            out.rejected.append(f"the same program as generation {g}, which failed with {earlier.stop.value}")
            log(f"generation {gen}: not run: the same program as generation {g}, which failed with {earlier.stop.value}")
            messages.append({"role": "user", "content": RETRY.format(
                failure=f"It is the same program as the one you sent in generation {g} (comments and layout "
                        f"aside), which failed:\n{describe_failure(earlier, shown_last, contract)}",
                keep=keep, guidance=f"{REPEAT_GUIDANCE} {retry_guidance(earlier.stop)}")})
            continue
        notes = [f"AI-generated by {model.name}; approach {plan.approach}"]
        if contract is MEMBERS:
            notes.append(f"{MEMBERS_NOTE}: the program yields the members; the runner's driver (in the executed "
                         f"program) numbers them from a({first}) and stops if they do not increase")
        notes += [f"fixed bound {b}: terms beyond what it covers may be wrong" for b in fixed_bounds(code)]
        if verified_elsewhere is not None:
            v = verified_elsewhere
            notes.append(f"{ENTRY_PROGRAM_NOTE} ({v.describe()}) reproduced all {v.known_count} known terms and "
                         f"found no new term ({v.stop}: {v.detail}); check any new terms against it")
        how = "; members(work), numbered by the runner" if contract is MEMBERS else ""
        prog = Program("python", code, origin=f"model {model.name}, generation {gen} (AI-generated{how})",
                       strategy="python:model", notes=notes,
                       script=code + MEMBERS_DRIVER.format(first=first) if contract is MEMBERS else None)
        result = runner(prog)
        out.attempts.append(result)
        log(f"generation {gen}: {result.outcome}: {result.stop.value} ({result.detail[:120]})")
        if result.verified:
            break
        if result.stop.value in REPEATS_IN_STAGE:
            failed_before.setdefault(shape, (gen, result))
        messages.append({"role": "user", "content": RETRY.format(failure=describe_failure(result, shown_last, contract),
                                                                 keep=keep, guidance=retry_guidance(result.stop))})
    return out
