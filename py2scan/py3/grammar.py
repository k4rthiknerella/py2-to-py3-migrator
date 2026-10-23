# -*- coding: utf-8 -*-
"""2.7 grammar that Python 3's rejects: tuple parameters, 2.7-only list
comprehension iterables, lambdas in comprehension conditions (3.9 and later),
except targets that are not a name, generator expressions beside other
arguments, parenthesized keyword names (3.8 and later), 3.6's limit of 255
arguments, and print and exec statements, which Python 3 reads as
expressions when it can."""
from py2scan.py27 import ast27, grammar, symbol
from py2scan.py27.parser import ParseResult, Py27SyntaxError, _Parser
from py2scan.py27.tokenizer import E_DONE, E_OK
from py2scan.py3.common import at, leaves, nodes, problem
from py2scan.versions import ALL, between, since

_PY36 = between((3, 6), (3, 6))
_MAX_ARGS = 255
_COMPREHENSION_IF = since((3, 9))
_TRAILING_COMMA = since((3, 7))
_KEYWORD_PARENS = since((3, 8))


def check_tuple_params(m):
    for fpdef in nodes(m.result.cst, (symbol.fpdef,)):
        if fpdef.children[0].type == grammar.LPAR:
            line, col = at(fpdef)
            yield problem(line, col, "tuple parameter; Python 3 has none (PEP 3113)", ALL)


def _is_lambda(old_test):
    return old_test.children[0].type == symbol.old_lambdef


def check_list_comprehensions(m):
    for list_for in nodes(m.result.cst, (symbol.list_for,)):
        safe = list_for.children[3]
        tests = [c for c in safe.children if c.type == symbol.old_test]
        if len(safe.children) > 1 or any(_is_lambda(t) for t in tests):
            line, col = at(safe)
            yield problem(line, col, "list comprehension over an unparenthesized tuple or lambda; Python 3 "
                          "needs parentheses", ALL)
    for clause in nodes(m.result.cst, (symbol.list_if, symbol.comp_if)):
        if _is_lambda(clause.children[1]):
            line, col = at(clause.children[1])
            yield problem(line, col, "lambda as a comprehension condition; Python 3.9 and later need "
                          "parentheses", _COMPREHENSION_IF)


def check_except_targets(m):
    for clause in m.except_clauses:
        if len(clause.children) > 3 and clause.children[2].value == "as" and len(leaves(clause.children[3])) > 1:
            line, col = at(clause.children[3])
            yield problem(line, col, "except ... as target that is not a name; Python 3 needs a name", ALL)


def _argument_kinds(arglist):
    """(arguments, generator expressions, 1 for each of *args and **kwargs)."""
    args = [c for c in arglist.children if c.type == symbol.argument]
    gens = [a for a in args if len(a.children) == 2 and a.children[1].type == symbol.comp_for]
    stars = [c for c in arglist.children if c.type in (grammar.STAR, grammar.DOUBLESTAR)]
    return args, gens, stars


def _generator_problem(arglist, args, gens, stars):
    if not gens:
        return None
    line, col = at(gens[0])
    if len(args) > 1 or stars:
        return problem(line, col, "generator expression beside other arguments; Python 3 needs it in "
                       "parentheses", ALL)
    if arglist.children[-1].type == grammar.COMMA:
        return problem(line, col, "generator expression with a trailing comma; Python 3.7 and later need it "
                       "in parentheses", _TRAILING_COMMA)
    return None


def arglist_problems(root):
    for arglist in nodes(root, (symbol.arglist,)):
        args, gens, stars = _argument_kinds(arglist)
        found = _generator_problem(arglist, args, gens, stars)
        if found:
            yield found
        if len(args) + len(stars) > _MAX_ARGS:
            line, col = at(arglist)
            yield problem(line, col, "call with more than 255 arguments; Python 3.6 rejects it", _PY36)
        for arg in args:
            if len(arg.children) == 3 and len(leaves(arg.children[0])) > 1:
                line, col = at(arg)
                yield problem(line, col, "keyword argument whose name is in parentheses; Python 3.8 and "
                              "later reject it", _KEYWORD_PARENS)


def check_arguments(m):
    return arglist_problems(m.result.cst)


def check_parameter_counts(m):
    for node in m.nodes:
        if isinstance(node, ast27.arguments) and len(node.args) > _MAX_ARGS:
            first = node.args[0]
            yield problem(first.lineno, first.col_offset, "more than 255 parameters; Python 3.6 rejects them",
                          _PY36)
        elif isinstance(node, ast27.ClassDef) and len(node.bases) > _MAX_ARGS:
            yield problem(node.lineno, node.col_offset, "more than 255 base classes; Python 3.6 rejects them",
                          _PY36)


class _Reparser(_Parser):
    """2.7's parser with print and exec as plain names, as Python 3 has them."""

    def classify(self, kind, value):
        if kind == grammar.NAME and value in ("print", "exec"):
            return self.g.token_labels.get(grammar.NAME, -1)
        return _Parser.classify(self, kind, value)


def _reparse(m, stmt):
    """The CST of a print or exec statement read as an expression statement,
    or None when Python 3's grammar has no such expression."""
    p = _Reparser(grammar.grammar())
    p.flags = m.result.flags
    tokens = [(t.type, t.value, (t.lineno, t.col, t.start_line, t.start_col)) for t in leaves(stmt)]
    last = tokens[-1][2]
    tokens += [(grammar.NEWLINE, "\n", last), (grammar.ENDMARKER, "", last)]
    for kind, value, pos in tokens:
        code = p.add_token(kind, value, pos)
        if code == E_DONE:
            break
        if code != E_OK:
            return None
    try:
        ast27.build(ParseResult(p.root, m.result.encoding, m.result.flags, None, None))
    except Py27SyntaxError:
        return None
    return p.root


def _statement(m, node):
    index = m.cache.get("statements")
    if index is None:
        index = m.cache["statements"] = dict(
            ((leaf.lineno, leaf.col), m.parent[id(leaf)]) for leaf in m.leaves
            if leaf.type == grammar.NAME and leaf.value in ("print", "exec"))
    return index.get((node.lineno, node.col_offset))


def statement_syntax(m, node):
    """The versions that cannot compile a print or exec statement: all, unless
    Python 3 reads it as an expression with print or exec a name, as in
    print (x) or exec (code) in ns; then only those that reject that
    expression's calls."""
    stmt = _statement(m, node)
    root = _reparse(m, stmt) if stmt is not None else None
    if root is None:
        return ALL
    versions = frozenset()
    for found in arglist_problems(root):
        versions |= found.versions
    return versions


DETECTORS = [check_tuple_params, check_list_comprehensions, check_except_targets, check_arguments,
             check_parameter_counts]
