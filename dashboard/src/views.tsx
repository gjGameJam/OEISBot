import { useEffect, useState } from "react";
import { BarList, LegendDot, LogScatter, StackedColumns, type ScatterPoint } from "./charts";
import {
  DataTable, OeisLink, Tile, fmtBytes, fmtInt, fmtPct, fmtSeconds, fmtTime, useApi, type Column,
} from "./lib";
import { describeError, sigFixed } from "./format";
import { actualOrBound, dayColumns } from "./scale";
import { notAWin, passesTrust, trustOf } from "./tabs";
import { MAX_ALPHA, parseAlpha } from "./treemap";

export function Status({ error, loading, hasData }: { error: string | null; loading: boolean; hasData: boolean }) {
  if (error) return <p className="error" role="alert">Could not load: {describeError(error)}{hasData ? ". What is shown is the last answer that arrived." : ""}</p>;
  if (loading && !hasData) return <p className="muted">Loading…</p>;
  return null;
}

// ============================================================================ estimator accuracy

interface PredictionPoint {
  id: number; attempt_id: number; a_number: string; strategy: string; n: number; cost_unit: string;
  model: string | null; trustworthy: number; feasible: number; value_dependent: number;
  predicted_s: number; predicted_s_low: number | null; predicted_s_high: number | null;
  actual_s: number | null; censored_s: number | null; started_at: string; finished?: boolean;
  fit_trustworthy?: number | null; rate_drift?: number | null;
}
interface EstimatorData {
  points: PredictionPoint[];
  stats: { finished: number; censored: number; within_2x: number | null; median_ratio: number | null;
           mean_abs_log10_error: number | null; in_reported_range_2x: number | null; underestimated_censored: number };
}

// `trustOf` (tabs.ts) says which of the three a projection is; these are the words for each
const TRUST_NOTE = { trusted: "", fit: " (cost fit sound, rate drifting)", untrusted: " (untrusted)" };
const TRUST_CELL = { trusted: "yes", fit: "no: rate drifting, cost fit sound", untrusted: "no" };
const TRUST_ORDER = { trusted: 2, fit: 1, untrusted: 0 };

export function EstimatorView() {
  const { data, error, loading } = useApi<EstimatorData>("/api/estimator");
  const [unit, setUnit] = useState("all");
  const [trust, setTrust] = useState("all");
  const [table, setTable] = useState(false);
  const pts = (data?.points ?? []).filter((p) => (unit === "all" || p.cost_unit === unit) && passesTrust(trust, p));
  // A point is what `actualOrBound` says it is: a finished time, or the time the term was stopped at. A row
  // with neither is not drawn at all (it used to be drawn at its own prediction, as if it had been measured).
  const scatter: ScatterPoint[] = pts.flatMap((p) => {
    // `finished` is the server's word (app.estimator); a zero or missing time is never a finished one
    const got = actualOrBound(p.finished === false ? null : p.actual_s, p.censored_s);
    if (!got || !(p.predicted_s > 0)) return [];
    const { y } = got, hollow = !got.finished;
    return [{
      id: p.id, x: p.predicted_s, y, series: p.cost_unit === "work" ? 0 : 1, hollow,
      title: `${p.a_number} a(${p.n}) · ${p.strategy}`,
      rows: [
        { label: hollow ? "stopped after" : "actual", value: fmtSeconds(y) },
        { label: "predicted", value: fmtSeconds(p.predicted_s) },
        { label: "predicted range", value: `${fmtSeconds(p.predicted_s_low)} – ${fmtSeconds(p.predicted_s_high)}` },
        { label: "actual / predicted", value: `${hollow ? "≥ " : ""}${sigFixed(y / p.predicted_s, 2)}` },
        { label: "model", value: `${p.model ?? "none"}${TRUST_NOTE[trustOf(p)]}` },
        // the number the trust was withdrawn on: work per second late in the run over early in it
        ...(trustOf(p) === "fit" && p.rate_drift != null ? [{ label: "rate drift", value: `${sigFixed(p.rate_drift, 3)}×` }] : []),
      ],
    }];
  });
  const s = data?.stats;
  const timeOf = (r: PredictionPoint) => actualOrBound(r.actual_s, r.censored_s);
  const columns: Column<PredictionPoint>[] = [
    { key: "a_number", label: "Sequence", render: (r) => <OeisLink a={r.a_number} /> },
    { key: "n", label: "n", numeric: true },
    { key: "cost_unit", label: "Unit" },
    { key: "model", label: "Model", render: (r) => r.model ?? "–" },
    { key: "predicted_s", label: "Predicted", numeric: true, render: (r) => fmtSeconds(r.predicted_s) },
    // sorted by the time shown: a term that was stopped sorts by the time it was stopped at, its lower bound
    { key: "actual_s", label: "Actual", numeric: true, sortValue: (r) => timeOf(r)?.y ?? null,
      render: (r) => { const t = timeOf(r); return !t ? "–" : `${t.finished ? "" : "≥ "}${fmtSeconds(t.y)}`; } },
    { key: "ratio", label: "Actual / predicted", numeric: true,
      sortValue: (r) => { const t = timeOf(r); return t ? t.y / r.predicted_s : null; },
      render: (r) => { const t = timeOf(r); return !t ? "–" : `${t.finished ? "" : "≥ "}${sigFixed(t.y / r.predicted_s, 2)}`; } },
    // three answers, not two: a sound cost fit whose trust was withdrawn for a drifting rate is not an unsound one
    { key: "trustworthy", label: "Trusted", sortValue: (r) => TRUST_ORDER[trustOf(r)], render: (r) => TRUST_CELL[trustOf(r)] },
  ];
  return (
    <>
      <Status error={error} loading={loading} hasData={!!data} />
      <div className="filters">
        <label>Cost unit
          <select value={unit} onChange={(e) => setUnit(e.target.value)}>
            <option value="all">All</option><option value="work">Work counts</option><option value="cpu">CPU time</option>
          </select>
        </label>
        <label>Projections
          <select value={trust} onChange={(e) => setTrust(e.target.value)}>
            <option value="all">All</option><option value="trusted">Trusted</option><option value="fit">Trusted, or cost fit sound</option>
          </select>
        </label>
        <button className="chip" onClick={() => setTable(!table)}>{table ? "Show chart" : "Show table"}</button>
      </div>
      <div className="kpis">
        <Tile label="Terms predicted and finished" value={fmtInt(s?.finished)} sub={`${fmtInt(s?.censored)} stopped before finishing`} />
        <Tile label="Within 2× of prediction" value={fmtPct(s?.within_2x)} sub="finished terms" />
        <Tile label="Median actual / predicted" value={s?.median_ratio != null ? sigFixed(s.median_ratio, 2) : "–"} sub="above 1 means underestimates" />
        <Tile label="Inside reported range (±2×)" value={fmtPct(s?.in_reported_range_2x)} sub="low/2 ≤ actual ≤ high×2" />
        <Tile label="Stopped far past prediction" value={fmtInt(s?.underestimated_censored)} sub="ran over 2× the high estimate" />
      </div>
      <div className={`card ${loading && data ? "stale" : ""}`}>
        <h2>Estimator accuracy: predicted vs actual time per new term</h2>
        <p className="caption">
          Each point is one term the estimator projected before computing it. On the diagonal the prediction was exact;
          the shaded band is within 2×. Hollow points were stopped before they finished, so the true cost is at least that high.
          If most points sit well above the band, the feasibility step is not working.
        </p>
        {!data ? null : data.points.length === 0 ? (
          <div className="empty">No projected terms have run yet. Points appear once a verified program starts computing new terms.</div>
        ) : pts.length === 0 ? (
          <div className="empty">No projected term matches these filters ({fmtInt(data.points.length)} without them).</div>
        ) : table ? (
          <DataTable rows={pts} columns={columns} rowKey={(r) => r.id} initialSort={{ key: "ratio", desc: true }} />
        ) : scatter.length === 0 ? (
          <div className="empty">None of these {fmtInt(pts.length)} terms has a time to plot; the table lists them.</div>
        ) : (
          <>
            <div className="legend">
              {unit !== "cpu" && <LegendDot color="var(--series-1)">Work counts (instrumented)</LegendDot>}
              {unit !== "work" && <LegendDot color="var(--series-2)">CPU time (uninstrumented)</LegendDot>}
              <LegendDot color="var(--text-muted)" hollow>Stopped before finishing (actual ≥ shown)</LegendDot>
            </div>
            <LogScatter points={scatter} />
          </>
        )}
      </div>
    </>
  );
}

// ============================================================================ queue

interface QueueRow {
  a_number: string; name: string; difficulty: number; weight: number; pick_probability: number; program_langs: string;
  keywords: string | null; bfile_status: string | null; known_terms: number | null; more_credits: number | null; value_dependent: boolean;
}

const QUEUE_LIMIT = 2000;

export function QueueView() {
  // The box holds text; a request goes out only for a number the server takes (`parseAlpha`, the Pick map's
  // rule and the same bounds, app.queue), half a second after the typing stops. It used to send every
  // keystroke as it stood, and an empty box as 0.
  const [alphaText, setAlphaText] = useState("1");
  const [alpha, setAlpha] = useState(1);
  const typed = parseAlpha(alphaText);
  useEffect(() => {
    if (typed == null || typed === alpha) return;
    const t = window.setTimeout(() => setAlpha(typed), 500);
    return () => window.clearTimeout(t);
  }, [typed, alpha]);
  const [pariOnly, setPariOnly] = useState(true);
  const { data, error, loading } = useApi<{ total: number; alpha: number; rows: QueueRow[] }>(
    `/api/queue?alpha=${alpha}&pari_only=${pariOnly}&limit=${QUEUE_LIMIT}`, 60000);
  const cut = data != null && data.rows.length < data.total;
  const columns: Column<QueueRow>[] = [
    { key: "a_number", label: "Sequence", render: (r) => <OeisLink a={r.a_number} /> },
    { key: "name", label: "Name", render: (r) => <div className="wrap">{r.name}</div> },
    { key: "difficulty", label: "Difficulty", numeric: true, render: (r) => r.difficulty.toFixed(3) },
    { key: "pick_probability", label: "Pick chance", numeric: true, render: (r) => fmtPct(r.pick_probability, 3) },
    { key: "program_langs", label: "Programs", render: (r) => <span className="secondary">{r.program_langs || "none"}</span> },
    { key: "known_terms", label: "Known terms", numeric: true, render: (r) => fmtInt(r.known_terms) },
    { key: "bfile_status", label: "B-file", render: (r) => r.bfile_status ?? <span className="muted">not fetched</span> },
    { key: "more_credits", label: "Extensions", numeric: true },
    { key: "value_dependent", label: "Search", render: (r) => (r.value_dependent ? "yes" : "") },
  ];
  return (
    <>
      <div className="filters">
        <label>α (preference for easy targets)
          <input type="number" min={0} max={MAX_ALPHA} step={0.25} value={alphaText} onChange={(e) => setAlphaText(e.target.value)}
                 aria-invalid={typed == null} aria-describedby={typed == null ? "queue-alpha-error" : undefined} />
        </label>
        <label><input type="checkbox" checked={pariOnly} onChange={(e) => setPariOnly(e.target.checked)} /> Only sequences with a PARI program</label>
        <span className="muted">{data ? `${fmtInt(data.total)} in this queue${cut ? `; showing the ${fmtInt(data.rows.length)} most likely picks` : ""}` : ""}</span>
      </div>
      {typed == null && (
        <p id="queue-alpha-error" className="error" role="alert">α must be a number from 0 to {MAX_ALPHA}; the table still shows α {data?.alpha ?? alpha}.</p>
      )}
      <Status error={error} loading={loading} hasData={!!data} />
      {error && data && data.alpha !== alpha && <p className="error">The table below still shows α {data.alpha}.</p>}
      <div className={`card ${loading && data ? "stale" : ""}`}>
        <h2>Candidate queue</h2>
        <p className="caption">
          Pick chance is proportional to 1 / difficulty^α, over every sequence the queue holds. This is the queue before a
          session checks what it can actually run; the Pick map shows the pool a session draws from.
          {cut ? ` Sorting a column reorders the ${fmtInt(data!.rows.length)} rows shown here, not all ${fmtInt(data!.total)}` +
            (data!.alpha === 0 ? "; at α 0 every sequence is equally likely, so which rows are shown is arbitrary." : ".") : ""}
        </p>
        {data && <DataTable rows={data.rows} columns={columns} rowKey={(r) => r.a_number} initialSort={{ key: "pick_probability", desc: true }} />}
      </div>
    </>
  );
}

// ============================================================================ attempts

interface AttemptRow {
  id: number; session_id: number | null; a_number: string; strategy: string; program_origin: string | null; started_at: string;
  verified: number; known_terms: number | null; known_source: string | null; reproduced: number | null; new_terms: number;
  runtime_s: number | null; cpu_s: number | null; peak_mem_bytes: number | null; cost_unit: string | null;
  projected_next_s_high: number | null; outcome: string; failure_mode: string | null; detail: string | null; artifact_path: string | null;
  win_rejected?: boolean; review_refused?: number | boolean | null;
}
interface AttemptsData {
  rows: AttemptRow[]; total?: number; failure_counts: Record<string, number>; skip_counts: Record<string, number>;
  outcome_counts: Record<string, number>; strategies: string[];
}

const toBars = (counts: Record<string, number>) =>
  Object.entries(counts).map(([k, v]) => ({ key: k || "none", label: (k || "none").replace(/_/g, " "), value: v }))
    .sort((a, b) => b.value - a.value);

export function AttemptsView() {
  const [failure, setFailure] = useState<string | null>(null);
  const [outcome, setOutcome] = useState("");
  const [strategy, setStrategy] = useState("");
  const q = new URLSearchParams({ limit: "1000" });
  if (failure) q.set("failure_mode", failure);
  if (outcome) q.set("outcome", outcome);
  if (strategy) q.set("strategy", strategy);
  const { data, error, loading } = useApi<AttemptsData>(`/api/attempts?${q}`);
  const columns: Column<AttemptRow>[] = [
    { key: "id", label: "#", numeric: true },
    { key: "started_at", label: "Started", render: (r) => fmtTime(r.started_at) },
    { key: "a_number", label: "Sequence", render: (r) => <OeisLink a={r.a_number} /> },
    { key: "strategy", label: "Strategy", render: (r) => <span className="mono">{r.strategy}</span> },
    // an `extended` run whose review was rejected, or that was refused one, keeps its outcome and is not a win:
    // say so here, and say which (tabs.notAWin)
    { key: "outcome", label: "Outcome", render: (r) => { const not = notAWin(r); return not ? <>{r.outcome} <span className="pill rejected" title={not.title}>{not.label}</span></> : r.outcome; } },
    { key: "failure_mode", label: "Stopped because", render: (r) => r.failure_mode?.replace(/_/g, " ") ?? "–" },
    { key: "reproduced", label: "Verified", numeric: true, render: (r) => (r.known_terms ? `${r.reproduced ?? 0}/${r.known_terms}` : "–") },
    { key: "new_terms", label: "New", numeric: true },
    { key: "runtime_s", label: "Runtime", numeric: true, render: (r) => fmtSeconds(r.runtime_s) },
    { key: "peak_mem_bytes", label: "Peak mem", numeric: true, render: (r) => fmtBytes(r.peak_mem_bytes) },
    { key: "detail", label: "Detail", render: (r) => <div className="wrap secondary">{r.detail}</div> },
  ];
  return (
    <>
      <div className="filters">
        <label>Outcome
          <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
            <option value="">All</option>
            {Object.keys(data?.outcome_counts ?? {}).map((o) => <option key={o} value={o}>{o} ({data!.outcome_counts[o]})</option>)}
          </select>
        </label>
        <label>Strategy
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            <option value="">All</option>
            {(data?.strategies ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        {failure && <button className="chip" onClick={() => setFailure(null)}>Stopped because: {failure.replace(/_/g, " ")} ✕</button>}
      </div>
      <Status error={error} loading={loading} hasData={!!data} />
      <div className="grid-2">
        <div className="card">
          <h2>Why runs stopped</h2>
          <p className="caption">All program runs by final stop reason, whatever the filters above say. Timeouts vs memory caps vs wrong terms vs crashes show what to fix next. Select a bar to filter the table.</p>
          <BarList bars={toBars(data?.failure_counts ?? {})} selected={failure} onSelect={(k) => setFailure(k === failure ? null : k)} />
        </div>
        <div className="card">
          <h2>Why sequences were skipped</h2>
          <p className="caption">All sequences never run, by reason (for example no supported program form). Select a bar to filter the table.</p>
          <BarList bars={toBars(data?.skip_counts ?? {})} selected={failure} onSelect={(k) => setFailure(k === failure ? null : k)} />
        </div>
      </div>
      <div className={`card ${loading && data ? "stale" : ""}`} style={{ marginTop: 20 }}>
        <h2>Attempts</h2>
        {data && data.total != null && data.rows.length < data.total && (
          <p className="caption">Showing the latest {fmtInt(data.rows.length)} of {fmtInt(data.total)} that match; the older ones are not loaded.</p>
        )}
        {data && (data.rows.length ? <DataTable rows={data.rows} columns={columns} rowKey={(r) => r.id} initialSort={{ key: "id", desc: true }} />
          : <div className="empty">No attempts match.</div>)}
      </div>
    </>
  );
}

// ============================================================================ review inbox

interface ReviewRow {
  id: number; a_number: string; attempt_id: number; artifact_path: string; first_new_index: number; last_new_index: number;
  status: string; note: string | null; created_at: string; updated_at: string; strategy: string; program_origin: string | null;
  new_terms: number; runtime_s: number | null; known_terms: number; known_source: string; name: string | null; files: string[];
  weak_verification: boolean; rewrites: string[]; below_bound: { bound: string; quote: string; indices: number[] } | null;
}

function FileViewer({ reviewId, name }: { reviewId: number; name: string }) {
  const { data, error } = useApi<string>(`/api/reviews/${reviewId}/files/${encodeURIComponent(name)}`, 3600_000, true);
  if (error) return <p className="error" role="alert">Could not load {name}: {describeError(error)}</p>;
  return <pre className="viewer">{data == null ? "Loading…" : String(data)}</pre>;
}

export function ReviewsView() {
  const { data, error, loading } = useApi<{ rows: ReviewRow[] }>("/api/reviews");
  const [open, setOpen] = useState<{ id: number; name: string } | null>(null);
  const rows = data?.rows ?? [];
  const counts = rows.reduce<Record<string, number>>((acc, r) => ({ ...acc, [r.status]: (acc[r.status] ?? 0) + 1 }), {});
  return (
    <>
      <Status error={error} loading={loading} hasData={!!data} />
      <div className="kpis">
        {["new", "reviewing", "submitted", "rejected"].map((s) => <Tile key={s} label={s[0].toUpperCase() + s.slice(1)} value={fmtInt(counts[s] ?? 0)} />)}
      </div>
      <div className="card">
        <h2>Review inbox</h2>
        <p className="caption">
          Runs that produced new terms, open reviews first. One marked new or reviewing is waiting for a human: read the
          program until you understand it before doing anything with the terms. One marked rejected is not a result, and
          its note says why. The dashboard never submits anything and this page is read-only; change status from the terminal with{" "}
          <span className="mono">oeisbot review set &lt;id&gt; reviewing|submitted|rejected</span>.
        </p>
        {data && rows.length === 0 && <div className="empty">No run has produced new terms yet.</div>}
        {rows.map((r) => (
          <div className={`review ${r.status === "rejected" ? "closed" : ""}`} key={r.id}>
            {/* The same three facts, in the same order, as `oeisbot review list` (cli.review_block): the
                sequence, the addition and where it came from, then the bookkeeping. Keep them in step. */}
            <div className="review-head">
              <span className={`pill ${r.status === "rejected" ? "rejected" : ""}`}>{r.status}</span>
              <OeisLink a={r.a_number} />
              {r.name && <span className="secondary">{r.name}</span>}
              <span className="muted mono">review #{r.id}</span>
            </div>
            <div style={{ marginTop: 4 }}>
              <b>{r.new_terms} new term{r.new_terms === 1 ? "" : "s"}, a({r.first_new_index})..a({r.last_new_index})</b>
              {", from "}{r.program_origin ?? r.strategy}{", attempt #"}{r.attempt_id}
              <span className="secondary">{" · "}{r.strategy} · {fmtSeconds(r.runtime_s)} · {fmtTime(r.created_at)}</span>
            </div>
            {/* the note is where a rejection says why; `oeisbot review list` prints it, and so must this */}
            {r.note && <div className="note"><b>{r.status === "rejected" ? "Rejected: " : "Note: "}</b>{r.note}</div>}
            {r.weak_verification && <div className="warn">Weak verification: only {r.known_terms} known terms to check against.</div>}
            {r.below_bound && <div className="warn">A term lands below a published bound ({r.below_bound.bound}): a({r.below_bound.indices.join("), a(")}).
              The entry says "{r.below_bound.quote}". Either that search or this program is wrong; resolve which before submitting.</div>}
            {r.strategy === "python:model" && <div className="warn">AI-generated program. Do not submit a program you do not fully understand.</div>}
            {/* "the entry's own program" is codegen.ENTRY_PROGRAM_NOTE and "list contract" codegen.MEMBERS_NOTE;
                keep them in step */}
            {r.rewrites.filter((w) => r.strategy !== "python:model" || w.startsWith("fixed bound")
                                      || w.startsWith("the entry's own program") || w.startsWith("list contract")).map((w) => (
              <div className="warn" key={w}>{r.strategy !== "python:model" ? `Program rewritten: ${w}`
                : w.startsWith("fixed bound") ? `Hard-coded ${w}`
                : w.startsWith("list contract") ? `Numbered by the runner (${w}): read executed.py too`
                : `Compare with the entry's program: ${w}`}</div>
            ))}
            <div className="filters" style={{ marginTop: 8, marginBottom: 0 }}>
              {r.files.map((f) => (
                <button key={f} className="chip" aria-pressed={open?.id === r.id && open.name === f}
                        onClick={() => setOpen(open?.id === r.id && open.name === f ? null : { id: r.id, name: f })}>{f}</button>
              ))}
              <span className="muted mono">{r.artifact_path}</span>
            </div>
            {/* keyed by file: a new file starts empty, and never shows the last one's text while it loads */}
            {open?.id === r.id && <FileViewer key={open.name} reviewId={r.id} name={open.name} />}
          </div>
        ))}
      </div>
    </>
  );
}

// ============================================================================ run history

interface HistoryDay { day: string; attempts: number; wins: number; rejected_wins?: number; skipped: number; machine_hours: number }
interface HistoryData {
  days: HistoryDay[];
  sessions: { id: number; started_at: string; finished_at: string | null; attempts: number; wins: number; rejected_wins?: number;
              machine_s: number; note: string | null }[];
  sessions_total?: number;
}

export function HistoryView() {
  const { data, error, loading } = useApi<HistoryData>("/api/history");
  const days = data?.days ?? [];
  const totalHours = days.reduce((s, d) => s + d.machine_hours, 0);
  const totalWins = days.reduce((s, d) => s + d.wins, 0);
  const totalRejected = days.reduce((s, d) => s + (d.rejected_wins ?? 0), 0);
  const totalAttempts = days.reduce((s, d) => s + d.attempts, 0);
  // One column per calendar day from the first run to the last (scale.dayColumns): a day without runs is an
  // empty slot and a long quiet stretch one marker, so that neighbouring columns are neighbouring days. The year
  // is in the label only when the chart spans more than one.
  const years = new Set(days.map((d) => d.day.slice(0, 4))).size;
  const label = (d: string) => (years > 1 ? d : d.slice(5));
  const columns = <V,>(values: (d: HistoryDay) => V, none: V) => dayColumns(days.map((d) => d.day)).map((c) =>
    c.kind === "gap"
      ? { key: `gap-${c.from}`, label: "…", values: none, gap: `${c.days} days without runs, ${c.from} to ${c.to}` }
      : { key: c.day, label: label(c.day), values: c.index == null ? none : values(days[c.index]), empty: c.index == null });
  return (
    <>
      <Status error={error} loading={loading} hasData={!!data} />
      <div className="kpis">
        <Tile label="Machine hours" value={totalHours.toFixed(1)} />
        <Tile label="Program runs" value={fmtInt(totalAttempts)} />
        <Tile label="Wins" value={fmtInt(totalWins)}
              sub={[totalAttempts ? `${fmtPct(totalWins / totalAttempts, 1)} of runs` : null,
                    totalRejected ? `${fmtInt(totalRejected)} more rejected in review` : null].filter(Boolean).join(" · ") || undefined} />
        <Tile label="Hours per win" value={totalWins ? (totalHours / totalWins).toFixed(1) : "–"} />
      </div>
      <div className="grid-2">
        <div className="card">
          <h2>Runs and wins per day</h2>
          <p className="caption">
            A win is a run whose new terms were verified, survived the live re-check, and were not rejected in review.
            Days are UTC days, so an evening run can fall on the next day's column.
          </p>
          <StackedColumns data={columns((d) => ({ other: d.attempts - d.wins - (d.rejected_wins ?? 0), rejected: d.rejected_wins ?? 0, wins: d.wins }),
                                        { other: 0, rejected: 0, wins: 0 })}
                          series={[{ key: "other", label: "Other runs", color: "var(--deemph)" },
                                   ...(totalRejected ? [{ key: "rejected", label: "Rejected in review", color: "var(--series-2)" }] : []),
                                   { key: "wins", label: "Wins", color: "var(--series-1)" }]} />
        </div>
        <div className="card">
          <h2>Machine hours per day</h2>
          <p className="caption">Wall-clock time spent inside the sandbox, by UTC day.</p>
          <StackedColumns data={columns((d) => ({ hours: d.machine_hours }), { hours: 0 })}
                          series={[{ key: "hours", label: "Machine hours", color: "var(--series-1)" }]}
                          format={(v) => (v < 10 ? v.toFixed(1) : v.toFixed(0))} />
        </div>
      </div>
      <div className="card" style={{ marginTop: 20 }}>
        <h2>Sessions</h2>
        <p className="caption">
          Wins are counted from each session's runs as they stand now, so a win rejected in review since is not in the count.
          {data && data.sessions_total != null && data.sessions.length < data.sessions_total
            ? ` Showing the latest ${fmtInt(data.sessions.length)} of ${fmtInt(data.sessions_total)} sessions.` : ""}
        </p>
        {data && (
          <DataTable rows={data.sessions} rowKey={(r) => r.id} initialSort={{ key: "id", desc: true }} columns={[
            { key: "id", label: "#", numeric: true },
            { key: "started_at", label: "Started", render: (r) => fmtTime(r.started_at) },
            { key: "finished_at", label: "Finished", render: (r) => (r.finished_at ? fmtTime(r.finished_at) : "running") },
            { key: "attempts", label: "Attempts", numeric: true },
            { key: "wins", label: "Wins", numeric: true,
              render: (r) => (r.rejected_wins ? <>{r.wins} <span className="muted">({r.rejected_wins} rejected)</span></> : r.wins) },
            { key: "machine_s", label: "Machine time", numeric: true, render: (r) => fmtSeconds(r.machine_s) },
            { key: "note", label: "Settings", render: (r) => <span className="mono secondary">{r.note}</span> },
          ]} />
        )}
      </div>
    </>
  );
}
