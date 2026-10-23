# -*- coding: utf-8 -*-
import os
import shutil
import sys
import tempfile

from py2scan.config import Config
from py2scan.scanner import scan, scan_file


def make_tree():
    root = tempfile.mkdtemp()
    os.mkdir(os.path.join(root, "pkg"))
    with open(os.path.join(root, "pkg", "a.py"), "wb") as f:
        f.write(b"print 'a'\n")
    with open(os.path.join(root, "b.py"), "wb") as f:
        f.write(b"print 'b'\nx = 1 / 2\n")
    with open(os.path.join(root, "c.py"), "wb") as f:
        f.write(b"x = 1\n")
    return root


def as_dicts(findings):
    return [f.to_dict() for f in findings]


def test_print_statement_is_a_blocker_on_whichever_interpreter_is_running():
    # R1: Python-2-only syntax can't ast.parse on Python 3, so check_print
    # never runs there - scan_file reports PY3-PARSE instead of PY3-PRINT.
    # The never-blocker-free guarantee holds either way (this test), but the
    # resulting rule/message text is NOT byte-identical JSON across
    # interpreters for this input - R1 says the guarantee wins the conflict,
    # not that the non-identical JSON is an accepted divergence; it is an
    # open, recorded defect against item 2b (see MIGRATION.md's Blockers).
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(b"print 'hi'\n")
        findings = scan_file(root, "m.py")
    finally:
        shutil.rmtree(root)
    assert len(findings) == 1
    assert findings[0].severity == "blocker"
    expected_rule = "PY3-PARSE" if sys.version_info[0] >= 3 else "PY3-PRINT"
    assert findings[0].rule == expected_rule


def test_jobs_does_not_affect_output():
    root = make_tree()
    try:
        files1, findings1 = scan(root, jobs=1)
        files4, findings4 = scan(root, jobs=4)
    finally:
        shutil.rmtree(root)
    assert files1 == files4
    assert as_dicts(findings1) == as_dicts(findings4)


def test_a_broken_file_does_not_affect_scanning_of_others():
    # ok.py uses unicode(), not a print statement: print is Python-2-only
    # syntax, so ast.parse itself would fail on Python 3 and this file would
    # report PY3-PARSE like broken.py does, rather than exercising the thing
    # this test is actually about (one bad file not poisoning the others).
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "broken.py"), "wb") as f:
            f.write(b"def f(:\n")
        with open(os.path.join(root, "ok.py"), "wb") as f:
            f.write(b"x = unicode('hi')\n")
        files, findings = scan(root, jobs=4)
    finally:
        shutil.rmtree(root)
    by_file = {}
    for f in findings:
        by_file.setdefault(f.file, []).append(f.rule)
    assert by_file["broken.py"] == ["PY3-PARSE"]
    assert by_file["ok.py"] == ["PY3-BUILTIN"]


def test_config_is_applied_end_to_end():
    # Deliberately not make_tree(): its fixtures use print statements, which
    # are Python-2-only syntax and report PY3-PARSE (not PY3-PRINT) once
    # ast.parse itself can't succeed, on Python 3. unicode()/division are
    # ordinary expressions that parse (and so are detectable) on both.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "a.py"), "wb") as fh:
            fh.write(b"x = unicode('hi')\n")
        with open(os.path.join(root, "b.py"), "wb") as fh:
            fh.write(b"y = 1 / 2\n")
        cfg = Config(disabled=["PY3-BUILTIN"], severity={})
        files, findings = scan(root, jobs=1, config=cfg)
    finally:
        shutil.rmtree(root)
    assert "PY3-BUILTIN" not in [f.rule for f in findings]
    assert "PY3-DIVISION" in [f.rule for f in findings]
