# -*- coding: utf-8 -*-
"""Rules that read a module's Python 2.7 AST or token stream."""
import ast
import codecs
import io
import re
import tokenize

from py2scan.encoding import detect_encoding
from py2scan.findings import Finding

_OLD_OCTAL = re.compile(r"^0[0-7]+$")

_STRING_PREFIX = re.compile(r"^[a-zA-Z]*")
_HEX4 = re.compile(r"^[0-9a-fA-F]{4}$")
_HEX8 = re.compile(r"^[0-9a-fA-F]{8}$")
_NAME_ESCAPE = re.compile(r"^\{[^}]+\}")

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


# R6: every version py2scan can judge readiness against. R10 found this
# set to be version-invariant (see BUILTIN_NAMES below); R8's stdlib set
# genuinely varies by version (see STDLIB_REMOVED_SINCE).
ALL_TARGET_VERSIONS = (
    "3.6", "3.7", "3.8", "3.9", "3.10", "3.11", "3.12", "3.13", "3.14",
    "3.15",
)

# R10: every name in Python 2.7's __builtin__ missing from a judged
# version's builtins. Derived by diffing 2.7.18's __builtin__ against
# builtins on 9 real, final-release interpreters spanning the whole R6
# range (3.6.15, 3.7.17, 3.8.20, 3.9.25, 3.10.19, 3.11.14, 3.12.12,
# 3.13.12, 3.14.7) plus 3.15.1 for 3.15 - see MIGRATION.md's R10 evidence.
# The missing set is identical across all 10: no per-version table is
# needed here, unlike STDLIB_REMOVED_SINCE below.
BUILTIN_NAMES = frozenset([
    "unicode", "basestring", "long", "xrange", "raw_input", "unichr",
    "execfile", "reduce", "file", "cmp", "reload", "apply", "buffer",
    "intern", "coerce", "StandardError",
])

# R8: every top-level Python 2.7 stdlib module missing from a judged
# version, keyed by the earliest judged version it's missing from.
# Derived the same way as BUILTIN_NAMES above, against the same 10
# interpreters - see MIGRATION.md's R8 evidence for the full receipt.
# Confirmed monotonic: nothing removed ever reappears in a later version.
# "3.6" means removed at the 2-vs-3 boundary, before R6's judged range
# even starts - true unconditionally for every version R6 can judge.
# cPickle/cStringIO/__builtin__ were confirmed removed-by-3.6 the same
# empirical way; Tkinter is sourced from the Python 3.0 porting guide
# instead, because the test images used have no system Tcl/Tk library,
# so Tkinter fails to import on 2.7 too, for an unrelated environment
# reason - not a usable receipt either way.
#
# audioop/crypt/nis/ossaudiodev/spwd needed the same care, the other
# direction: trying to import each directly against the slim test images
# makes every one of them look removed as early as 3.9, well before
# their real removal (PEP 594, Python 3.13) - because those optional C
# extensions need a system library the slim images don't ship, for every
# version, not because Python stopped shipping the module. Caught by
# cross-checking sys.stdlib_module_names (3.10+, independent of whether
# the extension actually built) directly: all five are still True at
# 3.10 and 3.12 and False starting at 3.13, matching PEP 594 and the
# already-correct 3.13 batch below exactly - confirming the slim images'
# earlier-looking failures were a build artifact, not a removal.
STDLIB_REMOVED_SINCE = {
    "BaseHTTPServer": "3.6", "Bastion": "3.6", "CGIHTTPServer": "3.6",
    "ConfigParser": "3.6", "Cookie": "3.6", "DocXMLRPCServer": "3.6",
    "HTMLParser": "3.6", "MimeWriter": "3.6", "Queue": "3.6",
    "SimpleHTTPServer": "3.6", "SimpleXMLRPCServer": "3.6",
    "SocketServer": "3.6", "StringIO": "3.6", "Tkinter": "3.6",
    "UserDict": "3.6", "UserList": "3.6", "UserString": "3.6",
    "__builtin__": "3.6", "anydbm": "3.6", "audiodev": "3.6",
    "bsddb": "3.6", "cPickle": "3.6", "cStringIO": "3.6",
    "commands": "3.6", "compiler": "3.6", "cookielib": "3.6",
    "copy_reg": "3.6", "dbhash": "3.6", "dircache": "3.6",
    "dumbdbm": "3.6", "dummy_thread": "3.6", "exceptions": "3.6",
    "fpformat": "3.6", "future_builtins": "3.6", "gdbm": "3.6",
    "hotshot": "3.6", "htmlentitydefs": "3.6",
    "htmllib": "3.6", "httplib": "3.6", "ihooks": "3.6", "imputil": "3.6",
    "linuxaudiodev": "3.6",
    "markupbase": "3.6", "md5": "3.6", "mhlib": "3.6", "mimetools": "3.6",
    "mimify": "3.6", "multifile": "3.6", "mutex": "3.6", "new": "3.6",
    "os2emxpath": "3.6", "popen2": "3.6", "posixfile": "3.6",
    "repr": "3.6", "rexec": "3.6", "rfc822": "3.6", "robotparser": "3.6",
    "sets": "3.6", "sgmllib": "3.6", "sha": "3.6", "sre": "3.6",
    "statvfs": "3.6", "stringold": "3.6", "strop": "3.6", "sunaudio": "3.6",
    "thread": "3.6", "toaiff": "3.6", "urllib2": "3.6", "urlparse": "3.6",
    "user": "3.6", "whichdb": "3.6", "xmllib": "3.6", "xmlrpclib": "3.6",
    "macurl2path": "3.7",
    "macpath": "3.8",
    "dummy_threading": "3.9",
    "formatter": "3.10", "parser": "3.10", "symbol": "3.10",
    "binhex": "3.11",
    "asynchat": "3.12", "asyncore": "3.12", "distutils": "3.12",
    "imp": "3.12", "smtpd": "3.12",
    "aifc": "3.13", "audioop": "3.13", "cgi": "3.13", "cgitb": "3.13",
    "chunk": "3.13", "crypt": "3.13",
    "imghdr": "3.13", "lib2to3": "3.13", "mailcap": "3.13",
    "nis": "3.13", "nntplib": "3.13", "ossaudiodev": "3.13",
    "pipes": "3.13", "sndhdr": "3.13", "spwd": "3.13", "sunau": "3.13",
    "telnetlib": "3.13", "uu": "3.13", "xdrlib": "3.13",
    "sre_compile": "3.15", "sre_constants": "3.15", "sre_parse": "3.15",
}


# A module surviving into Python 3 doesn't mean every name it exported
# on 2.7 still does - found via AutoSteer CI against the real stdlib
# (idlelib/CodeContext.py:13's `from sys import maxint`). Derived
# empirically, not from memory: every `from <module> import <name>` the
# real 2.7 stdlib actually uses (941 unique pairs, via an AST walk),
# checked with __import__/hasattr against a real 3.14.9 for modules that
# are NOT themselves in STDLIB_REMOVED_SINCE above - so a genuinely
# missing name, not a casualty of its whole module being gone. All of
# these left their module in Python 3.0, confirmed never to come back in
# any later 3.x, so every entry here uses the same floor as judged_versions
# can ever be asked about (3.6) rather than the real, earlier release.
# Narrowed by hand from the full empirical diff to the names a migrating
# application is actually likely to use: dropped private (leading-
# underscore) modules and names, idlelib's own internal submodule
# layout (renamed wholesale on Python 3, but nothing outside idlelib
# itself imports those names), and platform-conditional names that
# cannot be checked on this Linux-only test fleet either way. This only
# covers the `from <module> import <name>` form the real repro uses -
# `import sys; sys.maxint` (attribute access after a plain import, the
# more common real-world spelling: 39 of the 40 real-stdlib hits for
# sys.maxint alone are this form) is a known, separate, unclosed gap -
# recognizing it needs tracking which name a module import bound and
# then walking for Attribute nodes on it, the same scope check_builtin_use
# already does for bare names, which this rule does not do yet.
STDLIB_REMOVED_NAMES = {
    ("sys", "maxint"): "3.6",
    ("itertools", "imap"): "3.6", ("itertools", "izip"): "3.6",
    ("itertools", "ifilter"): "3.6", ("itertools", "ifilterfalse"): "3.6",
    ("string", "join"): "3.6", ("string", "split"): "3.6",
    ("string", "strip"): "3.6", ("string", "rstrip"): "3.6",
    ("string", "find"): "3.6", ("string", "rfind"): "3.6",
    ("string", "lower"): "3.6", ("string", "expandtabs"): "3.6",
    ("types", "StringType"): "3.6", ("types", "DictType"): "3.6",
    ("types", "ListType"): "3.6", ("types", "TupleType"): "3.6",
    ("types", "ClassType"): "3.6", ("types", "InstanceType"): "3.6",
    ("urllib", "quote"): "3.6", ("urllib", "unquote"): "3.6",
    ("urllib", "getproxies"): "3.6", ("urllib", "proxy_bypass"): "3.6",
    ("urllib", "splittype"): "3.6", ("urllib", "splithost"): "3.6",
    ("urllib", "splitport"): "3.6", ("urllib", "splituser"): "3.6",
    ("urllib", "splitpasswd"): "3.6", ("urllib", "splitattr"): "3.6",
    ("urllib", "splitvalue"): "3.6", ("urllib", "splittag"): "3.6",
    ("urllib", "toBytes"): "3.6", ("urllib", "unwrap"): "3.6",
    ("urllib", "url2pathname"): "3.6", ("urllib", "addinfourl"): "3.6",
    ("urllib", "ftpwrapper"): "3.6", ("urllib", "localhost"): "3.6",
    ("warnings", "warnpy3k"): "3.6",
}


def _version_tuple(version):
    return tuple(int(part) for part in version.split("."))


def _applicable_versions(removed_since, judged_versions):
    """The subset of judged_versions a removed-as-of-removed_since fact
    applies to - R6's "per-file/per-blocker version applicability"."""
    floor = _version_tuple(removed_since)
    return tuple(v for v in judged_versions if _version_tuple(v) >= floor)


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


def _default_value_exprs(arguments_node):
    """Every default-value expression an ast.arguments node carries -
    real Python evaluates these in the enclosing scope, at def time, not
    the function's own (confirmed via a real stdlib miss, R3/R10:
    json/encoder.py's `basestring=basestring` and `long=long`, a hand-
    optimization that binds a builtin name to a same-named parameter -
    the parameter's own shadowing must not reach its own default
    value, or Python 3's real NameError at def time goes undetected)."""
    exprs = list(getattr(arguments_node, "defaults", None) or [])
    kw_defaults = getattr(arguments_node, "kw_defaults", None) or []
    exprs.extend(d for d in kw_defaults if d is not None)
    return exprs


def _builtin_use_in_function(node, scope_chain, module_bound, path):
    local_bound, declared_globals = _own_bindings_and_globals(node.body)
    shadow = (local_bound - declared_globals) | _param_names(node.args)
    new_chain = (shadow,) + scope_chain
    for default in _default_value_exprs(node.args):
        for finding in _builtin_use_walk(
                default, scope_chain, module_bound, path):
            yield finding
    for decorator in getattr(node, "decorator_list", None) or []:
        for finding in _builtin_use_walk(
                decorator, scope_chain, module_bound, path):
            yield finding
    for stmt in node.body:
        for finding in _builtin_use_walk(stmt, new_chain, module_bound, path):
            yield finding


def _builtin_use_in_lambda(node, scope_chain, module_bound, path):
    new_chain = (_param_names(node.args),) + scope_chain
    for default in _default_value_exprs(node.args):
        for finding in _builtin_use_walk(
                default, scope_chain, module_bound, path):
            yield finding
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

    A parameter default value or a decorator is real Python's enclosing
    scope, not the function's own - _builtin_use_in_function and
    _builtin_use_in_lambda walk both with the scope_chain passed in
    (the enclosing one), not the new, inner one built for the body, so a
    builtin name shadowed only by a same-named parameter is never
    wrongly treated as shadowed in its own default value."""
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


def _stdlib_import_finding(path, lineno, name, severity, judged_versions):
    removed_since = STDLIB_REMOVED_SINCE.get(name)
    if removed_since is None:
        return None
    applicable = _applicable_versions(removed_since, judged_versions)
    if not applicable:
        return None
    return Finding(
        path, lineno, "PY3-STDLIB", severity,
        "import of %s; removed on Python %s" % (name, removed_since),
        versions=applicable)


def _stdlib_name_finding(path, lineno, module, name, severity,
                         judged_versions):
    removed_since = STDLIB_REMOVED_NAMES.get((module, name))
    if removed_since is None:
        return None
    applicable = _applicable_versions(removed_since, judged_versions)
    if not applicable:
        return None
    return Finding(
        path, lineno, "PY3-STDLIB", severity,
        "import of %s.%s; removed on Python %s" % (
            module, name, removed_since),
        versions=applicable)


def check_stdlib_import(path, tree, judged_versions=ALL_TARGET_VERSIONS):
    guarded = _import_error_guarded_imports(tree)
    for node in _nodes(tree, ast.Import):
        severity = "warning" if id(node) in guarded else "blocker"
        for alias in node.names:
            finding = _stdlib_import_finding(
                path, node.lineno, alias.name, severity, judged_versions)
            if finding is not None:
                yield finding
    for node in _nodes(tree, ast.ImportFrom):
        if node.level == 0:
            severity = "warning" if id(node) in guarded else "blocker"
            finding = _stdlib_import_finding(
                path, node.lineno, node.module, severity, judged_versions)
            if finding is not None:
                yield finding
                continue
            for alias in node.names:
                finding = _stdlib_name_finding(
                    path, node.lineno, node.module, alias.name, severity,
                    judged_versions)
                if finding is not None:
                    yield finding


AST_RULES = [check_print, check_exec, check_backtick,
             check_dict_iter, check_metaclass, check_division,
             check_builtin_use]

# R6: rules whose applicable-versions subset depends on which versions a
# scan judges, so scanner.scan_file passes judged_versions to these (and
# only these) explicitly, rather than relying on the ALL_TARGET_VERSIONS
# default above (which exists only so tests can call this rule directly
# with the old 2-argument form).
VERSION_AWARE_AST_RULES = [check_stdlib_import]


def check_ne_op(path, tokens):
    # Python 2.7's tokenizer (and Python 3.14.7's) lexes <> as one OP
    # token, "<>". Starting with Python 3.14.9, the tokenizer no longer
    # recognizes <> as a compound operator at all and splits it into two
    # adjacent OP tokens, "<" immediately followed by ">" - confirmed via
    # a direct tokenize.tokenize() comparison between the two patch
    # releases (see MIGRATION.md). Both forms need detecting.
    prev_end = prev_was_lt = None
    for toknum, tokval, start, end, _line in tokens:
        if toknum == tokenize.OP and tokval == "<>":
            yield Finding(path, start[0], "PY3-NE-OP", "blocker",
                          "<> operator; Python 3 only has !=")
        elif (toknum == tokenize.OP and tokval == ">"
                and prev_was_lt and start == prev_end):
            yield Finding(path, start[0], "PY3-NE-OP", "blocker",
                          "<> operator; Python 3 only has !=")
        prev_end = end
        prev_was_lt = toknum == tokenize.OP and tokval == "<"


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


def check_raise_comma(path, tokens):
    # Was AST-based (ast.Raise.inst, set only by the comma form) until
    # AutoSteer CI found 741 PY3-RAISE-COMMA findings lost on a 3.14
    # scan of the real stdlib - 100% of that rule's findings, the
    # single largest loss of any rule (2b/R1). Unlike print and exec,
    # raise is a real keyword on both 2 and 3, so `raise E, value`
    # always fails ast.parse on Python 3 outright - but it tokenizes
    # cleanly there regardless (confirmed directly), so - like
    # check_except_comma just below, already token-based for the same
    # reason - this needs no tree at all and now runs identically
    # whether or not ast.parse succeeded on the running interpreter.
    pending = False
    depth = 0
    for toknum, tokval, start, _end, _line in tokens:
        if not pending:
            if toknum == tokenize.NAME and tokval == "raise":
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
                    path, start[0], "PY3-RAISE-COMMA", "blocker",
                    "raise E, value form; Python 3 only has "
                    "raise E(value)")
                pending = False
                continue
        if toknum == tokenize.NEWLINE:
            pending = False


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


def _statement_starts(tokens):
    """Indices into tokens of the first significant token of each simple
    statement at bracket depth 0: the start of the file, or right after a
    NEWLINE or a top-level ';'. Doesn't see a simple statement embedded
    after a compound-statement colon on the same physical line
    (`if x: print y`) - check_print/check_exec's own AST-based detection
    already covers that shape identically on both interpreters, so the
    token checks below only need to add what that shape is missing."""
    depth = 0
    at_start = True
    for i, tok in enumerate(tokens):
        toknum, tokval = tok[0], tok[1]
        if toknum in (tokenize.COMMENT, tokenize.NL, tokenize.INDENT,
                      tokenize.DEDENT):
            continue
        if at_start:
            yield i
        at_start = False
        if toknum == tokenize.NEWLINE:
            at_start = True
        elif toknum == tokenize.OP:
            if tokval in _BRACKETS_OPEN:
                depth += 1
            elif tokval in _BRACKETS_CLOSE:
                depth -= 1
            elif tokval == ";" and depth == 0:
                at_start = True


def _next_significant(tokens, i):
    """The index at or after i of the first token that isn't a COMMENT
    or NL - None past the end."""
    while i < len(tokens) and tokens[i][0] in (
            tokenize.COMMENT, tokenize.NL):
        i += 1
    return i if i < len(tokens) else None


def _matching_close(tokens, i):
    """Index just past the bracket at tokens[i] (which must be an
    opening bracket) that matches its close - None if it never closes."""
    depth = 0
    while i < len(tokens):
        toknum, tokval = tokens[i][0], tokens[i][1]
        if toknum == tokenize.OP:
            if tokval in _BRACKETS_OPEN:
                depth += 1
            elif tokval in _BRACKETS_CLOSE:
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return None


def check_print_redirect(path, tokens):
    """check_print's ast.Print-based detection is correct and complete on
    Python 2.7, but a true no-op on Python 3 (see its comment) - right
    for every print-statement shape that fails to parse under Python 3
    at all. One shape doesn't fail: `print >> file, ...`. Once print is
    an ordinary name instead of a keyword, that's just a right-shift
    expression followed by a tuple - entirely legal Python 3, parsing to
    something silently different instead of raising. Found against the
    real stdlib (abc.py's _dump_registry) via AutoSteer CI comparing a
    scan run under 2.7.18 against the same scan run under 3.14.9. Tokens
    lex the same way regardless of whether print is a keyword, so this
    needs no AST and works identically on every interpreter - gated on
    _PRINT_TYPE so it adds nothing on 2.7, where check_print already
    reports this shape; it only fills the Python-3 blind spot."""
    if _PRINT_TYPE is not None:
        return
    tokens = list(tokens)
    for i in _statement_starts(tokens):
        if tokens[i][0] != tokenize.NAME or tokens[i][1] != "print":
            continue
        j = _next_significant(tokens, i + 1)
        if (j is not None and tokens[j][0] == tokenize.OP
                and tokens[j][1] == ">>"):
            yield Finding(
                path, tokens[i][2][0], "PY3-PRINT", "blocker",
                "print statement; Python 3 has only the print() function")


def check_exec_in_clause(path, tokens):
    """Parallel case to check_print_redirect, for exec's `in globals[,
    locals]` clause: once exec is an ordinary name, `exec(code) in g`
    parses as a legal Python 3 containment expression (call exec(code),
    discard its None result, check membership in g) instead of raising.
    Bare `exec code in g` (no parens) already fails to parse under
    Python 3 on its own - two adjacent names with no operator between
    them - and is caught by PY3-PARSE directly, so only the parenthesized
    shape needs this."""
    if _EXEC_TYPE is not None:
        return
    tokens = list(tokens)
    for i in _statement_starts(tokens):
        if tokens[i][0] != tokenize.NAME or tokens[i][1] != "exec":
            continue
        j = _next_significant(tokens, i + 1)
        if j is None:
            continue
        after = None
        if tokens[j][0] == tokenize.OP and tokens[j][1] in _BRACKETS_OPEN:
            end = _matching_close(tokens, j)
            if end is not None:
                after = _next_significant(tokens, end)
        if (after is not None and tokens[after][0] == tokenize.NAME
                and tokens[after][1] == "in"):
            yield Finding(
                path, tokens[i][2][0], "PY3-EXEC-STMT", "blocker",
                "exec statement; Python 3 has only the exec() function")


def check_ur_string(path, tokens):
    # Python 2.7 accepts a raw-unicode string prefix with u before r,
    # case-insensitively: ur/Ur/uR/UR (confirmed empirically - ru/Ru/rU/RU
    # is a SyntaxError even on 2.7). Python 3 has never accepted combining
    # u and r in any order, even after 3.3 restored a no-op u prefix - a
    # 2-vs-3 boundary issue like <> or the old octal literal, found via a
    # real-stdlib parity scan (item 2a) surfacing posixpath.py and
    # lib2to3/fixes/fix_unicode.py, both of which real Python 3 cannot
    # compile and which no existing rule caught (R1).
    for toknum, tokval, start, _end, _line in tokens:
        if toknum == tokenize.STRING and tokval[:2].lower() == "ur":
            yield Finding(
                path, start[0], "PY3-UR-STRING", "blocker",
                "%s string prefix; Python 3 never allows combining u "
                "and r" % tokval[:2])


def _string_prefix_and_body(tokval):
    prefix = _STRING_PREFIX.match(tokval).group(0)
    rest = tokval[len(prefix):]
    quote = rest[:3] if rest[:3] in ("'''", '"""') else rest[:1]
    return prefix, rest[len(quote):-len(quote)]


def _has_invalid_unicode_escape(body):
    i, n = 0, len(body)
    while i < n:
        if body[i] != "\\" or i + 1 >= n:
            i += 1
            continue
        nxt = body[i + 1]
        if nxt == "u":
            if not _HEX4.match(body[i + 2:i + 6]):
                return True
            i += 6
        elif nxt == "U":
            if not _HEX8.match(body[i + 2:i + 10]):
                return True
            i += 10
        elif nxt == "N":
            m = _NAME_ESCAPE.match(body[i + 2:])
            if not m:
                return True
            i += 2 + m.end()
        else:
            i += 2
    return False


# R9: the deepest nesting of (), [] or {} CPython's tokenizer accepts
# before raising, per judged target version - measured directly against
# each version's own final release (3.6.15, 3.7.17, 3.8.20, 3.9.25,
# 3.10.19, 3.11.14, 3.12.12, 3.13.12, 3.14.7, 3.15.1; see MIGRATION.md's
# R9 evidence). The PEG parser (3.9 and later) shares one hardcoded,
# bracket-shape-agnostic constant, 200, across (), [] and {} - confirmed
# directly: the SyntaxError it raises says "too many nested parentheses"
# even when the source nests [] or {} instead, and three final releases
# spanning the range (3.9.25, 3.14.7, 3.15.1) all hit it at exactly the
# same depth for every shape. The old pgen parser (2.7, 3.6-3.8) instead
# overflows a real C stack, so its limit is a per-version resource limit,
# not a constant - and on 3.8.20 alone it even varies by shape (98 for ()
# and [], 104 for {}, confirmed deterministic across repeated runs):
# using the lower of the two there is the direction that can never
# under-report a real blocker (R1).
PAREN_NESTING_LIMIT = {
    "3.6": 92, "3.7": 92, "3.8": 98, "3.9": 200, "3.10": 200,
    "3.11": 200, "3.12": 200, "3.13": 200, "3.14": 200, "3.15": 200,
}


def check_nesting_depth(path, tokens, judged_versions=ALL_TARGET_VERSIONS):
    """Found via AutoSteer CI running the hostile input set against real
    interpreters 3.6-3.15: hostile/deep_nesting (150 nested parens) parses
    fine under Python 3.14 (its own limit is 200), so scanner.scan_file's
    ast.parse never raises and never reaches its PY3-PARSE fallback - but
    real Python 3.6-3.8 cannot compile it (their limit is lower), so R1's
    never-blocker-free guarantee was violated for those versions.

    This can only ever see a depth up to the running interpreter's own
    limit: on 3.9+, the C tokenizer enforces the same hardcoded 200 as
    the parser (confirmed directly - tokenizing depth 201 itself raises
    TokenError("too many nested parentheses") on 3.14.7, not just
    compile()), so scanner.scan_file's own _tokenize call would already
    have raised before this rule ever ran. The gap this closes is
    therefore exactly between a judged version's own, possibly lower,
    limit and the running interpreter's limit - which is where
    hostile/deep_nesting's 150 sits relative to 3.14 (200) and 3.6-3.8
    (<=98)."""
    depth = max_depth = 0
    deepest_line = 1
    for toknum, tokval, start, _end, _line in tokens:
        if toknum != tokenize.OP:
            continue
        if tokval in _BRACKETS_OPEN:
            depth += 1
            if depth > max_depth:
                max_depth = depth
                deepest_line = start[0]
        elif tokval in _BRACKETS_CLOSE:
            depth -= 1
    if max_depth == 0:
        return
    blocked = tuple(
        v for v in judged_versions
        if max_depth > PAREN_NESTING_LIMIT.get(v, float("inf")))
    if blocked:
        yield Finding(
            path, deepest_line, "PY3-NESTING-DEPTH", "blocker",
            "%d levels of nested (), [] or {}; exceeds the real parser's "
            "limit on Python %s" % (max_depth, ", ".join(blocked)),
            versions=blocked)


def check_unicode_escape(path, tokens):
    # A bare string literal (no u/r/b prefix) with a \u, \U or \N{...}
    # escape that isn't valid (4 hex digits, 8 hex digits, or a non-empty
    # {name} respectively) is inert text under Python 2.7 - a plain
    # string there never processes those escapes at all - but a
    # SyntaxError under Python 3, where every non-raw, non-bytes string
    # is unicode and always processes them (confirmed empirically on
    # both interpreters, both for a bare string and for b'...', which
    # behaves identically on both sides and must not be flagged). Found
    # via a real-stdlib parity scan (item 2a) surfacing json/__init__.py's
    # docstring, which real Python 3 cannot compile and which no existing
    # rule caught (R1). u- and r-prefixed strings are excluded: a raw
    # string never processes escapes on either side, and a u-prefixed
    # string already requires a valid escape under Python 2.7 too, so
    # there is no 2-vs-3 difference to report.
    for toknum, tokval, start, _end, _line in tokens:
        if toknum != tokenize.STRING:
            continue
        prefix, body = _string_prefix_and_body(tokval)
        if any(c in prefix.lower() for c in "rub"):
            continue
        if _has_invalid_unicode_escape(body):
            yield Finding(
                path, start[0], "PY3-UNICODE-ESCAPE", "blocker",
                "string has a \\u/\\U/\\N escape that is inert text "
                "under Python 2.7 but a SyntaxError under Python 3")


def _col_and_altcol(line):
    """(col, altcol): the same leading-whitespace column CPython's own
    tokenizer computes two ways - col with a tab advancing to the next
    multiple of 8 (the real rule, what an indent/dedent decision
    normally uses), altcol with a tab counting as a single column, the
    same as a space. check_ambiguous_indentation below flags whenever
    the two disagree about whether a line indents, dedents or matches
    its enclosing block - exactly Python 3's own TabError check."""
    col = altcol = 0
    for ch in line:
        if ch == "\t":
            col = (col // 8 + 1) * 8
            altcol += 1
        elif ch == " ":
            col += 1
            altcol += 1
        else:
            break
    return col, altcol


def check_ambiguous_indentation(path, tokens):
    """Python 3 has rejected this, as TabError, since 3.0; Python 2.7's
    own tokenizer and compiler never check it by default (only -tt
    makes the real CPython binary strict, and 2.7's tokenize module
    does not implement the altcol side of this at all) - so the real
    stdlib can and does ship files 2.7 accepts silently that every real
    Python 3 rejects outright (confirmed directly: a one-tab line
    followed by an eight-space line at the same real indentation level
    parses on 2.7.18, and raises TabError on 3.14.9's tokenizer alone,
    before the parser even runs). A straight port of CPython's own
    dual-stack check: every logical line's leading whitespace is
    measured two ways, col and altcol from _col_and_altcol above: a
    real indent, dedent or same-level match must agree under both, or
    it is exactly what makes Python 3 raise TabError. Tokenizing this
    file must itself have already succeeded for this rule to run at
    all - which 2.7.18 always does for an ambiguous file like this, but
    3.x's own tokenizer does not, so this rule's own Python-3-side
    blind spot is the same, already-accepted kind scanner.scan_file's
    docstring describes: a token-based rule can add nothing once
    tokenizing itself fails on the running interpreter."""
    tokens = list(tokens)
    indents = [(0, 0)]
    for i in _statement_starts(tokens):
        if tokens[i][0] in (tokenize.NEWLINE, tokenize.ENDMARKER):
            continue
        col, altcol = _col_and_altcol(tokens[i][4])
        while len(indents) > 1 and indents[-1][0] > col:
            indents.pop()
        top_col, top_altcol = indents[-1]
        if col > top_col:
            if altcol <= top_altcol:
                yield Finding(
                    path, tokens[i][2][0], "PY3-TAB-SPACE", "blocker",
                    "indentation mixes tabs and spaces in a way that is "
                    "ambiguous; Python 3 always rejects this, as "
                    "TabError")
            indents.append((col, altcol))
        elif altcol != top_altcol:
            yield Finding(
                path, tokens[i][2][0], "PY3-TAB-SPACE", "blocker",
                "indentation mixes tabs and spaces in a way that is "
                "ambiguous; Python 3 always rejects this, as TabError")


TOKEN_RULES = [check_ne_op, check_octal, check_long_suffix, check_raise_comma,
               check_except_comma, check_ur_string, check_unicode_escape,
               check_print_redirect, check_exec_in_clause,
               check_ambiguous_indentation]

# Parallel to VERSION_AWARE_AST_RULES above: scanner.scan_file passes
# judged_versions to these (and only these) token rules too.
VERSION_AWARE_TOKEN_RULES = [check_nesting_depth]

# Canonical codecs.lookup().name for every alias Python 3 marks
# _is_text_encoding=False (confirmed identical on 2.7.18 and on three
# final releases spanning the whole judged range: 3.6.15, 3.9.25,
# 3.15.1 - see MIGRATION.md's R9 evidence). "zip" is an alias for zlib,
# not a separate codec.
_NON_TEXT_CODECS = frozenset([
    "base64", "bz2", "hex", "quopri", "rot-13", "uu", "zlib"])


def check_non_text_coding_declaration(path, source):
    """A PEP 263 coding declaration naming a registered, non-text codec
    (base64, bz2, hex, quopri, rot13, uu, zlib or an alias of one) is
    decoded and compiled cleanly by Python 2.7, which runs no such check
    at all - but every real Python 3.6-3.15 rejects it outright
    (confirmed directly: `SyntaxError: '<name>' is not a text encoding;
    use codecs.decode() to handle arbitrary codecs`, identical on every
    final release tested). Found via a held-back input AutoSteer CI ran
    against the real interpreters: `# -*- coding: rot13 -*-` decodes "k"
    to "x", so `k = 1` becomes the valid statement `x = 1` under 2.7 -
    R1's never-blocker-free guarantee was violated because nothing
    existing could see this. detect_encoding raising SyntaxError (an
    unrecognized codec name, not merely a non-text one) is the already-
    documented item 2b divergence, not this rule's concern - this only
    fires for a codec both interpreters can actually look up.

    detect_encoding itself is lib2to3's backport on an interpreter that
    still has lib2to3 (2.7 through 3.12) but falls back to the real
    tokenize module starting on 3.13, where lib2to3 was removed - and
    the real tokenize.detect_encoding runs this same non-text check
    itself, raising LookupError (confirmed directly on 3.14.7) rather
    than returning a name for check_non_text_coding_declaration to look
    up. Harmless either way: scan_file's own ast.parse already raises
    SyntaxError for the identical input on any such interpreter, so this
    rule is never reached there in the real pipeline - only a direct
    call (as the tests below make) can observe it."""
    try:
        encoding, _ = detect_encoding(io.BytesIO(source).readline)
    except (SyntaxError, LookupError):
        return
    try:
        canonical = codecs.lookup(encoding).name
    except LookupError:
        return
    if canonical in _NON_TEXT_CODECS:
        yield Finding(
            path, 1, "PY3-NON-TEXT-CODING", "blocker",
            "coding declaration names %s, a non-text codec; Python 3 "
            "rejects it as a source encoding" % canonical)


# Rules that read the raw source bytes directly, rather than the AST or
# the token stream - currently just the one PEP 263 cookie check above.
SOURCE_RULES = [check_non_text_coding_declaration]
