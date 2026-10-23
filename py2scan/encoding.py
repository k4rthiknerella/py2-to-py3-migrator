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
    unicode %-format, and guaranteed to render identically on both
    hosts for the same real bytes: a filename with bytes that aren't
    valid in the filesystem encoding (hostile input, not hypothetical -
    the real repro is a file literally named with a raw non-UTF-8 byte)
    comes back from os.path.relpath() looking different on each host.
    Used as-is, it still reaches the real filesystem correctly either
    way (os.path.join + open() need the exact original bytes - never
    pass this function's result to either), but display is a different
    question from access.

    On Python 2, it is a `str` (bytes) no different in type from any
    other path; left alone, it crashes json.dumps() the moment it
    becomes a dict key or value (Python 2's json encoder decodes `str`
    as UTF-8 and raises UnicodeDecodeError, taking the whole scan down
    with it, not just that one file).

    On Python 3, os.walk already decoded it to `str` - but via
    surrogateescape at the OS layer, which round-trips the exact
    original bytes through *lone surrogate code points*, not through
    the same U+FFFD replacement Python 2's "replace" error handler
    produces. json.dumps() does not raise on a lone surrogate (it just
    writes it out as a \\udcXX escape), so left alone, Python 3's JSON
    output byte-differs from Python 2's for the identical real file -
    R2's guarantee, broken by two correct-in-isolation defaults that
    disagree with each other. Undo the surrogateescape round-trip back
    to the original bytes, then apply the exact same utf-8/"replace"
    step the Python 2 side uses, so both hosts converge on the same
    U+FFFD text for the same bytes."""
    if sys.version_info[0] < 3:
        if isinstance(rel, str):
            return rel.decode("utf-8", "replace")
        return rel
    return rel.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
