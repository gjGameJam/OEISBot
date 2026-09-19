# OEISBot

A local triage tool that finds [OEIS](https://oeis.org) sequences marked `more` (needing more terms),
tries to compute further terms, and turns verified results into review folders for a person to read.
**It never submits anything.** OEIS forbids bulk or automated submissions and programs the submitter
does not understand, so the output is a review queue: you read the program, understand it, check the
terms, and submit by hand.

Expect a trickle, not a flood. Most `more` sequences are stuck because their next term is expensive.

## How it works

1. **Sync** a shallow clone of [oeis/oeisdata](https://github.com/oeis/oeisdata) and build a table of
   the 26,814 candidates (snapshot of 2026-09-17).
2. **Pick** candidates at random, weighted toward easy ones (probability ∝ 1/difficulty^α).
3. **Gather known terms** from the b-file (fetched from oeis.org, cached, 1 request/s) merged with the
   entry's DATA line, and skip the sequence if they disagree.
4. **Get a program**: the entry's own PARI/GP program, run for longer than its author ran it, or, with
   `--model`, Python written by a local code model (Ollama, `qwen2.5-coder:14b`).
5. **Run it in a sandbox**: a Windows Job Object and AppContainer with a hard memory cap, one process, no
   network and no access to your files.
6. **Verify**: every known term must come back as the right (index, value) pair before any new term
   counts. Before each new term, estimate whether it fits the time and memory budget.
7. **Record** every run in SQLite. When a program finds new terms, re-check oeis.org and write a review
   folder under `artifacts/` (if oeis.org cannot be reached, the win waits for `oeisbot recheck`).
8. **Review** in the terminal or the read-only dashboard, and submit by hand.

## Quickstart (Windows)

```
uv venv .venv --python 3.11
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
.venv\Scripts\oeisbot setup        # sandbox runtimes in tools/, AppContainer grants, database
.venv\Scripts\oeisbot sync         # clone oeisdata (about 2.3 GB) and build the candidate table
.venv\Scripts\python -m pytest     # 257 tests; proves the sandbox works on this machine
.venv\Scripts\oeisbot run -n 5     # pick and attempt 5 sequences that have PARI programs
.venv\Scripts\oeisbot review list  # anything found
```

With the local model (Ollama installed, `ollama pull qwen2.5-coder:14b`):

```
.venv\Scripts\oeisbot model-check
.venv\Scripts\oeisbot run -n 5 --model
```

Dashboard: `cd dashboard && npm install && npm run build`, then `.venv\Scripts\oeisbot dashboard`
(http://127.0.0.1:8765).

## Status

- All eight build steps from the [design spec](docs/design-spec.md) are implemented, and 257 tests pass.
- The sandbox runs on Windows only. A Linux `setrlimit` backend exists but has never run, and the rest
  of the project assumes Windows.
- Real runs so far (47 sequences, 88 program runs, about 3 machine-hours) found no new terms; see
  [known limitations](docs/known-limitations.md#observations-from-real-runs) and
  [status](docs/status.md) for the current state and next steps.

## Documentation

| Page | For |
|---|---|
| [Status and handoff](docs/status.md) | current state on the development machine, decisions, open items, next steps |
| [Operations guide](docs/operations.md) | install, commands, budgets, reading results, reviewing and submitting, troubleshooting |
| [Pipeline](docs/pipeline.md) | the end-to-end flow, stage by stage, with the functions that implement each |
| [Sandbox and safety model](docs/sandbox.md) | what the sandbox guarantees, how, the tests proving it, and its gaps |
| [Verification and estimation](docs/verification-and-estimation.md) | the term protocol, the checks on each term, stop reasons, feasibility math |
| [Strategies](docs/strategies.md) | difficulty and selection, PARI program handling, local-model code generation |
| [Data and schema](docs/data-and-schema.md) | directories, run logs, artifact folders, database tables |
| [Dashboard](docs/dashboard.md) | views, API, safety properties, frontend layout |
| [Development guide](docs/development.md) | module map, invariants, tests, how to extend |
| [Known limitations](docs/known-limitations.md) | gaps and surprises, with suggested fixes; observations from real runs |
| [Design spec](docs/design-spec.md) | the original spec, and a point-by-point map of how the implementation follows or deviates |
| [CLAUDE.md](CLAUDE.md) | orientation for coding agents |
