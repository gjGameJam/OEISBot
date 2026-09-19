from __future__ import annotations

import random
from collections import Counter

import pytest

from oeisbot import config, db, select
from oeisbot.ingest import bfile, oeisdata
from oeisbot.ingest.seqfile import parse, split_signed_programs

ENTRY = """\
%I A999999 #12 Jan 01 2026 00:00:00
%S A999999 1,2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79,83,89,
%T A999999 97,101,103,107,109,113
%N A999999 Smallest prime p such that something holds, test entry.
%H A999999 A. Person, <a href="/A999999/b999999.txt">Table of n, a(n) for n = 1..1000</a>
%t A999999 Table[Prime[n], {n, 30}]
%o A999999 (PARI) a(n) = prime(n) \\\\ _A. Person_, Jan 01 2026
%o A999999 (PARI) isok(k) = isprime(k)
%o A999999 (Python)
%o A999999 from sympy import prime
%o A999999 def a(n): return prime(n)
%K A999999 nonn,more,easy
%O A999999 1,2
%A A999999 _A. Person_, Jan 01 2026
%E A999999 More terms from _B. Person_, Feb 02 2026
%E A999999 a(40)-a(50) from _C. Person_, Mar 03 2026
"""


def test_parse_entry():
    e = parse(ENTRY)
    assert e.a_number == "A999999" and e.offset == 1
    assert e.data[:4] == [1, 2, 3, 5] and e.data[-1] == 113 and len(e.data) == 31
    assert e.data_values[1] == 1 and e.data_values[31] == 113
    assert e.keywords == ["nonn", "more", "easy"]
    assert e.languages == ["mathematica", "pari", "python"]
    assert [p.code for p in e.programs_in("pari")] == ["a(n) = prime(n) \\\\ _A. Person_, Jan 01 2026", "isok(k) = isprime(k)"]
    assert e.programs_in("python")[0].code == "from sympy import prime\ndef a(n): return prime(n)"
    assert e.more_credits == 2


def test_signed_data_preferred():
    text = "%S A000001 1,2,3\n%V A000001 1,-2,3\n%N A000001 x\n%O A000001 0,1\n%K A000001 sign\n"
    assert parse(text).data == [1, -2, 3]


def test_split_signed_programs():
    code = "a(n)=n \\\\ _X_, Jan 01 2020\nb(n)=2*n \\\\ _Y_, Feb 02 2021"
    assert split_signed_programs(code) == ["a(n)=n \\\\ _X_, Jan 01 2020", "b(n)=2*n \\\\ _Y_, Feb 02 2021"]


def test_parse_bfile():
    b = bfile.parse_bfile("A999999", "# comment\n1 1\n\n2 2\n3 5 # note\nbad line\n4 7\n")
    assert b.values == {1: 1, 2: 2, 3: 5, 4: 7}
    assert b.malformed == ["bad line"]


def test_known_terms_prefers_bfile_and_merges_data():
    e = parse(ENTRY)
    b = bfile.BFile("A999999", {n: v for n, v in e.data_values.items() if n <= 20})
    b.values.update({1: 1})
    k = bfile.known_terms(e, b)
    assert k.source == "bfile" and k.count == 31 and "DATA terms beyond" in k.notes[0]


def test_known_terms_rejects_conflicts_and_offset_errors():
    e = parse(ENTRY)
    with pytest.raises(bfile.InconsistentTerms, match="disagree at a\\(3\\)"):
        bfile.known_terms(e, bfile.BFile("A999999", {1: 1, 2: 2, 3: 4}))
    with pytest.raises(bfile.InconsistentTerms, match="offset"):
        bfile.known_terms(e, bfile.BFile("A999999", {0: 1, 1: 1}))


def test_fetch_uses_lfs_pointer_and_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OEISDATA", tmp_path / "oeisdata")
    monkeypatch.setattr(config, "BFILE_CACHE", tmp_path / "bfiles")
    (tmp_path / "oeisdata" / "files" / "A999").mkdir(parents=True)
    calls = []
    body = b"1 1\n2 2\n"
    monkeypatch.setattr(bfile, "http_get", lambda url, timeout=60: calls.append(url) or body)

    assert bfile.fetch("A999998") is None and calls == []          # no pointer: no b-file, no request
    assert bfile.cached("A999998") == (True, None)
    import hashlib
    (tmp_path / "oeisdata" / "files" / "A999" / "b999999.txt").write_text(
        f"version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(body).hexdigest()}\nsize {len(body)}\n")
    assert bfile.cached("A999999") == (False, None)                 # pointer, nothing cached: needs a request
    assert bfile.fetch("A999999").values == {1: 1, 2: 2} and len(calls) == 1
    assert bfile.fetch("A999999").values == {1: 1, 2: 2} and len(calls) == 1   # cache hit
    decided, bf = bfile.cached("A999999")
    assert decided and bf.values == {1: 1, 2: 2} and len(calls) == 1          # the same answer, offline
    (tmp_path / "oeisdata" / "files" / "A999" / "b999999.txt").write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:" + "0" * 64 + "\nsize 9\n")
    assert bfile.cached("A999999") == (False, None)                 # stale cache: cannot decide offline
    bfile.fetch("A999999")
    assert len(calls) == 2                                          # pointer changed: refetch


def test_cached_without_a_snapshot(tmp_path, monkeypatch):
    """No oeisdata mirror: a cached b-file is trusted as is, an `.absent` marker means no b-file, and
    anything else needs a request -- the same branches `fetch` takes before downloading."""
    monkeypatch.setattr(config, "OEISDATA", tmp_path / "no mirror")
    monkeypatch.setattr(config, "BFILE_CACHE", tmp_path / "bfiles")
    monkeypatch.setattr(bfile, "http_get", lambda url, timeout=60: pytest.fail("fetch made a request"))
    assert bfile.cached("A999999") == (False, None)
    path = bfile.cache_path("A999999")
    path.parent.mkdir(parents=True)
    path.with_suffix(".absent").touch()
    assert bfile.cached("A999999") == (True, None) and bfile.fetch("A999999") is None
    path.write_text("1 5\n2 6\n")               # a cached file wins over the marker
    decided, bf = bfile.cached("A999999")
    assert decided and bf.values == {1: 5, 2: 6} and bfile.fetch("A999999").values == {1: 5, 2: 6}


def test_fetch_rejects_an_html_page(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BFILE_CACHE", tmp_path / "bfiles")
    monkeypatch.setattr(bfile, "http_get", lambda url, timeout=60: b"<!DOCTYPE html>\n<html><body>slow down</body></html>")
    with pytest.raises(bfile.UnexpectedResponse, match="HTML page"):
        bfile.fetch("A999999", refresh=True)
    assert not bfile.cache_path("A999999").exists()


def write_seq(root, a_number: str, keywords: str, data: str | None = "1,2,3") -> None:
    path = root / "seq" / a_number[:4] / f"{a_number}.seq"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"%N {a_number} Test entry.", f"%O {a_number} 1,1", f"%K {a_number} {keywords}"]
    if data is not None:
        lines.insert(0, f"%S {a_number} {data}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_iter_more_entries_keeps_fini_and_drops_the_rest(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OEISDATA", tmp_path / "oeisdata")
    entries = {
        "A100001": "nonn,more",           # the ordinary case
        "A100002": "fini,more",           # finite but still missing terms: a candidate
        "A100003": "fini,full,more",      # every term is already shown
        "A100004": "dead,more",
        "A100005": "nonn,dumb,more",
        "A100006": "nonn,easy",           # not 'more'
    }
    for a, keywords in entries.items():
        write_seq(tmp_path / "oeisdata", a, keywords)
    write_seq(tmp_path / "oeisdata", "A100007", "nonn,more", data=None)      # no DATA terms
    assert [e.a_number for e in oeisdata.iter_more_entries()] == ["A100001", "A100002"]


def test_sync_records_candidates_and_drops_entries_that_lost_more(tmp_path, monkeypatch):
    root = tmp_path / "oeisdata"
    monkeypatch.setattr(config, "OEISDATA", root)
    monkeypatch.setattr(oeisdata, "_git", lambda *args, **kwargs: "c0ffee1234")
    write_seq(root, "A100001", "nonn,more")
    write_seq(root, "A100002", "fini,more")
    conn = db.connect(tmp_path / "t.sqlite3")
    try:
        assert oeisdata.sync(conn, log=lambda m: None, pull=False) == {
            "commit": "c0ffee1234", "candidates": 2, "gone": 0}
        assert db.get_meta(conn, "oeisdata_commit") == "c0ffee1234"

        write_seq(root, "A100002", "nonn,full")          # extended by a human since the last sync
        assert oeisdata.sync(conn, log=lambda m: None, pull=False)["gone"] == 1
        rows = conn.execute("SELECT a_number, in_more, difficulty FROM sequences ORDER BY a_number").fetchall()
        assert [(r["a_number"], r["in_more"]) for r in rows] == [("A100001", 1), ("A100002", 0)]
        assert all(r["difficulty"] > 0 for r in rows)
    finally:
        conn.close()


def test_sumtree_sampling_matches_weights():
    tree = select.SumTree([1.0, 0.0, 3.0, 6.0])
    rng = random.Random(0)
    counts = Counter(tree.sample(rng) for _ in range(20000))
    assert counts[1] == 0
    assert counts[3] / 20000 == pytest.approx(0.6, abs=0.02)
    assert counts[0] / 20000 == pytest.approx(0.1, abs=0.02)
    tree.update(3, 0.0)
    assert tree.total == pytest.approx(4.0)


def test_pick_without_replacement_and_alpha():
    pool = [select.Candidate(f"A{i:06d}", "", d, select.weight(d, 2.0), "pari") for i, d in enumerate([0.1, 1, 10, 100])]
    picks = select.pick(pool, 10, random.Random(1))
    assert len(picks) == 4 and len({p.a_number for p in picks}) == 4
    first = Counter(select.pick(pool, 1, random.Random(s))[0].a_number for s in range(2000))
    assert first["A000000"] > 1900        # alpha=2 strongly favors the easiest


def test_difficulty_features():
    base = dict(a_number="A1", name="Number of things", offset=0, keywords="nonn,more", data_terms=30,
                data_last_digits=5, program_langs="", more_credits=0, value_dependent=False)
    from oeisbot.db import SequenceRow
    plain = select.difficulty(SequenceRow(**base))
    assert select.difficulty(SequenceRow(**{**base, "program_langs": "pari"})) < plain
    assert select.difficulty(SequenceRow(**{**base, "keywords": "nonn,more,hard"})) > plain
    assert select.difficulty(SequenceRow(**{**base, "more_credits": 3})) > plain
    assert select.difficulty(SequenceRow(**{**base, "data_last_digits": 80})) > plain
