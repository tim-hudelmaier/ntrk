"""Classify a wrapped command's tokens into inputs, outputs, and the script.

An input/output flag is *greedy*: it consumes every following token up to the
next ``-``-prefixed token, and each consumed token is also split on commas. So
``-i a.csv b.csv,c.csv -o out1,out2`` -> inputs ``[a,b,c]``, outputs ``[out1,out2]``.

Accepted caveat: a filename containing a comma, or starting with ``-``, can't be
expressed.
"""

INTERPRETERS = {
    "python", "python3", "python2", "Rscript", "bash", "sh",
    "node", "ruby", "perl", "julia",
}
SOURCE_EXTS = (".py", ".R", ".r", ".sh", ".jl", ".rb", ".js", ".pl")


class ParsedCommand:
    def __init__(self, command, script, inputs, outputs):
        self.command = command  # list[str], verbatim
        self.script = script    # str or None
        self.inputs = inputs    # list[str]
        self.outputs = outputs  # list[str]


def _role(flag, config):
    if flag in config.input_flags:
        return "in"
    if flag in config.output_flags:
        return "out"
    return None


def _split(token):
    return [part for part in token.split(",") if part]


def parse(argv, config):
    inputs, outputs = [], []
    i, n = 0, len(argv)
    while i < n:
        flag, eq, inline = argv[i].partition("=")
        role = _role(flag, config)
        if role is None:
            i += 1
            continue
        bucket = inputs if role == "in" else outputs
        if eq:  # --flag=value : self-contained, comma-split, no greedy consume
            bucket.extend(_split(inline))
            i += 1
            continue
        # bare flag: greedily consume until the next '-'-prefixed token
        i += 1
        while i < n and not argv[i].startswith("-"):
            bucket.extend(_split(argv[i]))
            i += 1
    classified = set(inputs) | set(outputs)
    return ParsedCommand(list(argv), _detect_script(argv, classified), inputs, outputs)


def _is_interpreter(tok):
    base = tok.rsplit("/", 1)[-1]
    return base in INTERPRETERS or base.startswith("python") or base.startswith("Rscript")


def _detect_script(argv, classified=()):
    classified = set(classified)
    # 1. first non-input/output token ending in a known source extension
    for tok in argv:
        if tok not in classified and tok.endswith(SOURCE_EXTS):
            return tok
    # 2. first non-flag, non-input/output token after a known interpreter
    for idx, tok in enumerate(argv):
        if _is_interpreter(tok):
            for nxt in argv[idx + 1:]:
                if not nxt.startswith("-") and nxt not in classified:
                    return nxt
            break
    # 3. fall back to the first non-flag, non-input/output token
    for tok in argv:
        if not tok.startswith("-") and tok not in classified:
            return tok
    return argv[0] if argv else None
