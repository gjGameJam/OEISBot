"""The documentation's own numbers, checked against reality.

`docs/` is a deliverable here, not a comment: the handoff page's "Resuming in a new session" block tells
the next session which counts to expect, and a wrong one sends it looking for a problem that does not
exist. The test count alone is written out in eight places across five files, plus a per-file table and a
collected-count paragraph in `development.md` -- and during history item 36 it drifted three times in one
item, because every fix that added a test invalidated numbers nobody thought to look at. Some of the
drift was older still: item 34 left `test_attempt.py` documented as 52 against an actual 57.

So the numbers are derived here rather than trusted. This test reads what pytest actually collected in
*this* run, so it cannot disagree with the suite it is part of, and it skips rather than lies when only
part of the suite was collected (`-k`, a single file, `--lf`).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

# Where the total is written out. Every one of these is prose a reader acts on.
TOTAL_PATTERNS = [
    ("CLAUDE.md", r"# (\d+) tests, ~100 s"),
    ("README.md", r"# (\d+) tests; proves the sandbox"),
    ("README.md", r"implemented, and (\d+) tests pass\."),
    ("docs/development.md", r"`python -m pytest` runs (\d+) tests"),
    ("docs/operations.md", r"# (\d+) tests, about 100 s"),
    ("docs/status.md", r"^(\d+) tests pass and `scripts/check_docs\.py`"),
    ("docs/status.md", r"# expect (\d+) passed"),
    ("docs/status.md", r"implemented, with (\d+) passing tests"),
]


def collected(session) -> dict[str, int]:
    """How many tests pytest collected, per test file, in this very run."""
    counts: dict[str, int] = {}
    for item in session.items:
        counts[Path(str(item.fspath)).name] = counts.get(Path(str(item.fspath)).name, 0) + 1
    return counts


def count_test_functions(path: Path) -> int:
    """`def test_*` at module level: what the doc table's "Test functions" column means, as opposed to the
    collected count, which counts every parametrized case."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(1 for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"))


@pytest.fixture
def counts(request) -> dict[str, int]:
    got = collected(request.session)
    want = {p.name for p in TESTS.glob("test_*.py")}
    if set(got) != want:
        pytest.skip(f"partial collection ({len(got)} of {len(want)} test files); counts are only "
                    "meaningful for a full run")
    return got


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def before_history(text: str) -> str:
    """`status.md` up to its history section. Numbers inside a history item are that session's own
    record of what was true then -- "274 -> 294 tests" must never be updated -- so they are not checked."""
    return text.split("\n## History (condensed)")[0]


def test_the_documented_test_total_is_the_real_one(counts):
    total = sum(counts.values())
    wrong = []
    for rel, pattern in TOTAL_PATTERNS:
        text = read(rel)
        if rel == "docs/status.md":
            text = before_history(text)
        found = re.findall(pattern, text, re.M)
        if not found:
            wrong.append(f"{rel}: no match for {pattern!r} -- the sentence was reworded, so it is no "
                         "longer checked; fix the pattern or this guard is dead")
        elif any(int(f) != total for f in found):
            wrong.append(f"{rel}: says {found}, pytest collected {total}")
    assert not wrong, "documented test counts are stale:\n  " + "\n  ".join(wrong)


def test_the_per_file_table_matches_the_files(counts):
    """`development.md`'s table column is test *functions*; the paragraph above it is *collected* tests."""
    text = read("docs/development.md")
    table = {m[0]: int(m[1]) for m in re.findall(r"^\| `(test_\w+\.py)` \| (\d+) \|", text, re.M)}
    assert table, "the per-file test table could not be parsed; this guard is dead"
    assert set(table) == set(counts), f"table lists {sorted(table)}, tests/ has {sorted(counts)}"
    wrong = {name: (said, count_test_functions(TESTS / name)) for name, said in table.items()
             if said != count_test_functions(TESTS / name)}
    assert not wrong, f"per-file 'Test functions' counts are stale (said, actual): {wrong}"


def test_the_collected_counts_paragraph_matches_collection(counts):
    text = read("docs/development.md")
    said = {m[0]: int(m[1]) for m in re.findall(r"`(test_\w+\.py)` to (\d+)", text)}
    assert said, "the 'parametrized cases bring ... to N collected tests' paragraph could not be parsed"
    wrong = {name: (n, counts[name]) for name, n in said.items() if counts.get(name) != n}
    assert not wrong, f"collected counts in development.md are stale (said, actual): {wrong}"
    # and every file whose collected count exceeds its function count must be listed there, or the
    # paragraph quietly stops describing the suite
    missing = {name for name, n in counts.items() if n != count_test_functions(TESTS / name)} - set(said)
    assert not missing, f"these files are parametrized but the paragraph does not mention them: {missing}"
