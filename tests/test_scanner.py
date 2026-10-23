# -*- coding: utf-8 -*-
import errno
import os
import shutil
import sys
import tempfile

import pytest

from py2scan.config import Config
from py2scan.scanner import scan, scan_file

# chmod 0 proves nothing when the test runs as root: CAP_DAC_OVERRIDE makes
# root bypass permission checks entirely, so root would read the file fine
# and no OSError would ever reach scanner.py's except clause.
_IS_ROOT = hasattr(os, "getuid") and os.getuid() == 0


def make_tree():
    root = tempfile.mkdtemp()
    os.mkdir(os.path.join(root, "pkg"))
    with open(os.path.join(root, "pkg", "a.py"), "wb") as f:
        f.write(b"print 'a'\n")
    with open(os.path.join(root, "b.py"), "wb") as f:
        f.write(b"print 'b'\nx = 1 / 2\n")
    with open(os.path.join(root, "c.py"), "wb") as f:
        f.write(b"x = 1\n")
    return root


def as_dicts(findings):
    return [f.to_dict() for f in findings]


def test_print_statement_is_a_blocker_on_both_interpreters():
    # R1: Python-2-only syntax can't ast.parse on Python 3, so check_print
    # never runs there - scan_file reports PY3-PARSE instead of PY3-PRINT.
    # The never-blocker-free guarantee holds either way (this test), but the
    # resulting rule/message text is NOT byte-identical JSON across
    # interpreters for this input - R1 says the guarantee wins the conflict,
    # not that the non-identical JSON is an accepted divergence; it is an
    # open, recorded defect against item 2b (see MIGRATION.md's Blockers).
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(b"print 'hi'\n")
        findings, problem = scan_file(root, "m.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert findings[0].severity == "blocker"
    expected_rule = "PY3-PARSE" if sys.version_info[0] >= 3 else "PY3-PRINT"
    assert findings[0].rule == expected_rule


def test_rot13_coding_declaration_is_a_blocker_on_both_interpreters():
    # Real held-back AutoSteer CI input: rot13-decodes to "x = 1", so it
    # compiles cleanly under 2.7 (PY3-NON-TEXT-CODING is what catches
    # it there) - but every real Python 3.6-3.15 rejects the coding
    # declaration itself, so ast.parse already raises on a 3.x scan and
    # PY3-PARSE covers it before this rule would even run. R1 holds
    # either way; the exact rule differs, same recorded item-2b shape as
    # print/exec/backtick/raise-comma above.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(b"# -*- coding: rot13 -*-\nk = 1\n")
        findings, problem = scan_file(root, "m.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert findings[0].severity == "blocker"
    expected = ("PY3-PARSE" if sys.version_info[0] >= 3
                else "PY3-NON-TEXT-CODING")
    assert findings[0].rule == expected


def _assert_blocker_on_both_interpreters(source, rule_on_27):
    # Genuinely runs and asserts on both interpreters (T12): the exact rule
    # differs by version (R1's recorded item-2b defect - see MIGRATION.md),
    # but the never-blocker-free guarantee is checked for real on both
    # sides, not skipped on one.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(source)
        findings, problem = scan_file(root, "m.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert findings[0].severity == "blocker"
    expected = "PY3-PARSE" if sys.version_info[0] >= 3 else rule_on_27
    assert findings[0].rule == expected


def test_exec_statement_is_a_blocker_on_both_interpreters():
    _assert_blocker_on_both_interpreters(b"exec 'x = 1'\n", "PY3-EXEC-STMT")


def test_backtick_is_a_blocker_on_both_interpreters():
    _assert_blocker_on_both_interpreters(b"y = `x`\n", "PY3-BACKTICK")


def _assert_raise_comma_is_a_blocker(source):
    # check_raise_comma is token-based (2b/R1, AutoSteer CI: 741 lost
    # findings, recovered) - raise E, v still fails ast.parse on Python
    # 3 (raise is a real keyword there, unlike print/exec), but now also
    # tokenizes and gets its own PY3-RAISE-COMMA finding there too,
    # alongside the pre-existing PY3-PARSE - not instead of it.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(source)
        findings, problem = scan_file(root, "m.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    rules = sorted(f.rule for f in findings)
    if sys.version_info[0] >= 3:
        assert rules == ["PY3-PARSE", "PY3-RAISE-COMMA"]
    else:
        assert rules == ["PY3-RAISE-COMMA"]
    assert all(f.severity == "blocker" for f in findings)


def test_raise_comma_is_a_blocker_on_both_interpreters():
    _assert_raise_comma_is_a_blocker(b"raise E, v\n")


def test_raise_comma_with_traceback_is_a_blocker_on_both_interpreters():
    _assert_raise_comma_is_a_blocker(b"raise E, v, tb\n")


def test_except_comma_is_byte_identical_across_interpreters():
    # Unlike print/exec/backtick/raise-comma/<>/old-octal/long-suffix,
    # `except Exception, e:` is NOT a SyntaxError on Python 3: its grammar
    # still accepts a bare tuple expression there, so ast.parse succeeds
    # (verified directly against a real 3.14.7 interpreter) and
    # check_except_comma's TOKEN_RULES logic runs for real, producing the
    # same PY3-EXCEPT-COMMA blocker on both sides - no item-2b defect here.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(b"try:\n    pass\nexcept Exception, e:\n    pass\n")
        findings, problem = scan_file(root, "m.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert findings[0].rule == "PY3-EXCEPT-COMMA"
    assert findings[0].severity == "blocker"


def test_jobs_does_not_affect_output():
    root = make_tree()
    try:
        files1, findings1, problems1 = scan(root, jobs=1)
        files4, findings4, problems4 = scan(root, jobs=4)
    finally:
        shutil.rmtree(root)
    assert files1 == files4
    assert as_dicts(findings1) == as_dicts(findings4)
    assert problems1 == problems4 == []


def test_a_broken_file_does_not_affect_scanning_of_others():
    # ok.py uses unicode(), not a print statement: print is Python-2-only
    # syntax, so ast.parse itself would fail on Python 3 and this file would
    # report PY3-PARSE like broken.py does, rather than exercising the thing
    # this test is actually about (one bad file not poisoning the others).
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "broken.py"), "wb") as f:
            f.write(b"def f(:\n")
        with open(os.path.join(root, "ok.py"), "wb") as f:
            f.write(b"x = unicode('hi')\n")
        files, findings, problems = scan(root, jobs=4)
    finally:
        shutil.rmtree(root)
    assert problems == []
    by_file = {}
    for f in findings:
        by_file.setdefault(f.file, []).append(f.rule)
    assert by_file["broken.py"] == ["PY3-PARSE"]
    assert by_file["ok.py"] == ["PY3-BUILTIN"]


def test_parse_blocker_message_does_not_name_the_running_interpreter():
    # Reverted (R1/item 2b correction, flagged by AutoSteer CI): this
    # message used to report platform.python_version(), on the reasoning
    # that the exact patch version matters for debugging (the check_ne_op
    # regression this session proved 3.14.7 and 3.14.9 can disagree about
    # tokenizing the same source). But R1's compile guarantee never
    # required that difference, so it was an unforced divergence between
    # a 2.7 scan's JSON and a 3.x scan's JSON for the identical input
    # (confirmed directly: real 2.7.18 and 3.14.7 raise the identical
    # SyntaxError.msg, "unknown encoding: ...", for an invalid coding
    # declaration - only this code's own version-naming wrapper made the
    # two sides differ).
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "broken.py"), "wb") as f:
            f.write(b"def f(:\n")
        findings, problem = scan_file(root, "broken.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert "Python" not in findings[0].message


def test_parse_blocker_message_is_byte_identical_for_an_invalid_coding():
    # The real repro: real 2.7.18 and every real Python 3.6-3.15 raise
    # the identical SyntaxError.msg for this (confirmed directly) - the
    # message built here must not reintroduce a difference.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(b"# -*- coding: no-such-codec -*-\nx = 1\n")
        findings, problem = scan_file(root, "m.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert findings[0].message == (
        "does not parse: unknown encoding: no-such-codec")


def test_parse_blocker_message_is_stable_for_an_embedded_nul_byte():
    # 2.7 raises TypeError here and 3.x raises SyntaxError, with
    # genuinely different built-in message text on each side (confirmed
    # directly) - special-cased to a fixed, interpreter-independent
    # message instead of passing either one through.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(b"x = 1\n\x00\ny = 2\n")
        findings, problem = scan_file(root, "m.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert findings[0].message == (
        "does not parse: source contains an embedded NUL byte")


def test_scanner_never_executes_the_code_it_scans():
    # Item 2c: the scanner only ever ast.parse's/tokenizes raw bytes - it
    # must never import or execute a scanned file. A module-level side
    # effect (creating a sentinel file) would run the instant the module
    # were imported or exec'd; it must never run here, through either
    # scan_file directly or the full scan() pipeline (which runs each
    # file in a separate worker process via ProcessPoolExecutor).
    root = tempfile.mkdtemp()
    try:
        sentinel = os.path.join(root, "sentinel")
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(("open(%r, 'w').close()\n" % sentinel)
                    .encode("ascii"))
        findings, problem = scan_file(root, "m.py")
        assert problem is None
        assert findings == []
        assert not os.path.exists(sentinel)

        files, findings, problems = scan(root, jobs=1)
        assert files == ["m.py"]
        assert problems == []
        assert not os.path.exists(sentinel)
    finally:
        shutil.rmtree(root)


def test_config_is_applied_end_to_end():
    # Deliberately not make_tree(): its fixtures use print statements, which
    # are Python-2-only syntax and report PY3-PARSE (not PY3-PRINT) once
    # ast.parse itself can't succeed, on Python 3. unicode()/division are
    # ordinary expressions that parse (and so are detectable) on both.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "a.py"), "wb") as fh:
            fh.write(b"x = unicode('hi')\n")
        with open(os.path.join(root, "b.py"), "wb") as fh:
            fh.write(b"y = 1 / 2\n")
        cfg = Config(disabled=["PY3-BUILTIN"], severity={})
        files, findings, problems = scan(root, jobs=1, config=cfg)
    finally:
        shutil.rmtree(root)
    assert problems == []
    assert "PY3-BUILTIN" not in [f.rule for f in findings]
    assert "PY3-DIVISION" in [f.rule for f in findings]


@pytest.mark.skipif(_IS_ROOT, reason="root bypasses permission checks")
def test_unreadable_py_file_is_a_problem_not_a_crash():
    # R5: scan_file reports the reason instead of raising, and never
    # fabricates findings for a file it couldn't read.
    root = tempfile.mkdtemp()
    try:
        path = os.path.join(root, "secret.py")
        with open(path, "wb") as f:
            f.write(b"x = 1\n")
        os.chmod(path, 0o000)
        findings, problem = scan_file(root, "secret.py")
    finally:
        os.chmod(path, 0o644)
        shutil.rmtree(root)
    assert findings == []
    assert problem is not None


@pytest.mark.skipif(_IS_ROOT, reason="root bypasses permission checks")
def test_unreadable_directory_is_listed_as_a_problem():
    # R5: an unreadable directory is listed with its reason; it does not
    # silently vanish from the file list, and it does not abort the scan
    # of files elsewhere under the root.
    root = tempfile.mkdtemp()
    try:
        blocked = os.path.join(root, "blocked")
        os.mkdir(blocked)
        os.chmod(blocked, 0o000)
        with open(os.path.join(root, "ok.py"), "wb") as f:
            f.write(b"x = 1\n")
        files, findings, problems = scan(root, jobs=1)
    finally:
        os.chmod(blocked, 0o755)
        shutil.rmtree(root)
    assert files == ["ok.py"]
    assert len(problems) == 1
    assert problems[0][0] == "blocked"


@pytest.mark.skipif(not hasattr(os, "symlink"),
                    reason="platform has no symlink support")
def test_dangling_symlink_is_a_problem_not_a_crash():
    # A dangling symlink fails os.stat with ENOENT regardless of who runs
    # the scan - unlike permission denial, this is not root-bypassable, so
    # it exercises the per-entry OSError branch in every environment.
    root = tempfile.mkdtemp()
    try:
        os.symlink(os.path.join(root, "missing-target"),
                   os.path.join(root, "dangling.py"))
        with open(os.path.join(root, "ok.py"), "wb") as f:
            f.write(b"x = 1\n")
        files, findings, problems = scan(root, jobs=1)
    finally:
        shutil.rmtree(root)
    assert files == ["ok.py"]
    assert len(problems) == 1
    assert problems[0][0] == "dangling.py"


@pytest.mark.skipif(not hasattr(os, "mkfifo"),
                    reason="platform has no mkfifo support")
def test_non_regular_entry_is_a_problem_not_a_crash():
    # R5: a FIFO under the scan root is neither a file py2scan can scan nor
    # a directory it can recurse into; it must be listed, not dropped.
    root = tempfile.mkdtemp()
    try:
        os.mkfifo(os.path.join(root, "pipe.py"))
        with open(os.path.join(root, "ok.py"), "wb") as f:
            f.write(b"x = 1\n")
        files, findings, problems = scan(root, jobs=1)
    finally:
        shutil.rmtree(root)
    assert files == ["ok.py"]
    assert problems == [("pipe.py", "not a regular file or directory")]


def test_judged_versions_scopes_a_version_dependent_finding():
    # R6: distutils is only removed as of Python 3.12 - scanning with a
    # narrower judged_versions must not report it at all.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(b"import distutils\n")
        findings, problem = scan_file(root, "m.py", ("3.9",))
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert findings == []


def test_judged_versions_default_covers_the_full_range():
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(b"import distutils\n")
        findings, problem = scan_file(root, "m.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert findings[0].versions == ("3.12", "3.13", "3.14", "3.15")


def test_version_invariant_finding_gets_the_full_judged_set():
    # print is Python-2-only syntax - it's a blocker on every Python 3
    # version uniformly, so scan_file fills in the whole judged set,
    # not just a subset like check_stdlib_import computes for itself.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(b"print 'hi'\n")
        findings, problem = scan_file(root, "m.py", ("3.9", "3.12"))
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert findings[0].versions == ("3.9", "3.12")


def test_bad_byte_filename_is_scanned_and_stays_safe_to_serialize():
    # A legacy-encoded filename (common in older codebases) is an arbitrary
    # byte string on a POSIX filesystem. Python 2's os.listdir returns it
    # untouched with no decoding at all, so Finding.file can end up holding
    # bytes that aren't valid UTF-8; Python 3's os.listdir already
    # surrogate-escapes instead. Without Finding.to_dict()'s safe_text
    # call, this used to crash json.dumps on Python 2 even though the file
    # itself was always scanned correctly - only the output step crashed.
    root = tempfile.mkdtemp()
    try:
        if sys.version_info[0] >= 3:
            bad_path = os.path.join(root.encode("utf-8"), b"bad_\xff_name.py")
        else:
            bad_path = os.path.join(root, "bad_\xff_name.py")
        try:
            with open(bad_path, "wb") as f:
                f.write(b"x = unicode('hi')\n")
        except (OSError, IOError):
            pytest.skip("filesystem rejects an invalid-UTF-8 byte in a name")
        files, findings, problems = scan(root, jobs=1)
    finally:
        shutil.rmtree(root)
    assert problems == []
    assert len(files) == 1
    assert len(findings) == 1
    findings[0].to_dict()  # must never raise, on either interpreter


def test_embedded_nul_byte_is_a_parse_blocker_not_a_crash():
    # Item 3: the scan must complete on any tree a working copy can
    # contain, including a file with an embedded NUL byte. Python 2.7's
    # compile() raises TypeError for this (confirmed empirically - not
    # SyntaxError), which the original except SyntaxError clause let
    # propagate and crash the whole scan, not just this one file. Python
    # 3 already raises SyntaxError for the same input.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(b"x = 1\n\x00\ny = 2\n")
        findings, problem = scan_file(root, "m.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert findings[0].rule == "PY3-PARSE"
    assert findings[0].severity == "blocker"


@pytest.mark.skipif(not hasattr(os, "symlink"),
                    reason="platform has no symlink support")
def test_symlink_loop_is_a_problem_not_a_crash():
    # Item 3: a symlink that resolves back into its own ancestor must not
    # hang the scan. os.stat's own ELOOP bound (confirmed empirically to
    # return promptly, not hang) is already caught by _walk_entries's
    # per-entry OSError branch (R5).
    root = tempfile.mkdtemp()
    try:
        loopdir = os.path.join(root, "loopdir")
        os.mkdir(loopdir)
        os.symlink(loopdir, os.path.join(loopdir, "selfloop"))
        with open(os.path.join(root, "ok.py"), "wb") as f:
            f.write(b"x = 1\n")
        files, findings, problems = scan(root, jobs=1)
    finally:
        shutil.rmtree(root)
    assert files == ["ok.py"]
    assert len(problems) == 1
    assert problems[0][0].endswith("selfloop")
    assert os.strerror(errno.ELOOP) in problems[0][1]


def test_byte_order_mark_is_scanned_cleanly():
    # Item 3: a leading UTF-8 byte-order mark must not break parsing.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "bom.py"), "wb") as f:
            f.write(b"\xef\xbb\xbfx = 1\n")
        findings, problem = scan_file(root, "bom.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert findings == []


def test_crlf_line_endings_are_scanned_cleanly():
    # Item 3: CRLF line endings (common on a working copy checked out with
    # core.autocrlf) must not break parsing.
    root = tempfile.mkdtemp()
    try:
        with open(os.path.join(root, "crlf.py"), "wb") as f:
            f.write(b"x = 1\r\ny = 2\r\n")
        findings, problem = scan_file(root, "crlf.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert findings == []


def test_empty_file_is_scanned_cleanly():
    # Item 3: a 0-byte .py file must not break parsing.
    root = tempfile.mkdtemp()
    try:
        open(os.path.join(root, "empty.py"), "wb").close()
        findings, problem = scan_file(root, "empty.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert findings == []


def test_directory_named_dot_py_is_recursed_into_not_scanned_as_a_file():
    # Item 3: _walk_entries checks stat.S_ISDIR before the .py extension
    # check, so a directory literally named *.py is never mistaken for a
    # file and always recursed into.
    root = tempfile.mkdtemp()
    try:
        os.mkdir(os.path.join(root, "weird.py"))
        with open(os.path.join(root, "weird.py", "inner.py"), "wb") as f:
            f.write(b"x = 1\n")
        files, findings, problems = scan(root, jobs=1)
    finally:
        shutil.rmtree(root)
    assert files == ["weird.py/inner.py"]
    assert problems == []


def test_deeply_nested_expression_is_a_parse_blocker_not_a_crash():
    # Item 3: same guarantee, for a pathologically deep expression.
    # Python 2.7's C parser raises MemoryError ("s_push: parser stack
    # overflow", confirmed empirically) well before Python's own
    # recursion limit would trigger a RecursionError; Python 3's PEG
    # parser instead raises SyntaxError ("too many nested parentheses").
    # Both used to propagate uncaught and crash the whole scan.
    #
    # Tokenizing 3000 levels deep has no such stack limit on 2.7.18
    # (only the parser does), so there this also gets a second, more
    # specific finding from check_nesting_depth - scanner.scan_file now
    # runs TOKEN_RULES whenever tokenizing succeeds, independent of
    # whether ast.parse did (2b/R1, AutoSteer CI). On 3.9+, the
    # tokenizer itself shares the parser's 200-deep limit (confirmed
    # elsewhere in this suite), so 3000 levels fails to tokenize there
    # too and only PY3-PARSE fires.
    root = tempfile.mkdtemp()
    try:
        source = b"x = " + b"(" * 3000 + b"1" + b")" * 3000 + b"\n"
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(source)
        findings, problem = scan_file(root, "m.py")
    finally:
        shutil.rmtree(root)
    assert problem is None
    rules = sorted(f.rule for f in findings)
    if sys.version_info >= (3, 9):
        assert rules == ["PY3-PARSE"]
    else:
        assert rules == ["PY3-NESTING-DEPTH", "PY3-PARSE"]
    assert all(f.severity == "blocker" for f in findings)


def test_depth_95_blocks_3_6_and_3_7_on_both_interpreters():
    # AutoSteer CI repro: depth 95 exceeds 3.6's and 3.7's real limit
    # (92) but not 2.7.18's (98) or 3.14's (200) - so ast.parse succeeds
    # on both interpreters this project tests on, and PY3-NESTING-DEPTH
    # must fire identically on both, unlike the 150-deep case below
    # (which only parses on one side).
    root = tempfile.mkdtemp()
    try:
        source = b"x = " + b"(" * 95 + b"1" + b")" * 95 + b"\n"
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(source)
        findings, problem = scan_file(
            root, "m.py", ("3.6", "3.7", "3.14"))
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert findings[0].rule == "PY3-NESTING-DEPTH"
    assert findings[0].severity == "blocker"
    assert findings[0].versions == ("3.6", "3.7")


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="needs a running interpreter whose own parser handles depth "
           "150 (the PEG parser, 3.9+), so ast.parse succeeds and "
           "scan_file reaches VERSION_AWARE_TOKEN_RULES instead of its "
           "PY3-PARSE fallback")
def test_deep_nesting_still_blocks_versions_whose_own_limit_is_lower():
    # AutoSteer CI, real interpreters 3.6-3.15: hostile/deep_nesting (150
    # nested parens) parses fine under Python 3.9+ (real limit 200), so
    # ast.parse here never raises and PY3-PARSE's blanket, every-version
    # fallback never fires - but real Python 3.6-3.8 (real limit <= 98)
    # cannot compile it, so R1's never-blocker-free guarantee still
    # requires a blocker scoped to those versions specifically.
    root = tempfile.mkdtemp()
    try:
        source = b"x = " + b"(" * 150 + b"1" + b")" * 150 + b"\n"
        with open(os.path.join(root, "m.py"), "wb") as f:
            f.write(source)
        findings, problem = scan_file(
            root, "m.py", ("3.8", "3.9", "3.14"))
    finally:
        shutil.rmtree(root)
    assert problem is None
    assert len(findings) == 1
    assert findings[0].rule == "PY3-NESTING-DEPTH"
    assert findings[0].severity == "blocker"
    assert findings[0].versions == ("3.8",)
