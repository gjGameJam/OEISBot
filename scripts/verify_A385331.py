"""Independent re-derivation of A385331, for review #1 (the project's first win).

Written from the sequence's **name** rather than from the entry's PARI program, so it shares no code
with `program.gp` and derives what to compute from the definition instead of copying it.

It does **not** discharge step 6 of the review checklist in `docs/operations.md`, which asks for a
different program *or method*. The method here is the same one the entry uses -- trial division by
rising primes -- differing only in how the exponent is reduced (Fermat by hand, rather than PARI's own
modular powering) and in how the primes are enumerated. A genuinely independent check would factor
`N(n)` directly, or use a different factoring library.

    a(1) = 1; for n > 1, a(n) = the smallest prime factor of the n-th numerator of the partial sum of
    Liouville's constant (A145571).

    partial sum = sum_{k=1..n} 10^(-k!) = N(n) / 10^(n!),  so  N(n) = sum_{k=1..n} 10^(n!-k!)

Two facts fall straight out of that and are worth knowing before reading the terms:

  * The k = n term is 10^0 = 1 and every other term is a positive power of 10, so N(n) == 1 (mod 10).
    N is odd and prime to 5, which is why the entry's `forprime(p=3, oo, ...)` is correct to start at 3.
  * N(n) is a sum of n powers of 10, so its digit sum is n. Hence 3 | N(n) exactly when 3 | n, which
    *proves* the entry's stated a(3k) = 3 rather than merely observing it.

Divisibility is tested with Fermat's little theorem, so no huge integer is ever built (10^(43!) has
6e52 digits):

    N(n) mod q = sum_{k=1..n} 10^((n! - k!) mod (q-1))  mod q

valid for any prime q coprime to 10. **q = 5 must be skipped**: 10^e == 0 (mod 5) for every e >= 1,
while the reduced exponent returns 1 whenever 4 | e. An early version of this script did not skip it and
reported the impossible a(43) = 5, so the assertion in `divides` is deliberate.

Usage (from the project root, with the venv's Python):

    .venv\\Scripts\\python scripts\\verify_A385331.py [--bound N] [--bfile PATH]

The default bound of 2e8 takes about 19 minutes and resolves every term of the artifact, including
a(25) = 174,443,251. `--bound 1000000` takes about 13 s and settles 37 of the 41, leaving a(25), a(32),
a(37) and a(38) open.

Whatever is left unresolved at the end has a smallest prime factor above the bound, which is the useful
output for a(43): the term the run was stopped before computing.

The default b-file lives under `artifacts/`, which is gitignored, so on any other machine pass --bfile.
"""
import argparse
import time
from itertools import compress, count
from pathlib import Path

DEFAULT_BFILE = Path("artifacts/A385331/attempt-139/b385331.txt")


def odd_primes(limit):
    """The odd primes 3..limit, from one flat sieve (index i holds the value 2i+1)."""
    n = (limit - 1) // 2
    sieve = bytearray([1]) * (n + 1)
    sieve[0] = 0                                    # the value 1
    i = 1
    while (2 * i + 1) ** 2 <= limit:
        if sieve[i]:
            p = 2 * i + 1
            start = (p * p - 1) // 2
            sieve[start::p] = bytearray(len(range(start, n + 1, p)))
        i += 1
    return compress(count(3, 2), memoryview(sieve)[1:])


def divides(q, n):
    """Does the prime q divide N(n)? Only valid for q coprime to 10 -- see the module docstring."""
    assert q % 2 and q % 5, f"the Fermat reduction is invalid for q={q}"
    m = q - 1
    facts = []
    f = 1
    for k in range(1, n + 1):
        f = f * k % m
        facts.append(f)
    top = facts[-1]
    total = 0
    for e in facts:
        total += pow(10, (top - e) % m, q)
    return total % q == 0


def read_bfile(path):
    claimed = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            index, value = line.split()
            claimed[int(index)] = int(value)
    return claimed


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bound", type=int, default=200_000_000, help="sweep primes up to this (default 2e8)")
    ap.add_argument("--bfile", default=DEFAULT_BFILE, help=f"b-file to compare with (default {DEFAULT_BFILE})")
    args = ap.parse_args()

    claimed = read_bfile(args.bfile)
    ns = [n for n in sorted(claimed) if n >= 2]     # a(1) = 1 by definition, not by factoring
    # also carry the term the run was stopped before computing: whatever is still unresolved at the end
    # bounds it from below, which is what decides whether the `infeasible` stop was right
    next_n = max(ns) + 1
    unresolved, found = set(ns) | {next_n}, {}
    started, seen = time.time(), 0

    for q in odd_primes(args.bound):
        if q == 5:                                  # never divides N, and the reduction does not apply
            continue
        if not unresolved:
            break
        seen += 1
        for n in [n for n in unresolved if divides(q, n)]:
            found[n] = q
            unresolved.discard(n)

    elapsed = time.time() - started
    print(f"swept {seen:,} odd primes up to {args.bound:,} in {elapsed:.1f} s\n")
    print(f"{'n':>4} {'computed':>12} {'in b-file':>12}   verdict")
    agree = disagree = 0
    for n in ns:
        mine, theirs = found.get(n), claimed[n]
        if mine is None:
            print(f"{n:>4} {'> bound':>12} {theirs:>12}   not settled at this bound")
            continue
        ok = mine == theirs
        agree += ok
        disagree += not ok
        print(f"{n:>4} {mine:>12} {theirs:>12}   {'ok' if ok else '*** MISMATCH ***'}")

    print(f"\n{agree} agree, {disagree} disagree, "
          f"{len(unresolved - {next_n})} of the b-file's terms not settled")
    still = sorted(unresolved - {next_n})
    if still:
        print(f"a(n) > {args.bound:,} for n in {still}")

    # the term the run never reached
    if next_n in unresolved:
        print(f"\na({next_n}) > {args.bound:,}  -- the term the `infeasible` stop was made about")
    else:
        print(f"\na({next_n}) = {found[next_n]:,}  -- the term the `infeasible` stop was made about")

    # the digit-sum proof, checked rather than asserted
    bad = [n for n in ns if n % 3 == 0 and claimed[n] != 3]
    print(f"a(3k) = 3 holds for every multiple of 3 in the b-file: {not bad}"
          + (f" (exceptions: {bad})" if bad else ""))
    assert all(v % 2 and v % 5 for v in claimed.values() if v > 1), "N is prime to 10; no term may be 2 or 5"
    return 1 if disagree else 0


if __name__ == "__main__":
    raise SystemExit(main())
