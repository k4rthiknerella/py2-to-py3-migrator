# -*- coding: utf-8 -*-
"""Which \\N{name} escapes each judged Python 3 version resolves.

3.6 to 3.13 (Modules/unicodedata.c _getcode): "HANGUL SYLLABLE " and
"CJK UNIFIED IDEOGRAPH-" are matched case-sensitively, the latter with 4 or 5
upper-case hex digits; any other name, or alias, through the name table,
case-insensitively. 3.14 and 3.15 match every prefix in the version's
derived_name_prefixes case-insensitively, with 4 to 6 hex digits and no
leading zero, and anything else through the name table. Names never change
once assigned; the 5.2 names come from the same lookup the 2.7 front end
uses, the rest from names_data, which .py-migrate/py3_data.py recorded from
each judged interpreter.
"""
import base64
import bisect
import zlib

from py2scan.py27 import codecs27
from py2scan.py3 import names_data as data
from py2scan.versions import VERSIONS, label

_HEX = frozenset(u"0123456789ABCDEF")
_ALGORITHMIC = (u"HANGUL SYLLABLE ", u"CJK UNIFIED IDEOGRAPH-")
_regular = []


def unknown(name):
    """The judged versions in which \\N{name} is an error."""
    if any(char >= u"\x80" for char in name):
        return frozenset(VERSIONS)
    return frozenset(v for v in VERSIONS if not known(name, v))


def known(name, version):
    if version < (3, 14):
        return _known_classic(name, label(version))
    return _known_derived(name, label(version))


def _upper(name):
    return u"".join(unichr_(ord(c) - 32) if u"a" <= c <= u"z" else c for c in name)


def unichr_(code):
    return codecs27.unichr_(code)


def _in(ranges, code):
    i = bisect.bisect_right([r[0] for r in ranges], code) - 1
    return i >= 0 and ranges[i][0] <= code <= ranges[i][1]


def _known_classic(name, version):
    if name.startswith(u"HANGUL SYLLABLE "):
        return codecs27._hangul_syllable(name) is not None
    if name.startswith(u"CJK UNIFIED IDEOGRAPH-"):
        digits = name[22:]
        return (len(digits) in (4, 5) and set(digits) <= _HEX
                and _in(data.FAMILIES[u"CJK UNIFIED IDEOGRAPH-"].get(version, ()), int(digits, 16)))
    return _known_regular(_upper(name), version)


def _hex_code(digits):
    """parse_hex_code: 4 to 6 hex digits, either case, no leading zero."""
    if not 4 <= len(digits) <= 6 or digits[0] == u"0" or not set(digits) <= _HEX:
        return None
    code = int(digits, 16)
    return code if code <= 0x10FFFF else None


def _known_derived(name, version):
    upper = _upper(name)
    if upper.startswith(u"HANGUL SYLLABLE "):
        return codecs27._hangul_syllable(upper) is not None
    for prefix in data.DERIVED[version]:
        if upper.startswith(prefix):
            code = _hex_code(upper[len(prefix):])
            return code is not None and _in(data.FAMILIES[prefix].get(version, ()), code)
    return _known_regular(upper, version)


def _known_regular(upper, version):
    """In the version's name table: a name or an alias, upper-cased."""
    if upper.startswith(_ALGORITHMIC):
        return False
    for prefix, by_version in data.FAMILIES.items():
        if upper.startswith(prefix) and prefix not in _ALGORITHMIC:
            digits = upper[len(prefix):]
            if 4 <= len(digits) <= 5 and set(digits) <= _HEX:
                code = int(digits, 16)
                if upper == u"%s%04X" % (prefix, code) and _in(by_version.get(version, ()), code):
                    return True
    if codecs27.lookup_name(upper) is not None:
        return True
    first = regular().get(upper) or data.ALIASES.get(upper)
    return first is not None and data.VERSIONS.index(first) <= data.VERSIONS.index(version)


def regular():
    """name: the first judged version whose name table has it, for names
    beyond Unicode 5.2."""
    if not _regular:
        text = zlib.decompress(base64.b64decode(data.REGULAR)).decode("ascii")
        table = {}
        for line in text.split(u"\n"):
            if line:
                index, name = line.split(u" ", 1)
                table[name] = data.VERSIONS[int(index)]
        _regular.append(table)
    return _regular[0]
