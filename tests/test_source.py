# -*- coding: utf-8 -*-
import pytest

from py2scan.source import source_lines

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
