# -*- coding: utf-8 -*-
import sys

from py2scan.encoding import (
    bad_coding_cookie, decode_source_lines, display_path, undecodable_cookie)


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


def test_display_path_replaces_undecodable_bytes():
    # Real repro: a file literally named with a raw non-UTF-8 byte (the
    # independent check's hostile/non_utf8_name case). On Python 2,
    # os.path.relpath() hands this straight through as `str` (bytes) no
    # different in type from any other path; left alone, it reaches
    # json.dumps() later and crashes the whole scan - not just this one
    # file - with an unhandled UnicodeDecodeError (Python 2's json
    # encoder decodes str dict keys/values as UTF-8). On Python 3,
    # os.walk already decoded the same byte to a lone surrogate via
    # surrogateescape; left alone, json.dumps() doesn't crash but writes
    # a \udcXX escape instead of the Python 2 side's U+FFFD - the same
    # real file producing different JSON bytes per host (R2). Both
    # sides must converge on the identical result for the identical
    # bytes, so this test runs the same assertion on both rather than
    # skipping one.
    bad = b"caf\xe9.py" if sys.version_info[0] < 3 else u"caf\udce9.py"
    result = display_path(bad)
    assert result == u"caf�.py"
    assert isinstance(result, type(u""))


def test_bad_coding_cookie_detects_each_nontext_codec_and_its_aliases():
    # Real repro: a file whose coding cookie names rot13 (the independent
    # check's exact case) decodes without error on 2.7.18 - str and bytes
    # are the same type there - but every judged Python 3 version refuses
    # to decode the source at all under any of the stdlib's seven
    # non-text codecs (confirmed on real 3.6.15 and 3.14.9: each raises
    # "<name> is not a text encoding"). Every name tested here is a
    # distinct alias of one of the seven, not just the canonical module
    # name, since the cookie accepts either.
    for name in (u"rot13", u"ROT_13", u"base64", u"BASE-64", u"bz2",
                 u"hex", u"quoted-printable", u"uu", u"zip", u"zlib"):
        raw = (u"# -*- coding: %s -*-\nx = 1\n" % name).encode("ascii")
        assert bad_coding_cookie(raw) == name, name


def test_bad_coding_cookie_passes_real_encodings_through():
    assert bad_coding_cookie(b"# -*- coding: utf-8 -*-\nx = 1\n") is None
    assert bad_coding_cookie(b"x = 1\n") is None


def test_undecodable_cookie_detects_bytes_that_do_not_match_the_declared_name():
    # Real repro (independent check's round-3 held-back probes): the
    # cookie names a real text codec, unlike bad_coding_cookie's seven,
    # but these particular bytes aren't actually valid under it.
    assert undecodable_cookie(b"# -*- coding: utf-16 -*-\nx = 1\n") == u"utf-16"
    assert undecodable_cookie(b"# -*- coding: punycode -*-\nx = 1\n") == u"punycode"


def test_undecodable_cookie_passes_decodable_source_through():
    assert undecodable_cookie(b"# -*- coding: utf-8 -*-\nx = 1\n") is None
    assert undecodable_cookie(b"x = 1\n") is None


def test_undecodable_cookie_defers_nontext_codecs_to_bad_coding_cookie():
    # rot13 et al. decode without error on 2.7.18 (str is bytes there);
    # bad_coding_cookie, not this function, is what reports them.
    assert undecodable_cookie(b"# -*- coding: rot13 -*-\nx = 1\n") is None
