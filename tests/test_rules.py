# -*- coding: utf-8 -*-
import tokenize

from py2scan.parsing import parse_source
from py2scan.rules.ast_rules import (
    check_async_reserved,
    check_backtick,
    check_builtin,
    check_dict_iter,
    check_exec,
    check_keyword_binding,
    check_metaclass,
    check_print,
    check_raise_comma,
    check_stdlib,
    check_tuple_param,
    check_ur_string,
)
from py2scan.rules.token_rules import (
    check_division,
    check_except_comma,
    check_long_suffix,
    check_ne_op,
    check_octal,
)
from py2scan.versions import SUPPORTED_VERSIONS

V = SUPPORTED_VERSIONS


def parsed(source):
    tree, tokens, failure, compiles = parse_source("m.py", source.encode("ascii"))
    assert failure is None, getattr(failure, "message", failure)
    return tree, tokens


def rules(fn, source, versions=V):
    tree, tokens = parsed(source)
    return [(f.line, f.rule) for f in fn("m.py", tree, tokens, versions)]


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


def test_builtin_bound_by_del_alone_is_not_found_after():
    # R3: `del` of a name binds it in that scope on its own, even with no
    # prior assignment and even though del does not introduce a value.
    src = "del unicode\nx = unicode('a')\n"
    assert rules(check_builtin, src) == []


def test_builtin_shadowed_by_global_requires_an_actual_binding():
    # R3: a bare `global X` with no binding of X inside that function does
    # not, by itself, bind X anywhere; the module-level builtin use still
    # counts as a finding.
    src = "def f():\n    global unicode\n    return 1\nx = unicode('a')\n"
    assert rules(check_builtin, src) == [(4, "PY3-BUILTIN")]


def test_builtin_shadowed_by_global_with_real_binding_is_module_wide():
    src = "def f():\n    global unicode\n    unicode = str\nf()\nx = unicode('a')\n"
    assert rules(check_builtin, src) == []


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


def test_stdlib_import_in_bare_except_try_is_warning():
    # R2: a bare except covering the import downgrades it.
    src = "try:\n    import urllib2\nexcept:\n    import urllib.request as urllib2\n"
    tree, tokens = parsed(src)
    findings = list(check_stdlib("m.py", tree, tokens, V))
    assert [(f.line, f.severity) for f in findings] == [(2, "warning")]


def test_stdlib_import_in_handler_catching_import_error_is_warning():
    src = ("try:\n    import urllib.request as urllib2\n"
           "except ImportError:\n    import urllib2\n")
    tree, tokens = parsed(src)
    findings = list(check_stdlib("m.py", tree, tokens, V))
    assert [(f.line, f.severity) for f in findings] == [(4, "warning")]


def test_stdlib_import_in_try_without_qualifying_handler_is_blocker():
    src = "try:\n    import urllib2\nexcept ValueError:\n    pass\n"
    tree, tokens = parsed(src)
    findings = list(check_stdlib("m.py", tree, tokens, V))
    assert [(f.line, f.severity) for f in findings] == [(2, "blocker")]


def test_stdlib_import_in_try_else_is_blocker():
    # R2: "inside" means the try body or handler bodies only, not else/finally.
    src = ("try:\n    pass\nexcept ImportError:\n    pass\n"
           "else:\n    import urllib2\n")
    tree, tokens = parsed(src)
    findings = list(check_stdlib("m.py", tree, tokens, V))
    assert [(f.line, f.severity) for f in findings] == [(6, "blocker")]


def test_stdlib_import_in_nested_def_inside_try_is_blocker():
    # R2: a nested def's body runs later, so it is not "inside" the try.
    src = ("try:\n    def f():\n        import urllib2\nexcept ImportError:\n    pass\n")
    tree, tokens = parsed(src)
    findings = list(check_stdlib("m.py", tree, tokens, V))
    assert [(f.line, f.severity) for f in findings] == [(3, "blocker")]


def test_metaclass_assignment_is_found():
    src = "class C(object):\n    __metaclass__ = type\n"
    assert rules(check_metaclass, src) == [(2, "PY3-METACLASS")]


def test_other_class_assignment_is_not_found():
    src = "class C(object):\n    x = 1\n"
    assert rules(check_metaclass, src) == []


def token_rules(fn, source, versions=V):
    tree, tokens = parsed(source)
    return [(f.line, f.rule) for f in fn("m.py", tree, tokens, versions)]


def test_ne_op_is_found():
    assert token_rules(check_ne_op, "if x <> y:\n    pass\n") == [(1, "PY3-NE-OP")]


def test_standard_ne_is_not_found():
    assert token_rules(check_ne_op, "if x != y:\n    pass\n") == []


def test_ne_op_split_across_two_adjacent_tokens_is_found():
    # Some current CPython patches lex "<>" as two adjacent OP tokens
    # ("<" then ">", zero-width gap) instead of one -- not a stable
    # per-version fact (see check_ne_op's own comment). Build the token
    # stream directly so this test does not depend on the host's own
    # tokenize behavior.
    tokens = [(tokenize.OP, "<", (1, 5), (1, 6), "x <> y\n"),
              (tokenize.OP, ">", (1, 6), (1, 7), "x <> y\n")]
    findings = list(check_ne_op("m.py", None, tokens, V))
    assert [(f.line, f.rule) for f in findings] == [(1, "PY3-NE-OP")]


def test_ne_op_with_a_real_gap_between_tokens_is_not_found():
    # "x < > y" is chained-comparison-shaped, not the "<>" operator (and
    # was never valid 2.7 syntax either) -- the gap between the tokens is
    # what tells them apart.
    tokens = [(tokenize.OP, "<", (1, 5), (1, 6), "x < > y\n"),
              (tokenize.OP, ">", (1, 7), (1, 8), "x < > y\n")]
    assert list(check_ne_op("m.py", None, tokens, V)) == []


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
    tree, tokens = parsed(source)
    return [(f.line, f.rule, f.severity) for f in check_division("m.py", tree, tokens, V)]


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


def test_standard_error_builtin_is_found():
    assert rules(check_builtin, "raise StandardError('x')\n") == [(1, "PY3-BUILTIN")]


def test_tuple_param_in_def_is_found():
    assert rules(check_tuple_param, "def f((a, b)):\n    return a + b\n") == [
        (1, "PY3-TUPLE-PARAM"),
    ]


def test_tuple_param_in_lambda_is_found():
    assert rules(check_tuple_param, "f = lambda (a, b): a + b\n") == [(1, "PY3-TUPLE-PARAM")]


def test_plain_params_are_not_tuple_params():
    assert rules(check_tuple_param, "def f(a, b):\n    return a + b\n") == []


def test_async_as_identifier_blocks_only_versions_37_and_up():
    tree, tokens = parsed("async = 1\n")
    findings = list(check_async_reserved("m.py", tree, tokens, ((3, 6), (3, 7), (3, 9))))
    assert len(findings) == 1
    assert findings[0].versions == ((3, 7), (3, 9))


def test_async_as_identifier_judged_only_against_36_is_not_found():
    tree, tokens = parsed("async = 1\nawait = 2\n")
    findings = list(check_async_reserved("m.py", tree, tokens, ((3, 6),)))
    assert findings == []


def test_async_keyword_normal_use_is_not_an_identifier_finding():
    assert rules(check_async_reserved, "x = 1\ny = 2\n") == []


def test_stdlib_removed_in_313_blocks_only_313_and_later():
    tree, tokens = parsed("import telnetlib\n")
    findings = list(check_stdlib("m.py", tree, tokens, ((3, 9), (3, 13), (3, 14))))
    assert len(findings) == 1
    assert findings[0].versions == ((3, 13), (3, 14))


def test_stdlib_removed_in_313_judged_only_against_earlier_is_not_found():
    tree, tokens = parsed("import telnetlib\n")
    findings = list(check_stdlib("m.py", tree, tokens, ((3, 9), (3, 10))))
    assert findings == []


def test_universal_stdlib_removal_blocks_every_judged_version():
    tree, tokens = parsed("import urllib2\n")
    versions = ((3, 6), (3, 15))
    findings = list(check_stdlib("m.py", tree, tokens, versions))
    assert len(findings) == 1
    assert findings[0].versions == versions


def test_bare_urllib_import_is_not_a_stdlib_finding():
    # urllib and dbm survive as package names in Python 3; only the renamed
    # names (urllib2, dbhash, ...) are findings. See UNIVERSAL_STDLIB_MODULES.
    assert rules(check_stdlib, "import urllib\n") == []
    assert rules(check_stdlib, "import dbm\n") == []


def test_true_assigned_to_is_found():
    assert rules(check_keyword_binding, "True = 5\n") == [(1, "PY3-KEYWORD-BINDING")]


def test_false_as_function_name_is_found():
    assert rules(check_keyword_binding, "def False():\n    pass\n") == [
        (1, "PY3-KEYWORD-BINDING"),
    ]


def test_true_as_for_target_is_found():
    assert rules(check_keyword_binding, "for True in x:\n    pass\n") == [
        (1, "PY3-KEYWORD-BINDING"),
    ]


def test_true_used_as_a_value_is_not_found():
    assert rules(check_keyword_binding, "x = True\n") == []


def test_none_is_not_flagged_by_this_rule():
    # None is already a 2.7-side SyntaxError to bind, so it never reaches
    # parso in the first place as a binding target; nothing to flag here.
    assert rules(check_keyword_binding, "x = None\n") == []


def test_ur_string_double_quote_is_found():
    assert rules(check_ur_string, 'x = ur"foo"\n') == [(1, "PY3-UR-STRING")]


def test_ur_string_single_quote_is_found():
    assert rules(check_ur_string, "x = ur'foo'\n") == [(1, "PY3-UR-STRING")]


def test_ur_string_case_variants_are_found():
    assert rules(check_ur_string, 'a = uR"x"\nb = Ur"y"\nc = UR"z"\n') == [
        (1, "PY3-UR-STRING"), (2, "PY3-UR-STRING"), (3, "PY3-UR-STRING"),
    ]


def test_plain_raw_string_is_not_ur():
    assert rules(check_ur_string, 'x = r"foo"\n') == []


def test_plain_unicode_string_is_not_ur():
    assert rules(check_ur_string, 'x = u"foo"\n') == []


def test_byte_string_is_not_ur():
    assert rules(check_ur_string, 'x = b"foo"\n') == []


def test_ur_string_elsewhere_does_not_blind_token_rules_to_an_earlier_except_comma():
    # Regression test for parsing._tokenize: native tokenize used to raise
    # TokenError the moment it reached a ur"..." literal, silently losing
    # every token-based finding for the rest of the file on a Python 3
    # host. check_except_comma reads the token stream, so a real except
    # comma earlier in the same file must still be caught.
    source = "try:\n    pass\nexcept Exception, e:\n    pass\nx = ur'z'\n"
    assert token_rules(check_except_comma, source) == [(3, "PY3-EXCEPT-COMMA")]


def test_ur_string_elsewhere_does_not_blind_token_rules_to_a_later_except_comma():
    source = "x = ur'z'\ntry:\n    pass\nexcept Exception, e:\n    pass\n"
    assert token_rules(check_except_comma, source) == [(4, "PY3-EXCEPT-COMMA")]
