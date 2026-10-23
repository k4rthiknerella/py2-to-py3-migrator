# -*- coding: utf-8 -*-
import os
import shutil
import tempfile

from py2scan.encoding import read_lines
from py2scan.findings import Finding
from py2scan.report import render_html, summarize


def test_no_files_is_fully_ready():
    summary = summarize([], [])
    assert summary["files"] == 0
    assert summary["readiness"] == 100.0
    assert summary["rules"] == {}
    assert summary["findings"] == []


def test_clean_files_are_fully_ready():
    summary = summarize(["a.py", "b.py"], [])
    assert summary["readiness"] == 100.0


def test_readiness_counts_files_without_a_blocker():
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "x")]
    summary = summarize(["a.py", "b.py"], findings)
    assert summary["readiness"] == 50.0


def test_a_warning_does_not_affect_readiness():
    findings = [Finding("a.py", 1, "PY3-DIVISION", "warning", "x")]
    summary = summarize(["a.py", "b.py"], findings)
    assert summary["readiness"] == 100.0


def test_rules_counts_only_include_rules_with_findings():
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "x"),
                Finding("a.py", 2, "PY3-PRINT", "blocker", "y")]
    summary = summarize(["a.py"], findings)
    assert summary["rules"] == {"PY3-PRINT": 2}


def test_findings_are_plain_dicts():
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "x")]
    summary = summarize(["a.py"], findings)
    assert summary["findings"] == [findings[0].to_dict()]


def test_findings_tie_broken_by_message_when_file_line_rule_match():
    findings = [Finding("a.py", 1, "PY3-STDLIB", "blocker", "import of ConfigParser"),
                Finding("a.py", 1, "PY3-STDLIB", "blocker", "import of urllib2")]
    summary = summarize(["a.py"], findings)
    messages = [f["message"] for f in summary["findings"]]
    assert messages == ["import of ConfigParser", "import of urllib2"]


def test_read_lines_decodes_pep263_cookie():
    root = tempfile.mkdtemp()
    try:
        path = os.path.join(root, "latin1.py")
        with open(path, "wb") as f:
            f.write(b"# -*- coding: latin-1 -*-\nx = '\xe9'\n")
        lines = read_lines(path)
    finally:
        shutil.rmtree(root)
    assert lines[1] == u"x = '\xe9'"


def test_read_lines_defaults_to_utf8_without_a_cookie():
    root = tempfile.mkdtemp()
    try:
        path = os.path.join(root, "plain.py")
        with open(path, "wb") as f:
            f.write(u"x = 'é'\n".encode("utf-8"))
        lines = read_lines(path)
    finally:
        shutil.rmtree(root)
    assert lines[0] == u"x = 'é'"


def test_render_html_contains_readiness_rule_counts_and_escaped_source():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "a.py"), "wb") as f:
            f.write(b"print 'hi' if 1 < 2 else None\n")
        files = ["a.py"]
        findings = [Finding("a.py", 1, "PY3-PRINT", "blocker",
                            "print statement; Python 3 has only the print() function")]
        summary = summarize(files, findings)
        html = render_html(root, findings, summary)
    finally:
        shutil.rmtree(root)
    assert "50.0" not in html
    assert "0.0" in html
    assert "PY3-PRINT" in html
    assert "1" in html
    assert "1 &lt; 2" in html
    assert "1 < 2" not in html
