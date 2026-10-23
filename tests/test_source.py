# -*- coding: utf-8 -*-
import hashlib

import pytest

from py2scan.source import source_lines, utf8_text

UTF8_REPLACE_3_14 = "b4d72ae1501960c7"  # 472436 inputs

CASES = [
    (b"# -*- coding: latin-1 -*-\nprint 'caf\xe9'\n",
     [u"# -*- coding: latin-1 -*-", u"print 'caf\xe9'"]),
    (b"#!/usr/bin/env python\n# vim: set fileencoding=cp1252 :\ns = '\x93hi\x94'\n",
     [u"#!/usr/bin/env python", u"# vim: set fileencoding=cp1252 :", u"s = '“hi”'"]),
    (b"# coding: utf-8-unix\ns = '\xc3\xa9'\n", [u"# coding: utf-8-unix", u"s = '\xe9'"]),
    (b"# coding: shift_jis\ns = '\x95\x5c'\n", [u"# coding: shift_jis", u"s = '表'"]),
    (b"\xef\xbb\xbfs = '\xc3\xa9'\n", [u"s = '\xe9'"]),
    (b"s = '\xc3\xa9'\n", [u"s = '\xe9'"]),
    # A declaration after a line of code does not count (PEP 263), so this is UTF-8.
    (b"x = 1\n# coding: latin-1\ns = '\xc3\xa9'\n", [u"x = 1", u"# coding: latin-1", u"s = '\xe9'"]),
    (b"a\r\nb\rc\nd", [u"a", u"b", u"c", u"d"]),
    (b"a\x0cb\n", [u"a\x0cb"]),
]


@pytest.mark.parametrize("source,lines", CASES, ids=["src-%d" % i for i in range(len(CASES))])
def test_source_lines_follow_the_declared_encoding(source, lines):
    assert source_lines(source) == lines


def test_undecodable_bytes_do_not_fail():
    assert source_lines(b"# coding: ascii\ns = '\xff'\n") == [u"# coding: ascii", u"s = '�'"]


# Bytes at the edges of UTF-8's ranges (Unicode table 3-7).
_EDGES = bytearray(b"\x00\x41\x7f\x80\x8f\x90\x9f\xa0\xbf\xc0\xc1\xc2\xdf"
                   b"\xe0\xe1\xec\xed\xee\xef\xf0\xf1\xf3\xf4\xf5\xff")


def utf8_battery():
    """Every byte pair, and every sequence of up to four edge bytes."""
    yield [bytes(bytearray([a, b])) for a in range(256) for b in range(256)]
    level = [b""]
    for _ in range(4):
        level = [s + bytes(bytearray([b])) for s in level for b in _EDGES]
        yield level


def utf8_digest(decode):
    h = hashlib.sha256()
    for family in utf8_battery():
        for data in family:
            h.update(u",".join(u"%x" % ord(c) for c in decode(data)).encode("ascii") + b";")
    return h.hexdigest()[:16]


@pytest.mark.parametrize("data, text", [
    (b"caf\xe9.py", u"caf�.py"),
    (b"\xed\xa0\x80", u"���"),  # an encoded surrogate, which 2.7's codec accepts
    (b"\xf0\x90\x80", u"�"),  # one maximal subpart
    (b"\xe1\x80A", u"�A"),
    (b"\xf4\x90\x80\x80", u"����"),
    (u"表.py".encode("utf-8"), u"表.py"),
])
def test_utf8_text_replaces_as_python_3_does(data, text):
    assert utf8_text(data) == text


def test_utf8_text_is_what_python_3_14_decodes_with_replace():
    # Recorded on 3.14.9 with utf8_digest(lambda b: b.decode("utf-8", "replace")).
    assert utf8_digest(utf8_text) == UTF8_REPLACE_3_14
