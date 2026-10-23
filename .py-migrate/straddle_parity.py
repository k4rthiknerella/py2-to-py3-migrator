# -*- coding: utf-8 -*-
"""Straddle parity (task item 2b): the same input gives byte-identical JSON,
and the same exit code, under Python 2.7 and under the target.

  run OUT [CORPUS...]  on either interpreter, as a user who cannot read mode
                       000 files: build the hostile cases in a temporary
                       directory, run `python -m py2scan scan --format json`
                       on each case and each CORPUS, and write stdout and the
                       exit code to OUT/<name>.json and OUT/<name>.exit
  compare A B          exit 1 unless the two OUT directories hold the same
                       files with the same bytes

The hostile cases are AutoSteer CI's (one directory per case, each with ok.py
holding x = 1 beside the case), and a few more of the same kind.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CASES = [
    ("unreadable", {"t.py": b"x = 1\n"}),
    ("dangling", {}),
    ("symlink_loop", {}),
    ("nul_byte", {"t.py": b"x = 1\0"}),
    ("deep_nesting", {"t.py": b"x = " + b"(" * 150 + b"1" + b")" * 150 + b"\n"}),
    ("non_utf8_name", {b"caf\xe9.py": b"x = 1\n", b"\xed\xa0\x80.py": b"print 1\n"}),
    ("bom", {"t.py": b"\xef\xbb\xbfx = 1\n"}),
    ("crlf", {"t.py": b"x = 1\r\ny = 2\r\n"}),
    ("empty", {"t.py": b""}),
    ("invalid_coding", {"t.py": b"# -*- coding: no-such-codec -*-\nx = 1\n"}),
    ("dir_named_py", {"pkg.py/m.py": b"x = 1\n"}),
    ("fifo", {}),
    ("dot_directory", {".hidden/t.py": b"print 1\n"}),
    ("mixed", {"a.py": b"print 'hi'\n", "b.py": b"y = 1 / 2\n", "c.py": b"import urllib2\nx = 0777L\n"}),
]


def build(base):
    for name, files in CASES:
        case = os.path.join(base, name).encode("ascii")
        os.makedirs(case)
        files = dict(files, **{"ok.py": b"x = 1\n"})
        for rel, data in files.items():
            path = os.path.join(case, *(rel if isinstance(rel, bytes) else rel.encode("ascii")).split(b"/"))
            if not os.path.isdir(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            with open(path, "wb") as f:
                f.write(data)
    os.chmod(os.path.join(base, "unreadable", "t.py"), 0)
    os.symlink("missing.py", os.path.join(base, "dangling", "t.py"))
    os.mkdir(os.path.join(base, "symlink_loop", "d"))
    os.symlink("..", os.path.join(base, "symlink_loop", "d", "up"))
    os.mkfifo(os.path.join(base, "fifo", "t.py"))


def scan(path):
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
    process = subprocess.Popen([sys.executable, "-m", "py2scan", "scan", "--format", "json", path],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=ROOT)
    out, _ = process.communicate()
    return out, process.returncode


def run(out, corpora):
    if not os.path.isdir(out):
        os.makedirs(out)
    base = tempfile.mkdtemp()
    try:
        build(base)
        targets = [(name, os.path.join(base, name)) for name, _ in CASES]
        targets += [("corpus-%s" % os.path.basename(c.rstrip("/")), c) for c in corpora]
        for name, path in targets:
            stdout, code = scan(path)
            with open(os.path.join(out, name + ".json"), "wb") as f:
                f.write(stdout)
            with io.open(os.path.join(out, name + ".exit"), "w", encoding="ascii") as f:
                f.write(u"%d\n" % code)
            print("%s exit %d, %d bytes" % (name, code, len(stdout)))
    finally:
        os.chmod(os.path.join(base, "unreadable", "t.py"), 0o600)
        shutil.rmtree(base)
    return 0


def compare(a, b):
    names = sorted(set(os.listdir(a)) | set(os.listdir(b)))
    differ = 0
    for name in names:
        left, right = os.path.join(a, name), os.path.join(b, name)
        if not (os.path.isfile(left) and os.path.isfile(right)):
            differ += 1
            print("MISSING %s" % name)
            continue
        with open(left, "rb") as f, open(right, "rb") as g:
            if f.read() != g.read():
                differ += 1
                print("DIFF %s" % name)
    print("%d files compared, %d differ" % (len(names), differ))
    return 1 if differ or not names else 0


def main(argv):
    if argv[:1] == ["run"] and len(argv) >= 2:
        return run(argv[1], argv[2:])
    if argv[:1] == ["compare"] and len(argv) == 3:
        return compare(argv[1], argv[2])
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
