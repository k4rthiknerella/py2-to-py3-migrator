# -*- coding: utf-8 -*-
"""Rules that read a module's Python 2.7 AST."""
import ast

from py2scan.findings import Finding


def _nodes(tree, kind):
    for node in ast.walk(tree):
        if isinstance(node, kind):
            yield node


def check_print(path, tree, tokens):
    for node in _nodes(tree, ast.Print):
        yield Finding(path, node.lineno, "PY3-PRINT", "blocker",
                      "print statement; Python 3 has only the print() function")


def check_exec(path, tree, tokens):
    for node in _nodes(tree, ast.Exec):
        yield Finding(path, node.lineno, "PY3-EXEC-STMT", "blocker",
                      "exec statement; Python 3 has only the exec() function")


def check_backtick(path, tree, tokens):
    for node in _nodes(tree, ast.Repr):
        yield Finding(path, node.lineno, "PY3-BACKTICK", "blocker",
                      "backtick repr expression; Python 3 has only the repr() function")


def check_raise_comma(path, tree, tokens):
    for node in _nodes(tree, ast.Raise):
        if node.inst is not None:
            yield Finding(path, node.lineno, "PY3-RAISE-COMMA", "blocker",
                          "raise with comma-separated value; Python 3 uses raise E(value)")


DICT_ITER_METHODS = frozenset(["iteritems", "iterkeys", "itervalues", "has_key"])


def check_dict_iter(path, tree, tokens):
    for node in _nodes(tree, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in DICT_ITER_METHODS:
            yield Finding(path, node.lineno, "PY3-DICT-ITER", "blocker",
                          "%s(); not available in Python 3" % func.attr)


BUILTIN_NAMES = frozenset([
    "unicode", "basestring", "long", "xrange", "raw_input", "unichr",
    "execfile", "reduce", "file", "cmp", "reload", "apply", "buffer",
    "intern", "coerce",
])


def _bound_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def check_builtin(path, tree, tokens):
    bound = _bound_names(tree)
    for node in _nodes(tree, ast.Name):
        if (isinstance(node.ctx, ast.Load) and node.id in BUILTIN_NAMES
                and node.id not in bound):
            yield Finding(path, node.lineno, "PY3-BUILTIN", "blocker",
                          "%s; removed or renamed in Python 3" % node.id)


STDLIB_MODULES = frozenset([
    "urllib2", "urlparse", "ConfigParser", "Queue", "cPickle", "cStringIO",
    "StringIO", "httplib", "HTMLParser", "commands", "SocketServer",
    "Tkinter", "__builtin__", "copy_reg", "xmlrpclib", "thread", "Cookie",
    "cookielib", "BaseHTTPServer", "SimpleHTTPServer", "htmlentitydefs",
    "md5", "sha", "sets", "UserDict",
])


def check_stdlib(path, tree, tokens):
    for node in _nodes(tree, ast.Import):
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in STDLIB_MODULES:
                yield Finding(path, node.lineno, "PY3-STDLIB", "blocker",
                              "import of %s; renamed or removed in Python 3" % top)
    for node in _nodes(tree, ast.ImportFrom):
        top = (node.module or "").split(".")[0]
        if top in STDLIB_MODULES:
            yield Finding(path, node.lineno, "PY3-STDLIB", "blocker",
                          "import from %s; renamed or removed in Python 3" % top)


def check_metaclass(path, tree, tokens):
    for cls in _nodes(tree, ast.ClassDef):
        for stmt in cls.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == "__metaclass__":
                        yield Finding(path, stmt.lineno, "PY3-METACLASS", "warning",
                                      "__metaclass__ assignment; Python 3 uses the metaclass= keyword")


AST_RULES = [check_print, check_exec, check_backtick, check_raise_comma,
             check_dict_iter, check_builtin, check_stdlib, check_metaclass]
