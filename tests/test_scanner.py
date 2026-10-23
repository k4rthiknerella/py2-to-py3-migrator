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


def _find_on_path(name):
    # shutil.which() is Python 3.3+ only; this straddles 2.7 too.
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _discover_python3():
    # Under a Python 3 test run, sys.executable already IS that interpreter.
    # Under a Python 2.7 test run, fall back to whatever python3 the host
    # provides (the T12-fixed Dockerfile.test installs one alongside 2.7),
    # so this test drives the real cross-version subprocess path on both
    # sides of the straddle instead of skipping under 2.7.
    if sys.version_info[0] >= 3:
        return sys.executable
    return _find_on_path("python3")


def test_run_extra_backstop_detects_a_real_compile_failure(tmp_path):
    python3 = _discover_python3()
    if python3 is None:
        pytest.skip("no python3 interpreter available to drive the backstop")
    bad = str(tmp_path / "bad.py")
    with open(bad, "wb") as f:
        f.write(b"def f(:\n    pass\n")
    good = str(tmp_path / "good.py")
    with open(good, "wb") as f:
        f.write(b"x = 1\n")
    failed = _run_extra_backstop(python3, [bad, good])
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


def test_unreadable_file_is_reported_not_dropped():
    if os.getuid() == 0:
        pytest.skip("root bypasses the permission bits this test relies on")
    root = tempfile.mkdtemp()
    good = os.path.join(root, "good.py")
    bad = os.path.join(root, "bad.py")
    try:
        with open(good, "wb") as f:
            f.write(b"x = 1\n")
        with open(bad, "wb") as f:
            f.write(b"y = 2\n")
        os.chmod(bad, 0o000)
        result = scan(root, jobs=1)
        assert result.incomplete
        assert result.unreadable == [("bad.py", "permission denied")]
        assert result.files == ["good.py"]
    finally:
        os.chmod(bad, 0o644)
        shutil.rmtree(root)


def test_non_utf8_filename_does_not_crash_the_scan():
    # Real repro: a file literally named with a raw non-UTF-8 byte
    # (independent check's hostile/non_utf8_name case). Scanning it must
    # never raise - only json.dumps()/display_path() at the output
    # boundary need to know about this; discover()/scan_file() work with
    # the exact original bytes throughout, matching the real filesystem.
    root = tempfile.mkdtemp()
    # Python 2's open() takes the raw bytes directly (str is bytes there);
    # Python 3's os layer reconstructs the same raw byte from a lone
    # surrogate codepoint via surrogateescape when the OS call is made.
    bad_name = b"caf\xe9.py" if sys.version_info[0] < 3 else u"caf\udce9.py"
    try:
        with open(os.path.join(root, "ok.py"), "wb") as f:
            f.write(b"x = 1\n")
        try:
            with open(os.path.join(root, bad_name), "wb") as f:
                f.write(b"print x\n")
        except (OSError, ValueError, UnicodeDecodeError):
            pytest.skip("this filesystem rejects non-UTF-8 filenames")
        result = scan(root, jobs=1)
        assert len(result.files) == 2
        assert len(result.findings) == 1
        assert result.findings[0].rule == "PY3-PRINT"
    finally:
        shutil.rmtree(root)
