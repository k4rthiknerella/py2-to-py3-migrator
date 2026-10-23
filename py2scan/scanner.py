# -*- coding: utf-8 -*-
import errno
import os
import stat
from concurrent.futures import ProcessPoolExecutor

from py2scan.findings import Finding
from py2scan.parsing import parse_source
from py2scan.rules import RULES


class ScanResult(object):
    """files: relative, /-separated paths scanned. findings: sorted list of
    Finding. unreadable: sorted list of (relpath, reason) for anything under
    the root that could hold Python source but could not be read, or that
    was skipped because it is neither a regular file nor a directory."""

    def __init__(self, files, findings, unreadable):
        self.files = files
        self.findings = findings
        self.unreadable = unreadable

    @property
    def incomplete(self):
        return bool(self.unreadable)


def _relpath(full, root):
    return os.path.relpath(full, root).replace(os.sep, "/")


def _undiscoverable_dir_reason(full):
    """None if full should be descended into, else why it cannot be."""
    try:
        st = os.lstat(full)
    except OSError as e:
        return "cannot stat: %s" % (e.strerror or e)
    if stat.S_ISLNK(st.st_mode):
        return "symlink to a directory, not followed"
    return None


def _unreadable_file_reason(full):
    """None if full should be scanned, else why it cannot be."""
    try:
        st = os.stat(full)  # follows a file symlink to its target
    except OSError as e:
        if e.errno == errno.ENOENT:
            return "dangling symlink"
        return "cannot stat: %s" % (e.strerror or e)
    if not stat.S_ISREG(st.st_mode):
        return "not a regular file"
    if not os.access(full, os.R_OK):
        return "permission denied"
    return None


def discover(root):
    """Walk root, returning (py_files, unreadable) where py_files is a
    sorted list of relative .py paths to scan and unreadable is a sorted
    list of (relpath, reason) covering every entry that could hold Python
    source but could not be read or scanned. Never follows directory
    symlinks (so symlink loops cannot occur); each one is listed instead of
    silently skipped. Nothing under the root is dropped without a reason."""
    py_files = []
    unreadable = []

    def onerror(os_error):
        rel = _relpath(os_error.filename, root) if os_error.filename else "."
        unreadable.append((rel, "cannot list directory: %s" % (os_error.strerror or os_error)))

    for dirpath, dirnames, filenames in os.walk(root, onerror=onerror, followlinks=False):
        kept = []
        for name in sorted(dirnames):
            if name.startswith("."):
                continue
            full = os.path.join(dirpath, name)
            reason = _undiscoverable_dir_reason(full)
            if reason is None:
                kept.append(name)
            else:
                unreadable.append((_relpath(full, root), reason))
        dirnames[:] = kept

        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            reason = _unreadable_file_reason(full)
            if reason is None:
                py_files.append(_relpath(full, root))
            else:
                unreadable.append((_relpath(full, root), reason))

    py_files.sort()
    unreadable.sort()
    return py_files, unreadable


def iter_py_files(root):
    """Kept for compatibility with callers that only want the file list."""
    files, _ = discover(root)
    return iter(files)


def scan_file(root, rel):
    full = os.path.join(root, rel)
    try:
        with open(full, "rb") as f:
            source = f.read()
    except (IOError, OSError) as e:
        return [], (rel, "cannot read: %s" % (e.strerror or e))

    tree, tokens, failure, compiles = parse_source(full, source)
    if failure is not None:
        return [Finding(rel, failure.line, "PY3-PARSE", "blocker", failure.message)], None

    findings = []
    for rule in RULES:
        findings.extend(rule(rel, tree, tokens))

    if not compiles and not any(f.severity == "blocker" for f in findings):
        findings.append(Finding(
            rel, 1, "PY3-PARSE", "blocker",
            "parses as Python 2.7 but this interpreter cannot compile it, "
            "and no other rule flagged why"))

    return findings, None


def scan(root, jobs=4):
    files, unreadable = discover(root)
    if jobs <= 1 or len(files) <= 1:
        results = [scan_file(root, rel) for rel in files]
    else:
        executor = ProcessPoolExecutor(max_workers=jobs)
        try:
            results = list(executor.map(scan_file, [root] * len(files), files))
        finally:
            executor.shutdown()

    findings = []
    for file_findings, read_error in results:
        findings.extend(file_findings)
        if read_error is not None:
            unreadable.append(read_error)
    findings.sort(key=lambda f: f.key())
    unreadable.sort()
    return ScanResult(files, findings, unreadable)
