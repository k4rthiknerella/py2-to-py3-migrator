# -*- coding: utf-8 -*-
import tokenize

from py2scan.parsing import parse_source
from py2scan.rules.ast_rules import (
    check_async_reserved,
    check_backtick,
    check_bad_unicode_escape,
    check_builtin,
    check_dict_iter,
    check_exec,
    check_invalid_scope_use,
    check_keyword_binding,
    check_metaclass,
    check_mixed_bytes_literal,
    check_print,
    check_raise_comma,
    check_stdlib,
    check_tuple_param,
    check_ur_string,
)
from py2scan.rules.token_rules import (
    check_deep_nesting,
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


def test_print_function_call_with_file_kwarg_parses_at_all():
    # Regression test: real CPython 2.7 accepts print(x, file=y) once
    # print_function is imported, but parso's static print_stmt grammar
    # rejects the "file=y" keyword argument outright regardless of the
    # future import (it has no concept of it) -- parse_source works
    # around this (see _placeholder_print_if_future), so the whole file
    # must still produce a tree rather than a ParseFailure.
    src = "from __future__ import print_function\nimport sys\nprint('x', file=sys.stderr)\n"
    tree, tokens, failure, compiles = parse_source("m.py", src.encode("ascii"))
    assert failure is None, getattr(failure, "message", failure)
    assert rules(check_print, src) == []


def test_print_statement_without_future_import_still_found_after_fix():
    # The placeholder substitution only triggers when print_function is
    # actually imported; an ordinary print statement elsewhere must
    # still be flagged normally.
    assert rules(check_print, "x = 1\nprint x\n") == [(2, "PY3-PRINT")]


def test_leftover_print_statement_under_future_import_still_fails_to_parse():
    # A real bug: print_function makes "print" a plain name, so a
    # leftover "print x" (no parens) in the same module is genuinely
    # invalid under CPython too -- it must still fail to parse, not be
    # silently accepted by the substitution.
    src = "from __future__ import print_function\nprint x\n"
    tree, tokens, failure, compiles = parse_source("m.py", src.encode("ascii"))
    assert failure is not None


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


def test_builtin_name_as_attribute_access_is_not_found():
    # chunk.file.read(1) in real stdlib aifc.py:480: "file" here is the
    # attribute half of a "." trailer, never a reference to the builtin.
    assert rules(check_builtin, "x = chunk.file.read(1)\n") == []


def test_builtin_name_as_attribute_assignment_target_is_not_found():
    assert rules(check_builtin, "self.buffer = []\n") == []


def test_builtin_name_as_keyword_argument_name_is_not_found():
    # print(x, file=y): "file" here is the name half of a call's keyword
    # argument, not a reference to anything in scope.
    assert rules(check_builtin, "foo(x, file=y)\n") == []


def test_builtin_name_as_keyword_argument_value_is_still_found():
    # the VALUE side of a keyword argument is an ordinary reference and
    # must still be flagged if it names a builtin.
    assert rules(check_builtin, "foo(x=unicode('a'))\n") == [(1, "PY3-BUILTIN")]


def test_builtin_call_is_still_found_next_to_an_attribute_of_the_same_name():
    # a real call to the builtin must still be flagged even in a file that
    # also uses the same name as an attribute elsewhere on the same line.
    assert rules(check_builtin, "x = file(chunk.file)\n") == [(1, "PY3-BUILTIN")]


def test_builtin_named_method_does_not_shadow_the_builtin_inside_its_own_body():
    # Independent check, round 2, item 3. Real repro: CPython 2.7's own
    # code.py defines InteractiveInterpreter.raw_input(self, prompt),
    # whose body calls the bare name raw_input() - the builtin, since a
    # method can never see its own class's attributes unqualified. The
    # old scope model walked straight past the classdef looking for an
    # enclosing funcdef, found none, and wrongly bound "raw_input" at
    # module scope - suppressing every real builtin use of raw_input in
    # the whole module, not just inside this one method.
    src = (
        "class C(object):\n"
        "    def raw_input(self, prompt=\"\"):\n"
        "        return raw_input(prompt)\n"
    )
    assert rules(check_builtin, src) == [(3, "PY3-BUILTIN")]


def test_builtin_named_method_does_not_leak_to_module_scope_elsewhere():
    src = (
        "class C(object):\n"
        "    def raw_input(self, prompt=\"\"):\n"
        "        pass\n"
        "x = raw_input('> ')\n"
    )
    assert rules(check_builtin, src) == [(4, "PY3-BUILTIN")]


def test_builtin_shadowed_by_from_import_as_is_not_found():
    # Independent check, round 2, item 3. Real repro: pip's vendored
    # urllib3/response.py does `from .packages.six import string_types
    # as basestring` (six's own Python-3 shim) and later reads the bare
    # name basestring - correctly the alias, not the real builtin. The
    # "import_as_name" parso node type ("from M import X as Y") was
    # never recognized as a binding at all - distinct from
    # "dotted_as_name" ("import X as Y"), which was - so the alias
    # target itself was flagged as a builtin use, and so was every
    # later bare reference to it.
    src = (
        "from six import string_types as basestring\n"
        "def f(body):\n"
        "    return isinstance(body, (basestring, bytes))\n"
    )
    assert rules(check_builtin, src) == []


def test_builtin_as_a_params_own_default_value_is_still_found():
    # Round-3 independent check, item 3. Real repro: CPython 2.7's own
    # json/encoder.py writes `def _make_iterencode(..., basestring=
    # basestring, ...):`, the "hand-optimized bytecode" trick of giving
    # a function a local fast-path to a builtin via a same-named
    # default value. The default value evaluates in the *enclosing*
    # scope, once, at def-statement time - it is not a reference inside
    # the function it initializes, even though _enclosing_funcdef used
    # to say it was (finding "basestring" already "local" there, as the
    # parameter itself).
    src = "def f(basestring=basestring):\n    pass\n"
    assert rules(check_builtin, src) == [(1, "PY3-BUILTIN")]


def test_builtin_as_a_params_default_value_still_excludes_the_param_itself():
    src = "def f(x=unicode):\n    pass\n"
    assert rules(check_builtin, src) == [(1, "PY3-BUILTIN")]


def test_builtin_named_import_source_aliased_away_is_not_found():
    # Round-3 independent check, item 3. Real repro: pip's vendored
    # html5lib does `from pip._vendor.six import unichr as chr` -
    # "unichr" is spelled exactly like the Python 2 builtin but names
    # six's own attribute, aliased to a different local name ("chr")
    # entirely; it is never looked up in this module's own scope at all.
    src = "from six import unichr as chr\nx = chr(65)\n"
    assert rules(check_builtin, src) == []


def test_builtin_named_module_aliased_away_is_not_found():
    src = "import unichr as u\n"
    assert rules(check_builtin, src) == []


def test_return_outside_function_is_found():
    assert rules(check_invalid_scope_use, "return 1\n") == [(1, "PY3-INVALID-SCOPE")]


def test_yield_outside_function_is_found():
    assert rules(check_invalid_scope_use, "yield 1\n") == [(1, "PY3-INVALID-SCOPE")]


def test_break_outside_loop_is_found():
    assert rules(check_invalid_scope_use, "break\n") == [(1, "PY3-INVALID-SCOPE")]


def test_continue_outside_loop_is_found():
    assert rules(check_invalid_scope_use, "continue\n") == [(1, "PY3-INVALID-SCOPE")]


def test_return_inside_function_is_not_found():
    assert rules(check_invalid_scope_use, "def f():\n    return 1\n") == []


def test_yield_inside_function_is_not_found():
    assert rules(check_invalid_scope_use, "def f():\n    yield 1\n") == []


def test_break_inside_loop_is_not_found():
    assert rules(check_invalid_scope_use, "for x in y:\n    break\n") == []


def test_continue_inside_while_loop_is_not_found():
    assert rules(check_invalid_scope_use, "while True:\n    continue\n") == []


def test_break_inside_one_line_while_loop_body_is_not_found():
    # parso puts a one-line loop body's simple_stmt directly where a
    # "suite" wrapper would otherwise be, with no suite-typed child at
    # all - _enclosing_loop_body must find it by position (right after
    # the loop's first ":"), not by searching for a child of type
    # "suite", or it raises StopIteration here (silently swallowed as
    # generator exhaustion on 2.7, an uncaught RuntimeError under
    # PEP 479 on 3.7+).
    assert rules(check_invalid_scope_use, "while True: break\n") == []


def test_continue_inside_one_line_for_loop_body_is_not_found():
    assert rules(check_invalid_scope_use, "for x in y: continue\n") == []


def test_return_inside_method_is_not_found():
    src = "class C(object):\n    def f(self):\n        return 1\n"
    assert rules(check_invalid_scope_use, src) == []


def test_break_inside_nested_function_within_a_loop_is_still_found():
    # Real repro (verified on real 2.7.18: SyntaxError): a nested def's
    # own body is a separate scope for break/continue purposes too - it
    # cannot break a loop it merely happens to be lexically written
    # inside, since the def could be called long after that loop ends.
    src = "for x in y:\n    def f():\n        break\n"
    assert rules(check_invalid_scope_use, src) == [(3, "PY3-INVALID-SCOPE")]


def test_break_inside_a_loops_else_clause_is_still_found():
    # Real repro (verified on real 2.7.18: SyntaxError): a for/while's
    # else-suite runs only after the loop completes normally, never
    # during iteration, so break/continue there do not refer to that
    # loop either.
    src = "for x in y:\n    pass\nelse:\n    break\n"
    assert rules(check_invalid_scope_use, src) == [(4, "PY3-INVALID-SCOPE")]


def test_return_inside_a_loop_inside_a_function_is_not_found():
    src = "def f():\n    for x in y:\n        break\n    return 1\n"
    assert rules(check_invalid_scope_use, src) == []


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


def test_metaclass_assignment_in_one_line_class_body_is_found():
    # parso puts a one-line class body's simple_stmt directly where a
    # "suite" wrapper would otherwise be - same shape as the one-line
    # loop body gap below.
    src = "class C(object): __metaclass__ = type\n"
    assert rules(check_metaclass, src) == [(1, "PY3-METACLASS")]


def test_other_assignment_in_one_line_class_body_is_not_found():
    src = "class C(object): x = 1\n"
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


def test_newly_found_universal_stdlib_removals_are_blockers():
    # Independent check, round 2, item 4: these eight were missing from
    # UNIVERSAL_STDLIB_MODULES despite `import NAME` failing on real
    # 2.7.18's own names across every judged version (3.6.15-3.15.1) -
    # found by sweeping the entire real Lib/ listing instead of relying
    # on PEP 3108 alone. Real repro: a file holding only `import hotshot`
    # got no finding at all before this fix.
    for name in ("bsddb", "dummy_thread", "hotshot", "os2emxpath",
                 "statvfs", "sunaudio", "toaiff", "xmllib"):
        assert rules(check_stdlib, "import %s\n" % name) == [(1, "PY3-STDLIB")], name


def test_macurl2path_removed_in_37_one_minor_before_macpath():
    tree, tokens = parsed("import macurl2path\n")
    findings = list(check_stdlib("m.py", tree, tokens, ((3, 6), (3, 7), (3, 8))))
    assert len(findings) == 1
    assert findings[0].versions == ((3, 7), (3, 8))


def test_dummy_threading_removed_in_39():
    tree, tokens = parsed("import dummy_threading\n")
    findings = list(check_stdlib("m.py", tree, tokens, ((3, 8), (3, 9), (3, 10))))
    assert len(findings) == 1
    assert findings[0].versions == ((3, 9), (3, 10))


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


def test_incomplete_u_escape_in_plain_string_is_found():
    # Real repro: CPython 2.7's own json/__init__.py docstring writes the
    # literal text "\\uXXXX" to describe a format, not to encode a
    # character - "XXXX" are not hex digits, so this is a SyntaxError
    # under Python 3's always-unicode plain str, but silently literal
    # text under Python 2's bytes-like plain str.
    assert rules(check_bad_unicode_escape, 'x = "escaped with \\uXXXX sequences"\n') == [
        (1, "PY3-BAD-ESCAPE"),
    ]


def test_complete_u_escape_in_plain_string_is_not_found():
    assert rules(check_bad_unicode_escape, 'x = "\\u0041"\n') == []


def test_incomplete_capital_u_escape_is_found():
    # \U needs exactly 8 hex digits; this has only 4 before a non-hex "X".
    assert rules(check_bad_unicode_escape, 'x = "\\U0041XYZ"\n') == [(1, "PY3-BAD-ESCAPE")]


def test_complete_capital_u_escape_is_not_found():
    assert rules(check_bad_unicode_escape, 'x = "\\U00010041"\n') == []


def test_incomplete_named_escape_is_found():
    assert rules(check_bad_unicode_escape, 'x = "\\N{}"\n') == [(1, "PY3-BAD-ESCAPE")]


def test_incomplete_escape_in_raw_string_is_not_found():
    assert rules(check_bad_unicode_escape, 'x = r"\\uXXXX"\n') == []


def test_incomplete_escape_in_byte_string_is_not_found():
    assert rules(check_bad_unicode_escape, 'x = b"\\uXXXX"\n') == []


def test_incomplete_escape_in_unicode_string_is_found():
    assert rules(check_bad_unicode_escape, 'x = u"\\uXXXX"\n') == [(1, "PY3-BAD-ESCAPE")]


def test_escaped_backslash_before_u_is_not_a_bad_escape():
    # "\\\\u1234" in source is an escaped backslash followed by the
    # literal text "u1234", never a \\u escape attempt.
    assert rules(check_bad_unicode_escape, 'x = "\\\\uXXXX"\n') == []


def test_ordinary_escapes_are_not_flagged():
    assert rules(check_bad_unicode_escape, 'x = "\\n\\t\\x41"\n') == []


def test_bytes_adjacent_to_plain_string_is_found():
    # Real repro (independent check's round-3 held-back battery): valid
    # Python 2.7 syntax (str and bytes are the same type there), a
    # SyntaxError on every judged Python 3 version ("cannot mix bytes
    # and nonbytes literals", confirmed on real 3.14.9).
    assert rules(check_mixed_bytes_literal, 'x = b"a" "b"\n') == [(1, "PY3-MIXED-STR-BYTES")]


def test_plain_string_adjacent_to_bytes_is_found():
    assert rules(check_mixed_bytes_literal, 'x = "a" b"b"\n') == [(1, "PY3-MIXED-STR-BYTES")]


def test_unicode_adjacent_to_bytes_is_found():
    assert rules(check_mixed_bytes_literal, 'x = u"a" b"b"\n') == [(1, "PY3-MIXED-STR-BYTES")]


def test_unicode_adjacent_to_plain_string_is_not_found():
    # Both are text in Python 3 (the bare u prefix is a no-op there);
    # only a bytes/non-bytes mismatch is the SyntaxError.
    assert rules(check_mixed_bytes_literal, 'x = u"a" "b"\n') == []


def test_two_bytes_literals_adjacent_is_not_found():
    assert rules(check_mixed_bytes_literal, 'x = b"a" b"b"\n') == []


def test_two_plain_strings_adjacent_is_not_found():
    assert rules(check_mixed_bytes_literal, 'x = "a" "b"\n') == []


def test_single_string_literal_is_not_found():
    assert rules(check_mixed_bytes_literal, 'x = b"a"\n') == []


def test_deep_nesting_below_threshold_is_not_found():
    source = "x = " + "(" * 40 + "1" + ")" * 40 + "\n"
    assert token_rules(check_deep_nesting, source) == []


def test_deep_nesting_above_threshold_is_found():
    source = "x = " + "(" * 150 + "1" + ")" * 150 + "\n"
    assert token_rules(check_deep_nesting, source) == [(1, "PY3-DEEP-NESTING")]


def test_deep_nesting_is_not_blocked_for_versions_past_38():
    source = "x = " + "(" * 150 + "1" + ")" * 150 + "\n"
    tree, tokens = parsed(source)
    findings = list(check_deep_nesting("m.py", tree, tokens, V))
    assert len(findings) == 1
    assert (3, 9) not in findings[0].versions
    assert (3, 6) in findings[0].versions and (3, 8) in findings[0].versions


def test_deep_nesting_mixed_bracket_types_is_found():
    source = "x = " + "[" * 150 + "1" + "]" * 150 + "\n"
    assert token_rules(check_deep_nesting, source) == [(1, "PY3-DEEP-NESTING")]


def test_deep_nesting_at_60_compiles_on_every_pre_39_version_and_is_not_found():
    # Real repro (independent check): real 3.6.15, 3.7.17 and 3.8.20 all
    # compile 60 levels of nesting fine (the real cutoff is 93 for the
    # first two, 99 for 3.8) -- the old flat threshold of 50 flagged this
    # as a blocker for all three, which R6/R7 forbid: a version that
    # really compiles the file must never be reported unready for it.
    source = "x = " + "(" * 60 + "1" + ")" * 60 + "\n"
    assert token_rules(check_deep_nesting, source) == []


def test_deep_nesting_just_below_each_versions_measured_cutoff_is_not_found():
    tree, tokens = parsed("x = " + "(" * 92 + "1" + ")" * 92 + "\n")
    findings = list(check_deep_nesting("m.py", tree, tokens, ((3, 6), (3, 7))))
    assert findings == []
    tree, tokens = parsed("x = " + "(" * 98 + "1" + ")" * 98 + "\n")
    findings = list(check_deep_nesting("m.py", tree, tokens, ((3, 8),)))
    assert findings == []


def test_deep_nesting_at_95_blocks_36_and_37_but_not_38():
    # Real repro (independent check): at 95 deep, real 3.8.20 still
    # compiles (its measured cutoff is 99), but real 3.6.15 and 3.7.17
    # both already fail (cutoff 93) -- the report must name exactly the
    # versions that are actually unready, not the whole gated set.
    source = "x = " + "(" * 95 + "1" + ")" * 95 + "\n"
    tree, tokens = parsed(source)
    findings = list(check_deep_nesting("m.py", tree, tokens, ((3, 6), (3, 7), (3, 8))))
    assert len(findings) == 1
    assert set(findings[0].versions) == set([(3, 6), (3, 7)])


def test_deep_nesting_at_99_blocks_all_three_pre_39_versions():
    source = "x = " + "(" * 99 + "1" + ")" * 99 + "\n"
    tree, tokens = parsed(source)
    findings = list(check_deep_nesting("m.py", tree, tokens, ((3, 6), (3, 7), (3, 8))))
    assert len(findings) == 1
    assert set(findings[0].versions) == set([(3, 6), (3, 7), (3, 8)])
