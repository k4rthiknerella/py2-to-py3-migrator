# -*- coding: utf-8 -*-
import ast
import functools
import io
import os
import stat
import sys
import tokenize

from concurrent.futures import ProcessPoolExecutor

from py2scan import config as config_module
from py2scan.findings import Finding
from py2scan.rules import (
    ALL_TARGET_VERSIONS, AST_RULES, SOURCE_RULES, TOKEN_RULES,
    VERSION_AWARE_AST_RULES, VERSION_AWARE_TOKEN_RULES,
)


def _tokenize(source):
    """Tokenize raw bytes the same way on Python 2.7 and Python 3.

    tokenize.generate_tokens wants a text-mode readline on Python 3 (bytes
    fails with "readline() returned a non-string object"); it's fine on 2.7,
    where str is bytes. tokenize.tokenize is the bytes-mode generator on
    Python 3, but on 2.7 that same name is a different, callback-based
    function that returns None. So each version needs its own bytes-safe
    entry point; tokenize.tokenize's leading ENCODING token (added in
    Python 3) is dropped so both sides yield the same token sequence.
    """
    if sys.version_info[0] >= 3:
        return [t for t in tokenize.tokenize(io.BytesIO(source).readline)
                if t.type != tokenize.ENCODING]
    return list(tokenize.generate_tokens(io.BytesIO(source).readline))


def _relpath(full, root):
    return os.path.relpath(full, root).replace(os.sep, "/")


def _walk_entries(dirpath, root, files, problems):
    """Recurses into dirpath, adding every .py file found to files and
    every unreadable or non-file/non-dir entry to problems (R5: nothing
    under the scan root - directory or file - is dropped silently)."""
    try:
        names = sorted(os.listdir(dirpath))
    except OSError as e:
        problems.append((_relpath(dirpath, root), str(e)))
        return
    for name in names:
        full = os.path.join(dirpath, name)
        rel = _relpath(full, root)
        try:
            st = os.stat(full)
        except OSError as e:
            problems.append((rel, str(e)))
            continue
        if stat.S_ISDIR(st.st_mode):
            if not name.startswith("."):
                _walk_entries(full, root, files, problems)
        elif stat.S_ISREG(st.st_mode):
            if name.endswith(".py"):
                files.append(rel)
        else:
            problems.append((rel, "not a regular file or directory"))


def iter_py_files(root):
    """(files, problems): every .py file under root (sorted, relative,
    /-separated, skipping dot directories), and every entry that couldn't
    be scanned - an unreadable directory or file, or a non-file/non-dir
    entry - each as (relpath, reason). R5."""
    files = []
    problems = []
    _walk_entries(root, root, files, problems)
    files.sort()
    problems.sort()
    return files, problems


def _parse_failure_finding(rel, source, e):
    # Item 3: the scan must complete on any tree a working copy can
    # contain. A SyntaxError is the common case, but CPython's
    # compile()/ast.parse() raises other types for pathological
    # input depending on the interpreter: Python 2.7 raises TypeError
    # for embedded NUL bytes and MemoryError for a C parser stack
    # overflow on deeply nested expressions (confirmed empirically:
    # "s_push: parser stack overflow"); Python 3 raises SyntaxError
    # for both of those specific cases instead, but RuntimeError
    # covers RecursionError (added in 3.5, a RuntimeError subclass)
    # for other deep-recursion failures without needing a name that
    # does not exist on Python 2.
    #
    # An earlier version of this message named the exact running
    # interpreter (platform.python_version()) - reverted (R1/item 2b
    # correction, flagged by AutoSteer CI): R1's compile guarantee
    # never required that difference, so naming it was an unforced,
    # avoidable divergence between a 2.7 scan's JSON and a 3.x scan's
    # JSON for the same file. An embedded NUL byte gets its own fixed
    # wording for the same reason - 2.7 raises TypeError here and
    # 3.x raises SyntaxError, with genuinely different built-in
    # message text on each side (confirmed directly), so this is the
    # one case among the exception types above where the raw
    # message itself, not just a decoration this code added, would
    # otherwise differ.
    lineno = getattr(e, "lineno", None) or 1
    if b"\x00" in source:
        message = "source contains an embedded NUL byte"
    else:
        message = getattr(e, "msg", None) or str(e) or type(e).__name__
    return Finding(rel, lineno, "PY3-PARSE", "blocker",
                   "does not parse: %s" % message)


def _run_ast_rules(rel, tree, judged_versions):
    findings = []
    for rule in AST_RULES:
        findings.extend(rule(rel, tree))
    for rule in VERSION_AWARE_AST_RULES:
        findings.extend(rule(rel, tree, judged_versions))
    return findings


def _run_token_rules(rel, tokens, judged_versions):
    findings = []
    for rule in TOKEN_RULES:
        findings.extend(rule(rel, tokens))
    for rule in VERSION_AWARE_TOKEN_RULES:
        findings.extend(rule(rel, tokens, judged_versions))
    return findings


def scan_file(root, rel, judged_versions=ALL_TARGET_VERSIONS):
    """(findings, problem): problem is None, or the reason rel couldn't
    be read (R5) - in which case findings is always []. judged_versions
    (R6) is the set of Python 3 versions readiness is judged against;
    every finding ends up with a .versions subset of it - set by the
    rule itself for version-dependent rules (VERSION_AWARE_AST_RULES),
    or filled in here with the full judged_versions for every other
    rule, whose applicability doesn't vary by version.

    SOURCE_RULES and TOKEN_RULES run whenever their own input (raw bytes,
    or a token stream) is available, independent of whether ast.parse
    succeeded - found via AutoSteer CI comparing a real stdlib scan run
    under 2.7.18 against the same scan run under 3.14.9: any file with
    even one Python-2-only construct ast.parse can't handle (an
    `except X, e:`, a bare `print` statement, an old-style octal literal,
    and so on) made the running interpreter's own ast.parse raise -
    which, before this fix, discarded every other rule's findings for
    that file outright, on the interpreter where it mattered most,
    losing hundreds of real, independent findings across the stdlib
    (confirmed: 236 PY3-BUILTIN, 212 PY3-STDLIB and 337 PY3-EXCEPT-COMMA
    findings on a held-back corpus). Tokenizing is a strictly weaker
    requirement than parsing - CPython tokenizes `except X, e:` or a
    bare print statement without raising, since both are only invalid
    at the grammar level, not the lexical one - so TOKEN_RULES almost
    always still has something to work with even when ast.parse
    doesn't. AST_RULES and VERSION_AWARE_AST_RULES still need a real
    tree and stay gated on ast.parse succeeding: there is no tree to
    walk when it does not, on any interpreter."""
    try:
        with open(os.path.join(root, rel), "rb") as f:
            source = f.read()
    except (IOError, OSError) as e:
        return [], str(e)

    findings = []
    for rule in SOURCE_RULES:
        findings.extend(rule(rel, source))

    try:
        tree = ast.parse(source, rel)
    except (SyntaxError, TypeError, ValueError, MemoryError,
            RuntimeError) as e:
        findings.append(_parse_failure_finding(rel, source, e))
    else:
        findings.extend(_run_ast_rules(rel, tree, judged_versions))

    try:
        tokens = _tokenize(source)
    except (SyntaxError, TypeError, ValueError, MemoryError, RuntimeError,
            LookupError, tokenize.TokenError):
        # LookupError: Python 3.13+'s real tokenize.detect_encoding (see
        # _tokenize's own comment) does the same non-text-codec check
        # py2scan.encoding.detect_encoding does, but raises LookupError
        # instead of SyntaxError for it - confirmed directly (AutoSteer
        # CI, a rot13 coding declaration tokenized under 3.14.9).
        pass
    else:
        findings.extend(_run_token_rules(rel, tokens, judged_versions))

    for finding in findings:
        if finding.versions is None:
            finding.versions = judged_versions
    return findings, None


def scan(root, jobs=4, config=None, judged_versions=ALL_TARGET_VERSIONS):
    """(files, findings, problems): problems (R5) is every entry under
    root that couldn't be scanned, each as (relpath, reason) - from
    walking the tree (an unreadable directory, or a non-file/non-dir
    entry) or from reading a listed .py file (permission denied, etc)."""
    files, problems = iter_py_files(root)
    findings = []
    if files:
        executor = ProcessPoolExecutor(max_workers=jobs)
        try:
            worker = functools.partial(
                scan_file, root, judged_versions=judged_versions)
            for rel, (file_findings, problem) in zip(
                    files, executor.map(worker, files)):
                findings.extend(file_findings)
                if problem is not None:
                    problems.append((rel, problem))
        finally:
            executor.shutdown()
    findings.sort(key=lambda f: (f.file, f.line, f.rule, f.message))
    problems.sort()
    if config is not None:
        findings = config_module.apply(findings, config)
    return files, findings, problems
