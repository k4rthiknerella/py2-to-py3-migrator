# -*- coding: utf-8 -*-
import os

import pytest

from py2scan.config import load_config
from py2scan.findings import Finding

V = ((3, 9),)


def write_yaml(tmpdir, text):
    path = os.path.join(tmpdir, "py2scan.yml")
    with open(path, "wb") as f:
        f.write(text)
    return path


def test_no_config_passes_everything_through():
    config = load_config(None)
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "msg", V)]
    assert config.apply(findings) == findings


def test_disable_drops_findings_for_that_rule(tmp_path):
    path = write_yaml(str(tmp_path), b"disable: [PY3-PRINT]\n")
    config = load_config(path)
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "msg", V),
                Finding("a.py", 2, "PY3-EXEC-STMT", "blocker", "msg", V)]
    result = config.apply(findings)
    assert [f.rule for f in result] == ["PY3-EXEC-STMT"]


def test_severity_override_changes_severity(tmp_path):
    path = write_yaml(str(tmp_path), b"severity: {PY3-DIVISION: blocker}\n")
    config = load_config(path)
    findings = [Finding("a.py", 1, "PY3-DIVISION", "warning", "msg", V)]
    result = config.apply(findings)
    assert result[0].severity == "blocker"
    assert result[0].versions == V


def test_invalid_severity_value_raises(tmp_path):
    path = write_yaml(str(tmp_path), b"severity: {PY3-PRINT: critical}\n")
    with pytest.raises(ValueError):
        load_config(path)
