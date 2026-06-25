import subprocess

import pytest


def run(args, cwd):
    return subprocess.run(args, cwd=str(cwd), check=True, capture_output=True, text=True)


def commit_all(repo, message="snapshot"):
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-qm", message], repo)


@pytest.fixture
def git_repo(tmp_path):
    """A fresh git repo with one initial commit."""
    run(["git", "init", "-q", "-b", "main"], tmp_path)
    run(["git", "config", "user.email", "t@example.com"], tmp_path)
    run(["git", "config", "user.name", "tester"], tmp_path)
    (tmp_path / "README.md").write_text("seed\n")
    commit_all(tmp_path, "init")
    return tmp_path
