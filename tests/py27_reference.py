# -*- coding: utf-8 -*-
"""Canonical forms of what Python 2.7's parser and ast modules compute, and of
what py2scan.py27 computes, that serialize to the same JSON on 2.7 and 3.x.

Byte strings become hex, text becomes code points (so lone surrogates
survive), identifiers become text and numbers become their 2.7 type and an
exact value: hex for integers, float.hex() for floats. A failure becomes its
exception name, message and line.
"""
import hashlib
import json
import sys

from py2scan.py27 import ast27
from py2scan.py27.parser import Py27SyntaxError, parse_cst, to_tuple

text_type = type(u"")
ENCODING_DECL = 339
_LONG_MIN, _LONG_MAX = -2 ** 63, 2 ** 63 - 1  # C long on the LP64 platforms 2.7.18 runs on


def _decimal(digits):
    """int(digits) without 3.11's limit on decimal digits."""
    limit = getattr(sys, "set_int_max_str_digits", None)
    if limit is None:
        return int(digits)
    previous = sys.get_int_max_str_digits()
    limit(0)
    try:
        return int(digits)
    finally:
        limit(previous)


def _integer(text):
    sign, body = (-1, text[1:]) if text.startswith("-") else (1, text)
    if body[:2].lower() in ("0x", "0o", "0b"):
        return sign * int(body, 0)
    if len(body) > 1 and body[0] == "0":  # old-style octal
        return sign * int(body, 8)
    return sign * _decimal(body)


def number_of_text(text):
    """(2.7 type, exact value) of a Num.n that ast27 keeps as text, as 2.7's
    parsenumber computes it: PyOS_strtol, else a long, float or imaginary."""
    if text[-1] in "lL":
        return ["long", "%x" % _integer(text[:-1])]
    if text[-1] in "jJ":
        return ["complex", float(text[:-1]).hex()]
    body = text.lstrip("-")
    if body[:2].lower() in ("0x", "0o", "0b") or not any(c in body for c in ".eE"):
        value = _integer(text)
        return ["int" if _LONG_MIN <= value <= _LONG_MAX else "long", "%x" % value]
    return ["float", float(text).hex()]


def number_of_value(value):
    kind = type(value).__name__
    if kind in ("int", "long"):
        return [kind, "%x" % value]
    if kind == "float":
        return [kind, value.hex()]
    return [kind, value.imag.hex()]


def literal(value):
    if isinstance(value, bytes):
        return "b:" + "".join("%02x" % c for c in bytearray(value))
    return "u:" + ",".join("%x" % ord(c) for c in value)


def _identifier(value):
    return value.decode("ascii") if isinstance(value, bytes) else value


def canonical_ast(node):
    """A JSON-able form of an AST from 2.7's ast module or from ast27."""
    if isinstance(node, list):
        return [canonical_ast(item) for item in node]
    if node is None or isinstance(node, (bool, int)):
        return node
    if isinstance(node, (bytes, text_type)):
        return _identifier(node)
    out = [type(node).__name__]
    for name in node._fields:
        value = getattr(node, name)
        if out[0] == "Num":
            out.append(number_of_text(value) if isinstance(node, ast27.AST) else number_of_value(value))
        elif out[0] == "Str":
            out.append(literal(value))
        else:
            out.append(canonical_ast(value))
    out.extend(getattr(node, name) for name in node._attributes)
    return out


def canonical_cst(node):
    """A JSON-able form of parser.suite(source).totuple(True, True) or ast27's to_tuple."""
    if node[0] == ENCODING_DECL:
        return [node[0], canonical_cst(node[1]), _identifier(node[2])]
    if isinstance(node[1], (bytes, text_type)):
        value = node[1].decode("latin-1") if isinstance(node[1], bytes) else node[1]
        return [node[0], value] + list(node[2:])
    return [node[0]] + [canonical_cst(child) for child in node[1:]]


def canonical_error(kind, msg, lineno):
    """A failure: the exception's name, message and line."""
    return ["error", kind, _identifier(msg), lineno]


def as_json(form):
    return json.dumps(form, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(text):
    """The digest a long canonical JSON text is recorded as."""
    return "sha256:" + hashlib.sha256(text.encode("ascii")).hexdigest()


def recorded(text, inline=2000):
    """How a canonical JSON text is recorded: itself when short, else its digest."""
    return json.loads(text) if len(text) <= inline else digest(text)


def same(record, text):
    """Whether a canonical JSON text is what was recorded, in full or as a digest."""
    if isinstance(record, type(u"")) and record.startswith(u"sha256:"):
        return record == digest(text)
    return as_json(record) == text


def _deep(function, *args):
    """function(*args) with room for the deepest tree either side builds: 2.7's
    ast and parser objects, and these canonical forms, are converted recursively."""
    import threading
    result = []
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 200000))
    size = threading.stack_size(512 * 1024 * 1024)
    try:
        thread = threading.Thread(target=lambda: result.append(function(*args)))
        thread.start()
        thread.join()
    finally:
        threading.stack_size(size)
        sys.setrecursionlimit(limit)
    return result[0]


def mine(source):
    """(CST, AST) JSON that py2scan.py27 computes for source bytes."""
    def compute():
        try:
            result = parse_cst(source)
        except Py27SyntaxError as e:
            error = as_json(canonical_error(e.kind, e.msg, e.lineno))
            return error, error
        cst = as_json(canonical_cst(to_tuple(result)))
        try:
            return cst, as_json(canonical_ast(ast27.build(result)))
        except Py27SyntaxError as e:
            return cst, as_json(canonical_error(e.kind, e.msg, e.lineno))
    return _deep(compute)


def _failure(e):
    msg = e.msg if isinstance(e, SyntaxError) else str(e)
    return as_json(canonical_error(type(e).__name__, msg, getattr(e, "lineno", None)))


def reference(source):
    """(CST, AST) JSON that Python 2.7 itself computes. 2.7 only.

    parser.suite rejects a NUL byte while parsing its arguments, before the
    parser sees the source, so for such a source the compiler's own rejection
    stands for the CST as well."""
    import ast
    import parser

    def compute():
        try:
            tree = as_json(canonical_ast(ast.parse(source)))
        except Exception as e:  # what each failure is called is the point of the comparison
            tree = _failure(e)
        if b"\0" in source:
            return tree, tree
        try:
            cst = as_json(canonical_cst(parser.suite(source).totuple(True, True)))
        except Exception as e:
            cst = _failure(e)
        return cst, tree
    return _deep(compute)
