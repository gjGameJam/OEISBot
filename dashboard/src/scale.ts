// Scale arithmetic for the charts. Pure and import-free, like format.ts, so that test/scale.test.ts can load
// it under plain node.

export interface Tick { v: number; label: string }

/** The ladder of round times the log axes use, indexed by any integer: powers of ten of a second up to 10 s
 *  (index 1), then 1 min, 10 min, 1 h, 1 d and powers of ten of a day. It has no first or last rung: an axis
 *  that stopped at 1 ms drew every faster term outside the plot. */
export function timeTick(i: number): Tick {
  if (i >= 5) return { v: 86400 * 10 ** (i - 5), label: `${(10 ** (i - 5)).toLocaleString("en-US")} d` };
  if (i === 4) return { v: 3600, label: "1 h" };
  if (i === 3) return { v: 600, label: "10 min" };
  if (i === 2) return { v: 60, label: "1 min" };
  const v = Number(`1e${i}`);                       // the decimal literal itself, whatever `**` would round to
  if (i >= 0) return { v, label: `${10 ** i} s` };
  if (i >= -3) return { v, label: `${10 ** (i + 3)} ms` };
  if (i >= -6) return { v, label: `${10 ** (i + 6)} µs` };
  if (i >= -9) return { v, label: `${10 ** (i + 9)} ns` };
  return { v, label: `1e${i} s` };
}

const LOWEST = -30, HIGHEST = 40;

export interface TimeDomain { ticks: Tick[]; lo: number; hi: number }

/** The ticks of a log axis that holds every positive finite value in `values` with `pad` to spare on each
 *  side. Always at least two ticks, so that the axis has a length; `lo` and `hi` are the first and the last. */
export function timeDomain(values: readonly number[], pad = 1.5): TimeDomain {
  const pos = values.filter((v) => isFinite(v) && v > 0);
  const min = pos.length ? Math.min(...pos) / pad : 1e-3;
  const max = pos.length ? Math.max(...pos) * pad : 10;
  let first = LOWEST, last = HIGHEST;
  while (first < HIGHEST - 1 && timeTick(first + 1).v <= min) first++;
  while (last > first + 1 && timeTick(last - 1).v >= max) last--;
  const ticks: Tick[] = [];
  for (let i = first; i <= last; i++) ticks.push(timeTick(i));
  return { ticks, lo: ticks[0].v, hi: ticks[ticks.length - 1].v };
}

/** Where `v` falls on a log axis from `lo` to `hi`, as a fraction from 0 to 1, with whether it had to be
 *  pulled in to get there. A value that is zero, negative or not a number sits on the floor, flagged, so that
 *  nothing is ever drawn outside the plot. The estimator's chart never gets such a value (it drops a point
 *  that has no positive time, and `timeDomain` holds the rest), so it does not mark the flag. */
export function logFraction(v: number, lo: number, hi: number): { f: number; clamped: boolean } {
  if (!(v > 0) || !isFinite(v)) return { f: 0, clamped: true };
  const f = (Math.log10(v) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo));
  return f < 0 ? { f: 0, clamped: true } : f > 1 ? { f: 1, clamped: true } : { f, clamped: false };
}

/** The corners, in data units, of the part of the square [lo, hi] x [lo, hi] where y is within a factor `k`
 *  of x. On log axes straight lines between them are its exact outline. Needs `k * lo <= hi`. */
export function bandCorners(lo: number, hi: number, k = 2): [number, number][] {
  return [[lo, lo], [lo, k * lo], [hi / k, hi], [hi, hi], [hi, hi / k], [k * lo, lo]];
}

/** Which tick labels to draw when the ticks are `pxApart` apart on average and a label needs `minPx`: every
 *  n-th, counted from the first. The gridlines are all drawn; only the text is thinned. */
export function labelEvery(pxApart: number, minPx: number): number {
  return pxApart > 0 ? Math.max(1, Math.ceil(minPx / pxApart)) : 1;
}

/** A round step that splits `max` into about four parts. */
export function niceStep(max: number): number {
  const rough = max / 4;
  const mag = 10 ** Math.floor(Math.log10(rough));
  const n = rough / mag;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
}

/** What the estimator plots on the y axis and whether it is a finished time. The server calls a term
 *  finished only when its time is positive (app.py), and so does this: a zero is not a measurement. With
 *  neither a finished time nor a time it was stopped at there is nothing to plot, and the answer is null. */
export function actualOrBound(actual: number | null | undefined, censored: number | null | undefined): { y: number; finished: boolean } | null {
  if (actual != null && actual > 0) return { y: actual, finished: true };
  if (censored != null && censored > 0) return { y: censored, finished: false };
  return null;
}

export type DayColumn = { kind: "day"; day: string; index: number | null } | { kind: "gap"; from: string; to: string; days: number };

/** The columns of a per-day chart, from the days that have data (ISO dates, ascending): every calendar day from
 *  the first to the last, so that columns side by side are days side by side. A day with data carries its
 *  `index` in the input, a day without is `index: null`, and a run of more than `maxGap` empty days becomes one
 *  `gap` so that a quiet month does not flatten the chart. The dates are UTC days, as the server cuts them. */
export function dayColumns(days: readonly string[], maxGap = 3): DayColumn[] {
  const out: DayColumn[] = [];
  const stamp = (d: string) => Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10));
  const iso = (t: number) => new Date(t).toISOString().slice(0, 10);
  const DAY = 86400000;
  days.forEach((day, index) => {
    if (index > 0) {
      const missing = Math.round((stamp(day) - stamp(days[index - 1])) / DAY) - 1;
      const first = stamp(days[index - 1]) + DAY;
      if (missing > maxGap) out.push({ kind: "gap", from: iso(first), to: iso(stamp(day) - DAY), days: missing });
      else for (let k = 0; k < missing; k++) out.push({ kind: "day", day: iso(first + k * DAY), index: null });
    }
    out.push({ kind: "day", day, index });
  });
  return out;
}
