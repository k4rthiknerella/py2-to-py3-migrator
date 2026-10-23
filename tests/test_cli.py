# -*- coding: utf-8 -*-
import io
import json
import os

import pytest
from click.testing import CliRunner

from py2scan.cli import main


def tree(root, files):
    for rel, data in files.items():
        if isinstance(rel, bytes):  # a name given as the bytes on disk
            base = str(root) if str is bytes else os.fsencode(str(root))
            path = os.path.join(base, *rel.split(b"/"))
        else:
            path = os.path.join(str(root), *rel.split("/"))
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, "wb") as f:
            f.write(data)
    return str(root)


def run(root, *args):
    return CliRunner().invoke(main, ["scan", root] + list(args))


def run_json(root, *args):
    result = run(root, "--format", "json", *args)
    assert result.exception is None or isinstance(result.exception, SystemExit), result.output
    return result.exit_code, json.loads(result.output)


def triples(data):
    return [(f["file"], f["line"], f["rule"]) for f in data["findings"]]


MIXED = {
    "a.py": b"print 'hi'\n",
    "b.py": b"x = 1\n",
    "pkg/__init__.py": b"",
    "pkg/c.py": b"y = 1 / 2\n",
    ".venv/lib.py": b"print 'skipped'\n",
    "pkg/.hidden/d.py": b"print 'skipped'\n",
    "notes.txt": b"print 'not python'\n",
}


def test_text_report_lists_findings_with_relative_paths(tmpdir):
    root = tree(tmpdir, {"pkg/a.py": b"print 'hello'\n", "b.py": b"x = 1\n"})
    result = run(root)
    assert result.exit_code == 1, result.output
    assert "pkg/a.py:1: PY3-PRINT" in result.output
    assert "2 files, 1 findings" in result.output


def test_json_report(tmpdir):
    code, data = run_json(tree(tmpdir, MIXED))
    assert code == 1
    assert data["files"] == 4
    assert data["readiness"] == 75.0
    assert data["rules"] == {"PY3-DIVISION": 1, "PY3-PRINT": 1}
    assert [(f["file"], f["line"], f["rule"], f["severity"]) for f in data["findings"]] == [
        ("a.py", 1, "PY3-PRINT", "blocker"), ("pkg/c.py", 1, "PY3-DIVISION", "warning")]
    assert all(sorted(f) == ["file", "line", "message", "rule", "severity"] for f in data["findings"])
    assert all(f["message"] for f in data["findings"])


def test_readiness_is_percent_of_files_without_blockers(tmpdir):
    code, data = run_json(tree(tmpdir, {"a.py": b"print 1\n", "b.py": b"x = 1\n", "c.py": b"x = 2\n"}))
    assert data["readiness"] == pytest.approx(200.0 / 3)


def test_findings_are_sorted_by_file_line_rule(tmpdir):
    root = tree(tmpdir, {
        "z.py": b"x = 1\nprint `x`\nimport urllib2\n",
        "a/x.py": b"y = 2\nexec 'y'\n",
        "a.py": b"x = a <> b\nprint x\n",
    })
    code, data = run_json(root)
    assert triples(data) == [
        ("a.py", 1, "PY3-NE-OP"), ("a.py", 2, "PY3-PRINT"), ("a/x.py", 2, "PY3-EXEC-STMT"),
        ("z.py", 2, "PY3-BACKTICK"), ("z.py", 2, "PY3-PRINT"), ("z.py", 3, "PY3-STDLIB")]


def test_only_warnings_exit_zero(tmpdir):
    code, data = run_json(tree(tmpdir, {"a.py": b"x = 1 / 2\n"}))
    assert (code, data["readiness"]) == (0, 100.0)


def test_empty_tree(tmpdir):
    code, data = run_json(tree(tmpdir, {"README": b"nothing\n"}))
    assert (code, data) == (0, {"files": 0, "readiness": 100.0, "rules": {}, "findings": []})


def test_a_dot_directory_given_as_path_is_scanned(tmpdir):
    tree(tmpdir, {".src/a.py": b"print 1\n"})
    code, data = run_json(os.path.join(str(tmpdir), ".src"))
    assert triples(data) == [("a.py", 1, "PY3-PRINT")]


def test_parse_error_file_counts_as_a_blocker(tmpdir):
    code, data = run_json(tree(tmpdir, {"bad.py": b"print 'x'\nprint('a', end='')\n", "ok.py": b""}))
    assert (code, data["readiness"], triples(data)) == (1, 50.0, [("bad.py", 2, "PY3-PARSE")])


def test_a_literal_2_7_rejects_with_valueerror_is_a_parse_error_at_its_line(tmpdir):
    # 2.7's compiler raises ValueError, with no line, for an invalid \\x escape in a byte string.
    code, data = run_json(tree(tmpdir, {"bad.py": b"x = 1\ny = '\\x'\n"}))
    assert (code, triples(data)) == (1, [("bad.py", 2, "PY3-PARSE")])
    assert data["findings"][0]["message"] == "does not parse under Python 2.7: invalid \\x escape"


def write_config(tmpdir, text):
    path = os.path.join(str(tmpdir), "py2scan.yml")
    with open(path, "wb") as f:
        f.write(text)
    return path


def test_config_disables_rules(tmpdir):
    root = tree(tmpdir.mkdir("src"), {"a.py": b"print 1 / 2\n"})
    code, data = run_json(root, "--config", write_config(tmpdir, b"disable: [PY3-PRINT]\n"))
    assert (code, data["readiness"], data["rules"]) == (0, 100.0, {"PY3-DIVISION": 1})


def test_config_promotes_a_warning_to_a_blocker(tmpdir):
    root = tree(tmpdir.mkdir("src"), {"a.py": b"x = 1 / 2\n", "b.py": b""})
    cfg = write_config(tmpdir, b"severity:\n  PY3-DIVISION: blocker\n")
    code, data = run_json(root, "--config", cfg)
    assert (code, data["readiness"]) == (1, 50.0)
    assert [f["severity"] for f in data["findings"]] == ["blocker"]


def test_config_demotes_a_blocker_to_a_warning(tmpdir):
    root = tree(tmpdir.mkdir("src"), {"a.py": b"print 1\n"})
    cfg = write_config(tmpdir, b"severity: {PY3-PRINT: warning}\ndisable: []\n")
    code, data = run_json(root, "--config", cfg)
    assert (code, data["readiness"], data["findings"][0]["severity"]) == (0, 100.0, "warning")


@pytest.mark.parametrize("text,problem", [
    (b"disable: [PY3-PRNT]\n", "unknown rule PY3-PRNT"),
    (b"severity: {PY3-PRINT: fatal}\n", "fatal"),
    (b"severity: {NOPE: warning}\n", "unknown rule NOPE"),
    (b"disable: PY3-PRINT\n", "disable"),
    (b"ignore: [PY3-PRINT]\n", "ignore"),
    (b"- PY3-PRINT\n", "mapping"),
    (b"disable: [\n", "YAML"),
])
def test_invalid_config_is_a_usage_error(tmpdir, text, problem):
    root = tree(tmpdir.mkdir("src"), {"a.py": b"print 1\n"})
    result = run(root, "--config", write_config(tmpdir, text))
    assert result.exit_code == 2, result.output
    assert "--config" in result.output and problem in result.output, result.output


def test_empty_config_changes_nothing(tmpdir):
    root = tree(tmpdir.mkdir("src"), {"a.py": b"print 1\n"})
    code, data = run_json(root, "--config", write_config(tmpdir, b""))
    assert (code, data["rules"]) == (1, {"PY3-PRINT": 1})


def many_files(root):
    files = {}
    for i in range(40):
        files["pkg%d/m%02d.py" % (i % 3, i)] = (
            b"import urllib2\nprint `%d`\nx = %d / 2\n" % (i, i) if i % 4 == 0 else
            b"def f(:\n" if i % 7 == 0 else
            b"# -*- coding: latin-1 -*-\nprint 'caf\xe9'\n" if i % 5 == 0 else
            b"x = %d\n" % i)
    return tree(root, files)


def test_output_is_identical_for_any_number_of_jobs(tmpdir):
    root = many_files(tmpdir.mkdir("src"))
    outputs = set()
    js = None
    for jobs in ("1", "2", "3", "8"):
        html = os.path.join(str(tmpdir), "r%s.html" % jobs)
        text = run(root, "--jobs", jobs).output
        js = run(root, "--jobs", jobs, "--format", "json", "--html", html).output
        with open(html, "rb") as f:
            outputs.add((text, js, f.read()))
    assert len(outputs) == 1
    assert json.loads(js)["files"] == 40


def test_jobs_must_be_positive(tmpdir):
    result = run(tree(tmpdir, {"a.py": b""}), "--jobs", "0")
    assert result.exit_code == 2 and "Invalid value" in result.output, result.output


def html_report(tmpdir, files, *args):
    root = tree(tmpdir.mkdir("src"), files)
    out = os.path.join(str(tmpdir), "report.html")
    result = run(root, "--html", out, *args)
    assert result.exception is None or isinstance(result.exception, SystemExit), result.output
    with io.open(out, encoding="utf-8") as f:
        return f.read()


def test_html_report_shows_score_rule_counts_and_offending_lines(tmpdir):
    html = html_report(tmpdir, {
        "a.py": b"print 'hi'\nx = 1 <> 2\nprint 'bye'\n",
        "pkg/b.py": b"x = 1\n",
    })
    assert u"50.0%" in html
    assert u"PY3-PRINT" in html and u"PY3-NE-OP" in html
    assert u"<td>2</td>" in html.replace(u" class=\"count\"", u"")
    assert u"print 'hi'" in html and u"x = 1 &lt;&gt; 2" in html and u"print 'bye'" in html
    assert u"a.py" in html


def test_html_report_decodes_declared_encodings(tmpdir):
    html = html_report(tmpdir, {
        "latin.py": b"# -*- coding: latin-1 -*-\nprint 'caf\xe9'\n",
        "sjis.py": b"# coding: shift_jis\nprint '\x95\x5c'\n",
        "plain.py": b"print '\xc3\xa9t\xc3\xa9'\n",
    })
    assert u"print 'café'" in html
    assert u"print '表'" in html
    assert u"print 'été'" in html


def test_html_report_escapes_source(tmpdir):
    html = html_report(tmpdir, {"a.py": b"print \"<script>alert(1)</script>\"\n"})
    assert u"<script>alert" not in html
    assert u"print \"&lt;script&gt;alert(1)&lt;/script&gt;\"" in html


def test_html_report_is_self_contained(tmpdir):
    html = html_report(tmpdir, {"a.py": b"print 'x'\n"}).lower()
    for marker in (u"<link", u"<script", u"<img", u"src=", u"url(", u"@import", u"http:", u"https:"):
        assert marker not in html


def test_html_report_follows_config(tmpdir):
    cfg = write_config(tmpdir, b"disable: [PY3-PRINT]\n")
    html = html_report(tmpdir, {"a.py": b"print 'x'\nexec 'y'\n"}, "--config", cfg)
    assert u"PY3-EXEC-STMT" in html and u"PY3-PRINT" not in html


def test_non_ascii_paths_are_reported_as_text(tmpdir):
    root = tree(tmpdir, {u"caf\xe9/表.py".encode("utf-8"): b"print 1\n"})
    code, data = run_json(root)
    assert triples(data) == [(u"caf\xe9/表.py", 1, "PY3-PRINT")]
    assert u"caf\xe9/表.py:1: PY3-PRINT" in run(root).output


def test_broken_symlinks_are_not_files(tmpdir):
    root = tree(tmpdir, {"a.py": b"print 1\n"})
    os.symlink(os.path.join(root, "missing"), os.path.join(root, "gone.py"))
    code, data = run_json(root)
    assert (data["files"], triples(data)) == (1, [("a.py", 1, "PY3-PRINT")])


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read any file")
def test_unreadable_file_is_an_error_not_a_clean_file(tmpdir):
    root = tree(tmpdir, {"a.py": b"x = 1\n"})
    os.chmod(os.path.join(root, "a.py"), 0)
    result = run(root, "--format", "json")
    assert result.exit_code == 2 and "cannot read a.py" in result.output, result.output


def test_unwritable_html_path_is_an_error(tmpdir):
    root = tree(tmpdir, {"a.py": b"x = 1\n"})
    result = run(root, "--html", os.path.join(str(tmpdir), "no", "such", "dir", "r.html"))
    assert result.exit_code == 2 and "cannot write" in result.output, result.output
