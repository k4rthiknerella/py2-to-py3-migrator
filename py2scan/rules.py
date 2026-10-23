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

_FUNC_DEF_TYPES = tuple(t for t in (
    ast.FunctionDef, getattr(ast, "AsyncFunctionDef", None),
) if t is not None)

_CLASS_OR_FUNC_TYPES = _FUNC_DEF_TYPES + (ast.ClassDef,)


def _single_param_name(value):
    """The bound name of one arguments-node slot (an entry in .args or
    .kwonlyargs, or the .vararg/.kwarg value), or None if that slot is
    absent. Covers 2.7's Name(ctx=Param)/string vararg-kwarg and 3.x's
    ast.arg nodes."""
    if value is None:
        return None
    if _ARG_TYPE is not None and isinstance(value, _ARG_TYPE):
        return value.arg
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, str):
        return value
    return None


def _param_names(arguments_node):
    """Every name an ast.arguments node binds as a parameter. Doesn't
    handle 2.7's tuple-parameter unpacking (def f((a, b)): ...) - rare,
    Python-2-only syntax; a known, minor gap, not R3's concern."""
    names = set()
    for arg in list(getattr(arguments_node, "args", None) or []):
        name = _single_param_name(arg)
        if name:
            names.add(name)
    for arg in list(getattr(arguments_node, "kwonlyargs", None) or []):
        name = _single_param_name(arg)
        if name:
            names.add(name)
    for attr in ("vararg", "kwarg"):
        name = _single_param_name(getattr(arguments_node, attr, None))
        if name:
            names.add(name)
    return names


def _record_direct_binding(node, bound):
    """If this node directly binds a name - not a function/class/lambda
    or a global statement, which the caller handles itself - add it to
    bound and return True. Returns False (meaning "recurse into this
    node's children instead") for anything else."""
    if isinstance(node, ast.Name) and isinstance(node.ctx, _BINDING_CONTEXTS):
        bound.add(node.id)
        return True
    if _ARG_TYPE is not None and isinstance(node, _ARG_TYPE):
        bound.add(node.arg)
        return True
    if isinstance(node, ast.Import):
        for alias in node.names:
            bound.add((alias.asname or alias.name).split(".")[0])
        return True
    if isinstance(node, ast.ImportFrom):
        for alias in node.names:
            bound.add(alias.asname or alias.name)
        return True
    return False


def _own_bindings_and_globals(stmts):
    """(bound, declared_globals): names bound directly by these statements,
    and names named in a bare `global` statement directly within them -
    not crossing into a nested function, class, or lambda body (R3: a
    binding, including del, binds "in that scope")."""
    bound = set()
    declared_globals = set()
    stack = list(stmts)
    while stack:
        node = stack.pop()
        if isinstance(node, _CLASS_OR_FUNC_TYPES):
            bound.add(node.name)
        elif isinstance(node, ast.Lambda):
            pass
        elif isinstance(node, ast.Global):
            declared_globals.update(node.names)
        elif not _record_direct_binding(node, bound):
            stack.extend(ast.iter_child_nodes(node))
    return bound, declared_globals


def _module_bound_names(tree):
    """R3: names bound at module level - either directly, or inside a
    function that both declares the name global and binds it there. A
    bare `global` statement with no matching binding in that same
    function binds nothing by itself."""
    module_bound, _ = _own_bindings_and_globals(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, _FUNC_DEF_TYPES):
            local_bound, declared_globals = \
                _own_bindings_and_globals(node.body)
            module_bound.update(declared_globals & local_bound)
    return module_bound


def _is_shadowed(name, scope_chain, module_bound):
    for shadow in scope_chain:
        if name in shadow:
            return True
    return name in module_bound


def _builtin_use_in_name(node, scope_chain, module_bound, path):
    if (isinstance(node.ctx, ast.Load) and node.id in BUILTIN_NAMES
            and not _is_shadowed(node.id, scope_chain, module_bound)):
        yield Finding(
            path, node.lineno, "PY3-BUILTIN", "blocker",
            "%s; removed or changed on Python 3" % node.id)


def _builtin_use_in_function(node, scope_chain, module_bound, path):
    local_bound, declared_globals = _own_bindings_and_globals(node.body)
    shadow = (local_bound - declared_globals) | _param_names(node.args)
    new_chain = (shadow,) + scope_chain
    for child in ast.iter_child_nodes(node):
        for finding in _builtin_use_walk(child, new_chain, module_bound, path):
            yield finding


def _builtin_use_in_lambda(node, scope_chain, module_bound, path):
    new_chain = (_param_names(node.args),) + scope_chain
    for finding in _builtin_use_walk(node.body, new_chain, module_bound, path):
        yield finding


def _builtin_use_walk(node, scope_chain, module_bound, path):
    args = (scope_chain, module_bound, path)
    if isinstance(node, ast.Name):
        for finding in _builtin_use_in_name(node, *args):
            yield finding
        return
    if isinstance(node, _FUNC_DEF_TYPES):
        for finding in _builtin_use_in_function(node, *args):
            yield finding
        return
    if isinstance(node, ast.Lambda):
        for finding in _builtin_use_in_lambda(node, *args):
            yield finding
        return
    for child in ast.iter_child_nodes(node):
        for finding in _builtin_use_walk(child, *args):
            yield finding


def check_builtin_use(path, tree):
    """R3: PY3-BUILTIN scoping is Python 2.7's own compiler scoping - a
    builtin-name reference is shadowed only by a binding Python's real
    name resolution would actually reach: this function's own locals
    (including its parameters), an enclosing function's locals via
    closure (unless this function declares the name global, which skips
    straight to module scope), or a module-level binding. A class body's
    own bindings are not visible to its methods via this resolution, same
    as real Python - only a function creates a scope nested methods see
    through.

    Known gap: a parameter default value or a decorator is real Python's
    enclosing scope, not the function's own - this walk uses the new,
    inner scope for both (via the generic ast.iter_child_nodes descent
    in _builtin_use_in_function), so a builtin name shadowed only by a
    same-named parameter could be wrongly treated as shadowed in its own
    default value too. Rare enough (a builtin name reused as both a
    parameter and, in the same signature, a default) that R3 doesn't call
    it out; not fixed here to avoid losing parameter-annotation coverage
    for little gain."""
    module_bound = _module_bound_names(tree)
    for finding in _builtin_use_walk(tree, (), module_bound, path):
        yield finding


# Python 2.7's ast has separate TryExcept/TryFinally nodes; Python 3 unifies
# them into one Try node with body/handlers/orelse/finalbody. Either way,
# ExceptHandler itself (type/name/body) is the same shape on both versions.
_TRY_TYPE = getattr(ast, "Try", None)
_TRY_EXCEPT_TYPE = getattr(ast, "TryExcept", None)

_FUNCTION_TYPES = tuple(t for t in (
    ast.FunctionDef, ast.Lambda, getattr(ast, "AsyncFunctionDef", None),
) if t is not None)

# R2: a handler counts as "catches ImportError" if it's bare, or names one
# of these (alone or in a tuple). StandardError is Python-2-only, but this
# is a static text match against the except clause, not a live lookup.
_IMPORT_ERROR_NAMES = frozenset([
    "ImportError", "ModuleNotFoundError", "Exception", "BaseException",
    "StandardError",
])


def _is_try_node(node):
    return ((_TRY_TYPE is not None and isinstance(node, _TRY_TYPE))
            or (_TRY_EXCEPT_TYPE is not None
                and isinstance(node, _TRY_EXCEPT_TYPE)))


def _handler_catches_import_error(handler):
    if handler.type is None:
        return True
    types = (handler.type.elts if isinstance(handler.type, ast.Tuple)
             else [handler.type])
    return any(isinstance(t, ast.Name) and t.id in _IMPORT_ERROR_NAMES
               for t in types)


def _imports_in_blocks(stmt_lists):
    """Import/ImportFrom nodes reachable from these statement lists without
    descending into a nested function or lambda body - R2's "inside"."""
    found = []
    stack = [stmt for stmts in stmt_lists for stmt in stmts]
    while stack:
        node = stack.pop()
        if isinstance(node, _FUNCTION_TYPES):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found.append(node)
            continue
        stack.extend(ast.iter_child_nodes(node))
    return found


def _import_error_guarded_imports(tree):
    """id()s of Import/ImportFrom nodes inside a try body or a handler body
    (R2's "inside" - not else/finally) of a try with a handler that catches
    ImportError (bare except, or one of _IMPORT_ERROR_NAMES)."""
    guarded = set()
    for node in ast.walk(tree):
        if not _is_try_node(node):
            continue
        if not any(_handler_catches_import_error(h) for h in node.handlers):
            continue
        blocks = [node.body] + [h.body for h in node.handlers]
        guarded.update(id(imp) for imp in _imports_in_blocks(blocks))
    return guarded


def check_stdlib_import(path, tree):
    guarded = _import_error_guarded_imports(tree)
    for node in _nodes(tree, ast.Import):
        severity = "warning" if id(node) in guarded else "blocker"
        for alias in node.names:
            if alias.name in STDLIB_MODULES:
                yield Finding(
                    path, node.lineno, "PY3-STDLIB", severity,
                    "import of %s; renamed or removed on Python 3"
                    % alias.name)
    for node in _nodes(tree, ast.ImportFrom):
        if node.level == 0 and node.module in STDLIB_MODULES:
            severity = "warning" if id(node) in guarded else "blocker"
            yield Finding(
                path, node.lineno, "PY3-STDLIB", severity,
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
