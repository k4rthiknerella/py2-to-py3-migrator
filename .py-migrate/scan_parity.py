# -*- coding: utf-8 -*-
"""Parity of py2scan's findings on Python 2.7's standard library with the
findings of py2scan before the migration (commit bf6499e on Python 2.7.18).

  record REPORT OUT   write the record from REPORT, the output of
                      `python -m py2scan scan --format json --jobs 8 CORPUS`
                      run on 2.7.18 from a checkout of bf6499e
  check CORPUS RECORD on 2.7 or 3.x: scan CORPUS with this tree and exit 1
                      unless its findings are the record's, apart from the
                      required changes listed in CHANGES, each of which must
                      occur and name a test that exists

CORPUS is /usr/local/lib/python2.7 of the python:2.7.18-slim image. A finding
is compared by file, line, rule, severity and message.
"""
import io
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [ROOT]

from py2scan.scanner import scan  # noqa: E402

FIELDS = ("file", "line", "rule", "severity", "message")

# (change, finding, why, test): change is "added" or "removed", finding is a
# tuple of FIELDS, test is "tests/FILE.py::NAME".
CHANGES = []


def row(finding):
    return tuple(finding[k] for k in FIELDS)


def record(report_path, out_path):
    with io.open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(u"%s\n" % json.dumps({"files": report["files"], "findings": len(report["findings"])}))
        for finding in report["findings"]:
            f.write(u"%s\n" % json.dumps(row(finding), ensure_ascii=False))
    print("recorded %d findings in %d files" % (len(report["findings"]), report["files"]))
    return 0


def load(path):
    with io.open(path, encoding="utf-8") as f:
        header = json.loads(f.readline())
        return header, [tuple(json.loads(line)) for line in f]


def test_exists(test):
    path, name = test.split("::")
    with io.open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return re.search(r"^def %s\(" % re.escape(name), f.read(), re.M) is not None


def check(corpus, record_path):
    header, expected = load(record_path)
    result = scan(corpus, jobs=4)
    files = result.files
    actual = [row(f.to_dict()) for f in result.findings]
    added = sorted((Counter(actual) - Counter(expected)).elements())  # multisets: a line can repeat a finding
    removed = sorted((Counter(expected) - Counter(actual)).elements())
    problems = 0
    if len(files) != header["files"]:
        problems += 1
        print("FILES scanned %d, recorded %d" % (len(files), header["files"]))
    for change, finding, why, test in CHANGES:
        if finding not in (added if change == "added" else removed):
            problems += 1
            print("STALE %s %r (%s)" % (change, finding, why))
        if not test_exists(test):
            problems += 1
            print("NO TEST %s for %s %r" % (test, change, finding))
    listed = set((change, finding) for change, finding, _, _ in CHANGES)
    for change, rows in (("added", added), ("removed", removed)):
        for finding in rows:
            if (change, finding) not in listed:
                problems += 1
                print("UNEXPLAINED %s %s" % (change, json.dumps(finding, ensure_ascii=False)))
    print("cpython %d.%d.%d: %d files, %d findings, %d recorded; %d added, %d removed, %d required changes,"
          " %d problems" % (sys.version_info[0], sys.version_info[1], sys.version_info[2], len(files),
                            len(actual), len(expected), len(added), len(removed), len(CHANGES), problems))
    return 1 if problems else 0


def main(argv):
    if argv[:1] == ["record"] and len(argv) == 3:
        return record(*argv[1:])
    if argv[:1] == ["check"] and len(argv) == 3:
        return check(*argv[1:])
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
