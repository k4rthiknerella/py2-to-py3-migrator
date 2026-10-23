# -*- coding: utf-8 -*-
import json
import os
import shutil
import tempfile

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
    assert payload["readiness"] == 0.0
    assert payload["rules"] == {"PY3-PRINT": 1}
    assert payload["findings"][0]["rule"] == "PY3-PRINT"


def test_jobs_flag_is_accepted():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "a.py"), "wb") as f:
            f.write(b"print 'hello'\n")
        result = CliRunner().invoke(main, ["scan", root, "--jobs", "2"])
    finally:
        shutil.rmtree(root)
    assert result.exit_code == 1, result.output
