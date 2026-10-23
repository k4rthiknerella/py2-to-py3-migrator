# -*- coding: utf-8 -*-
"""Decodes a source file's lines using its PEP 263 coding cookie, for display."""
import io

from lib2to3.pgen2.tokenize import detect_encoding


def read_lines(path):
    with open(path, "rb") as f:
        source = f.read()
    encoding, _ = detect_encoding(io.BytesIO(source).readline)
    return source.decode(encoding, "replace").splitlines()
