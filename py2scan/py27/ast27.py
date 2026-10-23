# -*- coding: utf-8 -*-
"""Python 2.7's abstract syntax tree, built from the CST as Python/ast.c builds it.

parse(source) returns what Python 2.7's ast.parse(source) returns, as this
module's node classes (Parser/Python.asdl), or raises Py27SyntaxError with the
exception, message and line 2.7 would report. Two values differ in form: Num.n
is the literal's text (with a leading "-" when ast.c folds a unary minus into
it), since converting long literals is limited on Python 3.11 and later; and
identifiers are native str on both interpreters. Byte strings are bytes and
unicode strings are text, on either.

The functions keep ast.c's names and its order of evaluation, which decides
which error a file with several reports.

Copyright (c) 2001-2020 Python Software Foundation; All Rights Reserved.
Used under the PSF License Agreement, version 2, in PSF-LICENSE.txt.
"""
import sys

from py2scan.py27 import codecs27, registry27
from py2scan.py27.grammar import (
    AMPER, BACKQUOTE, CIRCUMFLEX, COLON, COMMA, DOT, DOUBLESLASH, DOUBLESTAR, EQEQUAL, EQUAL, GREATER,
    GREATEREQUAL, LBRACE, LEFTSHIFT, LESS, LESSEQUAL, LPAR, LSQB, MINUS, NAME, NEWLINE, NOTEQUAL,
    NUMBER, PERCENT, PLUS, RBRACE, RIGHTSHIFT, RPAR, RSQB, SEMI, SLASH, STAR, STRING, VBAR)
from py2scan.py27.parser import CO_FUTURE_UNICODE_LITERALS, Py27SyntaxError, parse_cst
from py2scan.py27.symbol import (
    and_expr, and_test, atom, argument, arith_expr, assert_stmt, augassign, break_stmt, classdef,
    comp_for, comp_if, comparison, compound_stmt, continue_stmt, decorated, del_stmt,
    dotted_as_name, dotted_name, except_clause, exec_stmt, expr, expr_stmt, factor, file_input,
    flow_stmt, for_stmt, fpdef, funcdef, global_stmt, if_stmt, import_as_name, import_name,
    import_stmt, lambdef, list_if, not_test, old_lambdef, old_test, or_test, parameters, pass_stmt,
    power, print_stmt, return_stmt, shift_expr, simple_stmt, single_input, sliceop, small_stmt,
    stmt, suite, term, test, testlist, trailer, try_stmt, while_stmt, with_stmt, xor_expr,
    yield_expr, yield_stmt)

text_type = type(u"")
PY2 = sys.version_info[0] == 2
# Deep enough for the deepest CST the parser accepts (MAXSTACK 1500 nested
# nonterminals, such as 1500 nested "not"), at about two frames a level.
RECURSION_LIMIT = 10000


class AST(object):
    _fields = ()
    _attributes = ()

    def __init__(self, *args, **kwargs):
        for name, value in zip(self._fields + self._attributes, args):
            setattr(self, name, value)
        for name, value in kwargs.items():
            setattr(self, name, value)


_POS = ("lineno", "col_offset")


class mod(AST):
    pass


class Module(mod):
    _fields = ("body",)


class Interactive(mod):
    _fields = ("body",)


class Expression(mod):
    _fields = ("body",)


class Suite(mod):
    _fields = ("body",)


class stmt_(AST):
    _attributes = _POS


class FunctionDef(stmt_):
    _fields = ("name", "args", "body", "decorator_list")


class ClassDef(stmt_):
    _fields = ("name", "bases", "body", "decorator_list")


class Return(stmt_):
    _fields = ("value",)


class Delete(stmt_):
    _fields = ("targets",)


class Assign(stmt_):
    _fields = ("targets", "value")


class AugAssign(stmt_):
    _fields = ("target", "op", "value")


class Print(stmt_):
    _fields = ("dest", "values", "nl")


class For(stmt_):
    _fields = ("target", "iter", "body", "orelse")


class While(stmt_):
    _fields = ("test", "body", "orelse")


class If(stmt_):
    _fields = ("test", "body", "orelse")


class With(stmt_):
    _fields = ("context_expr", "optional_vars", "body")


class Raise(stmt_):
    _fields = ("type", "inst", "tback")


class TryExcept(stmt_):
    _fields = ("body", "handlers", "orelse")


class TryFinally(stmt_):
    _fields = ("body", "finalbody")


class Assert(stmt_):
    _fields = ("test", "msg")


class Import(stmt_):
    _fields = ("names",)


class ImportFrom(stmt_):
    _fields = ("module", "names", "level")


class Exec(stmt_):
    _fields = ("body", "globals", "locals")


class Global(stmt_):
    _fields = ("names",)


class Expr(stmt_):
    _fields = ("value",)


class Pass(stmt_):
    pass


class Break(stmt_):
    pass


class Continue(stmt_):
    pass


class expr_(AST):
    _attributes = _POS


class BoolOp(expr_):
    _fields = ("op", "values")


class BinOp(expr_):
    _fields = ("left", "op", "right")


class UnaryOp(expr_):
    _fields = ("op", "operand")


class Lambda(expr_):
    _fields = ("args", "body")


class IfExp(expr_):
    _fields = ("test", "body", "orelse")


class Dict(expr_):
    _fields = ("keys", "values")


class Set(expr_):
    _fields = ("elts",)


class ListComp(expr_):
    _fields = ("elt", "generators")


class SetComp(expr_):
    _fields = ("elt", "generators")


class DictComp(expr_):
    _fields = ("key", "value", "generators")


class GeneratorExp(expr_):
    _fields = ("elt", "generators")


class Yield(expr_):
    _fields = ("value",)


class Compare(expr_):
    _fields = ("left", "ops", "comparators")


class Call(expr_):
    _fields = ("func", "args", "keywords", "starargs", "kwargs")


class Repr(expr_):
    _fields = ("value",)


class Num(expr_):
    _fields = ("n",)


class Str(expr_):
    _fields = ("s",)


class Attribute(expr_):
    _fields = ("value", "attr", "ctx")


class Subscript(expr_):
    _fields = ("value", "slice", "ctx")


class Name(expr_):
    _fields = ("id", "ctx")


class List(expr_):
    _fields = ("elts", "ctx")


class Tuple(expr_):
    _fields = ("elts", "ctx")


class expr_context(AST):
    pass


class Load(expr_context):
    pass


class Store(expr_context):
    pass


class Del(expr_context):
    pass


class AugLoad(expr_context):
    pass


class AugStore(expr_context):
    pass


class Param(expr_context):
    pass


class slice_(AST):
    pass


class Ellipsis(slice_):
    pass


class Slice(slice_):
    _fields = ("lower", "upper", "step")


class ExtSlice(slice_):
    _fields = ("dims",)


class Index(slice_):
    _fields = ("value",)


class boolop(AST):
    pass


class And(boolop):
    pass


class Or(boolop):
    pass


class operator(AST):
    pass


class Add(operator):
    pass


class Sub(operator):
    pass


class Mult(operator):
    pass


class Div(operator):
    pass


class Mod(operator):
    pass


class Pow(operator):
    pass


class LShift(operator):
    pass


class RShift(operator):
    pass


class BitOr(operator):
    pass


class BitXor(operator):
    pass


class BitAnd(operator):
    pass


class FloorDiv(operator):
    pass


class unaryop(AST):
    pass


class Invert(unaryop):
    pass


class Not(unaryop):
    pass


class UAdd(unaryop):
    pass


class USub(unaryop):
    pass


class cmpop(AST):
    pass


class Eq(cmpop):
    pass


class NotEq(cmpop):
    pass


class Lt(cmpop):
    pass


class LtE(cmpop):
    pass


class Gt(cmpop):
    pass


class GtE(cmpop):
    pass


class Is(cmpop):
    pass


class IsNot(cmpop):
    pass


class In(cmpop):
    pass


class NotIn(cmpop):
    pass


class comprehension(AST):
    _fields = ("target", "iter", "ifs")


class excepthandler(AST):
    _attributes = _POS


class ExceptHandler(excepthandler):
    _fields = ("type", "name", "body")


class arguments(AST):
    _fields = ("args", "vararg", "kwarg", "defaults")


class keyword(AST):
    _fields = ("arg", "value")


class alias(AST):
    _fields = ("name", "asname")


# The ASDL's names for the abstract classes (stmt and expr are also grammar
# symbols here, so the classes carry a trailing underscore).
stmt_.__name__, expr_.__name__, slice_.__name__ = "stmt", "expr", "slice"

LOAD, STORE, DEL, PARAM = Load(), Store(), Del(), Param()
_OPERATORS = {
    VBAR: BitOr, CIRCUMFLEX: BitXor, AMPER: BitAnd, LEFTSHIFT: LShift, RIGHTSHIFT: RShift,
    PLUS: Add, MINUS: Sub, STAR: Mult, SLASH: Div, DOUBLESLASH: FloorDiv, PERCENT: Mod,
}
_AUGMENTED = {"+": Add, "-": Sub, "%": Mod, "<": LShift, ">": RShift, "&": BitAnd, "^": BitXor,
              "|": BitOr}
_COMPARISONS = {LESS: Lt, GREATER: Gt, EQEQUAL: Eq, LESSEQUAL: LtE, GREATEREQUAL: GtE,
                NOTEQUAL: NotEq}
_UNASSIGNABLE = {
    Lambda: "lambda", Call: "function call", BoolOp: "operator", BinOp: "operator",
    UnaryOp: "operator", GeneratorExp: "generator expression", Yield: "yield expression",
    ListComp: "list comprehension", SetComp: "set comprehension", DictComp: "dict comprehension",
    Dict: "literal", Set: "literal", Num: "literal", Str: "literal", Compare: "comparison",
    Repr: "repr", IfExp: "conditional expression",
}


def _nch(n):
    return len(n.children) if n.children is not None else 0


def _identifier(n):
    """NEW_IDENTIFIER: a NAME token's text as a native str (2.7 names are ASCII)."""
    return str(n.value) if PY2 else n.value


def _error(n, msg):
    """ast_error: a SyntaxError at the CST node's line."""
    return Py27SyntaxError(msg, n.lineno)


def _num_stmts(n):
    kind = n.type
    if kind == single_input:
        return 0 if n.children[0].type == NEWLINE else _num_stmts(n.children[0])
    if kind == file_input:
        return sum(_num_stmts(ch) for ch in n.children if ch.type == stmt)
    if kind == stmt:
        return _num_stmts(n.children[0])
    if kind == compound_stmt:
        return 1
    if kind == simple_stmt:
        return len(n.children) // 2
    if kind == suite:
        if len(n.children) == 1:
            return _num_stmts(n.children[0])
        return sum(_num_stmts(ch) for ch in n.children[2:-1])
    raise AssertionError("Non-statement found: %d %d" % (kind, _nch(n)))


class _Builder(object):
    """struct compiling: the declared encoding and the unicode_literals flag."""

    def __init__(self, encoding, future_unicode):
        self.encoding = encoding
        self.future_unicode = future_unicode

    # PyAST_FromNode

    def module(self, n):
        body = []
        for ch in n.children[:-1]:
            if ch.type == NEWLINE:
                continue
            if _num_stmts(ch) == 1:
                body.append(self.ast_for_stmt(ch))
            else:
                ch = ch.children[0]
                for j in range(_num_stmts(ch)):
                    body.append(self.ast_for_stmt(ch.children[j * 2]))
        return Module(body)

    # Assignment targets

    def forbidden_check(self, n, name):
        if name == "None":
            raise _error(n, "cannot assign to None")
        if name == "__debug__":
            raise _error(n, "cannot assign to __debug__")

    def set_context(self, e, ctx, n):
        kind = e.__class__
        elts = None
        if kind is Attribute:
            if ctx is STORE:
                self.forbidden_check(n, e.attr)
            e.ctx = ctx
        elif kind is Subscript:
            e.ctx = ctx
        elif kind is Name:
            if ctx is STORE:
                self.forbidden_check(n, e.id)
            e.ctx = ctx
        elif kind is List:
            e.ctx = ctx
            elts = e.elts
        elif kind is Tuple:
            if not e.elts:
                raise _error(n, "can't %s ()" % ("assign to" if ctx is STORE else "delete"))
            e.ctx = ctx
            elts = e.elts
        else:
            raise _error(n, "can't %s %s" % ("assign to" if ctx is STORE else "delete", _UNASSIGNABLE[kind]))
        for elt in elts or ():
            self.set_context(elt, ctx, n)

    def ast_for_augassign(self, n):
        text = n.children[0].value
        if text[0] == "/":
            return FloorDiv() if text[1] == "/" else Div()
        if text[0] == "*":
            return Pow() if text[1] == "*" else Mult()
        return _AUGMENTED[text[0]]()

    def ast_for_comp_op(self, n):
        if len(n.children) == 1:
            ch = n.children[0]
            if ch.type == NAME:
                return In() if ch.value == "in" else Is()
            return _COMPARISONS[ch.type]()
        return NotIn() if n.children[1].value == "in" else IsNot()

    def seq_for_testlist(self, n):
        return [self.ast_for_expr(n.children[i]) for i in range(0, len(n.children), 2)]

    # Function definitions

    def compiler_complex_args(self, n):
        args = []
        for i in range((len(n.children) + 1) // 2):
            fpdef_node = n.children[2 * i]
            while True:
                child = fpdef_node.children[0]
                if child.type == NAME:
                    self.forbidden_check(n, child.value)
                    arg = Name(_identifier(child), STORE, child.lineno, child.col)
                    break
                child = fpdef_node.children[1]
                if len(child.children) == 1:
                    fpdef_node = child.children[0]
                    continue
                arg = self.compiler_complex_args(child)
                break
            args.append(arg)
        result = Tuple(args, STORE, n.lineno, n.col)
        self.set_context(result, STORE, n)
        return result

    def ast_for_arguments(self, n):
        if n.type == parameters:
            if len(n.children) == 2:
                return arguments([], None, None, [])
            n = n.children[1]
        children = n.children
        args, defaults = [], []
        vararg = kwarg = None
        found_default = False
        i = 0
        while i < len(children):
            ch = children[i]
            if ch.type == fpdef:
                i, found_default = self._fpdef(n, ch, i, args, defaults, found_default)
            elif ch.type == STAR:
                self.forbidden_check(children[i + 1], children[i + 1].value)
                vararg = _identifier(children[i + 1])
                i += 3
            else:  # DOUBLESTAR
                self.forbidden_check(children[i + 1], children[i + 1].value)
                kwarg = _identifier(children[i + 1])
                i += 3
        return arguments(args, vararg, kwarg, defaults)

    def _fpdef(self, n, ch, i, args, defaults, found_default):
        """handle_fpdef, which ast.c re-enters after each pair of parentheses
        around a single parameter, checking for a default again each time:
        (the index after the parameter, whether a default has been seen)."""
        children = n.children
        complex_args = parenthesized = False
        while True:
            if i + 1 < len(children) and children[i + 1].type == EQUAL:
                defaults.append(self.ast_for_expr(children[i + 2]))
                i += 2
                found_default = True
            elif found_default:
                if parenthesized and not complex_args:
                    raise _error(n, "parenthesized arg with default")
                raise _error(n, "non-default argument follows default argument")
            if len(ch.children) == 3:
                ch = ch.children[1]
                if len(ch.children) == 1:
                    parenthesized = True
                    ch = ch.children[0]
                    continue
                complex_args = True
                args.append(self.compiler_complex_args(ch))
            if ch.children[0].type == NAME:
                self.forbidden_check(n, ch.children[0].value)
                args.append(Name(_identifier(ch.children[0]), PARAM, ch.lineno, ch.col))
            return i + 2, found_default

    def ast_for_dotted_name(self, n):
        lineno, col = n.lineno, n.col
        e = Name(_identifier(n.children[0]), LOAD, lineno, col)
        for i in range(2, len(n.children), 2):
            e = Attribute(e, _identifier(n.children[i]), LOAD, lineno, col)
        return e

    def ast_for_decorator(self, n):
        name_expr = self.ast_for_dotted_name(n.children[1])
        if len(n.children) == 3:
            return name_expr
        if len(n.children) == 5:
            return Call(name_expr, [], [], None, None, name_expr.lineno, name_expr.col_offset)
        return self.ast_for_call(n.children[3], name_expr)

    def ast_for_decorators(self, n):
        return [self.ast_for_decorator(ch) for ch in n.children]

    def ast_for_funcdef(self, n, decorator_seq):
        name_node = n.children[1]
        name = _identifier(name_node)
        self.forbidden_check(name_node, name_node.value)
        args = self.ast_for_arguments(n.children[2])
        body = self.ast_for_suite(n.children[4])
        return FunctionDef(name, args, body, decorator_seq, n.lineno, n.col)

    def ast_for_decorated(self, n):
        decorator_seq = self.ast_for_decorators(n.children[0])
        if n.children[1].type == funcdef:
            thing = self.ast_for_funcdef(n.children[1], decorator_seq)
        else:
            thing = self.ast_for_classdef(n.children[1], decorator_seq)
        thing.lineno, thing.col_offset = n.lineno, n.col
        return thing

    def ast_for_lambdef(self, n):
        if len(n.children) == 3:
            args = arguments([], None, None, [])
            expression = self.ast_for_expr(n.children[2])
        else:
            args = self.ast_for_arguments(n.children[1])
            expression = self.ast_for_expr(n.children[3])
        return Lambda(args, expression, n.lineno, n.col)

    def ast_for_ifexpr(self, n):
        body = self.ast_for_expr(n.children[0])
        expression = self.ast_for_expr(n.children[2])
        orelse = self.ast_for_expr(n.children[4])
        return IfExp(expression, body, orelse, n.lineno, n.col)

    # Comprehensions

    def _generators(self, ch, iterable, if_type):
        """The comprehensions of a list_for or comp_for chain: per 'for', its
        target, then its iterable, then its 'if' tests."""
        generators = []
        while True:  # 'for' exprlist 'in' (testlist_safe | or_test) [list_iter | comp_iter]
            for_ch = ch.children[1]
            t = self.ast_for_exprlist(for_ch, STORE)
            expression = iterable(ch.children[3])
            first = t[0]
            # One child, not one element: "for x, in" still needs a Tuple.
            target = first if len(for_ch.children) == 1 else Tuple(t, STORE, first.lineno, first.col_offset)
            generator = comprehension(target, expression, [])
            generators.append(generator)
            if len(ch.children) != 5:
                return generators
            ch = ch.children[4].children[0]
            while ch.type == if_type:
                generator.ifs.append(self.ast_for_expr(ch.children[1]))
                if len(ch.children) != 3:
                    return generators
                ch = ch.children[2].children[0]

    def ast_for_listcomp(self, n):
        elt = self.ast_for_expr(n.children[0])
        generators = self._generators(n.children[1], self.ast_for_testlist, list_if)
        return ListComp(elt, generators, n.lineno, n.col)

    def ast_for_comprehension(self, n):
        return self._generators(n, self.ast_for_expr, comp_if)

    def ast_for_itercomp(self, n, kind):
        elt = self.ast_for_expr(n.children[0])
        comps = self.ast_for_comprehension(n.children[1])
        return kind(elt, comps, n.lineno, n.col)

    def ast_for_dictcomp(self, n):
        key = self.ast_for_expr(n.children[0])
        value = self.ast_for_expr(n.children[2])
        comps = self.ast_for_comprehension(n.children[3])
        return DictComp(key, value, comps, n.lineno, n.col)

    def ast_for_genexp(self, n):
        return self.ast_for_itercomp(n, GeneratorExp)

    # Atoms

    def ast_for_atom(self, n):
        return getattr(self, _ATOMS[n.children[0].type])(n)

    def _name(self, n):
        return Name(_identifier(n.children[0]), LOAD, n.lineno, n.col)

    def _string(self, n):
        try:
            value = self.parsestrplus(n)
        except codecs27.CodecError as e:
            raise _error(n, ("(unicode error) %s" % e.msg)[:127])
        return Str(value, n.lineno, n.col)

    def _number(self, n):
        return Num(_identifier(n.children[0]), n.lineno, n.col)

    def _parens(self, n):
        ch = n.children[1]
        if ch.type == RPAR:
            return Tuple([], LOAD, n.lineno, n.col)
        if ch.type == yield_expr:
            return self.ast_for_expr(ch)
        return self.ast_for_testlist_comp(ch)

    def _brackets(self, n):
        ch = n.children[1]
        if ch.type == RSQB:
            return List([], LOAD, n.lineno, n.col)
        if len(ch.children) == 1 or ch.children[1].type == COMMA:
            return List(self.seq_for_testlist(ch), LOAD, n.lineno, n.col)
        return self.ast_for_listcomp(ch)

    def _backquotes(self, n):
        return Repr(self.ast_for_testlist(n.children[1]), n.lineno, n.col)

    def _braces(self, n):
        ch = n.children[1]
        if ch.type == RBRACE:
            return Dict([], [], n.lineno, n.col)
        if len(ch.children) == 1 or ch.children[1].type == COMMA:
            return Set([self.ast_for_expr(ch.children[i]) for i in range(0, len(ch.children), 2)],
                       n.lineno, n.col)
        if ch.children[1].type == comp_for:
            return self.ast_for_itercomp(ch, SetComp)
        if len(ch.children) > 3 and ch.children[3].type == comp_for:
            return self.ast_for_dictcomp(ch)
        keys, values = [], []
        for i in range(0, len(ch.children), 4):
            keys.append(self.ast_for_expr(ch.children[i]))
            values.append(self.ast_for_expr(ch.children[i + 2]))
        return Dict(keys, values, n.lineno, n.col)

    def ast_for_slice(self, n):
        ch = n.children[0]
        if ch.type == DOT:
            return Ellipsis()
        if len(n.children) == 1 and ch.type == test:
            return Index(self.ast_for_expr(ch))
        lower = upper = step = None
        if ch.type == test:
            lower = self.ast_for_expr(ch)
        if ch.type == COLON:
            if len(n.children) > 1 and n.children[1].type == test:
                upper = self.ast_for_expr(n.children[1])
        elif len(n.children) > 2 and n.children[2].type == test:
            upper = self.ast_for_expr(n.children[2])
        ch = n.children[-1]
        if ch.type == sliceop:
            if len(ch.children) == 1:
                colon = ch.children[0]
                step = Name("None", LOAD, colon.lineno, colon.col)
            elif ch.children[1].type == test:
                step = self.ast_for_expr(ch.children[1])
        return Slice(lower, upper, step)

    def ast_for_binop(self, n):
        expr1 = self.ast_for_expr(n.children[0])
        expr2 = self.ast_for_expr(n.children[2])
        result = BinOp(expr1, _OPERATORS[n.children[1].type](), expr2, n.lineno, n.col)
        for i in range(1, (len(n.children) - 1) // 2):
            next_oper = n.children[i * 2 + 1]
            newoperator = _OPERATORS[next_oper.type]()
            tmp = self.ast_for_expr(n.children[i * 2 + 2])
            result = BinOp(result, newoperator, tmp, next_oper.lineno, next_oper.col)
        return result

    def ast_for_trailer(self, n, left_expr):
        first = n.children[0].type
        if first == LPAR:
            if len(n.children) == 2:
                return Call(left_expr, [], [], None, None, n.lineno, n.col)
            return self.ast_for_call(n.children[1], left_expr)
        if first == DOT:
            return Attribute(left_expr, _identifier(n.children[1]), LOAD, n.lineno, n.col)
        n = n.children[1]  # subscriptlist
        if len(n.children) == 1:
            return Subscript(left_expr, self.ast_for_slice(n.children[0]), LOAD, n.lineno, n.col)
        slices = [self.ast_for_slice(n.children[j]) for j in range(0, len(n.children), 2)]
        if any(s.__class__ is not Index for s in slices):
            return Subscript(left_expr, ExtSlice(slices), LOAD, n.lineno, n.col)
        e = Tuple([s.value for s in slices], LOAD, n.lineno, n.col)
        return Subscript(left_expr, Index(e), LOAD, n.lineno, n.col)

    def ast_for_factor(self, n):
        sign = n.children[0]
        if sign.type == MINUS and len(n.children) == 2:
            pfactor = n.children[1]
            if pfactor.type == factor and len(pfactor.children) == 1:
                ppower = pfactor.children[0]
                if ppower.type == power and len(ppower.children) == 1:
                    patom = ppower.children[0]
                    if patom.type == atom and patom.children[0].type == NUMBER:
                        return Num("-" + _identifier(patom.children[0]), n.lineno, n.col)
        expression = self.ast_for_expr(n.children[1])
        if sign.type == PLUS:
            return UnaryOp(UAdd(), expression, n.lineno, n.col)
        if sign.type == MINUS:
            return UnaryOp(USub(), expression, n.lineno, n.col)
        return UnaryOp(Invert(), expression, n.lineno, n.col)

    def ast_for_power(self, n):
        e = self.ast_for_atom(n.children[0])
        if len(n.children) == 1:
            return e
        for ch in n.children[1:]:
            if ch.type != trailer:
                break
            tmp = self.ast_for_trailer(ch, e)
            tmp.lineno, tmp.col_offset = e.lineno, e.col_offset
            e = tmp
        if n.children[-1].type == factor:
            f = self.ast_for_expr(n.children[-1])
            e = BinOp(e, Pow(), f, n.lineno, n.col)
        return e

    def ast_for_expr(self, n):
        while len(n.children) == 1 and n.type in _PASS_THROUGH:
            n = n.children[0]
        handler = _EXPRESSIONS.get(n.type)
        if handler is None:
            raise AssertionError("unhandled expr: %d" % n.type)
        return getattr(self, handler)(n)

    def _boolop(self, n):
        values = [self.ast_for_expr(n.children[i]) for i in range(0, len(n.children), 2)]
        op = And() if n.children[1].value == "and" else Or()
        return BoolOp(op, values, n.lineno, n.col)

    def _not(self, n):
        return UnaryOp(Not(), self.ast_for_expr(n.children[1]), n.lineno, n.col)

    def _compare(self, n):
        ops, cmps = [], []
        for i in range(1, len(n.children), 2):
            ops.append(self.ast_for_comp_op(n.children[i]))
            cmps.append(self.ast_for_expr(n.children[i + 1]))
        return Compare(self.ast_for_expr(n.children[0]), ops, cmps, n.lineno, n.col)

    def _yield(self, n):
        value = self.ast_for_testlist(n.children[1]) if len(n.children) == 2 else None
        return Yield(value, n.lineno, n.col)

    def ast_for_call(self, n, func):
        self._count_arguments(n)
        args, keywords = [], []
        vararg = kwarg = None
        i = 0
        while i < len(n.children):
            ch = n.children[i]
            if ch.type == argument:
                self._argument(ch, args, keywords, vararg)
            elif ch.type == STAR:
                vararg = self.ast_for_expr(n.children[i + 1])
                i += 1
            elif ch.type == DOUBLESTAR:
                kwarg = self.ast_for_expr(n.children[i + 1])
                i += 1
            i += 1
        return Call(func, args, keywords, vararg, kwarg, func.lineno, func.col_offset)

    def _count_arguments(self, n):
        nargs = nkeywords = ngens = 0
        for ch in n.children:
            if ch.type != argument:
                continue
            if len(ch.children) == 1:
                nargs += 1
            elif ch.children[1].type == comp_for:
                ngens += 1
            else:
                nkeywords += 1
        if ngens > 1 or (ngens and (nargs or nkeywords)):
            raise _error(n, "Generator expression must be parenthesized if not sole argument")
        if nargs + nkeywords + ngens > 255:
            raise _error(n, "more than 255 arguments")

    def _argument(self, ch, args, keywords, vararg):
        if len(ch.children) == 1:
            if keywords:
                raise _error(ch.children[0], "non-keyword arg after keyword arg")
            if vararg is not None:
                raise _error(ch.children[0], "only named arguments may follow *expression")
            args.append(self.ast_for_expr(ch.children[0]))
        elif ch.children[1].type == comp_for:
            args.append(self.ast_for_genexp(ch))
        else:
            keywords.append(self._keyword(ch, keywords))

    def _keyword(self, ch, keywords):
        e = self.ast_for_expr(ch.children[0])
        if e.__class__ is Lambda:
            raise _error(ch.children[0], "lambda cannot contain assignment")
        if e.__class__ is not Name:
            raise _error(ch.children[0], "keyword can't be an expression")
        self.forbidden_check(ch.children[0], e.id)
        if any(k.arg == e.id for k in keywords):
            raise _error(ch.children[0], "keyword argument repeated")
        return keyword(e.id, self.ast_for_expr(ch.children[2]))

    def ast_for_testlist(self, n):
        if len(n.children) == 1:
            return self.ast_for_expr(n.children[0])
        return Tuple(self.seq_for_testlist(n), LOAD, n.lineno, n.col)

    def ast_for_testlist_comp(self, n):
        if len(n.children) > 1 and n.children[1].type == comp_for:
            return self.ast_for_genexp(n)
        return self.ast_for_testlist(n)

    def ast_for_class_bases(self, n):
        if len(n.children) == 1:
            return [self.ast_for_expr(n.children[0])]
        return self.seq_for_testlist(n)

    # Statements

    def ast_for_expr_stmt(self, n):
        children = n.children
        if len(children) == 1:
            return Expr(self.ast_for_testlist(children[0]), n.lineno, n.col)
        if children[1].type == augassign:
            ch = children[0]
            expr1 = self.ast_for_testlist(ch)
            self.set_context(expr1, STORE, ch)
            if expr1.__class__ not in (Name, Attribute, Subscript):
                raise _error(ch, "illegal expression for augmented assignment")
            ch = children[2]
            expr2 = self.ast_for_testlist(ch) if ch.type == testlist else self.ast_for_expr(ch)
            return AugAssign(expr1, self.ast_for_augassign(children[1]), expr2, n.lineno, n.col)
        targets = []
        for i in range(0, len(children) - 2, 2):
            ch = children[i]
            if ch.type == yield_expr:
                raise _error(ch, "assignment to yield expression not possible")
            e = self.ast_for_testlist(ch)
            self.set_context(e, STORE, ch)
            targets.append(e)
        value = children[-1]
        expression = self.ast_for_testlist(value) if value.type == testlist else self.ast_for_expr(value)
        return Assign(targets, expression, n.lineno, n.col)

    def ast_for_print_stmt(self, n):
        dest = None
        start = 1
        if len(n.children) >= 2 and n.children[1].type == RIGHTSHIFT:
            dest = self.ast_for_expr(n.children[2])
            start = 4
        values = [self.ast_for_expr(n.children[i]) for i in range(start, len(n.children), 2)]
        return Print(dest, values, n.children[-1].type != COMMA, n.lineno, n.col)

    def ast_for_exprlist(self, n, context):
        seq = []
        for i in range(0, len(n.children), 2):
            e = self.ast_for_expr(n.children[i])
            seq.append(e)
            if context is not None:
                self.set_context(e, context, n.children[i])
        return seq

    def ast_for_del_stmt(self, n):
        return Delete(self.ast_for_exprlist(n.children[1], DEL), n.lineno, n.col)

    def ast_for_flow_stmt(self, n):
        ch = n.children[0]
        kind = ch.type
        if kind == break_stmt:
            return Break(n.lineno, n.col)
        if kind == continue_stmt:
            return Continue(n.lineno, n.col)
        if kind == yield_stmt:
            return Expr(self.ast_for_expr(ch.children[0]), n.lineno, n.col)
        if kind == return_stmt:
            value = self.ast_for_testlist(ch.children[1]) if len(ch.children) > 1 else None
            return Return(value, n.lineno, n.col)
        parts = [self.ast_for_expr(ch.children[i]) for i in range(1, len(ch.children), 2)]
        parts += [None] * (3 - len(parts))
        return Raise(parts[0], parts[1], parts[2], n.lineno, n.col)

    def alias_for_import_name(self, n, store):
        while True:
            kind = n.type
            if kind == import_as_name:
                name_node = n.children[0]
                asname = None
                if len(n.children) == 3:
                    str_node = n.children[2]
                    if store:
                        self.forbidden_check(str_node, str_node.value)
                    asname = _identifier(str_node)
                else:
                    self.forbidden_check(name_node, name_node.value)
                return alias(_identifier(name_node), asname)
            if kind == dotted_as_name:
                if len(n.children) == 1:
                    n = n.children[0]
                    continue
                asname_node = n.children[2]
                a = self.alias_for_import_name(n.children[0], False)
                self.forbidden_check(asname_node, asname_node.value)
                a.asname = _identifier(asname_node)
                return a
            if kind == dotted_name:
                if len(n.children) == 1:
                    name_node = n.children[0]
                    if store:
                        self.forbidden_check(name_node, name_node.value)
                    return alias(_identifier(name_node), None)
                return alias(".".join(_identifier(n.children[i]) for i in range(0, len(n.children), 2)), None)
            return alias("*", None)  # STAR

    def ast_for_import_stmt(self, n):
        lineno, col = n.lineno, n.col
        n = n.children[0]
        if n.type == import_name:
            names = n.children[1]
            return Import([self.alias_for_import_name(names.children[i], True)
                           for i in range(0, len(names.children), 2)], lineno, col)
        idx, ndots, mod = 1, 0, None
        while idx < len(n.children):
            ch = n.children[idx]
            if ch.type == dotted_name:
                mod = self.alias_for_import_name(ch, False)
                idx += 1
                break
            if ch.type != DOT:
                break
            ndots += 1
            idx += 1
        idx += 1  # 'import'
        ch = n.children[idx]
        if ch.type == STAR:
            names = [self.alias_for_import_name(ch, True)]
        else:
            if ch.type == LPAR:
                ch = n.children[idx + 1]
            elif len(ch.children) % 2 == 0:
                raise _error(ch, "trailing comma not allowed without surrounding parentheses")
            names = [self.alias_for_import_name(ch.children[i], True) for i in range(0, len(ch.children), 2)]
        return ImportFrom(mod.name if mod is not None else None, names, ndots, lineno, col)

    def ast_for_global_stmt(self, n):
        return Global([_identifier(n.children[i]) for i in range(1, len(n.children), 2)], n.lineno, n.col)

    def ast_for_exec_stmt(self, n):
        count = len(n.children)
        expr1 = self.ast_for_expr(n.children[1])
        globs = locs = None
        if expr1.__class__ is Tuple and count < 4 and len(expr1.elts) in (2, 3):
            globs = expr1.elts[1]
            if len(expr1.elts) == 3:
                locs = expr1.elts[2]
            expr1 = expr1.elts[0]
        if count >= 4:
            globs = self.ast_for_expr(n.children[3])
        if count == 6:
            locs = self.ast_for_expr(n.children[5])
        return Exec(expr1, globs, locs, n.lineno, n.col)

    def ast_for_assert_stmt(self, n):
        expr1 = self.ast_for_expr(n.children[1])
        msg = self.ast_for_expr(n.children[3]) if len(n.children) == 4 else None
        return Assert(expr1, msg, n.lineno, n.col)

    def ast_for_suite(self, n):
        seq = []
        if n.children[0].type == simple_stmt:
            n = n.children[0]
            end = len(n.children) - 1
            if n.children[end - 1].type == SEMI:
                end -= 1
            for i in range(0, end, 2):
                seq.append(self.ast_for_stmt(n.children[i]))
            return seq
        for ch in n.children[2:-1]:
            if _num_stmts(ch) == 1:
                seq.append(self.ast_for_stmt(ch))
                continue
            ch = ch.children[0]
            for j in range(0, len(ch.children), 2):
                if _nch(ch.children[j]) == 0:
                    break
                seq.append(self.ast_for_stmt(ch.children[j]))
        return seq

    def ast_for_if_stmt(self, n):
        children = n.children
        if len(children) == 4:
            expression = self.ast_for_expr(children[1])
            return If(expression, self.ast_for_suite(children[3]), [], n.lineno, n.col)
        if children[4].value[2] == "s":  # else
            expression = self.ast_for_expr(children[1])
            seq1 = self.ast_for_suite(children[3])
            seq2 = self.ast_for_suite(children[6])
            return If(expression, seq1, seq2, n.lineno, n.col)
        n_elif = len(children) - 4
        has_else = children[n_elif + 1].type == NAME and children[n_elif + 1].value[2] == "s"
        if has_else:
            n_elif -= 3
        n_elif //= 4
        orelse = []
        if has_else:
            last = children[-6]
            expression = self.ast_for_expr(last)
            suite_seq = self.ast_for_suite(children[-4])
            suite_seq2 = self.ast_for_suite(children[-1])
            orelse = [If(expression, suite_seq, suite_seq2, last.lineno, last.col)]
            n_elif -= 1
        for i in range(n_elif):
            off = 5 + (n_elif - i - 1) * 4
            expression = self.ast_for_expr(children[off])
            suite_seq = self.ast_for_suite(children[off + 2])
            orelse = [If(expression, suite_seq, orelse, children[off].lineno, children[off].col)]
        expression = self.ast_for_expr(children[1])
        return If(expression, self.ast_for_suite(children[3]), orelse, n.lineno, n.col)

    def ast_for_while_stmt(self, n):
        expression = self.ast_for_expr(n.children[1])
        seq1 = self.ast_for_suite(n.children[3])
        seq2 = self.ast_for_suite(n.children[6]) if len(n.children) == 7 else []
        return While(expression, seq1, seq2, n.lineno, n.col)

    def ast_for_for_stmt(self, n):
        seq = self.ast_for_suite(n.children[8]) if len(n.children) == 9 else []
        node_target = n.children[1]
        targets = self.ast_for_exprlist(node_target, STORE)
        first = targets[0]
        if len(node_target.children) == 1:
            target = first
        else:
            target = Tuple(targets, STORE, first.lineno, first.col_offset)
        expression = self.ast_for_testlist(n.children[3])
        suite_seq = self.ast_for_suite(n.children[5])
        return For(target, expression, suite_seq, seq, n.lineno, n.col)

    def ast_for_except_clause(self, exc, body):
        count = len(exc.children)
        if count == 1:
            return ExceptHandler(None, None, self.ast_for_suite(body), exc.lineno, exc.col)
        if count == 2:
            expression = self.ast_for_expr(exc.children[1])
            return ExceptHandler(expression, None, self.ast_for_suite(body), exc.lineno, exc.col)
        e = self.ast_for_expr(exc.children[3])
        self.set_context(e, STORE, exc.children[3])
        expression = self.ast_for_expr(exc.children[1])
        return ExceptHandler(expression, e, self.ast_for_suite(body), exc.lineno, exc.col)

    def ast_for_try_stmt(self, n):
        children = n.children
        nch = len(children)
        n_except = (nch - 3) // 3
        orelse = finally_ = None
        body = self.ast_for_suite(children[2])
        if children[nch - 3].type == NAME:
            if children[nch - 3].value == "finally":
                if nch >= 9 and children[nch - 6].type == NAME:
                    orelse = self.ast_for_suite(children[nch - 4])
                    n_except -= 1
                finally_ = self.ast_for_suite(children[nch - 1])
                n_except -= 1
            else:
                orelse = self.ast_for_suite(children[nch - 1])
                n_except -= 1
        elif children[nch - 3].type != except_clause:
            raise _error(n, "malformed 'try' statement")
        if n_except > 0:
            handlers = [self.ast_for_except_clause(children[3 + i * 3], children[5 + i * 3])
                        for i in range(n_except)]
            except_st = TryExcept(body, handlers, orelse or [], n.lineno, n.col)
            if finally_ is None:
                return except_st
            body = [except_st]
        return TryFinally(body, finally_, n.lineno, n.col)

    def ast_for_with_item(self, n, content):
        context_expr = self.ast_for_expr(n.children[0])
        optional_vars = None
        if len(n.children) == 3:
            optional_vars = self.ast_for_expr(n.children[2])
            self.set_context(optional_vars, STORE, n)
        return With(context_expr, optional_vars, content, n.lineno, n.col)

    def ast_for_with_stmt(self, n):
        i = len(n.children) - 1
        inner = self.ast_for_suite(n.children[i])
        while True:
            i -= 2
            ret = self.ast_for_with_item(n.children[i], inner)
            if i == 1:
                return ret
            inner = [ret]

    def ast_for_classdef(self, n, decorator_seq):
        children = n.children
        self.forbidden_check(n, children[1].value)
        if len(children) == 4:
            s = self.ast_for_suite(children[3])
            return ClassDef(_identifier(children[1]), [], s, decorator_seq, n.lineno, n.col)
        if children[3].type == RPAR:
            s = self.ast_for_suite(children[5])
            return ClassDef(_identifier(children[1]), [], s, decorator_seq, n.lineno, n.col)
        bases = self.ast_for_class_bases(children[3])
        s = self.ast_for_suite(children[6])
        return ClassDef(_identifier(children[1]), bases, s, decorator_seq, n.lineno, n.col)

    _SMALL = {
        expr_stmt: "ast_for_expr_stmt", print_stmt: "ast_for_print_stmt", del_stmt: "ast_for_del_stmt",
        flow_stmt: "ast_for_flow_stmt", import_stmt: "ast_for_import_stmt",
        global_stmt: "ast_for_global_stmt", exec_stmt: "ast_for_exec_stmt",
        assert_stmt: "ast_for_assert_stmt",
    }
    _COMPOUND = {
        if_stmt: "ast_for_if_stmt", while_stmt: "ast_for_while_stmt", for_stmt: "ast_for_for_stmt",
        try_stmt: "ast_for_try_stmt", with_stmt: "ast_for_with_stmt", decorated: "ast_for_decorated",
    }

    def ast_for_stmt(self, n):
        if n.type == stmt:
            n = n.children[0]
        if n.type == simple_stmt:
            n = n.children[0]
        if n.type == small_stmt:
            n = n.children[0]
            if n.type == pass_stmt:
                return Pass(n.lineno, n.col)
            return getattr(self, self._SMALL[n.type])(n)
        ch = n.children[0]
        if ch.type == funcdef:
            return self.ast_for_funcdef(ch, [])
        if ch.type == classdef:
            return self.ast_for_classdef(ch, [])
        return getattr(self, self._COMPOUND[ch.type])(ch)

    # String literals

    def parsestrplus(self, n):
        v = self.parsestr(n.children[0].value)
        for ch in n.children[1:]:
            s = self.parsestr(ch.value)
            if isinstance(v, bytes) and isinstance(s, bytes):
                v += s
            else:
                v = codecs27.ascii_text(v) + codecs27.ascii_text(s)
        return v

    def parsestr(self, s):
        """A STRING token's value: bytes or text, as 2.7's parsestr computes it."""
        quote = s[0]
        unicode_ = self.future_unicode
        rawmode = False
        i = 0
        if quote.isalpha() or quote == "_":
            if quote in "uU":
                i += 1
                quote = s[i]
                unicode_ = True
            if quote in "bB":
                i += 1
                quote = s[i]
                unicode_ = False
            if quote in "rR":
                i += 1
                quote = s[i]
                rawmode = True
        body = s[i + 1:-1]
        if len(body) >= 4 and body[0] == quote and body[1] == quote:
            body = body[2:-2]
        if unicode_:
            return self.decode_unicode(body, rawmode)
        encoding = self.encoding
        need_encoding = encoding is not None and encoding not in ("utf-8", "iso-8859-1")
        if rawmode or u"\\" not in body:
            if need_encoding:
                return registry27.encode(codecs27.utf8_decode(body), encoding)
            return body.encode("latin-1")
        return self.decode_escape(body, encoding if need_encoding else None)

    def decode_unicode(self, s, rawmode):
        """decode_unicode: under a declared codec other than latin-1, each run of
        UTF-8 bytes becomes \\U escapes first, and a backslash before one becomes
        \\u005c, so the escape decoder sees ASCII."""
        encoding = self.encoding
        if encoding is not None and encoding != "iso-8859-1":
            out = []
            i, end = 0, len(s)
            while i < end:
                if s[i] == u"\\":
                    out.append(u"\\")
                    i += 1
                    if i < end and s[i] >= u"\x80":
                        out.append(u"u005c")
                if i < end and s[i] >= u"\x80":
                    j = i
                    while j < end and s[j] >= u"\x80":
                        j += 1
                    out.extend(u"\\U%08x" % ord(char) for char in codecs27.utf8_decode(s[i:j]))
                    i = j
                elif i < end:
                    out.append(s[i])
                    i += 1
            s = u"".join(out)
        if rawmode:
            return codecs27.decode_raw_unicode_escape(s)
        return codecs27.decode_unicode_escape(s)

    def decode_escape(self, s, recode_encoding):
        """PyString_DecodeEscape for a byte string literal (strict errors)."""
        out = []
        i, end = 0, len(s)
        while i < end:
            if s[i] != u"\\":
                i = self._non_escape(s, i, out, recode_encoding)
                continue
            if i + 1 == end:
                raise Py27SyntaxError("Trailing \\ in string", None, "ValueError")
            i = self._escape(s, i + 2, s[i + 1], out, recode_encoding)
        return u"".join(out).encode("latin-1")

    def _escape(self, s, i, char, out, recode_encoding):
        """The escape whose character, char, comes just before s[i]: the index after it."""
        end = len(s)
        if char in codecs27.SIMPLE_ESCAPES:
            out.append(codecs27.SIMPLE_ESCAPES[char])
        elif char in codecs27.OCTAL_DIGITS:
            value = ord(char) - 48
            for _ in range(2):
                if i < end and s[i] in codecs27.OCTAL_DIGITS:
                    value, i = (value << 3) + ord(s[i]) - 48, i + 1
            out.append(codecs27.unichr_(value & 0xFF))
        elif char == u"x":
            if not (i + 1 < end and s[i] in codecs27.HEX_DIGITS and s[i + 1] in codecs27.HEX_DIGITS):
                raise Py27SyntaxError("invalid \\x escape", None, "ValueError")
            out.append(codecs27.unichr_(int(s[i:i + 2], 16)))
            i += 2
        elif char != u"\n":
            out.append(u"\\")
            i = self._non_escape(s, i - 1, out, recode_encoding)
        return i

    def _non_escape(self, s, i, out, recode_encoding):
        """The non_esc branch: one byte, or under a declared codec a run of
        UTF-8 bytes re-encoded in it."""
        if recode_encoding is not None and s[i] >= u"\x80":
            j = i
            while j < len(s) and s[j] >= u"\x80":
                j += 1
            out.append(registry27.encode(codecs27.utf8_decode(s[i:j]), recode_encoding).decode("latin-1"))
            return j
        out.append(s[i])
        return i + 1


# The nodes ast_for_expr passes through when they have a single child, and the
# builder method for each expression node and each kind of atom.
_PASS_THROUGH = frozenset((test, old_test, or_test, and_test, not_test, comparison, expr, xor_expr, and_expr,
                           shift_expr, arith_expr, term, factor))
_EXPRESSIONS = {
    test: "ast_for_ifexpr", old_test: "ast_for_ifexpr", lambdef: "ast_for_lambdef", old_lambdef: "ast_for_lambdef",
    or_test: "_boolop", and_test: "_boolop", not_test: "_not", comparison: "_compare", expr: "ast_for_binop",
    xor_expr: "ast_for_binop", and_expr: "ast_for_binop", shift_expr: "ast_for_binop", arith_expr: "ast_for_binop",
    term: "ast_for_binop", yield_expr: "_yield", factor: "ast_for_factor", power: "ast_for_power",
}
_ATOMS = {NAME: "_name", STRING: "_string", NUMBER: "_number", LPAR: "_parens", LSQB: "_brackets",
          LBRACE: "_braces", BACKQUOTE: "_backquotes"}


def build(result):
    """The Module for a parser.ParseResult."""
    builder = _Builder(result.encoding, bool(result.flags & CO_FUTURE_UNICODE_LITERALS))
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, RECURSION_LIMIT))
    try:
        return builder.module(result.cst)
    finally:
        sys.setrecursionlimit(limit)


def parse(source):
    """ast.parse(source) as Python 2.7 computes it, for source bytes."""
    return build(parse_cst(source))


def iter_fields(node):
    for name in node._fields:
        if hasattr(node, name):
            yield name, getattr(node, name)


def iter_child_nodes(node):
    for _, value in iter_fields(node):
        if isinstance(value, AST):
            yield value
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, AST):
                    yield item


def walk(node):
    """Every node under node, breadth first, as ast.walk; iterative, so any depth works."""
    todo = [node]
    i = 0
    while i < len(todo):
        todo.extend(iter_child_nodes(todo[i]))
        i += 1
    return iter(todo)
