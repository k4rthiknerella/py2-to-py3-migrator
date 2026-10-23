# -*- coding: utf-8 -*-
"""What Python 3 reads differently in a module's tokens: string prefixes and
escapes, bytes literals, adjacent literals, the ellipsis, long decimal
integers, indentation, and a line continuation at the end of the file."""
import re

from py2scan.py27 import grammar, symbol
from py2scan.py27.parser import CO_FUTURE_UNICODE_LITERALS
from py2scan.py3 import names
from py2scan.py3.common import (
    BARRY_NE, NONE, future_features, problem, string_leaves, string_prefix)
from py2scan.versions import ALL, VERSIONS, since

# sys.int_info.default_max_str_digits: 3.7.17, 3.8.20, 3.9.25 and 3.10.19 carry
# the limit's backport (CVE-2020-10735), 3.11 and later have it; 3.6.15 does not.
MAX_STR_DIGITS = 4300
_LONG_INT = since((3, 7))
_DECIMAL = re.compile(r"[1-9][0-9]*\Z")
_HEX = frozenset("0123456789abcdefABCDEF")


def position(leaf, offset):
    """(line, col) of the character at offset in a token's text."""
    before = leaf.value[:offset]
    newlines = before.count("\n")
    if not newlines:
        return leaf.start_line, leaf.start_col + offset
    return leaf.start_line + newlines, offset - before.rfind("\n") - 1


def split(value):
    """(lowercased prefix, offset of the body, body) of a STRING token."""
    prefix = string_prefix(value)
    quote = value[len(prefix):len(prefix) + 3]
    if quote not in ('"""', "'''"):
        quote = quote[0]
    start = len(prefix) + len(quote)
    return prefix, start, value[start:len(value) - len(quote)]


def check_prefix(m):
    for leaf in string_leaves(m):
        if string_prefix(leaf.value) == "ur":
            yield problem(leaf.start_line, leaf.start_col, "ur'' string prefix; Python 3 has no ur prefix", ALL)


def _hex_escape(body, i, digits):
    """The versions a \\u or \\U escape at body[i] stops: all, when it is short
    or names no code point."""
    text = body[i + 2:i + 2 + digits]
    if len(text) < digits or not set(text) <= _HEX:
        return ALL, "truncated \\%s escape" % body[i + 1]
    if int(text, 16) > 0x10FFFF:
        return ALL, "\\%s escape beyond U+10FFFF" % body[i + 1]
    return NONE, None


def _named_escape(body, i):
    """(end, versions, reason) for the \\N escape at body[i]."""
    j = i + 2
    if j < len(body) and body[j] == "{":
        close = body.find("}", j + 1)
        if close < 0:
            return len(body), ALL, "malformed \\N escape"
        if close == j + 1:
            return close + 1, ALL, "malformed \\N escape"
        return close + 1, names.unknown(body[j + 1:close]), "unknown \\N{%s} escape" % body[j + 1:close]
    return j, ALL, "malformed \\N escape"


def escapes(body, text27):
    """(offset, versions, reason) of each escape Python 3 rejects in a str
    literal's body; text27 when 2.7 already decoded it as unicode."""
    i = body.find("\\")
    while i >= 0:
        end, versions, reason = i + 2, NONE, None
        kind = body[i + 1]
        if kind == "N":
            end, versions, reason = _named_escape(body, i)
        elif kind in "uU" and not text27:
            versions, reason = _hex_escape(body, i, 4 if kind == "u" else 8)
        if versions:
            yield i, versions, reason
        i = body.find("\\", end)


def check_escapes(m):
    unicode_literals = m.result.flags & CO_FUTURE_UNICODE_LITERALS
    for leaf in string_leaves(m):
        prefix, start, body = split(leaf.value)
        if "b" in prefix or "r" in prefix:
            continue
        for offset, versions, reason in escapes(body, "u" in prefix or unicode_literals):
            line, col = position(leaf, start + offset)
            yield problem(line, col, "%s in a str literal; Python 3 reads it as text" % reason, versions)


def check_bytes(m):
    for leaf in string_leaves(m):
        if "b" in string_prefix(leaf.value) and any(c >= u"\x80" for c in leaf.value):
            yield problem(leaf.start_line, leaf.start_col,
                          "non-ASCII character in a bytes literal; Python 3 allows only ASCII there", ALL)


def check_concatenation(m):
    atoms = dict((id(m.parent[id(leaf)]), m.parent[id(leaf)]) for leaf in string_leaves(m))
    for atom in atoms.values():
        kinds = set("b" in string_prefix(leaf.value) for leaf in atom.children)
        if len(kinds) > 1:
            first = atom.children[0]
            yield problem(first.start_line, first.start_col,
                          "bytes and str literals side by side; Python 3 cannot join them", ALL)


def check_ellipsis(m):
    for leaf in m.leaves:
        if leaf.type != grammar.DOT or m.parent[id(leaf)].type != symbol.subscript:
            continue
        dots = m.parent[id(leaf)].children
        if leaf is not dots[0]:
            continue
        spots = [(d.start_line, d.start_col) for d in dots]
        if spots != [(spots[0][0], spots[0][1] + k) for k in range(3)]:
            yield problem(leaf.start_line, leaf.start_col, "... with space between the dots; Python 3 needs ...",
                          ALL)


def check_long_int(m):
    for leaf in m.leaves:
        if leaf.type == grammar.NUMBER and len(leaf.value) > MAX_STR_DIGITS and _DECIMAL.match(leaf.value):
            yield problem(leaf.start_line, leaf.start_col,
                          "integer literal of %d digits; Python 3.7 and later accept at most %d"
                          % (len(leaf.value), MAX_STR_DIGITS), _LONG_INT)


def check_barry_ne(m):
    if "barry_as_FLUFL" not in future_features(m):
        return
    for leaf in m.leaves:
        if leaf.type == grammar.NOTEQUAL and leaf.value == "!=":
            yield problem(leaf.start_line, leaf.start_col,
                          "!= under from __future__ import barry_as_FLUFL; Python 3.12 and later need <>",
                          BARRY_NE)


def _indent3(stack, col, altcol):
    """tok_get's indentation step in Python 3: ("same" | "indent" | the depth
    after a dedent), or None for TabError or IndentationError."""
    top, alttop = stack[-1]
    if col == top:
        return "same" if altcol == alttop else None
    if col > top:
        if altcol <= alttop:
            return None
        stack.append((col, altcol))
        return "indent"
    while len(stack) > 1 and col < stack[-1][0]:
        stack.pop()
    return len(stack) if stack[-1] == (col, altcol) else None


def _indent27(stack, col):
    """The same step in 2.7, which parsed the file: no TabError."""
    if col == stack[-1]:
        return "same"
    if col > stack[-1]:
        stack.append(col)
        return "indent"
    while len(stack) > 1 and col < stack[-1]:
        stack.pop()
    return len(stack)


def _python3_indents(indents):
    """The first line whose indentation Python 3 rejects or reads as another
    block structure than 2.7 did, or None. Python 3 counts a tab as 8 columns
    whatever the file's editor settings say, and rejects indentation whose
    meaning depends on the width of a tab (TabError)."""
    stack3, stack27 = [(0, 0)], [0]
    for line, col, altcol, col27 in indents:
        step = _indent3(stack3, col, altcol)
        if step is None or step != _indent27(stack27, col27):
            return line
    return None


def check_indentation(m):
    line = _python3_indents(m.result.tokenizer.indents)
    if line is not None:
        yield problem(line, 0, "indentation Python 3 reads differently: it counts a tab as 8 columns and "
                      "rejects tabs and spaces whose meaning depends on the tab width", ALL)


def _eof_continuation(m):
    """The versions whose text ends with the 2.7 tokenizer's last line
    continuation: 3.6 to 3.11 translate newlines as 2.7 does, adding a second
    newline to text that ends in \\r\\n; 3.12 and later do not."""
    at = m.result.tokenizer.continuation
    if at is None:
        return NONE
    size = len(m.result.text)
    size12 = size - 1 if m.source.endswith(b"\r\n") else size
    return frozenset(v for v in VERSIONS if v >= (3, 8) and at + 2 == (size if v < (3, 12) else size12))


def check_eof_continuation(m):
    versions = _eof_continuation(m)
    if versions:
        text = m.result.text
        line = text.count("\n", 0, m.result.tokenizer.continuation) + 1
        yield problem(line, 0, "line continuation at the end of the file; Python 3.8 and later reject it",
                      versions)


DETECTORS = [check_prefix, check_escapes, check_bytes, check_concatenation, check_ellipsis, check_long_int,
             check_barry_ne, check_indentation, check_eof_continuation]
