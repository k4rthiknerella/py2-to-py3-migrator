# -*- coding: utf-8 -*-
import ast
import functools
import io
import os
import platform
import stat
import sys
import tokenize

from concurrent.futures import ProcessPoolExecutor

from py2scan import config as config_module
from py2scan.findings import Finding
from py2scan.rules import (
    ALL_TARGET_VERSIONS, AST_RULES, TOKEN_RULES, VERSION_AWARE_AST_RULES,
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


def scan_file(root, rel, judged_versions=ALL_TARGET_VERSIONS):
    """(findings, problem): problem is None, or the reason rel couldn't
    be read (R5) - in which case findings is always []. judged_versions
    (R6) is the set of Python 3 versions readiness is judged against;
    every finding ends up with a .versions subset of it - set by the
    rule itself for version-dependent rules (VERSION_AWARE_AST_RULES),
    or filled in here with the full judged_versions for every other
    rule, whose applicability doesn't vary by version."""
    try:
        with open(os.path.join(root, rel), "rb") as f:
            source = f.read()
    except (IOError, OSError) as e:
        return [], str(e)
    try:
        tree = ast.parse(source, rel)
    except SyntaxError as e:
        findings = [Finding(rel, e.lineno or 1, "PY3-PARSE", "blocker",
                            "does not parse under Python %s: %s"
                            % (platform.python_version(), e.msg))]
    else:
        tokens = _tokenize(source)
        findings = []
        for rule in AST_RULES:
            findings.extend(rule(rel, tree))
        for rule in VERSION_AWARE_AST_RULES:
            findings.extend(rule(rel, tree, judged_versions))
        for rule in TOKEN_RULES:
            findings.extend(rule(rel, tokens))
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
