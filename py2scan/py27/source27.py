# -*- coding: utf-8 -*-
"""Source bytes as Python 2.7's tokenizer reads them, ported from decode_str in
Parser/tokenizer.c: newlines translated, the BOM and PEP 263 declaration found,
and the text recoded to UTF-8 when it declares another codec.

The result is text whose characters are those bytes (a latin-1 view), so
tokenizer offsets are byte offsets, as CPython's are.

Copyright (c) 2001-2020 Python Software Foundation; All Rights Reserved.
Used under the PSF License Agreement, version 2, in PSF-LICENSE.txt.
"""
from py2scan.py27 import codecs27, registry27

BOM = b"\xef\xbb\xbf"
_ALNUM = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
_NAME_CHARS = _ALNUM | frozenset("-_.")


class DecodeError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)
        self.msg = msg


def translate_newlines(data):
    """\\r\\n and \\r become \\n, and a newline ends the text. As in the C original,
    text ending in \\r\\n gets a second newline."""
    out = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if not data.endswith((b"\n", b"\r")) or data.endswith(b"\r\n"):
        out += b"\n"
    return out


def normal_name(name):
    """get_normal_name: the utf-8 and latin-1 spellings, judged on the first 12 characters."""
    low = "".join("-" if c == "_" else c.lower() for c in name[:12])
    if low == "utf-8" or low.startswith("utf-8-"):
        return "utf-8"
    if low in ("latin-1", "iso-8859-1", "iso-latin-1") or \
            low.startswith(("latin-1-", "iso-8859-1-", "iso-latin-1-")):
        return "iso-8859-1"
    return name


def coding_spec(line):
    """get_coding_spec: the declared encoding in a line, or None."""
    size = len(line)
    i = 0
    while i < size - 6:
        if line[i] == "#":
            break
        if line[i] not in " \t\f":
            return None
        i += 1
    while i < size - 6:
        if line.startswith("coding", i) and line[i + 6] in ":=":
            begin = t = i + 7
            while t < size and line[t] in " \t":
                begin = t = t + 1
            while t < size and line[t] in _NAME_CHARS:
                t += 1
            if begin < t:
                return normal_name(line[begin:t])
        i += 1
    return None


def _ends_coding_search(line):
    """check_coding_spec without a declaration: a line holding anything but
    whitespace before a comment stops the search."""
    for c in line:
        if c in "#\n\r":
            return False
        if c not in " \t\f":
            return True
    return False


def find_encoding(text, bom):
    """(encoding the tokenizer records, codec to decode with or None) for the
    first two lines; raises DecodeError for a declaration that conflicts with a BOM."""
    first_end = text.find("\n")
    second_end = text.find("\n", first_end + 1) if first_end >= 0 else -1
    lines = [text[:first_end]] if first_end >= 0 else []
    if second_end >= 0:
        lines.append(text[first_end + 1:second_end + 1])
    encoding = "utf-8" if bom else None
    for line in lines:
        spec = coding_spec(line)
        if spec is None:
            if _ends_coding_search(line):
                break
            continue
        if bom:
            if spec != "utf-8":
                raise DecodeError("encoding problem: %s with BOM" % spec)
            return encoding, None
        if spec in ("utf-8", "iso-8859-1"):
            return spec, None
        return spec, spec
    return encoding, None


def decode_source(source):
    """(text the tokenizer reads, the encoding the parse tree records or None)."""
    data = translate_newlines(source)
    bom = data.startswith(BOM)
    if bom:
        data = data[len(BOM):]
    text = data.decode("latin-1")
    encoding, codec = find_encoding(text, bom)
    if codec is not None:
        try:
            text = codecs27.to_utf8(registry27.decode(data, codec)).decode("latin-1")
        except codecs27.CodecError as e:
            raise DecodeError(e.msg)
    return text, encoding
