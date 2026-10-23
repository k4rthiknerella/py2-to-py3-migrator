# -*- coding: utf-8 -*-
"""The scan completes, and says what it could not scan, on any tree a working
copy can contain (spec item 3, rulings R5 and R6). Each case is built as
AutoSteer CI builds it: a directory holding ok.py (x = 1) beside the case."""
import json
import os

import pytest
from click.testing import CliRunner

from py2scan.cli import main
from py2scan.versions import VERSIONS, label

ALL = [label(v) for v in VERSIONS]


def case(tmpdir, name, files=None):
    root = tmpdir.join(name)
    root.ensure(dir=True)
    root.join("ok.py").write_binary(b"x = 1\n")
    for rel, data in sorted((files or {}).items()):
        root.join(rel).write_binary(data, ensure=True)
    return str(root)


def scan(root, *args):
    result = CliRunner(mix_stderr=False).invoke(main, ["scan", "--format", "json", root] + list(args))
    assert result.exception is None or isinstance(result.exception, SystemExit), result.output
    return result.exit_code, json.loads(result.output), result.stderr


def ready(data):
    return dict((entry["file"], entry["versions"]) for entry in data["ready"])


def outcome(data):
    return (data["files"], sorted(ready(data)), [(f["file"], f["line"], f["rule"]) for f in data["findings"]],
            data["skipped"], data["errors"], data["complete"])


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read any file")
def test_unreadable_file_is_listed_and_makes_the_report_incomplete(tmpdir):
    root = case(tmpdir, "unreadable", {"t.py": b"x = 1\n"})
    os.chmod(os.path.join(root, "t.py"), 0)
    code, data, stderr = scan(root)
    assert code == 2 and "t.py: cannot read: Permission denied" in stderr
    assert outcome(data) == (1, ["ok.py"], [], [], [{"path": "t.py", "reason": "cannot read: Permission denied"}],
                             False)


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read any directory")
def test_unreadable_directory_is_listed_even_when_blockers_are_found(tmpdir):
    root = case(tmpdir, "unreadable_dir", {"a.py": b"print 1\n", "sub/b.py": b"x = 1\n"})
    os.chmod(os.path.join(root, "sub"), 0)
    try:
        code, data, _ = scan(root)
    finally:
        os.chmod(os.path.join(root, "sub"), 0o700)
    assert code == 2
    assert outcome(data) == (2, ["a.py", "ok.py"], [("a.py", 1, "PY3-PRINT")], [],
                             [{"path": "sub", "reason": "cannot read: Permission denied"}], False)


def test_dangling_symlink_is_listed_as_skipped(tmpdir):
    root = case(tmpdir, "dangling")
    os.symlink("missing.py", os.path.join(root, "t.py"))
    code, data, _ = scan(root)
    assert code == 0
    assert outcome(data) == (1, ["ok.py"], [], [{"path": "t.py", "reason": "dangling symbolic link"}], [], True)


def test_symlink_to_a_directory_is_listed_as_skipped_and_not_followed(tmpdir):
    root = case(tmpdir, "symlink_loop")
    os.mkdir(os.path.join(root, "d"))
    os.symlink("..", os.path.join(root, "d", "up"))
    code, data, _ = scan(root)
    assert code == 0
    assert outcome(data) == (1, ["ok.py"], [], [
        {"path": "d/up", "reason": "symbolic link to a directory, not followed"}], [], True)


def test_symlink_loop_is_listed_as_skipped(tmpdir):
    root = case(tmpdir, "loop")
    os.symlink("b.py", os.path.join(root, "a.py"))
    os.symlink("a.py", os.path.join(root, "b.py"))
    code, data, _ = scan(root)
    assert code == 0
    assert data["skipped"] == [{"path": "a.py", "reason": "symbolic link loop"},
                               {"path": "b.py", "reason": "symbolic link loop"}]


def test_symlink_to_a_file_is_scanned(tmpdir):
    root = case(tmpdir, "file_link", {"real.txt": b"print 1\n"})
    os.symlink("real.txt", os.path.join(root, "t.py"))
    code, data, _ = scan(root)
    assert (code, outcome(data)[:3]) == (1, (2, ["ok.py", "t.py"], [("t.py", 1, "PY3-PRINT")]))


def test_fifo_named_py_is_listed_as_skipped(tmpdir):
    root = case(tmpdir, "fifo")
    os.mkfifo(os.path.join(root, "t.py"))
    code, data, _ = scan(root)
    assert (code, data["skipped"]) == (0, [{"path": "t.py", "reason": "a named pipe, not a regular file"}])


def test_dot_directory_is_listed_as_skipped(tmpdir):
    root = case(tmpdir, "dot", {".hidden/t.py": b"print 1\n"})
    code, data, _ = scan(root)
    assert code == 0
    assert outcome(data) == (1, ["ok.py"], [], [
        {"path": ".hidden", "reason": "a directory whose name starts with a dot"}], [], True)


@pytest.mark.parametrize("name, source", [
    ("nul_byte", b"x = 1\0"),
    ("nul_byte_line", b"x = 1\n\0"),
    ("deep_nesting", b"x = " + b"(" * 150 + b"1" + b")" * 150 + b"\n"),
    ("invalid_coding", b"# -*- coding: no-such-codec -*-\nx = 1\n"),
])
def test_source_2_7_rejects_is_a_parse_blocker(tmpdir, name, source):
    root = case(tmpdir, name, {"t.py": source})
    code, data, _ = scan(root)
    assert code == 1
    assert outcome(data)[:3] == (2, ["ok.py", "t.py"], [("t.py", 1 + source.startswith(b"x = 1\n"), "PY3-PARSE")])
    assert (ready(data), data["findings"][0]["versions"]) == ({"ok.py": ALL, "t.py": []}, ALL)


@pytest.mark.parametrize("name, source", [
    ("bom", b"\xef\xbb\xbfx = 1\n"),
    ("crlf", b"x = 1\r\ny = 2\r\n"),
    ("empty", b""),
])
def test_clean_source_is_ready_for_every_version(tmpdir, name, source):
    root = case(tmpdir, name, {"t.py": source})
    code, data, _ = scan(root)
    assert (code, outcome(data)) == (0, (2, ["ok.py", "t.py"], [], [], [], True))
    assert ready(data) == {"ok.py": ALL, "t.py": ALL}


def test_non_utf8_file_name_is_scanned_and_shown_with_a_replacement_character(tmpdir):
    root = case(tmpdir, "non_utf8_name")
    with open(os.path.join(root.encode("utf-8"), b"caf\xe9.py"), "wb") as f:
        f.write(b"x = 1\n")
    code, data, _ = scan(root)
    assert (code, outcome(data)) == (0, (2, [u"caf�.py", "ok.py"], [], [], [], True))


def test_directory_named_py_is_a_directory(tmpdir):
    root = case(tmpdir, "dir_named_py", {"pkg.py/m.py": b"x = 1\n"})
    code, data, _ = scan(root)
    assert (code, outcome(data)) == (0, (2, ["ok.py", "pkg.py/m.py"], [], [], [], True))
