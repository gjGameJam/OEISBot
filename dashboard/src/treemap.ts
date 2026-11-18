// Pure treemap layout and colour binning for the Pick map. No React and no imports, so that
// `npm test` can run it under plain node (dashboard/test/treemap.test.ts).

export interface Rect { x: number; y: number; w: number; h: number }

const worstRatio = (sum: number, max: number, min: number, side: number): number =>
  Math.max((side * side * max) / (sum * sum), (sum * sum) / (side * side * min));

/** Squarified treemap (Bruls, Huizing, van Wijk). One rect per value, in input order; a value <= 0 gets an
 *  empty rect. The rects tile `rect` exactly, with areas proportional to the values. */
export function squarify(values: readonly number[], rect: Rect): Rect[] {
  const out: Rect[] = values.map(() => ({ x: rect.x, y: rect.y, w: 0, h: 0 }));
  const order = values.map((_, i) => i).filter((i) => values[i] > 0).sort((a, b) => values[b] - values[a] || a - b);
  if (!order.length || rect.w <= 0 || rect.h <= 0) return out;
  const scale = (rect.w * rect.h) / order.reduce((s, i) => s + values[i], 0);
  let { x, y, w, h } = rect;
  let i = 0;
  while (i < order.length) {
    const side = Math.min(w, h);
    let j = i, sum = 0, max = 0, min = Infinity, worst = Infinity;
    while (j < order.length) {
      const a = values[order[j]] * scale;
      const nsum = sum + a, nmax = Math.max(max, a), nmin = Math.min(min, a);
      const nworst = worstRatio(nsum, nmax, nmin, side);
      if (j > i && nworst > worst) break;
      sum = nsum; max = nmax; min = nmin; worst = nworst; j++;
    }
    const last = j >= order.length;
    if (w >= h) {                       // a column down the left edge
      const cw = last ? w : sum / h;
      let cy = y;
      for (let k = i; k < j; k++) {
        const ch = k === j - 1 ? y + h - cy : (values[order[k]] * scale) / cw;
        out[order[k]] = { x, y: cy, w: cw, h: ch };
        cy += ch;
      }
      x += cw; w -= cw;
    } else {                            // a row along the top edge
      const rh = last ? h : sum / w;
      let cx = x;
      for (let k = i; k < j; k++) {
        const cwid = k === j - 1 ? x + w - cx : (values[order[k]] * scale) / rh;
        out[order[k]] = { x: cx, y, w: cwid, h: rh };
        cx += cwid;
      }
      y += rh; h -= rh;
    }
    i = j;
  }
  return out;
}

// ----------------------------------------------------------------------------- nested layout (all bands)

/** `keep`: draw this leaf on its own however small it comes out (a tile that changed must not vanish into a lump). */
export interface Leaf { id: string; value: number; keep?: boolean }
export interface PlacedLeaf { id: string; rect: Rect; members: string[] | null }   // members: set on a lump
/** `rect` is the group's whole tile, `inner` what the frame (header and padding) leaves of it, and `leaf` the
 *  part of `inner` the leaves are drawn in. `scaled` says the leaves are drawn at the layout's common scale;
 *  false for a group with no room for that (see `layoutGroups`), whose leaves fill `inner` at a smaller one. */
export interface PlacedGroup {
  key: string; value: number; rect: Rect; inner: Rect; leaf: Rect; scaled: boolean; header: boolean; leaves: PlacedLeaf[];
}

export const LUMP = "~lump:";

export interface NestOptions { headerH: number; minLeafArea: number; pad: number }

/** What of a group's rect its leaves get: the rect less a header strip (when it is big enough to carry one)
 *  and the padding all round. */
function frame(r: Rect, opt: NestOptions): { header: boolean; inner: Rect } {
  const header = r.h >= opt.headerH * 2.5 && r.w >= 90;
  const top = header ? opt.headerH : 0;
  return { header, inner: { x: r.x + opt.pad, y: r.y + top + opt.pad, w: Math.max(r.w - 2 * opt.pad, 0), h: Math.max(r.h - top - 2 * opt.pad, 0) } };
}

/** Whether a group's inner rect has room for tiles at all (see MIN_DRAWN_SIDE). */
const drawable = (inner: Rect, minSide: number): boolean => Math.min(inner.w, inner.h) >= minSide;

/** The area per unit of value that every group with room for tiles can give its leaves: the least of
 *  inner area / total among them. 0 when no group has room. */
function commonScale(totals: readonly number[], rects: readonly Rect[], opt: NestOptions): { scale: number; roomy: number } {
  let scale = Infinity, roomy = 0;
  rects.forEach((r, i) => {
    const { inner } = frame(r, opt);
    if (totals[i] > 0 && drawable(inner, MIN_DRAWN_SIDE)) { roomy++; scale = Math.min(scale, (inner.w * inner.h) / totals[i]); }
  });
  return { scale: roomy ? scale : 0, roomy };
}

/** The group rects. Squarifying the plain totals would give every group a rect in proportion to its total, but
 *  what the leaves get is the rect less its frame, and the header and padding take a larger part of a narrow
 *  rect than of a wide one. So a few more layouts are tried, each enlarging a group's weight by the part of its
 *  rect the frame took in the one before, and the layout kept is the one that leaves the tightest group the
 *  most room (`commonScale`), among those that draw the most groups. This search does *not* make the groups
 *  equal and was once trusted to: it cycles on squarify's row breaks and left bands up to 2x apart. Equality is
 *  `layoutGroups`' job; all this does is waste less space getting there. */
function fairRects(totals: number[], rect: Rect, opt: NestOptions): Rect[] {
  let rects = squarify(totals, rect);
  let best = rects, bestFit = commonScale(totals, rects, opt);
  for (let pass = 0; pass < 8; pass++) {
    const weights = totals.map((t, i) => {
      const r = rects[i];
      const inner = frame(r, opt).inner;
      const kept = r.w * r.h > 0 ? (inner.w * inner.h) / (r.w * r.h) : 0;
      return kept > MIN_KEPT ? t / kept : t;
    });
    rects = squarify(weights, rect);
    const fit = commonScale(totals, rects, opt);
    if (fit.roomy > bestFit.roomy || (fit.roomy === bestFit.roomy && fit.scale > bestFit.scale)) { best = rects; bestFit = fit; }
  }
  return best;
}
const MIN_KEPT = 0.25;

/** The part of `inner` with area `area`, from its top left corner, cut along its longer side. */
function shrunk(inner: Rect, area: number): Rect {
  if (!(area < inner.w * inner.h)) return inner;
  return inner.w >= inner.h ? { ...inner, w: area / inner.h } : { ...inner, h: area / inner.w };
}

/** Groups as one squarified level, then each group's leaves squarified inside it, **all at one scale**: a
 *  unit of value is the same number of px² in every group that has room for tiles. The scale is the tightest
 *  such group's (`commonScale`); a roomier group draws its leaves in the part of its inner rect that this scale
 *  fills (`leaf`) and leaves the rest of it empty, which is the price of areas that can be compared across
 *  groups. A group with no room for tiles (`scaled: false`; `undrawn` lists it) fills its sliver at its own,
 *  smaller scale.
 *
 *  A leaf that would get less than `minLeafArea` px² is not drawn on its own (unless it is marked `keep`):
 *  those leaves share one "lump" tile, so a group of 800 sequences does not turn into 800 specks. A lump of one
 *  leaf is just that leaf. */
export function layoutGroups(groups: { key: string; leaves: Leaf[] }[], rect: Rect, opt: NestOptions): PlacedGroup[] {
  const totals = groups.map((g) => g.leaves.reduce((s, l) => s + Math.max(l.value, 0), 0));
  const rects = fairRects(totals, rect, opt);
  const common = commonScale(totals, rects, opt).scale;
  return groups.map((g, gi) => {
    const r = rects[gi];
    const { header, inner } = frame(r, opt);
    const scaled = totals[gi] > 0 && drawable(inner, MIN_DRAWN_SIDE);
    const scale = scaled ? common : totals[gi] > 0 ? (inner.w * inner.h) / totals[gi] : 0;
    const leaf = scaled ? shrunk(inner, totals[gi] * scale) : inner;
    const live = g.leaves.filter((l) => l.value > 0).sort((a, b) => b.value - a.value || (a.id < b.id ? -1 : 1));
    let big = live.filter((l) => l.keep || l.value * scale >= opt.minLeafArea);
    let small = live.filter((l) => !l.keep && l.value * scale < opt.minLeafArea);
    if (small.length === 1) { big = [...big, small[0]]; small = []; }
    const entries: { id: string; value: number; members: string[] | null }[] = big.map((l) => ({ id: l.id, value: l.value, members: null }));
    if (small.length) entries.push({ id: LUMP + g.key, value: small.reduce((s, l) => s + l.value, 0), members: small.map((l) => l.id) });
    const placed = squarify(entries.map((e) => e.value), leaf);
    return { key: g.key, value: totals[gi], rect: r, inner, leaf, scaled, header,
             leaves: entries.map((e, i) => ({ id: e.id, rect: placed[i], members: e.members })) };
  });
}

// ----------------------------------------------------------------------------- colour bins

/** Seven classes of change in pick chance, as the ratio now / then (the server's `ratio`, which compares
 *  a sequence with the others that were in both pools):
 *  0 down 45% or more (r <= 0.55)   1 down 10-45%   2 down 1-10%   3 within 1% either way
 *  4 up 1-10%                       5 up 10-80%     6 up 80% or more (r >= 1.8).
 *  The outer edges are 0.55 and 1.8 rather than 0.5 and 2 because the commonest event, one failed or
 *  verified-without-terms attempt, doubles a sequence's difficulty and so moves its chance to 0.50 x
 *  (alpha 1): the class edge must not sit on the value the data piles up at. */
export const CHANGE_BINS = 7;
export const NEUTRAL_BIN = 3;
export const BIN_LABELS = ["down 45% or more", "down 10 to 45%", "down 1 to 10%", "within 1%", "up 1 to 10%", "up 10 to 80%", "up 80% or more"];

export function changeBin(ratio: number): number {
  if (Math.abs(ratio - 1) <= 0.01 + 1e-9) return NEUTRAL_BIN;   // 0.99 - 1 is 0.010000000000000009 in floating point
  if (ratio < 1) return ratio <= 0.55 ? 0 : ratio <= 0.9 ? 1 : 2;
  return ratio >= 1.8 ? 6 : ratio >= 1.1 ? 5 : 4;
}

/** "+12%", "−50%", "+0.40%" (U+2212 for the sign, as the typeset minus reads better in a tile). Rounded, except
 *  where rounding would carry the figure over the edge of its colour class: a change of −9.999% is in "down 1 to
 *  10%" and reads "−9.9%", never the "−10%" of the next class, so a tile's number and its colour cannot disagree.
 *  The number of decimals follows the figure shown, so both sides of an edge are written alike. */
export function fmtChange(ratio: number): string {
  const pct = (ratio - 1) * 100;
  const sign = pct < 0 ? -1 : 1, a = Math.abs(pct);
  const digitsFor = (x: number) => (x >= 10 ? 0 : x >= 1 ? 1 : 2);
  let digits = digitsFor(a);
  let shown = Number(a.toFixed(digits));
  if (digitsFor(shown) < digits) { digits = digitsFor(shown); shown = Number(a.toFixed(digits)); }
  if (shown !== 0 && changeBin(1 + (sign * shown) / 100) !== changeBin(ratio)) {
    digits = digitsFor(a);
    shown = Math.floor(a * 10 ** digits + 1e-9) / 10 ** digits;      // cut, not rounded; 1e-9 for 0.9 - 1 in floating point
  }
  if (shown === 0) return "0%";
  return `${sign < 0 ? "−" : "+"}${shown.toFixed(digits)}%`;
}

// ----------------------------------------------------------------------------- request

/** The largest alpha the server accepts (`MAX_ALPHA` in oeisbot/pickmap.py; tests/test_pickmap.py compares the two). */
export const MAX_ALPHA = 6;

/** The alpha a text field holds, or null when it is not a number the server would take. */
export function parseAlpha(text: string): number | null {
  if (text.trim() === "") return null;
  const v = Number(text);
  return Number.isFinite(v) && v >= 0 && v <= MAX_ALPHA ? v : null;
}

/** The request for a pool. `rebuild` (a counter) adds the flag that makes the server build the pool again, and a
 *  counter that differs from the last one so that the browser cannot answer it from its cache. */
export function pickmapPath(pool: string, alpha: number, rebuild = 0): string {
  return `/api/pickmap?pool=${pool}&alpha=${alpha}${rebuild > 0 ? `&refresh=true&v=${rebuild}` : ""}`;
}

/** Whether a label of roughly `chars` characters at 11px fits a tile, with padding. */
export function labelFits(r: Rect, chars: number, lines = 1): boolean {
  return r.w >= chars * 6.4 + 8 && r.h >= lines * 14 + 6;
}

// ----------------------------------------------------------------------------- what cannot be drawn

/** A band whose inner rect (the area its tiles get, inside the frame and padding) is narrower than this in either
 *  direction cannot be seen or pointed at. Measured on the real PARI pool (data/item55/inner_sizes.ts): band 8 (two
 *  sequences) gets 0 px at every width from 360 to 1600, band 7 gets 0 to 5 px at most widths and 8 to 11 px at a
 *  few, so 6 px sorts them by what a reader can use. */
export const MIN_DRAWN_SIDE = 6;

/** The keys of the groups whose tiles end up too small to see (a group that got no area at all included), in
 *  layout order. */
export function undrawn(layout: readonly PlacedGroup[], minSide = MIN_DRAWN_SIDE): string[] {
  return layout.filter((g) => Math.min(g.inner.w, g.inner.h) < minSide).map((g) => g.key);
}

// ----------------------------------------------------------------------------- keyboard

/** A tile narrower than this in either direction is not a keyboard stop. A tile marked `keep` is drawn however
 *  small, and once a model-pool snapshot exists thousands of them are under 3 px: a focus ring nobody can see, on
 *  a tile nobody can read, thousands of times over. The table view has them. */
export const MIN_FOCUS_SIDE = 3;

/** The tiles a keyboard can land on, in layout order (group by group, each group's largest tile first): every leaf
 *  at least `MIN_FOCUS_SIDE` on both sides, except the leaves of a group too small to see (the map lists those
 *  groups under it instead) and, unless `lumps`, the lumps. A group that is drawn but has no leaf that large
 *  (every one of them kept, and tiny) still gets one stop, its largest leaf: a band on the screen that a
 *  keyboard cannot enter at all would be worse than one small focus ring. */
export function focusOrder(layout: readonly PlacedGroup[], lumps: boolean, minSide = MIN_DRAWN_SIDE,
                           minTile = MIN_FOCUS_SIDE): { id: string; rect: Rect }[] {
  const small = new Set(undrawn(layout, minSide));
  return layout.filter((g) => !small.has(g.key)).flatMap((g) => {
    const drawn = g.leaves.filter((l) => l.rect.w > 0 && l.rect.h > 0 && (lumps || !l.members));
    const big = drawn.filter((l) => Math.min(l.rect.w, l.rect.h) >= minTile);
    const stops = big.length || !drawn.length ? big
      : [drawn.reduce((m, l) => (l.rect.w * l.rect.h > m.rect.w * m.rect.h ? l : m))];
    return stops.map((l) => ({ id: l.id, rect: l.rect }));
  });
}

export type Dir = "left" | "right" | "up" | "down";

/** The tile an arrow key moves to from tile `from`: among the tiles whose centre lies beyond `from`'s in that
 *  direction, the one with the smallest gap along the axis, counting the miss across it double (0 when the two
 *  overlap there); then the one whose centre is closest across the axis, then the smaller id. Null at the edge, for
 *  an unknown `from`, or when nothing lies that way. Tiles with no area are not candidates. */
export function neighbour(items: readonly { id: string; rect: Rect }[], from: string, dir: Dir): string | null {
  const src = items.find((i) => i.id === from)?.rect;
  if (!src) return null;
  const horizontal = dir === "left" || dir === "right";
  const sign = dir === "right" || dir === "down" ? 1 : -1;
  const lo = (r: Rect) => (horizontal ? r.x : r.y), len = (r: Rect) => (horizontal ? r.w : r.h);
  const clo = (r: Rect) => (horizontal ? r.y : r.x), clen = (r: Rect) => (horizontal ? r.h : r.w);
  const mid = (r: Rect) => lo(r) + len(r) / 2, cmid = (r: Rect) => clo(r) + clen(r) / 2;
  let best: { id: string; cost: number; off: number } | null = null;
  for (const it of items) {
    const r = it.rect;
    if (it.id === from || r.w <= 0 || r.h <= 0 || (mid(r) - mid(src)) * sign <= 0) continue;
    const gap = Math.max(sign > 0 ? lo(r) - (lo(src) + len(src)) : lo(src) - (lo(r) + len(r)), 0);
    const miss = Math.max(clo(r) - (clo(src) + clen(src)), clo(src) - (clo(r) + clen(r)), 0);
    const cost = gap + 2 * miss, off = Math.abs(cmid(r) - cmid(src));
    if (!best || cost < best.cost || (cost === best.cost && (off < best.off || (off === best.off && it.id < best.id)))) {
      best = { id: it.id, cost, off };
    }
  }
  return best ? best.id : null;
}

// ----------------------------------------------------------------------------- failure

/** The reason the server gives when it cannot build a pool, out of the error text `useApi` keeps. That text is
 *  `String(new Error("503: <body>"))`, so it starts with "Error: "; the body is the JSON of
 *  `{"error": "pool_build_failed", "reason": ...}` (oeisbot/dashboard/app.py). Null for any other failure, which
 *  includes the 503 the server sends when there is no database at all. */
export function failureReason(message: string): string | null {
  const m = /^(?:Error: )?503: ([\s\S]*)$/.exec(message.trim());
  if (!m) return null;
  try {
    const body = JSON.parse(m[1]);
    return body && body.error === "pool_build_failed" && typeof body.reason === "string" ? body.reason : null;
  } catch {
    return null;
  }
}
