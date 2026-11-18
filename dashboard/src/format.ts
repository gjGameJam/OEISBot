// Number and date formatting for the dashboard. Pure and import-free on purpose: `node --test` strips types
// but cannot load a .tsx file or resolve an extensionless import, so everything here is testable as it is
// (test/format.test.ts). Nothing in this file may print a number in exponent notation.

const DASH = "–";

/** `v` to `sig` significant digits, never in exponent notation: "60.3", "110", "652,000". */
export function sigFixed(v: number, sig = 3): string {
  const p = v.toPrecision(sig);
  return /e/i.test(p) ? Number(p).toLocaleString("en-US", { maximumFractionDigits: 20 }) : p;
}

const TIME_UNITS: { name: string; seconds: number; below: number }[] = [
  { name: "µs", seconds: 1e-6, below: 1000 },
  { name: "ms", seconds: 1e-3, below: 1000 },
  { name: "s", seconds: 1, below: 120 },
  { name: "min", seconds: 60, below: 120 },
  { name: "h", seconds: 3600, below: 48 },
  { name: "d", seconds: 86400, below: Infinity },
];

/** A duration in the largest unit that keeps it readable. A unit is passed over when the value *rounded* in
 *  it reaches the unit's limit, so 0.9996 s is "1.00 s" and never "1000 ms"; the next unit then shows the
 *  value as it is, which can be a hair under one ("0.999 ms" for 999.5 µs). Below a microsecond it says so
 *  instead of printing a string of zeros. */
export function fmtSeconds(s: number | null | undefined): string {
  if (s == null || !isFinite(s)) return DASH;
  if (s === 0) return "0 s";
  const abs = Math.abs(s);
  if (Number((abs * 1e6).toPrecision(3)) < 1) return "< 1 µs";
  if (s < 0) return `-${fmtSeconds(abs)}`;
  for (const u of TIME_UNITS) {
    const v = abs / u.seconds;      // each unit rounds the value itself: rounding the seconds first rounds twice
    if (Number(v.toPrecision(3)) < u.below) return `${sigFixed(v)} ${u.name}`;
  }
  return DASH;   // unreachable: the last unit has no upper limit
}

/** A peak-memory figure. Zero is a dash: for a gp run the figure is the largest stack the driver reported
 *  (verify.AttemptResult.peak_mem_bytes), and it is 0 exactly when the run ended before reporting any, which is
 *  "not measured" and not "used nothing". */
export function fmtBytes(b: number | null | undefined): string {
  if (b == null || b === 0) return DASH;
  if (b < 1 << 20) return `${(b / 1024).toFixed(0)} KiB`;
  if (b < 1 << 30) return `${(b / (1 << 20)).toFixed(0)} MiB`;
  return `${(b / (1 << 30)).toFixed(2)} GiB`;
}

export function fmtPct(x: number | null | undefined, digits = 0): string {
  return x == null ? DASH : `${(x * 100).toFixed(digits)}%`;
}

export function fmtInt(x: number | null | undefined, locale?: string): string {
  return x == null ? DASH : x.toLocaleString(locale);
}

export interface TimeOptions { locale?: string; timeZone?: string; now?: Date }

/** A timestamp as month, day, hour and minute, with the year added when it is not the current one (a bare
 *  "Sep 30" is ambiguous a year later). `opts` exists so a test can pin the locale, the zone and today. */
export function fmtTime(iso: string | null | undefined, opts: TimeOptions = {}): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return DASH;
  const year = (x: Date) => x.toLocaleString("en-US", { year: "numeric", timeZone: opts.timeZone });
  const sameYear = year(d) === year(opts.now ?? new Date());
  return d.toLocaleString(opts.locale, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: opts.timeZone,
    ...(sameYear ? {} : { year: "numeric" }),
  });
}

/** What to tell a person about a failed request, out of the text `useApi` keeps (`String(new Error("503:
 *  <body>"))`, or the browser's own error when no answer came). The raw text is JSON, or a whole HTML page from
 *  something in between, and was once shown as it stood. `useApi` goes on storing the raw text, because
 *  `treemap.failureReason` reads it; this is for the moment of display only. */
export function describeError(message: string, limit = 200): string {
  const clip = (s: string) => { const t = s.replace(/\s+/g, " ").trim(); return t.length > limit ? `${t.slice(0, limit)}…` : t; };
  const text = message.trim();
  const m = /^(?:\w*Error: )?(\d{3}):\s?([\s\S]*)$/.exec(text);
  if (!m) {
    return /failed to fetch|networkerror|load failed/i.test(text)
      ? "the dashboard server did not answer (is `oeisbot dashboard` still running?)"
      : clip(text.replace(/^\w*Error: /, ""));
  }
  const [, status, body] = m;
  try {
    const j = JSON.parse(body);
    if (j && typeof j.reason === "string") return clip(`${status}: ${j.reason}`);
    if (j && typeof j.detail === "string") return clip(`${status}: ${j.detail}`);
    if (j && Array.isArray(j.detail) && j.detail.length) {       // FastAPI's list of what was wrong with a request
      const d = j.detail[0];
      const where = Array.isArray(d.loc) ? d.loc.filter((x: unknown) => x !== "query" && x !== "path").join(".") : "";
      return clip(`${status}: ${where ? `${where}: ` : ""}${typeof d.msg === "string" ? d.msg : "the request was refused"}`);
    }
  } catch { /* not JSON: fall through */ }
  if (/^\s*</.test(body)) return `${status}: the server sent a page instead of an answer`;
  return clip(body.trim() ? `${status}: ${body}` : `${status}: the server gave no reason`);
}

/** A share of the picks as a percentage: whole numbers from 10% up, one decimal from 1%, two significant
 *  digits below that, and "< 0.0001%" for what is smaller still (at a high alpha a band's share is 1e-12, which
 *  used to be printed as "4.3e-10%"). The decimals follow the figure shown, so 9.96% is "10%", not "10.0%". */
export function fmtShare(p: number): string {
  const pct = p * 100;
  if (!(pct > 0)) return "0%";
  if (pct < 0.0001) return "< 0.0001%";
  if (Number(pct.toFixed(1)) >= 10) return `${pct.toFixed(0)}%`;
  if (Number(pct.toPrecision(2)) >= 1) return `${pct.toFixed(1)}%`;
  return `${sigFixed(pct, 2)}%`;
}
