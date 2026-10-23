# -*- coding: utf-8 -*-
import ast
import os
import shutil
import sys
import tempfile

import pytest

from py2scan import rules as rules_module
from py2scan.findings import Finding
from py2scan.scanner import _tokenize, scan_file
from py2scan.rules import (
    check_backtick,
    check_builtin_use,
    check_dict_iter,
    check_division,
    check_except_comma,
    check_exec,
    check_long_suffix,
    check_metaclass,
    check_ne_op,
    check_nesting_depth,
    check_non_text_coding_declaration,
    check_octal,
    check_print,
    check_raise_comma,
    check_stdlib_import,
    check_unicode_escape,
    check_ur_string,
)


# Python-2-only syntax (print/exec statements, backticks, raise-with-comma)
# can never ast.parse successfully on Python 3 - scanner.scan_file catches
# that SyntaxError and reports PY3-PARSE before these rule functions would
# ever run. There's nothing to port: the source literally cannot reach the
# rule on Python 3. R1 says the never-blocker-free guarantee wins this
# conflict and keeps PY3-PARSE - it does NOT call the resulting non-
# identical JSON (PY3-PRINT on 2.7 vs PY3-PARSE on 3.x for the same input)
# an accepted divergence; R1 requires it recorded as an open defect against
# item 2b instead (see MIGRATION.md's Blockers section).
PY2_ONLY_SYNTAX = pytest.mark.skipif(
    sys.version_info[0] >= 3, reason="syntax is Python-2-only; see R1")


def rules(fn, source):
    return [(f.line, f.rule) for f in fn("m.py", ast.parse(source))]


def token_rules(fn, source):
    tokens = _tokenize(source.encode("utf-8"))
    return [(f.line, f.rule) for f in fn("m.py", tokens)]


@PY2_ONLY_SYNTAX
def test_print_statement_is_found():
    assert rules(check_print, "x = 1\nprint x\n") == [(2, "PY3-PRINT")]


def test_print_function_is_not_found():
    src = "from __future__ import print_function\nprint('x')\n"
    assert rules(check_print, src) == []


@PY2_ONLY_SYNTAX
def test_exec_statement_is_found():
    assert rules(check_exec, "exec 'x = 1'\n") == [(1, "PY3-EXEC-STMT")]


def test_ne_op_is_found():
    assert token_rules(check_ne_op, "x = 1 <> 2\n") == [(1, "PY3-NE-OP")]


def test_standard_ne_is_not_found():
    assert token_rules(check_ne_op, "x = 1 != 2\n") == []


def test_old_octal_is_found():
    assert token_rules(check_octal, "x = 0777\n") == [(1, "PY3-OCTAL")]


def test_zero_is_not_found():
    assert token_rules(check_octal, "x = 0\n") == []


def test_new_octal_is_not_found():
    assert token_rules(check_octal, "x = 0o17\n") == []


def test_hex_is_not_found():
    assert token_rules(check_octal, "x = 0x1F\n") == []


def test_float_is_not_found():
    assert token_rules(check_octal, "x = 0.5\n") == []


def test_long_suffix_is_found():
    assert token_rules(check_long_suffix, "x = 10L\n") == \
        [(1, "PY3-LONG-SUFFIX")]


def test_lowercase_long_suffix_is_found():
    assert token_rules(check_long_suffix, "x = 10l\n") == \
        [(1, "PY3-LONG-SUFFIX")]


def test_plain_int_has_no_long_suffix():
    assert token_rules(check_long_suffix, "x = 10\n") == []


def test_old_octal_with_long_suffix_fires_both_rules():
    src = "x = 0777L\n"
    assert token_rules(check_octal, src) == [(1, "PY3-OCTAL")]
    assert token_rules(check_long_suffix, src) == [(1, "PY3-LONG-SUFFIX")]


def test_except_comma_is_found():
    src = "try:\n    pass\nexcept Exception, e:\n    pass\n"
    assert token_rules(check_except_comma, src) == [(3, "PY3-EXCEPT-COMMA")]


@PY2_ONLY_SYNTAX
def test_ur_string_is_found():
    # Found via item 2a's real-stdlib parity scan: posixpath.py and
    # lib2to3/fixes/fix_unicode.py both use this and real Python 3 cannot
    # compile either (R1) - no existing rule caught it before this.
    # Python-2-only at the tokenize level, not just ast.parse: Python
    # 3.14's own tokenize module raises TokenError for a ur-prefixed
    # string (confirmed empirically), so this can never reach
    # check_ur_string in the real scan_file pipeline on Python 3 either -
    # ast.parse's SyntaxError (PY3-PARSE) is reported first, same as
    # every other PY2_ONLY_SYNTAX case.
    assert token_rules(check_ur_string, r"x = ur'\$(\w+)'" + "\n") == \
        [(1, "PY3-UR-STRING")]


@PY2_ONLY_SYNTAX
def test_ur_string_every_u_before_r_ordering_is_found():
    for prefix in ("ur", "Ur", "uR", "UR"):
        src = "x = %s'test'\n" % prefix
        assert token_rules(check_ur_string, src) == [(1, "PY3-UR-STRING")], \
            prefix


def test_plain_raw_string_is_not_found():
    assert token_rules(check_ur_string, "x = r'test'\n") == []


def test_plain_unicode_string_is_not_found():
    assert token_rules(check_ur_string, "x = u'test'\n") == []


def test_invalid_unicode_escape_is_found():
    # Found via item 2a's real-stdlib parity scan: json/__init__.py's own
    # docstring uses this as placeholder text, and real Python 3 cannot
    # compile the file (R1) - no existing rule caught it before this.
    src = '''x = """text with \\uXXXX in it"""\n'''
    assert token_rules(check_unicode_escape, src) == \
        [(1, "PY3-UNICODE-ESCAPE")]


def test_valid_unicode_escape_is_not_found():
    assert token_rules(check_unicode_escape, "x = '\\u0041'\n") == []


def test_invalid_unicode_escape_in_byte_string_is_not_found():
    # b'...' never processes \\u on either interpreter - confirmed
    # empirically identical on both sides, so this is not a 2-vs-3
    # difference to report.
    assert token_rules(check_unicode_escape, "x = b'\\uXXXX'\n") == []


def test_invalid_unicode_escape_in_raw_string_is_not_found():
    assert token_rules(check_unicode_escape, "x = r'\\uXXXX'\n") == []


def test_invalid_unicode_escape_in_u_string_is_not_found():
    # A u-prefixed string already requires a valid \\u escape under
    # Python 2.7 too (SyntaxError on both sides) - not a 2-vs-3
    # difference.
    assert token_rules(check_unicode_escape, "x = u'\\uXXXX'\n") == []


def test_escaped_backslash_before_u_is_not_a_unicode_escape():
    # \\\\u is one escaped literal backslash followed by plain text
    # "u0041" - not a \\u escape at all, on either interpreter.
    assert token_rules(check_unicode_escape, "x = '\\\\u0041'\n") == []


def test_invalid_unicode_name_escape_is_found():
    assert token_rules(check_unicode_escape, "x = '\\N{}'\n") == \
        [(1, "PY3-UNICODE-ESCAPE")]


def test_valid_unicode_name_escape_is_not_found():
    assert token_rules(
        check_unicode_escape, "x = '\\N{BULLET}'\n") == []


def _nested_parens(depth):
    return "x = " + ("(" * depth) + "1" + (")" * depth) + "\n"


def _nested_mixed_brackets(depth):
    # depth/2 levels of "(" then "[" interleaved, closed in matching
    # order - exercises that check_nesting_depth counts every bracket
    # kind as one shared depth, the way the real tokenizer does (R9;
    # confirmed directly against 2.7.18, 3.6.15 and 3.9.25-3.15.1, which
    # all hit the exact same crossover for (), [] and {}).
    half = depth // 2
    return "x = " + ("([" * half) + "1" + ("])" * half) + "\n"


def test_nesting_depth_within_every_judged_versions_limit_is_not_found():
    tokens = _tokenize(_nested_parens(90).encode("utf-8"))
    findings = list(check_nesting_depth(
        "m.py", tokens, ("3.6", "3.7", "3.8", "3.9")))
    assert findings == []


def test_nesting_depth_at_the_exact_measured_limit_is_not_found():
    # 3.6.15's real crossover: depth 92 compiles, 93 doesn't (MIGRATION.md
    # R9 evidence) - the boundary itself must not false-positive.
    tokens = _tokenize(_nested_parens(92).encode("utf-8"))
    assert list(check_nesting_depth("m.py", tokens, ("3.6",))) == []


def test_nesting_depth_one_past_the_measured_limit_is_found():
    tokens = _tokenize(_nested_parens(93).encode("utf-8"))
    findings = list(check_nesting_depth("m.py", tokens, ("3.6",)))
    assert len(findings) == 1
    assert findings[0].versions == ("3.6",)


def test_nesting_depth_only_blocks_the_versions_it_exceeds():
    # Depth 150: real 3.6-3.8 (limit <= 98) cannot compile it, real
    # 3.9-3.15 (limit 200) can - the exact hostile/deep_nesting shape
    # AutoSteer CI found missing a blocker for 3.6-3.8 on a 3.14 scan.
    tokens = _tokenize(_nested_parens(150).encode("utf-8"))
    findings = list(check_nesting_depth("m.py", tokens, ("3.8", "3.9")))
    assert len(findings) == 1
    assert findings[0].versions == ("3.8",)


def test_nesting_depth_blocks_every_queried_version_when_all_are_exceeded():
    # Depth 95 exceeds both 3.6's and 3.7's limit (92) - unlike the
    # earlier test, every version judged_versions asks about is blocked
    # here, not just a subset. (201, past the PEG parser's own shared
    # 200, can't be used for this: _tokenize itself already raises
    # TokenError for it on a 3.9+ running interpreter - confirmed
    # directly - so check_nesting_depth would never even see it.)
    tokens = _tokenize(_nested_parens(95).encode("utf-8"))
    findings = list(check_nesting_depth("m.py", tokens, ("3.6", "3.7")))
    assert len(findings) == 1
    assert findings[0].versions == ("3.6", "3.7")


def test_nesting_depth_counts_every_bracket_kind_as_one_shared_depth():
    # 50 "(" interleaved with 50 "[" reaches a combined depth of 100 -
    # above 3.8's real limit (98) even though neither bracket kind alone
    # reaches it (50 of either, by itself, would not).
    tokens = _tokenize(_nested_mixed_brackets(100).encode("utf-8"))
    findings = list(check_nesting_depth("m.py", tokens, ("3.8",)))
    assert len(findings) == 1
    assert findings[0].versions == ("3.8",)


def test_nesting_depth_with_no_brackets_is_not_found():
    tokens = _tokenize(b"x = 1\n")
    assert list(check_nesting_depth("m.py", tokens, ("3.6",))) == []


_HAS_LIB2TO3_DETECT_ENCODING = pytest.mark.skipif(
    sys.version_info >= (3, 13),
    reason="py2scan.encoding falls back to the real tokenize module once "
           "lib2to3 is gone (3.13+), and that real detect_encoding runs "
           "this same non-text check itself and raises LookupError "
           "before returning a name - confirmed directly on 3.14.7. "
           "Harmless in the real pipeline: scan_file's own ast.parse "
           "already raises for the identical input there, so this rule "
           "is never reached outside a direct call like this one.")


@_HAS_LIB2TO3_DETECT_ENCODING
def test_rot13_coding_declaration_is_found():
    # rot13-decodes to "x = 1" - a real held-back AutoSteer CI input:
    # compiles cleanly under 2.7 (which runs no such check), rejected by
    # every real Python 3.6-3.15 (confirmed: codecs marks it a non-text
    # encoding there, identically on every final release tested).
    source = b"# -*- coding: rot13 -*-\nk = 1\n"
    findings = list(check_non_text_coding_declaration("m.py", source))
    assert len(findings) == 1
    assert findings[0].rule == "PY3-NON-TEXT-CODING"
    assert findings[0].severity == "blocker"


@_HAS_LIB2TO3_DETECT_ENCODING
def test_every_non_text_codec_alias_is_found():
    for name in ("base64", "bz2", "hex", "quopri", "quoted-printable",
                 "rot13", "rot-13", "uu", "zlib", "zip"):
        source = ("# -*- coding: %s -*-\nx = 1\n" % name).encode("ascii")
        findings = list(check_non_text_coding_declaration("m.py", source))
        assert len(findings) == 1, name


def test_ordinary_coding_declaration_is_not_found():
    source = b"# -*- coding: utf-8 -*-\nx = 1\n"
    assert list(check_non_text_coding_declaration("m.py", source)) == []


def test_no_coding_declaration_is_not_found():
    assert list(check_non_text_coding_declaration("m.py", b"x = 1\n")) == []


def test_unrecognized_codec_name_is_not_found():
    # A codec name detect_encoding can't look up at all is the already-
    # documented item 2b divergence (invalid_coding), not this rule's
    # concern - it must not also raise here.
    source = b"# -*- coding: no-such-codec -*-\nx = 1\n"
    assert list(check_non_text_coding_declaration("m.py", source)) == []


def test_except_as_is_not_found():
    src = "try:\n    pass\nexcept Exception as e:\n    pass\n"
    assert token_rules(check_except_comma, src) == []


def test_bare_except_is_not_found():
    src = "try:\n    pass\nexcept:\n    pass\n"
    assert token_rules(check_except_comma, src) == []


def test_except_tuple_without_name_is_not_found():
    src = "try:\n    pass\nexcept (A, B):\n    pass\n"
    assert token_rules(check_except_comma, src) == []


def test_except_tuple_with_comma_name_is_found():
    src = "try:\n    pass\nexcept (A, B), e:\n    pass\n"
    assert token_rules(check_except_comma, src) == [(3, "PY3-EXCEPT-COMMA")]


@PY2_ONLY_SYNTAX
def test_backtick_is_found():
    assert rules(check_backtick, "y = `x`\n") == [(1, "PY3-BACKTICK")]


@PY2_ONLY_SYNTAX
def test_raise_comma_is_found():
    assert rules(check_raise_comma, "raise E, v\n") == [(1, "PY3-RAISE-COMMA")]


@PY2_ONLY_SYNTAX
def test_raise_comma_with_traceback_is_found():
    assert rules(check_raise_comma, "raise E, v, tb\n") == \
        [(1, "PY3-RAISE-COMMA")]


def test_raise_without_comma_is_not_found():
    assert rules(check_raise_comma, "raise E\n") == []


def test_raise_call_is_not_found():
    assert rules(check_raise_comma, "raise E(v)\n") == []


def test_dict_iteritems_is_found():
    src = "for k, v in d.iteritems():\n    pass\n"
    assert rules(check_dict_iter, src) == [(1, "PY3-DICT-ITER")]


def test_dict_iterkeys_is_found():
    assert rules(check_dict_iter, "d.iterkeys()\n") == [(1, "PY3-DICT-ITER")]


def test_dict_itervalues_is_found():
    assert rules(check_dict_iter, "d.itervalues()\n") == [(1, "PY3-DICT-ITER")]


def test_dict_has_key_is_found():
    assert rules(check_dict_iter, "d.has_key(1)\n") == [(1, "PY3-DICT-ITER")]


def test_dict_items_is_not_found():
    assert rules(check_dict_iter, "d.items()\n") == []


def test_metaclass_in_class_body_is_found():
    src = "class C(object):\n    __metaclass__ = M\n"
    assert rules(check_metaclass, src) == [(2, "PY3-METACLASS")]


def test_metaclass_in_method_is_not_found():
    src = "class C(object):\n    def m(self):\n        __metaclass__ = N\n"
    assert rules(check_metaclass, src) == []


def test_metaclass_at_module_scope_is_not_found():
    assert rules(check_metaclass, "__metaclass__ = M\n") == []


def test_division_without_future_import_is_found():
    assert rules(check_division, "x = 1 / 2\n") == [(1, "PY3-DIVISION")]


def test_division_with_future_import_is_not_found():
    src = "from __future__ import division\nx = 1 / 2\n"
    assert rules(check_division, src) == []


def test_floor_division_is_never_found():
    assert rules(check_division, "x = 1 // 2\n") == []


def test_division_augassign_is_found():
    assert rules(check_division, "x = 1\nx /= 2\n") == [(2, "PY3-DIVISION")]


def test_builtin_use_is_found():
    assert rules(check_builtin_use, "x = unicode('a')\n") == \
        [(1, "PY3-BUILTIN")]


def test_builtin_use_is_suppressed_when_module_defines_it():
    src = "def unicode(x):\n    return x\n\ny = unicode(1)\n"
    assert rules(check_builtin_use, src) == []


def test_builtin_use_is_suppressed_when_module_assigns_it():
    src = "long = 5\ny = long\n"
    assert rules(check_builtin_use, src) == []


def test_builtin_use_is_suppressed_for_a_parameter_name():
    src = "def f(xrange):\n    return xrange\n"
    assert rules(check_builtin_use, src) == []


def test_standard_error_is_found():
    # R10: StandardError is in 2.7's __builtin__ but absent from every
    # judged version's builtins module (verified empirically against real
    # 3.6.15 through 3.14.7 interpreters, identically across all of them) -
    # it was missing from BUILTIN_NAMES, a real gap, not a design question.
    assert rules(check_builtin_use, "class E(StandardError):\n    pass\n") \
        == [(1, "PY3-BUILTIN")]


def test_unrelated_builtin_is_not_found():
    assert rules(check_builtin_use, "x = len([1, 2])\n") == []


def test_builtin_use_in_one_function_does_not_leak_to_another():
    # R3: scoping is Python's real compiler scoping, not a flat file-wide
    # set - f's purely local `unicode` must not shadow g's genuine builtin
    # use.
    src = ("def f():\n    unicode = 5\n    return unicode\n\n"
           "def g():\n    return unicode('hi')\n")
    assert rules(check_builtin_use, src) == [(6, "PY3-BUILTIN")]


def test_module_level_del_shadows_everywhere():
    src = "del long\nx = long\n"
    assert rules(check_builtin_use, src) == []


def test_del_inside_one_function_does_not_leak_to_another():
    src = "def f():\n    del long\n\ndef g():\n    return long\n"
    assert rules(check_builtin_use, src) == [(5, "PY3-BUILTIN")]


def test_bare_global_statement_alone_does_not_shadow():
    # R3: a bare `global` with no matching binding in that same function
    # binds nothing by itself.
    src = "def f():\n    global long\n    return long\n"
    assert rules(check_builtin_use, src) == [(3, "PY3-BUILTIN")]


def test_global_declared_and_bound_shadows_module_wide():
    src = ("def f():\n    global long\n    long = 5\n\n"
           "def g():\n    return long\n")
    assert rules(check_builtin_use, src) == []


def test_nested_function_sees_enclosing_functions_local_via_closure():
    src = ("def outer():\n    unicode = 5\n"
           "    def inner():\n        return unicode('x')\n"
           "    return inner\n")
    assert rules(check_builtin_use, src) == []


def test_class_body_binding_does_not_shadow_builtin_in_its_methods():
    # R3: only a function creates a scope nested methods see through - a
    # class body's own binding isn't visible to its methods this way.
    src = ("class C(object):\n    long = 5\n"
           "    def m(self):\n        return long\n")
    assert rules(check_builtin_use, src) == [(4, "PY3-BUILTIN")]


def test_builtin_name_as_its_own_default_value_is_found():
    # R3/R10: AutoSteer CI repro, stdlib json/encoder.py line 276 -
    # `def f(basestring=basestring, long=long): ...` is a real hand-
    # optimization (turning globals into locals for speed). Real Python
    # evaluates a default value in the *enclosing* scope at def time, so
    # the parameter named "basestring" does not shadow the "basestring"
    # on the right-hand side of its own default - a Python-3 NameError
    # this rule used to miss entirely.
    src = "def f(basestring=basestring, long=long):\n    pass\n"
    assert rules(check_builtin_use, src) == [
        (1, "PY3-BUILTIN"), (1, "PY3-BUILTIN")]


def test_builtin_name_as_a_different_parameters_default_is_found():
    src = "def f(x=long):\n    pass\n"
    assert rules(check_builtin_use, src) == [(1, "PY3-BUILTIN")]


def test_builtin_shadowed_by_an_unrelated_parameter_default_not_found():
    # The parameter "long" really does shadow "long" used inside the
    # body - only its own default value expression is the enclosing
    # scope, not the rest of the function.
    src = "def f(long=5):\n    return long\n"
    assert rules(check_builtin_use, src) == []


def test_builtin_name_in_a_decorator_is_found():
    src = "@long\ndef f():\n    pass\n"
    assert rules(check_builtin_use, src) == [(1, "PY3-BUILTIN")]


def test_builtin_name_as_a_lambda_parameters_default_is_found():
    src = "f = lambda long=long: long\n"
    assert rules(check_builtin_use, src) == [(1, "PY3-BUILTIN")]


def test_stdlib_import_is_found():
    assert rules(check_stdlib_import, "import urllib2\n") == \
        [(1, "PY3-STDLIB")]


def test_stdlib_import_from_is_found():
    src = "from ConfigParser import SafeConfigParser\n"
    assert rules(check_stdlib_import, src) == [(1, "PY3-STDLIB")]


def test_stdlib_import_with_alias_is_found():
    assert rules(check_stdlib_import, "import urllib2 as u2\n") == \
        [(1, "PY3-STDLIB")]


def test_multi_import_line_flags_only_the_stdlib_name():
    assert rules(check_stdlib_import, "import os, urllib2 as u2\n") == \
        [(1, "PY3-STDLIB")]


def test_two_stdlib_names_on_one_import_line_is_two_findings():
    result = rules(check_stdlib_import, "import urllib2, ConfigParser\n")
    assert result == [(1, "PY3-STDLIB"), (1, "PY3-STDLIB")]


def test_unrelated_import_is_not_found():
    assert rules(check_stdlib_import, "import os\n") == []


def test_relative_import_is_not_found():
    assert rules(check_stdlib_import, "from . import urllib2\n") == []


def test_relative_import_of_a_colliding_local_name_is_not_found():
    assert rules(check_stdlib_import, "from .urllib2 import Request\n") == []


def test_version_dependent_removal_is_not_found_before_its_version():
    # R6/R8: distutils isn't removed until Python 3.12 - judging only
    # against 3.9 (where it still works) must not report it.
    tree = ast.parse("import distutils\n")
    findings = list(check_stdlib_import("m.py", tree, ("3.9",)))
    assert findings == []


def test_version_dependent_removal_is_scoped_to_its_own_versions():
    # Judging against both 3.9 (still works) and 3.12 (removed): the
    # finding fires, but its versions only cover 3.12, not 3.9.
    tree = ast.parse("import distutils\n")
    findings = list(check_stdlib_import("m.py", tree, ("3.9", "3.12")))
    assert len(findings) == 1
    assert findings[0].versions == ("3.12",)


def test_boundary_removal_applies_to_every_judged_version():
    # urllib2 was removed at the 2-vs-3 boundary (long before 3.6, R6's
    # oldest judged version) - it applies to every version judged,
    # whatever subset that is.
    tree = ast.parse("import urllib2\n")
    findings = list(check_stdlib_import("m.py", tree, ("3.9", "3.12")))
    assert len(findings) == 1
    assert findings[0].versions == ("3.9", "3.12")


def test_stdlib_import_derived_beyond_the_original_hardcoded_list():
    # R8: STDLIB_REMOVED_SINCE is derived from every real interpreter's
    # own module list, not the small fixed set this rule shipped with
    # originally (urllib2, ConfigParser, cPickle, and 22 others - see
    # commit 0e39731). mimetools, rexec, markupbase and SimpleXMLRPCServer
    # were never in that original set; a real-stdlib parity scan (item 2a,
    # MIGRATION.md) found all four newly flagged in files that used to
    # scan clean of this rule (BaseHTTPServer.py, Bastion.py, HTMLParser.py,
    # DocXMLRPCServer.py) - reproduced directly here against the rule
    # itself, not just the files that happened to surface it.
    for name in ("mimetools", "rexec", "markupbase", "SimpleXMLRPCServer"):
        tree = ast.parse("import %s\n" % name)
        findings = list(check_stdlib_import("m.py", tree))
        assert len(findings) == 1, name
        assert findings[0].severity == "blocker"


def test_stdlib_import_covers_the_pep_594_batch_removed_in_3_13():
    # R8: AutoSteer CI repro, stdlib sunau.py line 395 ("import audioop")
    # got no finding at all - audioop, crypt, nis, ossaudiodev and spwd
    # were missing from STDLIB_REMOVED_SINCE's PEP 594 batch (they sit
    # right alongside aifc/cgi/cgitb/... already in that same batch).
    # Testing each by importing it directly against a slim test image
    # falsely looked like removal as early as 3.9 - every one of these
    # five needs a system library the slim images never had, at any
    # version - cross-checked against sys.stdlib_module_names instead
    # (3.10+, independent of whether the extension actually built):
    # True at 3.10 and 3.12, False starting at 3.13 - see MIGRATION.md's
    # R8 evidence.
    for name in ("audioop", "crypt", "nis", "ossaudiodev", "spwd"):
        tree = ast.parse("import %s\n" % name)
        findings = list(check_stdlib_import("m.py", tree, ("3.12", "3.13")))
        assert len(findings) == 1, name
        assert findings[0].versions == ("3.13",), name


def test_stdlib_import_covers_the_remaining_2a_gaps():
    # future_builtins/gdbm/linuxaudiodev/strop (gone at the 2-vs-3
    # boundary, before R6's judged range starts) and parser (removed in
    # 3.10, replaced by the PEG-based ast module) were the other five
    # names this same re-derivation found missing.
    for name, since in (("future_builtins", "3.6"), ("gdbm", "3.6"),
                        ("linuxaudiodev", "3.6"), ("strop", "3.6"),
                        ("parser", "3.10")):
        tree = ast.parse("import %s\n" % name)
        findings = list(check_stdlib_import("m.py", tree))
        assert len(findings) == 1, name
        assert findings[0].severity == "blocker"


def severities(fn, source):
    return [(f.rule, f.severity) for f in fn("m.py", ast.parse(source))]


def test_stdlib_import_guarded_by_bare_except_is_a_warning():
    src = "try:\n    import urllib2\nexcept:\n    pass\n"
    assert severities(check_stdlib_import, src) == [("PY3-STDLIB", "warning")]


def test_stdlib_import_guarded_by_importerror_handler_is_a_warning():
    src = ("try:\n    import cPickle as pickle\n"
           "except ImportError:\n    import pickle\n")
    assert severities(check_stdlib_import, src) == [("PY3-STDLIB", "warning")]


def test_stdlib_import_fallback_in_importerror_handler_is_a_warning():
    # The fallback import, inside the handler body, is just as guarded as
    # the try-body import above it.
    src = ("try:\n    import pickle\n"
           "except ImportError:\n    import cPickle as pickle\n")
    assert severities(check_stdlib_import, src) == [("PY3-STDLIB", "warning")]


def test_stdlib_import_guarded_by_tuple_of_exceptions_is_a_warning():
    src = ("try:\n    import urllib2\n"
           "except (ImportError, ValueError):\n    pass\n")
    assert severities(check_stdlib_import, src) == [("PY3-STDLIB", "warning")]


def test_stdlib_import_guarded_by_modulenotfounderror_is_a_warning():
    src = "try:\n    import urllib2\nexcept ModuleNotFoundError:\n    pass\n"
    assert severities(check_stdlib_import, src) == [("PY3-STDLIB", "warning")]


def test_stdlib_import_guarded_by_standarderror_is_a_warning():
    src = "try:\n    import urllib2\nexcept StandardError:\n    pass\n"
    assert severities(check_stdlib_import, src) == [("PY3-STDLIB", "warning")]


def test_stdlib_import_not_guarded_by_unrelated_except_is_still_a_blocker():
    src = "try:\n    import urllib2\nexcept ValueError:\n    pass\n"
    assert severities(check_stdlib_import, src) == [("PY3-STDLIB", "blocker")]


def test_stdlib_import_in_try_else_is_still_a_blocker():
    src = ("try:\n    pass\nexcept ImportError:\n    pass\n"
           "else:\n    import urllib2\n")
    assert severities(check_stdlib_import, src) == [("PY3-STDLIB", "blocker")]


def test_stdlib_import_in_try_finally_is_still_a_blocker():
    src = ("try:\n    pass\nexcept ImportError:\n    pass\n"
           "finally:\n    import urllib2\n")
    assert severities(check_stdlib_import, src) == [("PY3-STDLIB", "blocker")]


def test_stdlib_import_in_nested_function_inside_try_is_still_a_blocker():
    src = ("try:\n    def f():\n        import urllib2\nexcept ImportError:"
           "\n    pass\n")
    assert severities(check_stdlib_import, src) == [("PY3-STDLIB", "blocker")]


def test_stdlib_import_outside_any_try_is_still_a_blocker():
    assert severities(check_stdlib_import, "import urllib2\n") == \
        [("PY3-STDLIB", "blocker")]


def test_adding_a_rule_touches_at_most_two_files():
    # Item 5: scanner.scan_file dispatches generically over
    # rules.AST_RULES / VERSION_AWARE_AST_RULES / TOKEN_RULES - it never
    # names a rule function itself (confirmed: `grep -n "check_"
    # py2scan/scanner.py` has zero hits). So a new rule needs only its
    # function plus a one-line append to the matching list, both in
    # py2scan/rules.py, and a test in this file - never scanner.py.
    # Proven by appending a throwaway rule straight to rules.AST_RULES at
    # runtime (simulating that one-line append) and confirming scan_file
    # picks it up immediately, with zero change to scanner.py itself.
    def check_toy_rule(path, tree):
        yield Finding(path, 1, "PY3-TOY-RULE-FOR-TEST", "warning", "toy")

    rules_module.AST_RULES.append(check_toy_rule)
    try:
        root = tempfile.mkdtemp()
        try:
            with open(os.path.join(root, "m.py"), "wb") as f:
                f.write(b"x = 1\n")
            findings, problem = scan_file(root, "m.py")
        finally:
            shutil.rmtree(root)
    finally:
        rules_module.AST_RULES.remove(check_toy_rule)
    assert problem is None
    assert [finding.rule for finding in findings] == ["PY3-TOY-RULE-FOR-TEST"]
