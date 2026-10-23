# -*- coding: utf-8 -*-
import sys

import pytest

from py2scan.encoding import decode_source_lines, display_path


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


def test_display_path_passes_valid_text_through_unchanged():
    assert display_path(u"caf\xe9.py") == u"caf\xe9.py"


def test_display_path_on_python2_replaces_undecodable_bytes():
    # Real repro: a file literally named with a raw non-UTF-8 byte (the
    # independent check's hostile/non_utf8_name case). On Python 2,
    # os.path.relpath() hands this straight through as `str` (bytes) no
    # different in type from any other path; left alone, it reaches
    # json.dumps() later and crashes the whole scan - not just this one
    # file - with an unhandled UnicodeDecodeError (Python 2's json
    # encoder decodes str dict keys/values as UTF-8).
    if sys.version_info[0] >= 3:
        pytest.skip("display_path only decodes bytes on Python 2")
    result = display_path(b"caf\xe9.py")
    assert result == u"caf�.py"
    assert isinstance(result, type(u""))
