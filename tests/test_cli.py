# -*- coding: utf-8 -*-
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
    assert result.exit_code == 0, result.output
    assert "pkg/a.py:1: PY3-PRINT" in result.output
    assert "2 files, 1 findings" in result.output
