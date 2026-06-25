---
name: ntrk
description: Record and trace experiment lineage with the `nt` CLI. Use when running scripts or commands that produce output files (data processing, ML training, analysis) and reproducibility matters, or when asked how an existing output file was generated / whether it is still up to date. Wrap producing commands in `nt track`; inspect provenance with `nt trace`.
---

# ntrk

`nt` records how output files are produced — the exact command, the git commit, and md5 hashes
of every input and output — and traces any file back to its raw inputs.

## When to use
- A command reads input files and writes output files and the user wants it reproducible or
  auditable later → wrap it in `nt track`.
- The user asks "how was this file made?", "what produced X?", or "is this output stale?" →
  use `nt trace`.

## Install (once)
```bash
uv tool install ntrk
```

## Two commands

**Record a run** — prefix the command (no `--` separator needed):
```bash
nt track python main.py -i in.csv -o out.csv
```
`nt track` refuses to run on a dirty git tree (so every run maps to a real commit), runs the
command with live stdout/stderr (it does **not** capture program output), then records the
lineage. Inputs and outputs are detected from the conventional flags
`-i -o --in --out --input --output` (repeated, space-, or comma-separated lists are fine). If a
project's scripts use other flag names, add a `ntrk.toml`:
```toml
[flags]
inputs  = ["--source"]
outputs = ["--dest"]
```

**Trace a file** — one greppable line per step, raw inputs first:
```bash
nt trace out.csv
```
A `[modified]` marker means a file changed since it was produced.

## Guidance
- Commit code before tracking, or `nt track` will refuse (clean tree = reproducible run).
- Don't overwrite a tracked output by hand — re-run it through `nt track` so lineage stays true.
- Use `nt trace` to confirm provenance (and freshness) before reusing an output downstream.
