# -*- coding: utf-8 -*-
from py2scan.findings import Finding
from py2scan.report import compute_summary, render_html, to_json
from py2scan.scanner import ScanResult

V2 = ((3, 9), (3, 10))


def test_readiness_is_100_when_no_files():
    file_readiness, readiness, rules = compute_summary([], [], V2)
    assert file_readiness == {}
    assert readiness == {"3.9": 100.0, "3.10": 100.0}
    assert rules == {}


def test_readiness_counts_files_without_blockers():
    files = ["a.py", "b.py"]
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "msg", V2)]
    file_readiness, readiness, rules = compute_summary(files, findings, V2)
    assert readiness == {"3.9": 50.0, "3.10": 50.0}
    assert file_readiness == {"a.py": [], "b.py": ["3.9", "3.10"]}
    assert rules == {"PY3-PRINT": 1}


def test_warning_only_file_counts_as_ready():
    files = ["a.py"]
    findings = [Finding("a.py", 1, "PY3-DIVISION", "warning", "msg", V2)]
    _, readiness, _ = compute_summary(files, findings, V2)
    assert readiness == {"3.9": 100.0, "3.10": 100.0}


def test_blocker_scoped_to_one_version_only_blocks_that_version():
    files = ["a.py"]
    findings = [Finding("a.py", 1, "PY3-ASYNC-RESERVED", "blocker", "msg", ((3, 10),))]
    file_readiness, readiness, _ = compute_summary(files, findings, V2)
    assert file_readiness == {"a.py": ["3.9"]}
    assert readiness == {"3.9": 100.0, "3.10": 0.0}


def test_rules_with_zero_findings_are_excluded():
    files = ["a.py"]
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "msg", V2)]
    _, _, rules = compute_summary(files, findings, V2)
    assert "PY3-EXEC-STMT" not in rules


def test_to_json_shape():
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "print x", V2)]
    scan_result = ScanResult(["a.py"], findings, [])
    payload = to_json(scan_result, findings, V2)
    assert payload == {
        "schema": 3,
        "versions_judged": ["3.9", "3.10"],
        "files": 1,
        "readiness": {"3.9": 0.0, "3.10": 0.0},
        "file_readiness": {"a.py": []},
        "rules": {"PY3-PRINT": 1},
        "findings": [{"file": "a.py", "line": 1, "rule": "PY3-PRINT",
                      "severity": "blocker", "message": "print x",
                      "versions": ["3.9", "3.10"]}],
        "unreadable": [],
    }


def test_to_json_lists_unreadable_entries():
    scan_result = ScanResult(["a.py"], [], [("b.py", "permission denied")])
    payload = to_json(scan_result, [], V2)
    assert payload["unreadable"] == [{"path": "b.py", "reason": "permission denied"}]


def test_render_html_is_self_contained_and_shows_source(tmp_path):
    root = str(tmp_path)
    with open(root + "/a.py", "wb") as f:
        f.write(b"print 'hello'\n")
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker",
                        "print statement; Python 3 has only the print() function", V2)]
    html = render_html(root, ["a.py"], findings, V2)
    assert "<html" in html
    assert "<link" not in html
    assert "<script src" not in html
    assert "a.py" in html
    assert "PY3-PRINT" in html
    assert "3.9, 3.10" in html
    assert "print &#39;hello&#39;" in html or "print &#x27;hello&#x27;" in html


def test_render_html_escapes_source_line(tmp_path):
    root = str(tmp_path)
    with open(root + "/a.py", "wb") as f:
        f.write(b"x = 1 <> 2\n")
    findings = [Finding("a.py", 1, "PY3-NE-OP", "blocker", "<> operator", V2)]
    html = render_html(root, ["a.py"], findings, V2)
    assert "x = 1 &lt;&gt; 2" in html
