# -*- coding: utf-8 -*-
import ast
import os
import parser
import sys

from concurrent.futures import ProcessPoolExecutor

from py2scan.findings import Finding
from py2scan.rules import RULES, Module, check
from py2scan.source import coding_cookie, line_of_offset, source_lines


class ScanError(Exception):
    """A file under the scanned path could not be read."""


def iter_py_files(root):
    """Every .py file under root, relative and /-separated, skipping dot directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if name.endswith(".py") and os.path.isfile(full):  # not a broken symlink
                yield os.path.relpath(full, root).replace(os.sep, "/")


def display_path(path):
    return path.decode("utf-8", "replace") if isinstance(path, bytes) else path


def _parse_error(source, error):
    """(line, reason) for source that Python 2.7 refuses to parse."""
    if isinstance(error, TypeError) and b"\0" in source:  # compile() refuses NUL bytes
        return line_of_offset(source, source.index(b"\0")), "null byte in source"
    if isinstance(error, MemoryError):  # how 2.7 reports "s_push: parser stack overflow"
        return 1, "too deeply nested for the parser"
    if isinstance(error, SyntaxError):
        # An unknown or conflicting PEP 263 encoding is reported at line 0.
        return error.lineno or coding_cookie(source)[1] or 1, error.msg or str(error)
    return 1, str(error)


def scan_source(path, source):
    """The findings for one file's source bytes, ordered by line, rule, column."""
    try:
        tree = ast.parse(source)
        cst = parser.suite(source).totuple(True, True)
    except (SyntaxError, TypeError, MemoryError) as e:
        line, reason = _parse_error(source, e)
        found = [("PY3-PARSE", line, 0, "does not parse under Python 2.7: %s" % reason)]
    else:
        found = check(Module(tree, cst))
    lines = source_lines(source)
    findings = [Finding(path, lineno, rule_id, RULES[rule_id].severity, message, col,
                        lines[lineno - 1] if 0 < lineno <= len(lines) else None)
                for rule_id, lineno, col, message in found]
    findings.sort(key=Finding.key)  # stable, so ties keep the order the rule found them in
    return findings


def scan_file(root, rel):
    try:
        with open(os.path.join(root, rel), "rb") as f:
            source = f.read()
    except EnvironmentError as e:
        raise ScanError("cannot read %s: %s" % (display_path(rel), e.strerror or e))
    return scan_source(display_path(rel), source)


def _scan_batch(root, rels):
    return [scan_file(root, rel) for rel in rels]


def scan(root, jobs=1):
    """(paths of the scanned files, their findings sorted by file, line, rule).

    With jobs > 1, batches of files are parsed in worker processes: parsing is
    CPU-bound, and threads would serialize on the GIL. Results come back in
    submission order, so the output does not depend on jobs.
    """
    if not isinstance(root, bytes):
        try:
            root = root.encode(sys.getfilesystemencoding() or "utf-8")
        except UnicodeEncodeError:  # an ASCII locale; the names on disk are most likely UTF-8
            root = root.encode("utf-8")
    rels = list(iter_py_files(root))
    if jobs > 1 and len(rels) > 1:
        size = max(1, min(64, len(rels) // (jobs * 4)))
        batches = [rels[i:i + size] for i in range(0, len(rels), size)]
        with ProcessPoolExecutor(max_workers=min(jobs, len(batches))) as pool:
            results = [r for batch in pool.map(_scan_batch, [root] * len(batches), batches) for r in batch]
    else:
        results = _scan_batch(root, rels)
    findings = sorted((f for result in results for f in result), key=Finding.key)
    return [display_path(rel) for rel in rels], findings
