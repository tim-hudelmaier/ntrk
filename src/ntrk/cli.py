"""ntrk CLI: two verbs, no options.

    nt track <command...>    run a command, record how each output was made
    nt trace <file>          print how a file was made, back to raw inputs
"""

import subprocess
import sys
from pathlib import Path

from . import config, gitutil, hashing, parse, record, store

USAGE = (
    "usage: nt <track|trace> ...\n"
    "  nt track <command...>   run a command and record its lineage\n"
    "  nt trace <file>         show how a file was made\n"
)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        sys.stderr.write(USAGE)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "track":
        return cmd_track(rest)
    if cmd == "trace":
        return cmd_trace(rest)
    sys.stderr.write(USAGE)
    return 2


# --- track -----------------------------------------------------------------

def _to_rel(root, given):
    """Resolve a command path argument (relative to cwd) to a root-relative
    posix path. Returns (rel_or_None, abspath)."""
    ap = (Path.cwd() / given).resolve()
    try:
        return ap.relative_to(Path(root).resolve()).as_posix(), ap
    except ValueError:
        return None, ap


def _collect(root, tokens, kind):
    """Hash existing in-tree files among ``tokens``; warn-and-skip the rest."""
    items = []
    for tok in tokens:
        rel, ap = _to_rel(root, tok)
        if rel is None:
            sys.stderr.write(f"nt: {kind} outside repo, not tracked: {tok}\n")
            continue
        if not ap.exists():
            sys.stderr.write(f"nt: {kind} not found, not tracked: {tok}\n")
            continue
        try:
            md5, size = hashing.md5_file(ap)
        except OSError as e:
            sys.stderr.write(f"nt: cannot read {kind} {tok}: {e}\n")
            continue
        items.append({"path": rel, "md5": md5, "size": size})
    return items


def cmd_track(rest):
    if not rest:
        sys.stderr.write("usage: nt track <command...>\n")
        return 2

    try:
        root = gitutil.repo_root()
    except gitutil.GitError:
        sys.stderr.write("nt: not a git repository\n")
        return 1

    dirty = gitutil.dirty_paths(root)
    if dirty:
        sys.stderr.write(
            "nt: refusing to run — commit your changes first "
            "(every run maps to a commit):\n"
        )
        for p in dirty:
            sys.stderr.write(f"    {p}\n")
        return 1

    try:
        commit = gitutil.head_commit(root)
        branch_name = gitutil.branch(root)
    except gitutil.GitError:
        sys.stderr.write("nt: repository has no commits yet\n")
        return 1

    cfg = config.load(root)
    parsed = parse.parse(rest, cfg)

    inputs = _collect(root, parsed.inputs, "input")

    proc = subprocess.run(rest)
    if proc.returncode != 0:
        return proc.returncode

    outputs = _collect(root, parsed.outputs, "output")
    if not outputs:
        sys.stderr.write("nt: no tracked outputs produced; nothing recorded.\n")
        return proc.returncode

    script_meta = None
    if parsed.script:
        rel, ap = _to_rel(root, parsed.script)
        if rel is not None and ap.exists():
            md5, _ = hashing.md5_file(ap)
            script_meta = {"path": rel, "blob": gitutil.blob_hash(root, rel), "md5": md5}
        else:
            script_meta = {"path": parsed.script, "blob": None, "md5": None}

    cwd_rel = _to_rel(root, ".")[0] or "."
    rec = record.build(commit, branch_name, cwd_rel, script_meta, rest, inputs, outputs)
    store.append(root, rec)
    for o in outputs:
        store.write_sidecar(root, o["path"], rec)

    sys.stderr.write(
        f"nt: recorded {rec['id'][:8]} ({len(outputs)} output(s)); "
        "commit .ntrk/runs.jsonl to keep it.\n"
    )
    return 0


# --- trace -----------------------------------------------------------------

def cmd_trace(rest):
    if len(rest) != 1:
        sys.stderr.write("usage: nt trace <file>\n")
        return 2
    target = rest[0]
    try:
        root = gitutil.repo_root()
    except gitutil.GitError:
        root = None

    lines = _trace_chain(root, target)
    if not lines:
        sys.stderr.write(f"nt: no lineage found for {target}\n")
        return 1
    for line in lines:
        sys.stdout.write(line + "\n")
    return 0


def _trace_chain(root, target):
    records = store.read_records(root)
    first, out_rel = store.resolve(root, target)
    if first is None:
        return []

    index_by_id = {r.get("id"): i for i, r in enumerate(records)}
    start_idx = index_by_id.get(first.get("id"), len(records))

    steps = []          # (record, output_rel), discovered newest -> oldest
    visited = set()

    def walk(rec, output_rel, idx):
        key = (rec.get("id"), output_rel)
        if key in visited:
            return
        visited.add(key)
        steps.append((rec, output_rel))
        for inp in rec.get("inputs", []):
            prod, prod_out, prod_idx = store.producer_before(
                records, inp.get("md5"), idx, exclude_id=rec.get("id")
            )
            if prod is not None:
                walk(prod, prod_out, prod_idx)

    walk(first, out_rel, start_idx)
    steps.reverse()  # roots first -> reads left-to-right, top-to-bottom
    return [_format_step(root, rec, output_rel) for rec, output_rel in steps]


def _marker(root, path_rel, recorded_md5):
    if root is None or path_rel is None or recorded_md5 is None:
        return ""
    ap = Path(root) / path_rel
    if not ap.exists():
        return " [missing]"
    try:
        cur, _ = hashing.md5_file(ap)
    except OSError:
        return ""
    return "" if cur == recorded_md5 else " [modified]"


def _format_step(root, rec, output_rel):
    ins = rec.get("inputs", [])
    if ins:
        in_str = ", ".join(
            i.get("path", "?") + _marker(root, i.get("path"), i.get("md5"))
            for i in ins
        )
    else:
        in_str = "(no tracked inputs)"
    script = (rec.get("script") or {}).get("path") or "?"
    commit = (rec.get("git") or {}).get("commit", "")[:7]
    out_str = (output_rel or "?") + _marker(root, output_rel, store.md5_for_output(rec, output_rel))
    return f"{in_str} -> {script} @ {commit} -> {out_str}"
