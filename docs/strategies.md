# Strategies

How sequences are chosen, and the two ways the pipeline obtains a program for one: the entry's own PARI
code, and local-model code generation. Every program from either source is judged by the same
[verification harness](verification-and-estimation.md).

## Difficulty and selection

`oeisbot/select.py`.

### Difficulty

`difficulty(row)` multiplies factors starting from 1.0 (lower = easier):

| Feature | Factor |
|---|---|
| A runnable program in the entry: PARI / Python / Sage | ×0.3 / ×0.45 / ×0.5 (the smallest that applies) |
| Otherwise a Mathematica / Maple program | ×0.6 / ×0.7 (the smallest that applies) |
| Keyword `hard` | ×6 |
| Largest known last term, in digits (b-file if fetched, else DATA) | ×(1 + max(0, digits − 20) / 20) |
| "More terms" credits on `%E` lines (people already pushed it) | ×(1 + 0.75 × credits) |
| Name reads like a search ("smallest k such that ...") | ×1.5 |
| Number of known terms (b-file count if fetched, else DATA count) | ×(1 + log10(1 + terms / 50)) |

A credit is an `%E` line matching `more terms`, `additional terms`, `further terms`, `extended by`,
`terms extended`, `b-file extended`, or `a(n)-a(m) from` (case-insensitive).

Three places compute difficulty:

- `oeisbot sync` stores it in `sequences.difficulty` using DATA-line features only, overwriting any
  earlier value;
- `oeisbot fetch-bfiles` stores it again, including the b-file facts it just looked up;
- `select.candidates` recomputes it from the current row at pick time, including b-file facts when the
  b-file has been looked up, and multiplies in the failure penalty below.

The stored column is informational; selection never reads it.

### Failure penalty

At pick time: `× 2^k`, capped at `× 64`, where `k` counts earlier attempts on that sequence with outcome
`failed` or `verified` (skips, superseded runs, `recheck_pending` runs and wins do not count). The pool
is built once per session, so a failure affects the next session's picks. Which sequences are in the
pool at all is described in [pipeline](pipeline.md#2-selection-oeisbot-run--n-n---alpha-a---seed-s---model).

### Weighted pick

`weight = difficulty ** -alpha`. `alpha = 0` picks uniformly; the default 1 favors easy candidates;
larger values favor them more strongly. `oeisbot queue --alpha A` shows each candidate's resulting pick
probability.

`pick` draws `k` distinct candidates with a sum tree (a binary tree of partial sums: `O(log n)` sampling
and updates). After each draw that leaf's weight is set to 0. `--seed` fixes the random generator.

## PARI/GP

`oeisbot/strategies/pari.py`. Runs the programs already in the entry, for longer than their authors did.

### Where programs come from

`ingest/seqfile.py` collects `%o` lines into blocks. A block starts at a line beginning with a tag such
as `(PARI)`; tags are normalized (`PARI`, `PARI/GP` and `GP` all become `pari`), and following lines
without a tag continue the block. A block that holds several programs, each ending with a signature
comment (`\\ _Author Name_, Mon DD YYYY`), is split into parts.

### Reading GP code

- **Scanning** (`code_mask`): tracks strings, `\\` line comments and `/* */` block comments, so braces and
  parentheses inside them are ignored.
- **Statement splitting** (`split_statements`): a newline ends a statement unless it falls inside
  braces, inside open parentheses or brackets (joined with a space, which tolerates programs wrapped
  across `%o` lines), or after a trailing single `\`.
- **Classification** (`_classify`), on the comment-stripped text:
  - `def`: `name(params) = ...` or `name = (params) -> ...`
  - `assign`: `name = ...`, unless a later `;`-separated part is a loop or print (then `call`)
  - `keep`: `default(...)`, `\p`, `\ps`
  - `comment`: nothing left after stripping comments
  - `call`: anything else (`for(...)`, `print(...)`, `lista(1000)`, ...)

### Program forms

For each program part the first matching form is used.

**1. `a(n)` function.** A `def` named `a`, `A123456` or `a123456` (this entry's number) with at least one
parameter. The script is every `def`, `assign`, `keep` and `comment` statement (top-level calls such as
`vector(20, n, a(n))` are dropped), followed by this driver:

```
default(debugmem, 0);
{
  for(oeisbot_n = <first known index>, +oo,
    my(oeisbot_v = a(oeisbot_n));
    if(type(oeisbot_v) != "t_INT", error(...));
    print("@T ", oeisbot_n, " ", oeisbot_v, " ", getabstime() * 1000, " 0 ", default(parisize) + 8 * getheap()[2]));
}
quit
```

Cost unit: CPU time.

**2. Predicate.** A `def` named `is`, `isok`, `ok`, `isa`, `is_a`, `is_ok`, `isok1`, `isA123456` or
`is_A123456` (case-insensitive) with at least one parameter. Requires strictly increasing known terms,
since the driver lists every `k` for which the predicate is true, in order. The search starts at `k = 1`
(or at the first known term when it is below 1); indices start at the first known index. `work` counts
the candidates tested, so the estimator gets instrumented work counts.

**3. Print loop.** Tried when there is no `a(n)` or predicate function (helper functions are allowed and
kept). It needs exactly one driver statement: assignments followed by a single
bounded loop (`for`, `forprime`, `forstep`, `forcomposite`, `forsquarefree`) that is the last thing in
the statement, with exactly one `print` or `print1` in the whole program. For example
`for(n=1, 10^6, if(cond(n), print1(n, ", ")))`. The rewrite:

- replaces the print with `oeisbot_emit(expr)`, a helper that checks the value is an integer, prints an
  `@T` line and increments an index counter starting at the first known index. The print must be
  `print1(expr, "sep")`, `print1(expr)` or `print1(expr"sep")`, with no string inside `expr`;
- lifts literal loop bounds (digits combined with `*` and `^`, such as `10^6` or `2*10^5`) to `+oo`: the
  outermost loop's bound always, and inner loops' bounds when they are at least 1000 (search limits;
  small inner bounds such as `for(d=0, 9, ...)` are left alone);
- gives up when the outermost bound is not a literal (it cannot be run longer without guessing), when a
  loop has fewer than three arguments, or when no bound was lifted.

Every change is recorded in `Program.notes` and shown in the review artifact as
"Program was rewritten". The driver reports no work, so the estimator uses CPU time.

**Rejected**, with the reason logged per block:

- list printers: a `def` named `lista`, `list`, `upto`, `seq` or `A123456list`;
- a predicate whose known terms are not strictly increasing;
- anything else ("no a(n), predicate, or single print loop").

### Order and limits

Candidates are ordered: all `a(n)` forms, then predicates, then print loops. Within a form, programs that
appear later in the entry come first, since later additions are often faster rewrites. Identical
scripts are run once. At most 3 candidates are run per sequence; known dead ends are skipped without
running (see [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first)).

### Coverage (2026-09-17 snapshot)

Of the 5,316 candidates with a PARI program, measured with `oeisbot stats --forms` (the best supported
form per sequence):

| Form | Sequences |
|---|---|
| predicate | 2,153 |
| `a(n)` | 1,100 |
| print loop | 737 |
| list printer only (unsupported) | 434 |
| nothing usable (unsupported) | 892 |

That is 3,990 runnable (75%).

### Correctness caveats

- **Predicates are searched from `k = 1`.** A predicate that wrongly accepts smaller numbers would emit a
  wrong first term, which verification catches.
- **Print-loop rewrites change the program.** Lifting a bound can change what it computes. Verification
  catches changes that affect known terms, but not problems that only appear beyond them, for example a
  loop that does not enumerate values in increasing order. That is why rewrites are flagged for review.
- **Internal limits.** An `a(n)` or predicate program with an internal limit (a precomputed table, a
  `forprime` up to a constant) can verify and then produce wrong new terms. Unlike generated code, gp
  programs are not scanned for such limits.

## Local model code generation

`oeisbot/strategies/codegen.py` and `oeisbot/model.py`. Used only with `--model`, and only when the PARI
stage did not finish the sequence.

### Model client

`LocalModel` talks to the server set by environment variables (defaults in `config.py`):

| Variable | Default | Meaning |
|---|---|---|
| `OEISBOT_MODEL_API` | `ollama` | `ollama` uses `POST /api/chat` with `options.num_ctx`, `num_predict`, `temperature`; `openai` uses `POST /v1/chat/completions` |
| `OEISBOT_MODEL_URL` | `http://127.0.0.1:11434` | server address |
| `OEISBOT_MODEL` | `qwen2.5-coder:14b` | model name |
| `OEISBOT_MODEL_CONTEXT` | `8192` | context window (Ollama only). 8k keeps a 14B model entirely on a 12 GB GPU; 16k would spill onto the CPU |

Requests time out after 600 s. Connection failures raise `ModelUnavailable`. `available()` lists the
server's models (`/api/tags` or `/v1/models`) and accepts an exact name match or a match on the name
before `:`. The model is called from the harness process; generated code runs in the sandbox, which has
no network, so it cannot reach the model.

### What the model is shown

`_context` builds the same context for both steps:

- the name, and the first index (offset);
- **the first `min(30, max(3, ⌊0.6 × count⌋), count − 2)` known terms**. The rest are held out, always at
  least 2, and the prompt says how many are hidden and that the program is checked against them. With 3
  known terms 1 is shown, with 4 known terms 2, with 5 or 6 known terms 3. Below 3 known terms the model
  stage does not run at all (skip `too_few_known_terms`; `generate_and_verify` itself raises
  `ValueError`);
- up to 8 `%F` formulas and 8 `%C` comments;
- up to 4 existing programs (PARI, Mathematica, Maple, Python, Magma or Sage), each cut to 600 characters;

cut at 10,000 characters in total.

### Steps

1. **Classify** (temperature 0.2, up to 400 tokens): the model answers with JSON
   `{"approach", "reason", "plan"}`, where approach is `brute_force`, `search`, `dp_or_transfer_matrix`,
   `formula` or `skip`. An unparsable reply means `brute_force` with no plan. `skip` ends the model stage
   (recorded as `model_skip`).
2. **Generate** (up to 3 generations, up to 2048 tokens each; temperature 0.2, then 0.5, then 0.8,
   because retries at a low temperature tend to repeat the same mistake). The prompt gives the contract
   `def terms(work)` and these rules: yield `(n, value)` from the first index with no gaps; never stop;
   report work in batches; compute every term and never copy known terms; no fixed search limits; reuse
   work between terms; prefer memory-lean methods; only the allowed imports; no file, network or
   subprocess access; no printing; reply with one Python code block.
3. **Extract** the longest fenced Python block (or the whole reply if it contains `def terms`).
4. **Static checks** (defense in depth; the sandbox is the real boundary), in order:
   - the code parses;
   - fewer than 6 distinct known term values with absolute value ≥ 10 appear as integer literals or
     inside string literals. This is checked against **all** known terms, including held-out ones;
   - a top-level `def terms(work)` with exactly one argument exists;
   - imports only from `math`, `itertools`, `functools`, `collections`, `heapq`, `bisect`, `fractions`,
     `operator`, `array`, `gmpy2`, `sympy`, `numbers`, `decimal`;
   - no use of `open`, `exec`, `eval`, `compile`, `__import__`, `input`, `breakpoint`, `globals`, `vars`;
   - no dunder attribute access other than `__init__` and `__name__`.

   A failed check becomes the retry message, without running anything; its guidance is a plain "fix that
   and send the program again", since no run happened to diagnose.
5. **Flag fixed bounds** (`fixed_bounds`), without rejecting: assignments of an integer ≥ 100 to a name
   matching `limit`, `max`, `bound`, `upper`, `size`, `cap`, `sieve` or exactly `n`; and integer literals
   ≥ 1000 passed to `range`, `primerange`, `sieve`, `primepi` or `divisors_up_to`. Each becomes a
   "fixed bound" note, shown in the artifact and dashboard, because new terms beyond such a limit can be
   wrong even though verification passed.
6. **Run** through the same runner as PARI programs: strategy `python:model`, origin
   `model <name>, generation <g> (AI-generated)`, recorded in the database, source saved to `data/runs/`,
   and on success re-checked and turned into an artifact.
7. **Stop** at the first verified program, even if it found no new terms.
8. **Retry** after a failed run with a message holding the stop reason and detail, plus hints:
   - `bad_index`: the first index must be the offset, then consecutive;
   - `crash` or `incomplete`: the last 12 stderr lines;
   - `verify_timeout` or `timeout`: how many known terms were reproduced;
   - `wrong_term`: the range of terms that were correct. **If the wrong term is a held-out one, its correct
     value is replaced by "the correct value is not shown"**, so the next program cannot special-case it.

   The retry also carries an instruction that depends on the failure (`retry_guidance`), because what the
   model should look at differs:
   - `crash`: fix the error itself, not the reading of the definition, plus a list of functions that do
     exist in `gmpy2`, `sympy` and `math` (`API_NAMES`, checked against the sandbox runtime by a test);
   - `bad_index`, `protocol`: an output-protocol error — keep the algorithm, fix what is yielded;
   - `verify_timeout`, `timeout`, `cpu_cap`: too slow, not wrong — keep the reading, use a faster algorithm;
   - `memory_cap`: keep the reading, use a memory-lean method;
   - `incomplete`: the generator stopped by itself — it must yield until killed, so remove any bound;
   - `launch_error`: the run never started for a reason on the host, not in the program;
   - `disk_cap`: too much disk — generated programs must not write files;
   - `output_cap`: too much on stdout — emit only the contract's terms;
   - `wrong_term` and anything else: re-read the definition and find where the program's reading differs
     (the original wording, which used to be sent for every failure).

   Every stop that can reach a retry is classified: stops that only occur after verification never retry,
   because a verified program ends the loop. A test asserts that nothing retryable is left inheriting the
   definition advice, so a new `Stop` has to be classified deliberately.

   Each retry sends only the system prompt, the original task, the latest reply and the latest failure,
   not the whole conversation, to stay inside the context window.

### Why the defenses exist

In the first real test (before these defenses, when the prompt listed the first 40 and last 5 known
terms) the model's second program for semiprimes (A001358) hard-coded all 61 known terms as a literal
list and used a prime table capped at 1000 for anything further. It passed verification and reported new
terms. The holdout, the literal check, the redaction and the bound flags were added in response.

With them in place, the model solved 4 of 5 easy test sequences honestly (divisor counts, Catalan
numbers, palindromic primes, powers of 2). Semiprimes failed all 9 generations across three runs, each
time leaving out squares such as 4 = 2×2 and 9 = 3×3, and verification rejected every one.

### Contract for generated programs

The same contract applies to any Python program run through the harness (see
[verification](verification-and-estimation.md#python-programs)):

```python
import math                      # only allowed modules

def terms(work):
    n = 0                        # the sequence's first index
    while True:
        value = ...              # compute a(n); int or gmpy2.mpz
        work(1)                  # or batched work(k)
        yield n, value
        n += 1
```
