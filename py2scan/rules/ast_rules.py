# -*- coding: utf-8 -*-
"""Rules that read a module's parse tree.

The tree comes from parso's Python 2.7 grammar (py2scan.parsing), not from
the `ast` module: native ast.parse() rejects every one of these constructs
outright as soon as the host is Python 3, so it cannot be the backbone for
a scanner that straddles 2.7 and 3.x. See py2scan/parsing.py and the
migration strategy notes in MIGRATION.md for why.

Written to run on Python 2.7 or Python 3.x: no f-strings, no `yield from`,
no walrus, nothing newer than 2.7 syntax.
"""
from py2scan.findings import Finding


def _walk(node):
    yield node
    for c in getattr(node, "children", ()):
        for n in _walk(c):
            yield n


def _nodes(tree, type_name):
    for node in _walk(tree):
        if node.type == type_name:
            yield node


def _has_future_name(tree, name):
    """Whether the module has `from __future__ import <name>`. CPython's own
    2.7 parser honors this while parsing the rest of that module (print
    stops being a statement keyword the moment print_function is imported);
    parso's static 2.7 grammar never does, so callers that care about that
    CPython-specific behavior check it themselves."""
    for node in _nodes(tree, "import_from"):
        children = node.children
        if getattr(children[1], "value", None) != "__future__":
            continue
        import_idx = None
        for i, c in enumerate(children):
            if getattr(c, "value", None) == "import":
                import_idx = i
                break
        if import_idx is None:
            continue
        for c in children[import_idx + 1:]:
            for leaf in _walk(c):
                if getattr(leaf, "value", None) == name:
                    return True
    return False


def check_print(path, tree, tokens):
    if _has_future_name(tree, "print_function"):
        # Every print_stmt parso found here is really a call expression
        # under real CPython; none of them are Python-3 blockers.
        return
    for node in _nodes(tree, "print_stmt"):
        yield Finding(path, node.start_pos[0], "PY3-PRINT", "blocker",
                      "print statement; Python 3 has only the print() function")


def check_exec(path, tree, tokens):
    for node in _nodes(tree, "exec_stmt"):
        yield Finding(path, node.start_pos[0], "PY3-EXEC-STMT", "blocker",
                      "exec statement; Python 3 has only the exec() function")


def check_backtick(path, tree, tokens):
    for node in _nodes(tree, "atom"):
        children = node.children
        if children and getattr(children[0], "value", None) == "`":
            yield Finding(path, node.start_pos[0], "PY3-BACKTICK", "blocker",
                          "backtick repr expression; Python 3 has only the repr() function")


def check_raise_comma(path, tree, tokens):
    for node in _nodes(tree, "raise_stmt"):
        if any(getattr(c, "value", None) == "," for c in node.children):
            yield Finding(path, node.start_pos[0], "PY3-RAISE-COMMA", "blocker",
                          "raise with comma-separated value; Python 3 uses raise E(value)")


DICT_ITER_METHODS = frozenset(["iteritems", "iterkeys", "itervalues", "has_key"])


def check_dict_iter(path, tree, tokens):
    for node in _nodes(tree, "trailer"):
        children = node.children
        if (len(children) == 2 and getattr(children[0], "value", None) == "."
                and getattr(children[1], "value", None) in DICT_ITER_METHODS):
            parent = node.parent
            siblings = parent.children
            idx = siblings.index(node)
            if idx + 1 < len(siblings):
                nxt = siblings[idx + 1]
                if nxt.type == "trailer" and getattr(nxt.children[0], "value", None) == "(":
                    yield Finding(path, node.start_pos[0], "PY3-DICT-ITER", "blocker",
                                  "%s(); not available in Python 3" % children[1].value)


def check_metaclass(path, tree, tokens):
    for cls in _nodes(tree, "classdef"):
        suite = cls.children[-1]
        for stmt in getattr(suite, "children", ()):
            if stmt.type == "simple_stmt":
                expr = stmt.children[0]
                if (expr.type == "expr_stmt" and expr.children[0].type == "name"
                        and expr.children[0].value == "__metaclass__"):
                    yield Finding(path, stmt.start_pos[0], "PY3-METACLASS", "warning",
                                  "__metaclass__ assignment; Python 3 uses the metaclass= keyword")


# ---------------------------------------------------------------------------
# PY3-STDLIB

STDLIB_MODULES = frozenset([
    "urllib2", "urlparse", "ConfigParser", "Queue", "cPickle", "cStringIO",
    "StringIO", "httplib", "HTMLParser", "commands", "SocketServer",
    "Tkinter", "__builtin__", "copy_reg", "xmlrpclib", "thread", "Cookie",
    "cookielib", "BaseHTTPServer", "SimpleHTTPServer", "htmlentitydefs",
    "md5", "sha", "sets", "UserDict",
])

# R2: a bare except, or a handler naming one of these (alone or in a tuple),
# makes a PY3-STDLIB import inside the try (body or a handler body) a
# warning instead of a blocker.
_IMPORT_ERROR_CATCHERS = frozenset(
    ["ImportError", "ModuleNotFoundError", "Exception", "BaseException", "StandardError"])


def _dotted_module_names(node):
    """Top-level module name(s) a dotted_name/dotted_as_name/... node imports."""
    if node is None or getattr(node, "value", None) in ("(", ")", ",", "*", "import"):
        return
    if node.type == "name":
        yield node.value
    elif node.type == "dotted_name":
        yield node.children[0].value
    elif node.type == "dotted_as_name":
        yield node.children[0].value if node.children[0].type != "dotted_name" \
            else node.children[0].children[0].value
    elif node.type in ("dotted_as_names", "import_as_names", "testlist", "exprlist"):
        for c in node.children:
            for name in _dotted_module_names(c):
                yield name
    else:
        for c in getattr(node, "children", ()):
            for name in _dotted_module_names(c):
                yield name


def _handler_catches_import_error(marker):
    """marker is either an except_clause node (a named exception) or the
    bare 'except' keyword leaf: parso collapses a clause with no test down
    to that single leaf instead of wrapping it, so a bare except never
    actually appears as a 1-child except_clause node."""
    if getattr(marker, "type", None) != "except_clause":
        return True  # bare "except:"
    exc_type = marker.children[1]
    names = set(n.value for n in _walk(exc_type) if n.type == "name")
    return bool(names & _IMPORT_ERROR_CATCHERS)


def _except_markers(try_stmt):
    """Yield (marker, handler_suite) for each handler clause in a try_stmt."""
    children = try_stmt.children
    for i, c in enumerate(children):
        is_marker = c.type == "except_clause" or getattr(c, "value", None) == "except"
        if is_marker and i + 2 < len(children):
            yield c, children[i + 2]


def _qualifying_try_ancestor(node):
    """Walk up from node; return the nearest try_stmt whose body or handler
    body (not else/finally, not through a nested funcdef/lambdef) directly
    contains node, and whose handler catches ImportError. None otherwise."""
    current = node
    parent = node.parent
    while parent is not None:
        if parent.type in ("funcdef", "lambdef"):
            return None  # that suite runs later, outside the try
        if parent.type == "try_stmt":
            try_suite = parent.children[2]
            if current is try_suite:
                # inside the try body: any qualifying handler is enough
                for marker, _ in _except_markers(parent):
                    if _handler_catches_import_error(marker):
                        return parent
                return None
            for marker, handler_suite in _except_markers(parent):
                if current is handler_suite and _handler_catches_import_error(marker):
                    return parent
        current = parent
        parent = parent.parent
    return None


def check_stdlib(path, tree, tokens):
    for node in _nodes(tree, "import_name"):
        for top in _dotted_module_names(node.children[1]):
            if top in STDLIB_MODULES:
                severity = "warning" if _qualifying_try_ancestor(node) else "blocker"
                yield Finding(path, node.start_pos[0], "PY3-STDLIB", severity,
                              "import of %s; renamed or removed in Python 3" % top)
    for node in _nodes(tree, "import_from"):
        module_node = node.children[1]
        tops = list(_dotted_module_names(module_node))
        top = tops[0] if tops else None
        if top in STDLIB_MODULES:
            severity = "warning" if _qualifying_try_ancestor(node) else "blocker"
            yield Finding(path, node.start_pos[0], "PY3-STDLIB", severity,
                          "import from %s; renamed or removed in Python 3" % top)


# ---------------------------------------------------------------------------
# PY3-BUILTIN

BUILTIN_NAMES = frozenset([
    "unicode", "basestring", "long", "xrange", "raw_input", "unichr",
    "execfile", "reduce", "file", "cmp", "reload", "apply", "buffer",
    "intern", "coerce",
])

_GROUPING_TYPES = ("testlist", "exprlist", "testlist_star_expr", "testlist_comp", "atom")


def _target_names(node):
    """Yield the plain-name leaves bound by an assignment/for/with/except/del
    target expression. Attribute and subscript targets (obj.x, d[k]) are not
    name bindings and are skipped."""
    if node is None:
        return
    if node.type == "name":
        yield node
    elif node.type in _GROUPING_TYPES:
        for c in node.children:
            if getattr(c, "value", None) not in (",", "(", ")", "[", "]"):
                for leaf in _target_names(c):
                    yield leaf


def _enclosing_funcdef(node):
    p = node.parent
    while p is not None:
        if p.type == "funcdef":
            return p
        p = p.parent
    return None


class _ScopeCollector(object):
    """Collects the binding facts _collect_scopes needs, one node type at a
    time (see _SCOPE_VISITORS). Each visit_* method handles exactly one
    parso node type, so no single method accumulates the branch count of
    the binding rules as a whole."""

    def __init__(self):
        self.target_leaves = set()
        self.local_targets_by_func = {}
        self.declared_globals_by_func = {}
        self.module_level_names = set()

    def add_target(self, leaf):
        self.target_leaves.add(leaf)
        func = _enclosing_funcdef(leaf)
        if func is None:
            self.module_level_names.add(leaf.value)
        else:
            self.local_targets_by_func.setdefault(func, set()).add(leaf.value)

    def add_param(self, leaf, func):
        self.target_leaves.add(leaf)
        self.local_targets_by_func.setdefault(func, set()).add(leaf.value)

    def add_outer_name(self, def_or_class_node, name_leaf):
        self.target_leaves.add(name_leaf)
        outer_func = _enclosing_funcdef(def_or_class_node)
        if outer_func is None:
            self.module_level_names.add(name_leaf.value)
        else:
            self.local_targets_by_func.setdefault(outer_func, set()).add(name_leaf.value)

    def visit_expr_stmt(self, node):
        children = node.children
        for i in range(0, len(children) - 1, 2):
            for leaf in _target_names(children[i]):
                self.add_target(leaf)

    def visit_for_target(self, node):
        children = node.children
        if len(children) > 1:
            for leaf in _target_names(children[1]):
                self.add_target(leaf)

    def visit_with_item(self, node):
        children = node.children
        for i, c in enumerate(children):
            if getattr(c, "value", None) == "as" and i + 1 < len(children):
                for leaf in _target_names(children[i + 1]):
                    self.add_target(leaf)

    def visit_except_clause(self, node):
        children = node.children
        if len(children) >= 4 and getattr(children[2], "value", None) in ("as", ","):
            for leaf in _target_names(children[3]):
                self.add_target(leaf)

    def visit_del_stmt(self, node):
        for leaf in _target_names(node.children[1]):
            self.add_target(leaf)

    def visit_global_stmt(self, node):
        # The names named here are never a *use* of anything they happen to
        # shadow (BUILTIN_NAMES included) - they only ever declare scoping
        # intent. Mark them like any other binding target so check_builtin's
        # final walk skips them.
        name_leaves = [c for c in node.children if c.type == "name"]
        self.target_leaves.update(name_leaves)
        func = _enclosing_funcdef(node)
        if func is not None:
            names = set(c.value for c in name_leaves)
            self.declared_globals_by_func.setdefault(func, set()).update(names)

    def visit_import(self, node):
        for leaf in _import_bound_leaves(node):
            self.add_target(leaf)

    def visit_funcdef(self, node):
        self.add_outer_name(node, node.children[1])
        params = node.children[2]
        for p in params.children:
            if p.type == "param":
                for c in p.children:
                    if c.type == "name":
                        self.add_param(c, node)
                        break

    def visit_classdef(self, node):
        self.add_outer_name(node, node.children[1])


_SCOPE_VISITORS = {
    "expr_stmt": _ScopeCollector.visit_expr_stmt,
    "for_stmt": _ScopeCollector.visit_for_target,
    "sync_comp_for": _ScopeCollector.visit_for_target,
    "comp_for": _ScopeCollector.visit_for_target,
    "old_comp_for": _ScopeCollector.visit_for_target,
    "with_item": _ScopeCollector.visit_with_item,
    "except_clause": _ScopeCollector.visit_except_clause,
    "del_stmt": _ScopeCollector.visit_del_stmt,
    "global_stmt": _ScopeCollector.visit_global_stmt,
    "import_name": _ScopeCollector.visit_import,
    "import_from": _ScopeCollector.visit_import,
    "funcdef": _ScopeCollector.visit_funcdef,
    "classdef": _ScopeCollector.visit_classdef,
}


def _collect_scopes(tree):
    """Returns (target_leaves, local_targets_by_func, declared_globals_by_func,
    module_level_names) following Python 2.7's own binding rules (R3):
    assignment, for, with, except, del and comprehension targets, plus
    parameters, import names, and def/class names, each bind in their
    enclosing function (or at module level if not inside one); a bare
    `global X` binds nothing by itself."""
    collector = _ScopeCollector()
    for node in _walk(tree):
        visitor = _SCOPE_VISITORS.get(node.type)
        if visitor is not None:
            visitor(collector, node)
    return (collector.target_leaves, collector.local_targets_by_func,
            collector.declared_globals_by_func, collector.module_level_names)


def _import_bound_leaves(node):
    if node.type == "import_name":
        for leaf in _dotted_as_bound_leaves(node.children[1]):
            yield leaf
    else:
        import_idx = None
        for i, c in enumerate(node.children):
            if getattr(c, "value", None) == "import":
                import_idx = i
                break
        if import_idx is not None:
            for c in node.children[import_idx + 1:]:
                for leaf in _dotted_as_bound_leaves(c):
                    yield leaf


def _as_alias(dotted_as_name):
    """The leaf after 'as' in a dotted_as_name node, or None if it has none."""
    children = dotted_as_name.children
    for i, c in enumerate(children):
        if getattr(c, "value", None) == "as":
            return children[i + 1]
    return None


def _dotted_as_bound_leaves(node):
    if node is None or getattr(node, "value", None) in ("(", ")", ",", "*"):
        return
    if node.type == "name":
        yield node
    elif node.type == "dotted_name":
        yield node.children[0]
    elif node.type == "dotted_as_name":
        alias = _as_alias(node)
        if alias is not None:
            yield alias
        else:
            for leaf in _dotted_as_bound_leaves(node.children[0]):
                yield leaf
    elif node.type in ("dotted_as_names", "import_as_names", "testlist", "exprlist"):
        for c in node.children:
            for leaf in _dotted_as_bound_leaves(c):
                yield leaf


def check_builtin(path, tree, tokens):
    target_leaves, local_by_func, globals_by_func, module_level = _collect_scopes(tree)

    module_bound = set(module_level)
    for func, declared in globals_by_func.items():
        local = local_by_func.get(func, set())
        module_bound.update(declared & local)

    true_local_by_func = {}
    for func, local in local_by_func.items():
        declared = globals_by_func.get(func, set())
        true_local_by_func[func] = local - declared

    for leaf in _walk(tree):
        if leaf.type != "name" or leaf in target_leaves:
            continue
        if leaf.value not in BUILTIN_NAMES:
            continue
        shadowed = False
        func = _enclosing_funcdef(leaf)
        while func is not None:
            if leaf.value in true_local_by_func.get(func, ()):
                shadowed = True
                break
            func = _enclosing_funcdef(func)
        if not shadowed and leaf.value in module_bound:
            shadowed = True
        if not shadowed:
            yield Finding(path, leaf.start_pos[0], "PY3-BUILTIN", "blocker",
                          "%s; removed or renamed in Python 3" % leaf.value)


AST_RULES = [check_print, check_exec, check_backtick, check_raise_comma,
             check_dict_iter, check_builtin, check_stdlib, check_metaclass]
