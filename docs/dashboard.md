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
`/api/docs`; `/` is then a 404 that names the build command). The frontend can be built while the server
runs: the page and its assets are looked for at each request. The dashboard needs the `dashboard` extra (`fastapi`, `uvicorn`), which the `dev` extra
includes.

For frontend development run `oeisbot dashboard` and, separately, `npm run dev` in `dashboard/`. Vite
proxies `/api` to `127.0.0.1:8765`.

It can run while a session is writing: SQLite WAL lets it read mid-write.

## Views

Tabs are addressable by URL hash (`#estimator`, `#pickmap`, `#queue`, `#attempts`, `#reviews`,
`#history`); choosing a tab adds a browser-history entry, and an address with no fragment or an unknown
one is corrected in place to the first tab. The header shows the number of sequences with keyword `more`
in the mirror (`sequences.in_more`: far more than any pool a session draws from, which the Queue and the
Pick map each count for themselves), runs, **wins** and, after them, how many more were rejected in review,
reviews awaiting action, machine hours, and the oeisdata commit and sync time. **A win, everywhere on the
dashboard, is a run recorded `extended` whose review was not rejected and not refused** (`app.WIN`; history
item 56): reviews #2 and #3 were rejected as conjectural and their runs stay `extended`, so `extended` alone
counted them (the header read "3 wins" where there is one). Data refreshes every 15 s (the queue every 60 s, the Pick map every hour).
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
  orange = CPU-time projections. The diagonal is a perfect prediction; the shaded band is within 2×
  (between `y = 2x` and `y = x/2` along its whole length). Hollow points were stopped before finishing, so
  the true cost is at least the plotted value. Hovering or focusing a point shows sequence, index,
  predicted, range, ratio and model; a focused point has a visible ring and an `aria-label` with the same
  figures. The legend lists only the series the cost-unit filter leaves.
  - **The axes always hold every point** (`scale.timeDomain`, history item 56). The tick ladder is powers
    of ten of a second up to 10 s, then 1 min, 10 min, 1 h, 1 d and powers of ten of a day, with no first or
    last rung, and the axes run from the tick at or below the smallest value (less a margin) to the one at or
    above the largest. Until item 56 the ladder stopped at 1 ms, so seven terms of A385331 that finished in
    0.28 to 0.60 ms were drawn below the axis, on its labels. Nothing is clipped: a clip would hide such a
    point instead of showing the mistake. Tick labels are thinned when they would overlap.
  - A point is a finished time or, failing that, the time the term was stopped at (`scale.actualOrBound`,
    using the `finished` flag the server sends). A row with neither is not drawn; the table still lists it.
- **Table**: the same rows, sortable (defaults to worst ratio first). The Actual column sorts a stopped
  term by the time it was stopped at.
- **Durations** everywhere on the dashboard are written by `format.fmtSeconds`: three significant digits
  in µs, ms, s, min, h or d, never in exponent notation (an Attempts runtime used to read "1.1e+2 ms").

A point appears once a verified run has a time projection whose term finished (filled) or was cut short
(hollow, a genuine lower bound). A projection that stopped the run as `infeasible` does not appear: its
term never started, so it has neither an actual nor a censored time (see
[verification](verification-and-estimation.md#where-predictions-are-stored)). On the real database as
of 2026-11-17 the view has 20 points (`/api/estimator`: 10 finished, 10 stopped). **All ten finished points
are one run**, A385331's attempt 139, so the tiles above the chart describe that run and not the estimator
in general: its median actual/predicted is 0.0000013, because terms projected at minutes arrived in under a
millisecond. As of 2026-09-19 the view had five points, all hollow: A277532 and A390295 twice each, and
A247883's model program (attempt 92), which ran its whole 120 s extension without a new term. In session 5 the first
new terms of A277532 and A390295 were killed for over-prediction after 24 s and 10 s (before only trustworthy projections
could kill); in the offer-B check the same terms ran the whole 300 s extension without finishing.

### Pick map

How likely each candidate is to be drawn, and how that has moved (history items 54 and 55). A treemap in the
manner of a stock-market heat map: **a tile's area is the sequence's pick chance, its colour is how the chance
has changed** since an earlier snapshot of the pool. The pool is the one a session draws from
(`attempt.session_pool`, the same call `run_session`, `oeisbot queue`, `oeisbot snapshot` and `oeisbot sync`
make), not the wider one the Queue tab shows.

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
    `aria-disabled` (a click does nothing), and the map is dimmed. It is `aria-disabled` rather than `disabled`
    so that a keyboard user who pressed it keeps the focus, which a button that becomes disabled loses.
  - **A pool that cannot be built is said so, and the last map stays.** The server answers 503 with a JSON body
    `{"error": "pool_build_failed", "reason": "<ExceptionType>: <message>"}` (the message on one line, at most
    200 characters; the traceback goes to the `oeisbot.dashboard` logger, which nothing configures, so Python's
    last-resort handler prints it to the standard error of `oeisbot dashboard`; checked under uvicorn's own
    logging configuration, which touches only its three loggers) and caches nothing, so the next request builds
    again. The page shows
    "The PARI pool could not be built: <reason>" (`treemap.failureReason` reads the reason out of the error text
    `useApi` keeps) and a **Try again** button that asks for a rebuild, above the map of the last request that
    loaded, which the message says it is. Any other failure (including the 503 for a missing database, whose
    body is not this one) reads "Could not load: ..." with the same button; the text after the colon is
    `format.describeError`'s reading of the failure (the status and the server's reason, at most 200
    characters, never a raw JSON body or a whole HTML page), on this tab and every other. The message goes as soon as the
    new request starts, taking the button with it, so **Try again moves the keyboard focus to Rebuild now**
    (which then reads "Building…"); otherwise the focus would fall to the top of the page. The map is dimmed only while a
    request is out, not behind the message. The failure is not stored anywhere: the message goes when the page
    asks on another path (Try again, another pool or α) or when any request succeeds, and returns if the
    new request fails; the hourly refresh is the only retry on a timer.
- **Tiles** above the map: candidates; the snapshot compared with (id, time, session, size); how many
  sequences **moved 10% or more** and what share of the picks they hold; how many sequences entered and left
  the pool and what share of the picks each side held.
- **Notes** appear when the comparison needs a caveat. One that says the colours may mislead carries a red
  "!"; one that only describes the state of things a gray "i" (they all carried the "!" until item 56). The
  note for a pool with no snapshot names the command that stores one **for that pool**: `oeisbot snapshot`
  stores the PARI pool only, and the model pool needs `oeisbot snapshot --all` or a session started with
  `oeisbot run --model`. The cases: no snapshot is stored yet; every stored snapshot equals
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
  band's tab. Pressing the pool button that is already chosen does nothing (it used to reset the band).
- **Bands too small to draw are named under the map** (history item 55). In *All bands*, a band whose tiles get
  less than 6 px (`treemap.MIN_DRAWN_SIDE`) in either direction, inside its frame and padding, can be neither
  seen nor pointed at (`treemap.undrawn`; a band that got no area at all counts). Such a band is also the one
  band not drawn at the map's common scale (`scaled: false`, below). A line under the map,
  "Too small to draw to scale here:", lists each as a button reading the band's label, size and share; it
  opens the band's tab and puts the keyboard focus on that tab (the button it came from is gone).
  Measured on the real PARI pool at every width the page gives the map, 200 to 1198 px
  (`data/item56/area_spread.txt`): **band 8 (2 sequences, 0.002%) is listed at all 999 widths and band 7
  (25 sequences, 0.07%) at 678 of them**; on the model pool only band 8, at 102 widths. So the line is
  normally there on the PARI pool, and a band tab's own view never has it, because the band fills the box.
- **Keyboard** (history item 55). Tab reaches the map at **one** tile, the one last focused or else the first
  in `treemap.focusOrder`; the arrow keys then move to the nearest tile in that direction (`treemap.neighbour`: of the tiles whose
  centre lies beyond the current one's that way, the one with the smallest gap along the axis plus **twice** the
  miss across it, 0 when they overlap there; then the closer centre across the axis, then the smaller
  A-number; nothing happens at an edge), Home and End go to the first and the last, **Enter or Space** opens
  the entry on oeis.org (a lump opens its band and the focus then goes to the new map's first tile; on a
  band's own tab, where there is no band left to open, a lump opens the **table view** and the focus goes to
  its heading; a key held down acts once, not once per repeat, so it cannot open a tab per repeat), and
  **Escape** closes the tooltip (and it stays closed through a resize or a refresh, until the focus moves to
  a tile again). A focused tile shows the same 2 px outline as a hovered one
  and, when the browser calls the focus keyboard-driven (`:focus-visible`), its tooltip; a click that focuses a
  tile shows none. A sequence tile is a `link`, a lump a `button`, each with an `aria-label` of
  its name and figures. **Not reachable:** a tile under 3 px on either side (`treemap.MIN_FOCUS_SIDE`: a tile
  that changed is drawn however small, and a focus ring on a speck helps nobody; a band left with no stop at
  all by that rule keeps one, on its largest tile), a tile with no area, and every tile of a band listed in
  the "too small to draw to scale" line; the table view reaches all of them.
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
  to open: in *All bands* clicking it opens its band's tab, and on a band's own tab it opens the table view,
  which lists what it stands for. That second case is the only way into a band too dense for tiles: the model
  pool's band "1 to 1.5" holds 9,395 sequences, and its tab is one lump at the default width and a lump of
  6,851 beside 2,544 tiles at full width (it used to be a tile that did nothing).
- **Area means the same thing in every band, exactly** (history item 56). In *All bands* each band's block
  loses a header strip and padding, which take a larger part of a small block than of a large one, so laying
  out the plain band totals would draw the same pick chance smaller in a small band. `treemap.layoutGroups`
  therefore draws every band **at one scale**: the px² per unit of pick chance of the tightest band that has
  room for tiles (`commonScale`). A roomier band draws its tiles in the part of its inner box that scale fills
  (the box's top-left, cut along its longer side) and **leaves the rest of the box empty**; that empty strip is
  the price, and the caption says so. Before that, `treemap.fairRects` tries nine layouts of the band blocks
  (the plain totals, then eight in which each band's weight is enlarged by the part of its block the frame took
  in the layout before) and keeps the one whose tightest band has the most room, so that little is left
  empty: on the PARI pool a median of 0.4% of the framed area over the page's 999 widths, 23.5% at the worst
  one (`data/item56/area_spread.txt`). Until item 56 that search was the whole mechanism and was assumed to
  converge; it cycles on the squarified layout's row breaks, and bands were drawn 5% or more apart at 542 of
  the 999 widths and 2.0× apart at 323 px. A band with no room for tiles (under 6 px either way inside its
  frame) cannot be drawn at the common scale and does not set it; it is the band the line under the map
  names. A tile's paint stops 0.5 px short of its rect on each side (`pickmap.TILE_INSET`), so what is
  exactly equal is the tile's rect, gutter included; what that leaves is in
  [known limitations](known-limitations.md#the-pick-map).
- **Hover or keyboard focus** shows the chance of being picked first, the chance before (rescaled) and the change,
  the difficulty and the band; **clicking a tile opens its entry on oeis.org**. Whichever of the two moved last
  owns the tooltip: the mouse leaving, or moving over a band's header or frame, does not close one the keyboard
  opened, nor does blurring close one the mouse opened. A new layout (another band, a resize, a refresh) or a
  scroll (of the page or of anything in it) closes
  the tooltip, except that a tile which still has the keyboard focus gets its tooltip back, placed where the tile
  now is (it would otherwise stay closed until a key moved the focus, and the browser scrolls a half-hidden
  tile into view just after focusing it). A tooltip is not a live region: the focused tile's own label
  already says what it shows. If the new layout no longer has the
  focused tile (a refresh that lumps it, a pool without it) the browser drops the focus to the page and the next Tab
  starts from the top of it, by reading of the DOM rules and not seen in a browser; only opening a lump from
  the keyboard moves the focus on. The map is an SVG with `role="group"` and a
  label that names the keys, and a **table
  view** (`details` under the legend, built only when opened; opened by hand or by a lump on a band's tab,
  and closed again when another band is chosen) of the rows of the tab shown: sequence, name,
  difficulty, band, pick chance, before (rescaled), change, sortable; a new sequence has no "before" and reads
  `new`. A name longer than 90 characters is cut at a word and ends in "…" (`app.short_name`), in the map,
  the table and the "Left the pool" card alike; it used to stop mid-word with no mark. A change is written so
  that it never reads as the next colour class (`treemap.fmtChange`: −9.999% is "−9.9%", in "down 1 to 10%"),
  and a share too small for four decimals reads "< 0.0001%" (`format.fmtShare`).
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
  difference from the baseline is something that happened and not a change of budget. **A build that fails is
  never cached**: the next request builds again, which is what the tab's "Try again" button asks for.

### Queue

The candidate pool as selection sees it, before the last check a session applies (see the last point):

- **Controls**: α, "only sequences with a PARI program". α follows the Pick map's rule: only a number from
  0 to 6 is sent, half a second after typing stops (`treemap.parseAlpha`); anything else marks the field
  invalid and the message names the α the table still shows. The server refuses the same values with a 422.
- **Table** (up to 2,000 rows, sortable): A-number (links to oeis.org), name, difficulty, pick chance,
  programs, known terms, b-file status, extension credits, search flag. **Sorting reorders the rows that
  were sent, not the whole queue** (5,315 with a PARI program on 2026-11-17, of which the 2,000 most likely
  are sent), and at α 0 every sequence is equally likely, so which 2,000 are sent is arbitrary; the caption
  says both.
- Sequences with an open review or a `recheck_pending` win are excluded, exactly as in selection.
- Unlike a session, `oeisbot queue` and `oeisbot pick`, the tab does **not** leave out sequences an attempt
  could only skip (no supported PARI program, all programs dead ends or out of reach): that check reads
  every PARI-bearing entry from disk (about 3 s) and the tab refreshes every minute. Its totals and pick
  chances are therefore those of the wider pool. `oeisbot queue` shows the pool a session really uses.

### Attempts

What to fix next.

- **Filters**: outcome, strategy.
- **"Why runs stopped"**: bar chart of stop reasons for program runs. Clicking a bar (or Enter or Space on
  it) filters the table; a chip above clears the filter. **Both bar charts count all runs**, whatever the
  outcome and strategy filters say: they are the control that filters, not a view of the filtered rows. A run
  with no stop reason is counted, and filtered, as `none`.
- **"Why sequences were skipped"**: bar chart of skip reasons.
- **Table** (latest 1,000 matching rows, with a line saying so when more match): id, start time, sequence,
  strategy, outcome, stop reason, reproduced/known, new terms, runtime, peak memory, detail. An `extended`
  run that is not a win is marked "review rejected". Peak memory reads "–" for a gp run that ended before
  reporting any stack figure (the stored value is 0 there, which is "not measured": 20 rows on 2026-11-17).

### Review inbox

Runs that produced new terms, open reviews first.

- **Tiles**: counts by status.
- **A rejected review is set apart** (a rule down its left side, a red pill) **and shows its note**, which is
  where the rejection says why; `oeisbot review list` prints the note, and until item 56 this page dropped it,
  so reviews #2 and #3 read "200 new terms" under a caption about successes.
- **Each review** opens with the same three facts, in the same order, as `oeisbot review list`
  (`cli.review_block`): the sequence (status, A-number, name, review id), then the addition and where it
  came from (`N new terms, a(i)..a(j), from <program origin>, attempt #k`, with strategy, runtime and
  creation time after it), then the bookkeeping below. Keep the two in step (history item 51).
- **Warnings**: weak verification, AI-generated program, "numbered by the runner" (a `members(work)`
  program: read `executed.py` too), hard-coded bounds and "compare with the entry's program" (model
  programs), program rewrites (gp), and, since 2026-09-30, a term that lands below the entry's published
  searched bound (`extra.below_published_bound`: the bound, the quoted comment and the indices).
- **Files**: buttons open the artifact's text files (`.md`, `.txt`, `.csv`, `.json`, `.gp`, `.py`) in
  an inline viewer, which starts empty for each file (it used to show the last file's text while the next
  one loaded).
- **Read-only**: the page shows the command to change status (`oeisbot review set <id> ...`).

### Run history

- **Tiles**: machine hours, program runs, wins (the share of runs, and how many more were rejected in
  review), hours per win. On 2026-11-17: 1 win, 2 rejected, 18.6 hours per win (it read 3 wins and 6.2).
- **"Runs and wins per day"**: stacked columns, wins in blue, runs whose win was rejected in review in
  orange (the series appears only when there are any), and every other program run in gray ("Other runs"),
  including superseded and `recheck_pending` runs, which did find new terms. Runs are dated by when they
  started, **by UTC day**, which the captions say: an evening run in a zone west of Greenwich falls on the
  next day's column (session 10 started Sep 24, 8:20 PM local and is charted on 09-25).
- **One column per calendar day** from the first run to the last (`scale.dayColumns`): a day without runs is
  an empty slot, and a run of more than three such days is one "…" marker whose tooltip gives the dates, so
  that columns side by side are days side by side. Labels carry the year only when the chart spans more than
  one.
- **"Machine hours per day"**: columns, the same days.
- **Sessions table**: id, start, finish (or "running"), attempts, wins, machine time, settings note. **Wins
  are counted from the session's attempts when the page asks** (`app.history`), not read from
  `sessions.wins`: the stored figure was written when the session ended and still counts a win rejected
  since (session 9's stored 2 reads "0 (2 rejected)"), and it misses a `recheck_pending` win resolved later,
  which the count from attempts includes. Attempts and machine time are the stored figures. A line says so
  when more sessions exist than the 100 loaded.

Skip rows are excluded from the header's run count and from the Run history tiles and per-day charts.
They are included elsewhere: the Attempts table (filter the outcome to exclude `skipped`), the "Why
sequences were skipped" chart, and the Sessions table's Attempts column (`sessions.attempts`).

## API

All endpoints are `GET`, return JSON (except file contents), and open a fresh read-only connection. A
missing database returns 503, and so does a Pick map pool that cannot be built (below). A number out of
its range is a 422 (FastAPI's validation), a request addressed to a host name the server does not answer to
is a 400, and an API request a browser says another page made is a 403 (both under
[safety properties](#safety-properties)).

| Endpoint | Parameters | Returns |
|---|---|---|
| `/api/summary` | | `candidates` (sequences with keyword `more`), `attempts` (non-skip), `skipped`, `wins` and `new_terms` (of runs that are wins: `extended`, review neither rejected nor refused), `rejected_wins` (the other `extended` runs), `open_reviews` (new + reviewing), `machine_hours`, `oeisdata_commit`, `synced_at` |
| `/api/estimator` | | `points`: prediction rows with a positive prediction and an actual or censored time, joined with sequence and strategy, each with `finished` (it has a positive actual time; a zero is not one); `stats`: `finished`, `censored`, `within_2x`, `median_ratio`, `mean_abs_log10_error`, `in_reported_range_2x`, `underestimated_censored` |
| `/api/queue` | `alpha` (1.0; 0 to 6, as the Pick map's), `pari_only` (true), `limit` (500; 0 to 30,000), `sort` (`weight`, `difficulty`, `a_number`) | `total`, `alpha`, `rows` with difficulty, weight, pick probability, languages, keywords, b-file status, known terms, credits, search flag |
| `/api/attempts` | `failure_mode` (`none` selects runs with no stop reason), `outcome`, `strategy`, `limit` (300; 0 to 5,000) | `rows` (newest first, each with `win_rejected`: an `extended` run that is not a win), `total` (how many match in all), `failure_counts` (non-skip; a missing reason under `none`), `skip_counts`, `outcome_counts`, `strategies` |
| `/api/reviews` | | `rows`, ordered new, then reviewing, then the rest, newest first; each with `status`, `note`, attempt facts (`strategy`, `program_origin`, `new_terms`, `runtime_s`, ...), sequence name, `files`, `weak_verification`, `rewrites`, `below_bound` (the published bound a new term lands below, or null) |
| `/api/reviews/{id}/files/{name}` | `id` from 1 to 2⁶³ − 1 | plain text of one artifact file |
| `/api/history` | `session_limit` (100; 0 to 5,000) | `days` (per UTC day: runs, `wins`, `rejected_wins`, skipped, machine hours); `sessions` (the latest, with `wins` and `rejected_wins` counted from their attempts); `sessions_total` |
| `/api/pickmap` | `pool` (`pari` or `model`, default `pari`; anything else is a 422), `alpha` (1.0; outside 0 to 6, or `nan`, is a 422), `refresh` (false: rebuild the live pool now instead of using the cache) | `pool`, `alpha`, `n`, `bands` (per non-empty band: `band`, `label`, `n`, `share`), `built_at`, `age_s`, `note` (what the pool left out), `running_session`, `snapshots` (how many are stored for this pool), `baseline` (`id`, `taken_at`, `n`, `session_id`, `budgets_differ`, `rules_differ`; null when there is nothing to compare with), `entered` (`n`, `share`), `gone` (`n`, `share`, `reasons`, `top`), `rows` (largest first: `a`, `name`, `d`, `band`, `p`, `p0`, `ratio`, `new`). **When the live pool cannot be built** (any exception from `session_pool`, a locked or unreadable database among them) the answer is a 503 with the body `{"error": "pool_build_failed", "reason": "<ExceptionType>: <message>"}` (the message on one line, cut at 200 characters) and the traceback goes to the `oeisbot.dashboard` logger; nothing is cached for it. A missing database keeps FastAPI's own 503 body (`no database at …`), which the tab shows as `Could not load: …` (also with the retry button) |

### Safety properties

- **Never writes the database.** Every query runs on a `mode=ro` connection. (SQLite itself rewrites the
  `-shm` file beside a WAL database on every read: [known limitations](known-limitations.md#the-pick-map).)
  `tests/test_dashboard.py` checks the
  database file is unchanged after calling the seven JSON endpoints (not the file endpoint), that every
  connection they opened was read-only (a spy on `db.connect`, which also covers the Pick map's pool build
  and the start-up warm-up), and that the read-only connection refuses an `UPDATE`. The Pick map reads
  the snapshot tables but never writes them; only `oeisbot run`, `oeisbot snapshot` and `oeisbot sync` do.
- **Artifact files are confined.** The artifact folder must resolve inside `artifacts/`, and the file
  name must be one of that folder's own text files. Tested: path traversal (`..%2F...`, `..\...`) and
  unknown names return 404.
- **Only `/` is the page; every other path that no route claims is a 404** (history item 56). The tabs are
  addressed by the URL's fragment, which never reaches the server, so nothing else has a page behind it.
  `/api`, `/API/summary`, `/docs`, `/openapi.json` and `/index.html` used to come back as the page with a
  200, and `/redoc` as FastAPI's second set of API docs, now turned off. The route is registered whether or
  not the frontend is built, and tested.
- **The server answers only to its own names** (`app.ALLOWED_HOSTS`: `127.0.0.1`, `localhost`, `::1`, and
  whatever `--host` names; the `Host` header is compared without its port, in lower case, an IPv6 literal
  without its brackets, and a header that is not a host and an optional port is refused). A request under any
  other name is a **400**. This is what stops a page on another site from reading the API through the
  user's own browser by pointing a host name it controls at 127.0.0.1 (DNS rebinding); the API holds
  unsubmitted terms. **`--host 0.0.0.0` or `::` turns the check off**, with a printed warning, because a
  wildcard address is reachable under names nobody can list.
- **An API request made by another page is refused** with a **403**: any `Sec-Fetch-Site` other than
  `same-origin` (the dashboard's own page, the Vite dev server's proxied one included) or `none` (an address
  typed in). An `<img>` on any site, or on another port of this machine, could otherwise make the server build
  a pool or serialize the whole queue. curl and other clients that send no such header are unaffected, and
  the page itself (`/`) can be linked to from anywhere.
- **Every response carries `X-Content-Type-Options: nosniff`**, the 500 of an endpoint that raised included:
  the file route serves text that programs wrote.
- **Numbers are bounded**: `alpha` 0 to 6 on both endpoints that take it (`nan` and `inf` included in the
  refusal; the queue's used to return a 500 from about 598 up and to invert the weighting below 0), `limit`
  and `session_limit` not negative (a negative `LIMIT` is "no limit" to SQLite), a review id within SQLite's
  integers.

The server binds to `127.0.0.1` by default and has no authentication. Do not expose it on a network.

## Frontend layout

| File | Role |
|---|---|
| `src/main.tsx` | app shell, tabs, header summary |
| `src/views.tsx` | five of the six views (the Pick map has its own file) |
| `src/pickmap.tsx` | the Pick map view: controls, band tabs, the SVG treemap with its roving-tabindex keyboard handling and tooltip ownership, the "Too small to draw to scale here" chips, the failure message with its retry button, legend, table view, "Left the pool" card. Node cannot run `.tsx`, so this file has no automated test |
| `src/treemap.ts` | pure layout, colour binning and request building for the Pick map: squarified treemap, nested layout at one common scale with lumping (`layoutGroups`, `commonScale`, `fairRects`), the seven change classes and `fmtChange`, `parseAlpha` (the Queue uses it too), `pickmapPath`, and the logic the keyboard and the footer chip rest on (`undrawn`, `focusOrder`, `neighbour`, `failureReason`). No React and no imports, so `npm test` (`test/treemap.test.ts`, run by node itself) covers it |
| `src/scale.ts` | pure scale arithmetic for the charts: the time-tick ladder and `timeDomain`, `logFraction`, the 2× band's corners, label thinning, `niceStep`, `actualOrBound`, `dayColumns`. No imports; `test/scale.test.ts` |
| `src/format.ts` | pure formatting: `fmtSeconds`, `sigFixed`, `fmtBytes`, `fmtPct`, `fmtInt`, `fmtTime` (the year shown when it is not this one), `fmtShare`, `describeError`. No imports; `test/format.test.ts`. Nothing in it may print exponent notation |
| `src/charts.tsx` | SVG charts: `LogScatter`, `BarList`, `StackedColumns` (with empty-day slots and gap markers), tooltips, legend keys |
| `src/lib.tsx` | `useApi` (polling fetch; `pollPath` is what the repeats ask for, so a forced rebuild is asked once; it keeps the raw error text, which `failureReason` parses), `useWidth` (responsive width via a callback ref), the formatters re-exported from `format.ts`, `Tile`, sortable `DataTable` |
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
