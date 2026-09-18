import { useState } from "react";
import { BarList, LegendDot, LogScatter, StackedColumns, type ScatterPoint } from "./charts";
import {
  DataTable, OeisLink, Tile, fmtBytes, fmtInt, fmtPct, fmtSeconds, fmtTime, useApi, type Column,
} from "./lib";

function Status({ error, loading, hasData }: { error: string | null; loading: boolean; hasData: boolean }) {
  if (error) return <p className="error">Could not load: {error}</p>;
  if (loading && !hasData) return <p className="muted">Loading…</p>;
  return null;
}

// ============================================================================ estimator accuracy

interface PredictionPoint {
  id: number; attempt_id: number; a_number: string; strategy: string; n: number; cost_unit: string;
  model: string | null; trustworthy: number; feasible: number; value_dependent: number;
  predicted_s: number; predicted_s_low: number | null; predicted_s_high: number | null;
  actual_s: number | null; censored_s: number | null; started_at: string;
}
interface EstimatorData {
  points: PredictionPoint[];
  stats: { finished: number; censored: number; within_2x: number | null; median_ratio: number | null;
           mean_abs_log10_error: number | null; in_reported_range_2x: number | null; underestimated_censored: number };
}

export function EstimatorView() {
  const { data, error, loading } = useApi<EstimatorData>("/api/estimator");
  const [unit, setUnit] = useState("all");
  const [trusted, setTrusted] = useState(false);
  const [table, setTable] = useState(false);
  const pts = (data?.points ?? []).filter((p) => (unit === "all" || p.cost_unit === unit) && (!trusted || p.trustworthy));
  const scatter: ScatterPoint[] = pts.map((p) => {
    const hollow = p.actual_s == null;
    const y = (hollow ? p.censored_s : p.actual_s) ?? p.predicted_s;
    return {
      id: p.id, x: p.predicted_s, y: Math.max(y, 1e-6), series: p.cost_unit === "work" ? 0 : 1, hollow,
      title: `${p.a_number} a(${p.n}) · ${p.strategy}`,
      rows: [
        { label: hollow ? "stopped after" : "actual", value: fmtSeconds(y) },
        { label: "predicted", value: fmtSeconds(p.predicted_s) },
        { label: "predicted range", value: `${fmtSeconds(p.predicted_s_low)} – ${fmtSeconds(p.predicted_s_high)}` },
        { label: "actual / predicted", value: hollow ? `≥ ${(y / p.predicted_s).toPrecision(2)}` : (y / p.predicted_s).toPrecision(2) },
        { label: "model", value: `${p.model ?? "none"}${p.trustworthy ? "" : " (untrusted)"}` },
      ],
    };
  });
  const s = data?.stats;
  const columns: Column<PredictionPoint>[] = [
    { key: "a_number", label: "Sequence", render: (r) => <OeisLink a={r.a_number} /> },
    { key: "n", label: "n", numeric: true },
    { key: "cost_unit", label: "Unit" },
    { key: "model", label: "Model", render: (r) => r.model ?? "–" },
    { key: "predicted_s", label: "Predicted", numeric: true, render: (r) => fmtSeconds(r.predicted_s) },
    { key: "actual_s", label: "Actual", numeric: true, render: (r) => r.actual_s != null ? fmtSeconds(r.actual_s) : `≥ ${fmtSeconds(r.censored_s)}` },
    { key: "ratio", label: "Actual / predicted", numeric: true,
      sortValue: (r) => (r.actual_s ?? r.censored_s ?? 0) / r.predicted_s,
      render: (r) => `${r.actual_s == null ? "≥ " : ""}${((r.actual_s ?? r.censored_s ?? 0) / r.predicted_s).toPrecision(2)}` },
    { key: "trustworthy", label: "Trusted", render: (r) => (r.trustworthy ? "yes" : "no") },
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
        <label><input type="checkbox" checked={trusted} onChange={(e) => setTrusted(e.target.checked)} /> Trusted projections only</label>
        <button className="chip" onClick={() => setTable(!table)}>{table ? "Show chart" : "Show table"}</button>
      </div>
      <div className="kpis">
        <Tile label="Terms predicted and finished" value={fmtInt(s?.finished)} sub={`${fmtInt(s?.censored)} stopped before finishing`} />
        <Tile label="Within 2× of prediction" value={fmtPct(s?.within_2x)} sub="finished terms" />
        <Tile label="Median actual / predicted" value={s?.median_ratio != null ? s.median_ratio.toPrecision(2) : "–"} sub="above 1 means underestimates" />
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
        {pts.length === 0 ? (
          <div className="empty">No projected terms have run yet. Points appear once a verified program starts computing new terms.</div>
        ) : table ? (
          <DataTable rows={pts} columns={columns} rowKey={(r) => r.id} initialSort={{ key: "ratio", desc: true }} />
        ) : (
          <>
            <div className="legend">
              <LegendDot color="var(--series-1)">Work counts (instrumented)</LegendDot>
              <LegendDot color="var(--series-2)">CPU time (uninstrumented)</LegendDot>
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

export function QueueView() {
  const [alpha, setAlpha] = useState(1);
  const [pariOnly, setPariOnly] = useState(true);
  const { data, error, loading } = useApi<{ total: number; rows: QueueRow[] }>(
    `/api/queue?alpha=${alpha}&pari_only=${pariOnly}&limit=2000`, 60000);
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
          <input type="number" min={0} max={6} step={0.25} value={alpha} onChange={(e) => setAlpha(Number(e.target.value) || 0)} />
        </label>
        <label><input type="checkbox" checked={pariOnly} onChange={(e) => setPariOnly(e.target.checked)} /> Only sequences with a PARI program</label>
        <span className="muted">{data ? `${fmtInt(data.total)} candidates; showing the ${fmtInt(data.rows.length)} most likely picks` : ""}</span>
      </div>
      <Status error={error} loading={loading} hasData={!!data} />
      <div className={`card ${loading && data ? "stale" : ""}`}>
        <h2>Candidate queue</h2>
        <p className="caption">Pick chance is proportional to 1 / difficulty^α. Sort by any column to sanity-check the weighting.</p>
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
}
interface AttemptsData {
  rows: AttemptRow[]; failure_counts: Record<string, number>; skip_counts: Record<string, number>;
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
    { key: "outcome", label: "Outcome" },
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
          <p className="caption">Program runs by final stop reason. Timeouts vs memory caps vs wrong terms vs crashes show what to fix next. Select a bar to filter.</p>
          <BarList bars={toBars(data?.failure_counts ?? {})} selected={failure} onSelect={(k) => setFailure(k === failure ? null : k)} />
        </div>
        <div className="card">
          <h2>Why sequences were skipped</h2>
          <p className="caption">Sequences never run, by reason (for example no supported program form).</p>
          <BarList bars={toBars(data?.skip_counts ?? {})} selected={failure} onSelect={(k) => setFailure(k === failure ? null : k)} />
        </div>
      </div>
      <div className={`card ${loading && data ? "stale" : ""}`} style={{ marginTop: 20 }}>
        <h2>Attempts</h2>
        {data && (data.rows.length ? <DataTable rows={data.rows} columns={columns} rowKey={(r) => r.id} initialSort={{ key: "id", desc: true }} />
          : <div className="empty">No attempts match.</div>)}
      </div>
    </>
  );
}

// ============================================================================ review inbox

interface ReviewRow {
  id: number; a_number: string; attempt_id: number; artifact_path: string; first_new_index: number; last_new_index: number;
  status: string; note: string | null; created_at: string; updated_at: string; strategy: string; new_terms: number;
  runtime_s: number | null; known_terms: number; known_source: string; name: string | null; files: string[];
  weak_verification: boolean; rewrites: string[];
}

function FileViewer({ reviewId, name }: { reviewId: number; name: string }) {
  const { data, error } = useApi<string>(`/api/reviews/${reviewId}/files/${encodeURIComponent(name)}`, 3600_000, true);
  if (error) return <p className="error">{error}</p>;
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
          Successes waiting for a human. Nothing here has been submitted. Read the program until you understand it before
          doing anything with the terms. This page is read-only; change status from the terminal with{" "}
          <span className="mono">oeisbot review set &lt;id&gt; reviewing|submitted|rejected</span>.
        </p>
        {rows.length === 0 && <div className="empty">No successes yet.</div>}
        {rows.map((r) => (
          <div className="review" key={r.id}>
            <div className="review-head">
              <span className="pill">{r.status}</span>
              <OeisLink a={r.a_number} />
              <b>a({r.first_new_index})..a({r.last_new_index})</b>
              <span className="secondary">{r.new_terms} new · {r.strategy} · {fmtSeconds(r.runtime_s)} · {fmtTime(r.created_at)}</span>
              <span className="muted mono">review #{r.id}</span>
            </div>
            {r.name && <div className="secondary" style={{ marginTop: 4 }}>{r.name}</div>}
            {r.weak_verification && <div className="warn">Weak verification: only {r.known_terms} known terms to check against.</div>}
            {r.strategy === "python:model" && <div className="warn">AI-generated program. Do not submit a program you do not fully understand.</div>}
            {r.rewrites.filter((w) => r.strategy !== "python:model" || w.startsWith("fixed bound")).map((w) => (
              <div className="warn" key={w}>{r.strategy === "python:model" ? `Hard-coded ${w}` : `Program rewritten: ${w}`}</div>
            ))}
            <div className="filters" style={{ marginTop: 8, marginBottom: 0 }}>
              {r.files.map((f) => (
                <button key={f} className="chip" aria-pressed={open?.id === r.id && open.name === f}
                        onClick={() => setOpen(open?.id === r.id && open.name === f ? null : { id: r.id, name: f })}>{f}</button>
              ))}
              <span className="muted mono">{r.artifact_path}</span>
            </div>
            {open?.id === r.id && <FileViewer reviewId={r.id} name={open.name} />}
          </div>
        ))}
      </div>
    </>
  );
}

// ============================================================================ run history

interface HistoryData {
  days: { day: string; attempts: number; wins: number; skipped: number; machine_hours: number }[];
  sessions: { id: number; started_at: string; finished_at: string | null; attempts: number; wins: number; machine_s: number; note: string | null }[];
}

export function HistoryView() {
  const { data, error, loading } = useApi<HistoryData>("/api/history");
  const days = data?.days ?? [];
  const totalHours = days.reduce((s, d) => s + d.machine_hours, 0);
  const totalWins = days.reduce((s, d) => s + d.wins, 0);
  const totalAttempts = days.reduce((s, d) => s + d.attempts, 0);
  const label = (d: string) => d.slice(5);
  return (
    <>
      <Status error={error} loading={loading} hasData={!!data} />
      <div className="kpis">
        <Tile label="Machine hours" value={totalHours.toFixed(1)} />
        <Tile label="Program runs" value={fmtInt(totalAttempts)} />
        <Tile label="Wins" value={fmtInt(totalWins)} sub={totalAttempts ? `${fmtPct(totalWins / totalAttempts, 1)} of runs` : undefined} />
        <Tile label="Hours per win" value={totalWins ? (totalHours / totalWins).toFixed(1) : "–"} />
      </div>
      <div className="grid-2">
        <div className="card">
          <h2>Runs and wins per day</h2>
          <p className="caption">Wins are runs that produced verified new terms that survived the live re-check.</p>
          <StackedColumns data={days.map((d) => ({ label: label(d.day), values: { other: d.attempts - d.wins, wins: d.wins } }))}
                          series={[{ key: "other", label: "Runs without new terms", color: "var(--deemph)" },
                                   { key: "wins", label: "Wins", color: "var(--series-1)" }]} />
        </div>
        <div className="card">
          <h2>Machine hours per day</h2>
          <p className="caption">Wall-clock time spent inside the sandbox.</p>
          <StackedColumns data={days.map((d) => ({ label: label(d.day), values: { hours: d.machine_hours } }))}
                          series={[{ key: "hours", label: "Machine hours", color: "var(--series-1)" }]}
                          format={(v) => (v < 10 ? v.toFixed(1) : v.toFixed(0))} />
        </div>
      </div>
      <div className="card" style={{ marginTop: 20 }}>
        <h2>Sessions</h2>
        {data && (
          <DataTable rows={data.sessions} rowKey={(r) => r.id} initialSort={{ key: "id", desc: true }} columns={[
            { key: "id", label: "#", numeric: true },
            { key: "started_at", label: "Started", render: (r) => fmtTime(r.started_at) },
            { key: "finished_at", label: "Finished", render: (r) => (r.finished_at ? fmtTime(r.finished_at) : "running") },
            { key: "attempts", label: "Attempts", numeric: true },
            { key: "wins", label: "Wins", numeric: true },
            { key: "machine_s", label: "Machine time", numeric: true, render: (r) => fmtSeconds(r.machine_s) },
            { key: "note", label: "Settings", render: (r) => <span className="mono secondary">{r.note}</span> },
          ]} />
        )}
      </div>
    </>
  );
}
