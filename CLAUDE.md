# CLAUDE.md

Guidance for coding agents working in this repository.

**Start here:** `docs/status.md` has the current state, decisions made with the user, open offers and
next steps. Read it before doing anything, and update it before ending a working session. The user
commits the work themselves; do not commit or push unless asked.

## What this is

OEISBot finds OEIS sequences with keyword `more`, runs programs (the entry's own PARI/GP code, or Python
from a local model) in a sandbox, verifies every known term, and writes review folders for a human. It
never submits anything to OEIS, and must never be changed to.

Windows-only in practice: the sandbox is a Job Object + AppContainer (`oeisbot/sandbox/windows.py`).

## Commands

```
.venv\Scripts\python -m pytest                 # 274 tests, ~50 s; sandbox tests skip if `oeisbot setup` has not run
.venv\Scripts\python -m pytest tests/test_sandbox.py
.venv\Scripts\oeisbot setup                    # sandbox runtimes + AppContainer grants + database (idempotent)
.venv\Scripts\oeisbot sync --no-pull           # rebuild the candidate table from the local oeisdata clone
.venv\Scripts\oeisbot attempt A123456 --verify-s 60 --extend-s 60   # one sequence, short budgets
.venv\Scripts\oeisbot run -n 5 [--model]       # a session: pick and attempt 5 candidates
.venv\Scripts\oeisbot recheck                  # finish any re-check left pending by an earlier failure
cd dashboard && npm run build                  # frontend; output in oeisbot/dashboard/static (not committed)
```

Installing Python packages behind this machine's TLS inspection needs `UV_SYSTEM_CERTS=1`; npm needs
`NODE_USE_SYSTEM_CA=1`; git needs `git -c http.sslBackend=schannel push` (the system config sets
`openssl`, which fails with "unable to get local issuer certificate"). More in
[operations](docs/operations.md#troubleshooting).

## Where things are

- Flow: `oeisbot/attempt.py` (orchestration) → `strategies/pari.py`, `strategies/codegen.py` →
  `verify.py` (gate) → `sandbox/` → `db.py`, `artifact.py`.
- Ingest: `ingest/oeisdata.py` (mirror + sync), `ingest/bfile.py` (b-files + known terms),
  `ingest/seqfile.py` (entry parser). Selection: `select.py`. Estimation: `estimate.py`.
- Python program contract and term protocol: `oeisbot/runners/py_runner.py` docstring.
- Local state (never commit): `data/`, `tools/`, `artifacts/`, `oeisbot/dashboard/static/`,
  `dashboard/node_modules/`.

## Rules that must hold

The full list with rationale is in `docs/development.md#invariants`.

- All untrusted code runs through `sandbox.run(..., isolate=True)`. Never add a code path that runs
  entry or model programs outside it.
- oeis.org traffic only through `ingest.bfile.http_get` (rate-limited GETs). Never POST, never submit.
- New terms count only after every known term is reproduced as consecutive (index, value) pairs starting
  at the offset.
- Known terms beyond `codegen.shown_indices` are held out from the model (always at least 2; sequences
  with fewer than 3 known terms never reach the model), and the failure described in a retry prompt never
  carries a held-out value: not the correct one, and not a program value that equals one the prompt does
  not already show, either sign (`describe_failure`). Text the program wrote itself is passed on as it
  is: a crash's error message, the stderr tail, and a line it printed that became a `protocol` stop (see
  `docs/known-limitations.md`).
- Every run is recorded; wins are re-checked against oeis.org before an artifact is written. A run with
  new terms is recorded as `recheck_pending` and saved to `data/pending/` *before* its re-check starts,
  so an interrupted or failed re-check leaves it pending (never published unchecked, never lost).
  `retry_pending_rechecks` must not raise for a single attempt.
- The dashboard is read-only (`db.connect(readonly=True)`).
- Keep `tests/test_sandbox.py` passing. Add a test that attacks any new sandbox guarantee.

## Pitfalls

- Editing files that contain backslashes (GP `\\` comments, Windows paths, regex) through shell heredocs
  or `sed` corrupts escapes. Use a file-editing tool and `python -m py_compile` afterwards.
- AppContainer grants are path-based: after moving the project, run `oeisbot setup`.
- Packages in `tools/python` must be copies, not hard links (`--link-mode copy`), or the sandbox cannot
  read them.
- `gp.exe` commits its whole `parisizemax` at startup; job peak memory for gp is meaningless (the driver
  reports stack size instead).
- There are no database migrations; schema changes need `ALTER TABLE` on existing databases.
- Real timings on this machine are noisy: a term of a few milliseconds can take 0.2-0.4 s more wall time
  than CPU time. Do not assert on sub-second timings in a test; drive the harness in memory with
  controlled times instead, as the harness tests in `tests/test_estimate.py` do.

## Docs

`docs/` describes current behavior precisely. When you change behavior, update the matching page
(`pipeline.md`, `sandbox.md`, `verification-and-estimation.md`, `strategies.md`, `data-and-schema.md`,
`dashboard.md`, `operations.md`) and `docs/known-limitations.md` if you fix or introduce a limitation.
