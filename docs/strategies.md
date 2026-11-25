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

At pick time: `× 2^k`, capped at `× 64`, where `k` counts earlier attempts on that sequence with at least
one row whose outcome is `failed` or `verified` (skips, superseded runs, `recheck_pending` runs and wins
do not count). **A row whose stop is `interrupted` does not count either** (since history item 58,
`db.INTERRUPTED`): the run was stopped by its caller, `oeisbot daemon`, for reasons of the machine or
the clock, and counting it would make every sequence a stop happened to land on twice as hard to pick.
An attempt that has another `failed` or `verified` row beside the interrupted one still counts once.
Two kinds of row that are not the program's doing do still count, because they are `failed` rows with
another stop: a `harness_error`, and a `verify_timeout` on a machine too busy to give the run its CPU
(which is no longer a dead end, see [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first)).
An attempt is one `attempt_sequence` call (one sequence of an `oeisbot attempt` command,
or one pick of a session). It writes a row per program run, up to three PARI runs and three model
generations, and all of them carry the same `extra.attempt_call`, so the attempt counts once. Until
2026-09-19 (offer D) every row counted; the 108 run rows written before then were given their attempt's
key once (`legacy-<first row id>`). A row without a key, or with an unreadable `extra`, counts on its
own. The pool is built once per session, so a failure affects the next session's picks. Which sequences are in the
pool at all is described in [pipeline](pipeline.md#2-selection-oeisbot-run--n-n---alpha-a---seed-s---model).

### Weighted pick

`weight = difficulty ** -alpha`. `alpha = 0` picks uniformly; the default 1 favors easy candidates;
larger values favor them more strongly. `oeisbot queue --alpha A` shows each candidate's resulting pick
probability.

`pick` draws `k` distinct candidates with a sum tree (a binary tree of partial sums: `O(log n)` sampling
and updates). After each draw that leaf's weight is set to 0. `--seed` fixes the random generator.

**Not drawn at all** (`select.candidates`' blocked set): a sequence with a review at `new`, `reviewing`
or `submitted`, one with a win waiting for its re-check, and, since history item 58, one with a
`rejected` review. A win for a sequence with a rejected review is refused a review
(`db.ReviewRefused`), so drawing it could only spend the run and write an artifact folder nobody is
shown, and an unattended loop would do that every time the draw landed on it. Only the draw is blocked:
`oeisbot attempt A...` still runs such a sequence. It stays out for as long as the rejected row stands.
**No review status returns a sequence to the draw any more**: the four statuses a row can have (`new`,
`reviewing`, `submitted`, `rejected`) all block it, and no command deletes a review row. Today the
rejected ones are A162762 and A162764 (see [known limitations](known-limitations.md#the-daemon-and-the-writers-lock)).

Before the draw, sessions (and `oeisbot queue` and `oeisbot pick`) leave out sequences an attempt could
only skip: no supported PARI program, every program a known dead end, or every program out of reach of
the verify budget. See [pipeline](pipeline.md#2-selection-oeisbot-run--n-n---alpha-a---seed-s---model).

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

Each program part yields a **function form if one matches, and its own print loop as well if that can be
rewritten** — up to two candidates from one part. Since 2026-09-25; before then the first matching form
won and the loop was discarded.

The two are not interchangeable. The drivers below scan every index or every `k` from the start and emit
the bare value, so where the part's own loop restricts the domain (`forprime`, `forcomposite`,
`forstep`), transforms what it prints (`2*n`, `n^3`, `a(6*n-3)/2`), or supplies an argument the driver
does not pass (`a(n, 12)`), the function form computes a *different sequence* than the entry defines —
hand-checked at **18 of 32 such blocks in the live pool**. Which of the two is right is not decidable
from the text: a static check for it was written and measured against those same 32, and got 15 right,
**missed 3 and wrongly flagged 2**, so none ships. Both are offered, the function form runs first,
and the gate decides — a run that fails to verify leaves the loop form its turn in the same attempt.

Both candidates carry the same `origin` (the `%o` block label) and are told apart by `strategy`
(`pari:a(n)` vs `pari:print-loop`) and by `program_sha`.

A `def` is only driven if the drivers can actually call it with one argument: it needs a parameter, and
**every parameter after the first must have a default** (`pari._drivable`). gp does not refuse a call
that omits an argument — it binds the parameter to 0 and runs on, so the program silently computes
something else. A366832's `isok(k, b)`, whose own loop supplied `b = 9`, reached `digits(k, 0)`. It is
every parameter after the first rather than a count of those lacking defaults, because gp fills omitted
arguments from the left: `f(a=1,b)=[a,b]; f(7)` gives `[7, 0]`.

**A def whose *only* parameter carries a default is refused as a bulk printer** (2026-09-30, history
item 53; `pari._bulk_printer`): `a373945(upto=10^8)`, `a368129(rmax=235)` take a search bound, not an
index, and called with an index they run the search up to it and print a list — the driver's `@T` lines
then land on the program's own output, which the harness ignores, and the run is a plain timeout with
nothing in the row to say why (sessions 7 and 11). Measured over the corpus the same day: **4 such
defs, all four bulk printers, two in the pool** (A368124, A375093). The block's reason names the def;
its own print loop, if it has one, is still offered.

**A print loop that starts in the wrong place is refused** (2026-09-30, item 53;
`pari.loop_start_problem`, on `LoopFacts` the rewriter now returns). The emitter numbers from the first
known index whatever the loop does, so an **index loop** — one that prints on every iteration — must
start at the offset (A290024's `for(n=1, 7, ...)` under `%O 0` emitted a(2) as a(1) and a *correct*
program was retired `wrong_term`, session 11), and a **filter loop** that prints its own variable — one
whose print sits behind an `if`, a `&&`/`||` guard or an inner loop — must start at or below the first
known term (A215906's `for(i=2, ...)` under `%S 0,6,...` emitted 6 as a(1), session 12). Only a literal
start is judged, only a plain `for` counts as an index loop, and a filter loop that prints an expression
is left to the gate. Measured over the pool before building: 26 index loops off the offset, 20 filter
loops above the first term, **44 pool sequences**; the user chose refusing over renumbering because a
refusal costs a candidate where a wrong renumbering costs a sequence. What it removed is in item 53.

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

Because the driver tests every `k` in turn, reproducing the known terms costs at least one predicate
call per integer from the start up to the last known term, however cheap the predicate is. The cheapest
predicate there is, a single comparison, runs at about 5.8 million calls a second in the sandbox on this
machine, so `pari.out_of_reach` treats `PREDICATE_MAX_RATE` = 2 × 10^7 calls/s as a ceiling, with over 3×
headroom for faster hardware: a predicate program whose search would need more calls than that in
`verify_wall_s` is not run (at the default 60 s, a last known term above 1.2 × 10^9). A sandbox test times
the single-comparison predicate and fails if it ever comes within 1.5× of the constant.
The bound says nothing about the more common expensive predicates, whose cost is per call (for example
"numbers k such that 8191·2^k + 1 is prime"): those are left to the verify budget.

The scan runs in **blocks**, and after each one the driver prints a progress heartbeat
(`@P k tested cpu_us`) so that a run killed mid-scan still records how far it got — the driver otherwise
prints only when the predicate is true, and a killed run would leave no trace of its position. The block
is sized in time (it doubles under `HEARTBEAT_TARGET_MS`, halves when a block overruns it fourfold), and
the blocked loop costs about 4% of scan throughput against the unbounded loop it replaced. What the
harness will and will not believe about a heartbeat is in
[verification](verification-and-estimation.md#progress-heartbeats-predicate-form-only).

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

### Searched bounds apply to the predicate form only

The [searched-bound check](verification-and-estimation.md#the-searched-bound-check) skips an extension
when the entry itself publishes a range already searched. It is offered a bound only for the **predicate**
form, and that restriction is mechanical, not a matter of taste.

For a predicate program the driver tests k = `search_start`, `search_start`+1, ... and the terms *are* the
k that pass, so a bound on a term's **value** is a bound on the driver's **work**. For the other two forms
the loop variable need not be the term value at all. The pool holds the contrast side by side:

| Entry | Name | Terms are | A value bound |
|---|---|---|---|
| A038582 | Numbers k such that the sum of the first k primes is a palindrome | `k` | applies |
| A038583 | Palindromes that are the sum of consecutive initial primes | the sums | does **not** apply |

The same underlying search, opposite mappings. Independently of that, `A_DRIVER` prints a literal `0` for
`work` and the print-loop emitter is formatted with `work=0`, so for those two forms there is no measured
rate to compare a bound against even in principle.

### Order and limits

Candidates are ordered: all `a(n)` forms, then predicates, then print loops. Within a form, programs that
appear later in the entry come first, since later additions are often faster rewrites. Identical
scripts are run once. The ordering is entry-wide, not per block, which is what stops a block's own loop
from displacing a function form under the 3-candidate limit: every print loop sorts after every function
form, wherever it came from.

A block reports a **`Rejected`** — a form it could not build — only when the *whole block* came to
nothing. A print loop calling another entry's helper says nothing about the `a(n)` form beside it, whose
script never contains that call, so a block that yielded any candidate is not reported as rejected.

At most 3 candidates are run per attempt; known dead ends and out-of-reach
predicates are skipped without running (see [pipeline](pipeline.md#4a-the-entrys-own-pari-programs-always-first)).
The first program that reproduces every known term ends the PARI stage, whether or not it found new
terms; if it found none, the model stage may still run. Across attempts it does not: once a program has
verified and then found nothing new with no smaller budget (an `infeasible` or `extend_budget` dead end),
a later attempt at that budget skips it and runs the entry's next program (since 2026-09-19, offer E;
before that the others were held back).

### Coverage (2026-09-26 snapshot)

Of the 5,316 candidates with a PARI program, measured with `oeisbot stats --forms` (the best supported
form per sequence):

| Form | Sequences |
|---|---|
| predicate | 2,128 |
| `a(n)` | 1,029 |
| print-loop | 739 |
| no usable function (unsupported) | 905 |
| list printer only (unsupported) | 443 |
| calls another entry's helper (unrunnable) | 65 |
| author calls it conjectural (refused) | 7 |

That is **3,896 runnable (73.3%)**, and the rows sum to 5,316.

Two rows exist because a measurement moved a sequence out of "runnable" rather than because a form was
added. The **helper** row is from 2026-09-20 (item 33): those 65 had a supported form and were counted as
runnable until then, but every one fails at its first call into another entry — see below. The
**conjectural** row is from 2026-09-26 (item 47): 5 of its 7 define a perfectly good `a(n)` or predicate
and are refused for what their author said about the program, not for its shape, so filing them under
"no usable function" would be false.

**This table was re-measured for item 47 and the previous numbers were already stale** — the
2026-09-20 snapshot read predicate 2,138, `a(n)` 1,052, print loop 735, list printer 434, nothing usable
892, for 3,925 runnable (74%). Item 46 moved every one of them by changing what `build_candidates` builds
(a `%o` part now offers its own print loop as well as its def, and a def needing a second argument is
refused), which is why the shift here is much larger than the 7 this item refused. Re-run
`oeisbot stats --forms` rather than adjusting these by hand.

### Programs that call another entry's helper

An OEIS `%o` block may use a helper defined in a *different* entry: `A147803(n) = ... A007947(n-a) ...`,
or `A147805`, which reads `a147798[n]`. gp accepts the program, runs it and errors at the first such
call or index, so it can never reproduce the known terms. `pari.undefined_a_numbers` finds them
statically, and `build_candidates` rejects the block with reason `uses <names>, defined in another OEIS
entry and not in this program`, which surfaces as the skip reason `no_supported_program`.

- **What counts as a use:** a call or an index by a name that carries an A-number — `A007947(n)`,
  `a147798[n]`, and since 2026-09-30 (history item 51) helpers named *around* one, `is_A178751(n)`
  (A274003, session 11) and `a375301_row(n)` (A375302, session 7), which live in another entry just as
  often. **The whole identifier is captured and compared** against the block's definitions: capturing
  only the A-number would flag `is_A034293` in `is_A034293(n) = ...`, a program that verified in session
  11. A *bare* mention is left alone, because gp does not fail on it — an unknown name is a polynomial
  variable, so `n + A007947` prints the expression unevaluated and `#A007947` is 2. Those programs fail
  later, and their own stop reason says how.
- **What counts as defined** is read generously, since wrongly calling a name undefined would throw away
  a program that runs: any definition or assignment (`my(m = ...)` included), and any parameter name,
  whether of a function `f(x, &y) = ...` or of a closure `(x) -> ...`. Parameter lists are read to their
  **balanced** close (since 2026-09-30): `A122172_row(n, p = part(n)) = {...}` defines `A122172_row`,
  `n` and `p`; the `[^()]*` regexes this replaced could not cross the call in the default, so such a
  statement was classified as a call, dropped, and its own name reported undefined. A default value only
  *uses* the names in it, it does not define them: `my(m = A034386(p))` declares `m` and uses `A034386`,
  which is how `A242998(n, p = A000043[n])` is caught. A bare `my(x)` with no value is deliberately *not*
  a definition — it is the one declaration gp still errors on when the name is then called or indexed, so
  honouring it could only suppress a correct rejection. Matches inside strings and comments are ignored
  (`code_mask`).
- **Measured (2026-09-30, item 51; `data/measure0930/diff.txt`):** the balanced parse reclassifies
  exactly the **40 statements in 36 blocks** item 46 counted, from call to def. Against the corpus of
  5,316 PARI-bearing sequences that is **31 sequences gaining a candidate** (4 of them only a new sha,
  because a helper def is now kept beside the program) and **12 losing one** — every one of the 12 to
  the whole-identifier check, and every flagged name a helper from another entry by inspection (the
  predicates of A005835, A239058, A006037, A178751, A002975 twice, A005153 twice, A050936 and A267124,
  A375301's row function and A394890's square helper — named in `data/measure0930/diff.txt`, not
  quoted here, because `check_docs.py` would count each as a missing identifier); candidates 4,239 →
  4,253, rejections 1,576 → 1,562. The 27 genuinely new programs were read before being trusted: most are ordinary defs with
  defaults after the first parameter (`is(n, p=prime(n))`); a few will only ever waste a pick
  (A277852/A277853 return a set, not an integer; A278832 is a chess brute force marked "for illustrative
  purpose only"; A294900's def is head-only, below), and the gate decides, as item 46 intended.
- **Known gap left by that measurement:** a def whose `{` body starts on the *next* line
  (`is(n, f=factor(n))=` then `{ ... }`) is split by `split_statements` into a head-only def and a call
  block the function forms drop, so the kept program defines the function with the wrong body. Counted
  2026-09-30: **11 such defs in 10 sequences**, 9 of them followed by a `{` block
  (`data/measure0930/headonly.txt`); not fixed here because joining a line that ends in `=` with the
  next is a change to the statement splitter with its own blast radius.
- **Checked on the script that runs**, not on the block: driver statements are dropped for the function
  forms, so a helper named only in a dropped statement is never called and does not reject the block.
- **Measured (2026-09-20):** 65 of the 3,990 sequences that used to produce a candidate lose all of them,
  and 5 more lose one of two. That is **1.97% of the pick weight of a PARI-only session** and about
  **0.39 wasted picks per 20** — measured on the pool a session actually draws from, which `Runnable` has
  already filtered to 3,552 (the share of the unfiltered 5,316-candidate corpus is the smaller and less
  meaningful 1.40%). With `--model` on it is 0.47% and 0.09 picks, because nothing leaves that pool.
  The session pool shrinks by 58 rather than 65: 5 of the entries were already `verify_out_of_reach` and
  2 `all_programs_dead_ends`.
  All 71 rejected candidates were run through the harness before the check was written: none reproduced
  the known terms, so the rule costs nothing (see [status](status.md), history item 33).
- **Over-approximation:** gp only errors on a use it *reaches*. A block whose undefined call sits in a
  branch the known terms never take, or in a function nothing calls, would be rejected although it might
  have run; so would one whose helper is a closure parameter of a form not recognised here. No entry in
  the corpus is such a case. Eight of the 71 do emit 1–5 terms before reaching the call (A087638,
  A143700, A195264, A285331, A291786, A332081, A341715, A341717) — they still cannot reproduce the rest.

### Programs whose author calls them conjectural

A published program may carry its author's own disclaimer: A162763's closed form is annotated
`\\ Proved to be an upper bound, conjectured to be exact`. Such a program cannot extend the sequence,
and the reason is not that it is wrong — it is that **the verification gate learns nothing from it**.
Conditional on a conjecture published in OEIS, the closed form reproduces every known term by
construction, so agreement carries almost no information, and the run then emits values without limit
until `max_new_terms` stops it. Session 10 did exactly that twice, 200 values each for A162762 and
A162764, and opened two review rows that must never be submitted ([status](status.md), history item 45).

`pari.conjectural` finds them statically and `build_candidates` rejects the part with reason
`the program describes itself as <word> (a conjectural program cannot extend the sequence)`, surfacing
as the skip reason `no_supported_program`.

- **Why acting on an author's prose is legitimate here.** This is
  [invariant 10](development.md#invariants)'s rule: an unverified human claim may stop us spending time
  and may never be evidence about a term's value. The check only ever *stops* a run. It is the same
  reason the `%C` comments stay unread — see the measurement below.
- **The words are `conjectur*`, `heuristic*`, `unproved`, `unproven`, `not proved`**, case-insensitive.
  Deliberately narrow, and **measured over all 5,315 `more` entries with a PARI part (2026-09-26)**:
  7 parts match, 3 of them in the live pool. `heuristic` adds exactly one real member (A349899, whose
  comment says the program "fails if a(n) is divisible by a prime >= prime(n+2)"); the last three add
  nothing today and are insurance against a future `sync`. **`upper bound`, `lower bound`, `assuming`,
  `probable` and `believed` were measured and left out**: they take the count to 20 and are dominated by
  false positives — optional parameters literally named that (A002071, A217016, A340630) and the
  "assuming the vector A002975 holds enough terms" shape (A258885, A273815, A275493, A321995). Do not
  widen without redoing that measurement; `tests/test_pari.py` fails if anyone does.
- **Matched in a comment or a string, never in live code.** The signal is the author's prose, and a GP
  identifier named `heuristic` would be a false positive a future `sync` could introduce. Of the 20
  matches at any width, none sits in code and none inside a string literal, so the restriction is free
  today and is what keeps the reason from ever being a lie.
- **Checked on the raw part text**, not on the script that runs — the opposite choice from the
  helper check above, for the opposite reason. There the question is what gp will execute; here it is
  what the author said about the arithmetic, and a disclaimer written as a trailing comment on the
  entry's own loop would be *dropped* with that statement for the function forms (A393125 is such a
  part). Per signed part, so a conjectural part does not condemn a proved part beside it.
- **The reason names the matched word and never the surrounding line.** A comment could contain a term
  value ("conjectured that a(20) = …") and the reason reaches `say()` and `db.record_skip`'s detail.
  No path carries it to a model prompt; naming the word keeps that structurally impossible.
- **Effect (2026-09-26):** the pool goes 3,441 → 3,438, losing A162763, A349899 and A351088. Two further
  matches are **inert** — A107263 and A393125 already yield no candidate. The point is not the three:
  it is that **A162762 and A162764 stay out** now that their review rows are closed (`rejected`,
  2026-09-28, history item 49), instead of
  returning at 2.32x and 1.56x the mean pick weight to repeat the whole thing. (Since history item 58
  they are also out for a second reason: a sequence with a `rejected` review is not drawn at all, so
  they no longer reach this check during selection and are not counted under `no_supported_program`
  or `conjectural_program`.)
- **It distinguishes the siblings, which nothing could before.** Of A162761–A162764, exactly one
  (A162761) is proved; its `%F` records "edited and proved by _M. F. Hasler_" and its `%o` carries no
  disclaimer, so it keeps its candidate while the other three lose theirs. Note that a check reading
  `%C`/`%F` instead would have **falsely flagged A162761**, whose comments discuss the conjecture it
  proves — one reason the program text is the right channel.
- **The `%C`/`%F` channel is deliberately unread.** Measured: 427 pool entries carry conjecture language
  in `%C`/`%F`/`%N` against 3 in program text, and of those inspected the conjecture is an asymptotic or
  auxiliary claim while the runnable program is direct brute force. Reading it would be nearly all
  false positives.
- **What it misses** is in [known limitations](known-limitations.md): scope caveats phrased without
  these words, and the whole class where a program is conjectural and says so nowhere.
- **The model is offered a flagged program only under an honest header.** `codegen._context` lists
  existing programs under "Existing programs (correct, possibly slow)", and for a disclaimed program
  that is a lie: the model could reproduce a conjectural closed form in Python, where no disclaimer
  survives for anything to detect. The PARI rejection alone cannot cover this, because
  `Runnable._why_not` keeps a sequence for the model whatever the PARI verdict. From 2026-09-26 to
  2026-09-30 a flagged PARI block was dropped from the prompt; since history item 51 it is quoted under
  `codegen.CONJECTURAL_PROGRAMS_NOTE` instead — *"Programs the author calls conjectural or heuristic (do
  NOT assume they are correct: a term such a program produces is a conjecture, not a result, and
  reproducing its formula proves nothing):"* — with the author's own matched word beside it. The model
  keeps the algorithm and loses only the false claim. **PARI blocks only**, and **per block** rather than
  per signed part — `code_mask` implements GP's comment syntax, so another language's disclaimer is not
  covered, and a block is quoted whole so a clean part beside a flagged one is labelled conjectural too
  (the safe direction).
  **The header changes the claim, not the conjecture**: `_context` still quotes `entry.comments[:8]` and
  `entry.formulas[:8]`, and A162763's and A162764's `%F` lines state the conjecture outright, so a model
  can still implement it from there. See [known limitations](known-limitations.md#strategies) for the
  measurement and why filtering `%C`/`%F` is not the obvious fix.

### Correctness caveats

- **Predicates are searched from `k = 1`.** A predicate that wrongly accepts smaller numbers would emit a
  wrong first term, which verification catches.
- **Print-loop rewrites change the program.** Lifting a bound can change what it computes. Verification
  catches changes that affect known terms, but not problems that only appear beyond them, for example a
  loop that does not enumerate values in increasing order. That is why rewrites are flagged for review.
- **The emitter's index counter starts at the first known index, whatever the loop starts at.** When the
  entry's loop begins above the offset — A290024's `for(n=1, 7, ...)` printing a(1) onward while `%O`
  is 0 — every emitted index is one too low, and a correct program fails `wrong_term` at the first term
  whose value differs from its neighbour (session 11, history item 50). The rewriter never reads the
  loop variable's start; see [known limitations](known-limitations.md#strategies) and the options in
  [status](status.md#open-offers-and-next-steps), item (vii).
- **Internal limits.** An `a(n)` or predicate program with an internal limit (a precomputed table, a
  `forprime` up to a constant) can verify and then produce wrong new terms. Unlike generated code, gp
  programs are not scanned for such limits.

## Local model code generation

`oeisbot/strategies/codegen.py` and `oeisbot/model.py`. Used only with `--model`, and only when no PARI
run found new terms: after PARI programs that failed, were skipped or were missing, and also after one
that reproduced every known term but found nothing new, where only a faster program can help.

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

`_context` builds the same context for every question (classify, the list question and generate):

- the name;
- only when an entry's PARI program already verified without new terms, in this attempt or in an
  earlier one that made it a dead end (`verified_elsewhere`, a `codegen.VerifiedRun`): a note naming that
  program and its attempt id, how long it took to reproduce all N known terms (when known), and its stop
  reason and detail (`slow_program_note`). After a stop by the budget or a projection it says a Python
  translation will be no faster; when the program ended by itself (`finished`) it says the program may
  only cover the known range and asks for one that keeps going. It holds timings and a stop reason, never
  a term value, and it comes second so the 10,000-character cut cannot drop it;
- the first index (offset);
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
2. **Ask the form**, only when the known terms strictly increase (`FORM`, temperature 0.2, up to 200
   tokens): is the sequence a list of numbers with some property, in increasing order, or is a(n) a
   function of n? JSON `{"form", "reason"}`; anything but `list` counts as `function`. Then **choose the
   contract** (`contract_for`): `members(work)` for a list whose known terms strictly increase, as a
   list's members must; `terms(work)` otherwise. See [the list contract](#the-list-contract-memberswork).
3. **Generate** (up to 3 generations, up to 2048 tokens each; temperature 0.2, then 0.5, then 0.8,
   because retries at a low temperature tend to repeat the same mistake). For `terms(work)` the prompt
   gives the contract `def terms(work)` and the rule to yield `(n, value)` from the first index with no
   gaps; for `members(work)` it gives `def members(work)`, says the runner numbers what is yielded from
   the offset, and asks for the members themselves (for "Numbers k such that ...", k), never a pair or an
   index, smallest first, each larger than the one before. Both then have these rules: never stop; report
   work in batches; compute every term and never copy known terms; no fixed search limits; reuse work
   between terms; prefer memory-lean methods; only the allowed imports; no file, network or subprocess
   access; no printing; reply with one Python code block. The `terms(work)` prompt is word for word what it
   was before the list contract existed.
4. **Extract** the longest fenced Python block (or the whole reply if it contains `def terms`, or
   `def members` under the list contract).
5. **Static checks** (defense in depth; the sandbox is the real boundary), in order:
   - the code parses (code nested too deeply for the parser, such as a sum of thousands of literals, is
     rejected like a syntax error rather than raising);
   - fewer than 6 distinct known term values with absolute value ≥ 10 appear as integer literals or
     inside string literals. This is checked against **all** known terms, including held-out ones;
   - a top-level `def terms(work)` (under the list contract `def members(work)`) with exactly one
     argument exists, and under the list contract the name `terms` is not bound at module level at all (a
     `def` or class; an assignment, deletion, import, loop or `except` target; a `match` capture; an
     assignment expression in a default or a class base; or a `global terms` anywhere. A local variable
     of that name inside a function is fine, and a comprehension variable of that name at module level
     is refused although it would be harmless). The driver defines `terms` after the program, replacing
     whatever it was: a reviewer would read code that never ran, and the program would break in a way it
     cannot see;
   - imports only from `math`, `itertools`, `functools`, `collections`, `heapq`, `bisect`, `fractions`,
     `operator`, `array`, `gmpy2`, `sympy`, `numbers`, `decimal`;
   - no use of `open`, `exec`, `eval`, `compile`, `__import__`, `input`, `breakpoint`, `globals`, `vars`;
   - no dunder attribute access other than `__init__` and `__name__`.

   A failed check becomes the retry message, without running anything; its guidance is a plain "fix that
   and send the program again", since no run happened to diagnose.
6. **Skip a repeat.** A program whose syntax tree (`ast.dump`: comments and layout aside) is that of a
   program that already ran in this model stage and failed in a way that would recur in the stage
   (`codegen.REPEATS_IN_STAGE`) is not run. Those failures are the ones that repeat every time
   (`wrong_term`, `bad_index`, `protocol`, `crash` or `incomplete`: `db.DETERMINISTIC_FAILURES`) and
   `verify_timeout`: every generation of a stage runs under the same verify budget, so the same program
   would run out of it again (the offer-C measurement reran such programs 7 times, 4 programs in all,
   and each time it ran out again, reproducing the same number of known terms). This is the in-stage
   form of `db.is_dead_end`'s rule for a `verify_timeout`, without the CPU condition that rule gained in
   history item 58 (a timeout on a busy machine still makes a repeat here, costing one generation);
   `DETERMINISTIC_FAILURES` itself leaves it
   out, so a later attempt with a `--verify-s` longer than the time a PARI program already ran still
   runs it. A repeat is listed among the rejections, uses up its generation (a repeat always follows a
   run, so the stage still has an attempt row), and the retry says
   it is the same program as generation g, repeats that failure's description and says why it was not
   run (`REPEAT_GUIDANCE`) before the failure's own guidance. After any other failure (`timeout`,
   `memory_cap`, `cpu_cap`, `launch_error`, `disk_cap`, `output_cap`) the same program may run again.
   Code too deep for `ast.dump` is compared as text instead.
7. **Flag fixed bounds** (`fixed_bounds`), without rejecting: assignments of an integer ≥ 100 to a name
   matching `limit`, `max`, `bound`, `upper`, `size`, `cap`, `sieve` or exactly `n`; and integers ≥ 1000
   passed to `range`, `primerange`, `sieve`, `primepi` or `divisors_up_to`. An integer here is a literal or
   a constant expression of literals with `**`, `*`, `+`, `-` or `<<`, such as `10**7` or `2 * 10**6`
   (powers only up to an exponent of 64 and a base of 10^6, shifts up to 256, so nothing huge is built).
   Each becomes a "fixed bound" note, shown in the artifact and dashboard, because new terms beyond such a
   limit can be wrong even though verification passed.
8. **Run** through the same runner as PARI programs: strategy `python:model` (the artifact's and the
   dashboard's AI-generated warnings depend on that exact string), origin
   `model <name>, generation <g> (AI-generated)` (with `; members(work), numbered by the runner` under
   the list contract), recorded in the database, the executed program saved to `data/runs/`, and on
   success re-checked and turned into an artifact. After a verified PARI run, each program also
   carries a note starting "the entry's own program (<origin>, attempt #<id>) reproduced all N known terms
   and found no new term", which the artifact README and the dashboard's Review inbox show as **Compare
   with the entry's program**, so the reviewer checks the model's new terms against the search the entry's
   program already made (its run log is named in that attempt's `extra`).
9. **Stop** at the first verified program, even if it found no new terms. **Stop too when the caller
   asks** (since history item 58): `generate_and_verify(should_stop=...)` asks after the classify step,
   before each generation's model call and again before its run (a local model can take minutes over a
   reply), and a run that itself ended `interrupted` is not retried and nothing about it is sent to the
   model. In each case the stage ends with `CodegenOutcome.stopped` set, and `attempt_sequence` then
   records no model-stage skip row for it. No caller passes `should_stop` together with a model today:
   `oeisbot daemon` runs PARI sessions only.
10. **Retry** after a failed run with a message holding the stop reason and detail, plus hints:
    - `bad_index`: the first index must be the offset, then consecutive. If the index the program emitted
      equals a held-out term that the prompt does not also show, either sign (a program that put a value
      where the index belongs), it is left out: "program emitted a wrong index (not shown)";
    - `crash` or `incomplete`: the last 12 stderr lines;
    - `verify_timeout` or `timeout`: how many known terms were reproduced;
    - `wrong_term`: the range of terms that were correct. **If the wrong term is a held-out one, its correct
      value is replaced by "the correct value is not shown"**, so the next program cannot special-case it.
      Under the list contract the program's own value is left out too ("neither your value nor the correct
      one is shown"): it would say that number is not in the list, and the next program could exclude it.
      For the same reason, at a shown index the program's value is left out when it lies past the last
      term shown, where it may be a held-out member ("a(9) is wrong: it is 23 (your value is not
      shown)"). Under either contract the program's value is also left out whenever it equals a
      held-out term that the prompt does not show anyway, with either sign, compared as the harness
      prints values (so a long value is matched by its abbreviation). An off-by-one `terms(work)`
      program would otherwise show a(9) = <a(10)>, and in attempt #105 a list program's a(1) = -10031
      carried the digits of the held-out a(4) = 10031. The wording is the same as for the other cases,
      so it does not say that the value is a term.

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
    not the whole conversation, to stay inside the context window. It ends by asking to keep the contract:
    `def terms(work)` yielding `(n, a(n))` from the first index, or `def members(work)` yielding the members
    themselves in increasing order.

### The list contract (`members(work)`)

Before it existed, every one of the model's 17 `bad_index` failures (of 45 generations) was on a sequence
that is a list of numbers with a property ("Numbers k such that 4^k + 15 is prime"), and the programs show
why: they counted candidates and yielded `(n, n)`, or yielded the prime `c·b^k ± d` where k belonged. Run
again with the runner numbering the values they yielded, 6 of the 17 reproduced every known term, and 4
more were right as far as they got before the 60 s verify budget ran out. So for such a sequence the
model writes only the list, and a driver appended to its code (`MEMBERS_DRIVER`, not model-written) does
the numbering:

- it defines `terms(work)`, the function `py_runner` calls, and yields `(a(first), the first member)`,
  `(a(first + 1), the second)`, and so on;
- a pair `(index, value)`, or a value not larger than the one before, raises the driver's
  `OEISBotContractError` (`verify.CONTRACT_ERROR`). The harness ends the run as `protocol`, so the retry
  gets the output-protocol guidance. If the run had already verified, **its new terms are voided**
  (their records become kind `void`, the attempt records 0 new terms and the outcome `verified`): the
  order is wrong somewhere, so all are dropped, conservatively (a spurious low value after correct new
  terms voids those too). A program that yields 2, 3, 5, 7, 11 (the known terms), then 17, then 13
  would otherwise have a(6) = 17 recorded as a new term. The check only works while the run is going:
  the harness reads nothing after a stop, so a late value that would come after the extension budget, a
  kill or `max_new_terms` is never seen, and the last new terms of every productive run are unchecked
  for order. Nor can the driver see a member skipped for good: a(6) = 17 with 13 never yielded is still
  a wrong new term. Both are left to the reviewer (the re-check only compares with what oeis.org has
  published). The messages name positions only, never a value, since a value
  the program got right at a held-out index must not reach a retry prompt;
- `Program.source` stays the model's code (the artifact's `program.py`) and the driver is in
  `Program.script` (`executed.py`); the program's hash covers both. A note starting "list contract" is shown
  as **Numbered by the runner** in the README and the dashboard's Review inbox, pointing the reviewer at
  `executed.py`.

The model, not a name pattern, decides what is a list, in a question of its own. Asked it with the usual
context, it was right on all 44 sequences tried (the 14 it had been given by then, 15 named "Numbers k
such that ..." and 15 named "Number of ..."), while a name pattern missed 6 of the 10 lists among the 14
("Integers whose ...", "Primes of ...", "Consecutive exclusionary cubes: ...", a name that is a program
fragment). Folded into the classify question as a `form` field, the same model got 42 of the 44: it called
A129250 ("Primes of Erdős-Selfridge class 16-") and A057246 functions, 4 times out of 4 each, where the
question on its own called them lists 4 times out of 4.
Strictly increasing known terms alone would not do: A383336 ("Smallest number with ...") and 8 of the 15
counting sequences are increasing. The member contract still lets the model yield the wrong quantity (the
prime instead of k); a pure predicate `isok(k)` could not, but it would have to count up to the last known
term one integer at a time. The cheapest predicate runs in the sandbox at about 4.5 million calls a
second when the driver reports work on every call and 8.5 million when it reports in batches, so a
minute counts to 2.7 to 5.1 × 10^8, short of the last known term of 459 of the 2,575 list-style
candidates without a PARI program (those of 10 digits or more), whereas a generator can build its
candidates directly. The user chose `members(work)` on 2026-09-19.

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

A model program under the list contract defines `members(work)` instead; the appended driver turns it
into this `terms(work)`:

```python
def members(work):
    k = 1
    while True:
        k += 1
        work(1)
        if is_member(k):         # the property; the runner numbers what is yielded
            yield k
```
