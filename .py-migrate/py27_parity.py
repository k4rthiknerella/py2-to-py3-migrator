# -*- coding: utf-8 -*-
"""Parity of py2scan's Python 2.7 front end (py2scan/py27) with CPython 2.7
itself: the concrete syntax tree parser.suite(src).totuple(True, True) builds,
and the tree or error ast.parse(src) gives, compared in the canonical forms of
tests/py27_reference.py so a record made on 2.7 can be checked on 3.x.

  record-cases FIXTURE      on 2.7: what 2.7 computes for tests/py27_cases.py
  verify-cases FIXTURE      on 2.7: exit 1 unless the fixture is what 2.7 computes
  record RECORD ROOT        on 2.7: one line per .py file under ROOT
  check RECORD ROOT         on 2.7 or 3.x: py2scan.py27 against the record

check exits 1 when any file differs, or has changed since it was recorded.
"""
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), "tests")]

import py27_cases  # noqa: E402
from py27_reference import as_json, digest, mine, recorded, reference, same  # noqa: E402


def case_sources():
    return [c if isinstance(c, bytes) else c.encode("utf-8") for c in py27_cases.CASES + py27_cases.RAW]


def source_key(source):
    return hashlib.sha256(source).hexdigest()


def record_cases(fixture):
    results = {}
    for source in case_sources():
        cst, tree = reference(source)
        results[source_key(source)] = {"cst": digest(cst), "ast": recorded(tree)}  # CSTs are unreadable anyway
    with io.open(fixture, "w", encoding="ascii", newline="\n") as f:  # one case a line
        lines = [u"%s: %s" % (json.dumps(key), as_json(results[key])) for key in sorted(results)]
        f.write(u"{\n%s\n}\n" % u",\n".join(lines))
    print("recorded %d cases" % len(results))


def verify_cases(fixture):
    with io.open(fixture, encoding="ascii") as f:
        expected = json.load(f)
    sources = case_sources()
    differ = sorted(set(expected) ^ set(source_key(source) for source in sources))
    for source in sources:
        entry = expected.get(source_key(source))
        cst, tree = reference(source)
        if entry is not None and not (entry["cst"] == digest(cst) and same(entry["ast"], tree)):
            differ.append(source_key(source))
    for name in differ:
        print("DIFF %s" % name)
    print("%d cases, %d recorded, %d differ" % (len(sources), len(expected), len(differ)))
    return 1 if differ else 0


def python_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if name.endswith(".py"):
                path = os.path.join(dirpath, name)
                yield os.path.relpath(path, root).replace(os.sep, "/"), path


def read(path):
    with open(path, "rb") as f:
        return f.read()


def record(record_path, root):
    count = 0
    with io.open(record_path, "w", encoding="ascii", newline="\n") as out:
        for rel, path in python_files(root):
            source = read(path)
            cst, tree = reference(source)
            line = {"path": rel, "source": source_key(source), "cst": digest(cst), "ast": digest(tree)}
            out.write(u"%s\n" % as_json(line))
            count += 1
    print("recorded %d files" % count)


def check(record_path, root):
    total = same_cst = same_ast = changed = 0
    with io.open(record_path, encoding="ascii") as f:
        expected = [json.loads(line) for line in f]
    for entry in expected:
        total += 1
        source = read(os.path.join(root, entry["path"]))
        if source_key(source) != entry["source"]:
            changed += 1
            print("CHANGED %s" % entry["path"])
            continue
        cst, tree = mine(source)
        same_cst += digest(cst) == entry["cst"]
        same_ast += digest(tree) == entry["ast"]
        if digest(cst) != entry["cst"] or digest(tree) != entry["ast"]:
            print("DIFF %s cst=%s ast=%s" % (entry["path"], digest(cst) == entry["cst"], digest(tree) == entry["ast"]))
    print("%s %d.%d.%d: %d files, CST identical %d, AST identical %d, changed %d" % (
        sys.implementation.name if hasattr(sys, "implementation") else "cpython",
        sys.version_info[0], sys.version_info[1], sys.version_info[2], total, same_cst, same_ast, changed))
    return 0 if same_cst == same_ast == total else 1


def main(argv):
    if argv[:1] == ["record-cases"] and len(argv) == 2:
        record_cases(argv[1])
        return 0
    if argv[:1] == ["verify-cases"] and len(argv) == 2:
        return verify_cases(argv[1])
    if argv[:1] == ["record"] and len(argv) == 3:
        record(argv[1], argv[2])
        return 0
    if argv[:1] == ["check"] and len(argv) == 3:
        return check(argv[1], argv[2])
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
