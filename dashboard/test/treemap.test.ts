import assert from "node:assert/strict";
import { test } from "node:test";
import {
  BIN_LABELS, CHANGE_BINS, LUMP, MAX_ALPHA, MIN_DRAWN_SIDE, MIN_FOCUS_SIDE, NEUTRAL_BIN, changeBin, failureReason, fmtChange, focusOrder, labelFits,
  layoutGroups, neighbour, parseAlpha, pickmapPath, squarify, undrawn, type Dir, type PlacedGroup, type Rect,
} from "../src/treemap.ts";

const area = (r: Rect) => r.w * r.h;
const EPS = 1e-6;

// small deterministic generator, so a failure reproduces
function rng(seed: number) {
  let s = seed >>> 0;
  return () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 2 ** 32; };
}
const heavyTail = (n: number, seed: number) => { const r = rng(seed); return Array.from({ length: n }, () => 1 / (0.05 + r()) ** 2); };

function overlap(a: Rect, b: Rect) {
  const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return w > EPS && h > EPS ? w * h : 0;
}
const inside = (r: Rect, o: Rect) =>
  r.x >= o.x - EPS && r.y >= o.y - EPS && r.x + r.w <= o.x + o.w + EPS && r.y + r.h <= o.y + o.h + EPS;

test("squarify tiles the rectangle: areas proportional, nothing outside, nothing overlapping", () => {
  const box: Rect = { x: 10, y: 20, w: 900, h: 500 };
  for (const [n, seed] of [[1, 1], [2, 2], [7, 3], [60, 4], [300, 5]] as const) {
    const values = heavyTail(n, seed);
    const total = values.reduce((s, v) => s + v, 0);
    const rects = squarify(values, box);
    assert.equal(rects.length, n);
    let sum = 0;
    rects.forEach((r, i) => {
      assert.ok(inside(r, box), `rect ${i} escapes the box`);
      assert.ok(Math.abs(area(r) - (values[i] / total) * area(box)) < 1e-4 * area(box) / n + 1e-6, `area of ${i} not proportional`);
      sum += area(r);
    });
    assert.ok(Math.abs(sum - area(box)) < 1e-4, "areas do not add up to the box");
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) assert.ok(overlap(rects[i], rects[j]) === 0, `${i} overlaps ${j}`);
  }
});

test("squarify keeps input order and gives non-positive values an empty rect", () => {
  const rects = squarify([5, 0, 20, -3, 10], { x: 0, y: 0, w: 100, h: 100 });
  assert.equal(area(rects[1]), 0);
  assert.equal(area(rects[3]), 0);
  assert.ok(area(rects[2]) > area(rects[4]) && area(rects[4]) > area(rects[0]));
  assert.ok(Math.abs(area(rects[0]) + area(rects[2]) + area(rects[4]) - 10000) < EPS);
  assert.deepEqual(squarify([], { x: 0, y: 0, w: 10, h: 10 }), []);
  assert.equal(area(squarify([1, 2], { x: 0, y: 0, w: 0, h: 10 })[0]), 0);
});

test("squarify keeps tiles reasonably square", () => {
  const rects = squarify(heavyTail(200, 9), { x: 0, y: 0, w: 1200, h: 600 });
  const worst = Math.max(...rects.map((r) => Math.max(r.w / r.h, r.h / r.w)));
  assert.ok(worst < 12, `worst aspect ratio ${worst.toFixed(1)}`);
  const median = rects.map((r) => Math.max(r.w / r.h, r.h / r.w)).sort((a, b) => a - b)[100];
  assert.ok(median < 2.5, `median aspect ratio ${median.toFixed(2)}`);
});

const OPT = { headerH: 16, minLeafArea: 400, pad: 2 };

test("layoutGroups: leaves sit inside their group's frame and fill the part of it drawn to scale", () => {
  const box: Rect = { x: 0, y: 0, w: 1200, h: 600 };
  const groups = [
    { key: "a", leaves: heavyTail(300, 11).map((v, i) => ({ id: `a${i}`, value: v })) },
    { key: "b", leaves: heavyTail(40, 12).map((v, i) => ({ id: `b${i}`, value: v / 3 })) },
    { key: "c", leaves: [{ id: "c0", value: 2 }] },
  ];
  const placed = layoutGroups(groups, box, OPT);
  assert.equal(placed.length, 3);
  const totalArea = placed.reduce((s, g) => s + area(g.rect), 0);
  assert.ok(Math.abs(totalArea - area(box)) < 1e-4);
  for (const g of placed) {
    assert.ok(inside(g.rect, box) && inside(g.inner, g.rect) && inside(g.leaf, g.inner));
    const filled = g.leaves.reduce((s, l) => s + area(l.rect), 0);
    assert.ok(Math.abs(filled - area(g.leaf)) < 1e-3, `${g.key}: leaves fill ${filled}, the leaf box is ${area(g.leaf)}`);
    g.leaves.forEach((l) => assert.ok(inside(l.rect, g.leaf)));
    // the leaf box starts at the frame's corner and is cut along one side only
    assert.ok(g.leaf.x === g.inner.x && g.leaf.y === g.inner.y && (g.leaf.w === g.inner.w || g.leaf.h === g.inner.h));
    for (let i = 0; i < g.leaves.length; i++) for (let j = i + 1; j < g.leaves.length; j++)
      assert.ok(overlap(g.leaves[i].rect, g.leaves[j].rect) === 0);
  }
});

test("layoutGroups: small leaves share one lump that holds exactly the members left out", () => {
  const box: Rect = { x: 0, y: 0, w: 1200, h: 600 };
  const leaves = heavyTail(500, 21).map((v, i) => ({ id: `s${i}`, value: v }));
  const [g] = layoutGroups([{ key: "only", leaves }], box, OPT);
  const lump = g.leaves.filter((l) => l.members);
  assert.equal(lump.length, 1);
  assert.equal(lump[0].id, LUMP + "only");
  const single = g.leaves.filter((l) => !l.members);
  assert.ok(single.length > 0 && single.length < 500);
  single.forEach((l) => assert.ok(area(l.rect) >= OPT.minLeafArea - 1e-6, `${l.id} drawn alone at ${area(l.rect)} px²`));
  // every leaf is either drawn alone or in the lump, once
  const seen = [...single.map((l) => l.id), ...lump[0].members!];
  assert.equal(new Set(seen).size, 500);
  assert.equal(seen.length, 500);
  // the lump is worth the sum of what it holds
  const value = new Map(leaves.map((l) => [l.id, l.value]));
  const lumpValue = lump[0].members!.reduce((s, id) => s + value.get(id)!, 0);
  const total = leaves.reduce((s, l) => s + l.value, 0);
  assert.ok(Math.abs(area(lump[0].rect) / area(g.leaf) - lumpValue / total) < 1e-6);
  // every member of the lump would have been smaller than the threshold on its own
  lump[0].members!.forEach((id) => assert.ok((value.get(id)! / total) * area(g.leaf) < OPT.minLeafArea));
});

test("layoutGroups: a lone small leaf is drawn as itself, not as a lump of one", () => {
  const box: Rect = { x: 0, y: 0, w: 600, h: 300 };
  const [g] = layoutGroups([{ key: "g", leaves: [{ id: "big", value: 1000 }, { id: "tiny", value: 0.001 }] }], box, OPT);
  assert.equal(g.leaves.filter((l) => l.members).length, 0);
  assert.deepEqual(g.leaves.map((l) => l.id).sort(), ["big", "tiny"]);
});

test("layoutGroups: a header only where there is room for it", () => {
  const placed = layoutGroups(
    [{ key: "wide", leaves: [{ id: "w", value: 1000 }] }, { key: "sliver", leaves: [{ id: "s", value: 1 }] }],
    { x: 0, y: 0, w: 1000, h: 400 }, OPT);
  assert.equal(placed[0].header, true);
  assert.equal(placed[1].header, false);
  assert.equal(placed[1].inner.y, placed[1].rect.y + OPT.pad);
});

test("changeBin: seven classes, edges where the legend says", () => {
  assert.equal(CHANGE_BINS, 7);
  assert.equal(BIN_LABELS.length, CHANGE_BINS);
  const cases: [number, number][] = [
    [0.1, 0], [0.5, 0], [0.55, 0], [0.5501, 1], [0.9, 1], [0.9001, 2], [0.9899, 2], [0.99, 3], [1, 3], [1.01, 3],
    [1.0101, 4], [1.0999, 4], [1.1, 5], [1.7999, 5], [1.8, 6], [30, 6],
  ];
  for (const [r, bin] of cases) assert.equal(changeBin(r), bin, `ratio ${r}`);
  assert.equal(changeBin(1), NEUTRAL_BIN);
});

test("changeBin: one failed attempt (difficulty x2, so the chance x ~0.5 at alpha 1) is far from a class edge", () => {
  for (const r of [0.4995, 0.5, 0.5026]) assert.equal(changeBin(r), 0, `ratio ${r}`);
});

test("layoutGroups: a leaf marked keep is drawn on its own however small, and is not in the lump", () => {
  const box: Rect = { x: 0, y: 0, w: 1200, h: 600 };
  const leaves = heavyTail(500, 21).map((v, i) => ({ id: `s${i}`, value: v, keep: i === 499 || i === 3 }));
  const [g] = layoutGroups([{ key: "only", leaves }], box, OPT);
  const lump = g.leaves.find((l) => l.members)!;
  for (const id of ["s499", "s3"]) {
    assert.ok(g.leaves.some((l) => l.id === id && !l.members), `${id} is drawn alone`);
    assert.ok(!lump.members!.includes(id), `${id} is not in the lump`);
  }
  const seen = [...g.leaves.filter((l) => !l.members).map((l) => l.id), ...lump.members!];
  assert.equal(new Set(seen).size, 500);
  assert.equal(seen.length, 500);
  const filled = g.leaves.reduce((s, l) => s + area(l.rect), 0);
  assert.ok(Math.abs(filled - area(g.leaf)) < 1e-3);
});

test("layoutGroups: when every leaf is equal (alpha 0) a big group becomes one lump, a small one stays tiles", () => {
  const box: Rect = { x: 0, y: 0, w: 1200, h: 600 };
  const equal = (n: number, p: string, value = 1) => Array.from({ length: n }, (_, i) => ({ id: `${p}${i}`, value }));
  const [big, small] = layoutGroups([{ key: "big", leaves: equal(3000, "b") }, { key: "small", leaves: equal(4, "s", 500) }],
    box, OPT);
  assert.equal(big.leaves.length, 1);
  assert.equal(big.leaves[0].members!.length, 3000);
  assert.equal(small.leaves.filter((l) => l.members).length, 0);
  assert.equal(small.leaves.length, 4);
});

test("changeBin is monotone in the ratio", () => {
  let last = -1;
  for (let r = 0.01; r < 5; r += 0.001) { const b = changeBin(r); assert.ok(b >= last, `drops at ${r}`); last = b; }
});

test("fmtChange: signed percent with a typeset minus, no negative zero", () => {
  assert.equal(fmtChange(0.5), "−50%");
  assert.equal(fmtChange(2), "+100%");
  assert.equal(fmtChange(1.126), "+13%");
  assert.equal(fmtChange(1.034), "+3.4%");
  assert.equal(fmtChange(1.004), "+0.40%");
  assert.equal(fmtChange(0.996), "−0.40%");
  assert.equal(fmtChange(1), "0%");
  assert.equal(fmtChange(1.00001), "0%");
  assert.equal(fmtChange(0.99999), "0%");
});

test("fmtChange: the figure never reads as the next colour class, and both sides of an edge are written alike", () => {
  // each of these used to round over the edge of its class: "−10.0%" on a tile coloured "down 1 to 10%"
  assert.equal(fmtChange(0.90001), "−9.9%");
  assert.equal(fmtChange(1.09999), "+9.9%");
  assert.equal(fmtChange(0.5501), "−44%");
  assert.equal(fmtChange(1.7996), "+79%");
  // exactly on an edge: in the outer class, and written without a stray decimal on one side only
  assert.equal(fmtChange(0.9), "−10%");
  assert.equal(fmtChange(1.1), "+10%");
  assert.equal(fmtChange(0.55), "−45%");
  assert.equal(fmtChange(1.8), "+80%");
  // for every ratio: the class of the figure shown is the class of the tile, or the figure sits on the edge of it
  let seed = 5;
  const rnd = () => (seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 2 ** 32;
  const edges = [0.55, 0.9, 0.99, 1.01, 1.1, 1.8];
  const samples = [...Array.from({ length: 20000 }, () => 0.3 + rnd() * 1.9),
    ...edges.flatMap((e) => [-3e-4, -1e-5, -1e-9, 0, 1e-9, 1e-5, 3e-4].map((d) => e + d))];
  for (const ratio of samples) {
    const text = fmtChange(ratio);
    const shown = text === "0%" ? 1 : 1 + Number(text.replace("−", "-").replace("%", "")) / 100;
    const onEdge = edges.some((e) => Math.abs(shown - e) < 1e-9);
    assert.ok(onEdge || changeBin(shown) === changeBin(ratio) || text === "0%", `${ratio} is shown as ${text}`);
    if (onEdge && Math.abs(shown - 1) > 0.02) {
      // on an outer edge the tile must really be in the outer class (the edge belongs to it)
      assert.ok(Math.abs(ratio - 1) >= Math.abs(shown - 1) - 1e-9, `${ratio} is shown as ${text}, beyond itself`);
    }
  }
});

test("labelFits needs room for the text plus padding", () => {
  assert.equal(labelFits({ x: 0, y: 0, w: 60, h: 20 }, 7), true);
  assert.equal(labelFits({ x: 0, y: 0, w: 40, h: 20 }, 7), false);
  assert.equal(labelFits({ x: 0, y: 0, w: 60, h: 20 }, 7, 2), false);
});

test("layoutGroups: a header exactly where the group is at least 2.5 header-heights tall and 90 wide", () => {
  const one = (w: number, h: number) => layoutGroups([{ key: "g", leaves: [{ id: "x", value: 1 }] }], { x: 0, y: 0, w, h }, OPT)[0];
  const h = OPT.headerH * 2.5;
  assert.equal(one(200, h).header, true);
  assert.equal(one(200, h - 0.01).header, false);
  assert.equal(one(90, 200).header, true);
  assert.equal(one(89.99, 200).header, false);
  const withHeader = one(200, 200), without = one(200, h - 0.01);
  assert.equal(withHeader.inner.y, OPT.headerH + OPT.pad);
  assert.equal(withHeader.inner.h, 200 - OPT.headerH - 2 * OPT.pad);
  assert.equal(without.inner.y, OPT.pad);
  assert.equal(without.inner.h, h - 0.01 - 2 * OPT.pad);
});

// The pools of 2026-11-17 at alpha 1, band by band: how many sequences and what share of the picks
// (data/item56/pickmap_pari.json and pickmap_model.json). The model pool has a band of 9,395.
const REAL_BANDS: [number, number][] = [[797, 0.53902585], [537, 0.21441558], [290, 0.07827056], [153, 0.02950805],
  [546, 0.06801573], [701, 0.05692354], [306, 0.01316023], [25, 0.00065856], [2, 0.00002189]];
const MODEL_BANDS: [number, number][] = [[1573, 0.199557], [2727, 0.195378], [1052, 0.0544509], [9395, 0.377329],
  [3260, 0.0806917], [3529, 0.058533], [3783, 0.0285442], [1144, 0.00486185], [282, 0.000653579]];
// the page's own height rule and options, as pickmap.tsx has them
const pageHeight = (w: number) => Math.round(Math.min(680, Math.max(380, w * 0.55)));
const pageOpt = (w: number, h: number) => ({ headerH: 18, minLeafArea: Math.max(36, (w * h) / 9000), pad: 2 });
const bandGroups = (bands: [number, number][]) => bands.map(([n, share], i) =>
  ({ key: `b${i}`, leaves: Array.from({ length: n }, (_, k) => ({ id: `b${i}-${k}`, value: share / n })) }));

test("layoutGroups: one unit of pick chance is the same area in every band drawn to scale, at every width the page has", () => {
  // Every integer width, because the old balancing loop passed at the three sizes its test picked and left the
  // bands up to 2x apart at others (5% or more apart at 542 of these 999 widths).
  for (const bands of [REAL_BANDS, MODEL_BANDS]) {
    const groups = bandGroups(bands);
    let emptiest = 0;
    for (let w = 200; w <= 1198; w++) {
      const h = pageHeight(w);
      const placed = layoutGroups(groups, { x: 0, y: 0, w, h }, pageOpt(w, h));
      const scaled = placed.filter((g) => g.scaled);
      assert.ok(scaled.length >= 5, `${w}: only ${scaled.length} bands drawn to scale`);
      const perUnit = scaled.map((g) => area(g.leaf) / g.value);
      const spread = Math.max(...perUnit) / Math.min(...perUnit);
      assert.ok(spread < 1 + 1e-9, `${w}x${h}: area per unit of chance differs by a factor ${spread} between bands`);
      // and the tiles inside a band are at that scale too: every leaf (a lump as the sum of its members)
      for (const g of scaled) {
        const drawn = g.leaves.reduce((s, l) => s + area(l.rect), 0);
        assert.ok(Math.abs(drawn / g.value / perUnit[0] - 1) < 1e-6, `${w}: band ${g.key}`);
        assert.ok(inside(g.leaf, g.inner) && inside(g.inner, g.rect));
      }
      // a band not drawn to scale is exactly one `undrawn` names, so the page says so under the map
      assert.deepEqual(placed.filter((g) => !g.scaled).map((g) => g.key), undrawn(placed));
      assert.ok(Math.abs(placed.reduce((s, g) => s + area(g.rect), 0) - w * h) < 1e-3, "the band rects must still tile the canvas");
      emptiest = Math.max(emptiest, 1 - scaled.reduce((s, g) => s + area(g.leaf), 0) / scaled.reduce((s, g) => s + area(g.inner), 0));
    }
    // the price of the common scale: framed area left empty. Measured 23.5% (PARI) and 25.0% (model) at worst.
    assert.ok(emptiest < 0.3, `up to ${(emptiest * 100).toFixed(1)}% of the framed area is empty`);
  }
});

test("layoutGroups: the scale is set by the tightest band that has room, and the others leave the difference empty", () => {
  const opt = { headerH: 18, minLeafArea: 36, pad: 2 };
  const groups = [{ key: "a", leaves: [{ id: "a1", value: 6 }] }, { key: "b", leaves: [{ id: "b1", value: 3 }] },
                  { key: "c", leaves: [{ id: "c1", value: 1 }] }];
  const placed = layoutGroups(groups, { x: 0, y: 0, w: 400, h: 200 }, opt);
  const per = placed.map((g) => area(g.leaf) / g.value);
  assert.ok(Math.max(...per) / Math.min(...per) < 1 + 1e-12);
  assert.ok(placed.every((g) => g.scaled));
  const room = placed.map((g) => area(g.inner) / g.value);
  const tight = placed[room.indexOf(Math.min(...room))];
  assert.deepEqual(tight.leaf, tight.inner);                                   // the tightest band is full
  const roomy = placed.filter((g) => area(g.leaf) < area(g.inner) - 1);
  assert.ok(roomy.length > 0);                                                 // and another one is not
  // what is left empty is a strip off the end of the longer side, so the tiles keep the box's better proportions
  for (const g of roomy) {
    if (g.inner.w >= g.inner.h) assert.ok(g.leaf.w < g.inner.w && g.leaf.h === g.inner.h, g.key);
    else assert.ok(g.leaf.h < g.inner.h && g.leaf.w === g.inner.w, g.key);
  }
});

test("layoutGroups: a group with no room for tiles is not drawn to scale and does not set the scale", () => {
  // the gap in the values is what makes the first group's rect a sliver: it must neither be blown up to make up
  // for its frame nor drag every other group down to its scale
  const values = [0.00003, 0.03, 0.01, 0.001, 0.003, 0.03];
  const groups = values.map((v, i) => ({ key: `g${i}`, leaves: [{ id: `l${i}`, value: v }] }));
  const placed = layoutGroups(groups, { x: 0, y: 0, w: 1000, h: 600 }, { headerH: 18, minLeafArea: 36, pad: 2 });
  assert.equal(placed[0].scaled, false);
  assert.deepEqual(undrawn(placed), ["g0"]);
  assert.deepEqual(placed[0].leaf, placed[0].inner);              // it fills what little it has
  const scaled = placed.filter((g) => g.scaled);
  assert.equal(scaled.length, 5);
  const perUnit = scaled.map((g) => area(g.leaf) / g.value);
  assert.ok(Math.max(...perUnit) / Math.min(...perUnit) < 1 + 1e-9);
  // the others still use most of the canvas: the sliver did not set the scale
  assert.ok(scaled.reduce((s, g) => s + area(g.leaf), 0) > 0.6 * 1000 * 600);
});

test("layoutGroups: a band too dense for tiles is one lump on its own tab, and a keyboard can reach it", () => {
  // the model pool's band of 9,395 at the default width: every tile would be under the 36 px² floor
  const leaves = Array.from({ length: 9395 }, (_, k) => ({ id: `s${k}`, value: 1 / 9395 }));
  const [g] = layoutGroups([{ key: "b3", leaves }], { x: 0, y: 0, w: 600, h: 380 }, { headerH: 0, minLeafArea: Math.max(36, (600 * 380) / 9000), pad: 2 });
  assert.equal(g.leaves.length, 1);
  assert.equal(g.leaves[0].members!.length, 9395);
  assert.deepEqual(focusOrder([g], true).map((i) => i.id), [LUMP + "b3"]);
  assert.deepEqual(focusOrder([g], false), []);
});

test("layoutGroups: empty groups, zero values and a group the frame would swallow give finite rects that still tile", () => {
  const box: Rect = { x: 0, y: 0, w: 400, h: 300 };
  const groups = [
    { key: "none", leaves: [] },
    { key: "zero", leaves: [{ id: "z", value: 0 }] },
    { key: "big", leaves: [{ id: "b", value: 1000 }] },
    { key: "speck", leaves: [{ id: "s1", value: 0.01 }, { id: "s2", value: 0.01 }] },
  ];
  const placed = layoutGroups(groups, box, OPT);
  for (const g of placed) for (const r of [g.rect, g.inner, ...g.leaves.map((l) => l.rect)])
    for (const v of [r.x, r.y, r.w, r.h]) assert.ok(Number.isFinite(v), `${g.key}: ${JSON.stringify(r)}`);
  assert.ok(Math.abs(placed.reduce((s, g) => s + area(g.rect), 0) - area(box)) < 1e-3);
  assert.equal(area(placed[0].rect) + area(placed[1].rect), 0);
  assert.deepEqual(layoutGroups([], box, OPT), []);
});

test("parseAlpha: a number from 0 to the server's limit, nothing else", () => {
  assert.equal(MAX_ALPHA, 6);
  for (const [text, want] of [["1", 1], ["0", 0], ["6", 6], [" 2.5 ", 2.5], ["0.25", 0.25], ["1e0", 1]] as const) assert.equal(parseAlpha(text), want, text);
  for (const text of ["", "  ", "-0.1", "6.01", "7", "abc", "1,5", "Infinity", "NaN", "--1"]) assert.equal(parseAlpha(text), null, JSON.stringify(text));
});

test("pickmapPath: the rebuild flag appears once a rebuild is asked for, with a counter that makes each request new", () => {
  assert.equal(pickmapPath("pari", 1), "/api/pickmap?pool=pari&alpha=1");
  assert.equal(pickmapPath("model", 0.25), "/api/pickmap?pool=model&alpha=0.25");
  assert.equal(pickmapPath("pari", 1, 0), "/api/pickmap?pool=pari&alpha=1");
  assert.equal(pickmapPath("pari", 1, 3), "/api/pickmap?pool=pari&alpha=1&refresh=true&v=3");
  assert.notEqual(pickmapPath("pari", 1, 1), pickmapPath("pari", 1, 2));
});

// ----------------------------------------------------------------------------- undrawn

const bare = (key: string, inner: Rect): PlacedGroup =>
  ({ key, value: 0, rect: inner, inner, leaf: inner, scaled: Math.min(inner.w, inner.h) >= MIN_DRAWN_SIDE, header: false, leaves: [] });

test("undrawn: a group is listed when either side of its inner rect is under the limit, edge included, in layout order", () => {
  assert.equal(MIN_DRAWN_SIDE, 6);
  const at = (w: number, h: number) => bare("g", { x: 0, y: 0, w, h });
  assert.deepEqual(undrawn([at(5.99, 400)]), ["g"]);
  assert.deepEqual(undrawn([at(400, 5.99)]), ["g"]);
  assert.deepEqual(undrawn([at(6, 6)]), []);                     // exactly the limit is drawn
  assert.deepEqual(undrawn([at(0, 0)]), ["g"]);                  // no area at all
  assert.deepEqual(undrawn([at(4.4, 400)]), ["g"]);             // band 7 at some widths: a sliver
  assert.deepEqual(undrawn([at(8.2, 400)]), []);                // and at others, wide enough to point at
  assert.deepEqual(undrawn([]), []);
  const many = [bare("a", { x: 0, y: 0, w: 300, h: 300 }), bare("b", { x: 0, y: 0, w: 2, h: 300 }),
                bare("c", { x: 0, y: 0, w: 100, h: 100 }), bare("d", { x: 0, y: 0, w: 100, h: 0 })];
  assert.deepEqual(undrawn(many), ["b", "d"]);
  assert.deepEqual(undrawn([at(10, 10)], 12), ["g"]);           // the limit is a parameter
});

test("undrawn: on a real layout it names the bands that are a hair of the picks and not the large ones", () => {
  const leaves = (n: number, each: number, tag: string) => Array.from({ length: n }, (_, i) => ({ id: `${tag}-${i}`, value: each }));
  const groups = [{ key: "b0", leaves: leaves(40, 0.0135, "x") }, { key: "b1", leaves: leaves(20, 0.0135, "y") },
                  { key: "b2", leaves: [{ id: "tiny1", value: 0.00002 }, { id: "tiny2", value: 0.00002 }] }];
  const opt = { headerH: 18, minLeafArea: 36, pad: 2 };
  const placed = layoutGroups(groups, { x: 0, y: 0, w: 900, h: 500 }, opt);
  assert.ok(placed[0].inner.w > 100 && placed[1].inner.w > 100);          // the two big bands have room ...
  assert.deepEqual(undrawn(placed), ["b2"]);                              // ... and only the speck is listed
  // the same bands in a box where nothing has room for a tile
  const squeezed = layoutGroups(groups, { x: 0, y: 0, w: 10, h: 10 }, opt);
  assert.deepEqual(undrawn(squeezed), ["b0", "b1", "b2"]);
});

// ----------------------------------------------------------------------------- neighbour

/** Nine 10x10 tiles, ids 'a'..'i' in reading order: a b c / d e f / g h i. */
const grid = (): { id: string; rect: Rect }[] =>
  "abcdefghi".split("").map((id, i) => ({ id, rect: { x: (i % 3) * 10, y: Math.floor(i / 3) * 10, w: 10, h: 10 } }));

test("neighbour: the four arrows move one tile on a grid, and nothing lies past the edge", () => {
  const g = grid();
  const want: Record<Dir, string> = { left: "d", right: "f", up: "b", down: "h" };
  for (const dir of ["left", "right", "up", "down"] as Dir[]) assert.equal(neighbour(g, "e", dir), want[dir], dir);
  assert.equal(neighbour(g, "a", "left"), null);
  assert.equal(neighbour(g, "a", "up"), null);
  assert.equal(neighbour(g, "i", "right"), null);
  assert.equal(neighbour(g, "i", "down"), null);
  assert.equal(neighbour(g, "g", "down"), null);
  assert.equal(neighbour(g, "a", "right"), "b");
  assert.equal(neighbour(g, "c", "left"), "b");        // 'e' touches c at a corner, but 'b' is level with it
  assert.equal(neighbour(g, "i", "up"), "f");          // likewise 'e' at the corner
});

test("neighbour: an unknown source or an empty list gives null; a tile with no area is never a target", () => {
  assert.equal(neighbour(grid(), "nope", "right"), null);
  assert.equal(neighbour([], "a", "right"), null);
  const items = [{ id: "a", rect: { x: 0, y: 0, w: 10, h: 10 } }, { id: "ghost", rect: { x: 10, y: 0, w: 0, h: 10 } },
                 { id: "z", rect: { x: 10, y: 0, w: 10, h: 10 } }];
  assert.equal(neighbour(items, "a", "right"), "z");
  assert.equal(neighbour(items.slice(0, 2), "a", "right"), null);     // only the empty tile lies that way
  const flat = [items[0], { id: "flat", rect: { x: 10, y: 0, w: 10, h: 0 } }, { id: "z", rect: { x: 30, y: 0, w: 10, h: 10 } }];
  assert.equal(neighbour(flat, "a", "right"), "z");                   // a tile with a width but no height is no target either
  assert.equal(neighbour(flat.slice(0, 2), "a", "right"), null);
});

test("neighbour: leftward and upward the gap is measured to the candidate's near edge, as it is rightward and downward", () => {
  const wide = { x: 0, w: 40 }, narrow = { x: 20, w: 8 };            // 10 px and 22 px short of a source that starts at 50
  const row = [{ id: "src", rect: { x: 50, y: 0, w: 10, h: 10 } }, { id: "wide", rect: { ...wide, y: 0, h: 10 } },
               { id: "narrow", rect: { ...narrow, y: 0, h: 10 } }];
  assert.equal(neighbour(row, "src", "left"), "wide");
  const col = [{ id: "src", rect: { x: 0, y: 50, w: 10, h: 10 } }, { id: "wide", rect: { x: 0, y: wide.x, w: 10, h: wide.w } },
               { id: "narrow", rect: { x: 0, y: narrow.x, w: 10, h: narrow.w } }];
  assert.equal(neighbour(col, "src", "up"), "wide");
  const mirrored = [{ id: "src", rect: { x: 0, y: 0, w: 10, h: 10 } }, { id: "wide", rect: { x: 20, y: 0, w: 40, h: 10 } },
                    { id: "narrow", rect: { x: 32, y: 0, w: 8, h: 10 } }];     // the same, rightward: the nearer edge wins
  assert.equal(neighbour(mirrored, "src", "right"), "wide");
});

test("neighbour: the miss across the axis is counted twice exactly, from either side, and an overlap earns nothing", () => {
  const s = { id: "s", rect: { x: 0, y: 0, w: 10, h: 10 } };
  // doubled, not tripled: X touches but is 10 px off across (0 + 2 x 10 = 20), Y is level but 25 px away
  const x = { id: "x", rect: { x: 10, y: 20, w: 10, h: 10 } }, y = { id: "y", rect: { x: 35, y: 0, w: 10, h: 10 } };
  assert.equal(neighbour([s, x, y], "s", "right"), "x");
  // a miss above counts as much as a miss below
  const low = { id: "low", rect: { x: 0, y: 100, w: 10, h: 10 } };
  const above = { id: "above", rect: { x: 10, y: 0, w: 10, h: 10 } }, level = { id: "level", rect: { x: 60, y: 100, w: 10, h: 10 } };
  assert.equal(neighbour([low, above, level], "low", "right"), "level");
  // a tile that overlaps the source across the axis is not cheaper for overlapping more: the gap decides
  const tall = { id: "tall", rect: { x: 0, y: 0, w: 10, h: 40 } };
  const far = { id: "far", rect: { x: 20, y: 0, w: 10, h: 40 } }, near = { id: "near", rect: { x: 15, y: 10, w: 10, h: 10 } };
  assert.equal(neighbour([tall, far, near], "tall", "right"), "near");
});

test("neighbour: among tiles of different sizes it picks the one level with the source's centre, not the one that is nearest", () => {
  // a tall tile on the left; on its right a thin tile at the top and a big one below it
  const items = [
    { id: "tall", rect: { x: 0, y: 0, w: 10, h: 100 } },
    { id: "top", rect: { x: 10, y: 0, w: 90, h: 10 } },
    { id: "bottom", rect: { x: 10, y: 10, w: 90, h: 90 } },
  ];
  // both abut `tall`; the centre of 'bottom' (y 55) is closer to tall's (y 50) than that of 'top' (y 5)
  assert.equal(neighbour(items, "tall", "right"), "bottom");
  assert.equal(neighbour(items, "bottom", "left"), "tall");
  assert.equal(neighbour(items, "top", "left"), "tall");
  assert.equal(neighbour(items, "top", "down"), "bottom");
  assert.equal(neighbour(items, "bottom", "up"), "top");
});

test("neighbour: a tile that abuts beats a nearer-looking one off to the side, and the miss across the axis counts double", () => {
  const items = [
    { id: "s", rect: { x: 0, y: 0, w: 10, h: 10 } },
    { id: "abuts", rect: { x: 10, y: 0, w: 10, h: 10 } },
    { id: "diag", rect: { x: 10, y: 30, w: 10, h: 10 } },       // no gap along the axis, 20 px off across it
    { id: "far", rect: { x: 40, y: 0, w: 10, h: 10 } },
  ];
  assert.equal(neighbour(items, "s", "right"), "abuts");
  // with the abutting tile gone, the diagonal (0 + 2 x 20 = 40) loses to the far one in line (30)
  assert.equal(neighbour(items.filter((i) => i.id !== "abuts"), "s", "right"), "far");
  // and with only the diagonal it is still reachable
  assert.equal(neighbour(items.filter((i) => i.id === "s" || i.id === "diag"), "s", "right"), "diag");
});

test("neighbour: ties go to the closer centre across the axis, then to the smaller id, whatever the input order", () => {
  const m = { id: "m", rect: { x: 0, y: 10, w: 10, h: 10 } };
  const r1 = { id: "r1", rect: { x: 10, y: 0, w: 10, h: 10 } };       // both abut m; r2 is level with it, r1 is 10 px off
  const r2 = { id: "r2", rect: { x: 10, y: 10, w: 10, h: 10 } };
  assert.equal(neighbour([m, r1, r2], "m", "right"), "r2");
  assert.equal(neighbour([r2, r1, m], "m", "right"), "r2");
  const a = { id: "a", rect: { x: 10, y: 0, w: 10, h: 10 } };         // 10 px above and 10 px below: an exact tie
  const b = { id: "b", rect: { x: 10, y: 20, w: 10, h: 10 } };
  assert.equal(neighbour([m, b, a], "m", "right"), "a");
  assert.equal(neighbour([m, a, b], "m", "right"), "a");
});

test("neighbour: on a layout, every arrow walk ends, and arrow keys together reach every tile", () => {
  for (const seed of [7, 8, 9]) {
    const r = rng(seed);
    const leaves = Array.from({ length: 150 }, (_, i) => ({ id: `t${String(i).padStart(3, "0")}`, value: 1 / (0.05 + r()) ** 2 }));
    const placed = layoutGroups([{ key: "g", leaves }], { x: 0, y: 0, w: 800, h: 500 }, { headerH: 0, minLeafArea: 0, pad: 0 });
    const items = placed[0].leaves.map((l) => ({ id: l.id, rect: l.rect }));
    assert.equal(items.length, 150);
    for (const dir of ["left", "right", "up", "down"] as Dir[]) {
      for (const start of items) {
        let at = start.id, steps = 0;
        for (;;) {
          const next = neighbour(items, at, dir);
          if (next === null) break;
          assert.notEqual(next, at);
          at = next;
          assert.ok(++steps <= items.length, `${dir} from ${start.id} never ends`);      // every step moves the centre onwards
        }
      }
    }
    const seen = new Set([items[0].id]);
    const todo = [items[0].id];
    while (todo.length) {
      const at = todo.pop()!;
      for (const dir of ["left", "right", "up", "down"] as Dir[]) {
        const next = neighbour(items, at, dir);
        if (next !== null && !seen.has(next)) { seen.add(next); todo.push(next); }
      }
    }
    assert.equal(seen.size, items.length, `seed ${seed}: ${items.length - seen.size} tiles cannot be reached by arrow keys`);
  }
});

// ----------------------------------------------------------------------------- failureReason

test("failureReason: the reason out of the text useApi keeps for a 503 with the server's JSON, and null for everything else", () => {
  const body = JSON.stringify({ error: "pool_build_failed", reason: "OperationalError: database is locked" });
  // useApi throws new Error(`${status}: ${body}`) and stores String(e), which starts with 'Error: '
  const kept = String(new Error(`503: ${body}`));
  assert.equal(kept, `Error: 503: ${body}`);
  assert.equal(failureReason(kept), "OperationalError: database is locked");
  assert.equal(failureReason(`503: ${body}`), "OperationalError: database is locked");         // without the prefix too
  assert.equal(failureReason(`  ${kept}\n`), "OperationalError: database is locked");
  const awkward = 'x: y "quoted" \\ z';
  assert.equal(failureReason(String(new Error(`503: ${JSON.stringify({ error: "pool_build_failed", reason: awkward })}`))), awkward);
  const pretty = JSON.stringify({ error: "pool_build_failed", reason: "KeyError: 'A000001'" }, null, 2);     // a body over several lines
  assert.ok(pretty.includes("\n"));
  assert.equal(failureReason(String(new Error(`503: ${pretty}`))), "KeyError: 'A000001'");
  for (const other of [
    String(new Error('503: {"detail":"no database at C:\\\\x; run `oeisbot setup`"}')),         // FastAPI's own 503
    String(new Error("500: Internal Server Error")),
    String(new Error(`500: ${body}`)),                                                         // the code is part of the contract
    String(new Error(`404: ${body}`)),
    String(new Error('503: {"error":"something_else","reason":"r"}')),
    String(new Error('503: {"error":"pool_build_failed"}')),
    String(new Error('503: {"error":"pool_build_failed","reason":7}')),
    String(new Error("503: not json")),
    String(new Error("503: ")),
    String(new Error("503: null")),
    String(new Error(`1503: ${body}`)),                                                        // the status is the whole number
    String(new Error(`Error: 404: 503: ${body}`)),
    "TypeError: Failed to fetch",
    "",
  ]) assert.equal(failureReason(other), null, other);
});

// ----------------------------------------------------------------------------- focusOrder

test("focusOrder: layout order, leaving out the leaves of a group too small to see, tiles with no area, and (unless asked for) lumps", () => {
  const placed = (key: string, inner: Rect, leaves: { id: string; rect: Rect; members?: string[] }[]): PlacedGroup =>
    ({ key, value: 1, rect: inner, inner, leaf: inner, scaled: Math.min(inner.w, inner.h) >= MIN_DRAWN_SIDE, header: false, leaves: leaves.map((l) => ({ id: l.id, rect: l.rect, members: l.members ?? null })) });
  const r = (x: number, w: number, h = 40): Rect => ({ x, y: 0, w, h });
  const layout = [
    placed("b0", { x: 0, y: 0, w: 100, h: 40 }, [{ id: "a1", rect: r(0, 50) }, { id: "a2", rect: r(50, 30) }, { id: `${LUMP}b0`, rect: r(80, 20), members: ["z1", "z2"] }]),
    placed("b1", { x: 100, y: 0, w: 4, h: 40 }, [{ id: "s1", rect: r(100, 4) }]),                    // 4 px wide: not drawn
    placed("b2", { x: 104, y: 0, w: 60, h: 40 }, [{ id: "c1", rect: r(104, 40) }, { id: "ghost", rect: r(144, 0) }, { id: "flat", rect: r(144, 20, 0) }, { id: "c2", rect: r(144, 20) }]),
  ];
  assert.deepEqual(focusOrder(layout, true).map((i) => i.id), ["a1", "a2", `${LUMP}b0`, "c1", "c2"]);
  assert.deepEqual(focusOrder(layout, false).map((i) => i.id), ["a1", "a2", "c1", "c2"]);
  assert.deepEqual(focusOrder(layout, true)[0].rect, r(0, 50));
  assert.deepEqual(focusOrder(layout, true, 3).map((i) => i.id), ["a1", "a2", `${LUMP}b0`, "s1", "c1", "c2"]);   // the limit is a parameter
  assert.deepEqual(focusOrder([], true), []);
  // a group is left out exactly when undrawn() lists it
  const left = new Set(undrawn(layout));
  assert.deepEqual(layout.filter((g) => !left.has(g.key)).map((g) => g.key), ["b0", "b2"]);
});

test("focusOrder: on a layout with a speck band, the arrow keys reach every tile it lists", () => {
  const leaves = (n: number, each: number, tag: string) => Array.from({ length: n }, (_, i) => ({ id: `${tag}-${String(i).padStart(2, "0")}`, value: each }));
  const groups = [{ key: "b0", leaves: leaves(60, 0.01, "x") }, { key: "b1", leaves: leaves(30, 0.01, "y") },
                  { key: "b2", leaves: [{ id: "tiny1", value: 0.00002 }, { id: "tiny2", value: 0.00002 }] }];
  for (const W of [360, 600, 900]) {
    const H = Math.round(Math.min(680, Math.max(380, W * 0.55)));
    const placed = layoutGroups(groups, { x: 0, y: 0, w: W, h: H }, { headerH: 18, minLeafArea: Math.max(36, (W * H) / 9000), pad: 2 });
    assert.deepEqual(undrawn(placed), ["b2"]);
    const items = focusOrder(placed, true);
    assert.ok(items.length > 0 && items.every((i) => !i.id.startsWith("tiny")));
    const seen = new Set([items[0].id]);
    const todo = [items[0].id];
    while (todo.length) {
      const at = todo.pop()!;
      for (const dir of ["left", "right", "up", "down"] as Dir[]) {
        const next = neighbour(items, at, dir);
        if (next !== null && !seen.has(next)) { seen.add(next); todo.push(next); }
      }
    }
    assert.equal(seen.size, items.length, `W=${W}: ${items.length - seen.size} tiles cannot be reached by arrow keys`);
  }
});

test("focusOrder: a tile under three pixels on either side is not a keyboard stop, and the limit is inclusive", () => {
  assert.equal(MIN_FOCUS_SIDE, 3);
  const box: Rect = { x: 0, y: 0, w: 200, h: 40 };
  const g: PlacedGroup = { key: "b0", value: 1, rect: box, inner: box, leaf: box, scaled: true, header: false, leaves: [
    { id: "wide", rect: { x: 0, y: 0, w: 100, h: 40 }, members: null },
    { id: "hair", rect: { x: 100, y: 0, w: 2.99, h: 40 }, members: null },      // a kept tile that came out a hair wide
    { id: "flat", rect: { x: 103, y: 0, w: 40, h: 0.7 }, members: null },
    { id: "three", rect: { x: 143, y: 0, w: 3, h: 3 }, members: null },
  ] };
  assert.deepEqual(focusOrder([g], true).map((i) => i.id), ["wide", "three"]);
  assert.deepEqual(focusOrder([g], true, MIN_DRAWN_SIDE, 0).map((i) => i.id), ["wide", "hair", "flat", "three"]);   // the limit is a parameter
});

test("focusOrder: a drawn band whose tiles are all too small for a stop still gets one, on its largest tile", () => {
  const box: Rect = { x: 0, y: 0, w: 60, h: 60 };
  const tiny = (id: string, x: number, w: number) => ({ id, rect: { x, y: 0, w, h: 2 }, members: null });
  const g: PlacedGroup = { key: "b3", value: 1, rect: box, inner: box, leaf: box, scaled: true, header: false,
    leaves: [tiny("t1", 0, 2), tiny("t2", 2, 2.5), tiny("t3", 4.5, 1)] };
  assert.deepEqual(focusOrder([g], true).map((i) => i.id), ["t2"]);
  // not for a band with nothing drawn, and not when a real stop exists
  assert.deepEqual(focusOrder([{ ...g, leaves: [{ id: "none", rect: { x: 0, y: 0, w: 0, h: 0 }, members: null }] }], true), []);
  assert.deepEqual(focusOrder([{ ...g, leaves: [...g.leaves, { id: "ok", rect: { x: 10, y: 10, w: 9, h: 9 }, members: null }] }], true).map((i) => i.id), ["ok"]);
});
