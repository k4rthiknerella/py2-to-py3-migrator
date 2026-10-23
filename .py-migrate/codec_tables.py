# -*- coding: utf-8 -*-
"""A fingerprint of how an interpreter decodes with each of 2.7's stateless
text codecs: every 1- and 2-byte input, every 3-byte input after an EUC
SS3 lead (0x8F), and every 4-byte GB18030 input, decoded strictly. Equal
fingerprints on 2.7.18 and a 3.x version mean the codec turns any file into
the same text in both, since these decoders read a file one character at a
time with no state between characters (rulings R1, R9).

  python .py-migrate/codec_tables.py OUT       on 2.7.18 and each judged 3.x
Also prints whether "\\N{TANGUT IDEOGRAPH-XXXX}" resolves, as ranges.
"""
import codecs
import hashlib
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE)]

from py2scan.py27 import codecs27_data  # noqa: E402

# Codecs whose decoders carry state from one character to the next, or that
# are not text codecs: py2scan does not fingerprint them.
STATEFUL = frozenset(["utf_7", "hz", "iso2022_jp", "iso2022_jp_1", "iso2022_jp_2", "iso2022_jp_2004",
                      "iso2022_jp_3", "iso2022_jp_ext", "iso2022_kr", "unicode_escape", "raw_unicode_escape",
                      "idna", "punycode", "utf_8_sig", "utf_8", "utf_16", "utf_16_be", "utf_16_le", "utf_32",
                      "utf_32_be", "utf_32_le", "unicode_internal", "charmap", "undefined", "mbcs", "rot_13",
                      "base64_codec", "bz2_codec", "hex_codec", "quopri_codec", "string_escape", "uu_codec",
                      "zlib_codec"])


def inputs(module):  # noqa: C901
    for a in range(256):
        yield struct.pack("B", a)
    for a in range(256):
        for b in range(256):
            yield struct.pack("BB", a, b)
    if module.startswith("euc_"):
        for b in range(256):
            for c in range(256):
                yield struct.pack("BBB", 0x8F, b, c)
    if module == "gb18030":
        for a in range(0x81, 0xFF):
            for b in range(0x30, 0x3A):
                for c in range(0x81, 0xFF):
                    for d in range(0x30, 0x3A):
                        yield struct.pack("BBBB", a, b, c, d)


def fingerprint(module):
    try:
        decode = codecs.getdecoder(module)
    except LookupError:
        return None
    digest = hashlib.sha256()
    for data in inputs(module):
        try:
            text = decode(data, "strict")[0]
            digest.update(b"+" + text.encode("utf-8", "surrogatepass") + b"\0")
        except UnicodeDecodeError:
            digest.update(b"-\0")
    return digest.hexdigest()


def tangut():
    if sys.version_info[0] < 3:
        return []
    found = []
    for code in range(0x17000, 0x19000):
        try:
            eval(compile('"\\N{TANGUT IDEOGRAPH-%04X}"' % code, "t.py", "eval", dont_inherit=True))
        except SyntaxError:
            continue
        if found and found[-1][1] == code - 1:
            found[-1][1] = code
        else:
            found.append([code, code])
    return found


def main(argv):
    if len(argv) != 1:
        sys.stderr.write(__doc__)
        return 2
    modules = sorted(m for m in codecs27_data.MODULES if m not in STATEFUL)
    facts = {"python": "%d.%d.%d" % sys.version_info[:3], "tangut": tangut(),
             "codecs": dict((m, fingerprint(m)) for m in modules)}
    with open(argv[0], "w") as f:
        f.write(json.dumps(facts, sort_keys=True))
    print("%s: %d codecs" % (facts["python"], len(modules)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
