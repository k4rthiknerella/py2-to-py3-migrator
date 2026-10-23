# -*- coding: utf-8 -*-
"""py2scan's verdict on what each Python 3 version can compile (ruling R1),
checked against what the real interpreters did with every case in
tests/py3_cases.py: tests/data/py3_verdicts.json, recorded by
.py-migrate/py3_verdicts.sh with 3.6.15 to 3.15.1 and 2.7.18's ast.parse.

Two properties, for every case and every judged version:
- sound: where the interpreter cannot compile the case, py2scan reports a
  blocker for that version, so the file is never ready for it;
- exact: the versions py2scan says cannot compile the case (the syntax
  versions of its findings) are the versions that could not.
"""
import io
import json
import os

import pytest

from py2scan.scanner import scan_source
from py2scan.versions import VERSIONS, label
from tests.py3_cases import ALL_CASES

with io.open(os.path.join(os.path.dirname(__file__), "data", "py3_verdicts.json"), encoding="ascii") as _f:
    RECORD = json.load(_f)

LABELS = [label(v) for v in VERSIONS]

# Where py2scan's verdict and the interpreters' still differ: each line names a
# test and case whose input is in tests/py3_cases.py. Under ruling R1 each is a
# defect to fix, not an accepted divergence; strict, so a fix must delete it.
with io.open(os.path.join(os.path.dirname(__file__), "data", "py3_defects.txt"), encoding="ascii") as _f:
    DEFECTS = set(line.strip() for line in _f if line.strip())


def cases(test):
    return [pytest.param(name, source, id=name, marks=[pytest.mark.xfail(strict=True, reason="R1 defect")]
                         if "%s[%s]" % (test, name) in DEFECTS else [])
            for name, source in ALL_CASES]


def failing(name):
    return set(v for v in LABELS if RECORD["cases"][name][v] != "ok")


def labels(versions):
    return set(label(v) for v in versions)


def test_the_record_covers_every_case_and_every_judged_version():
    assert set(RECORD["cases"]) == set(name for name, _ in ALL_CASES)
    assert [p.rsplit(".", 1)[0] for p in RECORD["pythons"]] == ["2.7"] + LABELS
    assert all(set(verdicts) == set(["2.7"] + LABELS) for verdicts in RECORD["cases"].values())


@pytest.mark.parametrize("name, source", cases("test_blocked_on_every_version_that_cannot_compile_it"))
def test_blocked_on_every_version_that_cannot_compile_it(name, source):
    findings = scan_source(u"t.py", source)
    blocked = set()
    for f in findings:
        if f.severity == "blocker":
            blocked |= labels(f.versions)
    assert failing(name) <= blocked


@pytest.mark.parametrize("name, source", cases("test_compile_failures_are_predicted_exactly"))
def test_compile_failures_are_predicted_exactly(name, source):
    findings = scan_source(u"t.py", source)
    if RECORD["cases"][name]["2.7"] != "ok":
        assert [f.rule for f in findings] == ["PY3-PARSE"]
        return
    predicted = set()
    for f in findings:
        predicted |= labels(f.syntax)
    assert (sorted(predicted), [(f.line, f.rule, f.message) for f in findings if f.syntax]) == \
        (sorted(failing(name)), [(f.line, f.rule, f.message) for f in findings if f.syntax])
