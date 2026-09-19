"""Review artifacts: one folder per success, meant to be read before deciding anything.

    artifacts/A123456/attempt-17/
        README.md          what happened, and the questions to answer before submitting
        b123456.txt        OEIS b-file format: known terms + new terms
        program.gp|.py     the program as it appears in the entry (or as generated)
        executed.gp|.py    exactly what ran, driver included
        verification.md    which known terms were reproduced, and from where
        timing.csv         per-term wall/CPU/work/memory for every term, known and new
        predictions.csv    projected vs actual cost of each new term
        run.json           sandbox result and budgets

A new folder holds an `.incomplete` marker until the caller has recorded the win (`mark_complete`). A
folder that still has one was left by an interrupted attempt to record the same win and is replaced; any
other existing folder is never overwritten.
"""
from __future__ import annotations

import csv
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from . import config
from .config import Budgets
from .strategies import codegen
from .terms import format_bfile
from .verify import AttemptResult

EXT = {"gp": "gp", "python": "py"}
INCOMPLETE = ".incomplete"


def write(result: AttemptResult, attempt_id: int, entry_name: str, budgets: Budgets,
          recheck_note: str, root: Path | None = None) -> Path:
    a = result.known.a_number
    folder = (root or config.ARTIFACTS) / a / f"attempt-{attempt_id}"
    if (folder / INCOMPLETE).exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / INCOMPLETE).touch()
    new = result.new_terms
    ext = EXT[result.program.language]

    values = dict(result.known.values)
    values.update({t.n: t.value for t in new})
    (folder / f"b{a[1:]}.txt").write_text(format_bfile(values), encoding="utf-8")
    (folder / f"program.{ext}").write_text(result.program.source + "\n", encoding="utf-8")
    (folder / f"executed.{ext}").write_text(result.program.executed, encoding="utf-8")

    with open(folder / "timing.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n", "kind", "digits", "wall_s", "cpu_s", "work", "peak_mem_bytes", "arrived_at_s"])
        for r in result.records:
            w.writerow([r.n, r.kind, len(str(abs(r.value))), f"{r.dt:.6f}", f"{r.dcpu:.6f}", r.dwork, r.mem, f"{r.t:.3f}"])
    with open(folder / "predictions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n", "unit", "model", "trustworthy", "feasible", "predicted_s", "predicted_s_low",
                    "predicted_s_high", "predicted_mem", "actual_s", "actual_mem", "censored_s", "reasons"])
        for p in result.predictions:
            w.writerow([p.n, p.unit, p.model, p.trustworthy, p.feasible, p.seconds, p.seconds_low, p.seconds_high,
                        p.mem_high, p.actual_s, p.actual_mem, p.censored_s, " | ".join(p.reasons)])

    k = result.known
    (folder / "verification.md").write_text(f"""# Verification: {a}

- Known terms: {k.describe()}
- Offset (%O): {k.offset}; program's first emitted index: {result.records[0].n if result.records else '-'}
- Reproduced: {result.reproduced} of {k.count} known terms, every one compared as an (index, value) pair
- Notes on the known terms: {'; '.join(k.notes) or 'none'}
- Program origin: {result.program.origin}
- Program sha256 (executed file, first 16 hex): {result.program.sha}
- All known terms reproduced after {result.verified_at_s:.2f} s
- Re-check against oeis.org just before writing this: {recheck_note}
""", encoding="utf-8")

    run = asdict(result.run)
    run["status"] = result.run.status.value
    (folder / "run.json").write_text(json.dumps({
        "a_number": a, "attempt_id": attempt_id, "strategy": result.program.strategy, "stop": result.stop.value,
        "detail": result.detail, "cost_unit": result.cost_unit, "run": run, "budgets": asdict(budgets),
    }, indent=2), encoding="utf-8")

    first, last = new[0], new[-1]
    notes = []
    if result.weak_verification:
        notes.append(f"**Weak verification:** only {k.count} known terms were available to check against.")
    if result.program.strategy == "python:model":
        notes.append(f"**AI-generated program** ({result.program.origin}). OEIS does not accept AI-generated "
                     "programs the submitter does not understand; treat it as a lead, not a result.")
        notes += [f"**Numbered by the runner ({n}):** read `executed.{ext}` too, where the driver sits."
                  for n in result.program.notes if n.startswith(codegen.MEMBERS_NOTE)]
        notes += [f"**Hard-coded {n}**" for n in result.program.notes if n.startswith("fixed bound")]
        notes += [f"**Compare with the entry's program:** {n}" for n in result.program.notes
                  if n.startswith(codegen.ENTRY_PROGRAM_NOTE)]
    else:
        notes += [f"**Program was rewritten:** {n}" for n in result.program.notes]
    warnings = "\n" + "\n\n".join(notes) + "\n" if notes else ""
    total_new_s = sum(t.dt for t in new)
    (folder / "README.md").write_text(f"""# {a}: {len(new)} new term(s), a({first.n})..a({last.n})

**{entry_name}**

Nothing has been submitted. OEIS policy: no bulk or automated submissions, and no programs
you do not understand. This folder exists so you can decide.

| | |
|---|---|
| Strategy | `{result.program.strategy}` from {result.program.origin} |
| Known terms reproduced | {result.reproduced} of {k.count} ({k.describe()}) |
| New terms | a({first.n})..a({last.n}), largest {max(len(str(abs(t.value))) for t in new)} digits |
| Time on new terms | {total_new_s:.1f} s wall |
| Peak memory | {result.peak_mem_bytes / 2**20:.0f} MiB |
| Why it stopped | {result.stop.value}: {result.detail} |
{warnings}
## Before submitting, check

1. Read `program.{ext}` and be able to explain why it computes this sequence.
2. Confirm the index convention: the entry's offset is {k.offset} and the first new index is {first.n}.
3. Look at `timing.csv`: do the new terms' costs follow the trend of the known ones?
4. Re-open https://oeis.org/{a} and make sure nobody has extended it since this run.
5. Consider an independent check of the new terms (a different program or method).

## New terms

```
{format_bfile({t.n: t.value for t in new})}```
""", encoding="utf-8")
    return folder


def mark_complete(folder: Path) -> None:
    (folder / INCOMPLETE).unlink(missing_ok=True)
