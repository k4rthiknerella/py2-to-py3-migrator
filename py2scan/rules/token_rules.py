# -*- coding: utf-8 -*-
"""Rules that read a module's Python 2.7 token stream.

Native `tokenize` (the pure-Python, regex-based lexer, not the strict C
parser behind ast.parse()/compile()) lexes most of these constructs
identically on a 2.7 host and a 3.x host, but two need a portability
shim because the token stream itself differs by host: check_long_suffix,
because Python 3's tokenizer splits "123L" into a NUMBER token "123" and
a separate NAME token "L" instead of one NUMBER token "123L"; and
check_ne_op, because whether "<>" lexes as one OP token or as two
adjacent OP tokens is not consistent even across different patches of
the same minor (see check_ne_op's own comment) -- both are detected by
checking adjacent tokens for a zero-width gap between them.
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


def check_ne_op(path, tree, tokens, versions):
    # Whether native tokenize lexes "<>" as one OP token or as two adjacent
    # OP tokens ("<" immediately followed by ">", no gap) is not a stable
    # per-version fact: empirically, 3.12.15 keeps the combined token,
    # every other judged minor's current patch (3.6-3.11, 3.13, 3.15rc)
    # splits it, and even 3.14 flips between patches (3.14.3 combined,
    # 3.14.9 split) -- an incidental tokenizer detail, not a documented
    # removal, so no version table would stay correct. Check both shapes.
    n = len(tokens)
    for i in range(n):
        toknum, tokval, start, end, line = tokens[i]
        if toknum == tokenize.OP and tokval == "<>":
            yield Finding(path, start[0], "PY3-NE-OP", "blocker",
                          "<> operator; Python 3 has only !=", versions)
        elif toknum == tokenize.OP and tokval == "<" and i + 1 < n:
            t2, v2, s2, e2, l2 = tokens[i + 1]
            if t2 == tokenize.OP and v2 == ">" and s2 == end:
                yield Finding(path, start[0], "PY3-NE-OP", "blocker",
                              "<> operator; Python 3 has only !=", versions)


def check_octal(path, tree, tokens, versions):
    for toknum, tokval, start, end, line in tokens:
        if toknum == tokenize.NUMBER:
            text = tokval[:-1] if tokval[-1:] in ("L", "l") else tokval
            if _OCTAL_RE.match(text):
                yield Finding(path, start[0], "PY3-OCTAL", "blocker",
                              "%s; old-style octal literal, Python 3 requires a 0o prefix" % tokval,
                              versions)


def check_long_suffix(path, tree, tokens, versions):
    n = len(tokens)
    for i in range(n):
        toknum, tokval, start, end, line = tokens[i]
        if toknum != tokenize.NUMBER:
            continue
        if tokval[-1:] in ("L", "l"):
            yield Finding(path, start[0], "PY3-LONG-SUFFIX", "blocker",
                          "%s; the long type and L suffix do not exist in Python 3" % tokval,
                          versions)
        elif i + 1 < n:
            t2, v2, s2, e2, l2 = tokens[i + 1]
            if t2 == tokenize.NAME and v2 in ("L", "l") and s2 == end:
                message = "%s; the long type and L suffix do not exist in Python 3" % (tokval + v2)
                yield Finding(path, start[0], "PY3-LONG-SUFFIX", "blocker", message, versions)


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


def check_except_comma(path, tree, tokens, versions):
    n = len(tokens)
    i = 0
    while i < n:
        toknum, tokval, start, end, line = tokens[i]
        if toknum == tokenize.NAME and tokval == "except":
            comma_found, i = _except_header_end(tokens, i + 1)
            if comma_found:
                yield Finding(path, start[0], "PY3-EXCEPT-COMMA", "blocker",
                              "except X, e:; Python 3 requires except X as e:", versions)
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


def check_division(path, tree, tokens, versions):
    if _has_future_division(tree):
        return
    for toknum, tokval, start, end, line in tokens:
        if toknum == tokenize.OP and tokval in ("/", "/="):
            yield Finding(path, start[0], "PY3-DIVISION", "warning",
                          "%s; true division is not the default without "
                          "from __future__ import division" % tokval, versions)


_NESTING_OPEN = frozenset(["(", "[", "{"])
_NESTING_CLOSE = frozenset([")", "]", "}"])
_DEEP_NESTING_VERSIONS = frozenset([(3, 6), (3, 7), (3, 8)])
# Conservative: empirically, real 3.6.15/3.7.17/3.8.20 compile fine up to
# depth 90 and start failing by depth 95-99 (checked via `docker run
# python:X-slim`, a direct py_compile.compile() against a generated
# nested-parens file at each depth). The true cutoff is a C stack depth,
# not a language rule -- it can shift with the platform's stack size --
# so this flags well below the observed failure point rather than at it.
_DEEP_NESTING_THRESHOLD = 50


def check_deep_nesting(path, tree, tokens, versions):
    """CPython 3.6-3.8's old pgen2-based compiler has a fixed symbol-table
    stack depth (`s_push` in symtable.c); deeply nested brackets overflow
    it with a MemoryError, not a SyntaxError, but R1 treats any failure
    to compile the same way. 3.9's PEG parser removed this limit (real
    3.9.25 through 3.15.1 compile depth 200 nesting fine, checked the
    same way). Real CPython 2.7.18 has the *same* kind of limit and fails
    too at this depth -- irrelevant to this rule, which only tracks
    whether Python 3 can compile it, not 2.7."""
    gated = tuple(v for v in versions if v in _DEEP_NESTING_VERSIONS)
    if not gated:
        return
    depth = 0
    max_depth = 0
    start = None
    for toknum, tokval, tok_start, end, line in tokens:
        if toknum != tokenize.OP:
            continue
        if tokval in _NESTING_OPEN:
            depth += 1
            if depth > max_depth:
                max_depth = depth
                start = tok_start
        elif tokval in _NESTING_CLOSE:
            depth = max(0, depth - 1)
    if max_depth > _DEEP_NESTING_THRESHOLD:
        yield Finding(path, start[0] if start else 1, "PY3-DEEP-NESTING", "blocker",
                      "%d levels of nested brackets; may exceed Python "
                      "3.6-3.8's parser stack depth" % max_depth, gated)


TOKEN_RULES = [check_ne_op, check_octal, check_long_suffix, check_except_comma, check_division,
               check_deep_nesting]
