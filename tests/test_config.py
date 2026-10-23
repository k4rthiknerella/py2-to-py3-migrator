# -*- coding: utf-8 -*-
import os
import tempfile

from py2scan.config import apply, load_config
from py2scan.findings import Finding


def write_config(text):
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    with open(path, "wb") as f:
        f.write(text)
    return path


def test_disable_drops_matching_findings():
    path = write_config(b"disable: [PY3-PRINT]\n")
    try:
        cfg = load_config(path)
    finally:
        os.remove(path)
    findings = [Finding("m.py", 1, "PY3-PRINT", "blocker", "x"),
                Finding("m.py", 2, "PY3-EXEC-STMT", "blocker", "y")]
    result = apply(findings, cfg)
    assert [f.rule for f in result] == ["PY3-EXEC-STMT"]


def test_severity_override_changes_matching_findings():
    path = write_config(b"severity: {PY3-DIVISION: blocker}\n")
    try:
        cfg = load_config(path)
    finally:
        os.remove(path)
    original = [Finding("m.py", 1, "PY3-DIVISION", "warning", "x")]
    result = apply(original, cfg)
    assert result[0].severity == "blocker"
    assert original[0].severity == "warning"


def test_no_config_is_identity():
    findings = [Finding("m.py", 1, "PY3-PRINT", "blocker", "x")]
    result = apply(findings, None)
    assert result == findings


def test_missing_keys_default_to_no_op():
    path = write_config(b"disable: [PY3-PRINT]\n")
    try:
        cfg = load_config(path)
    finally:
        os.remove(path)
    findings = [Finding("m.py", 1, "PY3-EXEC-STMT", "blocker", "x")]
    assert [f.rule for f in apply(findings, cfg)] == ["PY3-EXEC-STMT"]
