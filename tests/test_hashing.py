import hashlib

import pytest

from ntrk import hashing


def test_md5_matches_hashlib(tmp_path):
    p = tmp_path / "f.bin"
    data = b"hello ntrk\n" * 100
    p.write_bytes(data)
    digest, size = hashing.md5_file(p)
    assert digest == hashlib.md5(data).hexdigest()
    assert size == len(data)


def test_md5_empty_file(tmp_path):
    p = tmp_path / "empty"
    p.write_bytes(b"")
    digest, size = hashing.md5_file(p)
    assert digest == hashlib.md5(b"").hexdigest()
    assert size == 0


def test_md5_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        hashing.md5_file(tmp_path / "nope")
