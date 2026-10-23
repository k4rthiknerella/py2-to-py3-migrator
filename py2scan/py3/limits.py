# -*- coding: utf-8 -*-
"""Nesting that exhausts a Python 3 version's parser stack (3.6 and 3.7) or
recursion limit, or its memory. py2scan does not yet model each version's
limit: past a depth the tested ones all survive, it blocks every version
without claiming that compile() fails."""
from py2scan.py27 import ast27
from py2scan.py3.common import problem
from py2scan.versions import ALL

_DEPTH_LIMIT = 85  # nested brackets: 3.6 and 3.7 fail from 88 calls or 93 parentheses
_CHAIN_LIMIT = 900  # operands, attributes, calls or subscripts in one chain
_COMPARE_LIMIT = 10000


def _depths(m):
    """(node, nesting of brackets, length of the left-leaning chain) for each AST node."""
    stack = [(m.tree, 0, 0)]
    while stack:
        node, brackets, chain = stack.pop()
        yield node, brackets, chain
        for child in ast27.iter_child_nodes(node):
            nested = isinstance(child, (ast27.Tuple, ast27.List, ast27.Dict, ast27.Set, ast27.Call,
                                        ast27.ListComp, ast27.GeneratorExp, ast27.SetComp, ast27.DictComp))
            stack.append((child, brackets + nested, chain + 1))


def _bracket_depth(m):
    depth = deepest = 0
    for kind, value, _, _ in m.tokens:
        if value in ("(", "[", "{"):
            depth += 1
            deepest = max(deepest, depth)
        elif value in (")", "]", "}"):
            depth -= 1
    return deepest


def check_limits(m):
    if _bracket_depth(m) > _DEPTH_LIMIT:
        yield problem(1, 0, "deeply nested brackets; py2scan cannot tell that every Python 3 version parses "
                      "them", ALL, decided=False)
        return
    for node, brackets, chain in _depths(m):
        too_deep = brackets > _DEPTH_LIMIT or chain > _CHAIN_LIMIT
        if too_deep or (isinstance(node, ast27.Compare) and len(node.ops) > _COMPARE_LIMIT):
            line = getattr(node, "lineno", 1)
            yield problem(line, getattr(node, "col_offset", 0), "deeply nested expression; py2scan cannot tell "
                          "that every Python 3 version compiles it", ALL, decided=False)
            return


DETECTORS = [check_limits]
