# -*- coding: utf-8 -*-
import json
import os
import shutil
import tempfile

import pytest
from click.testing import CliRunner

from py2scan.cli import main


def make_tree():
    # unicode(), not a print statement: print is Python-2-only syntax, so
    # ast.parse itself would fail on Python 3 and this would report
    # PY3-PARSE instead of exercising the rule these tests are actually
    # about. See R1 and tests/test_scanner.py's divergence test.
    root = tempfile.mkdtemp()
    os.mkdir(os.path.join(root, "pkg"))
    with open(os.path.join(root, "pkg", "a.py"), "wb") as f:
        f.write(b"x = unicode('hello')\n")
    with open(os.path.join(root, "b.py"), "wb") as f:
        f.write(b"x = 1\n")
    return root


def test_scan_reports_findings_with_relative_paths():
    root = make_tree()
    try:
        result = CliRunner().invoke(main, ["scan", root])
    finally:
        shutil.rmtree(root)
    assert "pkg/a.py:1: PY3-BUILTIN" in result.output
    assert "2 files, 1 findings" in result.output


def test_scan_exits_1_when_a_blocker_is_found():
    root = make_tree()
    try:
        result = CliRunner().invoke(main, ["scan", root])
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 1, result.output


def test_scan_exits_0_when_clean():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "clean.py"), "wb") as f:
            f.write(b"x = 1\n")
        result = CliRunner().invoke(main, ["scan", root])
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 0, result.output


def test_scan_format_json():
    root = make_tree()
    try:
        result = CliRunner().invoke(main, ["scan", "--format", "json", root])
    finally:
        shutil.rmtree(root)
    payload = json.loads(result.output)
    assert payload["files"] == 2
    assert payload["readiness"] == 50.0
    assert payload["rules"] == {"PY3-BUILTIN": 1}
    assert payload["findings"][0]["file"] == "pkg/a.py"


def test_scan_jobs_flag_does_not_change_output():
    root = make_tree()
    try:
        result1 = CliRunner().invoke(
            main, ["scan", "--format", "json", "--jobs", "1", root])
        result4 = CliRunner().invoke(
            main, ["scan", "--format", "json", "--jobs", "4", root])
    finally:
        shutil.rmtree(root)
    assert result1.output == result4.output


def test_scan_html_writes_a_report_file():
    root = make_tree()
    html_path = os.path.join(root, "report.html")
    try:
        result = CliRunner().invoke(main, ["scan", "--html", html_path, root])
        with open(html_path, "rb") as f:
            html = f.read().decode("utf-8")
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 1, result.output
    assert "PY3-BUILTIN" in html
    assert "unicode(&#39;hello&#39;)" in html


@pytest.mark.skipif(not hasattr(os, "symlink"),
                    reason="platform has no symlink support")
def test_scan_exits_2_and_takes_priority_over_a_blocker_exit_1():
    # R5: a scan root with both an unreadable entry and a blocker exits 2,
    # not 1 - the never-fully-silent guarantee on unreadable entries wins.
    root = make_tree()
    try:
        os.symlink(os.path.join(root, "missing-target"),
                   os.path.join(root, "dangling.py"))
        result = CliRunner().invoke(
            main, ["scan", "--format", "json", root])
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["complete"] is False
    assert len(payload["problems"]) == 1
    assert payload["problems"][0]["path"] == "dangling.py"


@pytest.mark.skipif(not hasattr(os, "symlink"),
                    reason="platform has no symlink support")
def test_scan_text_format_reports_the_unreadable_entry():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "clean.py"), "wb") as f:
            f.write(b"x = 1\n")
        os.symlink(os.path.join(root, "missing-target"),
                   os.path.join(root, "dangling.py"))
        result = CliRunner().invoke(main, ["scan", root])
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 2, result.output
    assert "dangling.py: could not be read:" in result.output


def test_scan_config_disables_a_rule():
    root = make_tree()
    config_path = os.path.join(root, "py2scan.yaml")
    with open(config_path, "wb") as f:
        f.write(b"disable: [PY3-BUILTIN]\n")
    try:
        result = CliRunner().invoke(
            main, ["scan", "--format", "json", "--config", config_path, root])
    finally:
        shutil.rmtree(root)
    payload = json.loads(result.output)
    assert payload["rules"] == {}
    assert payload["readiness"] == 100.0
    assert result.exit_code == 0
