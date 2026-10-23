# -*- coding: utf-8 -*-
"""Python 2.7's tokenizer, ported from Parser/tokenizer.c (tok_get and tok_nextc).

It reads a text whose characters are the source's bytes after the PEP 263
decoding step (see source27), so offsets are byte offsets, as in CPython.
Line numbers and columns follow parsetok.c: a token's line is the line the
tokenizer had reached when the token ended, and its column is -1 when it
started on an earlier line.

Copyright (c) 2001-2020 Python Software Foundation; All Rights Reserved.
Used under the PSF License Agreement, version 2, in PSF-LICENSE.txt.
"""
import re

from py2scan.py27.grammar import (
    DEDENT, ENDMARKER, ERRORTOKEN, INDENT, NAME, NEWLINE, NUMBER, ONE_CHAR, OP, STRING, THREE_CHARS,
    TWO_CHARS)

# Include/errcode.h
E_OK, E_EOF, E_TOKEN, E_SYNTAX, E_NOMEM, E_DONE = 10, 11, 13, 14, 15, 16
E_TABSPACE, E_TOODEEP, E_DEDENT, E_DECODE, E_EOFS, E_EOLS, E_LINECONT = 18, 20, 21, 22, 23, 24, 25

TABSIZE = 8
MAXINDENT = 100
EOF = ""

_SPACES = re.compile(r"[ \t\f]*")
_NAME_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_DIGITS = frozenset("0123456789")
_NAME_REST = re.compile(r"[A-Za-z0-9_]*")
_STRING_PREFIX = re.compile(r"(?:[bBuU][rR]?|[rR])(?=['\"])")
_DECIMALS = re.compile(r"[0-9]*")
_RADIX = {"x": re.compile(r"[0-9a-fA-F]*"), "o": re.compile(r"[0-7]*"), "b": re.compile(r"[01]*")}
_OCTALS = re.compile(r"[0-7]*")
# Single-quoted string bodies: anything but the quote, a backslash or a newline,
# or a backslash and the character it escapes (a newline included).
_BODY = {"'": re.compile(r"(?:[^\\\n']|\\[\s\S])*"), '"': re.compile(r'(?:[^\\\n"]|\\[\s\S])*')}
_TRIPLE_BODY = {"'": re.compile(r"(?:[^\\']|\\[\s\S]|'(?!''))*"),
                '"': re.compile(r'(?:[^\\"]|\\[\s\S]|"(?!""))*')}
# Editor modelines that set the tab size, as tok_get looks for them in a comment.
_TAB_FORMS = ("tab-width:", ":tabstop=", ":ts=", "set tabsize=")
_ATOI = re.compile(r"[ \t\n\v\f\r]*([-+]?[0-9]+)")


def _atoi(text, pos):
    """C's atoi on an LP64 platform: strtol saturates to a long, then the result is cut to an int."""
    match = _ATOI.match(text, pos)
    if not match:
        return 0
    value = max(-2 ** 63, min(2 ** 63 - 1, int(match.group(1))))
    value &= 0xFFFFFFFF
    return value - 2 ** 32 if value >= 2 ** 31 else value


class Tokenizer(object):
    """tok_state: the input buffer, the current line and the indentation stacks."""

    def __init__(self, text):
        self.buf = text
        self.cur = 0          # next character
        self.inp = 0          # end of the current line
        self.line_start = 0
        self.lineno = 0
        self.done = E_OK
        self.tabsize = TABSIZE
        self.indstack = [0]
        self.altindstack = [0]
        self.indent = 0
        self.pendin = 0
        self.atbol = True
        self.level = 0
        self.start = None
        self.start_lineno = 0
        self.start_col = 0
        self.tab_magic = False  # a comment changed the tab size
        # (line, column with 8-column tabs, column with 1-column tabs, column
        # with this tokenizer's tabs) of each indentation the tokenizer
        # measured: what Python 3 would compare, and what 2.7 did.
        self.indents = []
        self.continuation = None  # offset of the last line-continuation backslash

    # tok_nextc and tok_backup
    def nextc(self):
        if self.cur != self.inp:
            c = self.buf[self.cur]
            self.cur += 1
            return c
        if self.done != E_OK:
            return EOF
        end = self.buf.find("\n", self.inp)
        if end < 0:
            end = len(self.buf)
            if end == self.inp:
                self.done = E_EOF
                return EOF
        else:
            end += 1
        self.line_start = self.cur
        self.lineno += 1
        self.inp = end
        c = self.buf[self.cur]
        self.cur += 1
        return c

    def backup(self, c):
        if c != EOF:
            self.cur -= 1

    def _fail(self, code):
        self.done = code
        self.cur = self.inp
        return ERRORTOKEN, None, None

    def _token(self, kind):
        return kind, self.start, self.cur

    def _mark(self, offset):
        """Record where the token starts, `offset` characters before cur."""
        self.start = self.cur - offset
        self.start_lineno = self.lineno
        self.start_col = self.start - self.line_start

    # tok_get
    def get(self):
        """(type, start offset or None, end offset or None) of the next token."""
        while True:
            self.start = None
            blankline = False
            if self.atbol:
                blankline, result = self._indentation()
                if result is not None:
                    return result
            self.start = self.cur
            if self.pendin:
                return self._pending()
            result = self._token_after_spaces(blankline)
            if result is not None:
                return result

    def _indentation(self):
        self.atbol = False
        col = col8 = altcol = 0
        while True:
            c = self.nextc()
            if c == " ":
                col += 1
                col8 += 1
                altcol += 1
            elif c == "\t":
                col = (col // self.tabsize + 1) * self.tabsize
                col8 = (col8 // TABSIZE + 1) * TABSIZE
                altcol += 1
            elif c == "\f":
                col = col8 = altcol = 0
            else:
                break
        self.backup(c)
        blankline = c in ("#", "\n")
        if blankline or self.level:
            return blankline, None
        self.indents.append((self.lineno, col8, altcol, col))
        return False, self._new_indent(col, altcol)

    def _new_indent(self, col, altcol):
        if col == self.indstack[self.indent]:
            return None
        if col > self.indstack[self.indent]:
            if self.indent + 1 >= MAXINDENT:
                return self._fail(E_TOODEEP)
            self.pendin += 1
            self.indent += 1
            del self.indstack[self.indent:], self.altindstack[self.indent:]
            self.indstack.append(col)
            self.altindstack.append(altcol)
            return None
        while self.indent > 0 and col < self.indstack[self.indent]:
            self.pendin -= 1
            self.indent -= 1
        if col != self.indstack[self.indent]:
            return self._fail(E_DEDENT)
        return None

    def _pending(self):
        if self.pendin < 0:
            self.pendin += 1
            return DEDENT, None, None
        self.pendin -= 1
        return INDENT, None, None

    def _token_after_spaces(self, blankline):
        """The token after spaces and a comment; None to read the next line."""
        while True:
            self.start = None
            c = self.nextc()
            if c in " \t\f" and c:
                self.cur = _SPACES.match(self.buf, self.cur).end()
                c = self.nextc()
            self._mark(1)
            if c == "#":
                c = self._comment()
            if c == EOF:
                return (ENDMARKER, None, None) if self.done == E_EOF else (ERRORTOKEN, None, None)
            if c == "\\":
                if self._continuation():
                    continue
                return ERRORTOKEN, None, None
            return self._token_at(c, blankline)

    def _comment(self):
        end = self.buf.find("\n", self.cur)
        if end < 0:
            end = len(self.buf)
        self._tab_magic(self.buf[self.cur:min(end + 1, self.cur + 79)])
        self.cur = end
        return self.nextc()

    def _tab_magic(self, text):
        for form in _TAB_FORMS:
            at = text.find(form)
            if at >= 0:
                size = _atoi(text, at + len(form))
                if 1 <= size <= 40:
                    self.tabsize = size
                    self.tab_magic = True

    def _continuation(self):
        c = self.nextc()
        if c != "\n":
            self.done = E_LINECONT
            self.cur = self.inp
            return False
        self.continuation = self.cur - 2
        return True

    def _token_at(self, c, blankline):
        if c in _NAME_START:
            return self._name()
        if c == "\n":
            self.atbol = True
            if blankline or self.level > 0:
                return None
            return NEWLINE, self.start, self.cur - 1
        if c == ".":
            if self.cur < self.inp and self.buf[self.cur] in _DIGITS:
                return self._number(self._fraction(self.cur + 1))
            return self._token(ONE_CHAR["."])
        if c in _DIGITS:
            return self._number(self._number_end(c))
        if c in "'\"":
            return self._string(c)
        return self._operator(c)

    def _name(self):
        prefix = _STRING_PREFIX.match(self.buf, self.start)
        if prefix:
            self.cur = prefix.end() + 1
            return self._string(self.buf[prefix.end()])
        self.cur = _NAME_REST.match(self.buf, self.cur).end()
        return self._token(NAME)

    # Numbers: the result of each step is (end offset, or None for "invalid token").
    def _number(self, end):
        if end is None:
            return ERRORTOKEN, None, None
        self.cur = end
        return self._token(NUMBER)

    def _number_end(self, c):
        pos = self.cur
        if c != "0":
            pos = _DECIMALS.match(self.buf, pos).end()
            if self.buf[pos] in "lL":
                return pos + 1
            return self._fraction_or_exponent(pos)
        c = self.buf[pos]
        if c == ".":
            return self._fraction(pos + 1)
        if c in "jJ":
            return pos + 1
        if c in "xXoObB":
            return self._radix(c.lower(), pos + 1)
        return self._octal(pos)

    def _radix(self, kind, pos):
        end = _RADIX[kind].match(self.buf, pos).end()
        if end == pos:
            return self._invalid(pos)
        return end + 1 if self.buf[end] in "lL" else end

    def _octal(self, pos):
        pos = _OCTALS.match(self.buf, pos).end()
        decimal_end = _DECIMALS.match(self.buf, pos).end()
        c = self.buf[decimal_end]
        if c == ".":
            return self._fraction(decimal_end + 1)
        if c in "eE":
            return self._exponent(decimal_end)
        if c in "jJ":
            return decimal_end + 1
        if decimal_end != pos:
            return self._invalid(decimal_end)
        return pos + 1 if c in "lL" else pos

    def _fraction_or_exponent(self, pos):
        if self.buf[pos] == ".":
            return self._fraction(pos + 1)
        return self._exponent_or_imaginary(pos)

    def _fraction(self, pos):
        return self._exponent_or_imaginary(_DECIMALS.match(self.buf, pos).end())

    def _exponent_or_imaginary(self, pos):
        if self.buf[pos] in "eE":
            return self._exponent(pos)
        return pos + 1 if self.buf[pos] in "jJ" else pos

    def _exponent(self, pos):
        digits = pos + 1
        if self.buf[digits] in "+-":
            digits += 1
            if self.buf[digits] not in _DIGITS:
                return self._invalid(digits)
        elif self.buf[digits] not in _DIGITS:
            return pos  # "1e" is the number 1 and the name e
        end = _DECIMALS.match(self.buf, digits).end()
        return end + 1 if self.buf[end] in "jJ" else end

    def _invalid(self, pos):
        self.done = E_TOKEN
        self.cur = pos
        return None

    def _string(self, quote):
        body = self.cur
        if self.buf.startswith(quote * 2, body):
            return self._triple_string(quote, body + 2)
        end = _BODY[quote].match(self.buf, body).end()
        self._count_lines(body, min(end + 1, len(self.buf)))
        if end >= len(self.buf):
            return self._fail(E_EOLS)
        if self.buf[end] == "\n":
            self.done = E_EOLS
            self.cur = end
            return ERRORTOKEN, None, None
        self.cur = end + 1
        return self._token(STRING)

    def _triple_string(self, quote, body):
        end = _TRIPLE_BODY[quote].match(self.buf, body).end()
        if not self.buf.startswith(quote * 3, end):
            self._count_lines(body, len(self.buf))
            return self._fail(E_EOFS)
        self.cur = end + 3
        self._count_lines(body, self.cur)
        return self._token(STRING)

    def _count_lines(self, begin, end):
        """Move the line bookkeeping over the newlines a string spans, as tok_nextc would:
        a line starts when a character after a newline is read."""
        newline = self.buf.find("\n", begin, end)
        while newline >= 0 and newline + 1 < end:
            self.lineno += 1
            self.line_start = newline + 1
            next_newline = self.buf.find("\n", newline + 1)
            self.inp = next_newline + 1 if next_newline >= 0 else len(self.buf)
            newline = self.buf.find("\n", newline + 1, end)

    def _operator(self, c):
        two = self.buf[self.start:self.start + 2]
        if two in TWO_CHARS:
            three = self.buf[self.start:self.start + 3]
            if three in THREE_CHARS:
                self.cur = self.start + 3
                return self._token(THREE_CHARS[three])
            self.cur = self.start + 2
            return self._token(TWO_CHARS[two])
        if c in "([{":
            self.level += 1
        elif c in ")]}":
            self.level -= 1
        return self._token(ONE_CHAR.get(c, OP))
