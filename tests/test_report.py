# -*- coding: utf-8 -*-
from py2scan.findings import Finding
from py2scan.report import compute_summary, render_html, to_json
from py2scan.scanner import ScanResult


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
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "print x")]
    scan_result = ScanResult(["a.py"], findings, [])
    payload = to_json(scan_result, findings)
    assert payload == {
        "schema": 2,
        "files": 1,
        "readiness": 0.0,
        "rules": {"PY3-PRINT": 1},
        "findings": [{"file": "a.py", "line": 1, "rule": "PY3-PRINT",
                      "severity": "blocker", "message": "print x"}],
        "unreadable": [],
    }


def test_to_json_lists_unreadable_entries():
    scan_result = ScanResult(["a.py"], [], [("b.py", "permission denied")])
    payload = to_json(scan_result, [])
    assert payload["unreadable"] == [{"path": "b.py", "reason": "permission denied"}]


def test_render_html_is_self_contained_and_shows_source(tmp_path):
    root = str(tmp_path)
    with open(root + "/a.py", "wb") as f:
        f.write(b"print 'hello'\n")
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker",
                        "print statement; Python 3 has only the print() function")]
    html = render_html(root, ["a.py"], findings)
    assert "<html" in html
    assert "<link" not in html
    assert "<script src" not in html
    assert "a.py" in html
    assert "PY3-PRINT" in html
    assert "print &#39;hello&#39;" in html or "print &#x27;hello&#x27;" in html


def test_render_html_escapes_source_line(tmp_path):
    root = str(tmp_path)
    with open(root + "/a.py", "wb") as f:
        f.write(b"x = 1 <> 2\n")
    findings = [Finding("a.py", 1, "PY3-NE-OP", "blocker", "<> operator")]
    html = render_html(root, ["a.py"], findings)
    assert "x = 1 &lt;&gt; 2" in html
