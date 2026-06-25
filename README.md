# ntrk

**Wrap a command. Later, ask how any file was made.**

ntrk records how each output was produced — the exact command, the git commit, and md5
hashes of every input and output — so you can point at a file weeks later and see its full
lineage, back to the raw inputs. Pure Python standard library, no dependencies, two commands.

## Install

```bash
uv tool install ntrk
```

Commands: `nt` (alias `ntrk`). Run `uv tool update-shell` once if `nt` isn't on your `PATH`.

## Add to Claude

This repo is also a Claude Code plugin marketplace shipping the `ntrk` skill, so your coding
agent knows when to record runs and trace outputs:

```
/plugin marketplace add tim-hudelmaier/ntrk
/plugin install ntrk@ntrk
```

## Use

Two commands, no flags.

```bash
nt track python main.py -i in.csv -o out.csv     # run it, record how
nt trace out.csv                                 # how was this made?
```

`nt track` refuses to run on a dirty repo, so every result maps to a real commit. `nt trace`
prints one line per step — raw inputs first, the file you asked about last — so you can pipe it
through `head` / `grep` / `awk`. A `[modified]` marker appears if a file changed since it was made:

```console
$ nt trace out_final.csv
in.csv -> step1.py @ 9c4b2a1 -> out.csv
out.csv -> step2.py @ 3a1f9c8 -> out_final.csv
```

Inputs and outputs are detected from the conventional flags
`-i -o --in --out --input --output` (repeated, space-, or comma-separated lists work). If your
scripts use other flag names, add a small `ntrk.toml`:

```toml
[flags]
inputs  = ["--source"]
outputs = ["--dest"]
```

## How it works

Each run is appended as one JSON line to `.ntrk/runs.jsonl` (commit it — it's your lineage
history), and each output also gets an invisible self-contained sidecar (`.NAME.ntrk`) so a file
stays traceable even when copied outside the repo. `trace` walks the chain by content hash, so it
still works after intermediate files are renamed or deleted.

## Development

```bash
uv sync          # set up the environment
uv run pytest    # run the tests
```

## Releasing (maintainer)

CI (`.github/workflows/ci.yml`) runs the test matrix on every push/PR and publishes to PyPI on
push to `main` via **trusted publishing** (OIDC, no API token), using `skip-existing` so an
unchanged version is a no-op. One-time PyPI setup (a *pending publisher*, since the project is not
yet on PyPI):

1. PyPI → *Your account* → *Publishing* → add a pending GitHub publisher:
   - Project: `ntrk` · Owner: `tim-hudelmaier` · Repo: `ntrk`
   - Workflow: `ci.yml` · Environment: `pypi`
2. In GitHub → *Settings → Environments*, create an environment named `pypi`.
3. Bump the version in `pyproject.toml` and push to `main` — the first successful publish creates
   the project and converts the pending publisher.

## License

MIT
