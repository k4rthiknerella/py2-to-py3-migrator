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

import parso
from parso.parser import ParserSyntaxError

_GRAMMAR = parso.load_grammar(version="2.7")
_ENCODING_TOKEN = getattr(tokenize, "ENCODING", None)
_UR_PREFIX_RE = re.compile(r'[uU][rR](?=[\'"])')
_UR_PREFIX_RE_BYTES = re.compile(br'[uU][rR](?=[\'"])')


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
    """Whether the interpreter currently running us can compile() this file."""
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
    # parso's "2.7" grammar has no production for <>, so it hard-fails on
    # valid Python 2.7 source that native tokenize (check_ne_op) handles
    # fine. Swap it for the same-width != only for the grammar parse: the
    # byte count never changes, so every other node's start_pos still lines
    # up with the real source, and check_ne_op below still reads the real
    # tokens, where the <> is intact.
    ne_marker = b"<>" if isinstance(source, bytes) else u"<>"
    ne_replacement = b"!=" if isinstance(source, bytes) else u"!="
    grammar_source = source.replace(ne_marker, ne_replacement)
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
