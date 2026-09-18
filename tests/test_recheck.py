"""The oeis.org re-check verdicts, and the `oeisbot recheck` command. No sandbox needed."""
from __future__ import annotations

import pytest

from oeisbot import attempt, cli, db
from oeisbot.ingest import bfile
from oeisbot.terms import KnownTerms

KNOWN = KnownTerms("A999999", 1, {1: 2, 2: 3, 3: 5}, "data")
NEW = {4: 7, 5: 11}


def entry_text(data: str | None = "2,3,5", keywords: str = "nonn,more") -> str:
    lines = ["%N A999999 The primes.", "%O A999999 1,2", f"%K A999999 {keywords}"]
    if data is not None:
        lines.insert(0, f"%S A999999 {data}")
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("text, live_bfile, still_new, note", [
    (entry_text(), None, True, "live entry ends at a(3); new terms start at a(4)"),
    (entry_text(keywords="nonn,fini"), None, True, "keyword 'more' was removed"),
    (entry_text("2,3,5,7"), None, False, "live entry already has 1 of the new terms (up to a(4))"),
    (entry_text("2,3,5,13"), None, False, "a(4) = 13, which DISAGREES"),
    (entry_text(), {4: 7, 5: 11}, False, "live entry already has 2 of the new terms"),
    (None, None, False, "could not read the live entry"),
    ("nothing parsable here", None, False, "could not read the live entry"),
    (entry_text(data=None), None, False, "could not read any terms from the live entry"),
])
def test_recheck_verdicts(monkeypatch, text, live_bfile, still_new, note):
    monkeypatch.setattr(bfile, "fetch", lambda a, refresh=False: live_bfile and bfile.BFile(a, dict(live_bfile)))
    monkeypatch.setattr(bfile, "fetch_entry_text", lambda a: text)
    verdict, said = attempt.recheck(KNOWN, 4, NEW)
    assert verdict is still_new and note in said


def pending_row(conn) -> int:
    """An attempt row waiting for its re-check, with no saved result to load."""
    with conn:
        return conn.execute(
            """INSERT INTO attempts(a_number, strategy, program_sha, started_at, verified, known_terms, new_terms,
                                    outcome, failure_mode, extra)
               VALUES ('A999999', 'pari:a(n)', 'deadbeef', ?, 1, 3, 2, 'recheck_pending', 'max_new_terms',
                       '{"recheck": "not done yet"}')""", (db.now(),)).lastrowid


def test_recheck_command_reports_what_is_pending(tmp_path, monkeypatch, capsys):
    conn = db.connect(tmp_path / "t.sqlite3")
    monkeypatch.setattr(db, "connect", lambda *a, **k: conn)
    monkeypatch.setattr(attempt, "pending_path", lambda attempt_id: tmp_path / f"missing-{attempt_id}.pickle")

    assert cli.main(["recheck"]) == 0
    assert "no wins are waiting" in capsys.readouterr().out

    attempt_id = pending_row(conn)
    with pytest.raises(SystemExit) as exit_info:      # non-zero exit, so a script notices one is left
        cli.main(["recheck"])
    assert "1 win(s) still waiting" in str(exit_info.value)
    assert f"attempt #{attempt_id}: still pending (FileNotFoundError" in capsys.readouterr().out
    assert db.pending_recheck(conn, "A999999")["id"] == attempt_id
    conn.close()
