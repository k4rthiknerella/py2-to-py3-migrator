# -*- coding: utf-8 -*-
"""Decodes a source file's lines using its PEP 263 coding cookie, for
display."""
import io

try:
    # Python 2.7's own tokenize module lacks detect_encoding; lib2to3 backports
    # it. lib2to3 was removed from the stdlib in Python 3.13 (gh-104780), where
    # tokenize has carried the same function natively since Python 3.2.
    from lib2to3.pgen2.tokenize import detect_encoding
except ImportError:
    from tokenize import detect_encoding


def read_lines(path):
    with open(path, "rb") as f:
        source = f.read()
    encoding, _ = detect_encoding(io.BytesIO(source).readline)
    return source.decode(encoding, "replace").splitlines()
