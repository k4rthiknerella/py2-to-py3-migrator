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
import re

from py2scan.findings import Finding

_UR_STRING_RE = re.compile(r'^[uU][rR][\'"]')


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


def check_print(path, tree, tokens, versions):
    if _has_future_name(tree, "print_function"):
        # Every print_stmt parso found here is really a call expression
        # under real CPython; none of them are Python-3 blockers.
        return
    for node in _nodes(tree, "print_stmt"):
        yield Finding(path, node.start_pos[0], "PY3-PRINT", "blocker",
                      "print statement; Python 3 has only the print() function", versions)


def check_exec(path, tree, tokens, versions):
    for node in _nodes(tree, "exec_stmt"):
        yield Finding(path, node.start_pos[0], "PY3-EXEC-STMT", "blocker",
                      "exec statement; Python 3 has only the exec() function", versions)


def check_backtick(path, tree, tokens, versions):
    for node in _nodes(tree, "atom"):
        children = node.children
        if children and getattr(children[0], "value", None) == "`":
            yield Finding(path, node.start_pos[0], "PY3-BACKTICK", "blocker",
                          "backtick repr expression; Python 3 has only the repr() function",
                          versions)


def check_raise_comma(path, tree, tokens, versions):
    for node in _nodes(tree, "raise_stmt"):
        if any(getattr(c, "value", None) == "," for c in node.children):
            yield Finding(path, node.start_pos[0], "PY3-RAISE-COMMA", "blocker",
                          "raise with comma-separated value; Python 3 uses raise E(value)",
                          versions)


DICT_ITER_METHODS = frozenset(["iteritems", "iterkeys", "itervalues", "has_key"])


def check_dict_iter(path, tree, tokens, versions):
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
                                  "%s(); not available in Python 3" % children[1].value, versions)


def check_metaclass(path, tree, tokens, versions):
    for cls in _nodes(tree, "classdef"):
        suite = cls.children[-1]
        for stmt in getattr(suite, "children", ()):
            if stmt.type == "simple_stmt":
                expr = stmt.children[0]
                if (expr.type == "expr_stmt" and expr.children[0].type == "name"
                        and expr.children[0].value == "__metaclass__"):
                    yield Finding(path, stmt.start_pos[0], "PY3-METACLASS", "warning",
                                  "__metaclass__ assignment; Python 3 uses the metaclass= keyword",
                                  versions)


def check_tuple_param(path, tree, tokens, versions):
    """def f((a, b)): ... / lambda (a, b): ...: tuple-parameter unpacking.
    Valid 2.7 syntax (fpdef in the grammar), removed outright in 3.0 and
    never reintroduced - confirmed against real 2.7.18 (compiles) and
    3.14.9 (SyntaxError: Function parameters cannot be parenthesized), so
    this blocks every judged version, not just the ones tested directly."""
    for node in _nodes(tree, "fpdef"):
        yield Finding(path, node.start_pos[0], "PY3-TUPLE-PARAM", "blocker",
                      "tuple parameter unpacking; not supported in Python 3", versions)


def check_ur_string(path, tree, tokens, versions):
    """ur"..."/uR/Ur/UR: a raw unicode literal. Valid 2.7 syntax; PEP 414
    restored the bare u"..." prefix in Python 3.3+ but never ur"...", so
    this is a SyntaxError on every judged version (3.6 through 3.15,
    confirmed directly against each one's real interpreter: "invalid
    syntax" on the older ones, "'u' and 'r' prefixes are incompatible" on
    the newer ones - same break, worded differently).

    This must read parso's tree, not the native token stream: on a
    Python 3 host, tokenize.tokenize() raises TokenError the moment it
    reaches a ur"..." literal, which silently empties the token list for
    every token-based rule for the rest of the file (see
    py2scan/parsing.py's _tokenize) - parso's grammar has no such gap."""
    for node in _nodes(tree, "string"):
        if _UR_STRING_RE.match(node.value):
            yield Finding(path, node.start_pos[0], "PY3-UR-STRING", "blocker",
                          "%s; the ur\"...\" raw-unicode prefix does not exist in "
                          "Python 3" % node.value, versions)


_STRING_PREFIX_RE = re.compile(r'^[a-zA-Z]*')
_BAD_ESCAPE_RE = re.compile(
    r'\\\\'                       # an escaped backslash: never an escape start
    r'|\\u[0-9A-Fa-f]{0,4}'       # \u needs exactly 4 hex digits
    r'|\\U[0-9A-Fa-f]{0,8}'       # \U needs exactly 8 hex digits
    r'|\\N\{[^}]*\}?'             # \N{...} needs a non-empty, closed name
    r'|\\.')                      # any other escape: not this rule's concern


def _has_malformed_unicode_escape(text):
    for m in _BAD_ESCAPE_RE.finditer(text):
        g = m.group()
        if g.startswith(u"\\u") and len(g) != 6:
            return True
        if g.startswith(u"\\U") and len(g) != 10:
            return True
        if g.startswith(u"\\N{") and (not g.endswith(u"}") or g == u"\\N{}"):
            return True
    return False


def check_bad_unicode_escape(path, tree, tokens, versions):
    """A plain (unprefixed) or `u"..."` string literal containing `\\u`,
    `\\U`, or `\\N{...}` not followed by a complete, valid escape: e.g. a
    docstring that writes the literal text "\\uXXXX" to describe a format,
    not to encode a character (real repro: CPython 2.7's own
    json/__init__.py, line 133). Python 2's plain `str` is bytes-like and
    never treats `\\u`/`\\U`/`\\N` as escapes at all - whatever follows is
    left as literal text, valid or not. Python 3's plain `str` is always
    unicode, so the same bytes are mandatory, validated escapes: an
    incomplete one is a SyntaxError, not merely a changed meaning. A raw
    (`r`) or byte (`b`) prefix is excluded - raw strings never process any
    escape, and `\\u`/`\\U`/`\\N` were never byte-string escapes in either
    version, so nothing changes for those two prefixes."""
    for node in _nodes(tree, "string"):
        prefix = _STRING_PREFIX_RE.match(node.value).group().lower()
        if "r" in prefix or "b" in prefix:
            continue
        if _has_malformed_unicode_escape(node.value):
            yield Finding(path, node.start_pos[0], "PY3-BAD-ESCAPE", "blocker",
                          "incomplete \\u/\\U/\\N escape in a non-raw string; "
                          "a SyntaxError in Python 3, literal text in "
                          "Python 2", versions)


_RESERVED_SINCE_37 = frozenset(["async", "await"])


def check_async_reserved(path, tree, tokens, versions):
    """async/await used as ordinary identifiers: valid 2.7 syntax (they are
    plain NAME tokens there, never keywords) and still valid through real
    Python 3.6.15, but a SyntaxError on real Python 3.7.17 once PEP 492
    made them reserved words. Only the versions actually >= 3.7 among the
    ones judged are affected."""
    gated = tuple(v for v in versions if v >= (3, 7))
    if not gated:
        return
    for leaf in _walk(tree):
        if leaf.type == "name" and leaf.value in _RESERVED_SINCE_37:
            yield Finding(path, leaf.start_pos[0], "PY3-ASYNC-RESERVED", "blocker",
                          "%s; reserved keyword in Python 3.7 and later" % leaf.value, gated)


# ---------------------------------------------------------------------------
# PY3-STDLIB

# R8: every top-level 2.7 stdlib module missing from a judged version, not
# just this original set. Renamed/removed at the 3.0 boundary (PEP 3108)
# and gone from every judged version (3.6-3.15) ever since, confirmed by
# `import NAME` on real 2.7.18 (succeeds) and on 3.6.15 through 3.15.1
# (ModuleNotFoundError, every one). urllib and dbm are deliberately absent
# here even though PEP 3108 lists them as renamed: both names survive as
# package names in Python 3 (urllib.request etc., dbm.gnu etc.), so a bare
# `import urllib` or `import dbm` succeeds there too - flagging the bare
# import would be a false positive; the real break is an attribute access
# (urllib.urlopen), which this import-level rule does not reach.
UNIVERSAL_STDLIB_MODULES = frozenset([
    "urllib2", "urlparse", "ConfigParser", "Queue", "cPickle", "cStringIO",
    "StringIO", "httplib", "HTMLParser", "commands", "SocketServer",
    "Tkinter", "__builtin__", "copy_reg", "xmlrpclib", "thread", "Cookie",
    "cookielib", "BaseHTTPServer", "SimpleHTTPServer", "htmlentitydefs",
    "md5", "sha", "sets", "UserDict",
    # PEP 3108 "Previously Deprecated" / "Hardly Used" / "Obsolete":
    "mimetools", "MimeWriter", "mimify", "multifile", "posixfile", "rfc822",
    "timing", "audiodev", "imputil", "mutex", "stringold", "user", "new",
    "Bastion", "rexec", "Canvas", "compiler", "dircache", "dl", "fpformat",
    "htmllib", "ihooks", "imageop", "linuxaudiodev", "mhlib", "popen2",
    "sgmllib", "sre", "UserList", "UserString",
    # PEP 3108 "Modules Renamed" (old name -> new), minus urllib/dbm:
    "_winreg", "markupbase", "repr", "anydbm", "dbhash", "dumbdbm", "gdbm",
    "whichdb", "CGIHTTPServer", "robotparser", "DocXMLRPCServer",
    "SimpleXMLRPCServer", "Dialog", "FileDialog", "FixTk", "ScrolledText",
    "SimpleDialog", "Tix", "Tkconstants", "Tkdnd", "tkColorChooser",
    "tkCommonDialog", "tkFileDialog", "tkFont", "tkMessageBox",
    "tkSimpleDialog",
])

# R8: modules that stayed importable past the 3.0 boundary and were only
# removed later, within the 3.6-3.15 range py2scan judges. Each entry is
# (module, version_removed_in): the module blocks that version and every
# later one, and no earlier one. Sources, each cross-checked by import on
# the real interpreters either side of the boundary:
#   - PEP 594: aifc, audioop, cgi, cgitb, chunk, crypt, imghdr, mailcap,
#     msilib, nis, nntplib, ossaudiodev, pipes, sndhdr, spwd, sunau,
#     telnetlib, uu, xdrlib -> removed in 3.13. (nis imports fail on this
#     machine starting at 3.9, but that is this build missing libnsl, not
#     a real removal - PEP 594's documented 3.13 wins over that empirical
#     result, per R8's own "missing from a single build" caveat.)
#   - What's New in 3.12: asynchat, asyncore, smtpd, imp -> 3.12.
#   - PEP 632: distutils -> 3.12.
#   - What's New in 3.13: lib2to3 -> 3.13 (ships alongside the PEP 594 set).
#   - What's New in 3.15: sre_compile, sre_constants, sre_parse -> 3.15.
#   - Empirical only (no PEP; confirmed OK on the version before, gone on
#     the version named): macpath -> 3.8, parser/symbol/formatter -> 3.10,
#     binhex -> 3.11.
VERSIONED_STDLIB_REMOVALS = {
    "macpath": (3, 8),
    "parser": (3, 10),
    "symbol": (3, 10),
    "formatter": (3, 10),
    "binhex": (3, 11),
    "asynchat": (3, 12),
    "asyncore": (3, 12),
    "smtpd": (3, 12),
    "imp": (3, 12),
    "distutils": (3, 12),
    "aifc": (3, 13),
    "audioop": (3, 13),
    "cgi": (3, 13),
    "cgitb": (3, 13),
    "chunk": (3, 13),
    "crypt": (3, 13),
    "imghdr": (3, 13),
    "mailcap": (3, 13),
    "msilib": (3, 13),
    "nis": (3, 13),
    "nntplib": (3, 13),
    "ossaudiodev": (3, 13),
    "pipes": (3, 13),
    "sndhdr": (3, 13),
    "spwd": (3, 13),
    "sunau": (3, 13),
    "telnetlib": (3, 13),
    "uu": (3, 13),
    "xdrlib": (3, 13),
    "lib2to3": (3, 13),
    "sre_compile": (3, 15),
    "sre_constants": (3, 15),
    "sre_parse": (3, 15),
}

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


def _stdlib_removal_versions(module, versions):
    """None if module is unaffected by every judged version; otherwise the
    subset of versions it blocks."""
    if module in UNIVERSAL_STDLIB_MODULES:
        return versions
    removed_in = VERSIONED_STDLIB_REMOVALS.get(module)
    if removed_in is None:
        return None
    return tuple(v for v in versions if v >= removed_in) or None


def check_stdlib(path, tree, tokens, versions):
    for node in _nodes(tree, "import_name"):
        for top in _dotted_module_names(node.children[1]):
            affected = _stdlib_removal_versions(top, versions)
            if affected:
                severity = "warning" if _qualifying_try_ancestor(node) else "blocker"
                yield Finding(path, node.start_pos[0], "PY3-STDLIB", severity,
                              "import of %s; renamed or removed in Python 3" % top, affected)
    for node in _nodes(tree, "import_from"):
        module_node = node.children[1]
        tops = list(_dotted_module_names(module_node))
        top = tops[0] if tops else None
        affected = _stdlib_removal_versions(top, versions) if top else None
        if affected:
            severity = "warning" if _qualifying_try_ancestor(node) else "blocker"
            yield Finding(path, node.start_pos[0], "PY3-STDLIB", severity,
                          "import from %s; renamed or removed in Python 3" % top, affected)


# ---------------------------------------------------------------------------
# PY3-BUILTIN

# R10: every name in every judged version's builtins module that 2.7's
# __builtin__ has and it does not - not just this original set. Derived by
# diffing dir(__builtin__) on real 2.7.18 against dir(builtins) on real
# 3.6.15 through 3.15.1: all ten give the exact same 16-name difference, so
# this one frozenset covers every judged version with no per-version table
# needed (unlike PY3-STDLIB, nothing here varies release to release).
BUILTIN_NAMES = frozenset([
    "unicode", "basestring", "long", "xrange", "raw_input", "unichr",
    "execfile", "reduce", "file", "cmp", "reload", "apply", "buffer",
    "intern", "coerce", "StandardError",
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


def _is_attribute_name(leaf):
    """True for the "file" in "chunk.file": a name leaf that is the
    attribute half of a trailer ("." name), not a reference to anything
    in scope at all - obj.file, obj.buffer, obj.cmp(...) etc. never
    touch the builtin of the same name."""
    parent = leaf.parent
    return (parent is not None and parent.type == "trailer"
            and getattr(parent.children[0], "value", None) == ".")


def _is_keyword_argument_name(leaf):
    """True for the "file" in "print(x, file=y)": the name half of a
    call's keyword argument, not a reference to anything in scope -
    unlike a function *definition's* parameter name (already excluded
    via target_leaves/add_param), a call's keyword argument name has no
    binding of its own to collect."""
    parent = leaf.parent
    return (parent is not None and parent.type == "argument"
            and parent.children[0] is leaf
            and getattr(parent.children[1], "value", None) == "=")


def _is_non_reference_use(leaf):
    """True for any name leaf whose position never reads whatever is
    bound to that name - an attribute name or a call's keyword argument
    name, both syntactically identical "name" leaves to a real reference
    but never looked up anywhere."""
    return _is_attribute_name(leaf) or _is_keyword_argument_name(leaf)


def _resolve_shadowing_scopes(local_by_func, globals_by_func, module_level):
    """A `global x` declaration inside a function that also assigns x
    locally binds x at module scope, not function scope (CPython: the
    global statement wins); split each function's locals into those two
    buckets up front so check_builtin's own walk only has to look things
    up, not compute them."""
    module_bound = set(module_level)
    for func, declared in globals_by_func.items():
        local = local_by_func.get(func, set())
        module_bound.update(declared & local)

    true_local_by_func = {}
    for func, local in local_by_func.items():
        declared = globals_by_func.get(func, set())
        true_local_by_func[func] = local - declared

    return true_local_by_func, module_bound


def check_builtin(path, tree, tokens, versions):
    target_leaves, local_by_func, globals_by_func, module_level = _collect_scopes(tree)
    true_local_by_func, module_bound = _resolve_shadowing_scopes(
        local_by_func, globals_by_func, module_level)

    for leaf in _walk(tree):
        if leaf.type != "name" or leaf in target_leaves:
            continue
        if leaf.value not in BUILTIN_NAMES:
            continue
        if _is_non_reference_use(leaf):
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
                          "%s; removed or renamed in Python 3" % leaf.value, versions)


_RESERVED_SINCE_30 = frozenset(["True", "False"])


def check_keyword_binding(path, tree, tokens, versions):
    """True/False used as a binding target (assignment, del, for, with-as,
    except-as, a function/class name, a parameter, an import-as name):
    valid 2.7 syntax (True/False are plain builtins there, not grammar
    keywords, so nothing stops rebinding them) but a hard SyntaxError in
    every Python 3, since 3.0 made both real keywords. Confirmed on real
    2.7.18 (every form above compiles) and 3.14.9 (every form is a
    SyntaxError). None is deliberately excluded: 2.7's own compiler
    already rejects binding None ("cannot assign to None"), so that is
    already-broken 2.7 source, not a 2-to-3 migration concern."""
    target_leaves = _collect_scopes(tree)[0]
    for leaf in target_leaves:
        if leaf.value in _RESERVED_SINCE_30:
            yield Finding(path, leaf.start_pos[0], "PY3-KEYWORD-BINDING", "blocker",
                          "%s used as a binding target; reserved keyword in Python 3"
                          % leaf.value, versions)


AST_RULES = [check_print, check_exec, check_backtick, check_raise_comma,
             check_dict_iter, check_builtin, check_stdlib, check_metaclass,
             check_tuple_param, check_async_reserved, check_keyword_binding,
             check_ur_string, check_bad_unicode_escape]
