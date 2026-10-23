# -*- coding: utf-8 -*-
"""Python 2 sources that probe what each Python 3 version can compile.

Each case is (name, source bytes). Their verdicts on the real interpreters
(3.6.15 to 3.15.1, and 2.7.18's ast.parse) are recorded in
tests/data/py3_verdicts.json by .py-migrate/py3_verdicts.py; tests/test_py3.py
checks py2scan's verdict on every case and version against that record.
"""


def _named(prefix, sources):
    return [("%s-%d" % (prefix, i), s if isinstance(s, bytes) else s.encode("utf-8")) for i, s in enumerate(sources)]


LEXICAL = _named("prefix", [
    u"x = ur'a'\n", u"x = UR'a'\n", u"x = uR'''a'''\n", u"x = Ur\"a\"\n",
    u"from __future__ import unicode_literals\nx = ur'a'\n",
    u"x = u'a'\n", u"x = r'a'\n", u"x = b'a'\n", u"x = br'a'\n", u"x = BR'a'\n", u"x = U'a'\n",
]) + _named("escape", [
    u"x = '\\u1234'\n", u"x = '\\u12'\n", u"x = '\\u12g4'\n", u"x = '\\U0010ffff'\n", u"x = '\\U00110000'\n",
    u"x = '\\U0001F600'\n", u"x = '\\U0001F6'\n", u"x = '\\N{LATIN SMALL LETTER A}'\n",
    u"x = '\\N{latin small letter a}'\n", u"x = '\\N{NO SUCH NAME}'\n", u"x = '\\N'\n", u"x = '\\N{'\n",
    u"x = '\\N{}'\n", u"x = '\\Nabc'\n", u"x = '\\N{LATIN SMALL LETTER A'\n",
    u"x = '\\N{GRINNING FACE}'\n", u"x = '\\N{BITCOIN SIGN}'\n", u"x = '\\N{YAWNING FACE}'\n",
    u"x = '\\N{BUBBLE TEA}'\n", u"x = '\\N{MELTING FACE}'\n", u"x = '\\N{SHAKING FACE}'\n",
    u"x = '\\N{FACE WITH BAGS UNDER EYES}'\n", u"x = '\\N{LINE FEED}'\n", u"x = '\\N{LF}'\n",
    u"x = '\\N{BYTE ORDER MARK}'\n", u"x = '\\N{LATIN CAPITAL LETTER A WITH MACRON AND GRAVE}'\n",
    u"x = '\\N{CJK UNIFIED IDEOGRAPH-4E00}'\n", u"x = '\\N{CJK UNIFIED IDEOGRAPH-2EBF0}'\n",
    u"x = '\\N{HANGUL SYLLABLE GA}'\n", u"x = '\\N{TANGUT IDEOGRAPH-17000}'\n",
    u"x = r'\\N{NO SUCH NAME}'\n", u"x = b'\\N{NO SUCH NAME}'\n", u"x = '\\\\N{NO SUCH NAME}'\n",
    u"x = '''doc\n\\u12'''\n", u"x = '\\777'\n", u"x = '\\x4'\n", u"x = '\\d'\n",
    u"from __future__ import unicode_literals\nx = b'\\u12'\n",
    u"from __future__ import unicode_literals\nx = '\\u1234'\n",
    u"def f():\n    '''\\u12'''\n",
]) + _named("bytes", [
    u"# coding: utf-8\nx = b'\xe9'\n", u"# coding: utf-8\nx = br'\xe9'\n", u"x = b'\\xe9'\n",
    u"# coding: utf-8\nx = '\xe9'\n", u"# coding: utf-8\nx = u'\xe9'\n",
    u"# coding: utf-8\n# \xe9\nx = b'a'\n",
]) + _named("concat", [
    u"x = 'a' b'b'\n", u"x = b'a' 'b'\n", u"x = u'a' b'b'\n", u"x = b'a' u'b'\n", u"x = 'a' u'b'\n",
    u"x = b'a' br'b'\n", u"x = 'a' r'b'\n", u"x = ('a'\n     b'b')\n",
    u"from __future__ import unicode_literals\nx = 'a' b'b'\n",
]) + _named("number", [
    u"x = 00\n", u"x = 0\n", u"x = 0e0\n", u"x = 09.5\n", u"x = 0j\n", u"x = 0xff\n", u"x = 0o17\n", u"x = 0b1\n",
    u"x = 1if 1 else 2\n", u"x = 1or 2\n", u"x = 1and 2\n", u"x = 1in [1]\n", u"x = 1is 1\n",
    u"x = 1not in [1]\n", u"x = 1 if 1else 2\n", u"x = [0x1for x in []]\n", u"x = 0b1if 1 else 0\n",
    u"x = 0o7or 1\n", u"x = 1.5if 1 else 0\n", u"x = 1e5if 1 else 0\n", u"x = 1jif 1 else 0\n",
    u"x = 0xfor_\n", u"x = 1.e5\n", u"x = 1..real\n", u"x = 1 .real\n",
    u"x = " + u"1" * 4300 + u"\n", u"x = " + u"1" * 4301 + u"\n", u"x = " + u"0" * 5000 + u"\n",
    u"x = 0x" + u"f" * 5000 + u"\n", u"x = " + u"1" * 5000 + u"j\n", u"x = " + u"1" * 5000 + u".0\n",
    u"x = " + u"1" * 5000 + u"e0\n",
]) + _named("ellipsis", [
    u"x[...]\n", u"x[. . .]\n", u"x[.. .]\n", u"x[. ..]\n", u"x[1, ...]\n", u"x[1, . . .]\n",
    u"x[\n...]\n", u"x[.\\\n..]\n",
]) + _named("tabs", [
    u"if 1:\n\tx = 1\n        y = 2\n", u"if 1:\n        x = 1\n\ty = 2\n", u"if 1:\n\tx = 1\n\ty = 2\n",
    u"if 1:\n    \tx = 1\n\ty = 2\n", u"if 1:\n \tx = 1\n\ty = 2\n", u"if 1:\n\t x = 1\n\t y = 2\n",
    u"if 1:\n\tif 1:\n\t\tx = 1\n\t        y = 2\n", u"if 1:\n\tx = 1\nif 1:\n        y = 2\n",
    u"if 1:\n\tif 1:\n\t\tx = 1\n        y = 2\n", u"if 1:\n  \x0c\tx = 1\n\ty = 2\n",
    u"if 1:\n\x0c\tx = 1\n        y = 2\n", u"if 1:\n\tx = (1,\n        2)\n",
    u"if 1:\n\tx = 1\n        # comment\n\ty = 2\n", u"if 1:\n\tx = 1 \\\n        + 2\n",
    u"# vim: set ts=4 :\nif 1:\n\tx = 1\n    y = 2\n", u"if 1:\n\tx = 1\n\n        \n\ty = 2\n",
]) + _named("newline", [
    b"x = 1\\\n", b"x = 1 + \\\n2\n", b"x = 1\r\ny = 2\r\n", b"x = 1\ry = 2\r", b"x = 1\x0c\n",
    b"\x0cx = 1\n", b"if 1:\n    x = 1\n\x0c    y = 2\n", b"x = (1,\r\n 2)\r\n", b"# c\\\nx = 1\n",
    b"x = 1\n\\\n", b"x = 1 \\\n\n", b"x = '''a\r\nb'''\r\n",
])

ENCODING = _named("coding", [
    b"# coding: latin-1\nx = '\xe9'\n", b"# coding: cp1252\nx = '\x93'\n", b"# coding: utf-8\nx = '\xc3\xa9'\n",
    b"# coding: euc-jp\nx = '\xa4\xa2'\n", b"# coding: shift_jis\nx = '\x95\x5c'\n", b"# coding: gbk\nx = '\xc4\xe3'\n",
    b"# coding: big5\nx = '\xa4\xa4'\n", b"# coding: koi8-r\nx = '\xc1'\n", b"# coding: mac-roman\nx = '\x8e'\n",
    b"# coding: palmos\nx = '\x9b'\n", b"# coding: rot13\nk = 1\n", b"# coding: rot-13\nk = 1\n",
    b"# coding: utf-7\nx = '+AOk-'\n", b"# coding: utf-7\nx = 1\n", b"# coding: hz\nx = '~{<:~}'\n",
    b"# coding: unicode_escape\nx = '\\u00e9'\n", b"# coding: unicode_escape\nx = 1\n",
    b"# coding: unicode-escape\nx = '\\ud800'\n", b"# coding: raw_unicode_escape\nx = 1\n",
    b"# coding: unicode_internal\nx = 1\n", b"# coding: idna\nx = 1\n", b"# coding: punycode\nx = 1\n",
    b"# coding: base64\nx = 1\n", b"# coding: hex\nx = 1\n", b"# coding: zlib\nx = 1\n", b"# coding: uu\nx = 1\n",
    b"# coding: string_escape\nx = 1\n", b"# coding: cp65001\nx = 1\n", b"# coding: mbcs\nx = 1\n",
    b"# coding: utf8\nx = 1\n", b"# coding: UTF-8\nx = 1\n", b"# coding: utf-8-sig\nx = 1\n",
    b"# coding: utf_8_sig\nx = 1\n", b"# coding: latin.1\nx = 1\n", b"# coding: latin_1\nx = 1\n",
    b"# coding: iso8859_15\nx = 1\n", b"# coding: 8859\nx = 1\n", b"# coding: cp037\nx = 1\n",
    b"# coding: ascii\nx = 1\n", b"# coding: us-ascii\nx = 1\n", b"# coding: utf-16\nx = 1\n",
    b"# coding: utf-32\nx = 1\n", b"# coding: tis260\nx = 1\n", b"# coding: hp_roman8\nx = 1\n",
    b"# coding: cp1125\nx = 1\n", b"# coding: kz1048\nx = 1\n", b"# coding: cp273\nx = 1\n",
    b"# coding: koi8_t\nx = 1\n", b"# coding: oem\nx = 1\n", b"# coding: johab\nx = 1\n",
    b"# coding: utf-8\nx = '\xed\xa0\x80'\n", b"x = '\xed\xa0\x80'\n", b"x = '\xe9'\n", b"x = '\xc3\xa9'\n",
    b"# \xe9\nx = 1\n", b"x = 1\n# coding: latin-1\ny = '\xe9'\n", b"#!/usr/bin/python\n# coding: latin-1\nx = '\xe9'\n",
    b"\xef\xbb\xbfx = '\xc3\xa9'\n", b"\xef\xbb\xbf# coding: utf-8\nx = 1\n", b"x = '\xf0\x80\x80\x80'\n",
    b"x = '\xc0\xaf'\n", b"x = '\xf4\x90\x80\x80'\n", b"# coding: utf-8\nx = '\xc0\xaf'\n",
    b"# vim: set fileencoding=latin-1 :\nx = '\xe9'\n", b"# -*- coding: iso-8859-1-unix -*-\nx = '\xe9'\n",
    b"# coding: utf-8-unix\nx = 1\n", b"# coding=latin-1\nx = '\xe9'\n", b"#coding:latin-1\nx = '\xe9'\n",
    b"x = 1 # coding: latin-1\ny = '\xe9'\n", b"\n# coding: latin-1\nx = '\xe9'\n", b"\n\n# coding: latin-1\nx = '\xe9'\n",
    b"# coding: latin-1\n# coding: utf-8\nx = 1\n", b"# coding: utf-7\nx = '+2D3cAA-'\n",
    b"# coding: euc_jis_2004\nx = 1\n", b"# coding: iso2022_jp\nx = 1\n", b"# coding: ptcp154\nx = 1\n",
])

KEYWORD = _named("keyword", [
    u"True = 1\n", u"False = 0\n", u"x.True\n", u"x.True = 1\n", u"def True(): pass\n", u"class False: pass\n",
    u"def f(True): pass\n", u"lambda True: 1\n", u"f(True=1)\n", u"import True\n", u"from x import True\n",
    u"from True import x\n", u"import x as True\n", u"global True\n", u"for True in x: pass\n",
    u"with x as True: pass\n", u"try: pass\nexcept E as True: pass\n", u"del True\n", u"True += 1\n",
    u"[True for True in x]\n", u"def f(x=True): pass\n", u"x = True\n", u"x = None\n", u"x.None\n",
    u"f(None=1)\n", u"import x.True\n", u"@x.True\ndef f(): pass\n", u"def f(*True): pass\n", u"def f(**True): pass\n",
    u"nonlocal = 1\n", u"x = nonlocal\n", u"nonlocal.x\n", u"def nonlocal(): pass\n", u"x.nonlocal\n",
    u"nonlocal\n", u"f(nonlocal=1)\n",
    u"async = 1\n", u"await = 1\n", u"x.async\n", u"def async(): pass\n", u"def f(async=1): pass\n",
    u"f(async=1)\n", u"import async\n", u"print(await)\n", u"x = await\n", u"x.await\n", u"async(1)\n",
    u"__peg_parser__ = 1\n", u"x = __peg_parser__\n", u"x.__peg_parser__\n",
    u"__debug__ = 1\n", u"def __debug__(): pass\n", u"def f(__debug__): pass\n", u"f(__debug__=1)\n",
    u"x.__debug__ = 1\n", u"x.__debug__\n", u"import __debug__\n", u"import x as __debug__\n",
    u"from x import y as __debug__\n", u"for __debug__ in x: pass\n", u"class __debug__: pass\n",
    u"del __debug__\n", u"global __debug__\n", u"with x as __debug__: pass\n", u"lambda __debug__: 0\n",
    u"try: pass\nexcept E as __debug__: pass\n", u"__debug__ += 1\n", u"[__debug__ for __debug__ in x]\n",
    u"(__debug__ for __debug__ in x)\n", u"def f(*__debug__): pass\n", u"x = __debug__\n", u"del x.__debug__\n",
    u"x.__debug__ += 1\n", u"def f((__debug__, b)): pass\n", u"import __debug__.x\n",
    u"match = 1\n", u"case = 1\n", u"type = 1\n", u"_ = 1\n", u"match(x)\n", u"match[x]\n", u"match -1\n",
    u"match * x\n", u"lazy = 1\n", u"lazy(x)\n", u"print = 1\n", u"exec(x)\n", u"x.print\n", u"x.exec\n",
])

GRAMMAR = _named("tuple_param", [
    u"def f(a, (b, c)): pass\n", u"def f((a)): pass\n", u"lambda (a, b): 0\n", u"lambda (a): 0\n",
    u"def f((a, b)=(1, 2)): pass\n", u"def f(a, (b,)): pass\n",
]) + _named("listcomp", [
    u"[x for x in 1, 2]\n", u"[x for x in 1,]\n", u"[x for x in lambda: 1]\n", u"[x for x in y if lambda: 1]\n",
    u"(x for x in y if lambda: 1)\n", u"{x for x in y if lambda: 1}\n", u"{x: 1 for x in y if lambda: 1}\n",
    u"[x for x in y for z in 1, 2]\n", u"[x for x in y if a if b]\n", u"[x for x in y if a for z in b]\n",
    u"[x for x in lambda: 1, 2]\n", u"[x for x in y if lambda: 1 if 2 else 3]\n", u"[x for x in (1, 2)]\n",
    u"[x for x in y if (lambda: 1)]\n",
]) + _named("except_as", [
    u"try: pass\nexcept E as e.x: pass\n", u"try: pass\nexcept E as x[0]: pass\n",
    u"try: pass\nexcept E as (a, b): pass\n", u"try: pass\nexcept E as e: pass\n",
    u"try: pass\nexcept (A, B) as e: pass\n", u"try: pass\nexcept E, e.x: pass\n",
]) + _named("genexp_arg", [
    u"f(x for x in y,)\n", u"f(x for x in y, *a)\n", u"f(x for x in y, **k)\n", u"f(x for x in y)\n",
    u"f((x for x in y),)\n", u"f(x for x in y, *a, **k)\n",
]) + _named("keyword_arg", [
    u"f((a)=1)\n", u"f(((a))=1)\n", u"f(a=1)\n", u"f(a=1, *b)\n", u"f(*a, **k)\n", u"f(a, *b, **k)\n",
]) + _named("barry", [
    u"from __future__ import barry_as_FLUFL\nx = 1 <> 2\n", u"from __future__ import barry_as_FLUFL\nx = 1 != 2\n",
    u"from __future__ import barry_as_FLUFL\nx = 1\n",
]) + _named("many_args", [
    u"def f(%s): pass\n" % u", ".join(u"a%d" % i for i in range(256)),
    u"def f(%s): pass\n" % u", ".join(u"a%d" % i for i in range(255)),
    u"lambda %s: 0\n" % u", ".join(u"a%d" % i for i in range(256)),
    u"def f(%s, *b): pass\n" % u", ".join(u"a%d" % i for i in range(255)),
    u"f(%s)\n" % u", ".join(u"a%d" % i for i in range(255)),
    u"f(%s, *b)\n" % u", ".join(u"a%d" % i for i in range(255)),
    u"f(%s)\n" % u", ".join(u"a%d=1" % i for i in range(255)),
]) + _named("misc", [
    u"print >>f, x\n", u"print\n", u"exec(x, y)\n", u"x = `1`\n", u"x = 1 <> 2\n", u"raise E, v\n",
    u"from .... import x\n", u"from . import x\n", u"x = {1: 2, 3: 4}\n", u"x = {1, 2}\n",
    u"class C(): pass\n", u"class C(object,): pass\n", u"x = (yield)\n", u"assert x, y\n",
    u"x = 1; y = 2;\n", u"if x: pass\nelif y: pass\nelse: pass\n", u"while 1: break\nelse: pass\n",
    u"with a as b, c as d: pass\n", u"with a, b: pass\n", u"x = [1, 2,]\n", u"x = lambda *a, **k: 0\n",
    u"def f(a, b=1, *c, **d): pass\n", u"x = a if b else c\n", u"x = not not a\n", u"x = a ** -b\n",
    u"x = ~-+a\n", u"x = a[1:2:3]\n", u"x = a[::]\n", u"x = a[:, 1]\n", u"del a, b[0], c.d\n",
    u"del (a), [b]\n", u"x = y = z\n", u"x += 1\n", u"x **= 2\n", u"a, b = c\n", u"[a, b] = c\n",
    u"(a, b), c = d\n", u"for (a, b) in c: pass\n", u"for a, in b: pass\n", u"x = (a for b in c for d in e)\n",
    u"def f():\n    return\n", u"def f():\n    yield\n", u"def f():\n    x = yield 1\n",
    u"@d\ndef f(): pass\n", u"@d.e(1)\nclass C: pass\n", u"global a, b\n", u"import a.b.c as d\n",
    u"from a import (b, c,)\n", u"from a import *\n", u"exec 'x'\n", u"exec 'x' in d\n",
    u"x = 'a' 'b'\n", u"x = u'a' 'b'\n", u"x = 1e10\n", u"x = 10L\n", u"x = 0777\n",
    u"print 'x',\n", u"print >>f\n",
])

COMPILE = _named("outside", [
    u"return 1\n", u"class C:\n    return 1\n", u"yield 1\n", u"class C:\n    yield 1\n", u"break\n",
    u"continue\n", u"if 1:\n    break\n", u"while 1:\n    def f():\n        break\n",
    u"while 1:\n    class C:\n        continue\n", u"x = [(yield) for y in z]\n", u"x = lambda: (yield)\n",
    u"def f():\n    class C:\n        yield 1\n", u"while 1:\n    try:\n        pass\n    finally:\n        continue\n",
    u"while 1:\n    try:\n        pass\n    finally:\n        break\n",
    u"for x in y:\n    try:\n        pass\n    finally:\n        if x:\n            continue\n",
    u"while 1:\n    try:\n        pass\n    finally:\n        for z in y:\n            continue\n",
    u"while 1:\n    try:\n        pass\n    finally:\n        def f():\n            return 1\n",
    u"while 1:\n    try:\n        continue\n    finally:\n        pass\n",
    u"while 1:\n    try:\n        pass\n    except:\n        continue\n",
    u"while 1:\n    with x:\n        continue\n",
]) + _named("except_order", [
    u"try: pass\nexcept: pass\nexcept E: pass\n", u"try: pass\nexcept E: pass\nexcept: pass\n",
    u"try: pass\nexcept: pass\nelse: pass\n",
]) + _named("blocks", [
    u"".join(u"    " * i + u"for x%d in y:\n" % i for i in range(20)) + u"    " * 20 + u"pass\n",
    u"".join(u"    " * i + u"for x%d in y:\n" % i for i in range(21)) + u"    " * 21 + u"pass\n",
    u"".join(u"    " * i + u"while 1:\n" for i in range(21)) + u"    " * 21 + u"pass\n",
    u"".join(u"    " * i + u"try:\n" for i in range(21)) + u"    " * 21 + u"pass\n" +
    u"".join(u"    " * i + u"finally:\n" + u"    " * (i + 1) + u"pass\n" for i in reversed(range(21))),
    u"".join(u"    " * i + u"with x:\n" for i in range(21)) + u"    " * 21 + u"pass\n",
    u"".join(u"    " * i + u"if x:\n" for i in range(50)) + u"    " * 50 + u"pass\n",
    u"".join(u"    " * i + u"def f():\n" for i in range(50)) + u"    " * 50 + u"pass\n",
    u"".join(u"    " * i + u"for x%d in y:\n" % i for i in range(10)) +
    u"".join(u"    " * (10 + i) + u"try:\n" for i in range(11)) + u"    " * 21 + u"pass\n" +
    u"".join(u"    " * (10 + i) + u"except: pass\n" for i in reversed(range(11))),
    u"".join(u"    " * i + u"try:\n" for i in range(20)) + u"    " * 20 + u"pass\n" +
    u"".join(u"    " * i + u"except: pass\n" for i in reversed(range(20))),
]) + _named("args", [
    u"def f(a, a): pass\n", u"lambda a, a: 0\n", u"def f(a, *a): pass\n", u"def f(a, **a): pass\n",
    u"def f(*a, **a): pass\n", u"def f(a, (b, a)): pass\n", u"def f(a):\n    global a\n",
    u"def f(a):\n    def g(a, a): pass\n", u"class C:\n    def f(self, self): pass\n",
]) + _named("star_import", [
    u"def f():\n    from os import *\n", u"class C:\n    from os import *\n",
    u"def f():\n    class C:\n        from os import *\n", u"from os import *\n",
    u"if 1:\n    from os import *\n", u"try:\n    from os import *\nexcept: pass\n",
    u"def f():\n    from os import path\n",
]) + _named("global", [
    u"x = 1\nglobal x\n", u"def f():\n    x = 1\n    global x\n", u"def f():\n    print(x)\n    global x\n",
    u"def f():\n    global x\n    x = 1\n", u"def f():\n    for x in y: pass\n    global x\n",
    u"def f():\n    import x\n    global x\n", u"def f():\n    def x(): pass\n    global x\n",
    u"def f():\n    del x\n    global x\n", u"def f():\n    global x\n    global x\n",
    u"class C:\n    x = 1\n    global x\n", u"def f():\n    [x for x in y]\n    global x\n",
    u"def f():\n    (x for x in y)\n    global x\n", u"def f():\n    x += 1\n    global x\n",
    u"def f():\n    with a as x: pass\n    global x\n", u"def f():\n    try: pass\n    except E, x: pass\n    global x\n",
    u"def f():\n    def g():\n        x = 1\n    global x\n", u"def f():\n    lambda: x\n    global x\n",
    u"x\nglobal x\n", u"def f():\n    exec 'x'\n    global x\n", u"def f():\n    if 0:\n        x = 1\n    global x\n",
    u"def f():\n    global x\n    def g():\n        x = 1\n",
]) + _named("future", [
    u"x = 1\nfrom __future__ import division\n", u"'''doc'''\nfrom __future__ import division\n",
    u"'''doc'''\n'''doc2'''\nfrom __future__ import division\n", u"from __future__ import braces\n",
    u"from __future__ import nonexistent\n", u"from __future__ import annotations\n",
    u"from __future__ import generator_stop\n", u"from __future__ import barry_as_FLUFL\n",
    u"def f():\n    from __future__ import division\n", u"from __future__ import division\nfrom __future__ import print_function\n",
    u"from __future__ import (division)\n", u"from __future__ import division as d\n",
    u"from __future__ import division, absolute_import, nested_scopes, generators, with_statement\n",
    u"import os\nfrom __future__ import division\n", u"from __future__ import division; x = 1\n",
    u"x = 1; from __future__ import division\n", u"if 1:\n    from __future__ import division\n",
    u"from __future__ import *\n", u"from . import __future__\n", u"from __future__.x import y\n",
    u"from __future__ import unicode_literals, print_function\n", u"b'''doc'''\nfrom __future__ import division\n",
    u"u'''doc'''\nfrom __future__ import division\n", u"r'''doc'''\nfrom __future__ import division\n",
    u"'a' 'b'\nfrom __future__ import division\n", u"('doc')\nfrom __future__ import division\n",
    u"\n\n# c\n'''doc'''\n\nfrom __future__ import division\n",
]) + _named("yield_comp", [
    u"def f():\n    return [(yield x) for x in y]\n", u"def f():\n    return ((yield x) for x in y)\n",
    u"def f():\n    return {(yield x) for x in y}\n", u"def f():\n    return {(yield x): 1 for x in y}\n",
    u"def f():\n    return [lambda: (yield) for x in y]\n", u"def f():\n    return [x for x in (yield)]\n",
    u"def f():\n    return [x for x in y if (yield)]\n", u"def f():\n    return [x for x in y for z in (yield)]\n",
    u"def f():\n    return ((yield) for x in y)\n", u"def f():\n    return (x for x in (yield))\n",
    u"def f():\n    return {x: (yield) for x in y}\n",
]) + _named("misc_compile", [
    u"def f():\n    x = 1\n    del x\n    def g():\n        return x\n",
    u"def f():\n    yield 1\n    return 2\n", u"def f():\n    exec 'x'\n    def g():\n        return y\n",
    u"def f():\n    from os import *\n    def g():\n        return y\n",
    u"class C:\n    def f(self):\n        return __class__\n", u"def f():\n    super()\n",
    u"x = [i for i in range(3)]\nprint(i)\n", u"def f():\n    return x\n    x = 1\n",
    u"a, b, c = d\n", u"x = (1, 2)[0]\n", u"x = {}\nx[1] = 2\n",
])


def _nested(open_, close, inner, n):
    return u"x = " + open_ * n + inner + close * n + u"\n"


DEPTH = [
    ("parens-%d" % n, _nested(u"(", u")", u"1", n).encode("ascii")) for n in (50, 80, 86, 87, 88, 89, 90, 91, 92, 93, 94)
] + [
    ("lists-%d" % n, _nested(u"[", u"]", u"1", n).encode("ascii")) for n in (80, 87, 88, 89, 90, 92, 94)
] + [
    ("dicts-%d" % n, (u"x = " + u"{1: " * n + u"1" + u"}" * n + u"\n").encode("ascii")) for n in (80, 85, 86, 90, 93)
] + [
    ("tuples-%d" % n, _nested(u"(", u",)", u"1", n).encode("ascii")) for n in (80, 88, 92)
] + [
    ("calls-%d" % n, (u"x = " + u"f(" * n + u"1" + u")" * n + u"\n").encode("ascii")) for n in (80, 88, 92)
] + [
    ("not-%d" % n, (u"x = " + u"not " * n + u"1\n").encode("ascii")) for n in (100, 500, 900, 1000, 1400)
] + [
    ("neg-%d" % n, (u"x = " + u"-" * n + u"1\n").encode("ascii")) for n in (100, 500, 900, 1000, 1400)
] + [
    ("pow-%d" % n, (u"x = " + u"2 ** " * n + u"1\n").encode("ascii")) for n in (100, 300, 500, 700)
] + [
    ("lambda-%d" % n, (u"x = " + u"lambda: " * n + u"1\n").encode("ascii")) for n in (100, 300, 500, 700)
] + [
    ("ifelse-%d" % n, (u"x = " + u"1 if a else " * n + u"1\n").encode("ascii")) for n in (100, 500, 900, 1400)
] + [
    ("plus-%d" % n, (u"x = 1" + u" + 1" * n + u"\n").encode("ascii")) for n in (1000, 10000, 100000)
] + [
    ("and-%d" % n, (u"x = 1" + u" and 1" * n + u"\n").encode("ascii")) for n in (1000, 10000, 100000)
] + [
    ("cmp-%d" % n, (u"x = 1" + u" < 1" * n + u"\n").encode("ascii")) for n in (1000, 10000, 100000)
] + [
    ("attr-%d" % n, (u"x = a" + u".b" * n + u"\n").encode("ascii")) for n in (1000, 10000, 100000)
] + [
    ("callchain-%d" % n, (u"x = f" + u"()" * n + u"\n").encode("ascii")) for n in (1000, 10000, 100000)
] + [
    ("subscript-%d" % n, (u"x = a" + u"[0]" * n + u"\n").encode("ascii")) for n in (1000, 10000, 100000)
] + [
    ("strcat-%d" % n, (u"x = 'a'" + u" 'a'" * n + u"\n").encode("ascii")) for n in (1000, 10000, 100000)
] + [
    ("tuple-%d" % n, (u"x = 1" + u", 1" * n + u"\n").encode("ascii")) for n in (1000, 10000, 100000)
] + [
    ("statements-%d" % n, (u"x = 1\n" * n).encode("ascii")) for n in (10000, 100000)
] + [
    ("indent-%d" % n, (u"".join(u" " * i + u"if 1:\n" for i in range(n)) + u" " * n + u"pass\n").encode("ascii"))
    for n in (98, 99, 100)
] + [
    ("defs-%d" % n, (u"".join(u" " * i + u"def f():\n" for i in range(n)) + u" " * n + u"pass\n").encode("ascii"))
    for n in (98, 99)
]

CASES = LEXICAL + ENCODING + KEYWORD + GRAMMAR + COMPILE + DEPTH


# Second battery: the boundaries the first one showed, and the forms near them.
LEXICAL2 = _named("escape2", [
    u"x = b'\\777'\n", u"x = b'\\400'\n", u"x = '\\400'\n", u"x = '\\ud800'\n", u"x = '\\U0000d800'\n",
    u"x = '\\N{cjk unified ideograph-4e00}'\n", u"x = '\\N{CJK UNIFIED IDEOGRAPH-4e00}'\n",
    u"x = '\\N{CJK UNIFIED IDEOGRAPH-04E00}'\n", u"x = '\\N{hangul syllable ga}'\n",
    u"x = '\\N{HANGUL SYLLABLE G}'\n", u"x = '\\N{HANGUL SYLLABLE KAG}'\n", u"x = '\\N{NULL}'\n",
    u"x = '\\N{null}'\n", u"x = '\\N{ LATIN SMALL LETTER A}'\n", u"x = '\\N{LATIN SMALL LETTER A }'\n",
    u"x = '\\N{LATIN  SMALL LETTER A}'\n", u"x = '\\N{KHITAN SMALL SCRIPT CHARACTER-18B00}'\n",
    u"x = '\\N{NUSHU CHARACTER-1B170}'\n", u"x = '\\N{CJK COMPATIBILITY IDEOGRAPH-F900}'\n",
    u"x = '\\N{EGYPTIAN HIEROGLYPH-13460}'\n", u"x = '\\N{TANGUT COMPONENT-001}'\n",
    u"x = '\\N{CJK UNIFIED IDEOGRAPH-9FFF}'\n", u"x = '\\N{CJK UNIFIED IDEOGRAPH-31350}'\n",
    u"x = '\\N{CHARACTER TABULATION}'\n", u"x = '\\N{latin capital letter a with macron and grave}'\n",
    u"x = '\\N{tangut ideograph-17000}'\n", u"x = '\\N{DIGIT ONE}\\u0031\\U00000031'\n",
    u"x = '\\N{SNOWMAN}' 'a' b'b'\n", u"x = 'a' '\\u12'\n", u"x = '\\\\u12'\n", u"x = r'\\u12'\n",
    u"x = '\\\n\\u12'\n", u"x = '%s\\u12'\n" % (u"a" * 300),
]) + _named("number2", [
    u"x = 1" + u"0" * 4300 + u"\n", u"x = -" + u"1" * 4301 + u"\n", u"x = 0" + u"7" * 4301 + u"\n",
    u"x = " + u"9" * 4300 + u".\n", u"x = " + u"1" * 4300 + u"\nx = " + u"2" * 4301 + u"\n",
]) + _named("newline2", [
    b"x = 1\\", b"x = 1\\\n   ", b"x = 1\\\n#c", b"x = 1\\\r\n", b"if 1:\n  x = 1\\\n", b"x = 1\\\r",
    b"x = (1,\\\n", b"# c\\", b"x = 1\n\\", b"x = 1\\\n\\\n", b"x = 1 \\\n\x0c", b"\\\n", b"x = 1\\\n\n",
    b"x = '''a\\\n'''\\\n",
]) + _named("utf8", [
    b"x = 1\n# \xe9\n", b"x = 1 # \xe9\n", b"x = 1\n\n\n# \xe9\n", b"\xef\xbb\xbf# \xe9\nx = 1\n",
    b"# coding: utf-8\n# \xe9\n", b"'''\xe9'''\n", b"x = u'\xe9'\n", b"x = b'\xe9'\n", b"# \xed\xa0\x80\n",
    b"# \xc0\xaf\n", b"#!/usr/bin/env python\n# \xe9\n", b"# \xe9\n# coding: latin-1\nx = '\xe9'\n",
    b"x = r'\xe9'\n", b"# \xf4\x90\x80\x80\n", b"x = '\xc3\xa9' # \xe9\n", b"if 1:\n    pass\n    # \xe9\n",
    b"x = 1\n\n# \xe9", b"# \xe9\n" * 3,
]) + _named("coding2", [
    b"# coding: euc_kr\nx = '\xb0\xa1'\n", b"# coding: cp932\nx = '\x82\xa0'\n",
    b"# coding: gb18030\nx = '\x81\x30\x81\x30'\n", b"# coding: big5hkscs\nx = '\x88\x62\x88\x64'\n",
    b"# coding: iso2022_jp\nx = '\x1b$B$\"\x1b(B'\n", b"# coding: utf-7\nx = '+AGEAYgBj-'\n",
    b"# coding: raw_unicode_escape\nx = '\\u00e9'\n", b"# coding: mac-latin2\nx = 1\n",
    b"# coding: cp1006\nx = '\xa1'\n", b"# coding: utf-8\n# coding: latin-1\nx = '\xc3\xa9'\n",
    b"#!/bin/sh\n# coding: rot13\nk = 1\n", b"# coding: unicode_escape\nx = '\\N{SNOWMAN}'\n",
    b"# coding: unicode_escape\nx = 1 # \\xe9\n", b"# coding: utf-7\nx = '+2D3cAA'\n",
    b"# coding: hz\nx = '~{<:~}~'\n", b"# coding: latin-1\nx = b'\xe9'\n", b"# coding: latin-1\nx = u'\xe9'\n",
    b"# coding: cp1252\n# \x81\nx = 1\n", b"# coding: ascii\n# \xe9\nx = 1\n",
]) + _named("tabs2", [
    b"# vim:ts=4\nif 1:\n\tx = 1\n\ty = 2\n", b"# vim:ts=4\nif 1:\n    x = 1\n\ty = 2\n",
    b"# tab-width: 4\nif 1:\n\tif 1:\n\t\tx = 1\n\t    y = 2\n", b"# vim:ts=4\nif 1:\n\tx = 1\n",
    b"# vim:ts=4\nif 1:\n\tif 1:\n\t\tx = 1\n    y = 2\n", b"# :ts=2\nif 1:\n\tx = 1\n  y = 2\n",
    b"if 1:\n\x0c    x = 1\n\ty = 2\n", b"if 1:\n    x = 1\n\x0c\ty = 2\n",
])

KEYWORD2 = _named("keyword2", [
    u"(True) = 1\n", u"True, x = 1, 2\n", u"[True] = [1]\n", u"@True\ndef f(): pass\n", u"@None\ndef f(): pass\n",
    u"@False.x\ndef f(): pass\n", u"@async\ndef f(): pass\n", u"def f(x, async): pass\n", u"import __peg_parser__\n",
    u"x = True.real\n", u"None.x\n", u"del x.True\n", u"x.False = 1\n", u"print >>True, x\n",
    u"class C(True): pass\n", u"del (__debug__)\n", u"del [__debug__]\n", u"del a, __debug__\n",
    u"def f():\n    del __debug__\n", u"del x.y.__debug__\n", u"del (x.__debug__)\n", u"import a, __debug__.b\n",
    u"from __debug__ import x\n", u"from x import __debug__\n", u"import __debug__.x as y\n", u"__debug__.x = 1\n",
    u"del __debug__.x\n", u"print __debug__\n", u"async.x\n", u"x.await = 1\n", u"def await(): pass\n",
    u"class async: pass\n", u"for await in x: pass\n", u"lambda async: 0\n", u"global async\n", u"from async import x\n",
    u"from x import async\n", u"try: pass\nexcept E, async: pass\n", u"x = [async for async in y]\n",
    u"@x.async\ndef f(): pass\n", u"def f(**await): pass\n", u"x = {nonlocal: 1}\n", u"def f(a=nonlocal): pass\n",
    u"x = None.y\n", u"x.None = 1\n", u"def None(): pass\n", u"x = f(True)\n", u"x = True if False else None\n",
    u"del True.x\n", u"True.x = 1\n", u"x = [True for x in y]\n", u"x = {True: False}\n",
])

GRAMMAR2 = _named("print_stmt", [
    u"print (x)\n", u"print (a), b\n", u"print -1\n", u"print [1]\n", u"print [x for x in y]\n",
    u"print (x) if y else z\n", u"print >>f, x,\n", u"print ~x\n", u"print not x\n", u"print x,\n",
    u"print (a) % b, c\n", u"print (x for x in y)\n", u"print (a)(b)\n", u"def f():\n    print (yield)\n",
    u"print ()\n", u"print (a, b)\n", u"print (a, b),\n", u"print -x, -y\n", u"print +x\n", u"print [a][b]\n",
    u"print .5\n", u"print 1\n", u"print 'a' % b\n", u"print (a) in b\n", u"print (a) not in b\n",
    u"print (a) is b\n", u"print (a) and b\n", u"print (a) or b\n", u"print (1).real\n", u"print (a)[1:2]\n",
    u"print (a) ** 2\n", u"print (a) << 1\n", u"print >> f\n", u"print [x for x in 1, 2]\n", u"print (a) <> b\n",
    u"print `a`\n", u"print (a), `b`\n", u"print (lambda: 1)\n", u"print lambda: 1\n", u"print (x for x in y), z\n",
    u"print (a) if b else c, d\n", u"print -1 if x else 2\n", u"print [1], 2\n", u"print (a); print\n",
    u"if 1: print (x)\n", u"print (a)\\\n    , b\n", u"print 0777\n", u"print (0777)\n", u"print (a=1)\n",
    u"print (*a)\n", u"print (x for x in y, 1)\n", u"print (x for x in y,)\n", u"print >>f, (x for x in y)\n",
]) + _named("exec_stmt", [
    u"exec (x)\n", u"exec (x) in d\n", u"exec (x) in d, e\n", u"exec [x]\n", u"exec -x\n", u"exec x\n",
    u"exec (x)[0]\n", u"exec(x) in d\n", u"exec (x) + y in d\n", u"exec ('x')\n", u"exec ~x\n",
    u"exec (x), y\n", u"exec (x) if y else z\n", u"def f():\n    exec (x)\n", u"exec (x for x in y)\n",
    u"exec `x`\n", u"exec (a)(b) in c\n",
]) + _named("grammar2", [
    u"class C(%s): pass\n" % u", ".join(u"a%d" % i for i in range(256)),
    u"@d(%s)\ndef f(): pass\n" % u", ".join(u"a%d" % i for i in range(256)),
    u"f(%s, **k)\n" % u", ".join(u"a%d" % i for i in range(255)),
    u"f(%s, *a)\n" % u", ".join(u"a%d=1" % i for i in range(255)),
    u"def f(%s): pass\n" % u", ".join(u"a%d=0" % i for i in range(256)),
    u"def f(%s, **k): pass\n" % u", ".join(u"a%d" % i for i in range(255)),
    u"lambda %s, *a: 0\n" % u", ".join(u"a%d" % i for i in range(255)),
    u"f(%s, *a, **k)\n" % u", ".join(u"a%d" % i for i in range(254)),
    u"try: pass\nexcept E as (a): pass\n", u"[x for x in y if lambda: 1 for z in w]\n",
    u"@d(x for x in y,)\ndef f(): pass\n", u"f(a)(x for x in y,)\n", u"class C(object): x = [y for y in 1, 2]\n",
    u"x = [y for y in 1, 2 if y]\n", u"x = [y for y in lambda: 1 if y]\n", u"x = (y for y in z if lambda: 1)\n",
    u"x = [y for y in z if lambda x: x]\n", u"x = [y for y in z if lambda: (yield)]\n",
    u"f(x for x in y)(z for z in w,)\n", u"f((x for x in y), *a)\n", u"f(x for x in y if z)\n",
    u"from __future__ import barry_as_FLUFL\nx = 1 <> 2 != 3\n", u"from __future__ import barry_as_FLUFL\nx = 1 <> 2\ny = 3 <> 4\n",
    u"'''doc'''\nfrom __future__ import barry_as_FLUFL\nx = 1 <> 2\n",
    u"from __future__ import barry_as_FLUFL, division\nx = 1 <> 2\n",
    u"def f():\n    from __future__ import barry_as_FLUFL\nx = 1 <> 2\n",
    u"x[...]\nx[1:2, ...]\n", u"x[..., 1]\n", u"x[1:2, . . .]\n", u"x[(...)]\n",
    u"raise E, v, t\n", u"raise E, (a, b)\n", u"x = 0777L\n", u"x = 0xffL\n", u"x = 10l\n", u"x = 00\n", u"x = 0L\n",
    u"x = `a` + `b`\n", u"x = 1 <> 2 <> 3\n",
])

COMPILE2 = _named("compile2", [
    u"for x in y: pass\nelse: break\n", u"while 1: pass\nelse: continue\n",
    u"for x in y:\n    try: pass\n    finally:\n        def f(): continue\n",
    u"while 1:\n    try: pass\n    finally:\n        try: continue\n        except: pass\n",
    u"while 1:\n    try: pass\n    finally:\n        with x: continue\n",
    u"while 1:\n    try: pass\n    except: pass\n    finally: continue\n",
    u"while 1:\n    try: pass\n    finally:\n        try: pass\n        finally: continue\n",
    u"while 1:\n    try: pass\n    finally:\n        try: pass\n        except: continue\n",
    u"while 1:\n    try: pass\n    finally:\n        if x:\n            pass\n        else:\n            continue\n",
    u"while 1:\n    try:\n        pass\n    finally:\n        while 1:\n            try: pass\n            finally: continue\n",
    u"def f():\n    [x for x in [(yield)]]\n", u"def f():\n    [[(yield) for a in b] for c in d]\n",
    u"def f():\n    {k: v for k, v in (yield)}\n", u"def f():\n    (x for x in y if (yield))\n",
    u"x = lambda: [(yield) for x in y]\n", u"x = [x for x in (yield)]\n", u"x = ((yield) for x in y)\n",
    u"class C:\n    x = [(yield) for x in y]\n", u"def f():\n    class C:\n        x = ((yield) for y in z)\n",
    u"x = {(yield) for y in z}\n", u"def f():\n    return [(yield) for a in b][0]\n",
    u"if 0:\n    return 1\n", u"if 0:\n    break\n", u"if 0:\n    continue\n", u"while 0:\n    break\nelse:\n    break\n",
    u"while 1:\n    try: pass\n    finally:\n        if 0:\n            continue\n",
    u"if False:\n    return 1\n", u"if None:\n    return 1\n", u"if '':\n    return 1\n", u"if ():\n    return 1\n",
    u"if 1 - 1:\n    return 1\n", u"if not 1:\n    return 1\n", u"if __debug__:\n    pass\nelse:\n    return 1\n",
    u"if not __debug__:\n    return 1\n", u"if 0:\n    pass\nelif 1:\n    return 1\n", u"if 1:\n    pass\nelse:\n    return 1\n",
    u"while 0:\n    return 1\n", u"while False:\n    return 1\n", u"if 0:\n    yield 1\n", u"if 0:\n    x = 1\n    global x\n",
    u"if 0:\n    from __future__ import division\n", u"x = 1\nif 0:\n    from __future__ import division\n",
    u"if 0:\n    try: pass\n    except: pass\n    except E: pass\n", u"if 0:\n    def f(a, a): pass\n",
    u"if 0:\n    class C:\n        from os import *\n", u"if 0:\n    x = [(yield) for y in z]\n",
    u"if 0:\n    f(x for x in y, *a)\n", u"if 0.0:\n    return 1\n", u"if 0j:\n    return 1\n", u"if b'':\n    return 1\n",
    u"if u'':\n    return 1\n", u"if (0):\n    return 1\n", u"if 0 if 1 else 0:\n    return 1\n", u"if [] :\n    return 1\n",
    u"try: pass\nexcept: pass\nexcept E: pass\nelse: pass\n", u"try: pass\nexcept: pass\nexcept: pass\n",
    u"def f(a, b, a=1): pass\n", u"lambda a, *a: 0\n", u"def f(*a):\n    global a\n", u"def f(**a):\n    global a\n",
    u"def f():\n    def g():\n        from os import *\n", u"def f():\n    exec 'x'\n",
    u"def f():\n    [a for a in x]\n    global x\n", u"def f():\n    (a for a in x)\n    global x\n",
    u"def f():\n    @x\n    def g(): pass\n    global x\n", u"def f():\n    class C(x): pass\n    global x\n",
    u"def f():\n    def g(a=x): pass\n    global x\n", u"def f():\n    lambda a=x: 0\n    global x\n",
    u"def f():\n    import x.y\n    global x\n", u"def f():\n    from m import x\n    global x\n",
    u"def f():\n    import m as x\n    global x\n", u"def f():\n    x.y = 1\n    global x\n",
    u"def f():\n    x[0] = 1\n    global x\n", u"def f():\n    del x[0]\n    global x\n",
    u"def f():\n    print >>x\n    global x\n", u"def f():\n    global x\n    x = 1\n    global x\n",
    u"def f():\n    try: pass\n    except E as x: pass\n    global x\n", u"def f():\n    class x: pass\n    global x\n",
    u"def f():\n    x = 1\n    def g():\n        global x\n", u"import x\nglobal x\n", u"import x.y\nglobal x\n",
    u"class C:\n    def x(self): pass\n    global x\n", u"a, x = 1, 2\nglobal x\n", u"def f():\n    x\n    global x\n",
    u"def f():\n    if 1:\n        x = 1\n    else:\n        global x\n", u"def f():\n    global x, y\n    y = 1\n    global y\n",
    u"def f():\n    for x in y: pass\n    else:\n        global x\n", u"def f():\n    [x for y in z]\n    global x\n",
    u"def f():\n    f(x=1)\n    global x\n", u"def f():\n    x.attr\n    global attr\n",
    u"def f():\n    import x as y\n    global y\n", u"from m import x\nglobal x\n", u"x += 1\nglobal x\n",
    u"from __future__ import division\n'''doc'''\nfrom __future__ import print_function\n",
    u"'''doc'''; from __future__ import division\n",
    u"from __future__ import division\nimport os\nfrom __future__ import print_function\n",
    u"from __future__ import division; from __future__ import print_function\n",
    u"from __future__ import division\ndef f():\n    from __future__ import division\n",
    u"x = 1\n'''doc'''\nfrom __future__ import division\n", u"'''doc'''\nfrom __future__ import annotations\n",
    u"from __future__ import absolute_import as a, division\n", u"from __future__ import nested_scopes, braces\n",
    u"import os; from __future__ import division\n", u"from __future__ import division; import os; from __future__ import print_function\n",
    u"from __future__ import (division,\n    print_function)\nfrom __future__ import with_statement\n",
    u"from __future__ import division\nclass C:\n    from __future__ import division\n",
    u"'''doc'''\n\n\n'''doc2'''\n", u"b'doc'\n'''x'''\nfrom __future__ import division\n",
    u"u'doc' b'x'\nfrom __future__ import division\n", u"from __future__ import unicode_literals\nb'doc'\n",
    u"from __future__ import division\nfrom __future__ import nonexistent\n",
])


def _blocks(kinds, inner):
    """Source nesting the kinds of block in order, with inner innermost."""
    heads = {
        "for": ([u"for x%d in y:"], []), "while": ([u"while x:"], []), "if": ([u"if x:"], []),
        "with": ([u"with x:"], []), "with2": ([u"with x, y:"], []),
        "try_e": ([u"try:"], [u"except: pass"]), "try_f": ([u"try:"], [u"finally: pass"]),
        "try_ef": ([u"try:"], [u"except: pass", u"finally: pass"]),
        "h": ([u"try: pass", u"except:"], []), "hn": ([u"try: pass", u"except E as e%d:"], []),
        "h_ef": ([u"try: pass", u"except:"], [u"finally: pass"]), "fin": ([u"try: pass", u"finally:"], []),
        "fin_ef": ([u"try: pass", u"except: pass", u"finally:"], []), "else_e": ([u"try: pass", u"except: pass", u"else:"], []),
        "else_for": ([u"for x%d in y: pass", u"else:"], []), "def": ([u"def f%d():"], []),
        "gen": ([u"def f%d():", u"    yield"], []),
    }
    lines = []
    for depth, kind in enumerate(kinds):
        head, tail = heads[kind]
        for i, text in enumerate(head):
            body = u"    " if kind == "gen" and i == 1 else u""
            lines.append(u"    " * depth + body.lstrip() + (text % depth if u"%d" in text else text))
        tail_lines = [u"    " * depth + t for t in tail]
        lines.append(tail_lines)
    out = []
    pending = []
    for item in lines:
        if isinstance(item, list):
            pending.append(item)
        else:
            out.append(item)
    out.append(u"    " * len(kinds) + inner)
    for tail in reversed(pending):
        out.extend(tail)
    return (u"\n".join(out) + u"\n").encode("ascii")


_BLOCK_KINDS = ("for", "while", "with", "with2", "try_e", "try_f", "try_ef", "h", "hn", "h_ef", "fin", "fin_ef",
                "else_e", "else_for")

BLOCKS2 = [
    ("blocks2-%s-%d" % (kind, n), _blocks([kind] * n, u"pass")) for kind in _BLOCK_KINDS for n in (10, 11, 19, 20, 21, 22)
] + [
    ("blocks2-gen-for-%d" % n, _blocks(["gen"] + ["for"] * n, u"pass")) for n in (19, 20, 21)
] + [
    ("blocks2-def-for-%d" % n, _blocks(["for"] * 10 + ["def"] + ["for"] * n, u"pass")) for n in (20, 21)
] + [
    ("blocks2-comp-%d" % n, _blocks(["for"] * n, u"x = [z for z in w]")) for n in (19, 20, 21)
] + [
    ("blocks2-comp-def-%d" % n, _blocks(["def"] + ["for"] * n, u"x = [z for z in w]")) for n in (19, 20, 21)
] + [
    ("blocks2-genexp-%d" % n, _blocks(["for"] * n, u"x = (z for z in w)")) for n in (20, 21)
] + [
    ("blocks2-dead-%d" % n, (u"if 0:\n" + _blocks(["for"] * n, u"pass").decode("ascii").replace(u"\n", u"\n    ")
                             .rstrip(u" ").replace(u"for", u"    for", 1)).encode("ascii")) for n in (21, 25)
] + [
    ("blocks2-mix-%d" % i, _blocks(kinds, u"pass")) for i, kinds in enumerate([
        ["for"] * 10 + ["try_e"] * 10, ["for"] * 10 + ["h"] * 5, ["for"] * 9 + ["h"] * 5, ["for"] * 11 + ["h"] * 5,
        ["for"] * 18 + ["h"], ["for"] * 19 + ["h"], ["for"] * 20 + ["h"], ["for"] * 18 + ["h_ef"], ["for"] * 17 + ["h_ef"],
        ["for"] * 19 + ["try_ef"], ["for"] * 18 + ["try_ef"], ["for"] * 19 + ["fin"], ["for"] * 20 + ["fin"],
        ["for"] * 19 + ["hn"], ["for"] * 18 + ["hn"], ["with2"] * 10, ["with2"] * 11, ["for"] * 19 + ["with2"],
        ["for"] * 19 + ["fin_ef"], ["for"] * 20 + ["fin_ef"], ["for"] * 20 + ["else_e"], ["for"] * 20 + ["else_for"],
    ])
] + [
    ("blocks2-ret-%d" % n, _blocks(["def"] + ["try_f"] * n, u"return 1")) for n in (19, 20, 21)
] + [
    ("blocks2-retfin-%d" % n, _blocks(["def"] + ["for"] * n + ["fin"], u"return 1")) for n in (18, 19, 20)
] + [
    ("blocks2-break-%d" % n, _blocks(["for"] * n + ["try_f"], u"break")) for n in (18, 19, 20)
]

CASES2 = LEXICAL2 + KEYWORD2 + GRAMMAR2 + COMPILE2 + BLOCKS2

ALL_CASES = CASES + CASES2
