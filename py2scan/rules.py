# -*- coding: utf-8 -*-
"""Rules that read a module's Python 2.7 AST and concrete syntax tree.

The AST cannot tell `except X, e` from `except X as e`, or `<>` from `!=`, so
those rules read tokens from the CST that the same 2.7 parser builds. Each
rule yields (line, col, message) for every occurrence.
"""
import ast
import re
import symbol
import token
from collections import OrderedDict, namedtuple

BLOCKER = "blocker"
WARNING = "warning"

Rule = namedtuple("Rule", "id severity title")

RULES = OrderedDict()
_CHECKS = []


def rule(rule_id, title, severity=BLOCKER):
    def register(check):
        RULES[rule_id] = Rule(rule_id, severity, title)
        _CHECKS.append((rule_id, check))
        return check
    return register


# Reported by the scanner, in place of every other rule, when a file does not parse.
RULES["PY3-PARSE"] = Rule("PY3-PARSE", BLOCKER, "does not parse under Python 2.7")


class Module(object):
    """A parsed module: its AST nodes, its CST tokens and its except clauses."""

    def __init__(self, tree, cst):
        self.tree = tree
        self.nodes = list(ast.walk(tree))
        self.tokens = []  # (type, string, line, col)
        self.except_clauses = []
        stack = [cst]
        while stack:  # not recursive: the CST nests about 15 levels per expression
            node = stack.pop()
            if node[0] < token.NT_OFFSET:
                self.tokens.append(node)
            else:
                if node[0] == symbol.except_clause:
                    self.except_clauses.append(node)
                stack.extend(node[1:])

    def of(self, *kinds):
        return (node for node in self.nodes if isinstance(node, kinds))


def check(module):
    """(rule id, line, col, message) for every occurrence of every rule."""
    return [(rule_id, line, col, message)
            for rule_id, check_rule in _CHECKS
            for line, col, message in check_rule(module)]


@rule("PY3-PRINT", "print statement")
def check_print(m):
    for node in m.of(ast.Print):
        yield node.lineno, node.col_offset, "print statement; Python 3 has only the print() function"


@rule("PY3-EXEC-STMT", "exec statement")
def check_exec(m):
    for node in m.of(ast.Exec):
        yield node.lineno, node.col_offset, "exec statement; Python 3 has only the exec() function"


@rule("PY3-BACKTICK", "backtick repr")
def check_backtick(m):
    for node in m.of(ast.Repr):
        yield node.lineno, node.col_offset, "backtick repr expression; Python 3 has only repr()"


@rule("PY3-NE-OP", "<> operator")
def check_ne_op(m):
    for kind, text, line, col in m.tokens:
        if kind == token.NOTEQUAL and text == "<>":
            yield line, col, "<> operator; Python 3 has only !="


@rule("PY3-EXCEPT-COMMA", "except X, e:")
def check_except_comma(m):
    # except_clause: 'except' [test [('as' | ',') test]]; a comma inside
    # except (A, B): belongs to the test, not to the clause.
    for clause in m.except_clauses:
        if len(clause) > 3 and clause[3][0] == token.COMMA:
            keyword = clause[1]
            yield keyword[2], keyword[3], "except X, e: form; Python 3 needs except X as e:"


@rule("PY3-RAISE-COMMA", "raise E, value")
def check_raise_comma(m):
    for node in m.of(ast.Raise):
        if node.inst is not None:
            yield node.lineno, node.col_offset, "raise E, value form; Python 3 needs raise E(value)"


# 0 followed by octal digits, at least one of them non-zero: 00 is valid Python 3.
_OLD_OCTAL = re.compile(r"0[0-7]*[1-7][0-7]*[lL]?$")


@rule("PY3-OCTAL", "old-style octal literal")
def check_octal(m):
    for kind, text, line, col in m.tokens:
        if kind == token.NUMBER and _OLD_OCTAL.match(text):
            yield line, col, "old-style octal literal %s; Python 3 needs 0o%s" % (
                text, text.rstrip("lL").lstrip("0"))


@rule("PY3-LONG-SUFFIX", "long integer suffix")
def check_long_suffix(m):
    for kind, text, line, col in m.tokens:
        if kind == token.NUMBER and text[-1] in "lL":
            yield line, col, "long literal %s; Python 3 ints take no L suffix" % text


_DICT_METHODS = {
    "iteritems": "use .items()",
    "iterkeys": "use .keys()",
    "itervalues": "use .values()",
    "has_key": "use key in d",
}


@rule("PY3-DICT-ITER", "iteritems, iterkeys, itervalues or has_key call")
def check_dict_iter(m):
    for node in m.of(ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _DICT_METHODS:
            yield node.lineno, node.col_offset, ".%s() is gone in Python 3; %s" % (
                func.attr, _DICT_METHODS[func.attr])


_BUILTINS = {
    "unicode": "use str",
    "basestring": "use str",
    "long": "use int",
    "xrange": "use range",
    "raw_input": "use input",
    "unichr": "use chr",
    "execfile": "use exec(open(path).read())",
    "reduce": "use functools.reduce",
    "file": "use open",
    "cmp": "use a key function, or (a > b) - (a < b)",
    "reload": "use importlib.reload",
    "apply": "use f(*args, **kwargs)",
    "buffer": "use memoryview",
    "intern": "use sys.intern",
    "coerce": "convert the operands explicitly",
}


def bound_names(m):
    """Every name the module binds anywhere: imports, assignments, defs, classes."""
    bound = set()
    for node in m.nodes:
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.arguments):  # in 2.7, *args and **kwargs are bare strings
            bound.update(name for name in (node.vararg, node.kwarg) if name)
        elif isinstance(node, ast.Import):
            bound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            bound.update(alias.asname or alias.name for alias in node.names)
    return bound


@rule("PY3-BUILTIN", "builtin removed in Python 3")
def check_builtin(m):
    bound = bound_names(m)
    for node in m.of(ast.Name):
        if isinstance(node.ctx, ast.Load) and node.id in _BUILTINS and node.id not in bound:
            yield node.lineno, node.col_offset, "%s is not a builtin in Python 3; %s" % (
                node.id, _BUILTINS[node.id])


_STDLIB = {
    "urllib2": "urllib.request and urllib.error",
    "urlparse": "urllib.parse",
    "ConfigParser": "configparser",
    "Queue": "queue",
    "cPickle": "pickle",
    "cStringIO": "io",
    "StringIO": "io",
    "httplib": "http.client",
    "HTMLParser": "html.parser",
    "commands": "subprocess",
    "SocketServer": "socketserver",
    "Tkinter": "tkinter",
    "__builtin__": "builtins",
    "copy_reg": "copyreg",
    "xmlrpclib": "xmlrpc.client",
    "thread": "_thread or threading",
    "Cookie": "http.cookies",
    "cookielib": "http.cookiejar",
    "BaseHTTPServer": "http.server",
    "SimpleHTTPServer": "http.server",
    "htmlentitydefs": "html.entities",
    "md5": "hashlib",
    "sha": "hashlib",
    "sets": "the set builtin",
    "UserDict": "collections.UserDict",
}


@rule("PY3-STDLIB", "module renamed or removed in Python 3")
def check_stdlib(m):
    for node in m.of(ast.Import, ast.ImportFrom):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        else:  # a relative import names a module of the package, not the stdlib
            modules = [node.module] if node.module and not node.level else []
        for module in modules:
            top = module.split(".")[0]
            if top in _STDLIB:
                yield node.lineno, node.col_offset, "%s is renamed or removed in Python 3; use %s" % (
                    top, _STDLIB[top])


def future_features(tree):
    """The __future__ features a module enables, found as Python/future.c finds them:
    future imports count only before any other statement but one docstring."""
    features = set()
    docstring = False
    for stmt in tree.body:
        if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
            features.update(alias.name for alias in stmt.names)
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Str) and not docstring:
            docstring = True
        else:
            break
    return features


@rule("PY3-DIVISION", "/ without from __future__ import division", WARNING)
def check_division(m):
    if "division" in future_features(m.tree):
        return
    for kind, text, line, col in m.tokens:
        if kind in (token.SLASH, token.SLASHEQUAL):
            yield line, col, ("%s floors int operands in Python 2 but not in Python 3; "
                              "use // or from __future__ import division" % text)


@rule("PY3-METACLASS", "__metaclass__ in a class body", WARNING)
def check_metaclass(m):
    for cls in m.of(ast.ClassDef):
        stack = list(cls.body)
        while stack:
            stmt = stack.pop()
            if isinstance(stmt, (ast.FunctionDef, ast.ClassDef)):
                continue  # their bodies are other scopes; nested classes get their own turn
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    for node in ast.walk(target):
                        if isinstance(node, ast.Name) and node.id == "__metaclass__":
                            yield stmt.lineno, stmt.col_offset, (
                                "__metaclass__ in a class body is ignored by Python 3; "
                                "use class C(metaclass=M) or six.with_metaclass")
            stack.extend(child for child in ast.iter_child_nodes(stmt)
                         if isinstance(child, (ast.stmt, ast.excepthandler)))
