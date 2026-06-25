import shutil
import sys

from ntrk import cli, store
from conftest import commit_all

# A trivial script: read the -i file, append a line, write to -o. Each step
# grows the content so every file along the chain has a distinct md5.
SCRIPT = (
    "import sys\n"
    "a = sys.argv[1:]\n"
    "src = a[a.index('-i') + 1]\n"
    "dst = a[a.index('-o') + 1]\n"
    "open(dst, 'w').write(open(src).read() + 'step\\n')\n"
)


def _setup_chain(repo, monkeypatch):
    monkeypatch.chdir(repo)
    (repo / "step1.py").write_text(SCRIPT)
    (repo / "step2.py").write_text(SCRIPT)
    (repo / "in.csv").write_text("hello\n")
    (repo / ".gitignore").write_text("out.csv\nout_final.csv\n")
    commit_all(repo, "add pipeline")

    rc1 = cli.cmd_track([sys.executable, "step1.py", "-i", "in.csv", "-o", "out.csv"])
    rc2 = cli.cmd_track([sys.executable, "step2.py", "-i", "out.csv", "-o", "out_final.csv"])
    assert rc1 == 0 and rc2 == 0
    assert (repo / "out_final.csv").read_text() == "hello\nstep\nstep\n"


def test_track_records_and_creates_sidecar(git_repo, monkeypatch):
    _setup_chain(git_repo, monkeypatch)
    recs = store.read_records(git_repo)
    assert len(recs) == 2
    assert (git_repo / ".out.csv.ntrk").exists()
    assert (git_repo / ".out_final.csv.ntrk").exists()


def test_trace_full_ancestry_forward_order(git_repo, monkeypatch, capsys):
    _setup_chain(git_repo, monkeypatch)
    capsys.readouterr()  # drop track's stderr
    rc = cli.cmd_trace(["out_final.csv"])
    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert len(out) == 2
    # forward / dependency order: raw input first, queried file last
    assert out[0].startswith("in.csv ") and out[0].endswith("-> out.csv")
    assert out[1].startswith("out.csv ") and out[1].endswith("-> out_final.csv")
    # tail -n 1 is the direct producer of the queried file
    assert "step2.py" in out[1]


def test_dirty_tree_refuses(git_repo, monkeypatch):
    _setup_chain(git_repo, monkeypatch)
    (git_repo / "step1.py").write_text(SCRIPT + "# tweak\n")  # dirty a tracked file
    rc = cli.cmd_track([sys.executable, "step1.py", "-i", "in.csv", "-o", "out.csv"])
    assert rc == 1


def test_modified_input_flagged(git_repo, monkeypatch, capsys):
    _setup_chain(git_repo, monkeypatch)
    (git_repo / "in.csv").write_text("TOTALLY DIFFERENT\n")
    capsys.readouterr()
    cli.cmd_trace(["out_final.csv"])
    out = capsys.readouterr().out
    assert "[modified]" in out


def test_trace_via_sidecar_outside_repo(git_repo, monkeypatch, capsys, tmp_path_factory):
    _setup_chain(git_repo, monkeypatch)
    exported = tmp_path_factory.mktemp("exported")
    shutil.copy(git_repo / "out_final.csv", exported / "out_final.csv")
    shutil.copy(git_repo / ".out_final.csv.ntrk", exported / ".out_final.csv.ntrk")
    monkeypatch.chdir(exported)
    capsys.readouterr()
    rc = cli.cmd_trace(["out_final.csv"])
    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    # only the immediate step is available from a lone sidecar
    assert len(out) == 1
    assert out[0].endswith("-> out_final.csv")


def test_trace_unknown_file_exits_1(git_repo, monkeypatch, capsys):
    _setup_chain(git_repo, monkeypatch)
    (git_repo / "mystery.txt").write_text("who made me")
    capsys.readouterr()
    rc = cli.cmd_trace(["mystery.txt"])
    assert rc == 1
    assert capsys.readouterr().out == ""
