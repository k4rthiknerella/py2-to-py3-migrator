# -*- coding: utf-8 -*-
import os
import shutil
import tempfile

from py2scan.config import Config
from py2scan.scanner import scan


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
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "broken.py"), "wb") as f:
            f.write(b"def f(:\n")
        with open(os.path.join(root, "ok.py"), "wb") as f:
            f.write(b"print 'hi'\n")
        files, findings = scan(root, jobs=4)
    finally:
        shutil.rmtree(root)
    by_file = {}
    for f in findings:
        by_file.setdefault(f.file, []).append(f.rule)
    assert by_file["broken.py"] == ["PY3-PARSE"]
    assert by_file["ok.py"] == ["PY3-PRINT"]


def test_config_is_applied_end_to_end():
    root = make_tree()
    try:
        cfg = Config(disabled=["PY3-PRINT"], severity={})
        files, findings = scan(root, jobs=1, config=cfg)
    finally:
        shutil.rmtree(root)
    assert "PY3-PRINT" not in [f.rule for f in findings]
    assert "PY3-DIVISION" in [f.rule for f in findings]
