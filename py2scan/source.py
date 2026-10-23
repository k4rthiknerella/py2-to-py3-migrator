# -*- coding: utf-8 -*-
"""Python 2 source bytes as the 2.7 compiler sees them: encoding and lines."""
import codecs
import re

# The 2.7 compiler ends a line at \r\n, \r or \n, and only there.
_NEWLINE = re.compile(br"\r\n|\r|\n")
_TEXT_NEWLINE = re.compile(u"\r\n|\r|\n")
# PEP 263, as Parser/tokenizer.c get_coding_spec reads it.
_COOKIE = re.compile(br"^[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)")
_BLANK_OR_COMMENT = re.compile(br"^[ \t\f]*(?:#|$)")
text_type = type(u"")


def _normal_name(name):
    """Parser/tokenizer.c get_normal_name: utf-8-* and latin-1 spellings."""
    low = name[:12].lower().replace("_", "-")
    if low == "utf-8" or low.startswith("utf-8-"):
        return "utf-8"
    if low in ("latin-1", "iso-8859-1", "iso-latin-1") or \
            low.startswith(("latin-1-", "iso-8859-1-", "iso-latin-1-")):
        return "iso-8859-1"
    return name


def coding_cookie(source):
    """(encoding, line number) of the PEP 263 declaration, or (None, None).

    The declaration may be on line 1, or on line 2 when line 1 holds only a
    comment or whitespace.
    """
    if source.startswith(codecs.BOM_UTF8):
        source = source[len(codecs.BOM_UTF8):]
    for number, line in enumerate(_NEWLINE.split(source, 2)[:2], 1):
        match = _COOKIE.match(line)
        if match:
            return _normal_name(match.group(1).decode("ascii")), number
        if not _BLANK_OR_COMMENT.match(line):
            break
    return None, None


def decode(source):
    """The source as unicode, never failing: undecodable bytes become U+FFFD."""
    encoding = coding_cookie(source)[0]
    if source.startswith(codecs.BOM_UTF8):
        source, encoding = source[len(codecs.BOM_UTF8):], "utf-8"
    try:
        text = source.decode(encoding or "utf-8", "replace")
    except Exception:  # unknown codec, or a bytes-to-bytes one such as zlib
        text = None
    if not isinstance(text, text_type):
        text = source.decode("utf-8", "replace")
    return text


def source_lines(source):
    """Decoded lines, numbered as the compiler numbers them (index 0 is line 1)."""
    lines = _TEXT_NEWLINE.split(decode(source))
    if lines and lines[-1] == u"":
        lines.pop()
    return lines


def line_of_offset(source, offset):
    """The line number holding byte offset in source."""
    return len(_NEWLINE.findall(source, 0, offset)) + 1
