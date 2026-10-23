# -*- coding: utf-8 -*-
"""py2scan.py27.registry27 applies codecs as Python 2.7.18 does, on 2.7 and 3.x alike.

The expected values are what 2.7.18's PyUnicode_Decode and
PyUnicode_AsEncodedString return. The examples name the ways 3.x's codecs
differ; the record checks are a fast subset of tests/data/codec27.json, which
.py-migrate/codec_parity.py records on 2.7.18 and checks in full.
"""
import io
import json
import os

import pytest

from py2scan.py27 import codecs27_data, registry27
from py2scan.py27.codecs27 import CodecError
from tests.codec27_battery import Emulation, byte, digest, fingerprint, text_samples

RECORD_PATH = os.path.join(os.path.dirname(__file__), "data", "codec27.json")
with io.open(RECORD_PATH, encoding="ascii") as f:
    RECORD = json.load(f)


def decoded(data, name):
    try:
        return registry27.decode(data, name)
    except CodecError as e:
        return "error: " + e.msg


@pytest.mark.parametrize("data, name, expected", [
    # punycode_decode calls rfind on the buffer object 2.7 passes every codec
    (b"x = 1\n", "punycode", "error: 'buffer' object has no attribute 'rfind'"),
    # 2.7's a2b_base64 ends at "==" after two characters, where 3.14 wants a whole quad,
    # and words any other failure as incorrect padding
    (b"ab==c", "base64", "error: decoder did not return an unicode object (type=str)"),
    (b"abcde", "base64", "error: Incorrect padding"),
    # 2.7's UTF-7 ends a shift on any character, and rereads it outside the shift
    (b"+\x80", "utf-7", "error: 'utf7' codec can't decode byte 0x80 in position 1: unexpected special character"),
    (b"+\x00", "utf_7", u"\x00"),
    # 2.7's multibyte decoders reject the bytes they read, not one (bpo-12016)
    (b"~!", "hz", "error: 'hz' codec can't decode bytes in position 0-1: illegal multibyte sequence"),
    (b"\x80", "hz", "error: 'hz' codec can't decode byte 0x80 in position 0: illegal multibyte sequence"),
    (b"\xa0", "shift_jis", "error: 'shift_jis' codec can't decode bytes in position 0-1: illegal multibyte sequence"),
    (b"\x8f\xa1!", "euc_jp", "error: 'euc_jp' codec can't decode bytes in position 0-2: illegal multibyte sequence"),
    # nameprep maps U+0130 by 2.7's table B.3, which 3.x regenerated
    (b"xn--bfa", "idna", "error: ('IDNA does not round-trip', 'xn--bfa', 'xn--i-9bb')"),
    # \N{...} knows Unicode 5.2's names only
    (b"\\N{GRINNING FACE}", "unicode_escape",
     "error: 'unicodeescape' codec can't decode bytes in position 0-16: unknown Unicode character name"),
    (b"\\N{LATIN SMALL LETTER A}", "unicode-escape", u"a"),
    (b"\\U0001", "raw_unicode_escape",
     "error: 'rawunicodeescape' codec can't decode bytes in position 0-5: truncated \\uXXXX"),
    # 2.7's UTF codecs accept surrogates, and call themselves utf16, utf32 and utf8
    (b"\x00\xd8", "utf-16-le", "error: 'utf16' codec can't decode bytes in position 0-1: unexpected end of data"),
    (b"\x00\xd8\x00\xd8", "utf_16_le",
     "error: 'utf16' codec can't decode bytes in position 0-1: illegal UTF-16 surrogate"),
    (b"\x00\xd8\x00\x00", "utf-32", u"\ud800"),
    (b"\xed\xa0\x80", "utf8", u"\ud800"),
    # names resolve through 2.7's encodings.aliases, which never matches a dotted
    # name, a mixed-case key or an alias of a module 2.7 lacks
    (b"x", "latin.1", "error: unknown encoding: latin.1"),
    (b"x", "8859", u"x"),
    (b"x", "tis260", "error: unknown encoding: tis260"),
    (b"x", "csHPRoman8", "error: unknown encoding: csHPRoman8"),
    (b"x", "hp_roman8", u"x"),
    # rot_13 and palmos use 2.7's charmaps: 3.x's rot_13 is not a text codec,
    # and 3.x's palmos maps 0x9b to U+203A
    (b"x", "rot-13", u"k"),
    (b"\x9b", "palmos", u"\x9b"),
])
def test_decoding_is_2_7s(data, name, expected):
    assert decoded(data, name) == expected


@pytest.mark.parametrize("text, name, expected", [
    (u"\u0130", "idna", b"xn--i-9bb"),
    (u"a..b", "idna", "error: label empty or too long"),
    (u"\u20ac", "palmos", b"\x80"),
    (u"\xe9\xe8x", "ascii", "error: 'ascii' codec can't encode characters in position 0-1: ordinal not in range(128)"),
    (u"\U00010000", "utf-8", b"\xf0\x90\x80\x80"),
    (u"\U00010000", "utf-32-le", b"\x00\x00\x01\x00"),
])
def test_encoding_is_2_7s(text, name, expected):
    try:
        assert registry27.encode(text, name) == expected
    except CodecError as e:
        assert "error: " + e.msg == expected


def test_every_codec_decodes_each_byte_as_recorded():
    emulation = Emulation()
    for module, families in sorted(RECORD["decode"].items()):
        outcomes = [emulation.decode(byte(b), module)[0] for b in range(256)]
        assert [256, digest(outcomes)] == families["single"], module


def test_every_codec_that_decodes_text_encodes_literals_as_recorded():
    emulation = Emulation()
    for module, families in sorted(RECORD["encode"].items()):
        for family, texts in text_samples():
            if family in ("pairs", "labels"):
                outcomes = [emulation.encode(text, module) for text in texts]
                assert [len(texts), digest(outcomes)] == families[family], (module, family)


def test_every_name_finds_the_codec_2_7_finds():
    emulation = Emulation()
    assert dict((name, fingerprint(emulation, name)) for name in RECORD["names"]) == RECORD["names"]


def test_the_record_covers_2_7s_registry():
    assert sorted(RECORD["decode"]) == sorted(codecs27_data.MODULES)
