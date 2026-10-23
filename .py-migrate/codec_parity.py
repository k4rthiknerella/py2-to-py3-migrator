# -*- coding: utf-8 -*-
"""Parity of py2scan/py27/registry27 with the codecs Python 2.7 itself applies
to source code: what the tokenizer's PyUnicode_Decode(data, size, name, NULL)
and ast.c's PyUnicode_AsEncodedString(text, name, NULL) compute, called
through ctypes on 2.7.18, for a deterministic battery of inputs per codec.

  record RECORD     on 2.7.18: write what 2.7 computes, as one digest per
                    codec and family of inputs
  check RECORD      on 2.7 or 3.x: registry27 against the record
  dump RECORD SIDE SECTION CODEC FAMILY
                    one line per input of a family: the input and what the
                    oracle (2.7.18 only) or the emulation computes for it

Decoding is compared by the text or the error message (the tokenizer reports
str() of any decoding failure). Encoding matters only for the codecs whose
decoder returned text: with any other, the source never decodes and ast.c never
encodes a literal (string_escape and the bytes codecs return str by
construction; punycode fails on the buffer it is given). Their encoding is
compared the same way, and record fails unless every encoding failure is a
UnicodeError, which ast.c reports as "(unicode error) ..." and ast27 assumes.
check exits 1 on any difference.
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE)]

from py2scan.py27.codecs27 import unichr_  # noqa: E402
from tests.codec27_battery import (  # noqa: E402
    Emulation, canonical, decoding_battery, failure, measure, stored_inputs, text_samples)


class Oracle(object):
    """2.7.18's own entry points, through ctypes. 2.7 only."""

    def __init__(self):
        import ctypes
        self.decode_c = ctypes.pythonapi.PyUnicodeUCS4_Decode
        self.decode_c.restype = ctypes.py_object
        self.decode_c.argtypes = [ctypes.c_char_p, ctypes.c_ssize_t, ctypes.c_char_p, ctypes.c_char_p]
        self.encode_c = ctypes.pythonapi.PyUnicodeUCS4_AsEncodedString
        self.encode_c.restype = ctypes.py_object
        self.encode_c.argtypes = [ctypes.py_object, ctypes.c_char_p, ctypes.c_char_p]
        self.encode_errors = {}

    def decode(self, data, name):
        try:
            return canonical(self.decode_c(data, len(data), name, None)), True
        except Exception as e:  # str() of any failure is what the tokenizer reports
            return failure(str(e)), False

    def encode(self, text, name):
        try:
            return canonical(self.encode_c(text, name, None))
        except Exception as e:
            self.encode_errors.setdefault(type(e).__name__, set()).add(name)
            return failure(str(e))


def write(path, record):
    lines = [u"{"]
    for key in ("python", "encode_errors", "stored"):
        lines.append(u"%s: %s," % (json.dumps(key), json.dumps(record[key], sort_keys=True)))
    for section in ("decode", "encode", "names"):
        rows = [u"  %s: %s" % (json.dumps(k), json.dumps(v, sort_keys=True, separators=(",", ":")))
                for k, v in sorted(record[section].items())]
        lines.append(u"%s: {\n%s\n}," % (json.dumps(section), u",\n".join(rows)))
    lines[-1] = lines[-1][:-1]
    with io.open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(u"\n".join(lines) + u"\n}\n")


def record(path):
    oracle = Oracle()
    stored = stored_inputs()
    result = measure(oracle, stored)
    unexpected = sorted((kind, sorted(codecs)) for kind, codecs in oracle.encode_errors.items()
                        if kind not in ("UnicodeEncodeError", "UnicodeError"))
    if unexpected:
        print("encoding failed with %r, which ast.c does not report as a unicode error" % unexpected)
        return 1
    result["python"] = "%d.%d.%d" % sys.version_info[:3]
    result["encode_errors"] = sorted(oracle.encode_errors)
    result["stored"] = [canonical(data)[1:] for data in stored]
    write(path, result)
    print("recorded %d codecs and %d names on %s; no text decoded by: %s" % (
        len(result["decode"]), len(result["names"]), result["python"],
        " ".join(sorted(set(result["decode"]) - set(result["encode"])))))
    return 0


def check(path):
    with io.open(path, encoding="ascii") as f:
        expected = json.load(f)
    stored = [bytes(bytearray.fromhex(h)) for h in expected["stored"]]
    actual = measure(Emulation(), stored)
    differ = total = 0
    if sorted(actual["encode"]) != sorted(expected["encode"]):
        differ += 1
        print("DIFF the codecs that decode to text: %s" % sorted(set(actual["encode"]) ^ set(expected["encode"])))
    for section in ("decode", "encode"):
        for module, families in sorted(expected[section].items()):
            for family, (count, value) in sorted(families.items()):
                total += count
                if actual[section].get(module, {}).get(family) != [count, value]:
                    differ += 1
                    print("DIFF %s %s %s (%d inputs)" % (section, module, family, count))
    for name, value in sorted(expected["names"].items()):
        if actual["names"].get(name) != value:
            differ += 1
            print("DIFF name %s" % name)
    print("%s %d.%d.%d against %s: %d codecs, %d inputs, %d names, %d families differ" % (
        "cpython", sys.version_info[0], sys.version_info[1], sys.version_info[2], expected["python"],
        len(expected["decode"]), total, len(expected["names"]), differ))
    return 1 if differ else 0


def dump(path, side, section, module, family):
    with io.open(path, encoding="ascii") as f:
        stored = [bytes(bytearray.fromhex(h)) for h in json.load(f)["stored"]]
    codec = Oracle() if side == "oracle" else Emulation()
    if section == "decode":
        for data in dict(decoding_battery(stored))[family]:
            print("%s\t%s" % (canonical(data), codec.decode(data, module)[0]))
        return 0
    if family == "decoded":
        texts, oracle = [], Oracle()
        for _, inputs in decoding_battery(stored):
            texts.extend(oracle.decode(data, module)[0] for data in inputs)
        texts = [u"".join(unichr_(int(c, 16)) for c in t[1:].split(u",") if c) for t in texts if t[0] == u"t"][:3000]
    else:
        texts = dict(text_samples())[family]
    for text in texts:
        print("%s\t%s" % (canonical(text), codec.encode(text, module)))
    return 0


def main(argv):
    if argv[:1] == ["record"] and len(argv) == 2 and sys.version_info[:3] == (2, 7, 18):
        return record(argv[1])
    if argv[:1] == ["check"] and len(argv) == 2:
        return check(argv[1])
    if argv[:1] == ["dump"] and len(argv) == 6 and argv[2] in ("oracle", "emulation"):
        return dump(*argv[1:])
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
