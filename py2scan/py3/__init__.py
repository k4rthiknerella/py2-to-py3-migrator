# -*- coding: utf-8 -*-
"""What each judged Python 3 version cannot compile (ruling R1).

"Compile" is what import and py_compile do with a file's bytes:
compile(source, path, "exec", dont_inherit=True) on the official
python:X.Y.Z-slim image, with its default 8 MiB stack and 1 GiB of memory.
Each detector reads a rules.Module and yields a Problem: where, why, the
versions it blocks, and the versions whose compile() it stops (syntax). A
detector that cannot decide claims the versions it blocks but no syntax.

The verdicts are checked against the real interpreters by tests/test_py3.py.
"""
from py2scan.py3 import blocks, compiler, encoding, grammar, keywords, lexical, limits
from py2scan.py3.common import EXCEPT_COMMA, ne_syntax, statement_syntax

DETECTORS = (encoding.DETECTORS + lexical.DETECTORS + keywords.DETECTORS + grammar.DETECTORS
             + compiler.DETECTORS + blocks.DETECTORS + limits.DETECTORS)


def problems(m):
    for detect in DETECTORS:
        for found in detect(m):
            yield found


__all__ = ["EXCEPT_COMMA", "ne_syntax", "problems", "statement_syntax"]
