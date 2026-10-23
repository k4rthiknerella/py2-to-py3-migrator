# -*- coding: utf-8 -*-
from py2scan.findings import Finding
from py2scan.report import compute_summary, to_json


def test_readiness_is_100_when_no_files():
    readiness, rules = compute_summary([], [])
    assert readiness == 100.0
    assert rules == {}


def test_readiness_counts_files_without_blockers():
    files = ["a.py", "b.py"]
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "msg")]
    readiness, rules = compute_summary(files, findings)
    assert readiness == 50.0
    assert rules == {"PY3-PRINT": 1}


def test_warning_only_file_counts_as_ready():
    files = ["a.py"]
    findings = [Finding("a.py", 1, "PY3-DIVISION", "warning", "msg")]
    readiness, rules = compute_summary(files, findings)
    assert readiness == 100.0


def test_rules_with_zero_findings_are_excluded():
    files = ["a.py"]
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "msg")]
    _, rules = compute_summary(files, findings)
    assert "PY3-EXEC-STMT" not in rules


def test_to_json_shape():
    files = ["a.py"]
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "print x")]
    result = to_json(files, findings)
    assert result == {
        "files": 1,
        "readiness": 0.0,
        "rules": {"PY3-PRINT": 1},
        "findings": [{"file": "a.py", "line": 1, "rule": "PY3-PRINT",
                      "severity": "blocker", "message": "print x"}],
    }
