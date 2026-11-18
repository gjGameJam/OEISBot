import assert from "node:assert/strict";
import { test } from "node:test";
import { actualOrBound, bandCorners, dayColumns, labelEvery, logFraction, niceStep, timeDomain, timeTick } from "../src/scale.ts";

// The estimator's points on 2026-11-17 that the old axis (floor 1 ms) drew outside the plot: seven finished
// terms of A385331 attempt 139, and prediction #12's predicted time.
const BELOW_A_MILLISECOND = [0.000604, 0.000308, 0.000282, 0.000278, 0.000531, 0.00053, 0.000413, 0.000475];

test("the ladder is strictly increasing and its labels are round", () => {
  for (let i = -12; i < 12; i++) assert.ok(timeTick(i).v < timeTick(i + 1).v, `rung ${i}`);
  assert.deepEqual([-7, -6, -4, -3, -1, 0, 1, 2, 3, 4, 5, 6, 8].map((i) => timeTick(i).label),
    ["100 ns", "1 µs", "100 µs", "1 ms", "100 ms", "1 s", "10 s", "1 min", "10 min", "1 h", "1 d", "10 d", "1,000 d"]);
  assert.deepEqual([-9, -3, 0, 1, 2, 3, 4, 5, 6].map((i) => timeTick(i).v), [1e-9, 0.001, 1, 10, 60, 600, 3600, 86400, 864000]);
  assert.equal(timeTick(-9).label, "1 ns");
  assert.equal(timeTick(-10).label, "1e-10 s");
});

test("values that are not positive and finite do not shape the domain", () => {
  assert.deepEqual(timeDomain([0, -1, NaN, Infinity, -Infinity]), timeDomain([]));
  assert.deepEqual(timeDomain([0, 5, NaN, Infinity]), timeDomain([5]));
});

test("a value off the end of the ladder is pulled in and flagged", () => {
  const low = timeDomain([1e-40]);
  assert.equal(low.lo, 1e-30);
  assert.deepEqual(logFraction(1e-40, low.lo, low.hi), { f: 0, clamped: true });
  const high = timeDomain([1e50]);
  assert.equal(high.hi, 86400 * 10 ** 35);
  assert.deepEqual(logFraction(1e50, high.lo, high.hi), { f: 1, clamped: true });
});

test("the domain holds every value, including the ones under a millisecond", () => {
  const values = [...BELOW_A_MILLISECOND, 3821, 153, 12.5];
  const d = timeDomain(values);
  assert.equal(d.lo, 1e-4);
  assert.equal(d.hi, 86400);
  for (const v of values) {
    assert.ok(d.lo <= v && v <= d.hi, `${v} inside`);
    assert.equal(logFraction(v, d.lo, d.hi).clamped, false);
  }
});

test("the domain holds whatever it is given, at any magnitude", () => {
  let seed = 7;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let k = 0; k < 500; k++) {
    const values = Array.from({ length: 1 + Math.floor(rnd() * 6) }, () => 10 ** (rnd() * 40 - 22));
    const d = timeDomain(values);
    assert.ok(d.ticks.length >= 2);
    assert.ok(d.lo < d.hi);
    for (const v of values) assert.ok(d.lo <= v && v <= d.hi, `${v} in [${d.lo}, ${d.hi}]`);
  }
});

test("the domain always has a length: no values, one value, all tiny, all huge", () => {
  // 1e-40 and 1e50 are off both ends of the ladder: the axis still has two ticks, and the point is pulled in
  for (const values of [[], [5], [0, -1, NaN, Infinity], [2e-7, 3e-7], [5e8, 6e8], [1e-3], [86400], [1e-40], [1e50]]) {
    const d = timeDomain(values);
    assert.ok(d.ticks.length >= 2, JSON.stringify(values));
    assert.ok(isFinite(Math.log10(d.hi) - Math.log10(d.lo)) && d.hi > d.lo);
  }
  assert.deepEqual(timeDomain([]).ticks.map((t) => t.label), ["1 ms", "10 ms", "100 ms", "1 s", "10 s"]);
});

test("the domain is no wider than it needs to be", () => {
  const d = timeDomain([0.02, 30]);              // padded: 0.0133 .. 45
  assert.deepEqual(d.ticks.map((t) => t.label), ["10 ms", "100 ms", "1 s", "10 s", "1 min"]);
});

test("a fraction is 0 at the floor, 1 at the top, and flags what it pulled in", () => {
  assert.deepEqual(logFraction(1e-3, 1e-3, 10), { f: 0, clamped: false });
  assert.deepEqual(logFraction(10, 1e-3, 10), { f: 1, clamped: false });
  assert.ok(Math.abs(logFraction(0.1, 1e-3, 10).f - 0.5) < 1e-12);
  for (const v of [0, -3, NaN, 1e-9]) assert.deepEqual(logFraction(v, 1e-3, 10), { f: 0, clamped: true });
  assert.deepEqual(logFraction(1e9, 1e-3, 10), { f: 1, clamped: true });
  assert.deepEqual(logFraction(Infinity, 1e-3, 10), { f: 0, clamped: true });
});

test("the band is within a factor of two of the diagonal along its whole length", () => {
  const lo = 1e-4, hi = 86400;
  const corners = bandCorners(lo, hi);
  for (const [x, y] of corners) {
    assert.ok(lo <= x && x <= hi && lo <= y && y <= hi, `corner ${x},${y} inside the plot`);
    assert.ok(y / x <= 2 + 1e-12 && x / y <= 2 + 1e-12, `corner ${x},${y} within 2x`);
  }
  // the two long edges lie on y = 2x and y = x / 2, which the old polygon's did not
  assert.deepEqual(corners[1], [lo, 2 * lo]);
  assert.deepEqual(corners[2], [hi / 2, hi]);
  assert.deepEqual(corners[4], [hi, hi / 2]);
  assert.deepEqual(corners[5], [2 * lo, lo]);
});

test("prediction #32 (ratio 0.505), the one term counted as within 2x, is inside the band", () => {
  const predicted = 302.8, actual = 153.0;
  const { lo, hi } = timeDomain([predicted, actual, ...BELOW_A_MILLISECOND, 3821]);
  const fx = logFraction(predicted, lo, hi).f, fy = logFraction(actual, lo, hi).f;
  // on log axes the lower edge of the band is the diagonal moved down by log10(2)
  const edge = fx - Math.log10(2) / (Math.log10(hi) - Math.log10(lo));
  assert.ok(fy > edge && fy < fx, `y fraction ${fy} between ${edge} and ${fx}`);
});

test("labels thin out when the ticks crowd", () => {
  assert.equal(labelEvery(100, 48), 1);
  assert.equal(labelEvery(40, 48), 2);
  assert.equal(labelEvery(20, 48), 3);
  assert.equal(labelEvery(0, 48), 1);
});

test("nice steps", () => {
  assert.deepEqual([46, 6.77, 1, 100, 0.3].map(niceStep), [20, 2, 0.5, 50, 0.1]);
  assert.deepEqual([4, 8, 20, 40].map(niceStep), [1, 2, 5, 10]);       // exactly on each boundary
});

test("what the estimator plots: a finished time, else the time it was stopped at, else nothing", () => {
  assert.deepEqual(actualOrBound(1.5, null), { y: 1.5, finished: true });
  assert.deepEqual(actualOrBound(null, 60), { y: 60, finished: false });
  assert.deepEqual(actualOrBound(0, 60), { y: 60, finished: false });     // the server's rule: zero is not finished
  assert.equal(actualOrBound(0, null), null);
  assert.equal(actualOrBound(null, undefined), null);
  assert.equal(actualOrBound(null, 0), null);
});

test("day columns: every calendar day between the first and the last, in UTC", () => {
  const cols = dayColumns(["2026-09-17", "2026-09-18", "2026-09-21"]);
  assert.deepEqual(cols, [
    { kind: "day", day: "2026-09-17", index: 0 }, { kind: "day", day: "2026-09-18", index: 1 },
    { kind: "day", day: "2026-09-19", index: null }, { kind: "day", day: "2026-09-20", index: null },
    { kind: "day", day: "2026-09-21", index: 2 },
  ]);
  assert.deepEqual(dayColumns([]), []);
  assert.deepEqual(dayColumns(["2026-09-17"]), [{ kind: "day", day: "2026-09-17", index: 0 }]);
});

test("day columns: a long quiet stretch is one gap, a short one is its days", () => {
  // the run days of 2026-11-17: nothing on the 23rd, nothing from the 26th to the 28th
  const real = ["2026-09-17", "2026-09-18", "2026-09-19", "2026-09-20", "2026-09-21", "2026-09-22", "2026-09-24",
    "2026-09-25", "2026-09-29", "2026-09-30"];
  const cols = dayColumns(real);
  assert.equal(cols.length, 14);
  assert.deepEqual(cols.filter((c) => c.kind === "day" && c.index == null).map((c) => c.kind === "day" && c.day),
    ["2026-09-23", "2026-09-26", "2026-09-27", "2026-09-28"]);
  assert.deepEqual(dayColumns(["2026-09-30", "2026-10-05"]),      // four empty days: over the limit of three
    [{ kind: "day", day: "2026-09-30", index: 0 }, { kind: "gap", from: "2026-10-01", to: "2026-10-04", days: 4 },
     { kind: "day", day: "2026-10-05", index: 1 }]);
  assert.equal(dayColumns(["2026-09-30", "2026-10-04"]).length, 5);     // three empty days: drawn
  // across a year end and a leap day
  assert.deepEqual(dayColumns(["2027-12-31", "2028-01-01"]).map((c) => c.kind), ["day", "day"]);
  assert.equal(dayColumns(["2028-02-28", "2028-03-01"]).length, 3);
  assert.deepEqual(dayColumns(["2026-01-01", "2027-01-01"])[1], { kind: "gap", from: "2026-01-02", to: "2026-12-31", days: 364 });
});

test("day columns do not depend on the machine's time zone", () => {
  // East of Greenwich local midnight is still the day before in UTC, so arithmetic in local time names the
  // wrong days there; on a machine west of it the mistake does not show. Node rereads TZ when it is set.
  const before = process.env.TZ;
  try {
    for (const zone of ["Pacific/Kiritimati", "America/New_York", "UTC", "Europe/Berlin"]) {
      process.env.TZ = zone;
      const cols = dayColumns(["2026-03-28", "2026-03-30", "2026-10-24", "2026-10-26"], 500);
      assert.equal(cols.length, 213, zone);                              // every day from Mar 28 to Oct 26, both clock changes inside
      assert.deepEqual(cols.slice(0, 3), [{ kind: "day", day: "2026-03-28", index: 0 }, { kind: "day", day: "2026-03-29", index: null },
        { kind: "day", day: "2026-03-30", index: 1 }], zone);
      assert.deepEqual(cols.at(-2), { kind: "day", day: "2026-10-25", index: null }, zone);
    }
  } finally {
    if (before === undefined) delete process.env.TZ; else process.env.TZ = before;
  }
});
