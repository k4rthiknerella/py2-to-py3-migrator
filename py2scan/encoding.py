# -*- coding: utf-8 -*-
"""Decodes a source file's lines using its PEP 263 coding cookie, for
display."""
import io

try:
    # Python 2.7's own tokenize module lacks detect_encoding; lib2to3 backports
    # it. lib2to3 was removed from the stdlib in Python 3.13 (gh-104780), where
    # tokenize has carried the same function natively since Python 3.2.
    from lib2to3.pgen2.tokenize import detect_encoding
except ImportError:
    from tokenize import detect_encoding


def read_lines(path):
    with open(path, "rb") as f:
        source = f.read()
    try:
        encoding, _ = detect_encoding(io.BytesIO(source).readline)
    except SyntaxError:
        # Item 3: an invalid coding declaration (one naming a codec that
        # doesn't exist) makes detect_encoding itself raise - this is for
        # display only, so fall back instead of taking the whole HTML
        # report down over a single file's bad cookie.
        encoding = "utf-8"
    return source.decode(encoding, "replace").splitlines()


def safe_text(value):
    """A path/name that might not be clean, round-trippable Unicode, made
    safe to format, json.dumps, or render in a template - never raises.
    Deliberately not used for anything that still needs to open the real
    file afterward (scanner.py keeps the raw value for that) - this is
    for display only.

    Two distinct problems, one on each interpreter, for the same
    underlying cause (a legacy-encoded filename, an arbitrary byte string
    on a POSIX filesystem): Python 2's os.listdir returns it completely
    undecoded, so value can be raw non-UTF-8 bytes; Python 3's os.listdir
    decodes it with the surrogateescape error handler instead, so value
    is already str, but can hold lone surrogates that are not valid
    UTF-8 and raise UnicodeEncodeError the moment anything (click.echo,
    writing the HTML file) actually encodes the string - json.dumps was
    the one exception, since its default ensure_ascii=True escapes a
    surrogate as literal ASCII text instead of encoding it.
    """
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.decode("utf-8", "replace")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return value.encode("utf-8", "replace").decode("utf-8")
    return value
