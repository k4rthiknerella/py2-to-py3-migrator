# -*- coding: utf-8 -*-
import ast
import sys

import pytest

from py2scan.scanner import _tokenize
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
    check_octal,
    check_print,
    check_raise_comma,
    check_stdlib_import,
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


def test_unrelated_builtin_is_not_found():
    assert rules(check_builtin_use, "x = len([1, 2])\n") == []


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
