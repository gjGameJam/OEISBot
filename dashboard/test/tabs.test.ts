import assert from "node:assert/strict";
import { test } from "node:test";
import { notAWin, passesTrust, tapActs, tabAfter, trustOf } from "../src/tabs.ts";

const TABS = ["estimator", "pickmap", "queue", "attempts", "reviews", "history"];

test("left and right step to the neighbour", () => {
  assert.equal(tabAfter(TABS, "pickmap", "ArrowRight"), "queue");
  assert.equal(tabAfter(TABS, "pickmap", "ArrowLeft"), "estimator");
});

test("the ends wrap", () => {
  assert.equal(tabAfter(TABS, "history", "ArrowRight"), "estimator");
  assert.equal(tabAfter(TABS, "estimator", "ArrowLeft"), "history");
});

test("home and end go to the first and the last from anywhere", () => {
  for (const from of TABS) {
    assert.equal(tabAfter(TABS, from, "Home"), "estimator");
    assert.equal(tabAfter(TABS, from, "End"), "history");
  }
});

test("every other key is left alone", () => {
  // up and down scroll the page, Enter and Space press the button, Tab leaves the row
  for (const key of ["ArrowUp", "ArrowDown", "Enter", " ", "Tab", "a", "PageDown", "Escape", ""]) {
    assert.equal(tabAfter(TABS, "queue", key), null, key);
  }
});

test("a tab that is not in the row cannot strand the focus", () => {
  assert.equal(tabAfter(TABS, "gone", "ArrowRight"), "estimator");
  assert.equal(tabAfter(TABS, "gone", "ArrowLeft"), "history");
  assert.equal(tabAfter([], "gone", "ArrowRight"), null);
  assert.equal(tabAfter(["only"], "only", "ArrowRight"), "only");
  assert.equal(tabAfter(["only"], "only", "ArrowLeft"), "only");
});

test("the row may hold anything, not only strings", () => {
  // the Pick map's bands are numbers, with null for "All bands"
  const bands = [null, 0, 1, 4];
  assert.equal(tabAfter(bands, null, "ArrowRight"), 0);
  assert.equal(tabAfter(bands, 0, "ArrowLeft"), null);
  assert.equal(tabAfter(bands, 4, "ArrowRight"), null);
  assert.equal(tabAfter(bands, 1, "End"), 4);
});

test("a win is not labelled", () => {
  assert.equal(notAWin({}), null);
  assert.equal(notAWin({ win_rejected: false, review_refused: null }), null);
  assert.equal(notAWin({ win_rejected: false, review_refused: false }), null);
});

test("a rejected run and a refused run are told apart", () => {
  assert.equal(notAWin({ win_rejected: true, review_refused: null })!.label, "review rejected");
  const refused = notAWin({ win_rejected: true, review_refused: 2 })!;
  assert.equal(refused.label, "no review opened");
  assert.match(refused.title, /review #2\)/);
  // the refusal is recorded without the number of the earlier review: still refused, and no number is made up
  const bare = notAWin({ win_rejected: true, review_refused: true })!;
  assert.equal(bare.label, "no review opened");
  assert.doesNotMatch(bare.title, /#/);
  // review #0 does not exist, but a zero must not read as "not refused"
  assert.equal(notAWin({ win_rejected: true, review_refused: 0 })!.label, "no review opened");
});

test("trust has three levels", () => {
  assert.equal(trustOf({ trustworthy: 1, fit_trustworthy: 1 }), "trusted");
  assert.equal(trustOf({ trustworthy: 0, fit_trustworthy: 1 }), "fit");
  assert.equal(trustOf({ trustworthy: 0, fit_trustworthy: 0 }), "untrusted");
  assert.equal(trustOf({ trustworthy: 0, fit_trustworthy: null }), "untrusted");
  assert.equal(trustOf({ trustworthy: 0 }), "untrusted");
  // a row from before the fit's verdict was stored, trusted outright
  assert.equal(trustOf({ trustworthy: 1, fit_trustworthy: null }), "trusted");
});

test("the filter keeps what its name says", () => {
  const trusted = { trustworthy: 1, fit_trustworthy: 1 }, fit = { trustworthy: 0, fit_trustworthy: 1 }, none = { trustworthy: 0, fit_trustworthy: 0 };
  assert.deepEqual([trusted, fit, none].map((p) => passesTrust("all", p)), [true, true, true]);
  assert.deepEqual([trusted, fit, none].map((p) => passesTrust("trusted", p)), [true, false, false]);
  assert.deepEqual([trusted, fit, none].map((p) => passesTrust("fit", p)), [true, true, false]);
  assert.deepEqual([trusted, fit, none].map((p) => passesTrust("something else", p)), [true, true, true]);
});

test("a mouse click acts at once, and so does a pen or a press of unknown kind", () => {
  for (const kind of ["mouse", "pen", "", null]) {
    assert.equal(tapActs(kind, null, "A000001"), true, String(kind));
    assert.equal(tapActs(kind, "A000002", "A000001"), true, String(kind));
  }
});

test("a touch acts only on the tile its last tap put a tooltip up for", () => {
  assert.equal(tapActs("touch", null, "A000001"), false);            // the first tap
  assert.equal(tapActs("touch", "A000001", "A000001"), true);        // the second, on the same tile
  assert.equal(tapActs("touch", "A000002", "A000001"), false);       // a tap on another tile starts again
  assert.equal(tapActs("touch", "lump:b3", "lump:b3"), true);        // a lump is a tile like any other
});
