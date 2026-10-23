# -*- coding: utf-8 -*-
import ast
import os

from py2scan.findings import Finding
from py2scan.rules import AST_RULES


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
    findings = []
    for rule in AST_RULES:
        findings.extend(rule(rel, tree))
    return findings


def scan(root):
    files = list(iter_py_files(root))
    findings = []
    for rel in files:
        findings.extend(scan_file(root, rel))
    findings.sort(key=lambda f: f.key())
    return files, findings
