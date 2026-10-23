# -*- coding: utf-8 -*-
"""Python 2.7's codecs, as its compiler uses a declared source encoding: to
decode the whole source, and to encode string literals back into it.

A codec name resolves the way 2.7's encodings.search_function resolves it,
against 2.7's own registry (codecs27_data). Each codec then behaves as 2.7's
does on any interpreter, so a file decodes to the same text, or fails with
the same message, under 2.7 and 3.x:

- most codecs come from the running interpreter, where 2.7 and 3.14 agree on
  every input .py-migrate/codec_parity.py tries;
- the CJK codecs and HZ too, except that an illegal sequence spans the
  bytes 2.7 reads for it, not the one byte 3.3 and later report (bpo-12016);
- UTF-8, UTF-16, UTF-32 and unicode_internal are ports of 2.7's C codecs,
  which accept surrogates and word their errors differently;
- UTF-7, unicode_escape and raw_unicode_escape are ports of 2.7's C codecs,
  whose UTF-7 decoder ends a shift sequence on any character and whose
  \\N{...} escapes know only Unicode 5.2's names;
- punycode and idna are ports of 2.7's Python codecs, with 2.7's table B.3
  (its b3_exceptions and Unicode 5.2's lowercase) in nameprep;
- rot_13 and palmos use 2.7's charmaps, and the codecs that return bytes fail
  as 2.7 reports it.

Copyright (c) 2001-2020 Python Software Foundation; All Rights Reserved.
Used under the PSF License Agreement, version 2, in PSF-LICENSE.txt.
"""
import codecs
import re
import stringprep
import struct
from unicodedata import ucd_3_2_0

from py2scan.py27 import codecs27, codecs27_data
from py2scan.py27.codecs27 import CodecError, decode_error, encode_error, unichr_

text_type = type(u"")
_NOT_TEXT = "decoder did not return an unicode object (type=str)"
_NAME_SEPARATORS = re.compile(r"[^0-9a-z.]+")


def _ascii_lower(text):
    return u"".join(unichr_(ord(c) + 32) if u"A" <= c <= u"Z" else c for c in text)


def _ascii_upper(text):
    return u"".join(unichr_(ord(c) - 32) if u"a" <= c <= u"z" else c for c in text)


def module_of(name):
    """The encodings module 2.7 finds for a codec name, or None: codecs.lookup
    lowercases the name, normalize_encoding collapses every run of characters
    other than letters, digits and dots into one underscore, and an alias is
    tried before the name itself."""
    norm = u"_".join(part for part in _NAME_SEPARATORS.split(_ascii_lower(name)) if part)
    aliased = codecs27_data.ALIASES.get(norm) or codecs27_data.ALIASES.get(norm.replace(u".", u"_"))
    for module in ([aliased, norm] if aliased else [norm]):
        if module and u"." not in module and module in codecs27_data.MODULES:
            return str(module)
    return None


def _view(data):
    return data.decode("latin-1")


# UTF-16 and UTF-32 (PyUnicode_DecodeUTF16Stateful, PyUnicode_DecodeUTF32Stateful,
# wide build, little-endian native order, final).

def _byte_order(data, size, little_bom, big_bom, order):
    if order == 0 and data[:size] == little_bom:
        return "<", size
    if order == 0 and data[:size] == big_bom:
        return ">", size
    return (">" if order == 1 else "<"), 0


def _utf16_decode(data, order):
    view, out = _view(data), []
    endian, pos = _byte_order(data, 2, b"\xff\xfe", b"\xfe\xff", order)
    size = len(data)
    while pos < size:
        if size - pos < 2:
            raise CodecError(decode_error("utf16", view, pos, size, "truncated data"))
        unit = struct.unpack(endian + "H", data[pos:pos + 2])[0]
        pos += 2
        if not 0xD800 <= unit <= 0xDFFF:
            out.append(unichr_(unit))
            continue
        if size - pos < 2:
            raise CodecError(decode_error("utf16", view, pos - 2, size, "unexpected end of data"))
        if unit <= 0xDBFF:
            low = struct.unpack(endian + "H", data[pos:pos + 2])[0]
            pos += 2
            if 0xDC00 <= low <= 0xDFFF:
                out.append(unichr_((((unit & 0x3FF) << 10) | (low & 0x3FF)) + 0x10000))
                continue
            raise CodecError(decode_error("utf16", view, pos - 4, pos - 2, "illegal UTF-16 surrogate"))
        raise CodecError(decode_error("utf16", view, pos - 2, pos, "illegal encoding"))
    return u"".join(out)


def _utf32_decode(data, order):
    view, out = _view(data), []
    endian, pos = _byte_order(data, 4, b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff", order)
    size = len(data)
    while pos < size:
        if size - pos < 4:
            raise CodecError(decode_error("utf32", view, pos, size, "truncated data"))
        code = struct.unpack(endian + "I", data[pos:pos + 4])[0]
        if code >= 0x110000:
            raise CodecError(decode_error("utf32", view, pos, pos + 4, "code point not in range(0x110000)"))
        out.append(unichr_(code))
        pos += 4
    return u"".join(out)


def _utf16_encode(text, order):
    endian = ">" if order == 1 else "<"
    units = [0xFEFF] if order == 0 else []
    for char in text:
        code = ord(char)
        if code >= 0x10000:
            units.extend((0xD800 | ((code - 0x10000) >> 10), 0xDC00 | ((code - 0x10000) & 0x3FF)))
        else:
            units.append(code)
    return struct.pack(endian + "%dH" % len(units), *units)


def _utf32_encode(text, order):
    endian = ">" if order == 1 else "<"
    codes = ([0xFEFF] if order == 0 else []) + [ord(char) for char in text]
    return struct.pack(endian + "%dI" % len(codes), *codes)


def _unicode_internal_decode(data):
    """_PyUnicode_DecodeUnicodeInternal: native UCS-4 units."""
    view, out, size = _view(data), [], len(data)
    for pos in range(0, size, 4):
        if size - pos < 4:
            raise CodecError(decode_error("unicode_internal", view, pos, size, "truncated input"))
        code = struct.unpack("<I", data[pos:pos + 4])[0]
        if code > 0x10FFFF:
            raise CodecError(decode_error("unicode_internal", view, pos, pos + 4, "illegal code point (> 0x10FFFF)"))
        out.append(unichr_(code))
    return u"".join(out)


def _string_escape_decode(data):
    """string_escape's PyString_DecodeEscape: 2.7 fails either on an escape or,
    since it returns bytes, as a decoder that did not return text."""
    view, pos = _view(data), 0
    while pos < len(view):
        if view[pos] != u"\\":
            pos += 1
            continue
        if pos + 1 == len(view):
            raise CodecError("Trailing \\ in string")
        pos += 2
        if view[pos - 1] == u"x":
            if not (pos + 1 < len(view) and view[pos] in codecs27.HEX_DIGITS and view[pos + 1] in codecs27.HEX_DIGITS):
                raise CodecError("invalid \\x escape")
    raise CodecError(_NOT_TEXT)


# UTF-7 (PyUnicode_DecodeUTF7Stateful, wide build, final).

_BASE64 = dict((c, i) for i, c in enumerate(bytearray(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")))


class _Utf7(object):
    """2.7's decoder, which unlike 3.x's ends a shift sequence on any
    character that is not base 64, absorbing "-" and reading any other again."""

    def __init__(self, data):
        self.data, self.view, self.out = bytearray(data), _view(data), []
        self.shift_start = None  # where the shift sequence being read began
        self.bits = self.buffer = self.surrogate = 0

    def decode(self):
        pos, size = 0, len(self.data)
        while pos < size:
            ch = self.data[pos]
            if self.shift_start is not None:
                pos = self.shifted(ch, pos)
            elif ch == 0x2B:
                pos = self.plus(pos)
            elif ch <= 127:
                self.out.append(unichr_(ch))
                pos += 1
            else:
                self.fail(pos, pos + 1, "unexpected special character")
        if self.shift_start is not None and (self.surrogate or self.bits >= 6 or self.buffer):
            self.fail(self.shift_start, size, "unterminated shift sequence")
        return u"".join(self.out)

    def fail(self, start, end, reason):
        raise CodecError(decode_error("utf7", self.view, start, end, reason))

    def plus(self, pos):
        if self.data[pos + 1:pos + 2] == bytearray(b"-"):
            self.out.append(u"+")
            return pos + 2
        self.shift_start, self.bits, self.buffer = pos, 0, 0
        return pos + 1

    def shifted(self, ch, pos):
        if ch in _BASE64:
            self.buffer, self.bits = (self.buffer << 6) | _BASE64[ch], self.bits + 6
            if self.bits >= 16:
                self.bits -= 16
                unit, self.buffer = self.buffer >> self.bits, self.buffer & ((1 << self.bits) - 1)
                self.unit(unit)
            return pos + 1
        start, self.shift_start = self.shift_start, None
        if self.bits >= 6:
            self.fail(start, pos + 1, "partial character in shift sequence")
        if self.buffer:
            self.fail(start, pos + 1, "non-zero padding bits in shift sequence")
        if self.surrogate and ch <= 127:  # a lone high surrogate survives only before a direct character
            self.out.append(unichr_(self.surrogate))
        self.surrogate = 0
        return pos + 1 if ch == 0x2D else pos  # any other character is read again outside the shift

    def unit(self, unit):
        if self.surrogate and 0xDC00 <= unit <= 0xDFFF:
            self.out.append(unichr_((((self.surrogate & 0x3FF) << 10) | (unit & 0x3FF)) + 0x10000))
            self.surrogate = 0
            return
        self.flush()
        if 0xD800 <= unit <= 0xDBFF:
            self.surrogate = unit
        else:
            self.out.append(unichr_(unit))

    def flush(self):
        if self.surrogate:
            self.out.append(unichr_(self.surrogate))
            self.surrogate = 0


# Charmaps: 2.7's decoding maps are total, so only encoding can fail.

def _charmap(module):
    decoding = dict((byte, byte) for byte in range(256))
    decoding.update(codecs27_data.CHARMAPS[module])
    encoding = {}
    for byte, code in decoding.items():
        encoding[code] = None if code in encoding else byte  # make_encoding_map
    return decoding, encoding


def _charmap_decode(module, data):
    decoding = _charmap(module)[0]
    return u"".join(unichr_(decoding[byte]) for byte in bytearray(data))


def _charmap_encode(module, text):
    encoding = _charmap(module)[1]
    out = bytearray()
    for pos, char in enumerate(text):
        byte = encoding.get(ord(char))
        if byte is None:
            end = pos
            while end < len(text) and encoding.get(ord(text[end])) is None:
                end += 1
            raise CodecError(encode_error("charmap", text, pos, end, "character maps to <undefined>"))
        out.append(byte)
    return bytes(out)


# Punycode (Lib/encodings/punycode.py in 2.7).

def _threshold(j, bias):
    return min(26, max(1, 36 * (j + 1) - bias))


def _adapt(delta, first, numchars):
    delta //= 700 if first else 2
    delta += delta // numchars
    divisions = 0
    while delta > 455:
        delta //= 35
        divisions += 36
    return divisions + (36 * delta // (delta + 38))


def _decode_generalized_number(extended, extpos, bias):
    result, w, j = 0, 1, 0
    while True:
        if extpos >= len(extended):
            raise CodecError("incomplete punicode string")
        char = ord(extended[extpos])
        extpos += 1
        if 0x41 <= char <= 0x5A:
            digit = char - 0x41
        elif 0x30 <= char <= 0x39:
            digit = char - 22
        elif extpos < len(extended):  # 2.7 quotes the character after the bad one
            raise CodecError("Invalid extended code point '%s'" % extended[extpos])
        else:
            raise CodecError("string index out of range")
        t = _threshold(j, bias)
        result += digit * w
        if digit < t:
            return extpos, result
        w *= 36 - t
        j += 1


def punycode_decode(label):
    """punycode_decode for the ASCII label idna's ToUnicode passes it."""
    pos = label.rfind(u"-")
    base, extended = (u"", label) if pos == -1 else (label[:pos], label[pos + 1:])
    extended = _ascii_upper(extended)
    char, pos, bias, extpos = 0x80, -1, 72, 0
    while extpos < len(extended):
        newpos, delta = _decode_generalized_number(extended, extpos, bias)
        pos += delta + 1
        char += pos // (len(base) + 1)
        if char > 0x10FFFF:
            raise CodecError("Invalid character U+%x" % char)
        pos %= len(base) + 1
        base = base[:pos] + unichr_(char) + base[pos:]
        bias = _adapt(delta, extpos == 0, len(base))
        extpos = newpos
    return base


def _generalized_integer(n, bias):
    digits, j = [], 0
    while True:
        t = _threshold(j, bias)
        if n < t:
            digits.append(u"abcdefghijklmnopqrstuvwxyz0123456789"[n])
            return digits
        digits.append(u"abcdefghijklmnopqrstuvwxyz0123456789"[t + ((n - t) % (36 - t))])
        n = (n - t) // (36 - t)
        j += 1


def _insertion_unsort(text, extended):
    result, oldchar, oldindex = [], 0x80, -1
    for char in extended:
        code = ord(char)
        index = pos = -1
        delta = (sum(1 for c in text if ord(c) < code) + 1) * (code - oldchar)
        while True:
            pos += 1  # selective_find
            while pos < len(text) and text[pos] != char:
                if text[pos] < char:
                    index += 1
                pos += 1
            if pos == len(text):
                break
            index += 1
            delta += index - oldindex
            result.append(delta - 1)
            oldindex, delta = index, 0
        oldchar = code
    return result


def punycode_encode(text):
    base = u"".join(c for c in text if ord(c) < 128)
    deltas = _insertion_unsort(text, sorted(set(c for c in text if ord(c) >= 128)))
    digits, bias = [], 72
    for points, delta in enumerate(deltas):
        digits.extend(_generalized_integer(delta, bias))
        bias = _adapt(delta, points == 0, len(base) + points + 1)
    extended = u"".join(digits)
    return (base + u"-" + extended if base else extended).encode("ascii")


# IDNA (Lib/encodings/idna.py in 2.7).

_DOTS = re.compile(u"[.。．｡]")
_ACE = u"xn--"


def _map_b3(char):
    return codecs27_data.B3.get(ord(char), char)


def _map_b2(char):
    al = _map_b3(char)
    b = ucd_3_2_0.normalize("NFKC", al)
    c = ucd_3_2_0.normalize("NFKC", u"".join(_map_b3(ch) for ch in b))
    return c if b != c else al


_PROHIBITED = (stringprep.in_table_c12, stringprep.in_table_c22, stringprep.in_table_c3, stringprep.in_table_c4,
               stringprep.in_table_c5, stringprep.in_table_c6, stringprep.in_table_c7, stringprep.in_table_c8,
               stringprep.in_table_c9)


def nameprep(label):
    label = ucd_3_2_0.normalize("NFKC", u"".join(_map_b2(c) for c in label if not stringprep.in_table_b1(c)))
    for c in label:
        if any(table(c) for table in _PROHIBITED):
            raise CodecError("Invalid character %s" % py2_repr(c))
    randal = [stringprep.in_table_d1(c) for c in label]
    if any(randal):
        if any(stringprep.in_table_d2(c) for c in label):
            raise CodecError("Violation of BIDI requirement 2")
        if not randal[0] or not randal[-1]:
            raise CodecError("Violation of BIDI requirement 3")
    return label


def _is_ascii(text):
    return all(ord(c) < 128 for c in text)


def _ascii_label(label):
    if 0 < len(label) < 64:
        return label
    raise CodecError("label empty or too long")


def to_ascii(label):
    if _is_ascii(label):
        return _ascii_label(label)
    label = nameprep(label)
    if _is_ascii(label):
        return _ascii_label(label)
    if label.startswith(_ACE):
        raise CodecError("Label starts with ACE prefix")
    return _ascii_label(_ACE + punycode_encode(label).decode("ascii"))


def to_unicode(label):
    """ToUnicode for an ASCII label (the decoder has rejected anything else)."""
    if not label.startswith(_ACE):
        return label
    result = punycode_decode(label[len(_ACE):])
    label2 = to_ascii(result)
    if _ascii_lower(label) != label2:
        raise CodecError("('IDNA does not round-trip', %s, %s)" % (py2_repr(label, False), py2_repr(label2, False)))
    return result


def idna_decode(data):
    if not data:
        return u""
    view = codecs27.ascii_text(data)
    labels = view.split(u".")
    trailing = u""
    if labels and not labels[-1]:
        trailing = u"."
        del labels[-1]
    return u".".join(to_unicode(label) for label in labels) + trailing


def idna_encode(text):
    if not text:
        return b""
    labels = _DOTS.split(text)
    trailing = u""
    if labels and not labels[-1]:
        trailing = u"."
        del labels[-1]
    return (u".".join(to_ascii(label) for label in labels) + trailing).encode("ascii")


def py2_repr(text, unicode_=True):
    """repr() of a unicode (or, with unicode_ False, an ASCII str) in Python 2."""
    quote = u'"' if u"'" in text and u'"' not in text else u"'"
    out = [u"u" + quote if unicode_ else quote]
    for c in text:
        code = ord(c)
        if c == quote or c == u"\\":
            out.append(u"\\" + c)
        elif c in u"\t\n\r":
            out.append({u"\t": u"\\t", u"\n": u"\\n", u"\r": u"\\r"}[c])
        elif code < 0x20 or 0x7F <= code < 0x100:
            out.append(u"\\x%02x" % code)
        elif code < 0x100:
            out.append(c)
        elif code < 0x10000:
            out.append(u"\\u%04x" % code)
        else:
            out.append(u"\\U%08x" % code)
    out.append(quote)
    return u"".join(out)


# Codecs that 3.3 changed to resync one byte after an illegal sequence.
_MULTIBYTE = frozenset(("big5", "big5hkscs", "cp932", "cp949", "cp950", "euc_jis_2004", "euc_jisx0213",
                        "euc_jp", "euc_kr", "gb18030", "gb2312", "gbk", "hz", "johab", "shift_jis",
                        "shift_jis_2004", "shift_jisx0213"))
_THREE_BYTE_EUC = frozenset(("euc_jp", "euc_jis_2004", "euc_jisx0213"))


def _illegal_sequence_end(module, data, start):
    """Where 2.7 ends an illegal multibyte sequence: past the 2, 3 (EUC 0x8F)
    or 4 (GB18030 four-byte form) bytes its decoder read, even past the data;
    HZ rejects a byte with the high bit set on its own in both."""
    data = bytearray(data)
    if module == "hz" and data[start] & 0x80:
        return start + 1
    if module == "gb18030" and start + 1 < len(data) and 0x30 <= data[start + 1] <= 0x39:
        return start + 4
    if module in _THREE_BYTE_EUC and data[start] == 0x8F:
        return start + 3
    return start + 2


# The codecs that decode to bytes, which 2.7 then rejects as not text.

def _base64_decode(data):
    """binascii.a2b_base64 in 2.7, whose only failure is a quad left
    incomplete: "=" ends the data after three characters of a quad, or after
    two when the next valid character is "=" too, and is skipped elsewhere."""
    valid = [byte for byte in bytearray(data) if byte in _BASE64_VALID]
    quad_pos = 0
    for k, byte in enumerate(valid):
        if byte != 0x3D:
            quad_pos = (quad_pos + 1) & 3
        elif quad_pos == 3 or (quad_pos == 2 and valid[k + 1:k + 2] == [0x3D]):
            break
    else:
        if quad_pos:
            raise CodecError("Incorrect padding")
    raise CodecError(_NOT_TEXT)


_BASE64_VALID = frozenset(bytearray(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="))


def _bz2_decode(data):
    """bz2.decompress in 2.7: one stream, whatever follows it ignored."""
    import bz2
    if not data:
        raise CodecError(_NOT_TEXT)
    decompressor = bz2.BZ2Decompressor()
    try:
        decompressor.decompress(data)
    except (IOError, OSError):
        raise CodecError("invalid data stream")
    try:
        decompressor.decompress(b"")
    except EOFError:  # both interpreters raise it once the stream has ended
        raise CodecError(_NOT_TEXT)
    raise CodecError("couldn't find end of stream")


def _host_decode(module, data):
    try:
        text = codecs.lookup(module).decode(data)[0]
    except UnicodeDecodeError as e:
        end = e.end
        if module in _MULTIBYTE and e.reason == "illegal multibyte sequence" and e.end - e.start == 1:
            end = _illegal_sequence_end(module, data, e.start)
        raise CodecError(decode_error(e.encoding, _view(data), e.start, end, e.reason))
    except Exception as e:  # hex, zlib, uu and quopri raise their own errors
        raise CodecError(str(e))
    if not isinstance(text, text_type):
        raise CodecError(_NOT_TEXT)
    return text


def _utf8_sig_decode(data):
    return codecs27.utf8_decode(_view(data[3:] if data[:3] == codecs.BOM_UTF8 else data))


_DECODERS = {
    "utf_8": lambda data: codecs27.utf8_decode(_view(data)),
    "utf_8_sig": _utf8_sig_decode,
    "utf_16": lambda data: _utf16_decode(data, 0),
    "utf_16_le": lambda data: _utf16_decode(data, -1),
    "utf_16_be": lambda data: _utf16_decode(data, 1),
    "utf_32": lambda data: _utf32_decode(data, 0),
    "utf_32_le": lambda data: _utf32_decode(data, -1),
    "utf_32_be": lambda data: _utf32_decode(data, 1),
    "unicode_internal": _unicode_internal_decode,
    "string_escape": _string_escape_decode,
    "unicode_escape": lambda data: codecs27.decode_unicode_escape(_view(data)),
    "raw_unicode_escape": lambda data: codecs27.decode_raw_unicode_escape(_view(data)),
    "utf_7": lambda data: _Utf7(data).decode(),
    "rot_13": lambda data: _charmap_decode("rot_13", data),
    "palmos": lambda data: _charmap_decode("palmos", data),
    "punycode": lambda data: _raise("'buffer' object has no attribute 'rfind'"),
    "idna": idna_decode,
    "base64_codec": _base64_decode,
    "bz2_codec": _bz2_decode,
}

_ENCODERS = {
    "utf_8": codecs27.to_utf8,
    "utf_8_sig": lambda text: codecs.BOM_UTF8 + codecs27.to_utf8(text),
    "utf_16": lambda text: _utf16_encode(text, 0),
    "utf_16_le": lambda text: _utf16_encode(text, -1),
    "utf_16_be": lambda text: _utf16_encode(text, 1),
    "utf_32": lambda text: _utf32_encode(text, 0),
    "utf_32_le": lambda text: _utf32_encode(text, -1),
    "utf_32_be": lambda text: _utf32_encode(text, 1),
    "unicode_internal": lambda text: _utf32_encode(text, -1),
    "rot_13": lambda text: _charmap_encode("rot_13", text),
    "palmos": lambda text: _charmap_encode("palmos", text),
    "punycode": punycode_encode,
    "idna": idna_encode,
}


def _raise(msg):
    """punycode_decode calls text.rfind, which the buffer object
    PyUnicode_Decode passes to every codec lacks."""
    raise CodecError(msg)


_LOOKUPS = {}


def _module(name):
    if name not in _LOOKUPS:
        _LOOKUPS[name] = module_of(name)
    if _LOOKUPS[name] is None:
        raise CodecError("unknown encoding: %s" % name)
    return _LOOKUPS[name]


def decode(data, name):
    """PyUnicode_Decode(data, name, "strict") as 2.7 computes it: text, or a
    CodecError with str() of what 2.7 raises."""
    module = _module(name)
    if module in _DECODERS:
        return _DECODERS[module](data)
    return _host_decode(module, data)


def encode(text, name):
    """PyUnicode_AsEncodedString(text, name, "strict") as 2.7 computes it."""
    module = _module(name)
    if module in _ENCODERS:
        return _ENCODERS[module](text)
    try:
        return codecs.lookup(module).encode(text)[0]
    except UnicodeEncodeError as e:
        raise CodecError(encode_error(e.encoding, e.object, e.start, e.end, e.reason))
