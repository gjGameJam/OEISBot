import { memo, useEffect, useMemo, useState, type MouseEvent } from "react";
import { Tooltip, type TipRow, type TipState } from "./charts";
import { DataTable, OeisLink, Tile, fmtInt, fmtTime, useApi, useWidth, type Column } from "./lib";
import {
  BIN_LABELS, CHANGE_BINS, LUMP, MAX_ALPHA, NEUTRAL_BIN, changeBin, fmtChange, labelFits, layoutGroups, parseAlpha,
  pickmapPath, type Leaf, type PlacedGroup, type Rect,
} from "./treemap";

// ============================================================================ pick map

type Pool = "pari" | "model";

interface PmRow { a: string; d: number; band: number; p: number; p0: number | null; ratio: number | null; new: boolean; name: string }
interface PmBand { band: number; label: string; n: number; share: number }
interface PmData {
  pool: Pool; alpha: number; n: number; bands: PmBand[]; built_at: string; age_s: number; note: string;
  running_session: { id: number; started_at: string } | null; snapshots: number;
  baseline: { id: number; taken_at: string; n: number; session_id: number | null; budgets_differ: boolean; rules_differ: boolean | null } | null;
  entered: { n: number; share: number };
  gone: { n: number; share: number; reasons: { reason: string; n: number; share: number }[];
          top: { a: string; p0: number; name: string; reason: string }[] };
  rows: PmRow[];
}

const BAND_PREFIX = "b";
const bandKey = (band: number) => `${BAND_PREFIX}${band}`;
const bandOfKey = (key: string) => Number(key.slice(BAND_PREFIX.length));

/** Tiles in these classes are drawn on their own however small; the rest of the small ones share a lump. */
const NOTABLE = new Set([0, 1, 5, 6]);
/** Class of a row: -1 for "new in the pool" (nothing to compare), else 0..6. */
const NEW = -1;

function binOf(r: PmRow, compared: boolean): number {
  if (!compared) return NEUTRAL_BIN;
  if (r.new) return NEW;
  return r.ratio == null ? NEUTRAL_BIN : changeBin(r.ratio);
}

function fmtShare(p: number): string {
  const pct = p * 100;
  if (pct === 0) return "0%";
  if (pct >= 10) return `${pct.toFixed(0)}%`;
  if (pct >= 1) return `${pct.toFixed(1)}%`;
  return `${pct.toPrecision(2)}%`;
}

function ago(seconds: number): string {
  if (seconds < 90) return "moments ago";
  if (seconds < 5400) return `${Math.round(seconds / 60)} min ago`;
  return `${(seconds / 3600).toFixed(1)} h ago`;
}

interface Look { bin: number; p: number; p0: number | null; ratio: number | null }

function lookOf(id: string, members: string[] | null, byId: Map<string, PmRow>, compared: boolean): Look {
  if (!members) {
    const r = byId.get(id)!;
    return { bin: binOf(r, compared), p: r.p, p0: r.p0, ratio: r.ratio };
  }
  // a lump is coloured by what its members hold between them, over the part of them that was compared
  let p = 0, p0 = 0, pCompared = 0;
  for (const m of members) {
    const r = byId.get(m)!;
    p += r.p;
    if (r.p0 != null) { p0 += r.p0; pCompared += r.p; }
  }
  const ratio = compared && p0 > 0 ? pCompared / p0 : null;
  return { bin: compared && ratio != null ? changeBin(ratio) : NEUTRAL_BIN, p, p0: compared && p0 > 0 ? p0 : null, ratio };
}

function clip(text: string, width: number): string {
  const max = Math.floor((width - 8) / 6.4);
  return text.length <= max ? text : max > 1 ? text.slice(0, max - 1) + "…" : "";
}

interface TilesProps { layout: PlacedGroup[]; byId: Map<string, PmRow>; labels: Map<string, string>; compared: boolean; headers: boolean }

/** The drawing itself. Memoised: a mouse move updates only the tooltip, never these thousands of rects. */
const Tiles = memo(function Tiles({ layout, byId, labels, compared, headers }: TilesProps) {
  return (
    <g>
      {layout.map((g) => (
        <g key={g.key}>
          {headers && <rect className="pm-frame" x={g.rect.x + 0.5} y={g.rect.y + 0.5} width={Math.max(g.rect.w - 1, 0)} height={Math.max(g.rect.h - 1, 0)} />}
          {headers && g.header && (
            <text className="pm-head" data-band={g.key} x={g.rect.x + 6} y={g.rect.y + 13}>{clip(labels.get(g.key) ?? g.key, g.rect.w - 4)}</text>
          )}
          {g.leaves.map((l) => {
            const look = lookOf(l.id, l.members, byId, compared);
            const r = l.rect;
            const inset = Math.min(1, Math.min(r.w, r.h) / 4);
            const hatched = look.bin === NEW;
            const text = look.bin === NEW ? "new" : compared ? fmtChange(look.ratio ?? 1) : fmtShare(look.p);
            const first = l.members ? `${fmtInt(l.members.length)} small` : l.id;
            const lines = labelFits(r, Math.max(first.length, text.length), 2) ? 2 : labelFits(r, first.length) ? 1 : 0;
            return (
              <g key={l.id}>
                <rect className={l.members ? (headers ? "pm-tile lump" : "pm-tile lump flat") : "pm-tile"} data-id={l.id} x={r.x + inset} y={r.y + inset} width={Math.max(r.w - 2 * inset, 0)}
                      height={Math.max(r.h - 2 * inset, 0)} rx={1.5}
                      fill={hatched ? "url(#pm-new)" : `var(--chg-${look.bin})`} />
                {lines > 0 && (
                  <text className={`pm-label ${hatched ? "hatched" : ""}`} x={r.x + 5} y={r.y + 14}
                        style={hatched ? undefined : { fill: `var(--chg-ink-${look.bin})` }}>
                    <tspan className={l.members ? undefined : "mono"} style={{ fontSize: 11 }}>{first}</tspan>
                    {lines === 2 && <tspan x={r.x + 5} dy={14} fillOpacity={0.85}>{text}</tspan>}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      ))}
    </g>
  );
});

function Canvas({ layout, rows, byId, bands, compared, headers, width, height, baselineId, onBand }: {
  layout: PlacedGroup[]; rows: PmRow[]; byId: Map<string, PmRow>; bands: PmBand[]; compared: boolean; headers: boolean;
  width: number; height: number; baselineId: number | null; onBand: (band: number) => void;
}) {
  const [tip, setTip] = useState<TipState | null>(null);
  const members = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const g of layout) for (const l of g.leaves) if (l.members) m.set(l.id, l.members);
    return m;
  }, [layout]);
  const labels = useMemo(() => new Map(bands.map((b) => [bandKey(b.band), `${b.label} · ${fmtInt(b.n)} · ${fmtShare(b.share)}`])), [bands]);
  const bandLabel = (band: number) => bands.find((b) => b.band === band)?.label ?? String(band);

  const tipFor = (id: string, x: number, y: number): TipState => {
    const lump = members.get(id) ?? null;
    const look = lookOf(id, lump, byId, compared);
    const rowsOut: TipRow[] = [{ label: "Chance of being picked first", value: fmtShare(look.p) }];
    if (compared) {
      if (look.bin === NEW) rowsOut.push({ label: `Change since #${baselineId}`, value: "new in the pool" });
      else if (look.ratio != null) {
        rowsOut.push({ label: "Chance before (rescaled)", value: fmtShare(look.p0 ?? 0) });
        rowsOut.push({ label: `Change since #${baselineId}`, value: fmtChange(look.ratio) });
      }
    }
    if (lump) {
      const band = bandOfKey(id.slice(LUMP.length));
      rowsOut.push({ label: "Difficulty band", value: bandLabel(band) });
      if (headers) rowsOut.push({ label: "Click", value: "to open this band" });
      return { x, y, title: `${fmtInt(lump.length)} small tiles`, rows: rowsOut };
    }
    const r = byId.get(id)!;
    rowsOut.push({ label: "Difficulty", value: r.d.toFixed(3) });
    rowsOut.push({ label: "Band", value: bandLabel(r.band) });
    return { x, y, title: `${r.a} ${r.name}`, rows: rowsOut };
  };

  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    const id = (e.target as Element).closest?.("[data-id]")?.getAttribute("data-id");
    setTip(id ? tipFor(id, e.clientX, e.clientY) : null);
  };
  const onClick = (e: MouseEvent<SVGSVGElement>) => {
    const target = (e.target as Element).closest?.("[data-id],[data-band]");
    if (!target) return;
    const id = target.getAttribute("data-id");
    const key = target.getAttribute("data-band");
    if (key) onBand(bandOfKey(key));
    else if (id?.startsWith(LUMP)) { if (headers) onBand(bandOfKey(id.slice(LUMP.length))); }
    else if (id) window.open(`https://oeis.org/${id}`, "_blank", "noopener,noreferrer");
  };

  return (
    <>
      <svg width={width} height={height} role="img" onMouseMove={onMove} onMouseLeave={() => setTip(null)} onClick={onClick}
           aria-label={`Treemap of ${fmtInt(rows.length)} sequences; area is pick chance, colour is the change since the earlier snapshot. The table view below has the same data.`}>
        <defs>
          <pattern id="pm-new" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="7" height="7" style={{ fill: "var(--chg-3)" }} />
            <line x1="0" y1="0" x2="0" y2="7" style={{ stroke: "var(--text-muted)", strokeWidth: 2 }} />
          </pattern>
        </defs>
        <Tiles layout={layout} byId={byId} labels={labels} compared={compared} headers={headers} />
      </svg>
      <Tooltip tip={tip} />
    </>
  );
}

function Legend({ compared, baselineId }: { compared: boolean; baselineId: number | null }) {
  if (!compared) {
    return <div className="pm-legend"><span>No earlier snapshot to compare with, so every tile is gray; area is still the pick chance.</span></div>;
  }
  return (
    <div className="pm-legend" role="group" aria-label="Colour legend">
      <span className="secondary">Change since snapshot #{baselineId}:</span>
      {Array.from({ length: CHANGE_BINS }, (_, i) => (
        <span key={i}><svg width="14" height="14"><rect width="14" height="14" style={{ fill: `var(--chg-${i})` }} /></svg>{BIN_LABELS[i]}</span>
      ))}
      <span><svg width="14" height="14"><rect width="14" height="14" fill="url(#pm-new)" /></svg>new in the pool</span>
    </div>
  );
}

function TableTwin({ rows, compared, bands }: { rows: PmRow[]; compared: boolean; bands: PmBand[] }) {
  const [open, setOpen] = useState(false);
  const bandLabel = (band: number) => bands.find((b) => b.band === band)?.label ?? String(band);
  const columns: Column<PmRow>[] = [
    { key: "a", label: "Sequence", render: (r) => <OeisLink a={r.a} /> },
    { key: "name", label: "Name", render: (r) => <div className="wrap">{r.name}</div> },
    { key: "d", label: "Difficulty", numeric: true, render: (r) => r.d.toFixed(3) },
    { key: "band", label: "Band", render: (r) => bandLabel(r.band), sortValue: (r) => r.band },
    { key: "p", label: "Pick chance", numeric: true, render: (r) => fmtShare(r.p) },
    ...(compared ? [
      { key: "p0", label: "Before (rescaled)", numeric: true, render: (r: PmRow) => (r.p0 == null ? <span className="muted">–</span> : fmtShare(r.p0)) },
      { key: "ratio", label: "Change", numeric: true,
        render: (r: PmRow) => (r.new ? "new" : r.ratio == null ? <span className="muted">–</span> : fmtChange(r.ratio)),
        sortValue: (r: PmRow) => (r.new ? Infinity : r.ratio) },
    ] : []),
  ];
  return (
    <details className="twin" onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary>Table view ({fmtInt(rows.length)} sequences)</summary>
      {open && <DataTable rows={rows} columns={columns} rowKey={(r) => r.a} initialSort={{ key: "p", desc: true }} />}
    </details>
  );
}

export function PickMapView() {
  const [pool, setPool] = useState<Pool>("pari");
  const [alphaText, setAlphaText] = useState("1");
  const [alpha, setAlpha] = useState(1);
  const [rebuilds, setRebuilds] = useState(0);
  const [band, setBand] = useState<number | null>(null);
  const [wrapRef, width] = useWidth<HTMLDivElement>();
  const typed = parseAlpha(alphaText);

  useEffect(() => {
    if (typed == null || typed === alpha) return;
    const t = window.setTimeout(() => { setAlpha(typed); setRebuilds(0); }, 500);
    return () => window.clearTimeout(t);
  }, [typed, alpha]);

  // A rebuild is asked for once: the first request carries the flag, every later one (the hourly refresh) does not,
  // and choosing another pool or alpha drops it.
  const pickPool = (p: Pool) => { setPool(p); setBand(null); setRebuilds(0); };
  const { data, error, loading } = useApi<PmData>(pickmapPath(pool, alpha, rebuilds), 3600000, false, pickmapPath(pool, alpha));
  const shown = data && data.pool === pool ? data : null;
  const stale = loading || (shown != null && shown.alpha !== alpha);

  const derived = useMemo(() => {
    if (!shown) return null;
    const compared = shown.baseline != null;
    const byId = new Map(shown.rows.map((r) => [r.a, r]));
    const byBand = new Map<number, PmRow[]>();
    let changed = 0, changedShare = 0;
    for (const r of shown.rows) {
      const list = byBand.get(r.band);
      if (list) list.push(r); else byBand.set(r.band, [r]);
      if (compared && !r.new && NOTABLE.has(binOf(r, true))) { changed++; changedShare += r.p; }
    }
    return { compared, byId, byBand, changed, changedShare };
  }, [shown]);

  const activeBand = shown && band != null && shown.bands.some((b) => b.band === band) ? band : null;
  const rows = shown && derived ? (activeBand == null ? shown.rows : derived.byBand.get(activeBand) ?? []) : [];
  const height = Math.round(Math.min(680, Math.max(380, width * 0.55)));

  const layout = useMemo(() => {
    if (!shown || !derived) return [];
    const compared = derived.compared;
    const leaf = (r: PmRow): Leaf => ({ id: r.a, value: r.p, keep: NOTABLE.has(binOf(r, compared)) || binOf(r, compared) === NEW });
    const groups = activeBand == null
      ? shown.bands.map((b) => ({ key: bandKey(b.band), leaves: (derived.byBand.get(b.band) ?? []).map(leaf) }))
      : [{ key: bandKey(activeBand), leaves: (derived.byBand.get(activeBand) ?? []).map(leaf) }];
    const box: Rect = { x: 0, y: 0, w: Math.max(width, 200), h: height };
    return layoutGroups(groups, box, { headerH: activeBand == null ? 18 : 0, minLeafArea: Math.max(36, (box.w * box.h) / 9000), pad: 2 });
  }, [shown, derived, activeBand, width, height]);

  const notes: string[] = [];
  if (shown) {
    if (shown.snapshots === 0) notes.push(`No snapshot of the ${pool} pool is stored yet. Run \`oeisbot snapshot\` (every \`oeisbot run\` stores one too); until then there is nothing to compare with.`);
    else if (!shown.baseline) notes.push("Every stored snapshot is identical to the live pool, so there is no change to show yet.");
    if (shown.baseline?.budgets_differ) notes.push("The baseline was taken under other time budgets than the live pool, so part of the change comes from that and not from what happened.");
    if (shown.baseline?.rules_differ === true) notes.push("The selection rules (the code that scores candidates) changed since the baseline, so part of the change comes from the code.");
    if (shown.baseline && shown.baseline.rules_differ === null) notes.push("The selection rules could not be compared with the baseline's (it recorded none, or this server could not read its own source files), so a change in them cannot be ruled out.");
    if (shown.running_session) notes.push(`Session ${shown.running_session.id} (started ${fmtTime(shown.running_session.started_at)}) has not finished; the map shows the attempts it has recorded so far.`);
  }

  const base = shown?.baseline ?? null;
  return (
    <>
      <div className="filters">
        <span role="group" aria-label="Pool" style={{ display: "inline-flex", gap: 6 }}>
          <button className="chip" aria-pressed={pool === "pari"} onClick={() => pickPool("pari")}>PARI pool</button>
          <button className="chip" aria-pressed={pool === "model"} onClick={() => pickPool("model")}>Model pool</button>
        </span>
        <label>α
          <input type="number" min={0} max={MAX_ALPHA} step={0.25} value={alphaText} onChange={(e) => setAlphaText(e.target.value)}
                 aria-invalid={typed == null} aria-describedby={typed == null ? "pm-alpha-error" : undefined} />
        </label>
        <button className="chip" disabled={loading} onClick={() => setRebuilds((n) => n + 1)}>{loading ? "Building…" : "Rebuild now"}</button>
        <span className="muted">{shown ? `pool built ${ago(shown.age_s)}${shown.note ? ` · ${shown.note}` : ""}` : ""}</span>
      </div>
      {typed == null && (
        <p id="pm-alpha-error" className="error" role="alert">
          α must be a number from 0 to {MAX_ALPHA}; the map still shows α {alpha}.
        </p>
      )}
      {error && <p className="error">Could not load: {error}</p>}
      {!shown && loading && !error && <p className="muted">Building the {pool === "model" ? "model" : "PARI"} pool{pool === "model" ? " (about 27,000 sequences, this can take half a minute)" : ""}…</p>}
      {shown && derived && (
        <>
          <div className="kpis">
            <Tile label="Candidates" value={fmtInt(shown.n)} sub={`${pool === "pari" ? "PARI" : "model"} pool, α ${shown.alpha}`} />
            <Tile label="Compared with" value={base ? `#${base.id}` : "–"}
                  sub={base ? `${fmtTime(base.taken_at)}${base.session_id ? ` · session ${base.session_id}` : ""} · ${fmtInt(base.n)} candidates` : "no earlier snapshot"} />
            <Tile label="Moved 10% or more" value={base ? fmtInt(derived.changed) : "–"} sub={base ? `holding ${fmtShare(derived.changedShare)} of the picks` : undefined} />
            <Tile label="In / out of the pool" value={base ? `${fmtInt(shown.entered.n)} / ${fmtInt(shown.gone.n)}` : "–"}
                  sub={base ? `in: ${fmtShare(shown.entered.share)} of the picks now; out: ${fmtShare(shown.gone.share)} of the picks then` : undefined} />
          </div>
          {notes.length > 0 && <ul className="notes">{notes.map((n) => <li key={n}>{n}</li>)}</ul>}
          <div className={`card ${stale ? "stale" : ""}`} aria-busy={stale}>
            <h2>Pick map</h2>
            <p className="caption">
              Each tile is one sequence and its area is its chance of being the first pick of the next session, so a large tile is
              a likely one. Colour is how that chance has moved since the earlier snapshot, measured against the sequences that were in both
              pools: when a few sequences leave or fail, the rest do not all drift together. The &ldquo;before&rdquo; chance in a tooltip or
              the table is scaled the same way (the sequences in both pools hold the same total of it as they do now), so before and now
              divide into the change shown. Click a tile to open the entry on oeis.org.
            </p>
            {shown.n === 0 ? (
              <p className="muted">The {pool === "model" ? "model" : "PARI"} pool is empty: no sequence is a candidate for it right now.</p>
            ) : (
              <>
                <div className="subtabs" role="tablist" aria-label="Difficulty band">
                  <button className="chip" role="tab" aria-selected={activeBand == null} onClick={() => setBand(null)}>All bands</button>
                  {shown.bands.map((b) => (
                    <button key={b.band} className="chip" role="tab" aria-selected={activeBand === b.band} onClick={() => setBand(b.band)}
                            title={`${fmtInt(b.n)} sequences holding ${fmtShare(b.share)} of the picks`}>
                      {b.label}{" "}<span className="muted">{fmtInt(b.n)} · {fmtShare(b.share)}</span>
                    </button>
                  ))}
                </div>
                <div className="chart pm-wrap" ref={wrapRef}>
                  <Canvas layout={layout} rows={rows} byId={derived.byId} bands={shown.bands} compared={derived.compared}
                          headers={activeBand == null} width={Math.max(width, 200)} height={height}
                          baselineId={base?.id ?? null} onBand={setBand} />
                </div>
                <Legend compared={derived.compared} baselineId={base?.id ?? null} />
                <TableTwin key={activeBand ?? "all"} rows={rows} compared={derived.compared} bands={shown.bands} />
              </>
            )}
          </div>
          {base && shown.gone.n > 0 && (
            <div className="card">
              <h2>Left the pool since #{base.id}</h2>
              <p className="caption">
                {fmtInt(shown.gone.n)} sequences that were in snapshot #{base.id} are not in the pool now. They held {fmtShare(shown.gone.share)} of
                the picks then (as a share of that pool). The reason is read from what the database recorded after the snapshot.
              </p>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Reason</th><th className="num">Sequences</th><th className="num">Held</th></tr></thead>
                  <tbody>
                    {shown.gone.reasons.map((r) => (
                      <tr key={r.reason}><td>{r.reason}</td><td className="num">{fmtInt(r.n)}</td><td className="num">{fmtShare(r.share)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {shown.gone.top.length > 0 && (
                <>
                  <p className="caption" style={{ marginTop: 12 }}>The {shown.gone.top.length} that held most:</p>
                  <div className="table-wrap">
                    <table>
                      <thead><tr><th>Sequence</th><th>Name</th><th className="num">Held</th><th>Reason</th></tr></thead>
                      <tbody>
                        {shown.gone.top.map((g) => (
                          <tr key={g.a}><td><OeisLink a={g.a} /></td><td><div className="wrap">{g.name}</div></td>
                            <td className="num">{fmtShare(g.p0)}</td><td>{g.reason}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}
