# -*- coding: utf-8 -*-
"""Rules that read a module's Python 2.7 token stream.

Native `tokenize` (the pure-Python, regex-based lexer, not the strict C
parser behind ast.parse()/compile()) already lexes every one of these
constructs identically on a 2.7 host and a 3.x host, so these rules need
no portability shim beyond check_long_suffix: Python 3's tokenizer splits
"123L" into a NUMBER token "123" and a separate NAME token "L" instead of
one NUMBER token "123L", so that one case is detected across two tokens.
"""
import re
import tokenize

from py2scan.findings import Finding

_OCTAL_RE = re.compile(r"^0[0-7]+$")


def _walk(node):
    yield node
    for c in getattr(node, "children", ()):
        for n in _walk(c):
            yield n


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
    n = len(tokens)
    for i in range(n):
        toknum, tokval, start, end, line = tokens[i]
        if toknum != tokenize.NUMBER:
            continue
        if tokval[-1:] in ("L", "l"):
            yield Finding(path, start[0], "PY3-LONG-SUFFIX", "blocker",
                          "%s; the long type and L suffix do not exist in Python 3" % tokval)
        elif i + 1 < n:
            t2, v2, s2, e2, l2 = tokens[i + 1]
            if t2 == tokenize.NAME and v2 in ("L", "l") and s2 == end:
                message = "%s; the long type and L suffix do not exist in Python 3" % (tokval + v2)
                yield Finding(path, start[0], "PY3-LONG-SUFFIX", "blocker", message)


def _except_header_end(tokens, start):
    """Scan tokens[start:] for the end of an except header (its ':' or a
    NEWLINE if the header is malformed). Returns (comma_found, end_index)
    where comma_found means a top-level comma preceded the end - the old
    except X, e: form."""
    n = len(tokens)
    depth = 0
    comma_found = False
    j = start
    while j < n:
        toknum, tokval = tokens[j][0], tokens[j][1]
        if toknum == tokenize.NEWLINE:
            break
        if toknum == tokenize.OP:
            if tokval in ("(", "[", "{"):
                depth += 1
            elif tokval in (")", "]", "}"):
                depth -= 1
            elif depth == 0 and tokval == ",":
                comma_found = True
            elif depth == 0 and tokval == ":":
                break
        j += 1
    return comma_found, j


def check_except_comma(path, tree, tokens):
    n = len(tokens)
    i = 0
    while i < n:
        toknum, tokval, start, end, line = tokens[i]
        if toknum == tokenize.NAME and tokval == "except":
            comma_found, i = _except_header_end(tokens, i + 1)
            if comma_found:
                yield Finding(path, start[0], "PY3-EXCEPT-COMMA", "blocker",
                              "except X, e:; Python 3 requires except X as e:")
        i += 1


def _has_future_division(tree):
    for node in _walk(tree):
        if node.type != "import_from":
            continue
        children = node.children
        if getattr(children[1], "value", None) != "__future__":
            continue
        import_idx = None
        for i, c in enumerate(children):
            if getattr(c, "value", None) == "import":
                import_idx = i
                break
        if import_idx is None:
            continue
        for c in children[import_idx + 1:]:
            for leaf in _walk(c):
                if getattr(leaf, "value", None) == "division":
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
