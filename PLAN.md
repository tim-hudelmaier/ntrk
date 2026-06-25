# ntrk — Implementation Plan

**Wrap a command. Later, ask how any file was made.**

```
Install:   uv tool install ntrk
Use:       nt track <your command>     # run it, record how
           nt trace <file>             # how was this made?
```

That postcard is the entire tool. A pure-stdlib CLI that records how each output was produced —
exact command, git commit, and md5 hashes of every input and output — and walks any file's
lineage back to its raw inputs. Opinionated, zero-config by default, two verbs, no flags.

---

## Locked decisions (confirmed with user)

| Decision | Choice |
|---|---|
| Surface | **Two verbs: `track` + `trace`.** No `init`, `verify`, `list`, `guard`. No `--` separator. Zero options on either verb. |
| Install | **One command: `uv tool install ntrk`** (PyPI, `requires-python >=3.11`, no `--python` pin). |
| Input/output flags | **Baked-in convention** `-i -o --in --out --input --output`. Works with zero config. |
| Config | **Optional** `ntrk.toml` `[flags]` to *add* flags for codebases with other names. Absent ⇒ defaults. No other config exists. |
| Reproducibility guard | **Refuse to run on a dirty tree** (every run maps to a real commit). The only thing ntrk ever refuses. No override flag. |
| Overwrite protection | **Dropped.** ntrk never blocks a write; `trace` *tells* you if a file changed since it was produced. |
| Hash | **md5, always.** Not configurable. |
| Storage | Append-only `.ntrk/runs.jsonl` (source of truth) + invisible per-output sidecar `.NAME.ntrk` (so trace works on files copied anywhere). Auto-created on first `track`. |
| Recursive trace | `trace` walks the **full ancestry** (hash-linked over the log), **one greppable line per step**, reading left-to-right `input → script → output` (dependency order), with a quiet `[modified]` freshness marker. |
| Dependencies | **None** (runtime). Build backend: `uv_build`. |

## Defaulted assumptions (correct if wrong)

1. Experiment **outputs are gitignored** data artifacts → the tree stays clean for the next run.
2. The dirty-tree check **ignores ntrk's own files** (`.ntrk/` and `*.ntrk`) so the
   log/sidecars never trip the guard. ntrk otherwise **never touches git** (it only *reads*
   HEAD + status) — no auto-stage, no auto-commit. You commit `.ntrk/runs.jsonl` yourself.
3. Wrapped command **stdout/stderr pass through live**; ntrk never captures program output.
4. Only files behind the **input/output flags** (built-in + optional config) are hashed; no
   auto-discovery of other files the command touched.
5. `track` exits with the **wrapped command's own exit code**; only successful runs are recorded.

---

## Architecture

### Storage layout
```
<git-root>/
  ntrk.toml            # OPTIONAL — only if you need extra input/output flags
  .ntrk/
    runs.jsonl              # append-only lineage log, committed (source of truth)
    .gitattributes          # `runs.jsonl merge=union`
  results/
    out.csv                 # a tracked output
    .out.csv.ntrk           # invisible sidecar: self-contained copy of out.csv's record
```

### Run record (one JSONL line)
```json
{ "v":1, "id":"<uuid4hex>", "ts":"<UTC ISO8601>",
  "git": {"commit":"<40hex>","branch":"main"},
  "cwd":"<git-root-relative>",
  "script": {"path":"main.py","blob":"<git blob sha>","md5":"<md5>"},
  "command": ["python","main.py","-i","in.csv","-o","out.csv"],
  "inputs":  [{"path":"in.csv","md5":"<md5>","size":4096}],
  "outputs": [{"path":"out.csv","md5":"<md5>","size":128}] }
```
All paths git-root-relative, POSIX separators. No `dirty` field — a recorded run is always clean
by construction. No per-file algo (md5 always).

### Sidecars (`.NAME.ntrk`) — invisible by design
On a successful `track`, one hidden sidecar is written next to each output
(`results/out.csv` → `results/.out.csv.ntrk`): a self-contained copy of the run record + a
`sidecar_for` pointer. The user never thinks about these — they just make `trace` work on a file
copied outside the repo. The central log stays the source of truth (rebuildable, rename-robust by
md5). Known limit: a bare `cp`/`mv` won't carry the hidden sidecar, but the content-addressed log
still resolves the file in-repo.

### Config — optional, additive, tiny
Built-in defaults: inputs `-i --in --input`, outputs `-o --out --output`. If `ntrk.toml`
exists, its `[flags]` lists are **merged on top** (defaults always keep working):
```toml
# ntrk.toml — only needed if your scripts use non-standard flag names
[flags]
inputs  = ["--source", "--data"]
outputs = ["--dest", "--result"]
```
There is no `[git]` and no `[hash]` section. Strict-on-dirty and md5 are not negotiable.

### Exit codes (kept tiny)
```
0   track: clean run recorded   |  trace: lineage found
1   ntrk refused (dirty tree / not a git repo)  |  trace: no lineage for this file
N   track: the wrapped command's own non-zero exit code, propagated verbatim
```
`trace` returns 0 even when a file changed since production — it *found* the lineage; the change
is reported as a `⚠` line, not an error.

### stdlib surface (zero pip deps)
`argparse` (or hand dispatch) · `tomllib` (optional config) · `json` ·
`hashlib.file_digest(..., "md5", usedforsecurity=False)` · `subprocess.run([...])` (git via argv,
never `shell=True`) · `pathlib`/`os` · `fcntl.flock` · `uuid` · `datetime`.

---

## Implementation steps

Each step: **(a)** atomic spec + libs → **(b)** check stdlib/API docs if non-trivial →
**(c)** tests-first (`pytest-runner`) → **(d)** implement (`code-implementer`) →
**(e)** run tests (`code-executor`) → **(f)** debug (`bug-detective`) on failure →
**(g)** review (`code-reviewer`) → **(h)** commit.

### Step 1 — Scaffold (installable as a uv tool)
`src/ntrk/` package. Dispatch on `argv[1]`: `track` and `trace` only — **no own options**, so
everything after the verb is taken verbatim (this is what lets us drop `--`). Move/delete root
`main.py`. Add to `pyproject.toml`: `license = "MIT"`, `authors = [{name="tim-hudelmaier"}]`,
**`requires-python = ">=3.11"`** (drop the 3.14 pin), and:
```toml
[project.scripts]
nt   = "ntrk.cli:main"
ntrk = "ntrk.cli:main"

[build-system]
requires = ["uv_build>=0.11.24,<0.12"]
build-backend = "uv_build"
```
**Tests:** `uv run nt` with no args prints a one-line usage and exits non-zero; `nt track`/`nt
trace` reach their handlers; `uv build` yields a wheel exposing `nt`/`ntrk`.

### Step 2 — Repo discovery + optional config (`config.py`)
`find_root()` via `git rev-parse --show-toplevel`. `flag_map()` = built-in defaults, merged with
`ntrk.toml` `[flags]` via `tomllib` **if the file exists** (absent ⇒ defaults only).
**Tests:** defaults present with no config; config flags merged on top of defaults; malformed
toml → clear error; not-a-git-repo → clear error (exit 1).

### Step 3 — Git utilities (`gitutil.py`)
`is_clean(root)` → `git status --porcelain` excluding `.ntrk/` and `*.ntrk` → (clean, dirty
paths). `head_commit`, `branch`, `blob_hash(path)`. Not-a-repo / no-commits → typed failure.
**Tests:** temp-repo fixture: clean vs modified vs untracked; ntrk's own files ignored;
blob hash matches `git hash-object`.

### Step 4 — Hashing (`hashing.py`)
`digest(path)` → streaming `hashlib.file_digest(f, "md5", usedforsecurity=False)`, returns
`(hexdigest, size)`. Missing file → typed error.
**Tests:** known md5 vectors; empty file; size correctness.

### Step 5 — Command parsing (`parse.py`)
Input is `argv[2:]` (the wrapped command, verbatim — no `--`). Classify left-to-right against the
merged flag map. An input/output flag is **greedy**: it consumes **every following token up to the
next `-`-prefixed token**, and each consumed token is **also split on commas** — so
`-i a.csv b.csv,c.csv -o out1.csv,out2.csv` → `inputs=[a,b,c]`, `outputs=[out1,out2]`. Repeated
flags accumulate too (`-i a -i b`). The `--flag=value` form carries its own value(s) (comma-split)
and does not consume further tokens. `inputs`/`outputs` are always arrays in the record. Detect
`script` (known source ext, else first non-flag after a known interpreter, else argv[0]) —
script/interpreter tokens precede the io flags, so greedy consumption never reaches them. In-tree
paths recorded git-root-relative; a classified path outside the root is skipped with a one-line
stderr note (don't fail the run). Accepted caveat: a filename containing a comma, or starting with
`-`, can't be expressed.
**Tests:** `-i/-o` defaults; long forms; `=` form (comma-split, no over-consume); a config-added
flag; **space-list and comma-list each yield multiple inputs/outputs**; consumption **stops at the
next flag** (`-i a b --verbose -o x` → `inputs=[a,b]`, `outputs=[x]`); io flag with no value →
empty; interpreter-vs-script detection; out-of-tree path skipped, not fatal.

### Step 6 — Store (`store.py`)
**Log:** `append(root, record)` → `fcntl.flock(LOCK_EX)` around one `os.write` of
`json.dumps(rec, sort_keys=True)+"\n"`. **Resolve:** `resolve(target)` → sidecar next to target
first; else central content-match (md5 → newest record with that `outputs[].hash`); else
path-fallback (flag stale); else None. **Walk support:** `producer_of(md5)` → newest run whose
output hash matches (for recursion). **Sidecars:** `sidecar_path`, `write_sidecar`, `read_sidecar`.
**Tests:** append + flock-serialized concurrent appends (no partial lines); resolve by sidecar /
by content / after rename / path-fallback-stale / none; `producer_of` hit & miss; sidecar
round-trip; corrupt sidecar → None.

### Step 7 — `nt track <cmd...>` (cli)
`is_clean` guard (dirty / not-a-repo → exit 1, list offending paths on stderr) → parse (Step 5) →
hash inputs → run via `subprocess.run` (stdout/stderr pass-through) → on success: hash outputs,
build record, `append` to log + `write_sidecar` per output. Exit = wrapped returncode. ntrk
never stages or commits.
**Tests:** happy path records a correct line + a sidecar per output; dirty tree → exit 1, command
never runs; not-a-repo → exit 1; wrapped exit code propagated; first run auto-creates `.ntrk/`.

### Step 8 — `nt trace <file>` (cli) — recursive walk, one line per step
Resolve the target (Step 6). Walk the **full ancestry**: for each input, `producer_of(its md5)`
→ recurse to raw inputs (leaves); cycle/dedup guard keyed by (path, md5). Emit **one line per
production step**, in dependency order (raw inputs first; the queried file is the last line's
output), reading **left-to-right input → output**, so the output is `head`/`grep`/`awk`-friendly:
```
$ nt trace out_final.csv
in.csv -> step1.py @ 9c4b2a1 -> out.csv
out.csv -> step2.py @ 3a1f9c8 -> out_final.csv
```
One step = one run, formatted `INPUT[, INPUT…] -> SCRIPT @ <short-commit> -> OUTPUT` with
consistent ` -> ` / ` @ ` separators (awk-splittable). Multiple inputs are comma-joined; raw
inputs appear as inputs on the first line (they have no producing step). If a step produced
several outputs, its line shows the one on the path to the traced file (the run's full output set
is in the record). Freshness is
quiet-by-default: append ` [modified]` to a file whose on-disk md5 ≠ its recorded hash,
` [missing]` if gone — nothing when fresh. So `tail -n 1` = how the queried file was directly
made, `grep modified` = what drifted. The walk is content-addressed over the log → reconstructs the
chain even if intermediate files were renamed/deleted. A lone sidecar (file copied outside the
repo) yields the single immediate line. No lineage → exit 1, nothing on stdout.
**Tests:** single-step → one line; two-step chain → two lines, newest first; `head -n 1` = direct
producer; multiple inputs comma-joined on one line; shared-upstream DAG deduped; cycle terminates;
trace after rename (content match); chain survives a deleted intermediate; ` [modified]` marker
when bytes changed; sidecar-only → single line + note; exit 1 + empty stdout on miss.

### Step 9 — Distribution: one-command install
Lower `requires-python` to `>=3.11`; claim/publish `ntrk` on PyPI so `uv tool install
ntrk` works with no `--python` pin. Document fallbacks (`uvx --from ntrk nt …`,
`uv tool install --editable .` for dev, `uv tool update-shell` for PATH).
**Tests:** smoke — `uv tool install --editable .` in a temp tool-dir, then `nt`/`nt trace` resolve
from the installed entry point (not `uv run`).

### Step 10 — Claude Code skill + plugin marketplace
Repo doubles as a single-plugin marketplace (coexists with `pyproject.toml`). **Correct layout**
(skills at the plugin root, *not* inside `.claude-plugin/`):
```
<repo>/
  .claude-plugin/
    plugin.json            # name, description, version, author, repository, license=MIT
    marketplace.json       # owner + plugins:[{ name:"ntrk", source:"./", … }]
  skills/ntrk/SKILL.md  # frontmatter: name + description (triggers baked into description)
```
`SKILL.md` teaches the agent: prefix output-producing commands with `nt track` (records git
commit + md5 lineage; does **not** capture stdout), and `nt trace <file>` to see/verify provenance
(full ancestry + freshness). Author `tim-hudelmaier`, repo
`https://github.com/tim-hudelmaier/ntrk`. End-user install:
```
/plugin marketplace add tim-hudelmaier/ntrk
/plugin install ntrk@ntrk
```
**Checks:** manifests are valid JSON with required fields; `skills/ntrk/SKILL.md` has `name`
+ `description`; lint that no `skills/` dir is nested under `.claude-plugin/`.

### Step 11 — README + end-to-end + commit
Write `README.md` (canonical draft in **Appendix A**). One e2e test, a **two-step chain**: temp
repo → `track` (`in.csv → step1.py → out.csv`) → `track` (`out.csv → step2.py → out_final.csv`) →
`trace out_final.csv` prints two lines reading `in.csv → … → out_final.csv`, where `tail -n 1` is
the direct producer → copy the file + sidecar outside the repo and `trace` it (single line) →
dirty the tree and confirm `track` refuses (exit 1) → mutate `in.csv` and confirm `trace` shows
` [modified]` on its line. Final review + commit.

---

## Out of scope (documented non-goals)
`init` / `verify` / `list` / `guard` / `history` / `export` verbs; overwrite-blocking + `--force`;
`--dirty` / `--json` / `--depth` flags; the `[git]`/`[hash]` config sections; auto-discovery of
undeclared files; capturing program stdout/stderr; a global config layer; an on-disk index
(linear reverse-scan is sub-ms at per-repo scale). Machine-readable output = the JSONL log itself.

---

## Appendix A — `README.md` (draft)

````markdown
# ntrk

**Wrap a command. Later, ask how any file was made.**

ntrk records how each output was produced — the exact command, the git commit, and md5
hashes of every input and output — so you can point at a file weeks later and see its full
lineage, back to the raw inputs.

## Install

```bash
uv tool install ntrk
```

Commands: `nt` (alias `ntrk`). Run `uv tool update-shell` once if `nt` isn't on your PATH.

## Add to Claude

```
/plugin marketplace add tim-hudelmaier/ntrk
/plugin install ntrk@ntrk
```

## Use

Two commands.

```bash
nt track python main.py -i in.csv -o out.csv     # run it, record how
nt trace out.csv                                 # how was this made?
```

`track` refuses to run on a dirty repo, so every result maps to a real commit. `trace` prints one
line per step, reading left-to-right from the raw inputs down to the file you asked about — pipe
it through `head`/`grep`/`awk`. A `[modified]` marker appears if a file changed since it was made:

```console
$ nt trace out_final.csv
in.csv -> step1.py @ 9c4b2a1 -> out.csv
out.csv -> step2.py @ 3a1f9c8 -> out_final.csv
```

It uses the conventional `-i -o --in --out --input --output` flags out of the box. If your scripts
use other names, add a small `ntrk.toml`:

```toml
[flags]
inputs  = ["--source"]
outputs = ["--dest"]
```

## License

MIT
````
