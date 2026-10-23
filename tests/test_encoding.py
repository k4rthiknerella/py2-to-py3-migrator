# -*- coding: utf-8 -*-
from py2scan.encoding import decode_source_lines


def test_defaults_to_ascii():
    lines = decode_source_lines(b"x = 1\n")
    assert lines == [u"x = 1"]


def test_pep263_cookie_on_first_line():
    raw = u"# -*- coding: utf-8 -*-\nx = u'é'\n".encode("utf-8")
    lines = decode_source_lines(raw)
    assert lines[1] == u"x = u'é'"


def test_pep263_cookie_on_second_line():
    raw = u"#!/usr/bin/env python\n# coding: utf-8\nx = u'é'\n".encode("utf-8")
    lines = decode_source_lines(raw)
    assert lines[2] == u"x = u'é'"


def test_utf8_bom_without_cookie():
    raw = b"\xef\xbb\xbf" + u"x = u'é'\n".encode("utf-8")
    lines = decode_source_lines(raw)
    assert lines[0] == u"x = u'é'"


def test_utf8_bom_with_matching_cookie():
    raw = b"\xef\xbb\xbf" + u"# -*- coding: utf-8 -*-\nx = u'é'\n".encode("utf-8")
    lines = decode_source_lines(raw)
    assert lines[0] == u"# -*- coding: utf-8 -*-"
    assert lines[1] == u"x = u'é'"
