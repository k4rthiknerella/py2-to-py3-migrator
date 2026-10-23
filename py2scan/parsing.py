# -*- coding: utf-8 -*-
"""Parse Python 2.7 source the same way from a Python 2.7 or Python 3.x host.

Native ast.parse()/compile() reject Python-2-only syntax (print statements,
backticks, <>, old octals, ...) as soon as the host is Python 3, so they
cannot be the scanner's parser while straddling. parso ships a standalone
Python 2.7 grammar that both hosts can load, giving the same parse tree on
both sides. Native `tokenize` is kept for the handful of rules that only
need the token stream (parso's own 2.7 grammar has a known gap with the
<> operator); those rules read the raw token stream defensively rather
than trusting one fixed shape, since tokenize's own lexing of a couple of
these constructs is host-dependent -- see rules/token_rules.py.
"""
import io
import re
import sys
import tokenize
import warnings

import parso
from parso.parser import ParserSyntaxError

from py2scan.encoding import undecodable_cookie

_GRAMMAR = parso.load_grammar(version="2.7")
_ENCODING_TOKEN = getattr(tokenize, "ENCODING", None)
_UR_PREFIX_RE = re.compile(r'[uU][rR](?=[\'"])')
_UR_PREFIX_RE_BYTES = re.compile(br'[uU][rR](?=[\'"])')
_PRINT_FUTURE_RE = re.compile(
    r'^\s*from\s+__future__\s+import\s+.*\bprint_function\b', re.MULTILINE)
_PRINT_FUTURE_RE_BYTES = re.compile(
    br'^\s*from\s+__future__\s+import\s+.*\bprint_function\b', re.MULTILINE)
_PRINT_WORD_RE = re.compile(r'\bprint\b')
_PRINT_WORD_RE_BYTES = re.compile(br'\bprint\b')


def _placeholder_print_if_future(source):
    """CPython's real 2.7 parser honors `from __future__ import
    print_function` for the whole module, making print(...) an ordinary
    call expression - including forms parso's static print_stmt grammar
    rejects outright, like print(x, file=y) (a keyword argument, never
    valid as a print-statement operand). parso never adapts to
    __future__ imports (see ast_rules._has_future_name). Detected via a
    plain textual scan, since there is no tree yet to check: a false
    positive (the text appearing inside a string or comment) is
    vanishingly unlikely with the line-start anchor, and this file's own
    check_print already suppresses PY3-PRINT findings under the same
    condition, so the two layers agree either way.

    Replace the word "print" with the same-width "pr1nt" wherever it
    appears as its own word (never inside e.g. "print_function" or
    "pprint" - \\b doesn't match there) so parso parses it as a plain
    NAME/call instead of hitting the print_stmt production at all. If
    the file mixes true function-call print() with a genuine leftover
    print-statement line under the same future import, that line is a
    real syntax error under CPython too and will correctly still fail
    to parse after this substitution, for the same reason it fails for
    real: "pr1nt x" is exactly as invalid as "print x" was."""
    future_re = _PRINT_FUTURE_RE_BYTES if isinstance(source, bytes) else _PRINT_FUTURE_RE
    if not future_re.search(source):
        return source
    word_re = _PRINT_WORD_RE_BYTES if isinstance(source, bytes) else _PRINT_WORD_RE
    placeholder = b"pr1nt" if isinstance(source, bytes) else u"pr1nt"
    return word_re.sub(placeholder, source)


def _blank_ur_prefixes(source):
    """native tokenize raises TokenError the moment it reaches a ur"..."
    literal (a Python-2-only raw-unicode prefix; see check_ur_string),
    silently losing every token-based finding for the rest of the file.
    Blank the two prefix characters to same-width spaces before tokenize
    ever sees them: byte count and every other token's position are
    unchanged, and no token rule reads a STRING token's own text, so the
    substitution is invisible to all of them. The same style of fix as
    the <> substitution below, one token-stream step earlier."""
    if isinstance(source, bytes):
        return _UR_PREFIX_RE_BYTES.sub(b"  ", source)
    return _UR_PREFIX_RE.sub(u"  ", source)


class ParseFailure(object):
    def __init__(self, line, message):
        self.line = line
        self.message = message


def _tokenize(source):
    """Some Python-2-only lexical constructs (e.g. a ur"..." raw-unicode
    literal) make native tokenize raise partway through a file on a
    Python 3 host, even though the file tokenizes fine on 2.7. tokenize
    is a generator that yields progressively, so collect what it already
    produced before the raise instead of discarding the whole file's
    token-based findings for one construct elsewhere in it -- a defensive
    fallback for whatever specific construct trips it next, on top of
    (not instead of) fixing each one its own rule once found, the way
    check_ur_string does for this one."""
    tokenize_source = _blank_ur_prefixes(source)
    if sys.version_info[0] >= 3:
        raw = tokenize.tokenize(io.BytesIO(tokenize_source).readline)
    else:
        raw = tokenize.generate_tokens(io.BytesIO(tokenize_source).readline)
    tokens = []
    try:
        for t in raw:
            if t[0] != _ENCODING_TOKEN:
                tokens.append(t)
    except Exception:
        pass
    return tokens


def native_compiles(path, source):
    """Whether the interpreter currently running us can compile() this file.
    A pure boolean check: compile() can also emit a SyntaxWarning (e.g. an
    invalid escape sequence Python 2.7 never warned about) as a side
    effect even when it succeeds, which is not one of py2scan's own
    findings and would otherwise print to the user's terminal on every
    scan of an unrelated file; suppressed here, not reported."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            compile(source, path, "exec", 0, True)
        except Exception:
            return False
    return True


def parse_source(path, source):
    """Returns (tree, tokens, failure, native_compiles_bool).

    On a genuine Python-2.7 syntax error, tree and tokens are None and
    failure is a ParseFailure. Otherwise failure is None; tokens is [] if
    the native tokenizer could not lex the file even though parso could
    (defensive fallback, not expected to trigger on valid input).
    """
    # R2: a coding cookie naming a real text codec (unlike the seven
    # non-text ones scanner.py's bad_coding_cookie() already short-
    # circuits on) can still fail to decode these particular bytes -
    # e.g. "coding: utf-16" or "coding: punycode" on bytes that aren't
    # actually valid utf-16/punycode. Both hosts agree the file is
    # unparseable either way, but the real 2.7.18 and 3.14.9 codec
    # implementations raise different exception text for the identical
    # failure - confirmed to differ even in exception *type* for
    # punycode (AttributeError vs. UnicodeDecodeError) - so building
    # the message from the caught exception itself breaks byte parity.
    # Checked here, before the grammar ever sees the bytes, with a
    # message built only from the declared name, never the exception.
    bad_decode = undecodable_cookie(source)
    if bad_decode is not None:
        message = (u"does not parse under Python 2.7: coding: %s; these "
                   u"bytes do not decode under the declared encoding" % bad_decode)
        return None, None, ParseFailure(1, message), False

    # parso's "2.7" grammar has no production for <>, so it hard-fails on
    # valid Python 2.7 source that native tokenize (check_ne_op) handles
    # fine. Swap it for the same-width != only for the grammar parse: the
    # byte count never changes, so every other node's start_pos still lines
    # up with the real source, and check_ne_op below still reads the real
    # tokens, where the <> is intact.
    ne_marker = b"<>" if isinstance(source, bytes) else u"<>"
    ne_replacement = b"!=" if isinstance(source, bytes) else u"!="
    grammar_source = source.replace(ne_marker, ne_replacement)
    grammar_source = _placeholder_print_if_future(grammar_source)
    try:
        tree = _GRAMMAR.parse(grammar_source, error_recovery=False)
    except ParserSyntaxError as e:
        line = e.error_leaf.start_pos[0]
        message = u"does not parse under Python 2.7: %s" % e.message
        return None, None, ParseFailure(line, message), False
    except Exception as e:
        # LookupError (bad coding declaration), RecursionError (pathological
        # nesting), or anything else parso's grammar can raise: never let it
        # become an unhandled traceback (a traceback is a scanner failure).
        message = u"does not parse under Python 2.7: %s: %s" % (type(e).__name__, e)
        return None, None, ParseFailure(1, message), False

    try:
        tokens = _tokenize(source)
    except Exception:
        tokens = []

    return tree, tokens, None, native_compiles(path, source)
