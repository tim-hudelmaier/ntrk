"""The lineage record schema (v1)."""

import uuid
from datetime import datetime, timezone

SCHEMA_VERSION = 1


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id():
    return uuid.uuid4().hex


def build(commit, branch_name, cwd_rel, script, command, inputs, outputs,
          ts=None, rid=None):
    """Assemble one run record. ``script`` is ``{path, blob, md5}`` or None;
    ``inputs``/``outputs`` are lists of ``{path, md5, size}``."""
    return {
        "v": SCHEMA_VERSION,
        "id": rid or new_id(),
        "ts": ts or now_iso(),
        "git": {"commit": commit, "branch": branch_name},
        "cwd": cwd_rel,
        "script": script,
        "command": list(command),
        "inputs": inputs,
        "outputs": outputs,
    }
