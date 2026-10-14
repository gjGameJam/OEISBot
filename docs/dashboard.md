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

Tabs are addressable by URL hash (`#estimator`, `#pickmap`, `#queue`, `#attempts`, `#reviews`,
`#history`). The header shows candidates, runs, wins, reviews awaiting action, machine hours, and the
oeisdata commit and sync time. Data refreshes every 15 s (the queue every 60 s, the Pick map every hour).
The previous data stays on screen while it reloads; the estimator card, the queue table, the attempts table
and the Pick map are also dimmed during a reload.

### Estimator accuracy

Whether the feasibility step works.

- **Filters**: cost unit (all, work counts, CPU time), trusted projections only (`predictions.trustworthy`:
  those the over-prediction kill acts on, unless the term is value-dependent; session 5's two kills came before
  that rule and are stored untrusted), chart/table toggle. This filter is the *kill's* flag, not the cost
  fit's: since 2026-09-21 the table also has `fit_trustworthy`, which the dashboard does not yet show, so a
  fit withdrawn only by the rate drift is filtered out here while reading as a sound fit in SQL.
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

### Pick map

How likely each candidate is to be drawn, and how that has moved (history item 54). A treemap in the manner of
a stock-market heat map: **a tile's area is the sequence's pick chance, its colour is how the chance has
changed** since an earlier snapshot of the pool. The pool is the one a session draws from
(`attempt.session_pool`, the same call `run_session`, `oeisbot queue` and `oeisbot snapshot` make), not the
wider one the Queue tab shows.

- **Pick chance** is `weight / sum of weights` with `weight = difficulty ** -alpha` (`select.weight`) over
  the pool, i.e. the chance of being a session's **first** draw. It is the share that adds up to 100%
  across the pool and so can be drawn as area. A session makes later draws without replacement, so a
  sequence's chance of appearing somewhere in a session of k picks is larger than its tile says
  ([known limitations](known-limitations.md#the-pick-map)).
- **Controls**: the pool (`PARI pool`, about 3,400 sequences; `Model pool`, about 26,700), α (0 to 6, applied
  half a second after typing stops; it changes the areas and the colours, not the pool), and **Rebuild now**.
  The line after them says how long ago the pool was built and what it left out (`Runnable.summary()`).
  The age is the one in the last response (`age_s`), and the page asks again once an hour, so the line can
  read up to an hour less than the pool's true age.
  - **An α the server would refuse is not sent.** Empty, not a number, negative or above 6
    (`treemap.parseAlpha`, whose limit `MAX_ALPHA` is the server's; `tests/test_pickmap.py` fails if the two
    differ): the field is marked invalid, a message under the controls says so, and the map keeps the last
    α that was valid, which it names.
  - **Rebuild now asks once.** The request carries `refresh=true` and a counter (`treemap.pickmapPath`), so the
    browser cannot answer it from its cache; the hourly refresh that follows carries neither, and choosing
    another pool or α drops the request. While a load is in flight the button reads "Building…" and is
    disabled, and the map is dimmed.
- **Tiles** above the map: candidates; the snapshot compared with (id, time, session, size); how many
  sequences **moved 10% or more** and what share of the picks they hold; how many sequences entered and left
  the pool and what share of the picks each side held.
- **Notes** appear when the comparison needs a caveat: no snapshot is stored yet; every stored snapshot equals
  the live pool; the baseline was taken under other **budgets** than the live pool; the **selection rules**
  (the code that scores and gates candidates) changed since the baseline, or **could not be compared** with
  it (the baseline recorded none, or either side's fingerprint is `unknown` because a source file could not
  be read: the note then says a change cannot be ruled out); or a session is running now (the map then
  shows the attempts it has recorded so far; only the newest session can be running, and one unfinished for
  more than 24 hours counts as crashed, `RUNNING_SESSION_MAX_AGE`).
- **An empty pool** (no candidate left for it) draws no map: the card says so and nothing else is built.
- **Tabs by difficulty band**: *All bands* draws every band as a labelled block whose area is the band's
  share of the picks, with its tiles inside; one tab per **non-empty** band draws only that band's tiles,
  so a band of 800 sequences is readable on its own. The bands are on the *effective* difficulty
  (`pickmap.BAND_EDGES`: 0.5, 0.75, 1, 1.5, 2, 4, 8, 16; a value equal to an edge belongs to the band above),
  and each tab carries the band's size and share. Clicking a band's header, or a lump inside it, opens that
  band's tab.
- **Colour** is one of seven classes of `ratio`, the chance now over the chance then (red is down, blue is
  up, gray is within 1%): down 45% or more (ratio at most 0.55), down 10 to 45%, down 1 to 10%, within 1%,
  up 1 to 10%, up 10 to 80%, up 80% or more (at least 1.8). The outer edges are 0.55 and 1.8 rather than 0.5
  and 2 on purpose: the commonest event, one failed attempt, doubles a sequence's difficulty and so moves its
  chance to 0.50 times what it was (at α 1), and a class edge must not sit on the value the data piles up at.
  A tile for a sequence that was **not in the baseline** is hatched. With no baseline every tile is gray and
  its label shows the pick chance instead of the change.
- **How the change is measured** matters more than it looks. `ratio` compares each sequence with the others
  that were **in both pools**: its share of the picks those sequences hold between them, now over then
  (`pickmap.compare`). A plain `p / p_then` would move every tile by the same factor whenever sequences
  enter or leave. Measured 2026-10-13 from `data/oeisbot-before-session12.sqlite3` to the live database
  (`select.candidates` over the PARI pool, α 1): 55 sequences left, holding 1.9% of the picks, and a plain
  ratio painted the 3,355 survivors whose difficulty had not changed all "up 2%", which is true and says
  nothing about any of them. Here a sequence that failed (its difficulty doubled, its share halved) shows as
  about −50% and the rest as about 0%. "About" because the others read `1 / (1 − f/2)` when the sequences
  that moved held a fraction f of the survivors' picks at α 1: 1.006 for f = 1.25%, 1.016 for a single tile
  with 3.2%. The "Chance before (rescaled)" in a tooltip (and "Before (rescaled)" in the table view) is
  scaled by the same factor, so `before × change = now` adds up on screen; it is not the share the
  sequence held in the earlier pool, which is what the "Left the pool" card shows for sequences that left.
- **Small tiles are lumped.** A tile that would get less than `max(36, width × height / 9000)` pixels² is not
  drawn on its own; a band's small tiles share one dashed-outline "N small" tile, coloured by what its
  members hold between them. **A tile that changed (down 10% or more, up 10% or more) and a new tile are never
  lumped**, however small: the map exists to show them. A lump of one is just that tile. A lump has no entry
  to open: in *All bands* clicking it opens its band's tab, and on a band's own tab it does nothing.
- **Area means the same thing in every band.** In *All bands* each band's block loses a header strip and
  padding, which take a larger part of a small block than of a large one, so laying out the plain band totals
  would draw the same pick chance smaller in a small band. `treemap.fairRects` therefore enlarges each band's
  weight by the part of its block the frame takes, over eight passes, before the leaves are laid out. A band
  the frame all but swallows (less than a quarter of its block left, `MIN_KEPT`) is left as it was: it has
  nothing to compensate with. Two things still shave area, both listed in
  [known limitations](known-limitations.md#the-pick-map): that case, and the 1 px inset of every tile.
- **Hover** shows the chance of being picked first, the chance before (rescaled) and the change, the difficulty
  and the band; **clicking a tile opens its entry on oeis.org**. The map is an SVG with a label and a **table
  view** (`details` under the legend, built only when opened) of the rows of the tab shown: sequence, name,
  difficulty, band, pick chance, before (rescaled), change, sortable; a new sequence has no "before" and reads
  `new`.
- **"Left the pool since #N"**: the sequences in the baseline that are not in the live pool, how much of the
  baseline's picks they held, **why** (`pickmap.departure_reason`, read from what the database recorded after
  the snapshot) and the ten that held most. In order of precedence: an open review (`review new`, ...); the
  newest attempt since the snapshot (`attempted: failed (verify_timeout)`; `win waiting for its re-check` for a
  `recheck_pending` win); the sequence no longer being in the `more` list at a sync; the selection rules
  having changed; the budgets differing; otherwise **`unexplained`**. A sequence reads `unexplained` only when
  nothing the database recorded accounts for it and neither fingerprint is known to differ. When the rules
  cannot be compared (the baseline recorded none, or a fingerprint is `unknown`) the map carries a note saying
  a change in them cannot be ruled out, and a departure that rules could explain still reads `unexplained`,
  because the label would otherwise claim a cause nobody measured. The attempt reason looks at attempts that
  started at or after the baseline's `taken_at`, so the session that took the snapshot counts; the review
  reason is whatever review is open now, and the `more` list is read as it is now.
  The rules fingerprint is the one of the code the dashboard process **loaded** (taken once per process, so
  an edit to a rule file the server has not reloaded does not read as a change), against the one stored with
  the baseline (`attempt.rules_fingerprint`: [data and schema](data-and-schema.md#pick_snapshots-and-pick_snapshot_rows-the-pool-a-session-drew-from-history-item-54)
  lists what it covers).
- **The live pool is built on demand and cached.** Building it costs about 6 to 12 s for either pool, and
  the first build after a cold start more (measured 2026-10-13, six fresh processes against the live database:
  PARI 25.1, 5.8 and 5.7 s, the model pool 9.3, 6.0 and 6.7 s; the slow first build is presumably the disk cache,
  which was not isolated). The cache holds one pool per kind, keyed
  on the database file's and its WAL's modification time and size (any commit moves one, including a `sync` or
  a rescore) plus the budgets, with an hour as a backstop (`POOL_TTL_S`). A lock makes two requests that
  arrive together wait for one build, and a request accepts a build that **finished after it asked** even if
  the database has moved since (a build counter, `_generation`, decides that, not a clock: Windows'
  monotonic clock ticks about every 16 ms, so a build and the next request can read the same tick).
  Without that rule, while a session is running and the database moves all the time, every waiter would
  build again. A lookup that finds a usable entry takes no lock, so the PARI pool is never held up behind
  the model pool's build. So **while a session is running every commit invalidates the cache** and a fresh
  load waits for a rebuild. `oeisbot dashboard` builds the PARI pool in a background thread at start-up
  (a failure there is printed and the tab reports its own), so the first visit to the tab does not wait. The
  pool is built under the **budgets of the pool's newest snapshot** (the defaults when there is none), so a
  difference from the baseline is something that happened and not a change of budget.

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
- **Each review** opens with the same three facts, in the same order, as `oeisbot review list`
  (`cli.review_block`): the sequence (status, A-number, name, review id), then the addition and where it
  came from (`N new terms, a(i)..a(j), from <program origin>, attempt #k`, with strategy, runtime and
  creation time after it), then the bookkeeping below. Keep the two in step (history item 51).
- **Warnings**: weak verification, AI-generated program, "numbered by the runner" (a `members(work)`
  program: read `executed.py` too), hard-coded bounds and "compare with the entry's program" (model
  programs), program rewrites (gp), and, since 2026-09-30, a term that lands below the entry's published
  searched bound (`extra.below_published_bound`: the bound, the quoted comment and the indices).
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
| `/api/reviews` | | `rows`, ordered new, then reviewing, then the rest, newest first; each with attempt facts (`strategy`, `program_origin`, `new_terms`, `runtime_s`, ...), sequence name, `files`, `weak_verification`, `rewrites` |
| `/api/reviews/{id}/files/{name}` | | plain text of one artifact file |
| `/api/history` | | `days` (per UTC day: runs, wins, skipped, machine hours); `sessions` (latest 100) |
| `/api/pickmap` | `pool` (`pari` or `model`, default `pari`; anything else is a 422), `alpha` (1.0; outside 0 to 6, or `nan`, is a 422), `refresh` (false: rebuild the live pool now instead of using the cache) | `pool`, `alpha`, `n`, `bands` (per non-empty band: `band`, `label`, `n`, `share`), `built_at`, `age_s`, `note` (what the pool left out), `running_session`, `snapshots` (how many are stored for this pool), `baseline` (`id`, `taken_at`, `n`, `session_id`, `budgets_differ`, `rules_differ`; null when there is nothing to compare with), `entered` (`n`, `share`), `gone` (`n`, `share`, `reasons`, `top`), `rows` (largest first: `a`, `name`, `d`, `band`, `p`, `p0`, `ratio`, `new`) |

### Safety properties

- **Never writes.** Every query runs on a `mode=ro` connection. `tests/test_dashboard.py` checks the
  database file is unchanged after calling the seven JSON endpoints (not the file endpoint), that every
  connection they opened was read-only (a spy on `db.connect`, which also covers the Pick map's pool build
  and the start-up warm-up), and that the read-only connection refuses an `UPDATE`. The Pick map reads
  the snapshot tables but never writes them; only `oeisbot run` and `oeisbot snapshot` do.
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
| `src/views.tsx` | five of the six views (the Pick map has its own file) |
| `src/pickmap.tsx` | the Pick map view: controls, band tabs, the SVG treemap, legend, table view, "Left the pool" card |
| `src/treemap.ts` | pure layout, colour binning and request building for the Pick map: squarified treemap, nested layout with lumping and `fairRects`, the seven change classes, `parseAlpha`, `pickmapPath`. No React, so `npm test` (`test/treemap.test.ts`, run by node itself) covers it |
| `src/charts.tsx` | SVG charts: `LogScatter`, `BarList`, `StackedColumns`, tooltips, legend keys |
| `src/lib.tsx` | `useApi` (polling fetch; `pollPath` is what the repeats ask for, so a forced rebuild is asked once), `useWidth` (responsive width via a callback ref), formatters, `Tile`, sortable `DataTable` |
| `src/styles.css` | color tokens for light and dark themes (follows the OS setting), layout |

There is no chart library; charts are hand-written SVG. Series colors are validated for color-vision
deficiency in both themes. The estimator chart has a table view and the bar charts label every value,
but the per-day history columns show exact values only in their tooltips. The Pick map's red-to-blue
scale (`--chg-0` to `--chg-6` in `styles.css`, with a matching `--chg-ink-*` text colour, each defined for
both themes) is a diverging scale, which that check (written for categorical palettes) fails by design:
run on the light set it reports the three pale classes near the middle as below the chroma floor, its
worst adjacent pair (gray and light red) at ΔE 11 against a floor of 15 in normal vision (colour-vision
separation passes, at 9.4), and five classes as under 3:1 against the surface (the gray "within 1%" one
at 1.1:1), and it requires relief for that. The relief is that the map does
not rely on colour alone: a tile large enough carries its change as text, a new tile is hatched, and the
tooltip and the table view give every value. The dark set was not run through the validator.
Text is rendered through React, never as HTML.
