// Keyboard movement along a row of tabs, and the two labels the page derives from more than one field.
// No imports, as scale.ts, format.ts and treemap.ts have none: node runs the tests straight from this file.

/** The tab the keyboard moves to from `current`, or null when the key is not one of the four that move.
 *
 *  Left and Right step to the neighbour and wrap at the ends; Home and End go to the first and last. Up and
 *  Down are deliberately not here: both tab rows are horizontal, and those keys scroll the page. `current`
 *  is the tab that has the focus, which need not be the selected one, because moving does not select: Enter
 *  or Space on the focused tab does (it is a button). A tab row that selected on every arrow would add a
 *  history entry and start a request for every tab passed over. A `current` that is not in `ids` moves to
 *  the first tab (or the last, for Left and End), so a stale id can never strand the focus. */
export function tabAfter<T>(ids: readonly T[], current: T, key: string): T | null {
  if (ids.length === 0) return null;
  const at = ids.indexOf(current);
  switch (key) {
    case "ArrowRight": return ids[at < 0 ? 0 : (at + 1) % ids.length];
    case "ArrowLeft": return ids[at < 0 ? ids.length - 1 : (at - 1 + ids.length) % ids.length];
    case "Home": return ids[0];
    case "End": return ids[ids.length - 1];
    default: return null;
  }
}

/** Why an `extended` run is not a win, as the Attempts table says it, or null when it is one.
 *
 *  Two different things happened to such runs and the table used to call both "review rejected". A
 *  *rejected* run had a review, and a person rejected it. A *refused* run never had one: its sequence
 *  already had a rejected review, so the pipeline kept the terms and opened nothing (db.record_win). The
 *  second is the more specific fact, so it wins when a row somehow carries both. */
export function notAWin(row: { win_rejected?: boolean; review_refused?: number | boolean | null }): { label: string; title: string } | null {
  if (row.review_refused != null && row.review_refused !== false) {
    const prior = typeof row.review_refused === "number" ? ` (review #${row.review_refused})` : "";
    return { label: "no review opened",
             title: `This sequence already had a rejected review${prior}, so no new review was opened for this run. Its terms and its folder are kept.` };
  }
  if (row.win_rejected) return { label: "review rejected", title: "A person rejected this run's review. Its terms and its folder are kept." };
  return null;
}

/** Whether a click on a Pick map tile acts now (opens the entry, or the band or table of a lump), or only
 *  shows the tile's tooltip and waits for a second one.
 *
 *  A finger cannot hover. On a touch screen the first sign of a tile's tooltip was the browser's own
 *  made-up mouse move a few milliseconds before the click, so a tap opened oeis.org before one word of it
 *  could be read (seen with a simulated tap, item 57). So a touch acts only on the tile whose tooltip the
 *  previous tap put up: `armed` is that tile, and the caller clears it whenever the tooltip goes away or
 *  another tile's takes its place (a hover, a keyboard focus). A mouse, a pen (which hovers) and anything
 *  unknown act at once, as before. Simulated taps only: not seen under a finger, and a screen reader's
 *  activation on a touch device arrives as a touch click too, so it also needs two. */
export function tapActs(pointerType: string | null, armed: string | null, id: string): boolean {
  return pointerType !== "touch" || armed === id;
}

export type Trust = "trusted" | "fit" | "untrusted";

/** How far a projection is trusted: `trusted` (a kill may act on it), `fit` (its cost fit is sound, and the
 *  trust was withdrawn because the rate of work per second was drifting), `untrusted` (the fit itself is
 *  not sound, or nothing could be fitted). `predictions.trustworthy` is the first; `fit_trustworthy` with
 *  it clear is the second. A row stored before the fit's own verdict was kept has a null `fit_trustworthy`
 *  and is `untrusted` unless it is trusted outright. */
export function trustOf(p: { trustworthy: number | boolean; fit_trustworthy?: number | boolean | null }): Trust {
  return p.trustworthy ? "trusted" : p.fit_trustworthy ? "fit" : "untrusted";
}

/** Whether a point passes the Estimator's projection filter: `all`, `trusted`, or `fit` (trusted, or its
 *  cost fit sound). An unknown filter passes everything, so a stale value cannot blank the chart. */
export function passesTrust(filter: string, p: { trustworthy: number | boolean; fit_trustworthy?: number | boolean | null }): boolean {
  const t = trustOf(p);
  return filter === "trusted" ? t === "trusted" : filter === "fit" ? t !== "untrusted" : true;
}
