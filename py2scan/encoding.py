# -*- coding: utf-8 -*-
"""PEP 263 source-encoding detection, for displaying source lines correctly."""
import re

_COOKIE_RE = re.compile(r"coding[:=]\s*([-\w.]+)")


def detect_source_encoding(raw_bytes):
    for line in raw_bytes.split(b"\n", 2)[:2]:
        match = _COOKIE_RE.search(line.decode("ascii", "replace"))
        if match:
            return match.group(1)
    return "ascii"


def decode_source_lines(raw_bytes):
    encoding = detect_source_encoding(raw_bytes)
    text = raw_bytes.decode(encoding, "replace")
    return text.splitlines()
