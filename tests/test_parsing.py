# -*- coding: utf-8 -*-
import warnings

from py2scan.parsing import native_compiles


def test_native_compiles_suppresses_syntax_warnings():
    # compile() can emit a SyntaxWarning (e.g. an invalid \d escape
    # sequence Python 2.7 never warned about) as a side effect even when
    # it succeeds. native_compiles is a pure boolean signal for the
    # monotonic backstop, not one of py2scan's own findings, so it must
    # not leak that warning to the caller's terminal on every scan of an
    # unrelated file.
    source = b"x = '\\d'\n"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert native_compiles("m.py", source) is True
    assert caught == []
