# -*- coding: utf-8 -*-
import ast
import functools
import io
import os
import platform
import sys
import tokenize

from concurrent.futures import ProcessPoolExecutor

from py2scan import config as config_module
from py2scan.findings import Finding
from py2scan.rules import AST_RULES, TOKEN_RULES


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


def iter_py_files(root):
    """Every .py file under root, relative and /-separated, skipping dot
    directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.endswith(".py"):
                full = os.path.join(dirpath, name)
                yield os.path.relpath(full, root).replace(os.sep, "/")


def scan_file(root, rel):
    with open(os.path.join(root, rel), "rb") as f:
        source = f.read()
    try:
        tree = ast.parse(source, rel)
    except SyntaxError as e:
        return [Finding(rel, e.lineno or 1, "PY3-PARSE", "blocker",
                        "does not parse under Python %s: %s"
                        % (platform.python_version(), e.msg))]
    tokens = _tokenize(source)
    findings = []
    for rule in AST_RULES:
        findings.extend(rule(rel, tree))
    for rule in TOKEN_RULES:
        findings.extend(rule(rel, tokens))
    return findings


def scan(root, jobs=4, config=None):
    files = list(iter_py_files(root))
    findings = []
    if files:
        executor = ProcessPoolExecutor(max_workers=jobs)
        try:
            worker = functools.partial(scan_file, root)
            for file_findings in executor.map(worker, files):
                findings.extend(file_findings)
        finally:
            executor.shutdown()
    findings.sort(key=lambda f: (f.file, f.line, f.rule, f.message))
    if config is not None:
        findings = config_module.apply(findings, config)
    return files, findings
