# -*- coding: utf-8 -*-
"""The inputs on which py2scan/py27/registry27 must do what Python 2.7.18's
codecs do, and the digests their outcomes are recorded as.

tests/data/codec27.json is what 2.7.18 computes for them, recorded by
.py-migrate/codec_parity.py through the C functions 2.7's compiler calls;
the script checks every family, and tests/test_registry27.py a fast subset.
"""
import hashlib
import sys
import zlib

from py2scan.py27 import codecs27_data, registry27
from py2scan.py27.codecs27 import CodecError, unichr_

PY2 = sys.version_info[0] == 2
ESC, SO, SI = b"\x1b", b"\x0e", b"\x0f"


def byte(value):
    return chr(value) if PY2 else bytes([value])


def join(values):
    return b"".join(byte(v) for v in values)


def stream(seed, size):
    """size pseudo-random bytes, the same on every interpreter."""
    out, counter = bytearray(), 0
    while len(out) < size:
        out += hashlib.sha256(("%s:%d" % (seed, counter)).encode("ascii")).digest()
        counter += 1
    return out[:size]


def strings(seed, count, alphabet, longest):
    """count strings of 0 to longest characters drawn from alphabet."""
    alphabet = bytearray(alphabet)
    choices = stream(seed, count * (longest + 1))
    out = []
    for i in range(count):
        row = choices[i * (longest + 1):(i + 1) * (longest + 1)]
        out.append(join(alphabet[c % len(alphabet)] for c in row[1:1 + row[0] % (longest + 1)]))
    return out


# Decoding batteries: every 1- and 2-byte input, then the inputs each family
# of codecs is particular about.

def two_bytes(nibble):
    return [join((lead, second)) for lead in range(nibble * 16, nibble * 16 + 16) for second in range(256)]


def euc3():
    return [join((0x8F, a, b)) for a in range(0xA1, 0xFF) for b in range(0xA1, 0xFF)] + \
           [join((0x8F, a, b)) for a in (0x00, 0x41, 0x80, 0xA0, 0xFF) for b in range(256)]


def gb4():
    leads = (0x81, 0x82, 0x84, 0x8F, 0x90, 0xE3, 0xFE, 0xFF)
    return [join((a, b, c, d)) for a in leads for b in range(0x30, 0x3A) for c in range(0x81, 0xFF, 5)
            for d in (0x2F, 0x30, 0x35, 0x39, 0x3A)] + \
           [join((a, b, c)) for a in leads for b in range(0x30, 0x3A) for c in range(0x80, 0x100)]


def utf8():
    tails = (0x00, 0x7F, 0x80, 0x8F, 0x90, 0x9F, 0xA0, 0xBF, 0xC0, 0xFF)
    out = []
    for lead in range(0xE0, 0x100):
        for a in tails:
            out.append(join((lead, a)))
            for b in tails:
                out.append(join((lead, a, b)))
                out.extend(join((lead, a, b, c)) for c in tails)
    return out


def units(values, width, extra):
    """Sequences of one to three code units, in both byte orders, then with
    extra bytes after them."""
    import itertools
    import struct
    out = []
    for n in (1, 2, 3):
        for seq in itertools.product(values, repeat=n):
            for order in "<>":
                packed = struct.pack(order + "%d%s" % (n, width), *seq)
                out.extend(packed + tail for tail in extra)
    return out


def utf16():
    return units((0x0041, 0x00E9, 0xD7FF, 0xD800, 0xDBFF, 0xDC00, 0xDFFF, 0xE000, 0xFEFF, 0xFFFE, 0xFFFF),
                 "H", (b"", b"A"))


def utf32():
    return units((0x41, 0xD800, 0xDC00, 0xFEFF, 0xFFFE, 0x10000, 0x10FFFF, 0x110000, 0xFFFE0000, 0xFFFFFFFF),
                 "I", (b"", b"A", b"AB", b"ABC"))


def escapes():
    prefixes = (b"", ESC + b"$B", ESC + b"$@", ESC + b"$A", ESC + b"$(C", ESC + b"$(D", ESC + b"$(O",
                ESC + b"$(P", ESC + b"$(Q", ESC + b"(B", ESC + b"(J", ESC + b"(I", ESC + b".A", ESC + b".F",
                ESC + b"$)C" + SO, ESC + b"$)A", ESC + b"&@" + ESC + b"$B", b"~{", b"~}", b"~")
    middles = (b"", SO, SI, ESC + b"N", ESC + b"O", b"~", b"\n")
    body = (0x21, 0x24, 0x28, 0x30, 0x41, 0x5A, 0x7B, 0x7D, 0x7E, 0x7F, 0x0A, 0x1B, 0x80, 0xA1)
    return [p + m + join((a, b)) for p in prefixes for m in middles for a in body for b in body]


def idna_labels():
    words = [u"python", u"Example", u"xn--", u"XN--abc", u"a" * 63, u"a" * 64, u"", u"xn--abc-", u"xn--zz"]
    samples = [u"\u00e9", u"\u00df", u"\u03b1\u03b2", u"\u4e2d\u6587", u"\ud55c\uad6d", u"\u0645\u0635\u0631",
               u"\u05e9\u05dc\u05d5\u05dd", u"a\u0301", u"\ufb01", u"\u00ad", u"\u0340", u"\ue000", u"\ufffd",
               u"\u0221", u"\U0001f600", u"\u00c9COLE", u"\u0645a", u"a\u0645", u"\u200b", u"\uff21", u"\u2163",
               u"\u3002", u"\u0130", u"\u03a3", u"\u1e9e", u"\ud800"]
    out = list(words)
    for i, sample in enumerate(samples):
        for text in (sample, u"x" + sample, sample * 3, sample + u"-" + sample):
            out.append(u"xn--" + registry27.punycode_encode(text).decode("ascii"))
            out.append(u"xn--" + registry27.punycode_encode(text).decode("ascii").upper())
    out.extend(u"xn--" + s.decode("ascii") for s in strings("idna", 400, b"abcdefghijklmnopqrstuvwxyz0123456789-", 10))
    return [label.encode("ascii") for label in out] + \
           [a.encode("ascii") + b"." + b.encode("ascii") for a in out[:40] for b in out[:40:3]] + \
           [b".", b"..", b"a.", b"a..b", b".a", b"x = 1\nimport a.xn--abc\n", b"a.xn--\n.b"]


# Names \\N{...} escapes might use: ones Unicode 5.2 has, with case and
# spelling variations; later additions, which 2.7 does not know; the aliases
# 3.3 accepts; and the names 2.7 computes rather than lists.
LATER_NAMES = [b"GRINNING FACE", b"PILE OF POO", b"TURKISH LIRA SIGN", b"CJK UNIFIED IDEOGRAPH-9FCC",
               b"CJK UNIFIED IDEOGRAPH-2B740", b"LATIN CAPITAL LETTER SHARP S", b"LINE FEED", b"BYTE ORDER MARK",
               b"NBSP", b"ZWJ", b"LATIN SMALL LETTER A", b"latin small letter a", b"LATIN  SMALL LETTER A",
               b"HANGUL SYLLABLE GA", b"HANGUL SYLLABLE GAG", b"HANGUL SYLLABLE HIH", b"hangul syllable ga",
               b"HANGUL SYLLABLE", b"CJK UNIFIED IDEOGRAPH-4E00", b"CJK UNIFIED IDEOGRAPH-9FCB",
               b"CJK UNIFIED IDEOGRAPH-4e00", b"CJK UNIFIED IDEOGRAPH-", b"CJK UNIFIED IDEOGRAPH-34FF",
               b"CJK UNIFIED IDEOGRAPH-2A6D6", b"CJK UNIFIED IDEOGRAPH-2B734", b"CJK UNIFIED IDEOGRAPH-2B735",
               b"CJK COMPATIBILITY IDEOGRAPH-F900", b"", b"A", b"SNOWMAN", b"\xc3\xa9"]


def named_escapes():
    """\\N{...} escapes for every 211th code point Unicode 5.2 names, and the
    names above, whole and cut short. 2.7 only."""
    import unicodedata
    names = [unicodedata.name(unichr_(c)).encode("ascii") for c in range(0, 0x110000, 211)
             if unicodedata.name(unichr_(c), None)]
    out = []
    for name in names + LATER_NAMES:
        out.extend([b"\\N{" + name + b"}", b"x\\N{" + name + b"}y", b"\\N{" + name, b"\\N" + name + b"}"])
    return out


def stored_inputs():
    """Compressed and uuencoded inputs and \\N{...} escapes, made on 2.7 and
    kept in the record so every interpreter checks the same bytes."""
    import binascii
    import bz2
    texts = [b"", b"x = 1\n", b"# coding: zlib\n" * 3, b"\x00" * 100000, bytes(stream("bin", 300))]
    out = []
    for compress in (zlib.compress, bz2.compress):
        for text in texts:
            packed = compress(text)
            out.extend([packed, packed[:-1], packed[:-4], packed[:2], packed[:len(packed) // 2], packed + b"trailing",
                        packed + packed, packed + packed[:6], b"\n" + packed])
            for at in (0, 1, 5, len(packed) // 2, len(packed) - 1):
                flipped = bytearray(packed)
                flipped[at] ^= 0x55
                out.append(bytes(flipped))
    out.extend([b"BZ", b"BZh", b"BZh9", b"BZh91AY&SY", b"x\x9c", b"x\x9c\x03\x00"])
    lines = [binascii.b2a_uu(chunk) for chunk in (b"x = 1\n", bytes(stream("uu", 45)), b"", b"\xff" * 10)]
    for body in (lines, lines[:1], [], [b"M" + b"!" * 60 + b"\n"], [b"#86)C\n"], [b"%86)C\x7f\n"], [b"#86)C   ``\n"],
                 [b"\x7f\n"], [b"#86)C~~\n"], [line.replace(b"\n", b"\r\n") for line in lines]):
        out.append(b"begin 644 f\n" + b"".join(body) + b"end\n")
        out.append(b"begin 644 f\n" + b"".join(body))
        out.append(b"# coding: uu\n" + b"begin 644 f\n" + b"".join(body) + b" \nend\n")
        out.append(b"".join(body) + b"end\n")
    return out + named_escapes()


def decoding_battery(stored):
    families = [("single", [byte(b) for b in range(256)])]
    families.extend(("pairs%x" % nibble, two_bytes(nibble)) for nibble in range(16))
    families.extend([("euc3", euc3()), ("gb4", gb4()), ("utf8", utf8()), ("utf16", utf16()), ("utf32", utf32()),
                     ("escapes", escapes()), ("idna", idna_labels()), ("stored", stored)])
    families.append(("random", [bytes(stream("random%d" % i, 1 + i % 12)) for i in range(3000)]))
    families.append(("ascii", strings("ascii", 3000, b"AZaz09+/=-_.~\\'\"\n !x", 14)))
    families.append(("escape", strings("escape", 2000, b"\\x0aF7u\nN{}'\"", 8)))
    return families


# Encoding batteries: what each codec decoded, and text at large.

def text_samples():
    singles = [unichr_(c) for c in list(range(0x400)) + list(range(0x400, 0x110000, 61))]
    marks = [u"a", u".", u"~", u"\\", u"+", u"-", u"\u00e9", u"\u00df", u"\u03b1", u"\u0434", u"\u4e2d", u"\uac00",
             u"\u30a2", u"\ufb01", u"\u00ad", u"\u3002", u"\uff0e", u"\uff61", u"\ue000", u"\ufffd", u"\ud800",
             u"\udc00", u"\U00010000", u"\U0010ffff", u"\u0645", u"\u05d0"]
    pairs = [u"a" + x + y + u"b" for x in marks for y in marks]
    labels = [u"".join(p) for p in ((u"python", u".", u"org"), (u"a", u"\u3002", u"b", u"\uff0e"), (u"",),
                                    (u"a" * 64,), (u"\u00e9" * 30,), (u"xn--abc",), (u"\u0645\u0635\u0631",),
                                    (u"\u0645a",), (u"\u00c9cole", u".", u"\u4e2d\u6587", u"."), (u"\u200b",))]
    return [("singles", singles), ("pairs", pairs), ("labels", labels)]


def canonical(value):
    if isinstance(value, bytes):
        return u"b" + u"".join(u"%02x" % c for c in bytearray(value))
    return u"t" + u",".join(u"%x" % ord(c) for c in value)


def failure(message):
    return u"e" + (message.decode("latin-1") if isinstance(message, bytes) else message)


def digest(outcomes):
    return hashlib.sha256(u"\n".join(outcomes).encode("utf-8")).hexdigest()[:16]


class Emulation(object):
    """registry27, on whichever interpreter runs this."""

    def decode(self, data, name):
        try:
            return canonical(registry27.decode(data, name)), True
        except CodecError as e:
            return failure(e.msg), False

    def encode(self, text, name):
        try:
            return canonical(registry27.encode(text, name))
        except CodecError as e:
            return failure(e.msg)


def names():
    """Every name 2.7's registry knows, and spellings it normalizes or rejects."""
    known = set(codecs27_data.MODULES) | set(codecs27_data.ALIASES) | set(codecs27_data.ALIASES.values())
    spellings = ["UTF8", "Utf-16", "utf--8", "_utf8_", "utf_8.", ".utf8", "latin.1", "iso.8859.1", "8859",
                 "cp-1252", "CP1252", "rot-13", "string-escape", "unicode-internal", "unicode-1-1-utf-7", "x",
                 "aliases", "__init__", "encodings", "codecs", "mbcs", "dbcs", "tactis", "tis260", "csHPRoman8",
                 "zlib", "uu", "quopri", "hex", "base64", "bz2", "euc-jp", "EUC_JP", "shift-jis", "ms-kanji",
                 "u8", "U8", "utf", "iso-2022-jp", "hz-gb-2312", "koi8-r", "mac-roman", "latin-1", "iso-8859-15"]
    return sorted(known) + spellings


def fingerprint(codec, name):
    """Which codec a name finds, told apart by what it decodes."""
    probe = [byte(b) for b in range(256)] + [bytes(stream("name%d" % i, 1 + i % 9)) for i in range(300)] + \
            [b"x = 1\n", b"a.xn--abc", b"~{<:~}", b"+AOk-", ESC + b"$B\x30\x21"]
    return digest([codec.decode(data, name)[0] for data in probe])


def measure(codec, stored, modules=None, decoding=None, encoding=None, quiet=False):
    """{"decode": {module: {family: [count, digest]}}, "encode": ..., "names": {name: digest}},
    for the modules and families given, or all of them."""
    decoding = decoding or decoding_battery(stored)
    encoding = text_samples() if encoding is None else encoding
    result = {"decode": {}, "encode": {}, "names": {}}
    for module in modules or sorted(codecs27_data.MODULES):
        decoded, families = [], {}
        for family, inputs in decoding:
            outcomes = []
            for data in inputs:
                outcome, ok = codec.decode(data, module)
                outcomes.append(outcome)
                if ok and len(decoded) < 3000:
                    decoded.append(outcome)
            families[family] = [len(inputs), digest(outcomes)]
        result["decode"][module] = families
        if decoded:
            texts = [(u"decoded", [u"".join(unichr_(int(c, 16)) for c in d[1:].split(u",") if c) for d in decoded])]
            result["encode"][module] = dict((family, [len(inputs), digest([codec.encode(t, module) for t in inputs])])
                                            for family, inputs in texts + encoding)
        if not quiet:
            sys.stderr.write(".")
    if modules is None:
        for name in names():
            result["names"][name] = fingerprint(codec, name)
    return result
