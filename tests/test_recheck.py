"""The oeis.org re-check verdicts, the saved pending win, and the `oeisbot recheck` command. No sandbox."""
from __future__ import annotations

import csv
import json

import pytest

from oeisbot import artifact, attempt, cli, config, db
from oeisbot.config import Budgets
from oeisbot.ingest import bfile
from oeisbot.sandbox import RunResult, Status
from oeisbot.terms import KnownTerms, Program
from oeisbot.verify import AttemptResult, Prediction, Stop, TermRecord

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


def test_a_term_below_a_published_bound_is_called_out_in_the_readme(tmp_path):
    """Item 51: the safe direction of invariant 10. A new term inside a range a human reported empty is
    still a term -- the run neither drops it nor stops -- but the README says the two disagree and that
    the reviewer must find out which is wrong before submitting."""
    win = a_win()
    win.below_bound = {"bound": "100", "quote": "No more terms <= 100.", "indices": [4]}
    folder = artifact.write(win, 1, "The primes.", Budgets(), "still new", root=tmp_path)
    text = (folder / "README.md").read_text(encoding="utf-8")
    assert "**A term lands below a published bound (100):** a(4) = 71" in text
    assert "No more terms <= 100." in text and "Either that search or this program is wrong" in text
    clean = artifact.write(a_win(), 1, "The primes.", Budgets(), "still new", root=tmp_path / "clean")
    assert "published bound" not in (clean / "README.md").read_text(encoding="utf-8")


def a_win(value: int = 71) -> AttemptResult:
    """A finished win carrying everything a JSON round-trip could damage: a term far too long for a JSON
    number to be safe, a driver-wrapped program (`script` is not None, which decides `executed` and so
    `sha`), two enums, int-keyed known terms, and a prediction with None fields."""
    known = KnownTerms("A999999", 1, {1: 2, 2: 3, 3: 5}, "data", notes=["merged with DATA"])
    prog = Program("python", "def terms(work): ...", origin="model", strategy="python:model",
                   script="# driver\ndef terms(work): ...", notes=["numbered by the runner"])
    recs = [TermRecord(n, v, 0.5 * n, 0.4 * n, 10 * n, 2048, 0.5, 0.4, 10, kind) for n, v, kind in
            [(1, 2, "known"), (2, 3, "known"), (3, 5, "known"), (4, value, "new")]]
    preds = [Prediction(4, "work", 1.0, 0.5, 2.0, 1e6, "exp", True, True, False, False, None, ["fits"],
                        actual_s=1.5)]
    run = RunResult(Status.STOPPED, 0, 3.0, 2.5, 5_000_000, 6 << 30, "max_new_terms", ["@T 4"], "a warning\n")
    return AttemptResult(prog, known, "extended", Stop.MAX_NEW_TERMS, "5 new terms", True, 3, recs, preds,
                         run, verified_at_s=1.25)


HUGE = 7 ** 1500          # 1268 digits


def test_a_pending_win_survives_the_round_trip():
    result = a_win(HUGE)
    raw = attempt._dump_pending(result, "The primes.", Budgets(verify_wall_s=11))
    back, entry_name, budgets = attempt._load_pending(raw)

    assert entry_name == "The primes." and budgets == Budgets(verify_wall_s=11)
    assert back.stop is Stop.MAX_NEW_TERMS and back.run.status is Status.STOPPED   # enums, not bare str
    assert back.known.values == {1: 2, 2: 3, 3: 5}                                 # int keys and values
    assert back.program.script is not None and back.program.sha == result.program.sha
    assert [t.value for t in back.new_terms] == [HUGE] and back.new_terms[0].n == 4
    assert back.verified and back.reproduced == 3 and back.verified_at_s == 1.25
    assert back.predictions[0].next_bits_high is None and back.predictions[0].actual_s == 1.5
    assert back.scratch is None and back.run.stderr_tail == "a warning\n"
    assert attempt._dump_pending(back, entry_name, budgets) == raw                 # and it is stable


def test_an_artifact_from_a_reloaded_win_is_byte_identical(tmp_path):
    result = a_win(HUGE)
    back, name, budgets = attempt._load_pending(attempt._dump_pending(result, "The primes.", Budgets()))
    one = artifact.write(result, 1, name, budgets, "still new", root=tmp_path / "before")
    two = artifact.write(back, 1, name, budgets, "still new", root=tmp_path / "after")
    assert sorted(p.name for p in one.iterdir()) == sorted(p.name for p in two.iterdir())
    for p in sorted(one.iterdir()):
        assert p.read_bytes() == (two / p.name).read_bytes(), p.name


def test_the_bfile_ends_with_a_blank_line_and_the_readme_fence_does_not(tmp_path):
    """https://oeis.org/SubmitB.html requires a b-file to end with a blank line, warning in capitals that
    the last data line may otherwise be ignored -- and the last data line is the highest new term, the
    whole point of the run. Nothing else pins this: the byte-identical test above compares one artifact
    with another, so a file missing the blank line in both passes it.

    The second half pins *where* the fix lives. It is at the call site, not in `terms.format_bfile`,
    because the README formats the new terms with the same helper inside a ``` fence whose closing
    fence sits directly on the helper's trailing newline. Moving the fix into the helper would satisfy
    the first assertion and silently push that fence apart, so this test fails on that too."""
    folder = artifact.write(a_win(), 1, "The primes.", Budgets(), "still new", root=tmp_path)

    # read_text() normalises CRLF, so this holds on Windows (\r\n\r\n) and POSIX (\n\n) alike
    body = (folder / "b999999.txt").read_text(encoding="utf-8")
    assert body.endswith("\n\n"), repr(body[-12:])
    assert body.splitlines()[-2:] == ["4 71", ""]   # the blank line is extra, not a replaced data line
    assert [ln for ln in body.splitlines() if ln] == ["1 2", "2 3", "3 5", "4 71"]

    readme = (folder / "README.md").read_text(encoding="utf-8")
    assert "4 71\n```" in readme, "the new-terms fence gained a blank line"


def test_predictions_csv_columns_line_up_with_their_header(tmp_path):
    """The reviewer reads this file to judge a projection, so a header that has drifted out of step with
    its rows is a silent lie. Nothing else pins it: the byte-identical test above compares one artifact
    against another, so the same misalignment in both would pass it."""
    result = a_win()
    # Two rows, because a column swap is static: it shows only where the two columns differ, and four
    # booleans cannot render as four distinct strings in one row. What has to be distinct is each
    # column's pair of values down the two rows -- all 18 pairs below are, so no two columns can trade
    # places unseen. With one row, `feasible`/`fit_trustworthy` (both "True"),
    # `trustworthy`/`fit_climbing` (both "False") and `actual_mem`/`censored_s` (both "") could.
    result.predictions[:] = [
        Prediction(4, "work", 0.5, 0.5, 2.0, 1e6, "exp", False, True, True, False, 10,
                   ["fits"], actual_s=1.5, fit_trustworthy=True, fit_npoints=5,
                   fit_disagreement=1.75, fit_climbing=False, rate_drift=7.794),
        Prediction(5, "cpu", 4.0, 2.0, 4.0, 2e6, "ratio", False, False, True, False, 10,
                   ["a", "b"], actual_mem=9e7, censored_s=2.5, fit_trustworthy=True, fit_npoints=4,
                   fit_disagreement=2.5, fit_climbing=True, rate_drift=1.5),
    ]
    folder = artifact.write(result, 1, "The primes.", Budgets(), "still new", root=tmp_path)
    header, *rows = list(csv.reader((folder / "predictions.csv").read_text(encoding="utf-8").splitlines()))
    # the order is documented in data-and-schema.md, so it is pinned too: a dict comparison alone would
    # let the whole file be reordered consistently with nothing failing
    assert header == ["n", "unit", "model", "trustworthy", "feasible", "predicted_s", "predicted_s_low",
                      "predicted_s_high", "predicted_mem", "actual_s", "actual_mem", "censored_s",
                      "fit_trustworthy", "fit_npoints", "fit_disagreement", "fit_climbing", "rate_drift",
                      "reasons"]
    assert len(rows) == 2
    assert dict(zip(header, rows[0], strict=True)) == {
        "n": "4", "unit": "work", "model": "exp", "trustworthy": "False", "feasible": "True",
        "predicted_s": "0.5", "predicted_s_low": "0.5", "predicted_s_high": "2.0",
        "predicted_mem": "1000000.0", "actual_s": "1.5", "actual_mem": "", "censored_s": "",
        # the pair that has to survive: the kill said no, the cost fit itself said yes
        "fit_trustworthy": "True", "fit_npoints": "5", "fit_disagreement": "1.75",
        "fit_climbing": "False", "rate_drift": "7.794", "reasons": "fits",
    }
    assert dict(zip(header, rows[1], strict=True)) == {
        "n": "5", "unit": "cpu", "model": "ratio", "trustworthy": "False", "feasible": "False",
        "predicted_s": "4.0", "predicted_s_low": "2.0", "predicted_s_high": "4.0",
        "predicted_mem": "2000000.0", "actual_s": "", "actual_mem": "90000000.0", "censored_s": "2.5",
        "fit_trustworthy": "True", "fit_npoints": "4", "fit_disagreement": "2.5",
        "fit_climbing": "True", "rate_drift": "1.5", "reasons": "a | b",
    }


def test_the_saved_file_is_plain_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    attempt._save_pending(7, a_win(), "The primes.", Budgets())
    raw = attempt.pending_path(7).read_bytes()
    assert attempt.pending_path(7).name == "attempt-7.json"
    assert b"\r" not in raw                                   # text mode would have written CRLF here
    assert json.loads(raw)["format"] == attempt.PENDING_FORMAT


@pytest.mark.parametrize("damage, message", [
    (lambda d: d["result"]["program"].pop("script"), "Program: saved fields do not match"),
    (lambda d: d["result"]["run"].update(gpu_s=1.0), "RunResult: saved fields do not match"),
    (lambda d: d["result"]["records"][0].pop("dwork"), "TermRecord: saved fields do not match"),
    (lambda d: d["budgets"].pop("max_new_terms"), "Budgets: saved fields do not match"),
    (lambda d: d["result"].pop("verified_at_s"), "AttemptResult: saved fields do not match"),
    (lambda d: d["result"]["known"].pop("notes"), "KnownTerms: saved fields do not match"),
    (lambda d: d["result"]["predictions"][0].update(risk=1), "Prediction: saved fields do not match"),
    (lambda d: d.update(format=attempt.PENDING_FORMAT + 1),
     rf"format {attempt.PENDING_FORMAT + 1}, expected {attempt.PENDING_FORMAT}"),
])
def test_a_saved_win_that_no_longer_matches_the_code_is_a_loud_error(damage, message):
    """The point of the format: a field added or removed since the save must not reload as a default.
    Such a win stays `recheck_pending` with the error logged, exactly as an unreadable file always has."""
    saved = json.loads(attempt._dump_pending(a_win(), "The primes.", Budgets()))
    damage(saved)
    with pytest.raises(ValueError, match=message):
        attempt._load_pending(json.dumps(saved).encode("utf-8"))


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
    monkeypatch.setattr(attempt, "pending_path", lambda attempt_id: tmp_path / f"missing-{attempt_id}.json")

    assert cli.main(["recheck"]) == 0
    assert "no wins are waiting" in capsys.readouterr().out

    attempt_id = pending_row(conn)
    with pytest.raises(SystemExit) as exit_info:      # non-zero exit, so a script notices one is left
        cli.main(["recheck"])
    assert "1 win(s) still waiting" in str(exit_info.value)
    assert f"attempt #{attempt_id}: still pending (FileNotFoundError" in capsys.readouterr().out
    assert db.pending_recheck(conn, "A999999")["id"] == attempt_id
    conn.close()
