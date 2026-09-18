from __future__ import annotations

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


def test_api_never_writes(client):
    before = config.DB_PATH.stat().st_mtime_ns
    for path in ["/api/summary", "/api/estimator", "/api/queue", "/api/attempts", "/api/reviews", "/api/history"]:
        assert client.get(path).status_code == 200
    conn = db.connect(config.DB_PATH, readonly=True)
    with pytest.raises(Exception):
        conn.execute("UPDATE reviews SET status = 'submitted'")
    assert config.DB_PATH.stat().st_mtime_ns == before
