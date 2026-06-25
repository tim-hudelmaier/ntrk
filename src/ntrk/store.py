"""Storage: the append-only central log plus per-output sidecars.

The log (``.ntrk/runs.jsonl``) is the source of truth — committable,
greppable, rename-robust by md5. Each output also gets an invisible
self-contained sidecar (``.NAME.ntrk``) so a file can be traced even when copied
outside the repo.
"""

import fcntl
import json
import os
from pathlib import Path

from . import hashing

STORE_DIR = ".ntrk"
LOG_NAME = "runs.jsonl"


# --- central log ----------------------------------------------------------

def store_dir(root):
    return Path(root) / STORE_DIR


def log_path(root):
    return store_dir(root) / LOG_NAME


def ensure_store(root):
    """Create ``.ntrk/`` with the log and a union-merge .gitattributes."""
    d = store_dir(root)
    d.mkdir(exist_ok=True)
    log = d / LOG_NAME
    if not log.exists():
        log.touch()
    ga = d / ".gitattributes"
    if not ga.exists():
        ga.write_text(f"{LOG_NAME} merge=union\n", encoding="utf-8")
    return log


def append(root, rec):
    """Append one record as a single JSON line, serialized under an exclusive
    lock so concurrent runs never interleave."""
    ensure_store(root)
    line = json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n"
    with open(log_path(root), "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def read_records(root):
    if root is None:
        return []
    log = log_path(root)
    if not log.exists():
        return []
    records = []
    with open(log, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


# --- sidecars --------------------------------------------------------------

def sidecar_path(output_path):
    p = Path(output_path)
    return p.with_name("." + p.name + ".ntrk")


def write_sidecar(root, output_rel, rec):
    side = sidecar_path(Path(root) / output_rel)
    data = dict(rec)
    data["sidecar_for"] = output_rel
    tmp = side.with_name(side.name + ".tmp")
    tmp.write_text(
        json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, side)


def read_sidecar(target):
    side = sidecar_path(Path(target))
    if not side.exists():
        return None
    try:
        data = json.loads(side.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


# --- resolution & lineage links -------------------------------------------

def md5_for_output(rec, output_rel):
    """The recorded md5 of ``output_rel`` within ``rec``."""
    outs = rec.get("outputs", [])
    for o in outs:
        if o.get("path") == output_rel:
            return o.get("md5")
    # only guess the sole output when no specific path was asked for
    if output_rel is None and len(outs) == 1:
        return outs[0].get("md5")
    return None


def producer_of(records, md5):
    """Newest record whose outputs contain ``md5`` -> (record, output_rel)."""
    for rec in reversed(records):
        for o in rec.get("outputs", []):
            if o.get("md5") == md5:
                return rec, o.get("path")
    return None, None


def producer_before(records, md5, before_idx, exclude_id=None):
    """Newest record strictly before ``before_idx`` whose outputs contain
    ``md5`` (skipping ``exclude_id``) -> (record, output_rel, index).

    The trace walk uses this so an input always links to an *earlier* producer,
    never to the consuming run itself or a later one that re-emits the same
    bytes (which would mis-attribute byte-identical chain files)."""
    for i in range(min(before_idx, len(records)) - 1, -1, -1):
        rec = records[i]
        if rec.get("id") == exclude_id:
            continue
        for o in rec.get("outputs", []):
            if o.get("md5") == md5:
                return rec, o.get("path"), i
    return None, None, None


def _rel_to_root(root, target):
    if root is None:
        return None
    try:
        return Path(target).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return None


def resolve(root, target):
    """Find the run that produced ``target`` -> (record, output_rel).

    Order: sidecar next to the file -> exact (same path AND same bytes) ->
    content match (rename-robust) -> path match (file changed since produced).
    Returns (None, None) if nothing produced it.
    """
    target = Path(target)

    side = read_sidecar(target)
    if side is not None:
        return side, side.get("sidecar_for")

    records = read_records(root)
    rel = _rel_to_root(root, target)

    on_disk_md5 = None
    if target.exists():
        try:
            on_disk_md5, _ = hashing.md5_file(target)
        except OSError:
            on_disk_md5 = None

    # 1. exact: same recorded path AND same content (most specific)
    if rel is not None and on_disk_md5 is not None:
        for rec in reversed(records):
            for o in rec.get("outputs", []):
                if o.get("path") == rel and o.get("md5") == on_disk_md5:
                    return rec, rel
    # 2. content match (survives renames of unchanged files)
    if on_disk_md5 is not None:
        rec, out_rel = producer_of(records, on_disk_md5)
        if rec is not None:
            return rec, out_rel
    # 3. path match (file changed since it was produced)
    if rel is not None:
        for rec in reversed(records):
            for o in rec.get("outputs", []):
                if o.get("path") == rel:
                    return rec, rel
    return None, None
