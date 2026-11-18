import assert from "node:assert/strict";
import { test } from "node:test";
import { describeError, fmtBytes, fmtInt, fmtShare, fmtPct, fmtSeconds, fmtTime, sigFixed } from "../src/format.ts";

test("durations never come out in exponent notation", () => {
  let seed = 11;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let k = 0; k < 5000; k++) {
    const s = 10 ** (rnd() * 26 - 10);
    const text = fmtSeconds(s);
    assert.ok(!/e[+-]?\d/i.test(text), `${s} -> ${text}`);
    assert.match(text, /^(< 1 µs|[\d.,]+ (µs|ms|s|min|h|d))$/, `${s} -> ${text}`);
  }
});

test("the durations the dashboard showed wrongly on 2026-11-17", () => {
  assert.equal(fmtSeconds(0.11), "110 ms");            // Attempts runtime read "1.1e+2 ms"
  assert.equal(fmtSeconds(0.66), "660 ms");            // and "6.6e+2 ms"
  assert.equal(fmtSeconds(5.63e10), "652,000 d");      // a tooltip read "6.52e+5 d"
  assert.equal(fmtSeconds(0.9996), "1.00 s");          // was "1.0e+3 ms": the unit is chosen after rounding
  assert.equal(fmtSeconds(0.000278), "278 µs");
});

test("each unit hands over to the next at the rounded value", () => {
  assert.equal(fmtSeconds(0.0009996), "1.00 ms");
  assert.equal(fmtSeconds(60.3), "60.3 s");
  assert.equal(fmtSeconds(119.4), "119 s");
  assert.equal(fmtSeconds(119.96), "2.00 min");
  assert.equal(fmtSeconds(3066), "51.1 min");
  assert.equal(fmtSeconds(7199), "2.00 h");
  assert.equal(fmtSeconds(10008), "2.78 h");
  assert.equal(fmtSeconds(172799), "2.00 d");
  assert.equal(fmtSeconds(86400 * 1234.5), "1,230 d");
});

test("durations with nothing sensible to say", () => {
  assert.equal(fmtSeconds(null), "–");
  assert.equal(fmtSeconds(undefined), "–");
  assert.equal(fmtSeconds(NaN), "–");
  assert.equal(fmtSeconds(Infinity), "–");
  assert.equal(fmtSeconds(0), "0 s");
  assert.equal(fmtSeconds(3e-9), "< 1 µs");
  assert.equal(fmtSeconds(-2), "-2.00 s");
});

test("significant digits without an exponent", () => {
  assert.equal(sigFixed(110, 2), "110");
  assert.equal(sigFixed(1234567), "1,230,000");
  assert.equal(sigFixed(0.5), "0.500");
  assert.equal(sigFixed(1.3e-7, 2), "0.00000013");     // the estimator's median ratio is this small
  assert.equal(sigFixed(1234, 2), "1,200");
  assert.equal(sigFixed(190.4, 2), "190");
});

test("the unit thresholds, each from just below and just above", () => {
  assert.equal(fmtSeconds(6600), "110 min");           // minutes run to 120, not 100
  assert.equal(fmtSeconds(100000), "27.8 h");          // hours run to 48, not 24
  assert.equal(fmtSeconds(5e-7), "< 1 µs");
  assert.equal(fmtSeconds(9.996e-7), "1.00 µs");       // rounds up to a microsecond, so it is one
  assert.equal(fmtSeconds(0.0009995), "0.999 ms");     // 999.5 µs would round to "1000 µs": the next unit, unrounded
  assert.equal(fmtSeconds(3066), "51.1 min");          // not 51.2: the seconds are not rounded before the minutes are
  assert.equal(fmtSeconds(-1e-9), "< 1 µs");
});

test("bytes, percentages and counts", () => {
  assert.equal(fmtBytes(null), "–");
  assert.equal(fmtBytes(0), "–");                      // a gp run that ended before reporting a figure: not "0 KiB"
  assert.equal(fmtBytes(2048), "2 KiB");
  assert.equal(fmtBytes(8 * 1024 * 1024), "8 MiB");
  assert.equal(fmtBytes(3 * 1024 ** 3), "3.00 GiB");
  assert.equal(fmtPct(0.1), "10%");
  assert.equal(fmtPct(0.00045, 3), "0.045%");
  assert.equal(fmtPct(null), "–");
  assert.equal(fmtInt(26814, "en-US"), "26,814");
  assert.equal(fmtInt(undefined), "–");
});

// ICU releases differ on the space before AM/PM (U+0020 or U+202F); the tests do not care which
const plain = (s: string) => s.replace(/\s/gu, " ");

test("a timestamp shows its year only when that is not this year", () => {
  const pin = { locale: "en-US", timeZone: "UTC" };
  assert.equal(plain(fmtTime("2026-09-30T18:21:00+00:00", { ...pin, now: new Date("2026-11-17T12:00:00Z") })), "Sep 30, 06:21 PM");
  assert.equal(plain(fmtTime("2026-09-30T18:21:00+00:00", { ...pin, now: new Date("2027-01-02T12:00:00Z") })), "Sep 30, 2026, 06:21 PM");
});

test("the year compared is the year in the zone asked for", () => {
  // Kiritimati is UTC+14, a zone no development machine is in, so this cannot pass by coincidence with the
  // machine's own zone: 11:00 UTC on Dec 31 is already 01:00 on Jan 1 there.
  const zone = { locale: "en-US", timeZone: "Pacific/Kiritimati" };
  const late = "2026-12-31T11:00:00+00:00";
  assert.equal(plain(fmtTime(late, { ...zone, now: new Date("2026-12-31T09:00:00Z") })), "Jan 1, 2027, 01:00 AM");   // now is still 2026 there
  assert.equal(plain(fmtTime(late, { ...zone, now: new Date("2026-12-31T10:30:00Z") })), "Jan 1, 01:00 AM");         // now is 2027 there too
  // and in UTC the same instant is Dec 31 of the year `now` is in
  assert.equal(plain(fmtTime(late, { locale: "en-US", timeZone: "UTC", now: new Date("2026-12-31T10:30:00Z") })), "Dec 31, 11:00 AM");
});

test("the locale asked for is the locale used", () => {
  assert.equal(fmtInt(26814, "de-DE"), "26.814");
  assert.match(plain(fmtTime("2026-09-30T18:21:00+00:00", { locale: "de-DE", timeZone: "UTC", now: new Date("2026-11-17T12:00:00Z") })),
    /^30\. Sept?\.?,? 18:21$/);
  // digits and units are always written the same way, whatever the machine's locale
  assert.equal(sigFixed(1234567), "1,230,000");
});

test("a timestamp that is missing or unreadable is a dash, not a date in 1970", () => {
  assert.equal(fmtTime(null), "–");
  assert.equal(fmtTime(""), "–");
  assert.equal(fmtTime("not a date"), "–");
});

test("a failed request is described, not dumped", () => {
  assert.equal(describeError('Error: 503: {"detail":"no database at data/oeisbot.sqlite3; run `oeisbot setup` and `oeisbot sync`"}'),
    "503: no database at data/oeisbot.sqlite3; run `oeisbot setup` and `oeisbot sync`");
  assert.equal(describeError('Error: 503: {"error":"pool_build_failed","reason":"RuntimeError: boom"}'), "503: RuntimeError: boom");
  assert.equal(describeError('Error: 422: {"detail":[{"type":"less_than_equal","loc":["query","alpha"],"msg":"Input should be less than or equal to 6","input":"700"}]}'),
    "422: alpha: Input should be less than or equal to 6");
  assert.equal(describeError("Error: 500: Internal Server Error"), "500: Internal Server Error");
  assert.equal(describeError("Error: 502: <html><body><h1>Bad Gateway</h1>" + "x".repeat(5000) + "</body></html>"),
    "502: the server sent a page instead of an answer");
  assert.equal(describeError("Error: 500: "), "500: the server gave no reason");
  assert.match(describeError("TypeError: Failed to fetch"), /did not answer/);
  assert.match(describeError("TypeError: NetworkError when attempting to fetch resource."), /did not answer/);
  assert.equal(describeError("SyntaxError: Unexpected token < in JSON"), "Unexpected token < in JSON");
});

test("a description is never longer than its limit and an ellipsis", () => {
  const long = describeError(`Error: 500: ${"word ".repeat(400)}`);
  assert.ok(long.length <= 201 && long.endsWith("…"), long);
  assert.ok(describeError(`Error: 503: ${JSON.stringify({ detail: "d".repeat(900) })}`).length <= 201);
  assert.equal(describeError("Error: 500: a\n   b\tc"), "500: a b c");
});

test("a share of the picks, at every size", () => {
  assert.equal(fmtShare(0.539), "54%");
  assert.equal(fmtShare(0.078), "7.8%");
  assert.equal(fmtShare(0.0996), "10%");               // was "10.0%" beside a "10%"
  assert.equal(fmtShare(0.00066), "0.066%");
  assert.equal(fmtShare(0.0000219), "0.0022%");
  assert.equal(fmtShare(0.00999), "1.0%");
  assert.equal(fmtShare(0.0000011), "0.00011%");
  assert.equal(fmtShare(4.27e-12), "< 0.0001%");       // band 8 at alpha 6 read "4.3e-10%"
  assert.equal(fmtShare(9.2e-15), "< 0.0001%");
  assert.equal(fmtShare(0), "0%");
  assert.equal(fmtShare(1), "100%");
  let seed = 3;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let k = 0; k < 3000; k++) {
    const text = fmtShare(10 ** (rnd() * 18 - 18));
    assert.ok(!/e[+-]?\d/i.test(text), text);
  }
});
