# -*- coding: utf-8 -*-
"""Errors Python 3's symbol table and compiler raise for 2.7 source:
return, yield, break and continue where they cannot be; duplicate
parameters; a parameter declared global; import * below module level; a
global statement after the name is used or bound in its scope; yield in a
comprehension (3.8 and later); except: before another handler; and
from __future__ imports that are late or name an unknown feature.

3.6 and 3.7 skip the compiler's (not the symbol table's) errors in code they
drop as dead; py2scan does not model that and claims those errors for them
too, a conservative verdict."""
from py2scan.py27 import ast27
from py2scan.py3.common import leading_futures, problem
from py2scan.versions import ALL, since

_FUNCTIONS = (ast27.FunctionDef, ast27.Lambda)
_COMPREHENSIONS = (ast27.ListComp, ast27.SetComp, ast27.DictComp, ast27.GeneratorExp)
_SCOPES = _FUNCTIONS + (ast27.ClassDef,)
_LOOPS = (ast27.For, ast27.While)
# Lib/__future__.py all_feature_names, as Python/future.c accepts them.
_FEATURES = frozenset(["nested_scopes", "generators", "division", "absolute_import", "with_statement",
                       "print_function", "unicode_literals", "barry_as_FLUFL", "generator_stop"])
_ANNOTATIONS = since((3, 7))
_YIELD_IN_COMPREHENSION = since((3, 8))


def _children(node):
    return list(ast27.iter_child_nodes(node))


def _comprehension_parts(node):
    """A comprehension's own scope: all but its first iterable."""
    parts = [g for g in node.generators]
    first = parts[0].iter
    inner = [x for g in parts for x in [g.target] + list(g.ifs) + ([g.iter] if g.iter is not first else [])]
    inner += [node.key, node.value] if isinstance(node, ast27.DictComp) else [node.elt]
    return first, inner


def _walk_flow(m):
    """(node, function?, loop?, in comprehension?) for every node, in source order."""
    stack = [(m.tree, False, False, False)]
    while stack:
        node, function, loop, comprehension = stack.pop()
        yield node, function, loop, comprehension
        stack.extend(reversed(_flow_children(node, function, loop, comprehension)))


def _flow_children(node, function, loop, comprehension):
    if isinstance(node, _FUNCTIONS):
        return [(c, True, False, False) for c in _children(node)]
    if isinstance(node, ast27.ClassDef):
        return [(c, False, False, False) for c in node.body] + \
            [(c, function, loop, comprehension) for c in node.bases + node.decorator_list]
    if isinstance(node, _COMPREHENSIONS):
        first, inner = _comprehension_parts(node)
        return [(first, function, loop, comprehension)] + [(c, function, False, True) for c in inner]
    if isinstance(node, _LOOPS):
        head = [node.target, node.iter] if isinstance(node, ast27.For) else [node.test]
        return [(c, function, loop, comprehension) for c in head] + \
            [(c, function, True, comprehension) for c in node.body] + \
            [(c, function, loop, comprehension) for c in node.orelse]
    return [(c, function, loop, comprehension) for c in _children(node)]


def check_flow(m):
    for node, function, loop, comprehension in _walk_flow(m):
        if isinstance(node, ast27.Return) and not function:
            yield problem(node.lineno, node.col_offset, "return outside a function; Python 3 rejects it", ALL)
        elif isinstance(node, ast27.Yield) and comprehension:
            yield problem(node.lineno, node.col_offset, "yield in a comprehension; Python 3.8 and later "
                          "reject it", _YIELD_IN_COMPREHENSION)
        elif isinstance(node, ast27.Yield) and not function:
            yield problem(node.lineno, node.col_offset, "yield outside a function; Python 3 rejects it", ALL)
        elif isinstance(node, (ast27.Break, ast27.Continue)) and not loop:
            yield problem(node.lineno, node.col_offset, "%s outside a loop; Python 3 rejects it"
                          % ("break" if isinstance(node, ast27.Break) else "continue"), ALL)
        elif isinstance(node, ast27.TryExcept):
            for handler in node.handlers[:-1]:
                if handler.type is None:
                    yield problem(handler.lineno, handler.col_offset, "except: before another handler; "
                                  "Python 3 needs it last", ALL)


def _parameter_names(args):
    names = []
    for arg in args.args:
        names.extend(n.id for n in ast27.walk(arg) if isinstance(n, ast27.Name))
    names.extend(n for n in (args.vararg, args.kwarg) if n)
    return names


def check_parameters(m):
    for node in m.of(*_FUNCTIONS):
        names = _parameter_names(node.args)
        seen = set()
        for name in names:
            if name in seen:
                yield problem(node.lineno, node.col_offset, "duplicate parameter %s; Python 3 rejects it" % name,
                              ALL)
            seen.add(name)
        body = node.body if isinstance(node, ast27.FunctionDef) else []
        for stmt in _own_statements(body):
            if isinstance(stmt, ast27.Global):
                for name in stmt.names:
                    if name in seen:
                        yield problem(stmt.lineno, stmt.col_offset, "%s is a parameter and global; Python 3 "
                                      "rejects it" % name, ALL)


def _own_statements(body):
    """The statements of a scope, nested blocks included, functions and classes not."""
    stack = list(reversed(body))
    while stack:
        stmt = stack.pop()
        yield stmt
        if not isinstance(stmt, _SCOPES):
            stack.extend(reversed([c for c in _children(stmt) if isinstance(c, (ast27.stmt_, ast27.excepthandler))]))


def check_star_imports(m):
    for node in m.of(*_SCOPES):
        body = node.body if not isinstance(node, ast27.Lambda) else []
        for stmt in _own_statements(body):
            if isinstance(stmt, ast27.ImportFrom) and any(a.name == "*" for a in stmt.names):
                yield problem(stmt.lineno, stmt.col_offset, "import * below module level; Python 3 rejects it",
                              ALL)


def _names_in(node):
    """Names a statement uses or binds in its own scope, in order, before
    its nested statements."""
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, ast27.Name):
            yield n.id
        elif isinstance(n, (ast27.FunctionDef, ast27.ClassDef)):
            yield n.name
            stack.extend(reversed(list(n.decorator_list) + (n.args.defaults if isinstance(n, ast27.FunctionDef)
                                                            else n.bases)))
            continue
        elif isinstance(n, ast27.Lambda):
            stack.extend(reversed(n.args.defaults))
            continue
        elif isinstance(n, _COMPREHENSIONS):
            stack.append(n.generators[0].iter)
            continue
        elif isinstance(n, (ast27.Import, ast27.ImportFrom)):
            continue
        elif isinstance(n, ast27.ExceptHandler):
            stack.extend(reversed([x for x in (n.type, n.name) if x is not None]))
            continue
        stack.extend(reversed([c for c in _children(n) if not isinstance(c, (ast27.stmt_, ast27.excepthandler))]))


def _global_problems(body):
    seen = set()
    for stmt in _own_statements(body):
        if isinstance(stmt, ast27.Global):
            for name in stmt.names:
                if name in seen:
                    yield problem(stmt.lineno, stmt.col_offset, "global %s after %s is used or bound; Python 3 "
                                  "rejects it" % (name, name), ALL)
        else:
            seen.update(_names_in(stmt))
            for handler in getattr(stmt, "handlers", ()):
                seen.update(_names_in(handler))


def check_globals(m):
    for found in _global_problems(m.tree.body):
        yield found
    for node in m.of(ast27.FunctionDef, ast27.ClassDef):
        for found in _global_problems(node.body):
            yield found


def check_futures(m):
    leading = set(id(s) for s in leading_futures(m))
    for node in m.of(ast27.ImportFrom):
        if node.module != "__future__" or node.level:
            continue
        if id(node) not in leading:
            yield problem(node.lineno, node.col_offset, "from __future__ import after other statements; "
                          "Python 3 rejects it", ALL)
            continue
        for alias in node.names:
            if alias.name == "annotations":
                yield problem(node.lineno, node.col_offset, "from __future__ import annotations; Python 3.6 "
                              "has no such feature", ALL - _ANNOTATIONS)
            elif alias.name not in _FEATURES:
                yield problem(node.lineno, node.col_offset, "from __future__ import %s; Python 3 has no such "
                              "feature" % alias.name, ALL)


_CONTINUE_IN_FINALLY = frozenset([(3, 6), (3, 7)])


def _continue_in_finally(body, in_finally):
    """continue statements whose way to their loop crosses a finally body."""
    stack = [(stmt, in_finally) for stmt in reversed(body)]
    while stack:
        stmt, under = stack.pop()
        if isinstance(stmt, ast27.Continue) and under:
            yield stmt
        elif isinstance(stmt, _LOOPS):
            stack.extend((s, False) for s in reversed(stmt.body))
            stack.extend((s, under) for s in reversed(stmt.orelse))
        elif isinstance(stmt, ast27.TryFinally):
            stack.extend((s, True) for s in reversed(stmt.finalbody))
            stack.extend((s, under) for s in reversed(stmt.body))
        elif not isinstance(stmt, _SCOPES):
            nested = [c for c in _children(stmt) if isinstance(c, (ast27.stmt_, ast27.excepthandler))]
            stack.extend((c, under) for c in reversed(nested))


def check_continue_in_finally(m):
    for stmt in _continue_in_finally(m.tree.body, False):
        yield problem(stmt.lineno, stmt.col_offset, "continue in a finally block; Python 3.6 and 3.7 reject it",
                      _CONTINUE_IN_FINALLY)


DETECTORS = [check_continue_in_finally, check_flow, check_parameters, check_star_imports, check_globals, check_futures]
