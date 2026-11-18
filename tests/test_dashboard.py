from __future__ import annotations

import argparse

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from oeisbot import config, db  # noqa: E402
from oeisbot.dashboard import app as dashboard  # noqa: E402

from .test_db import make_result  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "t.sqlite3"
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path / "artifacts")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    conn = db.connect(path)
    db.upsert_sequences(conn, [db.SequenceRow("A000001", "Test sequence", 0, "nonn,more", 20, 3, "pari", 0, False),
                               db.SequenceRow("A000002", "Other sequence", 0, "nonn,more", 20, 3, "pari", 0, False)])
    aid = db.record_attempt(conn, make_result(), started_at="2026-09-17T10:00:00+00:00")
    folder = tmp_path / "artifacts" / "A000001" / f"attempt-{aid}"
    folder.mkdir(parents=True)
    (folder / "README.md").write_text("# hello")
    (tmp_path / "secret.txt").write_text("nope")
    db.add_review(conn, "A000001", aid, f"artifacts/A000001/attempt-{aid}", 2, 3)
    conn.close()
    return TestClient(dashboard.app)


def test_endpoints(client):
    assert client.get("/api/summary").json()["wins"] == 1
    est = client.get("/api/estimator").json()
    assert est["stats"]["finished"] == 2 and est["stats"]["within_2x"] == 1.0
    assert [r["a_number"] for r in client.get("/api/queue").json()["rows"]] == ["A000002"]   # open review excluded
    att = client.get("/api/attempts?outcome=extended").json()
    assert len(att["rows"]) == 1 and att["failure_counts"] == {"max_new_terms": 1}
    reviews = client.get("/api/reviews").json()["rows"]
    assert reviews[0]["files"] == ["README.md"]
    assert client.get("/api/history").json()["days"][0]["wins"] == 1


def test_artifact_files_are_confined(client):
    rid = client.get("/api/reviews").json()["rows"][0]["id"]
    assert client.get(f"/api/reviews/{rid}/files/README.md").text == "# hello"
    for evil in ("..%2F..%2F..%2Fsecret.txt", r"..\..\..\secret.txt"):
        r = client.get(f"/api/reviews/{rid}/files/{evil}")
        assert r.status_code == 404 and "nope" not in r.text
    assert client.get(f"/api/reviews/{rid}/files/nope.md").status_code == 404


def test_api_never_writes(client, monkeypatch):
    """Every connection an endpoint opens is read-only and the database file itself is not touched. What this
    does not cover: SQLite rewrites the `-shm` file beside a WAL database on every read, read-only or not
    (docs/known-limitations.md), so "nothing on disk changes" is not the claim."""
    from oeisbot import attempt, select
    monkeypatch.setattr(attempt, "session_pool", lambda conn, budgets, *, model, alpha=1.0: (
        [select.Candidate("A000001", "Test sequence", 1.0, 1.0, "pari"), select.Candidate("A000002", "Other sequence", 2.0, 0.5, "pari")],
        attempt.Runnable(conn, budgets, model)))
    monkeypatch.setattr(dashboard, "_live", {})
    opened = []
    real_connect = db.connect

    def spy(*args, **kwargs):
        opened.append(kwargs.get("readonly", False))
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(db, "connect", spy)
    before = config.DB_PATH.stat().st_mtime_ns
    for path in ["/api/summary", "/api/estimator", "/api/queue", "/api/attempts", "/api/reviews", "/api/history",
                 "/api/pickmap", "/api/pickmap?pool=model&alpha=2&refresh=true"]:
        assert client.get(path).status_code == 200
    assert opened and all(opened)                                        # every connection the endpoints made was read-only
    conn = real_connect(config.DB_PATH, readonly=True)
    with pytest.raises(Exception):
        conn.execute("UPDATE reviews SET status = 'submitted'")
    assert config.DB_PATH.stat().st_mtime_ns == before


# ---------------------------------------------------------------- item 56: the defect sweep of 2026-11-17

def _extended(conn, a_number="A000002"):
    """A second `extended` attempt, for another sequence, with its review."""
    aid = db.record_attempt(conn, make_result(), started_at="2026-09-18T10:00:00+00:00")
    conn.execute("UPDATE attempts SET a_number = ? WHERE id = ?", (a_number, aid))
    conn.commit()
    return aid, db.add_review(conn, a_number, aid, f"artifacts/{a_number}/attempt-{aid}", 2, 3)


def test_a_rejected_win_is_not_a_win_anywhere(client):
    conn = db.connect(config.DB_PATH)
    sid = db.start_session(conn, "count=2")
    aid, rid = _extended(conn)
    conn.execute("UPDATE attempts SET session_id = ? WHERE id = ?", (sid, aid))
    conn.execute("UPDATE sessions SET wins = 1, attempts = 1 WHERE id = ?", (sid,))     # as the session wrote it
    conn.commit()
    assert client.get("/api/summary").json()["wins"] == 2
    db.set_review_status(conn, rid, "rejected", "conjectural")
    conn.close()
    s = client.get("/api/summary").json()
    assert (s["wins"], s["rejected_wins"], s["new_terms"]) == (1, 1, 2)
    h = client.get("/api/history").json()
    assert [(d["day"], d["wins"], d["rejected_wins"]) for d in h["days"]] == [("2026-09-17", 1, 0), ("2026-09-18", 0, 1)]
    # the stored sessions.wins still says 1; the page is given the count from the attempts
    assert [(x["id"], x["wins"], x["rejected_wins"]) for x in h["sessions"]] == [(sid, 0, 1)]
    assert h["sessions_total"] == 1
    by_id = {r["id"]: r for r in client.get("/api/attempts").json()["rows"]}
    assert by_id[aid]["outcome"] == "extended" and by_id[aid]["win_rejected"] is True
    assert [r["win_rejected"] for i, r in by_id.items() if i != aid] == [False]


def test_a_refused_win_is_not_a_win_either(client):
    # db.record_win leaves such an attempt `extended` with no review row and extra.review_refused set
    conn = db.connect(config.DB_PATH)
    aid = db.record_attempt(conn, make_result(), started_at="2026-09-19T10:00:00+00:00")
    conn.execute("UPDATE attempts SET extra = json_set(COALESCE(extra, '{}'), '$.review_refused', json(?)) WHERE id = ?",
                 ('{"prior_review": 1}', aid))
    conn.commit()
    conn.close()
    s = client.get("/api/summary").json()
    assert (s["wins"], s["rejected_wins"], s["new_terms"]) == (1, 1, 2)
    last = client.get("/api/history").json()["days"][-1]
    assert (last["day"], last["attempts"], last["wins"], last["rejected_wins"]) == ("2026-09-19", 1, 0, 1)


@pytest.mark.parametrize("query", ["alpha=nan", "alpha=inf", "alpha=-inf", "alpha=-1", "alpha=700", "alpha=6.01",
                                   "limit=-1", "limit=-30000", "limit=30001", "sort=name"])
def test_the_queue_refuses_what_it_cannot_weigh(client, query):
    assert client.get(f"/api/queue?{query}").status_code == 422


def test_the_queue_accepts_the_whole_documented_range(client):
    for query in ("alpha=0", "alpha=6", "limit=0", "limit=30000"):
        assert client.get(f"/api/queue?{query}").status_code == 200, query
    assert client.get("/api/queue?limit=0").json()["rows"] == []


@pytest.mark.parametrize("path", ["/api/attempts?limit=-1", "/api/attempts?limit=-9223372036854775809",
                                  "/api/attempts?limit=5001", "/api/reviews/99999999999999999999999/files/README.md",
                                  "/api/reviews/0/files/README.md", "/api/reviews/-1/files/README.md",
                                  "/api/history?session_limit=-1"])
def test_numbers_out_of_range_are_refused_not_crashed_on(client, path):
    assert client.get(path).status_code == 422


def test_attempts_say_how_many_there_are_and_count_a_missing_reason_as_none(client):
    conn = db.connect(config.DB_PATH)
    for _ in range(3):
        aid = db.record_attempt(conn, make_result(verified=False), started_at="2026-09-20T10:00:00+00:00")
    conn.execute("UPDATE attempts SET failure_mode = NULL WHERE id = ?", (aid,))
    conn.commit()
    conn.close()
    out = client.get("/api/attempts?limit=2").json()
    assert len(out["rows"]) == 2 and out["total"] == 4
    assert out["failure_counts"] == {"max_new_terms": 3, "none": 1}
    none = client.get("/api/attempts?failure_mode=none").json()
    assert [r["id"] for r in none["rows"]] == [aid] and none["total"] == 1
    assert client.get("/api/attempts?outcome=failed").json()["total"] == 3


def test_the_estimator_says_which_points_finished_and_survives_a_missing_high(client):
    conn = db.connect(config.DB_PATH)
    ids = [r[0] for r in conn.execute("SELECT id FROM predictions ORDER BY id")]
    conn.execute("UPDATE predictions SET actual_s = 0, censored_s = 30 WHERE id = ?", (ids[0],))
    conn.execute("UPDATE predictions SET predicted_s_high = NULL WHERE id = ?", (ids[1],))
    conn.commit()
    conn.close()
    est = client.get("/api/estimator").json()
    assert [(p["id"], p["finished"]) for p in est["points"]] == [(ids[0], False), (ids[1], True)]
    assert est["stats"]["finished"] == 1 and est["stats"]["censored"] == 1
    assert est["stats"]["in_reported_range_2x"] == 0.0          # no range to be inside; it used to raise


def test_only_the_root_is_the_page_and_everything_unknown_is_a_404(client, monkeypatch, tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>page</title>")
    monkeypatch.setattr(dashboard, "STATIC", static)
    root = client.get("/")
    assert root.status_code == 200 and "page" in root.text
    for path in ("/api", "/api/", "/api/nope", "/API/summary", "/Api/summary", "/docs", "/redoc", "/openapi.json",
                 "/index.html", "/estimator", "/favicon.ico"):
        r = client.get(path)
        assert r.status_code == 404 and "page" not in r.text, path
    assert client.get("/api/docs").status_code == 200           # the interactive docs the documentation names
    assert client.get("/api/openapi.json").status_code == 200
    monkeypatch.setattr(dashboard, "STATIC", tmp_path / "not-built")
    assert client.get("/").status_code == 404                   # and without a build there is no page at all


@pytest.mark.parametrize("header, name", [
    ("127.0.0.1:8765", "127.0.0.1"), ("localhost", "localhost"), ("LocalHost:80", "localhost"),
    ("[::1]:8765", "::1"), ("[::1]", "::1"), ("  example.com:1 ", "example.com"), ("", ""), ("[::1", ""),
    # not a host and a port and nothing else: no host at all
    ("[::1]evil.example", ""), ("127.0.0.1:evil", ""), ("localhost:8765@evil.example", ""), ("user@127.0.0.1", ""),
    ("127.0.0.1:8765:1", ""), ("::1", ""), ("localhost/x", ""), ("local host", ""), ("localhost:", "localhost"),
])
def test_the_host_of_a_host_header(header, name):
    assert dashboard.host_name(header) == name


def test_a_request_addressed_to_another_name_is_refused(client, monkeypatch):
    monkeypatch.setattr(dashboard, "ALLOWED_HOSTS", {"127.0.0.1", "localhost", "::1"})
    for host in ("127.0.0.1:8765", "localhost:8765", "LOCALHOST", "[::1]:8765"):
        assert client.get("/api/summary", headers={"Host": host}).status_code == 200, host
    for host in ("attacker.example", "attacker.example:8765", "127.0.0.1.attacker.example", "testserver", "[::2]:8765"):
        r = client.get("/api/summary", headers={"Host": host})
        assert r.status_code == 400 and "wins" not in r.text, host
    assert client.get("/api/reviews/1/files/README.md", headers={"Host": "attacker.example"}).status_code == 400
    monkeypatch.setattr(dashboard, "ALLOWED_HOSTS", None)       # what a wildcard --host does
    assert client.get("/api/summary", headers={"Host": "anything.example"}).status_code == 200


def test_the_dashboard_command_allows_the_host_it_binds_and_no_other(monkeypatch, capsys):
    import uvicorn

    from oeisbot import cli
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
    monkeypatch.setattr(dashboard, "warm_live_pool", lambda *a, **k: None)
    args = lambda host: argparse.Namespace(host=host, port=8765)
    monkeypatch.setattr(dashboard, "ALLOWED_HOSTS", {"127.0.0.1", "localhost", "::1"})
    cli.cmd_dashboard(args("192.168.1.20"))
    assert dashboard.ALLOWED_HOSTS == {"127.0.0.1", "localhost", "::1", "192.168.1.20"}
    assert "warning" not in capsys.readouterr().out
    for wildcard in ("0.0.0.0", "::", "[::]", "0:0:0:0:0:0:0:0", "::0", "0"):
        monkeypatch.setattr(dashboard, "ALLOWED_HOSTS", {"127.0.0.1", "localhost", "::1"})
        cli.cmd_dashboard(args(wildcard))
        assert dashboard.ALLOWED_HOSTS is None
        assert "Host check is off" in capsys.readouterr().out


def test_a_request_from_another_page_is_refused_on_the_api_only(client, monkeypatch, tmp_path):
    for site in ("cross-site", "Cross-Site", "same-site", "anything-new"):   # same-site: another port of this machine
        assert client.get("/api/summary", headers={"Sec-Fetch-Site": site}).status_code == 403, site
    assert client.get("/API/summary", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    for site in ("same-origin", "none", " Same-Origin "):
        assert client.get("/api/summary", headers={"Sec-Fetch-Site": site}).status_code == 200, site
    assert client.get("/api/summary").status_code == 200        # curl, the CLI, this test client
    # the page itself may be linked to from anywhere
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>page</title>")
    monkeypatch.setattr(dashboard, "STATIC", static)
    assert client.get("/", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200


def test_a_row_whose_extra_is_not_json_does_not_take_the_counts_down(client):
    conn = db.connect(config.DB_PATH)
    conn.execute("UPDATE attempts SET extra = '{not json'")
    conn.commit()
    conn.close()
    assert client.get("/api/summary").json()["wins"] == 1
    assert client.get("/api/history").status_code == 200 and client.get("/api/attempts").status_code == 200


def test_an_endpoint_that_raises_still_answers_with_the_header(client, monkeypatch):
    def boom():
        raise RuntimeError("boom")
    monkeypatch.setattr(dashboard, "ro", boom)
    r = TestClient(dashboard.app, raise_server_exceptions=False).get("/api/summary")
    assert r.status_code == 500 and "boom" not in r.text
    assert r.headers["x-content-type-options"] == "nosniff"
    with pytest.raises(RuntimeError):                            # and a failure is still loud where it is asked to be
        client.get("/api/summary")


def test_every_response_forbids_content_type_guessing(client):
    rid = client.get("/api/reviews").json()["rows"][0]["id"]
    for path, headers in (("/api/summary", {}), (f"/api/reviews/{rid}/files/README.md", {}), ("/api/nope", {}),
                          ("/api/queue?alpha=nan", {}), ("/api/summary", {"Host": "attacker.example"}),
                          ("/api/summary", {"Sec-Fetch-Site": "cross-site"})):
        assert client.get(path, headers=headers).headers["x-content-type-options"] == "nosniff", path
