# -*- coding: utf-8 -*-
"""PEP 263 source-encoding detection, for displaying source lines correctly."""
import re
import sys

_COOKIE_RE = re.compile(r"coding[:=]\s*([-\w.]+)")
_BOM = b"\xef\xbb\xbf"


def detect_source_encoding(raw_bytes):
    # PEP 263: a leading UTF-8 BOM means utf-8 regardless of any cookie.
    # "utf-8-sig" also strips the BOM bytes themselves on decode.
    if raw_bytes.startswith(_BOM):
        return "utf-8-sig"
    for line in raw_bytes.split(b"\n", 2)[:2]:
        match = _COOKIE_RE.search(line.decode("ascii", "replace"))
        if match:
            return match.group(1)
    return "ascii"


def decode_source_lines(raw_bytes):
    encoding = detect_source_encoding(raw_bytes)
    text = raw_bytes.decode(encoding, "replace")
    return text.splitlines()


def display_path(rel):
    """A relative path, guaranteed safe to hand to json.dumps or a
    unicode %-format: a filename with bytes that aren't valid in the
    filesystem encoding (hostile input, not hypothetical - the real
    repro is a file literally named with a raw non-UTF-8 byte) comes
    back from os.path.relpath() on Python 2 as a `str` (bytes) no
    different in type from any other path. Used as-is, it still reaches
    the real filesystem correctly (os.path.join + open() need the exact
    original bytes - never pass this function's result to either), but
    it crashes json.dumps() the moment it becomes a dict key or value:
    Python 2's json encoder decodes `str` as UTF-8 and raises
    UnicodeDecodeError, taking the whole scan down with it, not just
    that one file. Call this only at an output boundary (JSON, text),
    never for anything used to open a file afterward. Python 3's
    os.walk already returns `str` for every path (surrogateescape at
    the OS layer, always valid unicode), so there is nothing to do
    there. 'surrogateescape' isn't even a decode error handler Python
    2.7 recognizes, so 'replace' is this side's equivalent, not a
    weaker stand-in for it."""
    if sys.version_info[0] < 3 and isinstance(rel, str):
        return rel.decode("utf-8", "replace")
    return rel
