import { useState, type ReactNode } from "react";
import { fmtSeconds, useWidth } from "./lib";

// ----------------------------------------------------------------------------- tooltip

export interface TipRow { label: string; value: string; color?: string }
interface TipState { x: number; y: number; title: string; rows: TipRow[] }

function Tooltip({ tip }: { tip: TipState | null }) {
  if (!tip) return null;
  const left = Math.min(tip.x + 14, window.innerWidth - 330);
  return (
    <div className="tooltip" style={{ left, top: tip.y + 14 }} role="status">
      <div className="t-title">{tip.title}</div>
      {tip.rows.map((r) => (
        <div className="t-row" key={r.label}>
          <span className="secondary">
            {r.color && <svg width="12" height="8" style={{ marginRight: 6 }}><line x1="0" y1="4" x2="12" y2="4" stroke={r.color} strokeWidth="2" strokeLinecap="round" /></svg>}
            {r.label}
          </span>
          <b>{r.value}</b>
        </div>
      ))}
    </div>
  );
}

// ----------------------------------------------------------------------------- log-log scatter

export interface ScatterPoint {
  id: number;
  x: number;              // predicted seconds
  y: number;              // actual seconds (or lower bound when hollow)
  series: 0 | 1;
  hollow: boolean;
  title: string;
  rows: TipRow[];
}

const SERIES = ["var(--series-1)", "var(--series-2)"];

// gridlines at round units of time rather than powers of ten of seconds
const TIME_TICKS = [1e-3, 1e-2, 0.1, 1, 10, 60, 600, 3600, 86400, 864000, 8640000];

function decades(lo: number, hi: number): number[] {
  const first = TIME_TICKS.filter((t) => t <= lo).pop() ?? TIME_TICKS[0];
  const last = TIME_TICKS.find((t) => t >= hi) ?? TIME_TICKS[TIME_TICKS.length - 1];
  return TIME_TICKS.filter((t) => t >= first && t <= last);
}

export function LogScatter({ points, height = 380 }: { points: ScatterPoint[]; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TipState | null>(null);
  const [active, setActive] = useState<number | null>(null);
  const m = { top: 12, right: 16, bottom: 44, left: 64 };
  const w = Math.max(width, 320), h = height;
  const all = points.flatMap((p) => [p.x, p.y]).filter((v) => v > 0);
  const lo = all.length ? Math.min(...all) / 1.5 : 1e-3;
  const hi = all.length ? Math.max(...all) * 1.5 : 10;
  const ticks = decades(lo, hi);
  const dlo = Math.log10(ticks[0]), dhi = Math.log10(ticks[ticks.length - 1]);
  const sx = (v: number) => m.left + ((Math.log10(v) - dlo) / (dhi - dlo)) * (w - m.left - m.right);
  const sy = (v: number) => h - m.bottom - ((Math.log10(v) - dlo) / (dhi - dlo)) * (h - m.top - m.bottom);
  const [t0, t1] = [ticks[0], ticks[ticks.length - 1]];
  // within-2x band around y = x
  const band = [[t0, t0 * 2], [t1, t1 * 2], [t1, t1 / 2], [t0, t0 / 2]]
    .map(([x, y]) => `${sx(x)},${sy(Math.min(Math.max(y, t0), t1))}`).join(" ");

  const show = (p: ScatterPoint, cx: number, cy: number) => {
    setActive(p.id);
    setTip({ x: cx, y: cy, title: p.title, rows: p.rows });
  };
  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const rect = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const px = e.clientX - rect.left, py = e.clientY - rect.top;
    let best: ScatterPoint | null = null, bestD = 24 * 24;
    for (const p of points) {
      const d = (sx(p.x) - px) ** 2 + (sy(p.y) - py) ** 2;
      if (d < bestD) { bestD = d; best = p; }
    }
    if (best) show(best, e.clientX, e.clientY);
    else { setActive(null); setTip(null); }
  };

  return (
    <div ref={ref} className="chart" style={{ position: "relative" }}>
      <svg width={w} height={h} role="img" aria-label="Predicted versus actual seconds per term, log-log">
        <polygon points={band} fill="var(--band)" />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={sx(t)} x2={sx(t)} y1={m.top} y2={h - m.bottom} stroke="var(--grid)" strokeWidth="1" />
            <line x1={m.left} x2={w - m.right} y1={sy(t)} y2={sy(t)} stroke="var(--grid)" strokeWidth="1" />
            <text x={sx(t)} y={h - m.bottom + 16} textAnchor="middle" fontSize="11" fill="var(--text-muted)">{fmtSeconds(t)}</text>
            <text x={m.left - 8} y={sy(t) + 4} textAnchor="end" fontSize="11" fill="var(--text-muted)">{fmtSeconds(t)}</text>
          </g>
        ))}
        <line x1={sx(t0)} y1={sy(t0)} x2={sx(t1)} y2={sy(t1)} stroke="var(--axis)" strokeWidth="1" />
        <text x={sx(t1) - 6} y={sy(t1) + 14} textAnchor="end" fontSize="11" fill="var(--text-muted)">actual = predicted</text>
        <text x={(m.left + w - m.right) / 2} y={h - 6} textAnchor="middle" fontSize="12" fill="var(--text-secondary)">predicted seconds for the term</text>
        <text transform={`translate(14 ${(m.top + h - m.bottom) / 2}) rotate(-90)`} textAnchor="middle" fontSize="12" fill="var(--text-secondary)">actual seconds</text>
        {points.map((p) => {
          const color = SERIES[p.series];
          const big = active === p.id;
          return (
            <circle key={p.id} cx={sx(p.x)} cy={sy(p.y)} r={big ? 6 : 4.5}
                    fill={p.hollow ? "var(--surface-1)" : color}
                    stroke={p.hollow ? color : "var(--surface-1)"} strokeWidth="2" />
          );
        })}
        <rect x={m.left} y={m.top} width={w - m.left - m.right} height={h - m.top - m.bottom} fill="transparent"
              onPointerMove={onMove} onPointerLeave={() => { setActive(null); setTip(null); }} />
        {points.map((p) => (
          <circle key={`hit-${p.id}`} cx={sx(p.x)} cy={sy(p.y)} r="12" fill="transparent" tabIndex={0}
                  style={{ outline: "none" }} aria-label={p.title}
                  onFocus={(e) => { const r = e.currentTarget.getBoundingClientRect(); show(p, r.left + 12, r.top + 12); }}
                  onBlur={() => { setActive(null); setTip(null); }} pointerEvents="none" />
        ))}
      </svg>
      <Tooltip tip={tip} />
    </div>
  );
}

// ----------------------------------------------------------------------------- horizontal bars

export interface Bar { key: string; label: string; value: number; detail?: string }

function barPath(x0: number, x1: number, y: number, t: number): string {
  const r = Math.min(4, (x1 - x0) / 2, t / 2);
  return `M${x0},${y} H${x1 - r} Q${x1},${y} ${x1},${y + r} V${y + t - r} Q${x1},${y + t} ${x1 - r},${y + t} H${x0} Z`;
}

export function BarList({ bars, onSelect, selected, color = "var(--series-1)" }: {
  bars: Bar[]; onSelect?: (key: string) => void; selected?: string | null; color?: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TipState | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const labelW = 150, valueW = 48, row = 30, thick = 16;
  const w = Math.max(width, 260);
  const max = Math.max(1, ...bars.map((b) => b.value));
  const scale = (v: number) => (v / max) * (w - labelW - valueW);
  if (!bars.length) return <div className="empty">Nothing recorded yet.</div>;
  return (
    <div ref={ref} className="chart">
      <svg width={w} height={bars.length * row + 4} role="list">
        <line x1={labelW} x2={labelW} y1={0} y2={bars.length * row} stroke="var(--axis)" strokeWidth="1" />
        {bars.map((b, i) => {
          const y = i * row + (row - thick) / 2;
          const x1 = labelW + Math.max(scale(b.value), 2);
          const dim = selected && selected !== b.key;
          return (
            <g key={b.key} role="listitem" tabIndex={0} style={{ cursor: onSelect ? "pointer" : "default", outline: "none" }}
               aria-label={`${b.label}: ${b.value}`}
               onClick={() => onSelect?.(b.key)}
               onKeyDown={(e) => { if (e.key === "Enter") onSelect?.(b.key); }}
               onPointerMove={(e) => { setHover(b.key); setTip({ x: e.clientX, y: e.clientY, title: b.label, rows: [{ label: b.detail ?? "count", value: b.value.toLocaleString() }] }); }}
               onPointerLeave={() => { setHover(null); setTip(null); }}
               onFocus={(e) => { const r = e.currentTarget.getBoundingClientRect(); setHover(b.key); setTip({ x: r.right, y: r.top, title: b.label, rows: [{ label: b.detail ?? "count", value: b.value.toLocaleString() }] }); }}
               onBlur={() => { setHover(null); setTip(null); }}>
              <rect x={0} y={i * row} width={w} height={row} fill={hover === b.key ? "var(--hover)" : "transparent"} />
              <text x={labelW - 8} y={i * row + row / 2 + 4} textAnchor="end" fontSize="12" fill="var(--text-secondary)">{b.label}</text>
              <path d={barPath(labelW, x1, y, thick)} fill={color} opacity={dim ? 0.35 : 1} />
              <text x={x1 + 6} y={i * row + row / 2 + 4} fontSize="12" fill="var(--text-primary)" style={{ fontVariantNumeric: "tabular-nums" }}>{b.value.toLocaleString()}</text>
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} />
    </div>
  );
}

// ----------------------------------------------------------------------------- stacked columns

export interface StackSeries { key: string; label: string; color: string }
export interface ColumnDatum { label: string; values: Record<string, number> }

export function StackedColumns({ data, series, height = 220, format = (v: number) => v.toLocaleString(), legend = true }: {
  data: ColumnDatum[]; series: StackSeries[]; height?: number; format?: (v: number) => string; legend?: boolean;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TipState | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const m = { top: 10, right: 8, bottom: 26, left: 44 };
  const w = Math.max(width, 280);
  const totals = data.map((d) => series.reduce((s, k) => s + (d.values[k.key] || 0), 0));
  const rawMax = Math.max(1e-9, ...totals);
  const step = niceStep(rawMax);
  const max = Math.ceil(rawMax / step) * step;
  const ticks = Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step);
  const plotH = height - m.top - m.bottom;
  const slot = (w - m.left - m.right) / Math.max(data.length, 1);
  const colW = Math.min(24, slot * 0.6);
  const sy = (v: number) => m.top + plotH - (v / max) * plotH;
  const everyLabel = Math.ceil(data.length / Math.max(1, Math.floor((w - m.left) / 56)));
  if (!data.length) return <div className="empty">Nothing recorded yet.</div>;
  return (
    <div ref={ref} className="chart">
      {legend && series.length > 1 && (
        <div className="legend">
          {series.map((s) => (
            <span key={s.key}><svg width="10" height="10"><rect width="10" height="10" rx="2" fill={s.color} /></svg>{s.label}</span>
          ))}
        </div>
      )}
      <svg width={w} height={height}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.left} x2={w - m.right} y1={sy(t)} y2={sy(t)} stroke={t === 0 ? "var(--axis)" : "var(--grid)"} strokeWidth="1" />
            <text x={m.left - 6} y={sy(t) + 4} textAnchor="end" fontSize="11" fill="var(--text-muted)" style={{ fontVariantNumeric: "tabular-nums" }}>{format(t)}</text>
          </g>
        ))}
        {data.map((d, i) => {
          const cx = m.left + slot * i + slot / 2;
          let acc = 0;
          const segs = series.map((s) => ({ s, v: d.values[s.key] || 0 })).filter((x) => x.v > 0);
          return (
            <g key={d.label} tabIndex={0} style={{ outline: "none" }}
               aria-label={`${d.label}: ${series.map((s) => `${s.label} ${format(d.values[s.key] || 0)}`).join(", ")}`}
               onPointerMove={(e) => { setHover(i); setTip({ x: e.clientX, y: e.clientY, title: d.label, rows: series.map((s) => ({ label: s.label, value: format(d.values[s.key] || 0), color: s.color })) }); }}
               onPointerLeave={() => { setHover(null); setTip(null); }}
               onFocus={(e) => { const r = e.currentTarget.getBoundingClientRect(); setHover(i); setTip({ x: r.right, y: r.top, title: d.label, rows: series.map((s) => ({ label: s.label, value: format(d.values[s.key] || 0), color: s.color })) }); }}
               onBlur={() => { setHover(null); setTip(null); }}>
              <rect x={cx - slot / 2} y={m.top} width={slot} height={plotH} fill={hover === i ? "var(--hover)" : "transparent"} />
              {segs.map(({ s, v }, j) => {
                const y0 = sy(acc), y1 = sy(acc + v);
                acc += v;
                const top = j === segs.length - 1;
                const gap = j > 0 ? 2 : 0;           // 2px surface gap between stacked segments
                const hgt = Math.max(y0 - y1 - gap, 1);
                const r = top ? Math.min(4, hgt / 2, colW / 2) : 0;
                const x0 = cx - colW / 2, x1 = cx + colW / 2, yb = y0 - gap, yt = yb - hgt;
                const path = `M${x0},${yb} V${yt + r} Q${x0},${yt} ${x0 + r},${yt} H${x1 - r} Q${x1},${yt} ${x1},${yt + r} V${yb} Z`;
                return <path key={s.key} d={path} fill={s.color} />;
              })}
              {i % everyLabel === 0 && (
                <text x={cx} y={height - 8} textAnchor="middle" fontSize="11" fill="var(--text-muted)">{d.label}</text>
              )}
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} />
    </div>
  );
}

function niceStep(max: number): number {
  const rough = max / 4;
  const mag = 10 ** Math.floor(Math.log10(rough));
  const n = rough / mag;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
}

export function LegendDot({ color, hollow, children }: { color: string; hollow?: boolean; children: ReactNode }) {
  return (
    <span>
      <svg width="12" height="12"><circle cx="6" cy="6" r="4" fill={hollow ? "var(--surface-1)" : color} stroke={color} strokeWidth={hollow ? 2 : 0} /></svg>
      {children}
    </span>
  );
}
