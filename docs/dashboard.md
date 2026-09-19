# Dashboard

A read-only web view over the database: FastAPI backend (`oeisbot/dashboard/app.py`) and React frontend
(`dashboard/`).

## Running it

```
cd dashboard
npm install          # once; on TLS-inspecting networks: set NODE_USE_SYSTEM_CA=1 first
npm run build        # type-checks, then writes oeisbot/dashboard/static/
cd ..
.venv\Scripts\oeisbot dashboard            # http://127.0.0.1:8765
.venv\Scripts\oeisbot dashboard --host 127.0.0.1 --port 8765
```

Without a build, `oeisbot dashboard` says so and serves only the API (interactive API docs at
`/api/docs`). The dashboard needs the `dashboard` extra (`fastapi`, `uvicorn`), which the `dev` extra
includes.

For frontend development run `oeisbot dashboard` and, separately, `npm run dev` in `dashboard/`. Vite
proxies `/api` to `127.0.0.1:8765`.

It can run while a session is writing: SQLite WAL lets it read mid-write.

## Views

Tabs are addressable by URL hash (`#estimator`, `#queue`, `#attempts`, `#reviews`, `#history`). The
header shows candidates, runs, wins, reviews awaiting action, machine hours, and the oeisdata commit and
sync time. Data refreshes every 15 s (the queue every 60 s). The previous data stays on screen while it
reloads; the estimator card, the queue table and the attempts table are also dimmed during a reload.

### Estimator accuracy

Whether the feasibility step works.

- **Filters**: cost unit (all, work counts, CPU time), trusted projections only (`predictions.trustworthy`:
  those the over-prediction kill acts on, unless the term is value-dependent; session 5's two kills came before
  that rule and are stored untrusted), chart/table toggle.
- **Tiles** (computed by the server over all points; the unit and trusted filters do not change them):
  - terms predicted and finished (and how many were stopped before finishing);
  - share within 2× of prediction;
  - median actual/predicted (above 1 means underestimates);
  - share inside the reported range, widened ×2 (low/2 ≤ actual ≤ high×2);
  - number stopped at more than 2× their high estimate.
- **Chart**: log-log scatter of predicted vs actual seconds per new term. Blue = work-count projections,
  orange = CPU-time projections. The diagonal is a perfect prediction; the shaded band is within 2×.
  Hollow points were stopped before finishing, so the true cost is at least the plotted value. Hovering
  or focusing a point shows sequence, index, predicted, range, ratio and model.
- **Table**: the same rows, sortable (defaults to worst ratio first).

A point appears once a verified run has a time projection whose term finished (filled) or was cut short
(hollow, a genuine lower bound). A projection that stopped the run as `infeasible` does not appear: its
term never started, so it has neither an actual nor a censored time (see
[verification](verification-and-estimation.md#where-predictions-are-stored)). On the real database as
of 2026-09-19 the view has five points, all hollow: A277532 and A390295 twice each, and A247883's model
program (attempt 92), which ran its whole 120 s extension without a new term. In session 5 the first
new terms of A277532 and A390295 were killed for over-prediction after 24 s and 10 s (before only trustworthy projections
could kill); in the offer-B check the same terms ran the whole 300 s extension without finishing.

### Queue

The candidate pool as selection sees it, before the last check a session applies (see the last point):

- **Controls**: α, "only sequences with a PARI program".
- **Table** (up to 2,000 rows, sortable): A-number (links to oeis.org), name, difficulty, pick chance,
  programs, known terms, b-file status, extension credits, search flag.
- Sequences with an open review or a `recheck_pending` win are excluded, exactly as in selection.
- Unlike a session, `oeisbot queue` and `oeisbot pick`, the tab does **not** leave out sequences an attempt
  could only skip (no supported PARI program, all programs dead ends or out of reach): that check reads
  every PARI-bearing entry from disk (about 3 s) and the tab refreshes every minute. Its totals and pick
  chances are therefore those of the wider pool. `oeisbot queue` shows the pool a session really uses.

### Attempts

What to fix next.

- **Filters**: outcome, strategy.
- **"Why runs stopped"**: bar chart of stop reasons for program runs. Clicking a bar filters the table;
  a chip above clears the filter.
- **"Why sequences were skipped"**: bar chart of skip reasons.
- **Table** (latest 1,000 matching rows): id, start time, sequence, strategy, outcome, stop reason,
  reproduced/known, new terms, runtime, peak memory, detail.

### Review inbox

Wins waiting for a person.

- **Tiles**: counts by status.
- **Each review** shows status, A-number, new index range, new-term count, strategy, runtime, creation
  time, review id and name.
- **Warnings**: weak verification, AI-generated program, "numbered by the runner" (a `members(work)`
  program: read `executed.py` too), hard-coded bounds and "compare with the entry's program" (model
  programs), and program rewrites (gp).
- **Files**: buttons open the artifact's text files (`.md`, `.txt`, `.csv`, `.json`, `.gp`, `.py`) in
  an inline viewer.
- **Read-only**: the page shows the command to change status (`oeisbot review set <id> ...`).

### Run history

- **Tiles**: machine hours, program runs, wins (and the share of runs), hours per win.
- **"Runs and wins per day"**: stacked columns, wins (outcome `extended`) in blue and every other program
  run in gray, including superseded and `recheck_pending` runs, which did find new terms. Runs are dated by
  when they started.
- **"Machine hours per day"**: columns.
- **Sessions table**: id, start, finish (or "running"), attempts, wins, machine time, settings note. The
  counts are the ones stored when the session ended, so a `recheck_pending` win resolved later is missing
  from its session's wins.

Skip rows are excluded from the header's run count and from the Run history tiles and per-day charts.
They are included elsewhere: the Attempts table (filter the outcome to exclude `skipped`), the "Why
sequences were skipped" chart, and the Sessions table's Attempts column (`sessions.attempts`).

## API

All endpoints are `GET`, return JSON (except file contents), and open a fresh read-only connection. A
missing database returns 503.

| Endpoint | Parameters | Returns |
|---|---|---|
| `/api/summary` | | `candidates`, `attempts` (non-skip), `skipped`, `wins`, `new_terms`, `open_reviews` (new + reviewing), `machine_hours`, `oeisdata_commit`, `synced_at` |
| `/api/estimator` | | `points`: prediction rows with a positive prediction and an actual or censored time, joined with sequence and strategy; `stats`: `finished`, `censored`, `within_2x`, `median_ratio`, `mean_abs_log10_error`, `in_reported_range_2x`, `underestimated_censored` |
| `/api/queue` | `alpha` (1.0), `pari_only` (true), `limit` (500, max 30,000), `sort` (`weight`, `difficulty`, `a_number`) | `total`, `alpha`, `rows` with difficulty, weight, pick probability, languages, keywords, b-file status, known terms, credits, search flag |
| `/api/attempts` | `failure_mode`, `outcome`, `strategy`, `limit` (300, max 5,000) | `rows` (newest first), `failure_counts` (non-skip), `skip_counts`, `outcome_counts`, `strategies` |
| `/api/reviews` | | `rows`, ordered new, then reviewing, then the rest, newest first; each with attempt facts, sequence name, `files`, `weak_verification`, `rewrites` |
| `/api/reviews/{id}/files/{name}` | | plain text of one artifact file |
| `/api/history` | | `days` (per UTC day: runs, wins, skipped, machine hours); `sessions` (latest 100) |

### Safety properties

- **Never writes.** Every query runs on a `mode=ro` connection. `tests/test_dashboard.py` checks the
  database file is unchanged after calling the six JSON endpoints (not the file endpoint), and that the
  read-only connection refuses an `UPDATE`.
- **Artifact files are confined.** The artifact folder must resolve inside `artifacts/`, and the file
  name must be one of that folder's own text files. Tested: path traversal (`..%2F...`, `..\...`) and
  unknown names return 404.
- **Unknown `/api/...` paths return 404** rather than the frontend's `index.html`. This catch-all route
  exists only when the frontend is built, and it is not covered by a test.

The server binds to `127.0.0.1` by default and has no authentication. Do not expose it on a network.

## Frontend layout

| File | Role |
|---|---|
| `src/main.tsx` | app shell, tabs, header summary |
| `src/views.tsx` | the five views |
| `src/charts.tsx` | SVG charts: `LogScatter`, `BarList`, `StackedColumns`, tooltips, legend keys |
| `src/lib.tsx` | `useApi` (polling fetch), `useWidth` (responsive width via a callback ref), formatters, `Tile`, sortable `DataTable` |
| `src/styles.css` | color tokens for light and dark themes (follows the OS setting), layout |

There is no chart library; charts are hand-written SVG. Series colors are validated for color-vision
deficiency in both themes. The estimator chart has a table view and the bar charts label every value,
but the per-day history columns show exact values only in their tooltips. Text is rendered through
React, never as HTML.
