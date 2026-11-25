import { memo, useEffect, useMemo, useRef, useState, type FocusEvent, type KeyboardEvent, type MouseEvent, type PointerEvent, type ReactNode } from "react";
import { Tooltip, type TipRow, type TipState } from "./charts";
import { describeError, fmtShare } from "./format";
import { DataTable, OeisLink, Tile, fmtInt, fmtTime, tabKeys, useApi, useWidth, type Column } from "./lib";
import {
  BIN_LABELS, CHANGE_BINS, LUMP, MAX_ALPHA, NEUTRAL_BIN, changeBin, failureReason, fmtChange, focusOrder, labelFits, layoutGroups,
  neighbour, parseAlpha, pickmapPath, undrawn, type Dir, type Leaf, type PlacedGroup, type PlacedLeaf, type Rect,
} from "./treemap";
import { tapActs } from "./tabs";

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

/** How far a tile's paint stops short of its rect on each side, in px: half a pixel, so neighbours are a pixel
 *  apart. It was 1, and a band of small tiles then lost so much of itself to gutters that it showed about 1.8x
 *  less paint per unit of chance than a band drawn as one lump; at 0.5 that is about 1.3x
 *  (data/item56/area_spread.ts, which must use the same figure). */
const TILE_INSET = 0.5;

/** Tiles in these classes are drawn on their own however small; the rest of the small ones share a lump. */
const NOTABLE = new Set([0, 1, 5, 6]);
/** Class of a row: -1 for "new in the pool" (nothing to compare), else 0..6. */
const NEW = -1;

function binOf(r: PmRow, compared: boolean): number {
  if (!compared) return NEUTRAL_BIN;
  if (r.new) return NEW;
  return r.ratio == null ? NEUTRAL_BIN : changeBin(r.ratio);
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

/** What a tile says about itself in words, for the tooltip's first row and for a screen reader. */
function describeLook(look: Look, compared: boolean, baselineId: number | null): string {
  const parts = [`${fmtShare(look.p)} chance of being picked first`];
  if (compared) {
    if (look.bin === NEW) parts.push("new in the pool");
    else if (look.ratio != null) parts.push(`${fmtChange(look.ratio)} since snapshot #${baselineId}`);
  }
  return parts.join(", ");
}

interface LeafTileProps {
  l: PlacedLeaf; byId: Map<string, PmRow>; names: Map<string, string>; compared: boolean; headers: boolean;
  baselineId: number | null;
  /** The tab index of a tile a keyboard can land on (0: the one Tab reaches, -1: reached by the arrow keys), null for one it cannot. */
  tab: 0 | -1 | null;
}

/** One tile. Memoised on plain values, so moving the keyboard focus redraws the two tiles that change and not the other two thousand. */
const LeafTile = memo(function LeafTile({ l, byId, names, compared, headers, baselineId, tab }: LeafTileProps) {
  const look = lookOf(l.id, l.members, byId, compared);
  const r = l.rect;
  const inset = Math.min(TILE_INSET, Math.min(r.w, r.h) / 4);
  const hatched = look.bin === NEW;
  const text = look.bin === NEW ? "new" : compared ? fmtChange(look.ratio ?? 1) : fmtShare(look.p);
  const first = l.members ? `${fmtInt(l.members.length)} small` : l.id;
  const lines = labelFits(r, Math.max(first.length, text.length), 2) ? 2 : labelFits(r, first.length) ? 1 : 0;
  const about = tab == null ? undefined : l.members
    ? `${fmtInt(l.members.length)} small tiles in band ${names.get(l.id.slice(LUMP.length)) ?? ""}, ${describeLook(look, compared, baselineId)}; ${headers ? "opens the band" : "opens the table view, which lists them"}`
    : `${l.id}, ${byId.get(l.id)!.name}, ${describeLook(look, compared, baselineId)}`;
  return (
    <g>
      <rect className={l.members ? "pm-tile lump" : "pm-tile"} data-id={l.id} x={r.x + inset} y={r.y + inset} width={Math.max(r.w - 2 * inset, 0)}
            height={Math.max(r.h - 2 * inset, 0)} rx={1.5}
            fill={hatched ? "url(#pm-new)" : `var(--chg-${look.bin})`}
            tabIndex={tab ?? undefined} role={tab == null ? undefined : l.members ? "button" : "link"} aria-label={about} />
      {lines > 0 && (
        <text className={`pm-label ${hatched ? "hatched" : ""}`} x={r.x + 5} y={r.y + 14}
              style={hatched ? undefined : { fill: `var(--chg-ink-${look.bin})` }}>
          <tspan className={l.members ? undefined : "mono"} style={{ fontSize: 11 }}>{first}</tspan>
          {lines === 2 && <tspan x={r.x + 5} dy={14} fillOpacity={0.85}>{text}</tspan>}
        </text>
      )}
    </g>
  );
});

interface TilesProps {
  layout: PlacedGroup[]; byId: Map<string, PmRow>; labels: Map<string, string>; names: Map<string, string>; compared: boolean;
  headers: boolean; baselineId: number | null; focusIds: Set<string>; stopId: string | null;
}

/** The drawing itself. Memoised: a mouse move updates only the tooltip, never these thousands of rects. */
const Tiles = memo(function Tiles({ layout, byId, labels, names, compared, headers, baselineId, focusIds, stopId }: TilesProps) {
  return (
    <g>
      {layout.map((g) => (
        <g key={g.key}>
          {headers && <rect className="pm-frame" x={g.rect.x + 0.5} y={g.rect.y + 0.5} width={Math.max(g.rect.w - 1, 0)} height={Math.max(g.rect.h - 1, 0)} />}
          {headers && g.header && (
            <text className="pm-head" data-band={g.key} x={g.rect.x + 6} y={g.rect.y + 13}>{clip(labels.get(g.key) ?? g.key, g.rect.w - 4)}</text>
          )}
          {g.leaves.map((l) => (
            <LeafTile key={l.id} l={l} byId={byId} names={names} compared={compared} headers={headers} baselineId={baselineId}
                      tab={focusIds.has(l.id) ? (l.id === stopId ? 0 : -1) : null} />
          ))}
        </g>
      ))}
    </g>
  );
});

/** What shows the tooltip: the mouse over a tile, or the keyboard focus on one. Whichever moved last owns it. */
interface Shown { tip: TipState; by: "mouse" | "focus" }

const ARROWS: Record<string, Dir> = { ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down" };

function Canvas({ layout, rows, byId, bands, compared, headers, width, height, baselineId, onBand, onTable }: {
  layout: PlacedGroup[]; rows: PmRow[]; byId: Map<string, PmRow>; bands: PmBand[]; compared: boolean; headers: boolean;
  width: number; height: number; baselineId: number | null; onBand: (band: number) => void;
  /** Open the table view: what a lump does on a band's own tab, where there is no band left to open. */
  onTable: () => void;
}) {
  const [shown, setShown] = useState<Shown | null>(null);
  const [stop, setStop] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const refocus = useRef(false);
  const dismissed = useRef<string | null>(null);   // the tile whose tooltip Escape closed, until the focus moves to a tile again
  // What the last press came from, and the tile a touch has put a tooltip up for and may now open (tabs.tapActs).
  const pointer = useRef<string | null>(null);
  const armed = useRef<string | null>(null);
  useEffect(() => { if (!shown) armed.current = null; }, [shown]);   // no tooltip on show, nothing to confirm
  const members = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const g of layout) for (const l of g.leaves) if (l.members) m.set(l.id, l.members);
    return m;
  }, [layout]);
  const labels = useMemo(() => new Map(bands.map((b) => [bandKey(b.band), `${b.label} · ${fmtInt(b.n)} · ${fmtShare(b.share)}`])), [bands]);
  const names = useMemo(() => new Map(bands.map((b) => [bandKey(b.band), b.label])), [bands]);
  const bandLabel = (band: number) => bands.find((b) => b.band === band)?.label ?? String(band);

  // The tiles a keyboard can land on, lumps included: a lump opens its band, or on a band's own tab the table.
  // One of them is the tab stop: the one last focused, else the first.
  const order = useMemo(() => focusOrder(layout, true), [layout]);
  const focusIds = useMemo(() => new Set(order.map((i) => i.id)), [order]);
  const stopId = stop != null && focusIds.has(stop) ? stop : order[0]?.id ?? null;

  const tipFor = (id: string, x: number, y: number, touch = false): TipState => {
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
      rowsOut.push({ label: touch ? "Tap again" : "Click or Enter", value: headers ? "to open this band" : "to open the table view" });
      return { x, y, title: `${fmtInt(lump.length)} small tiles`, rows: rowsOut };
    }
    const r = byId.get(id)!;
    rowsOut.push({ label: "Difficulty", value: r.d.toFixed(3) });
    rowsOut.push({ label: "Band", value: bandLabel(r.band) });
    if (touch) rowsOut.push({ label: "Tap again", value: "to open the entry on oeis.org" });
    return { x, y, title: `${r.a} ${r.name}`, rows: rowsOut };
  };

  const activate = (id: string) => {
    if (id.startsWith(LUMP)) { if (headers) onBand(bandOfKey(id.slice(LUMP.length))); else onTable(); }
    else window.open(`https://oeis.org/${id}`, "_blank", "noopener,noreferrer");
  };
  const focusTile = (id: string) => {
    svgRef.current?.querySelector<SVGElement>(`[data-id="${CSS.escape(id)}"]`)?.focus();
  };
  // The tooltip for the tile that has the keyboard focus, placed from where the tile is now. False when no tile has it
  // or the focus came from a mouse click (which gets no tooltip).
  const showFor = (el: Element): boolean => {
    const id = el.getAttribute("data-id");
    if (id == null || !focusIds.has(id) || dismissed.current === id || !el.matches(":focus-visible")) return false;
    if (id !== armed.current) armed.current = null;   // the tooltip about to show is another tile's: nothing is confirmed
    const box = el.getBoundingClientRect();
    setShown({ tip: tipFor(id, box.left + box.width / 2, box.top + box.height / 2), by: "focus" });
    return true;
  };
  // A tooltip belongs to a tile of the layout it was made from; a new layout (another band, a resize, a refresh) ends it,
  // except that a tile the keyboard is still on gets its tooltip again (it has not moved the focus, so nothing else would).
  useEffect(() => {
    const el = document.activeElement;
    if (!(el && svgRef.current?.contains(el) && showFor(el))) setShown(null);
  }, [layout]);
  // Opening a band from the keyboard removes the tile that had the focus: put it on the new map's first tile.
  useEffect(() => {
    if (!refocus.current) return;
    refocus.current = false;
    if (order.length) focusTile(order[0].id);
  }, [order]);

  // A tooltip is placed in the window, once, from where its tile or the pointer was. When the page scrolls, the
  // tile moves and the tooltip would stay behind, pointing at whatever slid under it. So a scroll ends the
  // pointer's tooltip and puts the keyboard's back where its tile now is. It must not simply close that one: the
  // browser scrolls a half-hidden tile into view just after it takes the focus, which is a scroll too.
  const onScroll = useRef<() => void>(() => undefined);
  onScroll.current = () => {
    const el = document.activeElement;
    if (!(el && svgRef.current?.contains(el) && showFor(el))) setShown(null);
  };
  useEffect(() => {
    const handler = () => onScroll.current();
    window.addEventListener("scroll", handler, { capture: true, passive: true });
    return () => window.removeEventListener("scroll", handler, { capture: true });
  }, []);

  const idOf = (e: { target: EventTarget }) => (e.target as Element).getAttribute?.("data-id") ?? null;

  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    const id = (e.target as Element).closest?.("[data-id]")?.getAttribute("data-id");
    // A touch makes up a mouse move just before its click. Over the armed tile it keeps the "tap again" line;
    // over anything else the tile is disarmed, because its tooltip is no longer the one on show.
    if (id !== armed.current) armed.current = null;
    const tip = id ? tipFor(id, e.clientX, e.clientY, armed.current === id) : null;
    setShown((s) => (tip ? { tip, by: "mouse" } : s?.by === "mouse" ? null : s));   // over a header or a frame: only a mouse tooltip ends
  };
  const onClick = (e: MouseEvent<SVGSVGElement>) => {
    const target = (e.target as Element).closest?.("[data-id],[data-band]");
    if (!target) return;
    const id = target.getAttribute("data-id");
    const key = target.getAttribute("data-band");
    if (key) onBand(bandOfKey(key));
    else if (id && tapActs(pointer.current, armed.current, id)) { armed.current = null; activate(id); }
    else if (id) {
      // a first tap: the tooltip, where the finger is, saying that a second tap opens it
      setShown({ tip: tipFor(id, e.clientX, e.clientY, true), by: "mouse" });
      armed.current = id;
    }
  };
  const onPointerDown = (e: PointerEvent<SVGSVGElement>) => { pointer.current = e.pointerType; };
  const onFocus = (e: FocusEvent<SVGSVGElement>) => {
    const id = idOf(e);
    if (id == null || !focusIds.has(id)) return;
    setStop(id);
    dismissed.current = null;
    showFor(e.target as Element);
  };
  const onBlur = () => setShown((s) => (s?.by === "focus" ? null : s));
  const onKeyDown = (e: KeyboardEvent<SVGSVGElement>) => {
    const id = idOf(e);
    if (id == null || !focusIds.has(id) || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === "Escape") { dismissed.current = id; setShown(null); return; }
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();                                               // Space must not scroll the page
      if (e.repeat) return;                                             // a held key must not open a tab per repeat
      if (id.startsWith(LUMP) && headers) refocus.current = true;         // the band's map replaces this one; the table takes its own focus
      activate(id);
      return;
    }
    const dir = ARROWS[e.key];
    const next = dir ? neighbour(order, id, dir) : e.key === "Home" ? order[0].id : e.key === "End" ? order[order.length - 1].id : undefined;
    if (next === undefined) return;
    e.preventDefault();
    if (next !== null && next !== id) focusTile(next);
  };

  return (
    <>
      <svg ref={svgRef} width={width} height={height} role="group" onMouseMove={onMove} onClick={onClick} onPointerDown={onPointerDown}
           onMouseLeave={() => setShown((s) => (s?.by === "mouse" ? null : s))} onFocus={onFocus} onBlur={onBlur} onKeyDown={onKeyDown}
           aria-label={`Treemap of ${fmtInt(rows.length)} sequences; area is pick chance${compared ? ", colour is the change since the earlier snapshot" : ""}. Arrow keys move between tiles, Enter opens one, Escape closes the tooltip. The table view below has the same data.`}>
        <defs>
          <pattern id="pm-new" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="7" height="7" style={{ fill: "var(--chg-3)" }} />
            <line x1="0" y1="0" x2="0" y2="7" style={{ stroke: "var(--text-muted)", strokeWidth: 2 }} />
          </pattern>
        </defs>
        <Tiles layout={layout} byId={byId} labels={labels} names={names} compared={compared} headers={headers}
               baselineId={baselineId} focusIds={focusIds} stopId={stopId} />
      </svg>
      <Tooltip tip={shown?.tip ?? null} />
    </>
  );
}

/** The bands "All bands" has no room to draw, each a button that opens the band. */
function Undrawn({ keys, bands, onBand }: { keys: string[]; bands: PmBand[]; onBand: (band: number) => void }) {
  const hidden = keys.map((k) => bands.find((b) => b.band === bandOfKey(k))).filter((b): b is PmBand => b != null);
  if (hidden.length === 0) return null;
  return (
    <div className="pm-undrawn" role="group" aria-label="Bands too small to draw">
      <span className="secondary">Too small to draw to scale here:</span>
      {hidden.map((b) => (
        <button key={b.band} className="chip" onClick={() => onBand(b.band)}
                title={`${fmtInt(b.n)} sequences holding ${fmtShare(b.share)} of the picks; open this band to see them`}>
          {b.label}{" "}<span className="muted">{fmtInt(b.n)} · {fmtShare(b.share)}</span>
        </button>
      ))}
    </div>
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

function TableTwin({ rows, compared, bands, open, onOpen }: {
  rows: PmRow[]; compared: boolean; bands: PmBand[]; open: boolean; onOpen: (open: boolean) => void;
}) {
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
    <details className="twin" open={open} onToggle={(e) => onOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary id="pm-table-summary">Table view ({fmtInt(rows.length)} sequences)</summary>
      {open && <DataTable rows={rows} columns={columns} rowKey={(r) => r.a} initialSort={{ key: "p", desc: true }} />}
    </details>
  );
}

export function PickMapView() {
  const [pool, setPool] = useState<Pool>("pari");
  const [alphaText, setAlphaText] = useState("1");
  const [alpha, setAlpha] = useState(1);
  const [rebuilds, setRebuilds] = useState(0);
  const [band, setBandState] = useState<number | null>(null);
  const [tableOpen, setTableOpen] = useState(false);
  // another band is another table: it starts closed, as it did when the table was remounted per band
  const setBand = (b: number | null) => { setBandState(b); setTableOpen(false); };
  // A lump on a band's own tab: the band is too dense for tiles, so the table is where its sequences are. The
  // focus goes with it, or a keyboard user would be left on a tile that did nothing they could see.
  const openTable = () => {
    setTableOpen(true);
    window.requestAnimationFrame(() => {
      const summary = document.getElementById("pm-table-summary");
      summary?.focus();
      summary?.scrollIntoView({ block: "nearest" });
    });
  };
  const [wrapRef, width] = useWidth<HTMLDivElement>();
  const typed = parseAlpha(alphaText);

  useEffect(() => {
    if (typed == null || typed === alpha) return;
    const t = window.setTimeout(() => { setAlpha(typed); setRebuilds(0); }, 500);
    return () => window.clearTimeout(t);
  }, [typed, alpha]);

  // A rebuild is asked for once: the first request carries the flag, every later one (the hourly refresh) does not,
  // and choosing another pool or alpha drops it.
  // Pressing the pool that is already chosen does nothing: it used to reset the band and drop a rebuild in flight.
  const pickPool = (p: Pool) => { if (p === pool) return; setPool(p); setBand(null); setRebuilds(0); };
  const { data, error, loading } = useApi<PmData>(pickmapPath(pool, alpha, rebuilds), 3600000, false, pickmapPath(pool, alpha));
  const shown = data && data.pool === pool ? data : null;
  // Dimmed while a request is out, or while the map is for another alpha than the box says; not once a request failed,
  // or the failure message would sit over a map that stays dim for good.
  const stale = loading || (shown != null && shown.alpha !== alpha && !error);
  // The buttons that rebuild are aria-disabled, not disabled, while a build runs: a focused button that becomes disabled
  // loses the focus. Trying again also moves the focus to "Rebuild now", because the failure block it was in goes away
  // when the new request starts.
  const rebuildRef = useRef<HTMLButtonElement>(null);
  const rebuild = () => { if (!loading) setRebuilds((n) => n + 1); };
  const tryAgain = () => { if (loading) return; rebuild(); rebuildRef.current?.focus(); };
  const reason = error == null ? null : failureReason(error);
  const poolName = pool === "model" ? "model" : "PARI";

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
  // A band opened from the "too small to draw" chips takes the keyboard focus to its tab: the chip it came from is gone.
  const focusTab = useRef<number | null>(null);
  useEffect(() => {
    if (focusTab.current == null || activeBand !== focusTab.current) return;
    focusTab.current = null;
    document.getElementById(`pm-tab-${activeBand}`)?.focus();
  }, [activeBand]);
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
  const hidden = useMemo(() => (activeBand == null ? undrawn(layout) : []), [layout, activeBand]);

  // `alarm` marks a note that says the colours may mislead; the others only describe the state of things.
  const notes: { key: string; text: ReactNode; alarm?: boolean }[] = [];
  const cmd = (text: string) => <span className="mono">{text}</span>;
  if (shown) {
    // which commands store which pool: cli.cmd_snapshot stores the model pool only with --all, a session stores
    // the pool it drew from, and a sync stores the PARI pool only (attempt.snapshot_after_sync)
    if (shown.snapshots === 0) {
      notes.push({ key: "none", text: pool === "model"
        ? <>No snapshot of the model pool is stored yet. Run {cmd("oeisbot snapshot --all")} (a session started with {cmd("oeisbot run --model")} stores one too); until then there is nothing to compare with.</>
        : <>No snapshot of the PARI pool is stored yet. Run {cmd("oeisbot snapshot")} (every {cmd("oeisbot run")}, and an {cmd("oeisbot sync")} that changes the pool, stores one too); until then there is nothing to compare with.</> });
    } else if (!shown.baseline) notes.push({ key: "same", text: "Every stored snapshot is identical to the live pool, so there is no change to show yet." });
    if (shown.baseline?.budgets_differ) notes.push({ key: "budgets", alarm: true, text: "The baseline was taken under other time budgets than the live pool, so part of the change comes from that and not from what happened." });
    if (shown.baseline?.rules_differ === true) notes.push({ key: "rules", alarm: true, text: "The selection rules (the code that scores candidates) changed since the baseline, so part of the change comes from the code." });
    if (shown.baseline && shown.baseline.rules_differ === null) notes.push({ key: "rules-unknown", alarm: true, text: "The selection rules could not be compared with the baseline's (it recorded none, or this server could not read its own source files), so a change in them cannot be ruled out." });
    if (shown.running_session) notes.push({ key: "running", text: `Session ${shown.running_session.id} (started ${fmtTime(shown.running_session.started_at)}) has not finished; the map shows the attempts it has recorded so far.` });
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
        <button ref={rebuildRef} className="chip" aria-disabled={loading} onClick={rebuild}>{loading ? "Building…" : "Rebuild now"}</button>
        <span className="muted">{shown ? `pool built ${ago(shown.age_s)}${shown.note ? ` · ${shown.note}` : ""}` : ""}</span>
      </div>
      {typed == null && (
        <p id="pm-alpha-error" className="error" role="alert">
          α must be a number from 0 to {MAX_ALPHA}; the map still shows α {alpha}.
        </p>
      )}
      {error && (
        <div className="error pm-failure" role="alert">
          <p>
            {reason != null ? `The ${poolName} pool could not be built: ${reason}` : `Could not load: ${describeError(error)}`}
            {shown ? (shown.alpha !== alpha ? `. The map below still shows α ${shown.alpha}.` : ". The map below is the last one that loaded.") : null}
          </p>
          <button className="chip" aria-disabled={loading} onClick={tryAgain}>{loading ? "Building…" : "Try again"}</button>
        </div>
      )}
      {!shown && loading && !error && <p className="muted">Building the {poolName} pool{pool === "model" ? " (about 27,000 sequences, this can take half a minute)" : ""}…</p>}
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
          {notes.length > 0 && <ul className="notes">{notes.map((n) => <li key={n.key} className={n.alarm ? "alarm" : undefined}><span>{n.text}</span></li>)}</ul>}
          <div className={`card ${stale ? "stale" : ""}`} aria-busy={loading}>
            <h2>Pick map</h2>
            <p className="caption">
              Each tile is one sequence and its area is its chance of being the first pick of the next session, so a large tile is
              a likely one. Colour is how that chance has moved since the earlier snapshot, measured against the sequences that were in both
              pools: when a few sequences leave or fail, the rest do not all drift together. The &ldquo;before&rdquo; chance in a tooltip or
              the table is scaled the same way (the sequences in both pools hold the same total of it as they do now), so before and now
              divide into the change shown. Every band is drawn at one scale, so a tile in one band can be compared with a tile in
              another; a band with room to spare leaves some of its box empty for that. Click a tile to open the entry on oeis.org. From
              the keyboard, Tab enters the map, the arrow keys move between tiles, and Enter opens the entry. A dashed tile stands for
              many sequences too small to draw: it opens their band, or, on the band&rsquo;s own tab, the table view that lists them.
            </p>
            {shown.n === 0 ? (
              <p className="muted">The {pool === "model" ? "model" : "PARI"} pool is empty: no sequence is a candidate for it right now.</p>
            ) : (
              <>
                <div className="subtabs" role="tablist" aria-label="Difficulty band"
                     onKeyDown={tabKeys(["pm-tab-all", ...shown.bands.map((b) => `pm-tab-${b.band}`)])}>
                  <button className="chip" role="tab" id="pm-tab-all" aria-controls="pm-panel" aria-selected={activeBand == null}
                          tabIndex={activeBand == null ? 0 : -1} onClick={() => setBand(null)}>All bands</button>
                  {shown.bands.map((b) => (
                    <button key={b.band} id={`pm-tab-${b.band}`} className="chip" role="tab" aria-controls="pm-panel" aria-selected={activeBand === b.band}
                            tabIndex={activeBand === b.band ? 0 : -1} onClick={() => setBand(b.band)}
                            title={`${fmtInt(b.n)} sequences holding ${fmtShare(b.share)} of the picks`}>
                      {b.label}{" "}<span className="muted">{fmtInt(b.n)} · {fmtShare(b.share)}</span>
                    </button>
                  ))}
                </div>
                <div className="chart pm-wrap" ref={wrapRef} id="pm-panel" role="tabpanel" aria-labelledby={`pm-tab-${activeBand ?? "all"}`}>
                  <Canvas layout={layout} rows={rows} byId={derived.byId} bands={shown.bands} compared={derived.compared}
                          headers={activeBand == null} width={Math.max(width, 200)} height={height}
                          baselineId={base?.id ?? null} onBand={setBand} onTable={openTable} />
                </div>
                <Undrawn keys={hidden} bands={shown.bands} onBand={(b) => { focusTab.current = b; setBand(b); }} />
                <Legend compared={derived.compared} baselineId={base?.id ?? null} />
                <TableTwin key={activeBand ?? "all"} rows={rows} compared={derived.compared} bands={shown.bands} open={tableOpen} onOpen={setTableOpen} />
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
