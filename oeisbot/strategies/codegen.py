"""Local-model code generation (build step 7).

  1. classify: ask the model which approach fits (brute force, search, DP / transfer matrix, formula)
     or whether to skip
  2. generate one Python function `terms(work)` with a fixed contract (see runners/py_runner.py)
  3. static checks (defense in depth; the sandbox is the real boundary)
  4. run through the verification harness; on failure, retry with the actual error text
     (at most config.CODEGEN_ATTEMPTS generations)

Generated programs are marked as AI-generated everywhere they appear. OEIS policy forbids submitting
programs the submitter does not understand; the review artifact is where that understanding happens.
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Callable

from .. import config
from ..ingest.seqfile import Entry
from ..model import ModelClient
from ..terms import KnownTerms, Program
from ..verify import AttemptResult, Stop

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


def _context(entry: Entry, known: KnownTerms, limit: int = 2500) -> str:
    shown = shown_indices(known)
    held = known.count - len(shown)
    parts = [f"Sequence {entry.a_number}: {entry.name}",
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

GENERATE = """{context}

Approach: {approach}. {plan}

Write Python 3.11 code defining exactly this generator:

def terms(work):
    # yields (n, a(n)) for n = {first}, {first}+1, {first}+2, ... in order, forever

Rules:
- Yield tuples (n, value) where value is a Python int or gmpy2.mpz. Start at n = {first}. Never skip an index.
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

Keep the same contract (def terms(work) yielding (n, a(n)) from n = {first}).
Output a single ```python code block and nothing else."""

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


@dataclass
class Plan:
    approach: str
    reason: str
    plan: str


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


def extract_code(text: str) -> str | None:
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    return text.strip() + "\n" if "def terms" in text else None


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


def fixed_bounds(code: str) -> list[str]:
    """Hard-coded limits that verification cannot see past: new terms beyond them may be silently wrong."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and type(node.value.value) is int \
                and node.value.value >= 100:
            for t in node.targets:
                if isinstance(t, ast.Name) and re.search(r"limit|max|bound|upper|size|cap|sieve|^n$", t.id, re.I):
                    found.append(f"{t.id} = {node.value.value}")
        elif isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            if name in ("range", "primerange", "sieve", "primepi", "divisors_up_to"):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and type(arg.value) is int and arg.value >= 1000:
                        found.append(f"{name}(..., {arg.value})")
    return sorted(set(found))


def static_check(code: str, known_values=()) -> str | None:
    """None if acceptable, otherwise why not."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"
    copied = copied_terms(code, known_values)
    if copied >= HARDCODE_LIMIT:
        return (f"the program contains {copied} known term values as literals; it must compute the terms, "
                "not copy them (it is checked against terms you have not seen)")
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "terms"), None)
    if fn is None:
        return "no top-level function `terms` defined"
    if len(fn.args.args) != 1:
        return "`terms` must take exactly one argument (work)"
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


def describe_failure(r: AttemptResult, shown_last_index: int | None = None) -> str:
    detail = r.detail
    m = re.match(r"a\((-?\d+)\) = (.*?), known value ", detail)
    if r.stop is Stop.WRONG_TERM and m and shown_last_index is not None and int(m.group(1)) > shown_last_index:
        # a held-out term: never reveal its value, or the next program could special-case it
        detail = f"a({m.group(1)}) = {m.group(2)} is wrong (the correct value is not shown; fix the computation)"
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
                        max_generations: int = config.CODEGEN_ATTEMPTS) -> CodegenOutcome:
    """runner(program) runs one program through the verification harness (and records it)."""
    if known.count < config.CODEGEN_MIN_KNOWN_TERMS:
        raise ValueError(f"{known.a_number}: {known.count} known terms; at least {config.CODEGEN_MIN_KNOWN_TERMS} "
                         f"are needed to hold {config.CODEGEN_HELD_OUT_MIN} out from the model")
    context = _context(entry, known)
    plan = parse_plan(model.chat([{"role": "system", "content": SYSTEM},
                                  {"role": "user", "content": CLASSIFY.format(context=context, approaches=list(APPROACHES))}],
                                 max_tokens=400))
    out = CodegenOutcome(plan)
    log(f"model plan: {plan.approach}: {plan.reason}")
    if plan.approach == "skip":
        out.skipped = f"model judged infeasible: {plan.reason}"
        return out

    base = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": GENERATE.format(context=context, approach=plan.approach, plan=plan.plan,
                                                        first=known.first_index, imports=", ".join(sorted(ALLOWED_IMPORTS)))}]
    messages = list(base)
    shown_last = shown_indices(known)[-1]
    for gen in range(1, max_generations + 1):
        # retries at the same low temperature tend to repeat the same mistake
        reply = model.chat(messages, temperature=min(0.2 + 0.3 * (gen - 1), 0.9), max_tokens=2048)
        code = extract_code(reply)
        problem = "no ```python code block in the reply" if code is None else static_check(code, known.values.values())
        # retries carry only the latest attempt and its failure, so the prompt stays inside the context window
        messages = base + [{"role": "assistant", "content": reply}]
        if problem:
            out.rejected.append(problem)
            log(f"generation {gen}: rejected before running: {problem}")
            messages.append({"role": "user", "content": RETRY.format(failure=problem, first=known.first_index,
                                                                     guidance=retry_guidance(None))})
            continue
        notes = [f"AI-generated by {model.name}; approach {plan.approach}"]
        notes += [f"fixed bound {b}: terms beyond what it covers may be wrong" for b in fixed_bounds(code)]
        prog = Program("python", code, origin=f"model {model.name}, generation {gen} (AI-generated)",
                       strategy="python:model", notes=notes)
        result = runner(prog)
        out.attempts.append(result)
        log(f"generation {gen}: {result.outcome}: {result.stop.value} ({result.detail[:120]})")
        if result.verified:
            break
        messages.append({"role": "user", "content": RETRY.format(failure=describe_failure(result, shown_last),
                                                                 first=known.first_index,
                                                                 guidance=retry_guidance(result.stop))})
    return out
