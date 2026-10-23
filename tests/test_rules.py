# -*- coding: utf-8 -*-
import ast
import tokenize
from io import BytesIO

from py2scan.rules.ast_rules import (
    check_backtick,
    check_builtin,
    check_dict_iter,
    check_exec,
    check_metaclass,
    check_print,
    check_raise_comma,
    check_stdlib,
)
from py2scan.rules.token_rules import (
    check_division,
    check_except_comma,
    check_long_suffix,
    check_ne_op,
    check_octal,
)


def rules(fn, source):
    return [(f.line, f.rule) for f in fn("m.py", ast.parse(source), [])]


def test_print_statement_is_found():
    assert rules(check_print, "x = 1\nprint x\n") == [(2, "PY3-PRINT")]


def test_print_function_is_not_found():
    src = "from __future__ import print_function\nprint('x')\n"
    assert rules(check_print, src) == []


def test_exec_statement_is_found():
    assert rules(check_exec, "exec 'x = 1'\n") == [(1, "PY3-EXEC-STMT")]


def test_backtick_repr_is_found():
    assert rules(check_backtick, "x = `1`\n") == [(1, "PY3-BACKTICK")]


def test_raise_with_comma_is_found():
    assert rules(check_raise_comma, "raise ValueError, 'bad'\n") == [(1, "PY3-RAISE-COMMA")]


def test_raise_with_comma_and_traceback_is_found():
    assert rules(check_raise_comma, "raise ValueError, 'bad', tb\n") == [(1, "PY3-RAISE-COMMA")]


def test_raise_without_comma_is_not_found():
    assert rules(check_raise_comma, "raise ValueError('bad')\n") == []


def test_dict_iteritems_is_found():
    assert rules(check_dict_iter, "d.iteritems()\n") == [(1, "PY3-DICT-ITER")]


def test_dict_has_key_is_found():
    assert rules(check_dict_iter, "d.has_key('x')\n") == [(1, "PY3-DICT-ITER")]


def test_dict_items_is_not_found():
    assert rules(check_dict_iter, "d.items()\n") == []


def test_builtin_use_is_found():
    assert rules(check_builtin, "x = unicode('a')\n") == [(1, "PY3-BUILTIN")]


def test_builtin_shadowed_by_assignment_is_not_found():
    assert rules(check_builtin, "unicode = str\nx = unicode('a')\n") == []


def test_builtin_shadowed_by_import_is_not_found():
    assert rules(check_builtin, "from mymod import unicode\nx = unicode('a')\n") == []


def test_builtin_shadowed_by_def_is_not_found():
    assert rules(check_builtin, "def unicode(x):\n    return x\nunicode(1)\n") == []


def test_two_builtins_on_one_line_are_two_findings():
    assert rules(check_builtin, "x = long(xrange(1))\n") == [
        (1, "PY3-BUILTIN"), (1, "PY3-BUILTIN"),
    ]


def test_stdlib_import_is_found():
    assert rules(check_stdlib, "import urllib2\n") == [(1, "PY3-STDLIB")]


def test_stdlib_import_from_is_found():
    assert rules(check_stdlib, "from ConfigParser import SafeConfigParser\n") == [(1, "PY3-STDLIB")]


def test_stdlib_submodule_import_is_found():
    assert rules(check_stdlib, "import Tkinter.ttk\n") == [(1, "PY3-STDLIB")]


def test_non_stdlib_import_is_not_found():
    assert rules(check_stdlib, "import os\n") == []


def test_two_stdlib_imports_on_one_line_are_two_findings():
    assert rules(check_stdlib, "import urllib2, httplib\n") == [
        (1, "PY3-STDLIB"), (1, "PY3-STDLIB"),
    ]


def test_metaclass_assignment_is_found():
    src = "class C(object):\n    __metaclass__ = type\n"
    assert rules(check_metaclass, src) == [(2, "PY3-METACLASS")]


def test_other_class_assignment_is_not_found():
    src = "class C(object):\n    x = 1\n"
    assert rules(check_metaclass, src) == []


def tokens_for(source):
    return list(tokenize.generate_tokens(BytesIO(source).readline))


def token_rules(fn, source):
    return [(f.line, f.rule) for f in fn("m.py", None, tokens_for(source))]


def test_ne_op_is_found():
    assert token_rules(check_ne_op, "if x <> y:\n    pass\n") == [(1, "PY3-NE-OP")]


def test_standard_ne_is_not_found():
    assert token_rules(check_ne_op, "if x != y:\n    pass\n") == []


def test_old_octal_is_found():
    assert token_rules(check_octal, "x = 0777\n") == [(1, "PY3-OCTAL")]


def test_zero_is_not_found():
    assert token_rules(check_octal, "x = 0\n") == []


def test_new_octal_is_not_found():
    assert token_rules(check_octal, "x = 0o777\n") == []


def test_hex_is_not_found():
    assert token_rules(check_octal, "x = 0x1F\n") == []


def test_float_is_not_found():
    assert token_rules(check_octal, "x = 0.5\n") == []


def test_long_suffix_is_found():
    assert token_rules(check_long_suffix, "x = 123L\n") == [(1, "PY3-LONG-SUFFIX")]


def test_lowercase_long_suffix_is_found():
    assert token_rules(check_long_suffix, "x = 123l\n") == [(1, "PY3-LONG-SUFFIX")]


def test_plain_int_is_not_found_as_long():
    assert token_rules(check_long_suffix, "x = 123\n") == []


def test_old_octal_with_long_suffix_is_both():
    assert token_rules(check_octal, "x = 0777L\n") == [(1, "PY3-OCTAL")]
    assert token_rules(check_long_suffix, "x = 0777L\n") == [(1, "PY3-LONG-SUFFIX")]


def test_except_comma_is_found():
    src = "try:\n    pass\nexcept ValueError, e:\n    pass\n"
    assert token_rules(check_except_comma, src) == [(3, "PY3-EXCEPT-COMMA")]


def test_except_as_is_not_found():
    src = "try:\n    pass\nexcept ValueError as e:\n    pass\n"
    assert token_rules(check_except_comma, src) == []


def test_except_tuple_without_name_is_not_found():
    src = "try:\n    pass\nexcept (ValueError, TypeError):\n    pass\n"
    assert token_rules(check_except_comma, src) == []


def test_except_tuple_with_comma_name_is_found():
    src = "try:\n    pass\nexcept (ValueError, TypeError), e:\n    pass\n"
    assert token_rules(check_except_comma, src) == [(3, "PY3-EXCEPT-COMMA")]


def test_bare_except_is_not_found():
    src = "try:\n    pass\nexcept:\n    pass\n"
    assert token_rules(check_except_comma, src) == []


def division_rules(source):
    tree = ast.parse(source)
    return [(f.line, f.rule, f.severity) for f in check_division("m.py", tree, tokens_for(source))]


def test_division_without_future_import_is_warning():
    assert division_rules("x = 1 / 2\n") == [(1, "PY3-DIVISION", "warning")]


def test_division_assign_without_future_import_is_warning():
    assert division_rules("x = 1\nx /= 2\n") == [(2, "PY3-DIVISION", "warning")]


def test_division_with_future_import_is_not_found():
    assert division_rules("from __future__ import division\nx = 1 / 2\n") == []


def test_floor_division_is_not_found():
    assert division_rules("x = 1 // 2\n") == []


def test_two_divisions_on_one_line_are_two_findings():
    assert division_rules("x = 1 / 2 / 3\n") == [
        (1, "PY3-DIVISION", "warning"), (1, "PY3-DIVISION", "warning"),
    ]
