# -*- coding: utf-8 -*-
import os
import shutil
import tempfile

from py2scan.encoding import read_lines
from py2scan.findings import Finding
from py2scan.report import render_html, summarize


def test_summary_carries_a_schema_version():
    # Spec item 3: the JSON output carries a schema version, so a
    # consumer can tell readiness-as-dict (R6) apart from any future
    # breaking shape change without guessing from the keys present.
    summary = summarize([], [])
    assert summary["schema_version"] == 1


def test_no_files_is_fully_ready():
    # R6: readiness is per judged Python 3 version, not one scalar - a
    # file can be ready for 3.9 while still blocked on 3.12.
    summary = summarize([], [])
    assert summary["files"] == 0
    assert set(summary["readiness"].values()) == {100.0}
    assert summary["rules"] == {}
    assert summary["findings"] == []


def test_clean_files_are_fully_ready():
    summary = summarize(["a.py", "b.py"], [])
    assert set(summary["readiness"].values()) == {100.0}


def test_readiness_counts_files_without_a_blocker():
    # A Finding built directly with no versions= applies to every judged
    # version (summarize's documented None-means-universal fallback).
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "x")]
    summary = summarize(["a.py", "b.py"], findings)
    assert set(summary["readiness"].values()) == {50.0}


def test_a_warning_does_not_affect_readiness():
    findings = [Finding("a.py", 1, "PY3-DIVISION", "warning", "x")]
    summary = summarize(["a.py", "b.py"], findings)
    assert set(summary["readiness"].values()) == {100.0}


def test_readiness_only_counts_versions_a_finding_applies_to():
    findings = [Finding("a.py", 1, "PY3-STDLIB", "blocker", "x",
                        versions=("3.12", "3.13"))]
    summary = summarize(["a.py", "b.py"], findings,
                        judged_versions=("3.9", "3.12"))
    assert summary["readiness"]["3.9"] == 100.0
    assert summary["readiness"]["3.12"] == 50.0


def test_file_readiness_names_every_file_even_with_no_findings():
    # R6: the report says, per file, which versions it is ready for - a
    # clean file never appears in "findings" at all, so without this key
    # it would be named nowhere in the report (found missing by AutoSteer
    # CI: 57% of the real stdlib's files had no findings and so were
    # invisible in the JSON output).
    summary = summarize(["a.py", "b.py"], [],
                        judged_versions=("3.9", "3.12"))
    assert summary["file_readiness"] == {
        "a.py": ["3.9", "3.12"], "b.py": ["3.9", "3.12"]}


def test_file_readiness_excludes_only_the_versions_a_file_is_blocked_on():
    findings = [Finding("a.py", 1, "PY3-STDLIB", "blocker", "x",
                        versions=("3.12",))]
    summary = summarize(["a.py", "b.py"], findings,
                        judged_versions=("3.9", "3.12"))
    assert summary["file_readiness"]["a.py"] == ["3.9"]
    assert summary["file_readiness"]["b.py"] == ["3.9", "3.12"]


def test_file_readiness_a_warning_does_not_block_any_version():
    findings = [Finding("a.py", 1, "PY3-DIVISION", "warning", "x")]
    summary = summarize(["a.py"], findings, judged_versions=("3.9", "3.12"))
    assert summary["file_readiness"]["a.py"] == ["3.9", "3.12"]


def test_file_readiness_version_invariant_finding_blocks_every_version():
    findings = [Finding("a.py", 1, "PY3-PRINT", "blocker", "x")]
    summary = summarize(["a.py"], findings, judged_versions=("3.9", "3.12"))
    assert summary["file_readiness"]["a.py"] == []


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
    findings = [
        Finding("a.py", 1, "PY3-STDLIB", "blocker", "import of ConfigParser"),
        Finding("a.py", 1, "PY3-STDLIB", "blocker", "import of urllib2"),
    ]
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


def test_read_lines_falls_back_to_utf8_for_an_unknown_codec():
    # Item 3: an invalid coding declaration (one naming a codec that
    # doesn't exist) must not take down HTML rendering. detect_encoding
    # itself raises SyntaxError for this - confirmed directly against
    # lib2to3.pgen2.tokenize.detect_encoding before this was fixed.
    root = tempfile.mkdtemp()
    try:
        path = os.path.join(root, "badcoding.py")
        with open(path, "wb") as f:
            f.write(b"# -*- coding: bogus-nonexistent-codec -*-\nx = 1\n")
        lines = read_lines(path)
    finally:
        shutil.rmtree(root)
    assert lines[1] == u"x = 1"


def test_no_problems_is_a_complete_report():
    summary = summarize(["a.py"], [])
    assert summary["complete"] is True
    assert summary["problems"] == []


def test_problems_make_the_report_incomplete():
    summary = summarize(["a.py"], [],
                        problems=[("bad.py", "Permission denied")])
    assert summary["complete"] is False
    assert summary["problems"] == [
        {"path": "bad.py", "reason": "Permission denied"}]


def test_problems_are_sorted_by_path():
    summary = summarize(["a.py"], [], problems=[("z.py", "x"), ("a.py", "y")])
    assert [p["path"] for p in summary["problems"]] == ["a.py", "z.py"]


def test_render_html_contains_readiness_rule_counts_and_escaped_source():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "a.py"), "wb") as f:
            f.write(b"print 'hi' if 1 < 2 else None\n")
        files = ["a.py"]
        findings = [Finding("a.py", 1, "PY3-PRINT", "blocker",
                            "print statement; Python 3 has only the "
                            "print() function")]
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
