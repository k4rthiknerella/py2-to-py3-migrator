# -*- coding: utf-8 -*-
import ast
import io
import os
import tokenize
from concurrent.futures import ProcessPoolExecutor

from py2scan.findings import Finding
from py2scan.rules import RULES


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
    for rule in RULES:
        findings.extend(rule(rel, tree, tokens))
    return findings


def scan(root, jobs=4):
    files = list(iter_py_files(root))
    if jobs <= 1 or len(files) <= 1:
        results = [scan_file(root, rel) for rel in files]
    else:
        executor = ProcessPoolExecutor(max_workers=jobs)
        try:
            results = list(executor.map(scan_file, [root] * len(files), files))
        finally:
            executor.shutdown()
    findings = []
    for r in results:
        findings.extend(r)
    findings.sort(key=lambda f: f.key())
    return files, findings
