# -*- coding: utf-8 -*-
import pytest

from py2scan.scanner import scan_source


def lines_of(rule, source):
    return [f.line for f in scan_source(u"m.py", source) if f.rule == rule]


def found(source):
    return [(f.line, f.rule) for f in scan_source(u"m.py", source)]


CASES = [
    ("PY3-PRINT", b"x = 1\nprint x\n", [2]),
    ("PY3-PRINT", b"print 'a'; print 'b'\n", [1, 1]),
    ("PY3-PRINT", b"print ('a',\n       'b')\n", [1]),
    ("PY3-PRINT", b"print >>sys.stderr, 'x'\n", [1]),
    ("PY3-PRINT", b"from __future__ import print_function\nprint('x')\n", []),

    ("PY3-EXEC-STMT", b"exec 'x = 1'\n", [1]),
    ("PY3-EXEC-STMT", b"exec code in ns\n", [1]),
    ("PY3-EXEC-STMT", b"x = 1\n", []),

    ("PY3-BACKTICK", b"x = `1` + `y`\n", [1, 1]),
    ("PY3-BACKTICK", b"x = (1,\n     `y`)\n", [2]),
    ("PY3-BACKTICK", b"x = repr(y)\ns = '`y`'  # `y`\n", []),

    ("PY3-NE-OP", b"if a <> b: pass\n", [1]),
    ("PY3-NE-OP", b"x = a <> b <> c\n", [1, 1]),
    ("PY3-NE-OP", b"x = (a\n     <> b)\n", [2]),
    ("PY3-NE-OP", b"x = a != b\ns = '<>'  # <>\n", []),

    ("PY3-EXCEPT-COMMA", b"try:\n    pass\nexcept ValueError, e:\n    pass\n", [3]),
    ("PY3-EXCEPT-COMMA", b"try:\n    pass\nexcept (A, B), e:\n    pass\n", [3]),
    ("PY3-EXCEPT-COMMA", b"try:\n    pass\nexcept (A,\n        B), e:\n    pass\n", [3]),
    ("PY3-EXCEPT-COMMA", b"try:\n    pass\nexcept (A, B):\n    pass\n", []),
    ("PY3-EXCEPT-COMMA", b"try:\n    pass\nexcept A as e:\n    pass\nexcept:\n    pass\n", []),

    ("PY3-RAISE-COMMA", b"raise ValueError, 'bad'\n", [1]),
    ("PY3-RAISE-COMMA", b"raise E, v, tb\n", [1]),
    ("PY3-RAISE-COMMA", b"raise ValueError, \\\n    'bad'\n", [1]),
    ("PY3-RAISE-COMMA", b"raise ValueError('bad')\nraise (E, 'v')\nraise\n", []),

    ("PY3-OCTAL", b"os.chmod(p, 0777)\n", [1]),
    ("PY3-OCTAL", b"x = 0777 + 0644\n", [1, 1]),
    ("PY3-OCTAL", b"x = 0777L\n", [1]),
    ("PY3-OCTAL", b"x = [0, 00, 0L, 0o777, 0O17, 0x1F, 0.5, 0777.5, 07e1, 07j, 10]\n", []),
    ("PY3-OCTAL", b"x = '0777'  # 0777\n", []),

    ("PY3-LONG-SUFFIX", b"x = 10L + 0x1fl + 0L + 0777L\n", [1, 1, 1, 1]),
    ("PY3-LONG-SUFFIX", b"x = 10 + 1e5 + 1j + 0x1f\ns = '10L'\n", []),

    ("PY3-DICT-ITER", b"d.iteritems()\nd.iterkeys()\nd.itervalues()\nd.has_key(k)\n", [1, 2, 3, 4]),
    ("PY3-DICT-ITER", b"for k, v in a.iteritems(): b.has_key(k)\n", [1, 1]),
    ("PY3-DICT-ITER", b"x = (foo(a,\n         b)\n     .iteritems())\n", [1]),
    ("PY3-DICT-ITER", b"d.items()\nf = d.iteritems\niteritems(d)\n", []),

    ("PY3-BUILTIN", b"x = unicode(y)\n", [1]),
    ("PY3-BUILTIN", b"isinstance(s, basestring) or isinstance(s, unicode)\n", [1, 1]),
    ("PY3-BUILTIN", b"x = [unicode, basestring, long, xrange, raw_input, unichr, execfile, reduce,\n"
                    b"     file, cmp, reload, apply, buffer, intern, coerce]\n", [1] * 8 + [2] * 7),
    ("PY3-BUILTIN", b"x = [str, int, range, input, chr, open, repr, obj.unicode]\nf(file=1)\n", []),
    ("PY3-BUILTIN", b"try:\n    unicode\nexcept NameError:\n    unicode = str\nx = unicode(1)\n", []),
    ("PY3-BUILTIN", b"from six.moves import xrange\nfor i in xrange(3): pass\n", []),
    ("PY3-BUILTIN", b"import foo as unicode, reduce\nunicode, reduce\n", []),
    ("PY3-BUILTIN", b"def cmp(a, b): pass\nclass file(object): pass\nsorted(xs, cmp), file()\n", []),
    ("PY3-BUILTIN", b"def f():\n    long = int\n    return long(1)\nlong(2)\n", []),
    ("PY3-BUILTIN", b"for file in files:\n    open(file)\n", []),
    ("PY3-BUILTIN", b"def f(cmp=None, *apply, **buffer):\n    return cmp, apply, buffer\n", []),
    ("PY3-BUILTIN", b"del unicode\nunicode(1)\n", [2]),

    ("PY3-STDLIB", b"import urllib2\n", [1]),
    ("PY3-STDLIB", b"from urlparse import urljoin\n", [1]),
    ("PY3-STDLIB", b"import os, cPickle, StringIO\n", [1, 1]),
    ("PY3-STDLIB", b"import ConfigParser as configparser\n", [1]),
    ("PY3-STDLIB", b"from Tkinter import (Tk,\n    Label)\n", [1]),
    ("PY3-STDLIB", b"def f():\n    import cPickle\n", [2]),
    ("PY3-STDLIB", b"import urllib2, urlparse, ConfigParser, Queue, cPickle, cStringIO, StringIO, httplib,"
                   b" HTMLParser, commands, SocketServer, Tkinter, __builtin__, copy_reg, xmlrpclib, thread,"
                   b" Cookie, cookielib, BaseHTTPServer, SimpleHTTPServer, htmlentitydefs, md5, sha, sets,"
                   b" UserDict\n", [1] * 25),
    ("PY3-STDLIB", b"import urllib\nimport queue\nimport configparser\nimport xml.dom\nimport threading\n", []),
    ("PY3-STDLIB", b"from . import Queue\nfrom .sets import x\ns = 'import urllib2'\n", []),

    ("PY3-DIVISION", b"x = a / b\n", [1]),
    ("PY3-DIVISION", b"x /= 2\n", [1]),
    ("PY3-DIVISION", b"x = a / b / c\n", [1, 1]),
    ("PY3-DIVISION", b"x = (a +\n     b) / c\n", [2]),
    ("PY3-DIVISION", b"from __future__ import print_function\nx = a / b\n", [2]),
    ("PY3-DIVISION", b"x = a // b\nx //= 2\ns = 'a/b'  # c/d\n", []),
    ("PY3-DIVISION", b"from __future__ import division\nx = a / b\n", []),
    ("PY3-DIVISION", b'"""Doc."""\nfrom __future__ import (absolute_import,\n'
                     b'                        division)\nx = a / b\n', []),

    ("PY3-METACLASS", b"class A:\n    __metaclass__ = Meta\n", [2]),
    ("PY3-METACLASS", b"class A(object):\n    if PY2:\n        __metaclass__ = Meta\n", [3]),
    ("PY3-METACLASS", b"class A:\n    class B:\n        __metaclass__ = M\n", [3]),
    ("PY3-METACLASS", b"__metaclass__ = type\n", []),
    ("PY3-METACLASS", b"class A:\n    def f(self):\n        __metaclass__ = M\n", []),
]


@pytest.mark.parametrize("rule,source,lines", CASES, ids=["%s-%d" % (c[0], i) for i, c in enumerate(CASES)])
def test_rule_finds_each_occurrence_at_its_starting_line(rule, source, lines):
    assert lines_of(rule, source) == lines


def test_warnings_and_blockers():
    src = b"class A:\n    __metaclass__ = M\nx = a / b\nprint x\n"
    severities = dict((f.rule, f.severity) for f in scan_source(u"m.py", src))
    assert severities == {"PY3-METACLASS": "warning", "PY3-DIVISION": "warning", "PY3-PRINT": "blocker"}


def test_findings_on_one_line_are_ordered_by_rule():
    assert found(b"print `x` <> 0777L\n") == [
        (1, "PY3-BACKTICK"), (1, "PY3-LONG-SUFFIX"), (1, "PY3-NE-OP"), (1, "PY3-OCTAL"), (1, "PY3-PRINT")]


LEGACY = b"""\
import urllib2, cPickle
from StringIO import StringIO

class Base:
    __metaclass__ = Meta

def ratio(a, b):
    if b <> 0:
        return a / b
    raise ValueError, "zero"

try:
    data = urllib2.urlopen(u).read()
except IOError, e:
    print `e`
for k, v in cfg.iteritems():
    os.chmod(k, 0755)
total = long(v) + 10L
"""


def test_legacy_module_gets_every_finding_in_order():
    assert found(LEGACY) == [
        (1, "PY3-STDLIB"), (1, "PY3-STDLIB"), (2, "PY3-STDLIB"), (5, "PY3-METACLASS"),
        (8, "PY3-NE-OP"), (9, "PY3-DIVISION"), (10, "PY3-RAISE-COMMA"), (14, "PY3-EXCEPT-COMMA"),
        (15, "PY3-BACKTICK"), (15, "PY3-PRINT"), (16, "PY3-DICT-ITER"), (17, "PY3-OCTAL"),
        (18, "PY3-BUILTIN"), (18, "PY3-LONG-SUFFIX")]


def test_tokens_are_read_after_decoding_the_declared_encoding():
    # In Shift_JIS the second byte of U+8868 is 0x5C, a backslash. Read as raw
    # bytes it would escape the closing quote and hide the <> after it.
    src = b"# coding: shift_jis\ns = '\x95\x5c'; t = a <> b\n"
    assert found(src) == [(2, "PY3-NE-OP")]


def test_declared_latin1_source_is_scanned():
    assert found(b"# -*- coding: latin-1 -*-\nprint 'caf\xe9'\n") == [(2, "PY3-PRINT")]


PARSE_CASES = [
    (b"print 'x'\ndef f(:\n    pass\n", 2),
    (b"print('a', end='')\n", 1),
    (b"def f(*, a):\n    pass\n", 1),
    (b"x = 1\ny = '\x00'\n", 2),
    (b"#!/usr/bin/env python\n# coding: no-such-codec\nprint 'x'\n", 2),
    (b"x = " + b"(" * 200 + b"1" + b")" * 200 + b"\n", 1),
    (b"\xef\xbb\xbf#!/usr/bin/env python\n# coding: latin-1\nprint 'x'\n", 2),
]


@pytest.mark.parametrize("source,line", PARSE_CASES, ids=["parse-%d" % i for i in range(len(PARSE_CASES))])
def test_unparseable_file_gets_only_a_parse_finding(source, line):
    findings = scan_source(u"m.py", source)
    assert [(f.line, f.rule, f.severity) for f in findings] == [(line, "PY3-PARSE", "blocker")]
