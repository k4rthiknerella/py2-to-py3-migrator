# -*- coding: utf-8 -*-
"""Rules that read a module's Python 2.7 AST or token stream."""
import ast
import re
import tokenize

from py2scan.findings import Finding

_OLD_OCTAL = re.compile(r"^0[0-7]+$")

_BRACKETS_OPEN = frozenset("([{")
_BRACKETS_CLOSE = frozenset(")]}")


def _nodes(tree, kind):
    for node in ast.walk(tree):
        if isinstance(node, kind):
            yield node


# ast.Print/Exec/Repr don't exist on Python 3 at all - not just "never
# matched", the names themselves are gone, because a tree that reached this
# code already parsed successfully, and source containing any of these three
# constructs can never parse successfully under Python 3 in the first place
# (scanner.scan_file's SyntaxError branch already reported PY3-PARSE for it).
# getattr keeps each check a safe no-op there instead of an AttributeError.
_PRINT_TYPE = getattr(ast, "Print", None)
_EXEC_TYPE = getattr(ast, "Exec", None)
_REPR_TYPE = getattr(ast, "Repr", None)


def check_print(path, tree):
    if _PRINT_TYPE is None:
        return
    for node in _nodes(tree, _PRINT_TYPE):
        yield Finding(path, node.lineno, "PY3-PRINT", "blocker",
                      "print statement; Python 3 has only the print() "
                      "function")


def check_exec(path, tree):
    if _EXEC_TYPE is None:
        return
    for node in _nodes(tree, _EXEC_TYPE):
        yield Finding(path, node.lineno, "PY3-EXEC-STMT", "blocker",
                      "exec statement; Python 3 has only the exec() function")


def check_backtick(path, tree):
    if _REPR_TYPE is None:
        return
    for node in _nodes(tree, _REPR_TYPE):
        yield Finding(path, node.lineno, "PY3-BACKTICK", "blocker",
                      "backtick repr expression; Python 3 has only the "
                      "repr() function")


def check_raise_comma(path, tree):
    for node in _nodes(tree, ast.Raise):
        # Python 3's ast.Raise has no .inst/.type at all (it's exc/cause
        # instead) because the comma form can't parse there in the first
        # place; getattr keeps this rule a no-op on that shape rather than
        # an AttributeError.
        if getattr(node, "inst", None) is not None:
            yield Finding(path, node.lineno, "PY3-RAISE-COMMA", "blocker",
                          "raise E, value form; Python 3 only has "
                          "raise E(value)")


def check_dict_iter(path, tree):
    iter_attrs = frozenset(["iteritems", "iterkeys", "itervalues", "has_key"])
    for node in _nodes(tree, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in iter_attrs:
            yield Finding(path, node.lineno, "PY3-DICT-ITER", "blocker",
                          "%s(); not available on Python 3 dicts" % func.attr)


def check_metaclass(path, tree):
    for cls in _nodes(tree, ast.ClassDef):
        for stmt in cls.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for target in stmt.targets:
                if (isinstance(target, ast.Name)
                        and target.id == "__metaclass__"):
                    yield Finding(
                        path, stmt.lineno, "PY3-METACLASS", "warning",
                        "__metaclass__ assignment; Python 3 uses the "
                        "metaclass= keyword")


def _has_future_division(tree):
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            if any(alias.name == "division" for alias in node.names):
                return True
    return False


def check_division(path, tree):
    if _has_future_division(tree):
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            yield Finding(path, node.lineno, "PY3-DIVISION", "warning",
                          "/ is true division on Python 3; add from "
                          "__future__ import division")
        elif isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Div):
            yield Finding(path, node.lineno, "PY3-DIVISION", "warning",
                          "/= is true division on Python 3; add from "
                          "__future__ import division")


BUILTIN_NAMES = frozenset([
    "unicode", "basestring", "long", "xrange", "raw_input", "unichr",
    "execfile", "reduce", "file", "cmp", "reload", "apply", "buffer",
    "intern", "coerce",
])

STDLIB_MODULES = frozenset([
    "urllib2", "urlparse", "ConfigParser", "Queue", "cPickle", "cStringIO",
    "StringIO", "httplib", "HTMLParser", "commands", "SocketServer",
    "Tkinter", "__builtin__", "copy_reg", "xmlrpclib", "thread", "Cookie",
    "cookielib", "BaseHTTPServer", "SimpleHTTPServer", "htmlentitydefs",
    "md5", "sha", "sets", "UserDict",
])

_BINDING_CONTEXTS = (ast.Store, ast.Param, ast.Del)

# ast.arg doesn't exist on Python 2.7: its arguments.args holds Name(ctx=Param)
# nodes instead, already covered by _BINDING_CONTEXTS above. On Python 3,
# parameters are ast.arg nodes with no ctx at all, so they need this
# separate, version-guarded branch.
_ARG_TYPE = getattr(ast, "arg", None)


def _module_bound_names(tree):
    bound = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Name)
                and isinstance(node.ctx, _BINDING_CONTEXTS)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif _ARG_TYPE is not None and isinstance(node, _ARG_TYPE):
            bound.add(node.arg)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound.add(alias.asname or alias.name)
    return bound


def check_builtin_use(path, tree):
    bound = _module_bound_names(tree)
    for node in _nodes(tree, ast.Name):
        if (isinstance(node.ctx, ast.Load) and node.id in BUILTIN_NAMES
                and node.id not in bound):
            yield Finding(path, node.lineno, "PY3-BUILTIN", "blocker",
                          "%s; removed or changed on Python 3" % node.id)


def check_stdlib_import(path, tree):
    for node in _nodes(tree, ast.Import):
        for alias in node.names:
            if alias.name in STDLIB_MODULES:
                yield Finding(
                    path, node.lineno, "PY3-STDLIB", "blocker",
                    "import of %s; renamed or removed on Python 3"
                    % alias.name)
    for node in _nodes(tree, ast.ImportFrom):
        if node.level == 0 and node.module in STDLIB_MODULES:
            yield Finding(
                path, node.lineno, "PY3-STDLIB", "blocker",
                "import of %s; renamed or removed on Python 3"
                % node.module)


AST_RULES = [check_print, check_exec, check_backtick, check_raise_comma,
             check_dict_iter, check_metaclass, check_division,
             check_builtin_use, check_stdlib_import]


def check_ne_op(path, tokens):
    for toknum, tokval, start, _end, _line in tokens:
        if toknum == tokenize.OP and tokval == "<>":
            yield Finding(path, start[0], "PY3-NE-OP", "blocker",
                          "<> operator; Python 3 only has !=")


def check_octal(path, tokens):
    for toknum, tokval, start, _end, _line in tokens:
        if toknum != tokenize.NUMBER:
            continue
        body = tokval[:-1] if tokval[-1] in "Ll" else tokval
        if _OLD_OCTAL.match(body):
            yield Finding(
                path, start[0], "PY3-OCTAL", "blocker",
                "old-style octal literal %s; Python 3 requires the "
                "0o prefix" % tokval)


def check_long_suffix(path, tokens):
    # Python 2.7's tokenizer lexes 10L as one NUMBER token, '10L'. Python 3's
    # tokenizer doesn't know the L suffix at all and splits it into a NUMBER
    # token '10' immediately followed by a bare NAME token 'L' - "immediately"
    # meaning the NAME starts exactly where the NUMBER ends, with nothing
    # between them.
    prev_end = prev_value = None
    for toknum, tokval, start, end, _line in tokens:
        if toknum == tokenize.NUMBER and tokval[-1] in "Ll":
            yield Finding(
                path, start[0], "PY3-LONG-SUFFIX", "blocker",
                "long literal %s; Python 3 has a single int type with "
                "no L suffix" % tokval)
        elif (toknum == tokenize.NAME and tokval in ("L", "l")
                and prev_value is not None and start == prev_end):
            yield Finding(
                path, start[0], "PY3-LONG-SUFFIX", "blocker",
                "long literal %s%s; Python 3 has a single int type "
                "with no L suffix" % (prev_value, tokval))
        if toknum == tokenize.NUMBER:
            prev_end, prev_value = end, tokval
        else:
            prev_end = prev_value = None


def check_except_comma(path, tokens):
    pending = False
    depth = 0
    for toknum, tokval, start, _end, _line in tokens:
        if not pending:
            if toknum == tokenize.NAME and tokval == "except":
                pending = True
                depth = 0
            continue
        if toknum == tokenize.OP:
            if tokval in _BRACKETS_OPEN:
                depth += 1
                continue
            if tokval in _BRACKETS_CLOSE:
                depth -= 1
                continue
            if depth == 0 and tokval == ",":
                yield Finding(
                    path, start[0], "PY3-EXCEPT-COMMA", "blocker",
                    "except X, e: form; Python 3 only has "
                    "except X as e:")
                pending = False
                continue
            if depth == 0 and tokval == ":":
                pending = False
                continue


TOKEN_RULES = [check_ne_op, check_octal, check_long_suffix, check_except_comma]
