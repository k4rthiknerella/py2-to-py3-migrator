# -*- coding: utf-8 -*-
"""Names that are keywords, or reserved, in Python 3: True, False and None
anywhere but as a value; nonlocal; async and await (3.7 and later);
__peg_parser__ (3.9); and the forms of __debug__ that 2.7 allows but later
versions reject."""
from py2scan.py27 import ast27, grammar, symbol
from py2scan.py3.common import problem
from py2scan.versions import ALL, between, since, until

_CONSTANTS = frozenset(["True", "False", "None"])
_NAMES = {
    "nonlocal": ALL,
    "async": since((3, 7)),
    "await": since((3, 7)),
    "__peg_parser__": between((3, 9), (3, 9)),
}
_DECORATOR_NAME = until((3, 8))  # PEP 614: from 3.9 a decorator is any expression


def _constant_versions(m, leaf):
    """The versions that reject True, False or None at this token: none where
    it is a value (an atom), the 3.6 to 3.8 grammar where it starts a
    decorator, all of them elsewhere."""
    parent = m.parent[id(leaf)]
    if parent.type == symbol.atom:
        return None
    if parent.type == symbol.dotted_name and parent.children[0] is leaf and \
            m.parent[id(parent)].type == symbol.decorator:
        return _DECORATOR_NAME
    return ALL


def _token_problems(m):
    for leaf in m.leaves:
        if leaf.type != grammar.NAME:
            continue
        if leaf.value in _CONSTANTS:
            versions = _constant_versions(m, leaf)
        else:
            versions = _NAMES.get(leaf.value)
        if versions:
            yield problem(leaf.start_line, leaf.start_col,
                          "%s used as a name; it is a keyword in Python 3" % leaf.value, versions)


def _debug_problems(m):
    for node in m.nodes:
        if isinstance(node, ast27.Name) and node.id == "__debug__" and isinstance(node.ctx, ast27.Del):
            yield problem(node.lineno, node.col_offset, "del __debug__; Python 3.10 and later reject it",
                          since((3, 10)))
        elif isinstance(node, ast27.Attribute) and node.attr == "__debug__" and isinstance(node.ctx, ast27.Del):
            yield problem(node.lineno, node.col_offset, "del of an attribute named __debug__; Python 3.14 and "
                          "later reject it", since((3, 14)))
        elif isinstance(node, ast27.Import):
            for alias in node.names:
                if alias.asname is None and alias.name.split(".")[0] == "__debug__":
                    yield problem(node.lineno, node.col_offset, "import %s binds __debug__; Python 3.9 and "
                                  "later reject it" % alias.name, since((3, 9)))


def _constant_targets(m):
    for node in m.nodes:
        if isinstance(node, ast27.Name) and node.id in _CONSTANTS and not isinstance(node.ctx, ast27.Load):
            yield problem(node.lineno, node.col_offset, "assignment to %s; it is a keyword in Python 3" % node.id,
                          ALL)
        elif isinstance(node, ast27.keyword) and node.arg in _CONSTANTS:
            value = node.value
            yield problem(value.lineno, value.col_offset, "keyword argument named %s; it is a keyword in "
                          "Python 3" % node.arg, ALL)


def check_keywords(m):
    seen = set()
    for found in list(_token_problems(m)) + list(_constant_targets(m)) + list(_debug_problems(m)):
        if (found.line, found.col, found.versions) not in seen:
            seen.add((found.line, found.col, found.versions))
            yield found


DETECTORS = [check_keywords]
