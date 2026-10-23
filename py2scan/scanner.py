# -*- coding: utf-8 -*-
import errno
import functools
import os
import stat
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

from py2scan.findings import Finding
from py2scan.parsing import parse_source
from py2scan.rules import RULES
from py2scan.versions import SUPPORTED_VERSIONS


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


def scan_file(root, rel, versions=SUPPORTED_VERSIONS):
    full = os.path.join(root, rel)
    try:
        with open(full, "rb") as f:
            source = f.read()
    except (IOError, OSError) as e:
        return [], (rel, "cannot read: %s" % (e.strerror or e))

    tree, tokens, failure, compiles = parse_source(full, source)
    if failure is not None:
        return [Finding(rel, failure.line, "PY3-PARSE", "blocker", failure.message,
                        versions)], None

    findings = []
    for rule in RULES:
        findings.extend(rule(rel, tree, tokens, versions))

    # R1/R9: the live compile() backstop only ever ADDS a blocker, never
    # removes one a static rule already found, and it only speaks for the
    # one version it was actually run under - py2scan's own runtime here,
    # whichever of the judged versions (if any) that happens to be.
    own_version = sys.version_info[:2]
    if (not compiles and own_version in versions
            and not any(f.severity == "blocker" and own_version in f.versions for f in findings)):
        findings.append(Finding(
            rel, 1, "PY3-PARSE", "blocker",
            "parses as Python 2.7 but %d.%d cannot compile it, and no other rule flagged why"
            % own_version, (own_version,)))

    return findings, None


_EXTRA_BACKSTOP_DRIVER = (
    "import sys\n"
    "for raw in sys.stdin.buffer.read().split(b'\\0'):\n"
    "    if not raw:\n"
    "        continue\n"
    "    path = raw.decode('utf-8', 'surrogateescape')\n"
    "    try:\n"
    "        with open(path, 'rb') as f:\n"
    "            src = f.read()\n"
    "        compile(src, path, 'exec')\n"
    "    except Exception:\n"
    "        sys.stdout.write(path + '\\n')\n"
)


def _run_extra_backstop(interpreter_path, full_paths):
    """The subset of full_paths that interpreter_path cannot compile.
    Never raises: a broken or missing interpreter just means this extra
    check contributes nothing (R9: a missing one must not weaken any
    verdict) rather than failing the scan."""
    payload = b"\0".join(p.encode("utf-8") for p in full_paths)
    try:
        proc = subprocess.Popen(
            [interpreter_path, "-c", _EXTRA_BACKSTOP_DRIVER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = proc.communicate(payload)
    except OSError:
        return frozenset()
    failed = set()
    for line in out.splitlines():
        try:
            failed.add(line.decode("utf-8"))
        except UnicodeDecodeError:
            continue
    return failed


def _apply_extra_interpreters(root, files, findings, versions, extra_interpreters):
    """R9: an operator may point py2scan at other locally-installed
    interpreters for judged versions it is not itself running on. Strictly
    additive, same monotonic rule as the own-runtime backstop above - a
    missing or unusable path here just means no extra check ran."""
    if not extra_interpreters:
        return findings
    already_blocked = set()
    for f in findings:
        if f.severity == "blocker":
            for v in f.versions:
                already_blocked.add((f.file, v))

    extra_findings = []
    for version in sorted(extra_interpreters):
        if version not in versions:
            continue
        interp_path = extra_interpreters[version]
        candidates = [rel for rel in files if (rel, version) not in already_blocked]
        if not candidates:
            continue
        full_paths = [os.path.join(root, rel) for rel in candidates]
        failed = _run_extra_backstop(interp_path, full_paths)
        for rel, full in zip(candidates, full_paths):
            if full in failed:
                extra_findings.append(Finding(
                    rel, 1, "PY3-PARSE", "blocker",
                    "parses as Python 2.7 but %d.%d (via %s) cannot compile it, "
                    "and no other rule flagged why" % (version[0], version[1], interp_path),
                    (version,)))
    return findings + extra_findings


def scan(root, jobs=4, versions=SUPPORTED_VERSIONS, extra_interpreters=None):
    files, unreadable = discover(root)
    worker = functools.partial(scan_file, versions=versions)
    if jobs <= 1 or len(files) <= 1:
        results = [worker(root, rel) for rel in files]
    else:
        executor = ProcessPoolExecutor(max_workers=jobs)
        try:
            results = list(executor.map(worker, [root] * len(files), files))
        finally:
            executor.shutdown()

    findings = []
    for file_findings, read_error in results:
        findings.extend(file_findings)
        if read_error is not None:
            unreadable.append(read_error)

    findings = _apply_extra_interpreters(root, files, findings, versions, extra_interpreters)
    findings.sort(key=lambda f: f.key())
    unreadable.sort()
    return ScanResult(files, findings, unreadable)
