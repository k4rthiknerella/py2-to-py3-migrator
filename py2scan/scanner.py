# -*- coding: utf-8 -*-
import errno
import os
import stat
import sys
from collections import namedtuple

from concurrent.futures import ProcessPoolExecutor

from py2scan.findings import Finding
from py2scan.py27 import ast27
from py2scan.py27.parser import Py27SyntaxError, parse_cst
from py2scan.rules import BLOCKER, Module, check
from py2scan.source import coding_cookie, line_of_offset, source_lines, utf8_text
from py2scan.versions import ALL

# What a scan found under its root. files are the scanned .py files; skipped and
# errors are (path, reason) for every entry not scanned (ruling R5): an error
# makes the report incomplete, a skipped entry does not.
Scan = namedtuple("Scan", "files findings skipped errors")

_KINDS = ((stat.S_ISFIFO, "a named pipe"), (stat.S_ISSOCK, "a socket"), (stat.S_ISCHR, "a character device"),
          (stat.S_ISBLK, "a block device"))


def _reason(error):
    return error.strerror or str(error)


def _kind(mode):
    for test, kind in _KINDS:
        if test(mode):
            return kind
    return "neither a file nor a directory"


def _classify_link(path, name):
    """("file" | "skipped" | "error" | None, reason) for a symbolic link: links to
    files are followed, as the files they name; links to directories are not."""
    try:
        mode = os.stat(path).st_mode
    except EnvironmentError as e:
        if e.errno == errno.ENOENT:
            return "skipped", "dangling symbolic link"
        if e.errno == errno.ELOOP:
            return "skipped", "symbolic link loop"
        return "error", "cannot read: %s" % _reason(e)  # it may name a directory
    if stat.S_ISDIR(mode):
        return "skipped", "symbolic link to a directory, not followed"
    if not name.endswith(b".py"):
        return None, None
    if stat.S_ISREG(mode):
        return "file", None
    return "skipped", "symbolic link to %s, not a regular file" % _kind(mode)


def _classify(path, name):
    """("dir" | "file" | "skipped" | "error" | None, reason) for one directory entry;
    None for what is not Python source by definition: anything but a directory
    or a .py file."""
    try:
        mode = os.lstat(path).st_mode
    except EnvironmentError as e:
        return "error", "cannot read: %s" % _reason(e)
    if stat.S_ISDIR(mode):
        if name.startswith(b"."):
            return "skipped", "a directory whose name starts with a dot"
        return "dir", None
    if stat.S_ISLNK(mode):
        return _classify_link(path, name)
    if not name.endswith(b".py"):
        return None, None
    if stat.S_ISREG(mode):
        return "file", None
    return "skipped", "%s, not a regular file" % _kind(mode)


def walk(root):
    """(files, skipped, errors) under root (bytes): paths relative to root, /-separated, sorted."""
    found = {"file": [], "skipped": [], "error": []}
    pending = [b""]
    while pending:
        rel = pending.pop()
        directory = os.path.join(root, rel) if rel else root
        try:
            names = os.listdir(directory)
        except EnvironmentError as e:
            found["error"].append((rel or b".", "cannot read: %s" % _reason(e)))
            continue
        for name in names:
            child = rel + b"/" + name if rel else name
            kind, reason = _classify(os.path.join(directory, name), name)
            if kind == "dir":
                pending.append(child)
            elif kind == "file":
                found["file"].append(child)
            elif kind:
                found[kind].append((child, reason))
    return sorted(found["file"]), sorted(found["skipped"]), sorted(found["error"])


def display_path(path):
    return utf8_text(path) if isinstance(path, bytes) else path


def _parse_error(source, error):
    """(line, reason) for source that Python 2.7 refuses to parse."""
    if error.kind == "TypeError":  # compile() refuses NUL bytes
        return line_of_offset(source, source.index(b"\0")), "null byte in source"
    if error.kind == "MemoryError":  # how 2.7 reports "s_push: parser stack overflow"
        return 1, "too deeply nested for the parser"
    # An unknown or conflicting PEP 263 encoding is reported at line 0.
    return error.at or coding_cookie(source)[1] or 1, error.msg


def scan_source(path, source):
    """The findings for one file's source bytes, ordered by line, rule, column."""
    try:
        result = parse_cst(source)
        tree = ast27.build(result)
    except Py27SyntaxError as e:
        line, reason = _parse_error(source, e)
        found = [("PY3-PARSE", line, 0, "does not parse under Python 2.7: %s" % reason, ALL, BLOCKER)]
    else:
        found = check(Module(tree, result.cst))
    lines = source_lines(source)
    findings = [Finding(path, lineno, rule_id, severity, message, col,
                        lines[lineno - 1] if 0 < lineno <= len(lines) else None, versions)
                for rule_id, lineno, col, message, versions, severity in found]
    findings.sort(key=Finding.key)  # stable, so ties keep the order the rule found them in
    return findings


def scan_file(root, rel):
    """(findings, None), or (None, reason) when the file cannot be read or analysed."""
    try:
        with open(os.path.join(root, rel), "rb") as f:
            source = f.read()
    except EnvironmentError as e:
        return None, "cannot read: %s" % _reason(e)
    try:
        return scan_source(display_path(rel), source), None
    except Exception as e:  # a defect in py2scan; the report says so instead of a traceback
        return None, "cannot analyse: %s: %s" % (type(e).__name__, e)


def _scan_batch(root, rels):
    return [scan_file(root, rel) for rel in rels]


def _encoded(root):
    if isinstance(root, bytes):
        return root
    try:
        return root.encode(sys.getfilesystemencoding() or "utf-8")
    except UnicodeEncodeError:  # an ASCII locale; the names on disk are most likely UTF-8
        return root.encode("utf-8")


def scan(root, jobs=1):
    """A Scan of every .py file under root; findings sorted by file, line, rule.

    With jobs > 1, batches of files are parsed in worker processes: parsing is
    CPU-bound, and threads would serialize on the GIL. Results come back in
    submission order, so the output does not depend on jobs.
    """
    root = _encoded(root)
    rels, skipped, errors = walk(root)
    if jobs > 1 and len(rels) > 1:
        size = max(1, min(64, len(rels) // (jobs * 4)))
        batches = [rels[i:i + size] for i in range(0, len(rels), size)]
        with ProcessPoolExecutor(max_workers=min(jobs, len(batches))) as pool:
            results = [r for batch in pool.map(_scan_batch, [root] * len(batches), batches) for r in batch]
    else:
        results = _scan_batch(root, rels)
    files = [display_path(rel) for rel, (found, _) in zip(rels, results) if found is not None]
    findings = sorted((f for found, _ in results if found for f in found), key=Finding.key)
    errors = sorted(errors + [(rel, reason) for rel, (found, reason) in zip(rels, results) if found is None])
    return Scan(files, findings, [(display_path(p), r) for p, r in skipped],
                [(display_path(p), r) for p, r in errors])
