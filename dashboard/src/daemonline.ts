// What the header says about `oeisbot daemon` (item 58). No imports, so node can test it (dashboard.md).
//
// The server's answer (`/api/daemon`, oeisbot.daemon.status) has three parts: `running` comes from the
// writers' lock, never from the heartbeat's age; `other_command` names a different command holding that
// lock; `heartbeat` is the last state a daemon wrote, which a killed one leaves behind looking fresh.

export interface Heartbeat {
  state?: string; detail?: string | null; a_number?: string | null; tier?: string | null;
  window?: string; window_ends?: string | null; at?: string; progress_at?: string; synced_at?: string | null;
  stop_reason?: string | null; stopping_for_s?: number | null; warnings?: string[];
}
/** `armed`: the user has allowed nights to run here (`oeisbot daemon --arm`). Until then a start does nothing. */
export interface DaemonReport { running: boolean; other_command: string | null; heartbeat: Heartbeat | null; armed?: boolean }
export interface DaemonLine { tone: "ok" | "warn" | "idle"; text: string; notes: string[] }

/** A daemon that is alive (its watcher still writes `at`) but whose main loop has taken no step for this
 *  long is probably stuck in one call. The longest honest silence is one pick at the top tier: three
 *  verifications of ten minutes, a three-hour extension and a win's re-check in network trouble, about
 *  3 h 45 min. Four hours left a quarter of an hour's margin; this leaves three quarters. */
export const NO_STEP_MS = 4.5 * 3600 * 1000;
/** The daemon writes its heartbeat every 30 s (`daemon.HEARTBEAT_S`). One this old, from a daemon the lock
 *  says is running, means what is shown is not current: the file cannot be written, or the process is
 *  frozen whole. */
export const NO_BEAT_MS = 5 * 60 * 1000;

const PAUSED: Record<string, string> = {
  paused_disk: "paused, the disk is nearly full", paused_ram: "paused, memory is short",
  paused_machine: "paused, the machine was short of disk or memory",
};

/** "3 min", "2 h 5 min": how long ago, to the minute. */
export function ago(ms: number): string {
  const min = Math.max(0, Math.round(ms / 60000));
  if (min < 1) return "under a minute";
  if (min < 60) return `${min} min`;
  return `${Math.floor(min / 60)} h ${min % 60} min`;
}

/** The local hour and minute of a naive local timestamp ("2026-11-23T08:00" is 08:00 where the daemon runs,
 *  which is where the dashboard is served from). Not parsed as a date: a browser would shift it. */
export function clock(naive: string | null | undefined): string | null {
  const m = /T(\d\d:\d\d)/.exec(naive ?? "");
  return m ? m[1] : null;
}

export function daemonLine(r: DaemonReport, nowMs: number): DaemonLine {
  const b = r.heartbeat ?? {};
  const notes = [...(b.warnings ?? [])];
  if (!r.running) {
    // Not armed comes first: it is why nothing will happen tonight, whatever last night's heartbeat says.
    // (`armed` missing is an older server's answer, and is not read as "no".)
    if (r.armed === false) {
      const last = b.state === "stopped" && b.detail ? `; last night: ${b.detail}` : "";
      return { tone: "idle", notes,
               text: `Daemon is not armed, so a start will do nothing (oeisbot daemon --arm allows it)${last}` };
    }
    if (r.other_command) return { tone: "idle", text: `Daemon not running; oeisbot ${r.other_command} is`, notes };
    if (!r.heartbeat) return { tone: "idle", text: "Daemon has not run here", notes };
    if (b.state !== "stopped") {
      return { tone: "warn", notes,
               text: `Daemon is not running, and its last run did not finish (it was ${b.state ?? "starting"} when its process ended)` };
    }
    return { tone: notes.length ? "warn" : "idle", text: `Daemon not running; last night: ${b.detail ?? "finished"}`, notes };
  }
  const doing = b.state === "running" ? (b.a_number ? `running ${b.a_number}` : (b.detail ?? "between picks"))
    : b.state === "sync" ? "syncing the mirror"
    : PAUSED[b.state ?? ""] ?? (b.state ?? "starting");
  const tier = b.state === "running" && b.tier ? ` at tier ${b.tier}` : "";
  const closes = clock(b.window_ends);
  let text = `Daemon ${doing}${tier}` + (closes ? ` · window closes ${closes}` : b.window ? ` · window ${b.window}` : "");
  let tone: DaemonLine["tone"] = (b.state ?? "").startsWith("paused") ? "warn" : "ok";
  if (b.state?.startsWith("paused") && b.detail) notes.unshift(b.detail);
  if (b.stopping_for_s != null) {
    tone = "warn";
    text += ` · stopping (${b.stop_reason ?? "asked to stop"}), ${ago(b.stopping_for_s * 1000)} so far`;
  }
  const beatAt = b.at ? Date.parse(b.at) : NaN;
  if (!isNaN(beatAt) && nowMs - beatAt > NO_BEAT_MS) {
    tone = "warn";
    notes.unshift(`this was written ${ago(nowMs - beatAt)} ago and has not been refreshed since: it may not be current`);
  }
  const step = b.progress_at ? Date.parse(b.progress_at) : NaN;
  if (!isNaN(step)) {
    const quiet = nowMs - step;
    if (quiet > NO_STEP_MS) {
      tone = "warn";
      notes.unshift(`no step for ${ago(quiet)}: it may be stuck (see oeisbot daemon --status)`);
    } else if (b.state === "running" && b.a_number) {
      text += ` · started ${ago(quiet)} ago`;
    }
  }
  if (notes.length) tone = "warn";
  return { tone, text, notes };
}
