import assert from "node:assert/strict";
import { test } from "node:test";
import { ago, clock, daemonLine, NO_BEAT_MS, NO_STEP_MS, type DaemonReport } from "../src/daemonline.ts";

const NOW = Date.parse("2026-11-23T06:10:00+00:00");
const beat = {
  state: "running", detail: null, a_number: "A000045", tier: "base", window: "22:00-08:00",
  window_ends: "2026-11-23T08:00", at: "2026-11-23T06:09:40+00:00", progress_at: "2026-11-23T06:07:00+00:00",
  synced_at: "2026-11-23T03:01:00+00:00", stop_reason: null, stopping_for_s: null, warnings: [],
};
const running = (over: object = {}): DaemonReport => ({ running: true, other_command: null, heartbeat: { ...beat, ...over } });

test("a daemon at work names the sequence, the tier, the close and how long", () => {
  assert.deepEqual(daemonLine(running(), NOW),
    { tone: "ok", text: "Daemon running A000045 at tier base · window closes 08:00 · started 3 min ago", notes: [] });
});

test("between picks it says what it is doing instead of a sequence", () => {
  const line = daemonLine(running({ a_number: null, detail: "building the pool" }), NOW);
  assert.equal(line.text, "Daemon building the pool at tier base · window closes 08:00");
  assert.equal(daemonLine(running({ a_number: null, detail: null }), NOW).text, "Daemon between picks at tier base · window closes 08:00");
  assert.equal(daemonLine(running({ state: "sync", a_number: null }), NOW).text, "Daemon syncing the mirror · window closes 08:00");
});

test("a window with no closing time is named, not given a time", () => {
  assert.equal(daemonLine(running({ window: "always", window_ends: null }), NOW).text,
    "Daemon running A000045 at tier base · window always · started 3 min ago");
});

test("a pause is a warning and says what is short", () => {
  const line = daemonLine(running({ state: "paused_disk", a_number: null, detail: "7.0 GiB free on the data drive; a run needs 10 GiB" }), NOW);
  assert.equal(line.tone, "warn");
  assert.equal(line.text, "Daemon paused, the disk is nearly full · window closes 08:00");
  assert.deepEqual(line.notes, ["7.0 GiB free on the data drive; a run needs 10 GiB"]);
  assert.match(daemonLine(running({ state: "paused_ram", a_number: null }), NOW).text, /memory is short/);
  assert.match(daemonLine(running({ state: "paused_machine", a_number: null }), NOW).text, /short of disk or memory/);
});

test("a stop that is being obeyed says why and for how long", () => {
  const line = daemonLine(running({ stop_reason: "the window 22:00-08:00 closed", stopping_for_s: 125 }), NOW);
  assert.equal(line.tone, "warn");
  assert.match(line.text, / · stopping \(the window 22:00-08:00 closed\), 2 min so far/);
  assert.equal(daemonLine(running({ stopping_for_s: 0 }), NOW).tone, "warn");   // zero seconds is still stopping
});

test("warnings from the night are shown and make the line a warning", () => {
  const line = daemonLine(running({ warnings: ["sync failed (GitTimeout: ...)"] }), NOW);
  assert.deepEqual([line.tone, line.notes], ["warn", ["sync failed (GitTimeout: ...)"]]);
});

test("alive but taking no step for hours is said, because the heartbeat alone would look fine", () => {
  const quiet = new Date(NOW - NO_STEP_MS - 60000).toISOString();
  const line = daemonLine(running({ progress_at: quiet }), NOW);
  assert.equal(line.tone, "warn");
  assert.equal(line.notes[0], "no step for 4 h 31 min: it may be stuck (see oeisbot daemon --status)");
  assert.equal(NO_STEP_MS, 4.5 * 3600 * 1000);
  assert.doesNotMatch(line.text, /started/);
  // exactly at the limit is not over it, and a long honest pick is not a warning
  assert.equal(daemonLine(running({ progress_at: new Date(NOW - NO_STEP_MS).toISOString() }), NOW).tone, "ok");
  assert.equal(daemonLine(running({ progress_at: undefined }), NOW).text, "Daemon running A000045 at tier base · window closes 08:00");
});

test("not running: nothing yet, a clean end, an unfinished run, another command", () => {
  const off = (heartbeat: object | null, other: string | null = null): DaemonReport => ({ running: false, other_command: other, heartbeat });
  assert.deepEqual(daemonLine(off(null), NOW), { tone: "idle", text: "Daemon has not run here", notes: [] });
  assert.deepEqual(daemonLine(off({ state: "stopped", detail: "the window 22:00-08:00 closed", warnings: [] }), NOW),
    { tone: "idle", text: "Daemon not running; last night: the window 22:00-08:00 closed", notes: [] });
  // a killed daemon leaves a heartbeat that says "running": the lock says otherwise, and the line says both
  const killed = daemonLine(off({ ...beat }), NOW);
  assert.equal(killed.tone, "warn");
  assert.equal(killed.text, "Daemon is not running, and its last run did not finish (it was running when its process ended)");
  assert.equal(daemonLine(off({ ...beat }, "sync"), NOW).text, "Daemon not running; oeisbot sync is");
  // last night's warnings stay visible in the morning
  const morning = daemonLine(off({ state: "stopped", detail: "the window closed", warnings: ["A000001 raised ZeroDivisionError"] }), NOW);
  assert.deepEqual([morning.tone, morning.notes], ["warn", ["A000001 raised ZeroDivisionError"]]);
});

test("ago rounds to the minute and never goes negative", () => {
  assert.deepEqual([0, 29000, 31000, 59 * 60000, 60 * 60000, 125 * 60000, -5000].map(ago),
    ["under a minute", "under a minute", "1 min", "59 min", "1 h 0 min", "2 h 5 min", "under a minute"]);
});

test("the closing time is read off the text, not through a date that would shift it", () => {
  assert.equal(clock("2026-11-23T08:00"), "08:00");
  assert.equal(clock("2026-11-23T23:59:00"), "23:59");
  assert.equal(clock(null), null);
  assert.equal(clock("never"), null);
});

test("a heartbeat that has stopped being refreshed is not shown as current", () => {
  // the lock says the daemon is running, but what is on screen was written long ago
  const old = new Date(NOW - NO_BEAT_MS - 60000).toISOString();
  const line = daemonLine(running({ at: old }), NOW);
  assert.equal(line.tone, "warn");
  assert.equal(line.notes[0], "this was written 6 min ago and has not been refreshed since: it may not be current");
  assert.equal(daemonLine(running({ at: new Date(NOW - NO_BEAT_MS).toISOString() }), NOW).tone, "ok");   // exactly at the limit
  assert.equal(daemonLine(running({ at: undefined }), NOW).tone, "ok");
  assert.equal(NO_BEAT_MS, 5 * 60 * 1000);
});

test("not armed is said first, because it is why nothing will happen tonight", () => {
  const off = (heartbeat: object | null, armed: boolean | undefined): DaemonReport =>
    ({ running: false, other_command: null, heartbeat, armed });
  assert.deepEqual(daemonLine(off(null, false), NOW),
    { tone: "idle", text: "Daemon is not armed, so a start will do nothing (oeisbot daemon --arm allows it)", notes: [] });
  assert.equal(daemonLine(off({ state: "stopped", detail: "the window 22:00-08:00 closed", warnings: [] }, false), NOW).text,
    "Daemon is not armed, so a start will do nothing (oeisbot daemon --arm allows it); last night: the window 22:00-08:00 closed");
  // armed, or an answer from a server that does not say: the line is what it was
  assert.equal(daemonLine(off(null, true), NOW).text, "Daemon has not run here");
  assert.equal(daemonLine(off(null, undefined), NOW).text, "Daemon has not run here");
  // a daemon that is running is described as running whatever the flag says (disarmed mid-night)
  assert.match(daemonLine({ ...running(), armed: false }, NOW).text, /^Daemon running A000045/);
});
