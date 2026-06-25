"""Thin, read-only git interface. ntrk never mutates git state."""

import subprocess
from pathlib import Path


class GitError(Exception):
    pass


def _git(args, cwd):
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def repo_root(cwd="."):
    """Absolute path to the git work-tree root. Raises GitError outside a repo."""
    out = _git(["rev-parse", "--show-toplevel"], cwd)
    return Path(out.strip())


def head_commit(root):
    """40-char commit sha of HEAD. Raises GitError if there are no commits."""
    return _git(["rev-parse", "HEAD"], root).strip()


def branch(root):
    return _git(["rev-parse", "--abbrev-ref", "HEAD"], root).strip()


def blob_hash(root, relpath):
    """git blob sha of ``relpath`` at HEAD, or None if untracked / no commits."""
    try:
        return _git(["rev-parse", f"HEAD:{relpath}"], root).strip()
    except GitError:
        return None


def _is_ntrk_file(path):
    # Only ntrk's own artifacts: the .ntrk/ dir and dot-prefixed
    # `.NAME.ntrk` sidecars. A genuine experiment file named e.g. `model.ntrk`
    # is NOT excluded — it must still count toward a dirty tree.
    name = path.rsplit("/", 1)[-1]
    return (
        path == ".ntrk"
        or path.startswith(".ntrk/")
        or (name.startswith(".") and name.endswith(".ntrk"))
    )


def dirty_paths(root):
    """Porcelain paths that count as 'dirty', excluding ntrk's own files.

    Uses ``--porcelain -z`` so paths with spaces/unicode aren't quoted/escaped
    and rename entries are unambiguous (the original path follows in its own
    NUL-separated field)."""
    # -uall lists untracked files individually (not collapsed to a dir) so a
    # sidecar in a new directory can be excluded by name.
    out = _git(["status", "--porcelain", "-z", "-uall"], root)
    fields = out.split("\0")
    dirty = []
    i = 0
    while i < len(fields):
        entry = fields[i]
        if not entry:
            i += 1
            continue
        status, path = entry[:2], entry[3:]
        # rename/copy: the next field is the original path; skip it.
        if status[:1] in ("R", "C") or status[1:2] in ("R", "C"):
            i += 2
        else:
            i += 1
        if not _is_ntrk_file(path):
            dirty.append(path)
    return dirty


def is_clean(root):
    return not dirty_paths(root)
