# -*- coding: utf-8 -*-
import ast
import functools
import io
import os
import tokenize

from concurrent.futures import ProcessPoolExecutor

from py2scan import config as config_module
from py2scan.findings import Finding
from py2scan.rules import AST_RULES, TOKEN_RULES


def iter_py_files(root):
    """Every .py file under root, relative and /-separated, skipping dot directories."""
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
                        "does not parse under Python 2.7: %s" % e.msg)]
    tokens = list(tokenize.generate_tokens(io.BytesIO(source).readline))
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
            for file_findings in executor.map(functools.partial(scan_file, root), files):
                findings.extend(file_findings)
        finally:
            executor.shutdown()
    findings.sort(key=lambda f: (f.file, f.line, f.rule, f.message))
    if config is not None:
        findings = config_module.apply(findings, config)
    return files, findings
