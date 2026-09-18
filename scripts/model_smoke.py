"""Check the local model end to end on easy, well-known sequences.

Runs classification, generation, static checks and sandboxed verification for each A-number, using DATA
terms only (no network) and short budgets. Nothing is written to the database or to artifacts/.

    .venv\\Scripts\\python scripts\\model_smoke.py                      # A000005 A001358 A000108
    .venv\\Scripts\\python scripts\\model_smoke.py A000045 A000079

Needs `oeisbot setup`, `oeisbot sync` (for the local .seq files) and a running model server
(`oeisbot model-check`).
"""
import sys
import time

from oeisbot import config
from oeisbot.config import Budgets
from oeisbot.ingest import bfile, oeisdata
from oeisbot.model import LocalModel
from oeisbot.strategies import codegen
from oeisbot.verify import run_attempt

BUDGET = Budgets(verify_wall_s=60, extend_wall_s=5, max_new_terms=3)


def main(a_numbers: list[str]) -> None:
    model = LocalModel()
    print("model:", model.name, model.available() or "available")
    for a in a_numbers:
        entry = oeisdata.load_entry(a)
        if entry is None:
            print(f"\n=== {a}: not in the local oeisdata mirror")
            continue
        known = bfile.known_terms(entry, None)
        print(f"\n=== {a}: {entry.name[:80]} ({known.describe()})")
        if known.count < config.CODEGEN_MIN_KNOWN_TERMS:
            print(f"   skipped: the model needs at least {config.CODEGEN_MIN_KNOWN_TERMS} known terms")
            continue
        t0 = time.perf_counter()

        def runner(prog, entry=entry, known=known):
            r = run_attempt(prog, known, BUDGET, name=entry.name)
            print(f"   run: {r.outcome} {r.stop.value}: {r.detail[:100]}  ({r.run.wall_s:.1f}s)")
            return r

        out = codegen.generate_and_verify(entry, known, model, runner, log=lambda m: print("  ", m))
        ok = out.success
        print(f"   => {'VERIFIED' if ok else 'not verified'} after {len(out.attempts)} run(s), "
              f"{len(out.rejected)} rejected, {time.perf_counter() - t0:.0f}s total")
        if ok:
            print("   code:\n" + "\n".join("      " + line for line in ok.program.source.splitlines()[:25]))


if __name__ == "__main__":
    main(sys.argv[1:] or ["A000005", "A001358", "A000108"])
