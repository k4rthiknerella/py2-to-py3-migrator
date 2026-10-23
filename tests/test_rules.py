# -*- coding: utf-8 -*-
import ast

from py2scan.rules import check_exec, check_print


def rules(fn, source):
    return [(f.line, f.rule) for f in fn("m.py", ast.parse(source))]


def test_print_statement_is_found():
    assert rules(check_print, "x = 1\nprint x\n") == [(2, "PY3-PRINT")]


def test_print_function_is_not_found():
    src = "from __future__ import print_function\nprint('x')\n"
    assert rules(check_print, src) == []


def test_exec_statement_is_found():
    assert rules(check_exec, "exec 'x = 1'\n") == [(1, "PY3-EXEC-STMT")]
