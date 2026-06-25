"""Regression tests for issues found in the adversarial review."""

import sys

from ntrk import cli, gitutil, store
from ntrk.config import Config, DEFAULT_INPUT_FLAGS, DEFAULT_OUTPUT_FLAGS
from ntrk.parse import parse
from ntrk.record import build
from conftest import commit_all


def _cfg():
    return Config(DEFAULT_INPUT_FLAGS, DEFAULT_OUTPUT_FLAGS)


# H2: only dot-prefixed *.ntrk sidecars are excluded from the dirty check.
def test_genuine_ntrk_artifact_counts_dirty(git_repo):
    (git_repo / "model.ntrk").write_text("weights")  # not a sidecar
    assert "model.ntrk" in gitutil.dirty_paths(git_repo)
    assert not gitutil.is_clean(git_repo)


def test_real_sidecar_in_subdir_excluded(git_repo):
    (git_repo / "results").mkdir()
    (git_repo / "results" / ".out.csv.ntrk").write_text("{}")
    assert gitutil.is_clean(git_repo)


# H3: paths with spaces are handled (porcelain -z, no quoting).
def test_path_with_spaces_is_dirty(git_repo):
    (git_repo / "a b.txt").write_text("x")
    assert "a b.txt" in gitutil.dirty_paths(git_repo)


# M5/L1: script detection skips classified inputs and handles versioned interpreters.
def test_script_detection_skips_input_source_file():
    p = parse(["python", "train.py", "-i", "config.py", "-o", "out.bin"], _cfg())
    assert p.script == "train.py"


def test_script_detection_versioned_interpreter():
    p = parse(["python3.13", "runme", "-i", "a"], _cfg())
    assert p.script == "runme"


# C1/C2: producer_before links to an earlier producer, never self/later.
def test_producer_before_prefers_earlier_not_self():
    def rec(rid, inputs, outputs):
        return build("c" * 40, "main", ".", None, ["cmd"], inputs, outputs,
                     ts="2026-01-01T00:00:00Z", rid=rid)

    recs = [
        rec("a", [], [{"path": "out.csv", "md5": "SAME", "size": 1}]),
        rec("b", [{"path": "out.csv", "md5": "SAME", "size": 1}],
            [{"path": "final.csv", "md5": "SAME", "size": 1}]),
    ]
    found, out, idx = store.producer_before(recs, "SAME", before_idx=1, exclude_id="b")
    assert found["id"] == "a" and out == "out.csv" and idx == 0


_COPY = (
    "import sys\n"
    "a = sys.argv[1:]\n"
    "open(a[a.index('-o') + 1], 'w').write(open(a[a.index('-i') + 1]).read())\n"
)


# C1/C2 end-to-end: a pure-copy chain (every file identical md5) still recovers
# both steps instead of collapsing to one.
def test_byte_identical_chain_keeps_both_steps(git_repo, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)
    (git_repo / "c1.py").write_text(_COPY)
    (git_repo / "c2.py").write_text(_COPY)
    (git_repo / "in.csv").write_text("same\n")
    (git_repo / ".gitignore").write_text("mid.csv\nfinal.csv\n")
    commit_all(git_repo, "copies")
    assert cli.cmd_track([sys.executable, "c1.py", "-i", "in.csv", "-o", "mid.csv"]) == 0
    assert cli.cmd_track([sys.executable, "c2.py", "-i", "mid.csv", "-o", "final.csv"]) == 0
    capsys.readouterr()
    cli.cmd_trace(["final.csv"])
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2
    assert out[0].endswith("-> mid.csv")
    assert out[1].endswith("-> final.csv")


# M4: a run that produces no tracked outputs records nothing.
def test_zero_output_run_not_recorded(git_repo, monkeypatch):
    monkeypatch.chdir(git_repo)
    (git_repo / "noop.py").write_text("print('hi')\n")
    commit_all(git_repo, "noop")
    rc = cli.cmd_track([sys.executable, "noop.py", "-i", "README.md"])
    assert rc == 0
    assert store.read_records(git_repo) == []


# H1: tracking from a subdirectory records correct root-relative paths.
def test_track_from_subdirectory(git_repo, monkeypatch):
    monkeypatch.chdir(git_repo)
    sub = git_repo / "sub"
    sub.mkdir()
    (sub / "s.py").write_text(
        "import sys\n"
        "a = sys.argv[1:]\n"
        "open(a[a.index('-o') + 1], 'w').write(open(a[a.index('-i') + 1]).read())\n"
    )
    (sub / "in.csv").write_text("hi\n")
    (git_repo / ".gitignore").write_text("sub/out.csv\n")
    commit_all(git_repo, "sub")

    monkeypatch.chdir(sub)
    rc = cli.cmd_track([sys.executable, "s.py", "-i", "in.csv", "-o", "out.csv"])
    assert rc == 0
    rec = store.read_records(git_repo)[-1]
    assert rec["outputs"][0]["path"] == "sub/out.csv"
    assert rec["inputs"][0]["path"] == "sub/in.csv"
