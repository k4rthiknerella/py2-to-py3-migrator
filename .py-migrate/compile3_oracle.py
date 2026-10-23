# -*- coding: utf-8 -*-
"""What a real interpreter's compile() makes of each input: the test equipment
for py2scan's verdicts on Python 3 versions (rulings R1, R6, R7, R9).

  tree ROOT OUT      every .py file under ROOT
  cases CASES OUT    every source in CASES, a JSON list of hex strings
  (either, with --ast first: ast.parse instead of compile, as 2.7.18 is
  asked what parses)

OUT gets one JSON line per input: its name, the interpreter's exact version,
and either "ok" or the exception's type, message and line. Each input is
compiled with compile(source, name, "exec", dont_inherit=True) in a worker
process, as a file would be; warnings are not failures. A worker that dies
(a crash on deep nesting, for example) is recorded as "crash" and replaced.
"""
import binascii
import json
import os
import subprocess
import sys
import warnings

import _ast

VERSION = "%d.%d.%d" % sys.version_info[:3]


def worker(flags):
    stdin = getattr(sys.stdin, "buffer", sys.stdin)
    stdout = getattr(sys.stdout, "buffer", sys.stdout)
    for line in iter(stdin.readline, b""):  # not "for line in stdin": 2.7 reads ahead and would wait
        source = binascii.unhexlify(line.strip())
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                compile(source, "t.py", "exec", flags, True)
                result = {"ok": True}
            except BaseException as e:  # RecursionError, MemoryError and ValueError count too
                result = {"ok": False, "error": type(e).__name__, "msg": str(getattr(e, "msg", e))[:300],
                          "line": getattr(e, "lineno", None)}
        stdout.write((json.dumps(result) + "\n").encode("ascii"))
        stdout.flush()


class Oracle(object):
    def __init__(self, flags):
        self.process = None
        self.flags = flags

    def start(self):
        self.process = subprocess.Popen([sys.executable, os.path.abspath(__file__), "worker", str(self.flags)],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def compile(self, source):
        if self.process is None or self.process.poll() is not None:
            self.start()
        try:
            self.process.stdin.write(binascii.hexlify(source) + b"\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
        except (IOError, OSError):
            line = b""
        if not line:
            code = self.process.wait()
            self.process = None
            return {"ok": False, "error": "crash", "msg": "exit status %d" % code, "line": None}
        return json.loads(line.decode("ascii"))


def tree_inputs(root):
    for directory, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            if name.endswith(".py"):
                path = os.path.join(directory, name)
                with open(path, "rb") as f:
                    yield os.path.relpath(path, root), f.read()


def case_inputs(path):
    with open(path) as f:
        for index, source in enumerate(json.load(f)):
            yield str(index), binascii.unhexlify(source)


def record(inputs, out, flags):
    oracle = Oracle(flags)
    failed = 0
    with open(out, "w") as f:
        for name, source in inputs:
            result = oracle.compile(source)
            failed += not result["ok"]
            result.update(name=name, python=VERSION)
            f.write(json.dumps(result, sort_keys=True) + "\n")
    print("%s: %d failed" % (VERSION, failed))
    return 0


def main(argv):
    if len(argv) == 2 and argv[0] == "worker":
        return worker(int(argv[1]))
    flags = 0
    if argv[:1] == ["--ast"]:
        flags, argv = _ast.PyCF_ONLY_AST, argv[1:]
    if len(argv) == 3 and argv[0] == "tree":
        return record(tree_inputs(argv[1]), argv[2], flags)
    if len(argv) == 3 and argv[0] == "cases":
        return record(case_inputs(argv[1]), argv[2], flags)
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
