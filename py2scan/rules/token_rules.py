# -*- coding: utf-8 -*-
"""Rules that read a module's Python 2.7 token stream."""
import ast
import re
import tokenize

from py2scan.findings import Finding

_OCTAL_RE = re.compile(r"^0[0-7]+$")


def check_ne_op(path, tree, tokens):
    for toknum, tokval, start, end, line in tokens:
        if toknum == tokenize.OP and tokval == "<>":
            yield Finding(path, start[0], "PY3-NE-OP", "blocker",
                          "<> operator; Python 3 has only !=")


def check_octal(path, tree, tokens):
    for toknum, tokval, start, end, line in tokens:
        if toknum == tokenize.NUMBER:
            text = tokval[:-1] if tokval[-1:] in ("L", "l") else tokval
            if _OCTAL_RE.match(text):
                yield Finding(path, start[0], "PY3-OCTAL", "blocker",
                              "%s; old-style octal literal, Python 3 requires a 0o prefix" % tokval)


def check_long_suffix(path, tree, tokens):
    for toknum, tokval, start, end, line in tokens:
        if toknum == tokenize.NUMBER and tokval[-1:] in ("L", "l"):
            yield Finding(path, start[0], "PY3-LONG-SUFFIX", "blocker",
                          "%s; the long type and L suffix do not exist in Python 3" % tokval)


def check_except_comma(path, tree, tokens):
    n = len(tokens)
    i = 0
    while i < n:
        toknum, tokval, start, end, line = tokens[i]
        if toknum == tokenize.NAME and tokval == "except":
            except_line = start[0]
            depth = 0
            comma_found = False
            j = i + 1
            while j < n:
                t2, v2, s2, e2, l2 = tokens[j]
                if t2 == tokenize.OP:
                    if v2 in ("(", "[", "{"):
                        depth += 1
                    elif v2 in (")", "]", "}"):
                        depth -= 1
                    elif v2 == "," and depth == 0:
                        comma_found = True
                    elif v2 == ":" and depth == 0:
                        break
                elif t2 == tokenize.NEWLINE:
                    break
                j += 1
            if comma_found:
                yield Finding(path, except_line, "PY3-EXCEPT-COMMA", "blocker",
                              "except X, e:; Python 3 requires except X as e:")
            i = j
        i += 1


def _has_future_division(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            for alias in node.names:
                if alias.name == "division":
                    return True
    return False


def check_division(path, tree, tokens):
    if _has_future_division(tree):
        return
    for toknum, tokval, start, end, line in tokens:
        if toknum == tokenize.OP and tokval in ("/", "/="):
            yield Finding(path, start[0], "PY3-DIVISION", "warning",
                          "%s; true division is not the default without "
                          "from __future__ import division" % tokval)


TOKEN_RULES = [check_ne_op, check_octal, check_long_suffix, check_except_comma, check_division]
