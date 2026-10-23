# -*- coding: utf-8 -*-
"""Python 2.7's LL(1) parser and its driver, ported from Parser/parser.c and parsetok.c.

parse_cst(source) returns the concrete syntax tree CPython 2.7's parser
module would build, as Node objects, or raises Py27SyntaxError with the
message and line pythonrun.c's err_input would report.

Copyright (c) 2001-2020 Python Software Foundation; All Rights Reserved.
Used under the PSF License Agreement, version 2, in PSF-LICENSE.txt.
"""
from py2scan.py27 import source27
from py2scan.py27.grammar import (
    DEDENT, ENDMARKER, ERRORTOKEN, INDENT, LPAR, NAME, NEWLINE, NT_OFFSET, STAR, grammar)
from py2scan.py27.tokenizer import (
    E_DECODE, E_DEDENT, E_DONE, E_EOF, E_EOFS, E_EOLS, E_LINECONT, E_NOMEM, E_OK, E_SYNTAX,
    E_TABSPACE, E_TOKEN, E_TOODEEP, Tokenizer)

MAXSTACK = 1500  # Parser/parser.h
ENCODING_DECL = 339
CO_FUTURE_PRINT_FUNCTION = 0x10000
CO_FUTURE_UNICODE_LITERALS = 0x20000


class Py27SyntaxError(Exception):
    """What CPython 2.7 raises for source it cannot parse: kind is the exception's
    name, lineno the line 2.7 reports (None for its ValueErrors) and at the
    line the error arose on, when known."""

    def __init__(self, msg, lineno, kind="SyntaxError"):
        Exception.__init__(self, msg)
        self.msg = msg
        self.lineno = lineno
        self.kind = kind
        self.at = lineno


class Node(object):
    """A CST node. A token has a value and no children; a nonterminal the reverse.

    lineno and col are CPython's (the line a token ended on, -1 for a column
    on an earlier line); start_line and start_col are where it begins.
    """
    __slots__ = ("type", "value", "children", "lineno", "col", "start_line", "start_col")

    def __init__(self, kind, value, children, lineno, col, start_line, start_col):
        self.type = kind
        self.value = value
        self.children = children
        self.lineno = lineno
        self.col = col
        self.start_line = start_line
        self.start_col = start_col

    def totuple(self):
        """parser.st2tuple(line_info=True, col_info=True), built without recursion."""
        return _totuple(self)


def _totuple(root):
    done = {}
    stack = [(root, False)]
    while stack:
        node, expanded = stack.pop()
        if node.children is None:
            done[id(node)] = (node.type, node.value, node.lineno, node.col)
        elif expanded:
            done[id(node)] = (node.type,) + tuple(done.pop(id(c)) for c in node.children)
        else:
            stack.append((node, True))
            stack.extend((c, False) for c in node.children)
    return done[id(root)]


class _Parser(object):
    """parser_state: the DFA stack and the future flags the parser itself tracks."""

    def __init__(self, g):
        self.g = g
        self.root = Node(g.start, None, [], 0, 0, 0, 0)
        self.stack = [(g.dfas[g.start], 0, self.root, g.start)]
        self.flags = 0
        self.expected = -1

    def classify(self, kind, value):
        if kind == NAME and value in self.g.keywords:
            if not (value == "print" and self.flags & CO_FUTURE_PRINT_FUNCTION):
                return self.g.keywords[value]
        return self.g.token_labels.get(kind, -1)

    def add_token(self, kind, value, pos):
        """PyParser_AddToken: E_OK, E_DONE, E_SYNTAX or E_NOMEM."""
        label = self.classify(kind, value)
        if label < 0:
            return E_SYNTAX
        stack = self.stack
        while True:
            dfa, state, node, symbol = stack[-1]
            accel, final, _ = dfa[state]
            action = accel.get(label)
            if action is None:
                if not final:
                    self.expected = self.g.labels[next(iter(accel))][0] if len(accel) == 1 else -1
                    return E_SYNTAX
                if self._pop(symbol):
                    return E_SYNTAX
                continue
            if action.__class__ is tuple:
                if len(stack) >= MAXSTACK:
                    return E_NOMEM
                child_symbol, arrow = action
                child = Node(child_symbol, None, [], pos[0], pos[1], pos[2], pos[3])
                node.children.append(child)
                stack[-1] = (dfa, arrow, node, symbol)
                stack.append((self.g.dfas[child_symbol], 0, child, child_symbol))
                continue
            node.children.append(Node(kind, value, None, pos[0], pos[1], pos[2], pos[3]))
            stack[-1] = (dfa, action, node, symbol)
            return self._pop_accepted()

    def _pop(self, symbol):
        """Pop the top DFA; True if that empties the stack."""
        if symbol == self.g.symbols["import_stmt"]:
            self._future_hack(self.stack[-1][2])
        self.stack.pop()
        return not self.stack

    def _pop_accepted(self):
        stack = self.stack
        while True:
            dfa, state, node, symbol = stack[-1]
            if not dfa[state][2]:
                return E_OK
            if self._pop(symbol):
                return E_DONE

    def _future_hack(self, import_stmt):
        """parser.c future_hack, including its quirks: a relative or dotted module
        name also counts as __future__."""
        n = import_stmt.children[0]
        if len(n.children) < 4 or n.children[0].value != "from":
            return
        module = n.children[1]
        if module.children and len(module.children) == 1 and module.children[0].value != "__future__":
            return
        names = n.children[3]
        if names.type == STAR:
            return
        if names.type == LPAR:
            names = n.children[4]
        for item in (names.children or [])[::2]:
            first = item.children[0] if item.children else None
            if first is not None and first.type == NAME:
                if first.value == "print_function":
                    self.flags |= CO_FUTURE_PRINT_FUNCTION
                elif first.value == "unicode_literals":
                    self.flags |= CO_FUTURE_UNICODE_LITERALS


class ParseResult(object):
    """A parsed module: the CST root (unwrapped from encoding_decl), its tokens'
    tokenizer, the declared encoding and the parser's future flags."""

    def __init__(self, cst, encoding, flags, tokenizer, text):
        self.cst = cst
        self.encoding = encoding
        self.flags = flags
        self.tokenizer = tokenizer
        self.text = text


_ERRORS = {
    E_TOKEN: ("SyntaxError", "invalid token"),
    E_EOFS: ("SyntaxError", "EOF while scanning triple-quoted string literal"),
    E_EOLS: ("SyntaxError", "EOL while scanning string literal"),
    E_EOF: ("SyntaxError", "unexpected EOF while parsing"),
    E_TABSPACE: ("TabError", "inconsistent use of tabs and spaces in indentation"),
    E_DEDENT: ("IndentationError", "unindent does not match any outer indentation level"),
    E_TOODEEP: ("IndentationError", "too many levels of indentation"),
    E_LINECONT: ("SyntaxError", "unexpected character after line continuation character"),
    E_NOMEM: ("MemoryError", "s_push: parser stack overflow"),
}


def _error(code, expected, token, lineno):
    """pythonrun.c err_input."""
    if code == E_SYNTAX:
        if expected == INDENT:
            return Py27SyntaxError("expected an indented block", lineno, "IndentationError")
        if token == INDENT:
            return Py27SyntaxError("unexpected indent", lineno, "IndentationError")
        if token == DEDENT:
            return Py27SyntaxError("unexpected unindent", lineno, "IndentationError")
        return Py27SyntaxError("invalid syntax", lineno)
    kind, msg = _ERRORS[code]
    return Py27SyntaxError(msg, lineno, kind)


def _parse_tokens(tok, g):
    """parsetok: feed tokens to the parser; the CST root and flags, or raise."""
    p = _Parser(g)
    started = False
    while True:
        kind, a, b = tok.get()
        if kind == ERRORTOKEN:
            code, token = tok.done, -1
            break
        if kind == ENDMARKER and started:
            kind = NEWLINE
            started = False
            if tok.indent:
                tok.pendin = -tok.indent
                tok.indent = 0
        else:
            started = True
        value = tok.buf[a:b] if a is not None and b is not None else ""
        col = a - tok.line_start if a is not None and a >= tok.line_start else -1
        if a is None:
            start = (tok.lineno, col)
        else:
            start = (tok.start_lineno, tok.start_col)
        code = p.add_token(kind, value, (tok.lineno, col, start[0], start[1]))
        if code != E_OK:
            token = kind
            break
    if code == E_DONE:
        return p.root, p.flags
    if tok.lineno <= 1 and tok.done == E_EOF:
        code = E_EOF
    raise _error(code, p.expected, token, tok.lineno)


def parse_cst(source):
    """The CST of Python 2 source bytes, as 2.7's parser.suite builds it."""
    if b"\0" in source:
        raise Py27SyntaxError("compile() expected string without null bytes", None, "TypeError")
    try:
        text, encoding = source27.decode_source(source)
    except source27.DecodeError as e:
        raise Py27SyntaxError(e.msg, 0)
    tok = Tokenizer(text)
    root, flags = _parse_tokens(tok, grammar())
    return ParseResult(root, encoding, flags, tok, text)


def to_tuple(result):
    """parser.suite(source).totuple(True, True) for a ParseResult."""
    if result.encoding is None:
        return result.cst.totuple()
    return (ENCODING_DECL, result.cst.totuple(), result.encoding)


def is_terminal(kind):
    return kind < NT_OFFSET


__all__ = ["E_DECODE", "Node", "ParseResult", "Py27SyntaxError", "parse_cst", "to_tuple"]
