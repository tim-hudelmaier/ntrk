"""md5 file fingerprints. md5 is a content fingerprint, not tamper-evidence."""

import hashlib
from pathlib import Path


def md5_file(path):
    """Return ``(hexdigest, size_bytes)`` for ``path``, streamed.

    Raises FileNotFoundError if the path does not exist.
    """
    p = Path(path)
    with open(p, "rb") as f:
        digest = hashlib.file_digest(f, lambda: hashlib.md5(usedforsecurity=False))
    return digest.hexdigest(), p.stat().st_size
