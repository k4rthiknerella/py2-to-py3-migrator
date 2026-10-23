# -*- coding: utf-8 -*-
import os
import shutil
import sys
import tempfile

import pytest

from py2scan.scanner import _run_extra_backstop, scan

V2 = ((3, 6), (3, 13), (3, 14))


def make_tree(n):
    root = tempfile.mkdtemp()
    for i in range(n):
        with open(os.path.join(root, "m%02d.py" % i), "wb") as f:
            if i % 2 == 0:
                f.write(b"print 'x'\n")
            else:
                f.write(b"x = 1\n")
    return root


def test_output_identical_across_job_counts():
    root = make_tree(12)
    try:
        baseline = scan(root, jobs=1)
        for jobs in (1, 2, 4, 8):
            result = scan(root, jobs=jobs)
            assert result.files == baseline.files
            got = [f.to_dict() for f in result.findings]
            want = [f.to_dict() for f in baseline.findings]
            assert got == want
            assert result.unreadable == baseline.unreadable
    finally:
        shutil.rmtree(root)


def test_versioned_stdlib_removal_scoped_to_judged_versions():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as fh:
            fh.write(b"import telnetlib\n")  # removed in 3.13, not in 3.6
        result = scan(root, jobs=1, versions=V2)
        stdlib = [f for f in result.findings if f.rule == "PY3-STDLIB"]
        assert len(stdlib) == 1
        assert stdlib[0].versions == ((3, 13), (3, 14))
    finally:
        shutil.rmtree(root)


def test_run_extra_backstop_detects_a_real_compile_failure(tmp_path):
    if sys.version_info[0] < 3:
        pytest.skip("the extra-interpreter driver needs a Python 3 interpreter")
    bad = str(tmp_path / "bad.py")
    with open(bad, "wb") as f:
        f.write(b"def f(:\n    pass\n")
    good = str(tmp_path / "good.py")
    with open(good, "wb") as f:
        f.write(b"x = 1\n")
    failed = _run_extra_backstop(sys.executable, [bad, good])
    assert failed == set([bad])


def test_missing_extra_interpreter_path_is_harmless():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(b"x = 1\n")
        result = scan(root, jobs=1, versions=V2,
                      extra_interpreters={(3, 13): "/no/such/interpreter-xyz"})
        assert result.findings == []
    finally:
        shutil.rmtree(root)
