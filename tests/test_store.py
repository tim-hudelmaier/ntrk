from ntrk import hashing, store
from ntrk.record import build


def _rec(rid, inputs, outputs):
    return build("c" * 40, "main", ".", None, ["cmd"], inputs, outputs, ts="2026-01-01T00:00:00Z", rid=rid)


def test_append_and_read_roundtrip(tmp_path):
    store.append(tmp_path, _rec("a", [], [{"path": "out.csv", "md5": "m1", "size": 1}]))
    store.append(tmp_path, _rec("b", [], [{"path": "out2.csv", "md5": "m2", "size": 2}]))
    recs = store.read_records(tmp_path)
    assert [r["id"] for r in recs] == ["a", "b"]


def test_read_records_missing_log(tmp_path):
    assert store.read_records(tmp_path) == []


def test_sidecar_path_naming():
    assert store.sidecar_path("results/out.csv").name == ".out.csv.ntrk"


def test_sidecar_roundtrip(tmp_path):
    rec = _rec("a", [], [{"path": "out.csv", "md5": "m1", "size": 1}])
    (tmp_path / "out.csv").write_text("x")
    store.write_sidecar(tmp_path, "out.csv", rec)
    loaded = store.read_sidecar(tmp_path / "out.csv")
    assert loaded["id"] == "a"
    assert loaded["sidecar_for"] == "out.csv"


def test_read_sidecar_absent(tmp_path):
    assert store.read_sidecar(tmp_path / "nope.csv") is None


def test_producer_of(tmp_path):
    recs = [
        _rec("a", [], [{"path": "out.csv", "md5": "M", "size": 1}]),
        _rec("b", [], [{"path": "x.csv", "md5": "N", "size": 1}]),
    ]
    rec, out = store.producer_of(recs, "M")
    assert rec["id"] == "a" and out == "out.csv"
    assert store.producer_of(recs, "missing") == (None, None)


def test_resolve_by_content_after_rename(tmp_path):
    # produced as out.csv; on disk now renamed to moved.csv but same bytes
    (tmp_path / "moved.csv").write_text("payload")
    md5, _ = hashing.md5_file(tmp_path / "moved.csv")
    store.append(tmp_path, _rec("a", [], [{"path": "out.csv", "md5": md5, "size": 7}]))
    rec, out_rel = store.resolve(tmp_path, tmp_path / "moved.csv")
    assert rec["id"] == "a"
    assert out_rel == "out.csv"


def test_resolve_by_path_when_content_changed(tmp_path):
    (tmp_path / "out.csv").write_text("ORIGINAL")
    store.append(tmp_path, _rec("a", [], [{"path": "out.csv", "md5": "stale", "size": 8}]))
    rec, out_rel = store.resolve(tmp_path, tmp_path / "out.csv")
    assert rec["id"] == "a" and out_rel == "out.csv"


def test_resolve_sidecar_first(tmp_path):
    rec = _rec("side", [], [{"path": "out.csv", "md5": "m", "size": 1}])
    (tmp_path / "out.csv").write_text("x")
    store.write_sidecar(tmp_path, "out.csv", rec)
    found, out_rel = store.resolve(tmp_path, tmp_path / "out.csv")
    assert found["id"] == "side" and out_rel == "out.csv"


def test_resolve_none(tmp_path):
    (tmp_path / "stray.csv").write_text("unknown")
    assert store.resolve(tmp_path, tmp_path / "stray.csv") == (None, None)
