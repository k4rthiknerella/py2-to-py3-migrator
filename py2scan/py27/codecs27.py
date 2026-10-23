# -*- coding: utf-8 -*-
"""Codecs as Python 2.7 applies them to source code and string literals.

The UTF-8 decoder is a port of 2.7's (Objects/unicodeobject.c): it accepts
encoded surrogates, which Python 3 rejects, and words its errors as 2.7 does.
registry27 applies a declared codec; this module has what the compiler does
around it: the escape decoders, \\N{...} names and the errors' wording.

Copyright (c) 2001-2020 Python Software Foundation; All Rights Reserved.
Used under the PSF License Agreement, version 2, in PSF-LICENSE.txt.
"""
import bisect
import re
import sys
import unicodedata

from py2scan.py27 import unicode52

text_type = type(u"")
unichr_ = chr if sys.version_info[0] >= 3 else unichr  # noqa: F821 (Python 2 only)
_SURROGATEPASS = "surrogatepass" if sys.version_info[0] >= 3 else "strict"
_SURROGATE_PAIR = re.compile(u"[\ud800-\udbff][\udc00-\udfff]")
SIMPLE_ESCAPES = {u"\\": u"\\", u"'": u"'", u'"': u'"', u"b": u"\b", u"f": u"\x0c", u"t": u"\t",
                  u"n": u"\n", u"r": u"\r", u"v": u"\x0b", u"a": u"\x07"}
HEX_DIGITS = frozenset(u"0123456789abcdefABCDEF")
OCTAL_DIGITS = frozenset(u"01234567")


class CodecError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)
        self.msg = msg


def decode_error(codec, data, start, end, reason):
    """str() of 2.7's UnicodeDecodeError, for data as a latin-1 view of the bytes."""
    if start < len(data) and end == start + 1:
        return "'%s' codec can't decode byte 0x%02x in position %d: %s" % (
            codec, ord(data[start]), start, reason)
    return "'%s' codec can't decode bytes in position %d-%d: %s" % (codec, start, end - 1, reason)


# utf8_code_length from 2.7's Objects/unicodeobject.c
def _sequence_length(byte):
    if byte < 0x80:
        return 1
    if byte < 0xC2:
        return 0
    if byte < 0xE0:
        return 2
    if byte < 0xF0:
        return 3
    return 4 if byte < 0xF5 else 0


def _continuation(data, pos):
    return pos < len(data) and (ord(data[pos]) & 0xC0) == 0x80


def _utf8_error(data, start, n):
    """(end, reason) of the invalid sequence starting at start, as 2.7 reports it."""
    first = ord(data[start])
    if n == 0:
        return start + 1, "invalid start byte"
    if start + n > len(data):
        end = start + 1
        while end < len(data) and _continuation(data, end):
            end += 1
        return end, "unexpected end of data"
    second = ord(data[start + 1])
    bad = not _continuation(data, start + 1) or any(
        not _continuation(data, start + k) for k in range(2, n))
    bad = bad or (n == 3 and first == 0xE0 and second < 0xA0)
    bad = bad or (n == 4 and ((first == 0xF0 and second < 0x90) or (first == 0xF4 and second > 0x8F)))
    if not bad:
        return None, None
    end = start + 1
    for k in range(1, n - 1):
        if not _continuation(data, start + k):
            break
        end += 1
    return end, "invalid continuation byte"


def utf8_decode(data):
    """2.7's strict UTF-8 decoder over a latin-1 view of bytes, returning text."""
    out = []
    pos = 0
    size = len(data)
    while pos < size:
        byte = ord(data[pos])
        if byte < 0x80:
            out.append(data[pos])
            pos += 1
            continue
        n = _sequence_length(byte)
        end, reason = _utf8_error(data, pos, n)
        if reason:
            raise CodecError(decode_error("utf8", data, pos, end, reason))
        value = byte & (0x7F >> n)
        for k in range(1, n):
            value = (value << 6) | (ord(data[pos + k]) & 0x3F)
        out.append(unichr_(value))
        pos += n
    return u"".join(out)


def to_utf8(text):
    """Text to UTF-8 bytes as 2.7 encodes them: a high surrogate followed by a
    low one as the code point they pair to, and any other surrogate as itself."""
    paired = _SURROGATE_PAIR.sub(
        lambda m: unichr_(0x10000 + ((ord(m.group()[0]) - 0xD800) << 10) + ord(m.group()[1]) - 0xDC00), text)
    return paired.encode("utf-8", _SURROGATEPASS)


def encode_error(codec, text, start, end, reason):
    """str() of 2.7's UnicodeEncodeError."""
    if start < len(text) and end == start + 1:
        code = ord(text[start])
        char = "x%02x" % code if code <= 0xFF else "u%04x" % code if code <= 0xFFFF else "U%08x" % code
        return "'%s' codec can't encode character u'\\%s' in position %d: %s" % (codec, char, start, reason)
    return "'%s' codec can't encode characters in position %d-%d: %s" % (codec, start, end - 1, reason)


def ascii_text(value):
    """A concatenated literal as PyUnicode_Concat converts it: text as it is,
    bytes decoded with 2.7's default codec, ASCII."""
    if isinstance(value, text_type):
        return value
    view = value.decode("latin-1")
    for pos, char in enumerate(view):
        if char >= u"\x80":
            raise CodecError(decode_error("ascii", view, pos, pos + 1, "ordinal not in range(128)"))
    return view


# Unicode 5.2 as 2.7.18's unicodedata names it (Modules/unicodedata.c).
_HANGUL = (
    (u"G", u"GG", u"N", u"D", u"DD", u"R", u"M", u"B", u"BB", u"S", u"SS", u"", u"J", u"JJ", u"C", u"K",
     u"T", u"P", u"H"),
    (u"A", u"AE", u"YA", u"YAE", u"EO", u"E", u"YEO", u"YE", u"O", u"WA", u"WAE", u"OE", u"YO", u"U",
     u"WEO", u"WE", u"WI", u"YU", u"EU", u"YI", u"I"),
    (u"", u"G", u"GG", u"GS", u"N", u"NJ", u"NH", u"D", u"L", u"LG", u"LM", u"LB", u"LS", u"LT", u"LP",
     u"LH", u"M", u"B", u"BS", u"S", u"SS", u"NG", u"J", u"C", u"K", u"T", u"P", u"H"),
)
_HANGUL_FIRST, _HANGUL_LAST = 0xAC00, 0xD7A3
_UNIFIED_IDEOGRAPHS = ((0x3400, 0x4DB5), (0x4E00, 0x9FCB), (0x20000, 0x2A6D6), (0x2A700, 0x2B734))
_NAMED_STARTS = [first for first, _ in unicode52.NAMED]
_UPPER_HEX = frozenset(u"0123456789ABCDEF")


def _unified_ideograph(code):
    return any(first <= code <= last for first, last in _UNIFIED_IDEOGRAPHS)


def _named_in_52(code):
    i = bisect.bisect_right(_NAMED_STARTS, code) - 1
    return i >= 0 and code <= unicode52.NAMED[i][1]


def _hangul_syllable(name):
    """The Hangul branch of _getcode: find_syllable takes the longest (first
    on ties) entry of each column in turn, and the parts must use the whole name."""
    pos, parts = 16, []
    for column in _HANGUL:
        size, index = -1, -1
        for i, syllable in enumerate(column):
            if len(syllable) > size and name.startswith(syllable, pos):
                size, index = len(syllable), i
        parts.append(index)
        pos += max(size, 0)
    if -1 in parts or pos != len(name):
        return None
    return _HANGUL_FIRST + (parts[0] * 21 + parts[1]) * 28 + parts[2]


def lookup_name(name):
    """The code point \\N{name} denotes in 2.7, or None: _getcode with Unicode
    5.2 and no aliases. The algorithmic prefixes are case-sensitive; other names
    are matched case-insensitively (ASCII only) through the running
    interpreter's database, kept to names 5.2 has. Names never change once
    assigned, so a 5.2 name is the same in any later version."""
    if name.startswith(u"HANGUL SYLLABLE "):
        return _hangul_syllable(name)
    if name.startswith(u"CJK UNIFIED IDEOGRAPH-"):
        digits = name[22:]
        if len(digits) not in (4, 5) or not set(digits) <= _UPPER_HEX:
            return None
        code = int(digits, 16)
        return code if _unified_ideograph(code) else None
    if any(char >= u"\x80" for char in name):
        return None
    upper = u"".join(unichr_(ord(char) - 32) if u"a" <= char <= u"z" else char for char in name)
    try:
        found = unicodedata.lookup(upper)
    except KeyError:
        return None
    if len(found) != 1:  # a named sequence
        return None
    code = ord(found)
    if not _named_in_52(code) or _unified_ideograph(code) or _HANGUL_FIRST <= code <= _HANGUL_LAST:
        return None
    return code if unicodedata.name(found) == upper else None  # not an alias


def _hex_escape(s, start, i, digits, message):
    """(value, end) of the hex digits after \\x, \\u or \\U, or the 2.7 error."""
    end = i
    while end < len(s) and end - i < digits and s[end] in HEX_DIGITS:
        end += 1
    if end - i < digits:
        raise CodecError(decode_error("unicodeescape", s, start, end, message))
    return int(s[i:end], 16), end


def _named_escape(s, start, i):
    """(code point, end) of \\N{name} at s[i:], or the 2.7 error."""
    if i < len(s) and s[i] == u"{":
        close = s.find(u"}", i)
        if close > i + 1:
            code = lookup_name(s[i + 1:close])
            if code is None:
                raise CodecError(decode_error("unicodeescape", s, start, close + 1, "unknown Unicode character name"))
            return code, close + 1
        i = close if close != -1 else len(s)
    raise CodecError(decode_error("unicodeescape", s, start, i, "malformed \\N character escape"))


_HEX_ESCAPES = {u"x": (2, "truncated \\xXX escape"), u"u": (4, "truncated \\uXXXX escape"),
                u"U": (8, "truncated \\UXXXXXXXX escape")}


def _unicode_escape(s, start, i, char, out):
    """The escape at s[start:] whose character, char, comes just before s[i]: the index after it."""
    if char in SIMPLE_ESCAPES:
        out.append(SIMPLE_ESCAPES[char])
    elif char in OCTAL_DIGITS:
        value = ord(char) - 48
        for _ in range(2):
            if i < len(s) and s[i] in OCTAL_DIGITS:
                value, i = (value << 3) + ord(s[i]) - 48, i + 1
        out.append(unichr_(value))
    elif char in _HEX_ESCAPES:
        value, i = _hex_escape(s, start, i, *_HEX_ESCAPES[char])
        if value > 0x10FFFF:
            raise CodecError(decode_error("unicodeescape", s, start, i, "illegal Unicode character"))
        out.append(unichr_(value))
    elif char == u"N":
        value, i = _named_escape(s, start, i)
        out.append(unichr_(value))
    elif char != u"\n":
        out.append(u"\\" + char)
    return i


def decode_unicode_escape(s):
    """PyUnicode_DecodeUnicodeEscape with strict errors, for a latin-1 view of bytes."""
    out = []
    i, size = 0, len(s)
    while i < size:
        char = s[i]
        if char != u"\\":
            out.append(char)
            i += 1
            continue
        start = i
        if i + 1 >= size:
            raise CodecError(decode_error("unicodeescape", s, start, size, "\\ at end of string"))
        i = _unicode_escape(s, start, i + 2, s[i + 1], out)
    return u"".join(out)


def decode_raw_unicode_escape(s):
    """PyUnicode_DecodeRawUnicodeEscape with strict errors, for a latin-1 view of
    bytes. Where 2.7 reads past the end for missing digits (the closing quote,
    or uninitialised memory when the literal was re-encoded), this stops at the end."""
    out = []
    i, size = 0, len(s)
    while i < size:
        if s[i] != u"\\":
            out.append(s[i])
            i += 1
            continue
        start = i
        while i < size and s[i] == u"\\":
            out.append(u"\\")
            i += 1
        if (i - start) % 2 == 0 or i >= size or s[i] not in u"uU":
            continue
        out.pop()
        count = 4 if s[i] == u"u" else 8
        i += 1
        for end in range(i, i + count):
            if end >= size or s[end] not in HEX_DIGITS:
                raise CodecError(decode_error("rawunicodeescape", s, start, end, "truncated \\uXXXX"))
        value, i = int(s[i:i + count], 16), i + count
        if value > 0x10FFFF:
            raise CodecError(decode_error("rawunicodeescape", s, start, i, "\\Uxxxxxxxx out of range"))
        out.append(unichr_(value))
    return u"".join(out)
