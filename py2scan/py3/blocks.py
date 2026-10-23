# -*- coding: utf-8 -*-
"""Statically nested blocks: Python 3's compiler allows 20 (CO_MAXBLOCKS; 21
from 3.12), and each construct costs a version-dependent number of them;
3.9 and later also copy finally bodies at every exit, which grows
exponentially with nesting. py2scan does not yet model the costs per
version: past a nesting weight no tested construct reaches below its
limit, it blocks every version without claiming that compile() fails."""
from py2scan.py27 import ast27
from py2scan.py3.common import problem
from py2scan.versions import ALL

_WEIGHT_LIMIT = 9


def _weight(node):
    if isinstance(node, (ast27.For, ast27.While)):
        return 1
    if isinstance(node, ast27.With):
        return 2
    if isinstance(node, (ast27.TryExcept, ast27.TryFinally)):
        return 2
    return 0


def check_blocks(m):
    stack = [(m.tree, 0)]
    while stack:
        node, depth = stack.pop()
        if isinstance(node, (ast27.FunctionDef, ast27.ClassDef, ast27.Lambda)) and node is not m.tree:
            depth = 0
        depth += _weight(node)
        if depth > _WEIGHT_LIMIT:
            yield problem(node.lineno, node.col_offset, "deeply nested blocks; py2scan cannot tell that Python 3 "
                          "compiles them within its block limit", ALL, decided=False)
            return
        stack.extend((c, depth) for c in ast27.iter_child_nodes(node))


DETECTORS = [check_blocks]
