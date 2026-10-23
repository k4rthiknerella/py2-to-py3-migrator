# -*- coding: utf-8 -*-
"""What the Python 3 detectors share: the Problem they report, positions,
CST walks and the facts that two rules need."""
from collections import namedtuple

from py2scan.py27 import ast27, grammar, symbol
from py2scan.versions import ALL, since, until

NONE = frozenset()
Problem = namedtuple("Problem", "line col message versions syntax")

# PEP 758: from 3.14 on, except A, B: catches A and B.
EXCEPT_COMMA = until((3, 13))


def problem(line, col, message, versions, decided=True):
    """A Problem whose versions cannot compile the file; with decided=False,
    py2scan blocks them without claiming that compile() fails."""
    return Problem(line, col, message, versions, versions if decided else NONE)


def leaves(node):
    """The tokens under a CST node, in source order."""
    found, stack = [], [node]
    while stack:
        n = stack.pop()
        if n.children is None:
            found.append(n)
        else:
            stack.extend(reversed(n.children))
    return found


def nodes(node, kinds):
    """The CST nodes of the given types under node, in source order."""
    found, stack = [], [node]
    while stack:
        n = stack.pop()
        if n.type in kinds:
            found.append(n)
        if n.children:
            stack.extend(reversed(n.children))
    return found


def first_leaf(node):
    while node.children:
        node = node.children[0]
    return node


def at(node):
    """(line, col) where a CST node starts."""
    leaf = first_leaf(node)
    return leaf.start_line, leaf.start_col


def cached(m, key, compute):
    if key not in m.cache:
        m.cache[key] = compute(m)
    return m.cache[key]


def _first_small_stmt(m):
    for stmt in stmt_children(m.result.cst):
        node = stmt.children[0]
        return node.children[0] if node.type == symbol.simple_stmt else node
    return None


def has_docstring(m):
    """Python 3's docstring test on the module's first statement: an
    expression that is a str literal; b'' is bytes in Python 3."""
    body = m.tree.body
    if not body or not isinstance(body[0], ast27.Expr) or not isinstance(body[0].value, ast27.Str):
        return False
    return not any("b" in string_prefix(leaf.value) for leaf in leaves(_first_small_stmt(m))
                   if leaf.type == grammar.STRING)


def string_prefix(value):
    """The lowercased prefix of a STRING token."""
    end = 0
    while value[end] not in "'\"":
        end += 1
    return value[:end].lower()


def leading_futures(m):
    """The from __future__ imports Python 3's future.c accepts: those before
    any other statement but one docstring."""
    found = []
    for i, stmt in enumerate(m.tree.body):
        if isinstance(stmt, ast27.ImportFrom) and stmt.module == "__future__" and not stmt.level:
            found.append(stmt)
        elif not (i == 0 and has_docstring(m)):
            break
    return found


def future_features(m):
    return cached(m, "futures", lambda m: set(a.name for s in leading_futures(m) for a in s.names))


def ne_syntax(m):
    """The versions <> stops: all of them, or with a leading
    from __future__ import barry_as_FLUFL, 3.6 to 3.11, whose compile() does
    not apply the import to the module it is in."""
    if "barry_as_FLUFL" in future_features(m):
        return until((3, 11))
    return ALL


BARRY_NE = since((3, 12))


def statement_syntax(m, node):
    from py2scan.py3 import grammar as py3grammar
    return py3grammar.statement_syntax(m, node)


def string_leaves(m):
    return [leaf for leaf in m.leaves if leaf.type == grammar.STRING]


def stmt_children(node):
    """A suite's or file_input's stmt nodes."""
    return [c for c in node.children or () if c.type == symbol.stmt]
