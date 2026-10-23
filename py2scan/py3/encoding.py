# -*- coding: utf-8 -*-
"""How each judged Python 3 version reads a file's bytes.

With no coding declaration, a UTF-8 one, or a BOM, Python 3 reads UTF-8:
3.6 to 3.13 decode each string literal strictly, and 3.14 and later the
whole file. With Latin-1 every byte is a character. Any other declared codec
decodes the whole file, whose text must then encode back to UTF-8 (no lone
surrogates). The 2.7 front end recoded the file with 2.7's codec; that text
is Python 3's when the version accepts the codec name and decodes as 2.7
does, which codecs_data records per version. A codec whose decoder keeps
state between characters is not fingerprinted, and py2scan blocks every
version for it without claiming that compile() fails.
"""
import re

from py2scan.py27 import registry27
from py2scan.py3 import codecs_data
from py2scan.py3.common import problem, string_leaves
from py2scan.versions import ALL, VERSIONS, label, since

_VALID_UTF8 = re.compile(
    u"(?:[\x00-\x7f]|[\xc2-\xdf][\x80-\xbf]|\xe0[\xa0-\xbf][\x80-\xbf]|[\xe1-\xec\xee\xef][\x80-\xbf]{2}"
    u"|\xed[\x80-\x9f][\x80-\xbf]|\xf0[\x90-\xbf][\x80-\xbf]{2}|[\xf1-\xf3][\x80-\xbf]{3}"
    u"|\xf4[\x80-\x8f][\x80-\xbf]{2})*")
_SURROGATE = re.compile(u"\xed[\xa0-\xbf][\x80-\xbf]")
_NON_ASCII = re.compile(u"[\x80-\xff]")
_NAME_SEPARATORS = re.compile(r"[^0-9a-z.]+")
_SELF_DECODED = (None, "utf-8", "iso-8859-1")
_UTF8_MODULES = ("utf_8", "utf_8_sig")


def invalid_utf8(text):
    """The offset of the first byte of a latin-1 view of bytes that does not
    start valid UTF-8 (no surrogates, nothing beyond U+10FFFF), or None."""
    end = _VALID_UTF8.match(text).end()
    return end if end < len(text) else None


def _line(text, offset):
    return text.count(u"\n", 0, offset) + 1


def check_utf8(m):
    if m.result.encoding not in (None, "utf-8"):
        return
    for leaf in string_leaves(m):
        offset = invalid_utf8(leaf.value)
        if offset is not None:
            yield problem(leaf.start_line, leaf.start_col,
                          "string literal that is not valid UTF-8; Python 3 reads this file as UTF-8", ALL)
            return
    offset = invalid_utf8(m.result.text)
    if offset is not None:
        yield problem(_line(m.result.text, offset), 0,
                      "bytes that are not valid UTF-8; Python 3.14 and later read the whole file as UTF-8",
                      since((3, 14)))


def _versions(labels):
    return frozenset(v for v in VERSIONS if label(v) in labels)


def _normalized(name):
    lower = u"".join(c.lower() if u"A" <= c <= u"Z" else c for c in name)
    return u"_".join(part for part in _NAME_SEPARATORS.split(lower) if part)


def check_codec(m):
    name = m.result.encoding
    if name in _SELF_DECODED:
        return
    line = _cookie_line(m)
    key = _normalized(name)
    rejected = _versions(codecs_data.REJECTED.get(key) or codecs_data.REJECTED.get(key.replace(u".", u"_")) or ())
    if rejected:
        yield problem(line, 0, "coding declaration %s, which Python 3 does not accept as a source encoding"
                      % name, rejected)
    accepted = ALL - rejected
    if _SURROGATE.search(m.result.text):
        yield problem(line, 0, "%s decodes this file to lone surrogates, which Python 3 cannot compile"
                      % name, accepted)
        return
    module = registry27.module_of(name)
    if module in _UTF8_MODULES or not accepted:
        return
    if module not in codecs_data.FINGERPRINTED:
        yield problem(line, 0, "%s keeps state between characters; py2scan cannot tell that Python 3 decodes "
                      "this file as 2.7 does" % name, accepted, decided=False)
        return
    differs = _versions(codecs_data.DIFFERS.get(module, ())) & accepted
    if differs and _NON_ASCII.search(m.source.decode("latin-1")):
        yield problem(line, 0, "%s decodes some bytes otherwise in these versions than in 2.7; py2scan "
                      "cannot tell that they compile this file" % name, differs, decided=False)


def _cookie_line(m):
    text = m.result.text
    first = text.find(u"\n")
    return 2 if first >= 0 and u"coding" not in text[:first] else 1


DETECTORS = [check_utf8, check_codec]
