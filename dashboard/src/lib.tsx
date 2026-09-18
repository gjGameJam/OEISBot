import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

/** Polls a read-only API path. Keeps the previous data while refetching (no flash). */
export function useApi<T>(path: string, refreshMs = 15000, asText = false) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    let timer = 0;
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(path);
        if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
        const json = (asText ? await res.text() : await res.json()) as T;
        if (alive) {
          setData(json);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(String(e));
      } finally {
        if (alive) {
          setLoading(false);
          timer = window.setTimeout(load, refreshMs);
        }
      }
    };
    load();
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [path, refreshMs, asText]);
  return { data, error, loading };
}

/** Width of an element. A callback ref, so charts that first render a placeholder still get observed. */
export function useWidth<T extends HTMLElement>(): [(el: T | null) => void, number] {
  const [width, setWidth] = useState(600);
  const observer = useRef<ResizeObserver | null>(null);
  const ref = useCallback((el: T | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!el) return;
    const initial = Math.floor(el.getBoundingClientRect().width);   // observers are throttled in background tabs
    if (initial > 0) setWidth(initial);
    observer.current = new ResizeObserver((entries) => {
      const next = Math.floor(entries[0].contentRect.width);
      setWidth((prev) => (Math.abs(prev - next) >= 1 ? next : prev));
    });
    observer.current.observe(el);
  }, []);
  return [ref, width];
}

export function fmtSeconds(s: number | null | undefined): string {
  if (s == null || !isFinite(s)) return "–";
  const round: Record<number, string> = { 0.001: "1 ms", 0.01: "10 ms", 0.1: "100 ms", 1: "1 s", 10: "10 s", 60: "1 min",
    600: "10 min", 3600: "1 h", 36000: "10 h", 86400: "1 d", 864000: "10 d", 8640000: "100 d" };
  if (round[s]) return round[s];
  if (s < 1) return `${(s * 1000).toPrecision(2)} ms`;
  if (s < 120) return `${s.toPrecision(3)} s`;
  if (s < 7200) return `${(s / 60).toPrecision(3)} min`;
  if (s < 172800) return `${(s / 3600).toPrecision(3)} h`;
  return `${(s / 86400).toPrecision(3)} d`;
}

export function fmtBytes(b: number | null | undefined): string {
  if (b == null) return "–";
  if (b < 1 << 20) return `${(b / 1024).toFixed(0)} KiB`;
  if (b < 1 << 30) return `${(b / (1 << 20)).toFixed(0)} MiB`;
  return `${(b / (1 << 30)).toFixed(2)} GiB`;
}

export function fmtPct(x: number | null | undefined, digits = 0): string {
  return x == null ? "–" : `${(x * 100).toFixed(digits)}%`;
}

export function fmtInt(x: number | null | undefined): string {
  return x == null ? "–" : x.toLocaleString();
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function Tile({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="tile">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub != null && <div className="sub">{sub}</div>}
    </div>
  );
}

export function OeisLink({ a }: { a: string }) {
  return (
    <a href={`https://oeis.org/${a}`} target="_blank" rel="noreferrer" className="mono">
      {a}
    </a>
  );
}

export interface Column<R> {
  key: string;
  label: string;
  numeric?: boolean;
  render?: (row: R) => ReactNode;
  sortValue?: (row: R) => number | string | null;
}

/** Sortable table; text is rendered through React, never as HTML. */
export function DataTable<R>({ rows, columns, initialSort, pageSize = 100, rowKey }: {
  rows: R[];
  columns: Column<R>[];
  initialSort?: { key: string; desc: boolean };
  pageSize?: number;
  rowKey: (row: R) => string | number;
}) {
  const [sort, setSort] = useState(initialSort ?? null);
  const [shown, setShown] = useState(pageSize);
  let sorted = rows;
  if (sort) {
    const col = columns.find((c) => c.key === sort.key);
    const get = col?.sortValue ?? ((r: R) => (r as Record<string, unknown>)[sort.key] as number | string | null);
    sorted = [...rows].sort((a, b) => {
      const va = get(a), vb = get(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sort.desc ? -cmp : cmp;
    });
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.numeric ? "num" : undefined}
                  aria-sort={sort?.key === c.key ? (sort.desc ? "descending" : "ascending") : "none"}>
                <button onClick={() => setSort({ key: c.key, desc: sort?.key === c.key ? !sort.desc : !!c.numeric })}>
                  {c.label}
                  {sort?.key === c.key ? (sort.desc ? " ↓" : " ↑") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, shown).map((r) => (
            <tr key={rowKey(r)}>
              {columns.map((c) => (
                <td key={c.key} className={c.numeric ? "num" : undefined}>
                  {c.render ? c.render(r) : String((r as Record<string, unknown>)[c.key] ?? "–")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length > shown && (
        <button className="chip more" onClick={() => setShown(shown + pageSize)}>
          Show more ({sorted.length - shown} remaining)
        </button>
      )}
    </div>
  );
}
