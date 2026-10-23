# -*- coding: utf-8 -*-
"""Rules that read a module's Python 2.7 AST."""
import ast

from py2scan.findings import Finding


def _nodes(tree, kind):
    for node in ast.walk(tree):
        if isinstance(node, kind):
            yield node


def check_print(path, tree):
    for node in _nodes(tree, ast.Print):
        yield Finding(path, node.lineno, "PY3-PRINT", "blocker",
                      "print statement; Python 3 has only the print() function")


def check_exec(path, tree):
    for node in _nodes(tree, ast.Exec):
        yield Finding(path, node.lineno, "PY3-EXEC-STMT", "blocker",
                      "exec statement; Python 3 has only the exec() function")


AST_RULES = [check_print, check_exec]
