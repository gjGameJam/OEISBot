import assert from "node:assert/strict";
import { test } from "node:test";
import {
  BIN_LABELS, CHANGE_BINS, LUMP, MAX_ALPHA, NEUTRAL_BIN, changeBin, fmtChange, labelFits, layoutGroups, parseAlpha,
  pickmapPath, squarify, type Rect,
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

test("layoutGroups: leaves sit inside their group and fill its inner box", () => {
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
    assert.ok(inside(g.rect, box) && inside(g.inner, g.rect));
    const filled = g.leaves.reduce((s, l) => s + area(l.rect), 0);
    assert.ok(Math.abs(filled - area(g.inner)) < 1e-3, `${g.key}: leaves fill ${filled}, inner is ${area(g.inner)}`);
    g.leaves.forEach((l) => assert.ok(inside(l.rect, g.inner)));
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
  assert.ok(Math.abs(area(lump[0].rect) / area(g.inner) - lumpValue / total) < 1e-6);
  // every member of the lump would have been smaller than the threshold on its own
  lump[0].members!.forEach((id) => assert.ok((value.get(id)! / total) * area(g.inner) < OPT.minLeafArea));
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
  assert.ok(Math.abs(filled - area(g.inner)) < 1e-3);
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

test("layoutGroups: the same pick chance gets the same area in a small group as in a large one", () => {
  // shares as in the real pool: one band holds half of everything, the others a few percent each
  const shares = [0.539, 0.214, 0.078, 0.0295, 0.068, 0.0569, 0.0132];
  const groups = shares.map((s, i) => ({ key: `b${i}`, leaves: Array.from({ length: 20 }, (_, k) => ({ id: `b${i}-${k}`, value: s / 20 })) }));
  for (const [w, h] of [[1232, 680], [900, 600], [1600, 500]]) {
    const placed = layoutGroups(groups, { x: 0, y: 0, w, h }, { headerH: 18, minLeafArea: 36, pad: 2 });
    const perUnit = placed.map((g) => area(g.inner) / g.value);
    const spread = Math.max(...perUnit) / Math.min(...perUnit);
    assert.ok(spread < 1.02, `${w}x${h}: area per unit of chance differs by ${((spread - 1) * 100).toFixed(1)}% between groups`);
    const rects = placed.reduce((s, g) => s + area(g.rect), 0);
    assert.ok(Math.abs(rects - w * h) < 1e-3, "the group rects must still tile the canvas");
    placed.forEach((g, i) => assert.ok(inside(g.rect, { x: 0, y: 0, w, h }) && (i === 0 || overlap(g.rect, placed[0].rect) === 0)));
  }
});

test("layoutGroups: a group the frame nearly swallows is not blown up to make up for it", () => {
  // Without the MIN_KEPT guard these values spread the area per unit of chance 12-fold between the groups that
  // have room (the measured spread with it is 1.8); the gap in the values is what makes a group's first rect tiny.
  const values = [0.00003, 0.03, 0.01, 0.001, 0.003, 0.03];
  const groups = values.map((v, i) => ({ key: `g${i}`, leaves: [{ id: `l${i}`, value: v }] }));
  const placed = layoutGroups(groups, { x: 0, y: 0, w: 1000, h: 600 }, { headerH: 18, minLeafArea: 36, pad: 2 });
  const perUnit = placed.filter((g) => area(g.inner) >= 1500).map((g) => area(g.inner) / g.value);
  assert.ok(perUnit.length >= 4, `only ${perUnit.length} groups have room`);
  assert.ok(Math.max(...perUnit) / Math.min(...perUnit) < 3);
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
