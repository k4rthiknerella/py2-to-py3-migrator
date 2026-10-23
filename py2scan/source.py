# -*- coding: utf-8 -*-
"""Python 2 source bytes as the 2.7 compiler sees them: encoding and lines."""
import codecs
import re

from py2scan.py27 import registry27
from py2scan.py27.codecs27 import CodecError

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


# Well-formed UTF-8 (Unicode table 3-7), and the maximal subparts of ill-formed
# sequences: the longest prefix of a well-formed sequence, else one byte.
_UTF8 = re.compile(br"(?:[\x00-\x7f]|[\xc2-\xdf][\x80-\xbf]|\xe0[\xa0-\xbf][\x80-\xbf]|"
                   br"[\xe1-\xec\xee\xef][\x80-\xbf]{2}|\xed[\x80-\x9f][\x80-\xbf]|"
                   br"\xf0[\x90-\xbf][\x80-\xbf]{2}|[\xf1-\xf3][\x80-\xbf]{3}|\xf4[\x80-\x8f][\x80-\xbf]{2})+")
_SUBPART = re.compile(br"\xe0[\xa0-\xbf]|[\xe1-\xec\xee\xef][\x80-\xbf]|\xed[\x80-\x9f]|"
                      br"\xf0[\x90-\xbf][\x80-\xbf]?|[\xf1-\xf3][\x80-\xbf]{1,2}|\xf4[\x80-\x8f][\x80-\xbf]?|.",
                      re.S)
_SURROGATE = re.compile(u"[\ud800-\udfff]")


def utf8_text(data):
    """data as UTF-8, each maximal ill-formed subpart replaced by U+FFFD: what
    Python 3's "replace" gives, and the same on 2.7, whose UTF-8 codec accepts
    surrogates and so cannot be used."""
    parts, i = [], 0
    while i < len(data):
        match = _UTF8.match(data, i) or _SUBPART.match(data, i)
        parts.append(match.group().decode("utf-8") if match.re is _UTF8 else u"\ufffd")
        i = match.end()
    return u"".join(parts)


def decode(source):
    """The source as unicode, never failing: as 2.7 decodes it when it can,
    else as UTF-8 with U+FFFD for what does not decode, and for surrogates."""
    encoding = coding_cookie(source)[0]
    if source.startswith(codecs.BOM_UTF8):
        source, encoding = source[len(codecs.BOM_UTF8):], "utf-8"
    if encoding:
        try:
            return _SURROGATE.sub(u"\ufffd", registry27.decode(source, encoding))
        except CodecError:  # an unknown codec, a failed decoding, or one that gives bytes
            pass
    return utf8_text(source)


def source_lines(source):
    """Decoded lines, numbered as the compiler numbers them (index 0 is line 1)."""
    lines = _TEXT_NEWLINE.split(decode(source))
    if lines and lines[-1] == u"":
        lines.pop()
    return lines


def line_of_offset(source, offset):
    """The line number holding byte offset in source."""
    return len(_NEWLINE.findall(source, 0, offset)) + 1
