import subprocess

import pytest

from ntrk import gitutil
from conftest import commit_all


def test_repo_root_and_head(git_repo):
    root = gitutil.repo_root(git_repo)
    assert root == git_repo.resolve()
    assert len(gitutil.head_commit(git_repo)) == 40
    assert gitutil.branch(git_repo) == "main"


def test_clean_then_dirty(git_repo):
    assert gitutil.is_clean(git_repo)
    (git_repo / "README.md").write_text("changed\n")
    dirty = gitutil.dirty_paths(git_repo)
    assert "README.md" in dirty
    assert not gitutil.is_clean(git_repo)


def test_untracked_counts_as_dirty(git_repo):
    (git_repo / "new.txt").write_text("x")
    assert "new.txt" in gitutil.dirty_paths(git_repo)


def test_ntrk_files_excluded(git_repo):
    (git_repo / ".ntrk").mkdir()
    (git_repo / ".ntrk" / "runs.jsonl").write_text("{}\n")
    (git_repo / ".out.csv.ntrk").write_text("{}")
    # only ntrk's own files are dirty -> still considered clean
    assert gitutil.is_clean(git_repo)


def test_blob_hash_matches_git(git_repo):
    (git_repo / "f.txt").write_text("content\n")
    commit_all(git_repo, "add f")
    expected = subprocess.run(
        ["git", "hash-object", "f.txt"], cwd=git_repo,
        capture_output=True, text=True,
    ).stdout.strip()
    assert gitutil.blob_hash(git_repo, "f.txt") == expected


def test_not_a_repo(tmp_path):
    with pytest.raises(gitutil.GitError):
        gitutil.repo_root(tmp_path)
