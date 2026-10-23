# -*- coding: utf-8 -*-
import json
import os
import shutil
import tempfile

import pytest
from click.testing import CliRunner

from py2scan.cli import main


def test_scan_reports_findings_with_relative_paths():
    root = tempfile.mkdtemp()
    try:
        os.mkdir(os.path.join(root, "pkg"))
        with open(os.path.join(root, "pkg", "a.py"), "wb") as f:
            f.write(b"print 'hello'\n")
        with open(os.path.join(root, "b.py"), "wb") as f:
            f.write(b"x = 1\n")
        result = CliRunner().invoke(main, ["scan", root])
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 1, result.output
    assert "pkg/a.py:1: PY3-PRINT" in result.output
    assert "2 files, 1 findings" in result.output


def test_scan_exits_zero_when_no_blockers():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "a.py"), "wb") as f:
            f.write(b"x = 1\n")
        result = CliRunner().invoke(main, ["scan", root])
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 0, result.output


def test_disable_rule_via_config(tmp_path):
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "a.py"), "wb") as f:
            f.write(b"print 'hello'\n")
        config_path = os.path.join(str(tmp_path), "py2scan.yml")
        with open(config_path, "wb") as f:
            f.write(b"disable: [PY3-PRINT]\n")
        result = CliRunner().invoke(main, ["scan", root, "--config", config_path])
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 0, result.output
    assert "0 findings" in result.output


def test_format_json_output():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "a.py"), "wb") as f:
            f.write(b"print 'hello'\n")
        result = CliRunner().invoke(main, ["scan", root, "--format", "json"])
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["files"] == 1
    assert payload["readiness"]["3.9"] == 0.0
    assert payload["file_readiness"] == {"a.py": []}
    assert payload["rules"] == {"PY3-PRINT": 1}
    assert payload["findings"][0]["rule"] == "PY3-PRINT"
    assert "3.9" in payload["findings"][0]["versions"]


def test_unreadable_file_exits_2_and_is_listed():
    if os.getuid() == 0:
        pytest.skip("root bypasses the permission bits this test relies on")
    root = tempfile.mkdtemp()
    bad = os.path.join(root, "bad.py")
    try:
        with open(bad, "wb") as f:
            f.write(b"x = 1\n")
        os.chmod(bad, 0o000)
        result = CliRunner().invoke(main, ["scan", root])
    finally:
        os.chmod(bad, 0o644)
        shutil.rmtree(root)
    assert result.exit_code == 2, result.output
    assert "bad.py: unreadable: permission denied" in result.output


def test_jobs_flag_is_accepted():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "a.py"), "wb") as f:
            f.write(b"print 'hello'\n")
        result = CliRunner().invoke(main, ["scan", root, "--jobs", "2"])
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 1, result.output


def test_py3_flag_narrows_judged_versions():
    root = tempfile.mkdtemp()
    try:
        # async/await as identifiers only block Python 3.7+ (PY3-ASYNC-RESERVED);
        # judging only 3.6 should find nothing here.
        with open(os.path.join(root, "a.py"), "wb") as f:
            f.write(b"async = 1\n")
        result = CliRunner().invoke(main, ["scan", root, "--py3", "3.6", "--format", "json"])
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["versions_judged"] == ["3.6"]
    assert payload["findings"] == []


def test_invalid_py3_version_is_rejected():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "a.py"), "wb") as f:
            f.write(b"x = 1\n")
        result = CliRunner().invoke(main, ["scan", root, "--py3", "9.9"])
    finally:
        shutil.rmtree(root)
    assert result.exit_code != 0
    assert "9.9" in result.output


def test_html_report_is_written(tmp_path):
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "a.py"), "wb") as f:
            f.write(b"print 'hello'\n")
        html_path = os.path.join(str(tmp_path), "report.html")
        result = CliRunner().invoke(main, ["scan", root, "--html", html_path])
        assert result.exit_code == 1, result.output
        with open(html_path, "rb") as f:
            content = f.read().decode("utf-8")
        assert "PY3-PRINT" in content
        assert "a.py" in content
    finally:
        shutil.rmtree(root)
