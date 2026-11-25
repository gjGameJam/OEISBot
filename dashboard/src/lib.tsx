import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { tabAfter } from "./tabs";

/** A key handler for a row of tabs, given the tabs' element ids in the order they are drawn: Left, Right, Home
 *  and End move the focus along the row (tabs.tabAfter) and nothing else. With a modifier the key is left to
 *  the browser, whose Alt+Left is Back. */
export function tabKeys(elementIds: string[]) {
  return (e: KeyboardEvent<HTMLElement>) => {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    const to = tabAfter(elementIds, document.activeElement?.id ?? "", e.key);
    if (to == null) return;
    e.preventDefault();
    document.getElementById(to)?.focus();
  };
}

/** Polls a read-only API path: fetches `path`, then again every `refreshMs`, keeping the previous data while it
 *  refetches (no flash). `pollPath`, when given, is what the repeats ask for, so that a request which must not
 *  be repeated (a forced rebuild) is made once. An error stays until the next request for a different `path`
 *  starts or any request succeeds. */
export function useApi<T>(path: string, refreshMs = 15000, asText = false, pollPath = path) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    let timer = 0;
    let target = path;
    setError(null);
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(target);
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
          target = pollPath;
          timer = window.setTimeout(load, refreshMs);
        }
      }
    };
    load();
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [path, pollPath, refreshMs, asText]);
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

// The formatters live in format.ts, which node can test; they are re-exported so call sites need not care.
export { fmtBytes, fmtInt, fmtPct, fmtSeconds, fmtTime } from "./format";

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
