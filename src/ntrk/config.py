"""Built-in input/output flag convention, plus optional per-repo extensions.

ntrk knows the conventional flags out of the box. A repo only needs a
``ntrk.toml`` if its scripts use other flag names:

    [flags]
    inputs  = ["--source"]
    outputs = ["--dest"]

These are *added* to the built-ins (the defaults always keep working). There is
no other configuration: strict-on-dirty and md5 are not negotiable.
"""

import tomllib
from pathlib import Path

DEFAULT_INPUT_FLAGS = ("-i", "--in", "--input")
DEFAULT_OUTPUT_FLAGS = ("-o", "--out", "--output")


class Config:
    def __init__(self, input_flags, output_flags):
        self.input_flags = set(input_flags)
        self.output_flags = set(output_flags)


def load(root):
    """Return a Config: built-in flags merged with optional ``ntrk.toml``."""
    inputs = set(DEFAULT_INPUT_FLAGS)
    outputs = set(DEFAULT_OUTPUT_FLAGS)
    cfg = Path(root) / "ntrk.toml"
    if cfg.exists():
        with open(cfg, "rb") as f:
            data = tomllib.load(f)
        flags = data.get("flags", {})
        inputs |= set(flags.get("inputs", []))
        outputs |= set(flags.get("outputs", []))
    return Config(inputs, outputs)
