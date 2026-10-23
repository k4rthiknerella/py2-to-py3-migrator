# -*- coding: utf-8 -*-
"""Python 2.7's grammar, and the parse tables pgen builds from it.

GRAMMAR is CPython 2.7's Grammar/Grammar, rules unchanged. The table builder
follows Parser/pgen.c: each rule becomes an NFA, then a DFA by subset
construction, then the FIRST sets and the accelerators Parser/acceler.c adds.
Nonterminals are numbered from 256 in the order the rules appear, so the
numbers are 2.7's symbol module's. Token numbers are Include/token.h's.

Copyright (c) 2001-2020 Python Software Foundation; All Rights Reserved.
Used under the PSF License Agreement, version 2, in PSF-LICENSE.txt.
"""
import re

# Include/token.h
(ENDMARKER, NAME, NUMBER, STRING, NEWLINE, INDENT, DEDENT, LPAR, RPAR, LSQB, RSQB, COLON, COMMA,
 SEMI, PLUS, MINUS, STAR, SLASH, VBAR, AMPER, LESS, GREATER, EQUAL, DOT, PERCENT, BACKQUOTE,
 LBRACE, RBRACE, EQEQUAL, NOTEQUAL, LESSEQUAL, GREATEREQUAL, TILDE, CIRCUMFLEX, LEFTSHIFT,
 RIGHTSHIFT, DOUBLESTAR, PLUSEQUAL, MINEQUAL, STAREQUAL, SLASHEQUAL, PERCENTEQUAL, AMPEREQUAL,
 VBAREQUAL, CIRCUMFLEXEQUAL, LEFTSHIFTEQUAL, RIGHTSHIFTEQUAL, DOUBLESTAREQUAL, DOUBLESLASH,
 DOUBLESLASHEQUAL, AT, OP, ERRORTOKEN) = range(53)
N_TOKENS = 53
NT_OFFSET = 256

# Parser/tokenizer.c PyToken_OneChar, PyToken_TwoChars and PyToken_ThreeChars
ONE_CHAR = {
    "(": LPAR, ")": RPAR, "[": LSQB, "]": RSQB, ":": COLON, ",": COMMA, ";": SEMI, "+": PLUS,
    "-": MINUS, "*": STAR, "/": SLASH, "|": VBAR, "&": AMPER, "<": LESS, ">": GREATER, "=": EQUAL,
    ".": DOT, "%": PERCENT, "`": BACKQUOTE, "{": LBRACE, "}": RBRACE, "^": CIRCUMFLEX, "~": TILDE,
    "@": AT,
}
TWO_CHARS = {
    "==": EQEQUAL, "!=": NOTEQUAL, "<>": NOTEQUAL, "<=": LESSEQUAL, "<<": LEFTSHIFT,
    ">=": GREATEREQUAL, ">>": RIGHTSHIFT, "+=": PLUSEQUAL, "-=": MINEQUAL, "**": DOUBLESTAR,
    "*=": STAREQUAL, "//": DOUBLESLASH, "/=": SLASHEQUAL, "|=": VBAREQUAL, "%=": PERCENTEQUAL,
    "&=": AMPEREQUAL, "^=": CIRCUMFLEXEQUAL,
}
THREE_CHARS = {
    "<<=": LEFTSHIFTEQUAL, ">>=": RIGHTSHIFTEQUAL, "**=": DOUBLESTAREQUAL, "//=": DOUBLESLASHEQUAL,
}

GRAMMAR = """\
single_input: NEWLINE | simple_stmt | compound_stmt NEWLINE
file_input: (NEWLINE | stmt)* ENDMARKER
eval_input: testlist NEWLINE* ENDMARKER
decorator: '@' dotted_name [ '(' [arglist] ')' ] NEWLINE
decorators: decorator+
decorated: decorators (classdef | funcdef)
funcdef: 'def' NAME parameters ':' suite
parameters: '(' [varargslist] ')'
varargslist: ((fpdef ['=' test] ',')*
              ('*' NAME [',' '**' NAME] | '**' NAME) |
              fpdef ['=' test] (',' fpdef ['=' test])* [','])
fpdef: NAME | '(' fplist ')'
fplist: fpdef (',' fpdef)* [',']
stmt: simple_stmt | compound_stmt
simple_stmt: small_stmt (';' small_stmt)* [';'] NEWLINE
small_stmt: (expr_stmt | print_stmt  | del_stmt | pass_stmt | flow_stmt |
             import_stmt | global_stmt | exec_stmt | assert_stmt)
expr_stmt: testlist (augassign (yield_expr|testlist) |
                     ('=' (yield_expr|testlist))*)
augassign: ('+=' | '-=' | '*=' | '/=' | '%=' | '&=' | '|=' | '^=' |
            '<<=' | '>>=' | '**=' | '//=')
print_stmt: 'print' ( [ test (',' test)* [','] ] |
                      '>>' test [ (',' test)+ [','] ] )
del_stmt: 'del' exprlist
pass_stmt: 'pass'
flow_stmt: break_stmt | continue_stmt | return_stmt | raise_stmt | yield_stmt
break_stmt: 'break'
continue_stmt: 'continue'
return_stmt: 'return' [testlist]
yield_stmt: yield_expr
raise_stmt: 'raise' [test [',' test [',' test]]]
import_stmt: import_name | import_from
import_name: 'import' dotted_as_names
import_from: ('from' ('.'* dotted_name | '.'+)
              'import' ('*' | '(' import_as_names ')' | import_as_names))
import_as_name: NAME ['as' NAME]
dotted_as_name: dotted_name ['as' NAME]
import_as_names: import_as_name (',' import_as_name)* [',']
dotted_as_names: dotted_as_name (',' dotted_as_name)*
dotted_name: NAME ('.' NAME)*
global_stmt: 'global' NAME (',' NAME)*
exec_stmt: 'exec' expr ['in' test [',' test]]
assert_stmt: 'assert' test [',' test]
compound_stmt: if_stmt | while_stmt | for_stmt | try_stmt | with_stmt | funcdef | classdef | decorated
if_stmt: 'if' test ':' suite ('elif' test ':' suite)* ['else' ':' suite]
while_stmt: 'while' test ':' suite ['else' ':' suite]
for_stmt: 'for' exprlist 'in' testlist ':' suite ['else' ':' suite]
try_stmt: ('try' ':' suite
           ((except_clause ':' suite)+
            ['else' ':' suite]
            ['finally' ':' suite] |
           'finally' ':' suite))
with_stmt: 'with' with_item (',' with_item)*  ':' suite
with_item: test ['as' expr]
except_clause: 'except' [test [('as' | ',') test]]
suite: simple_stmt | NEWLINE INDENT stmt+ DEDENT
testlist_safe: old_test [(',' old_test)+ [',']]
old_test: or_test | old_lambdef
old_lambdef: 'lambda' [varargslist] ':' old_test
test: or_test ['if' or_test 'else' test] | lambdef
or_test: and_test ('or' and_test)*
and_test: not_test ('and' not_test)*
not_test: 'not' not_test | comparison
comparison: expr (comp_op expr)*
comp_op: '<'|'>'|'=='|'>='|'<='|'<>'|'!='|'in'|'not' 'in'|'is'|'is' 'not'
expr: xor_expr ('|' xor_expr)*
xor_expr: and_expr ('^' and_expr)*
and_expr: shift_expr ('&' shift_expr)*
shift_expr: arith_expr (('<<'|'>>') arith_expr)*
arith_expr: term (('+'|'-') term)*
term: factor (('*'|'/'|'%'|'//') factor)*
factor: ('+'|'-'|'~') factor | power
power: atom trailer* ['**' factor]
atom: ('(' [yield_expr|testlist_comp] ')' |
       '[' [listmaker] ']' |
       '{' [dictorsetmaker] '}' |
       '`' testlist1 '`' |
       NAME | NUMBER | STRING+)
listmaker: test ( list_for | (',' test)* [','] )
testlist_comp: test ( comp_for | (',' test)* [','] )
lambdef: 'lambda' [varargslist] ':' test
trailer: '(' [arglist] ')' | '[' subscriptlist ']' | '.' NAME
subscriptlist: subscript (',' subscript)* [',']
subscript: '.' '.' '.' | test | [test] ':' [test] [sliceop]
sliceop: ':' [test]
exprlist: expr (',' expr)* [',']
testlist: test (',' test)* [',']
dictorsetmaker: ( (test ':' test (comp_for | (',' test ':' test)* [','])) |
                  (test (comp_for | (',' test)* [','])) )
classdef: 'class' NAME ['(' [testlist] ')'] ':' suite
arglist: (argument ',')* (argument [',']
                         |'*' test (',' argument)* [',' '**' test]
                         |'**' test)
argument: test [comp_for] | test '=' test
list_iter: list_for | list_if
list_for: 'for' exprlist 'in' testlist_safe [list_iter]
list_if: 'if' old_test [list_iter]
comp_iter: comp_for | comp_if
comp_for: 'for' exprlist 'in' or_test [comp_iter]
comp_if: 'if' old_test [comp_iter]
testlist1: test (',' test)*
encoding_decl: NAME
yield_expr: 'yield' [testlist]
"""

_TOKEN_NAMES = {"ENDMARKER": ENDMARKER, "NAME": NAME, "NUMBER": NUMBER, "STRING": STRING,
                "NEWLINE": NEWLINE, "INDENT": INDENT, "DEDENT": DEDENT}
_META = re.compile(r"\s*(?:([A-Za-z_][A-Za-z0-9_]*)|'([^']*)'|([:|()\[\]*+]))")


class _NFAState(object):
    def __init__(self):
        self.arcs = []  # (label or None for an empty arc, _NFAState)


class _MetaParser(object):
    """Grammar text to one NFA per rule (Parser/metagrammar.c's language)."""

    def __init__(self, text):
        self.tokens = []
        pos = 0
        text = text.rstrip()
        while pos < len(text):
            match = _META.match(text, pos)
            if not match:
                raise ValueError("grammar: cannot read %r" % text[pos:pos + 20])
            self.tokens.append(match.groups(""))
            pos = match.end()
        self.pos = 0

    def rules(self):
        while self.pos < len(self.tokens):
            name = self.tokens[self.pos][0]
            self.pos += 1
            self._expect(":")
            start, end = self._rhs()
            yield name, start, end

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ("", "", "")

    def _expect(self, op):
        if self._peek()[2] != op:
            raise ValueError("grammar: expected %r at token %d" % (op, self.pos))
        self.pos += 1

    def _rhs(self):
        start, end = self._alt()
        if self._peek()[2] != "|":
            return start, end
        first, last = _NFAState(), _NFAState()
        first.arcs.append((None, start))
        end.arcs.append((None, last))
        while self._peek()[2] == "|":
            self.pos += 1
            start, end = self._alt()
            first.arcs.append((None, start))
            end.arcs.append((None, last))
        return first, last

    def _alt(self):
        start, end = self._item()
        while self._at_item():
            nxt, nend = self._item()
            end.arcs.append((None, nxt))
            end = nend
        return start, end

    def _at_item(self):
        if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1][2] == ":":
            return False  # the next token names the next rule
        name, string, op = self._peek()
        return bool(name or string or op in ("(", "["))

    def _item(self):
        if self._peek()[2] == "[":
            self.pos += 1
            start, end = self._rhs()
            self._expect("]")
            start.arcs.append((None, end))
            return start, end
        start, end = self._atom()
        op = self._peek()[2]
        if op == "+":
            self.pos += 1
            end.arcs.append((None, start))
        elif op == "*":
            self.pos += 1
            end.arcs.append((None, start))
            return start, start
        return start, end

    def _atom(self):
        name, string, op = self._peek()
        self.pos += 1
        if op == "(":
            start, end = self._rhs()
            self._expect(")")
            return start, end
        start, end = _NFAState(), _NFAState()
        start.arcs.append((name or "'%s'" % string, end))
        return start, end


def _closure(state, into):
    stack = [state]
    while stack:
        s = stack.pop()
        if s not in into:
            into.add(s)
            stack.extend(nxt for label, nxt in s.arcs if label is None)
    return into


def _make_dfa(start, finish):
    """Subset construction, then Parser/pgen.c's simplify(): states as [arcs, is_final]."""
    sets = [frozenset(_closure(start, set()))]
    arcs = []
    i = 0
    while i < len(sets):
        moves = {}
        order = []
        for nfa_state in sets[i]:
            for label, nxt in nfa_state.arcs:
                if label is not None:
                    if label not in moves:
                        moves[label] = set()
                        order.append(label)
                    _closure(nxt, moves[label])
        state_arcs = {}
        for label in sorted(order):
            target = frozenset(moves[label])
            if target not in sets:
                sets.append(target)
            state_arcs[label] = sets.index(target)
        arcs.append(state_arcs)
        i += 1
    finals = [finish in s for s in sets]
    return _simplify(arcs, finals)


def _simplify(arcs, finals):
    alive = list(range(len(arcs)))
    changed = True
    while changed:
        changed = False
        for i in alive[1:]:
            for j in alive:
                if j >= i:
                    break
                if finals[i] == finals[j] and arcs[i] == arcs[j]:
                    alive.remove(i)
                    for state_arcs in arcs:
                        for label, target in state_arcs.items():
                            if target == i:
                                state_arcs[label] = j
                    changed = True
                    break
    renumber = dict((old, new) for new, old in enumerate(alive))
    return [(dict((label, renumber[t]) for label, t in arcs[old].items()), finals[old]) for old in alive]


class Grammar(object):
    """Parse tables: symbol numbers, labels, DFAs with FIRST sets and accelerators.

    labels[i] is (type, keyword or None). dfas[symbol] is a list of states;
    a state is (accel, is_final, accept_only), where accel maps a label index
    to the next state (shift) or to (symbol, next state) (push).
    """

    def __init__(self, text=GRAMMAR):
        rules = list(_MetaParser(text).rules())
        self.symbols = dict((name, NT_OFFSET + i) for i, (name, _, _) in enumerate(rules))
        self.names = dict((number, name) for name, number in self.symbols.items())
        self.start = self.symbols["file_input"]
        self.labels = [(0, "EMPTY")]
        self._label_index = {}
        self._dfa_labels = {}
        for name, start, end in rules:
            self._dfa_labels[self.symbols[name]] = [
                (dict((self._label(label), target) for label, target in sorted(arcs.items())), final)
                for arcs, final in _make_dfa(start, end)]
        self.keywords = dict((kw, i) for i, (kind, kw) in enumerate(self.labels) if kind == NAME and kw)
        self.token_labels = dict((kind, i) for i, (kind, kw) in enumerate(self.labels)
                                 if kw is None and kind < NT_OFFSET)
        self.first = {}
        for symbol in sorted(self._dfa_labels):
            self._first_set(symbol)
        self.dfas = dict((symbol, [self._accelerate(arcs, final) for arcs, final in states])
                         for symbol, states in self._dfa_labels.items())

    def _label(self, text):
        if text not in self._label_index:
            self._label_index[text] = len(self.labels)
            self.labels.append(self._label_value(text))
        return self._label_index[text]

    def _label_value(self, text):
        if text in self.symbols:
            return (self.symbols[text], None)
        if text in _TOKEN_NAMES:
            return (_TOKEN_NAMES[text], None)
        value = text[1:-1]
        if value[0].isalpha():
            return (NAME, value)
        return (THREE_CHARS.get(value) or TWO_CHARS.get(value) or ONE_CHAR[value], None)

    def _first_set(self, symbol, active=()):
        if symbol in self.first:
            return self.first[symbol]
        if symbol in active:
            raise ValueError("grammar: left recursion in %s" % self.names[symbol])
        result = {}
        for label in self._dfa_labels[symbol][0][0]:
            kind = self.labels[label][0]
            members = self._first_set(kind, active + (symbol,)) if kind >= NT_OFFSET else [label]
            for member in members:
                if member in result:
                    raise ValueError("grammar: %s is not LL(1)" % self.names[symbol])
                result[member] = label
        self.first[symbol] = result
        return result

    def _accelerate(self, arcs, final):
        accel = {}
        for label, target in arcs.items():
            kind = self.labels[label][0]
            if kind >= NT_OFFSET:
                for member in self.first[kind]:
                    accel[member] = (kind, target)
            else:
                accel[label] = target
        return accel, final, final and not arcs


_GRAMMAR = []


def grammar():
    """The 2.7 grammar's tables, built once per process."""
    if not _GRAMMAR:
        _GRAMMAR.append(Grammar())
    return _GRAMMAR[0]
