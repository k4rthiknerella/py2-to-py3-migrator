# -*- coding: utf-8 -*-
"""py2scan.py27 computes what CPython 2.7 computes, on whichever interpreter runs it.

tests/data/py27_cases.json records what 2.7.18 itself computes for each input
in tests/py27_cases.py: .py-migrate/py27_parity.py record-cases writes it, and
verify-cases compares it with 2.7.18's parser and ast modules, so it cannot
drift. These tests compare py2scan.py27 with the record, on 2.7 and 3.x alike.
"""
import hashlib
import io
import json
import os

import pytest

from py2scan.py27 import ast27
from tests import py27_cases
from tests.py27_reference import digest, mine, same

FIXTURE = os.path.join(os.path.dirname(__file__), "data", "py27_cases.json")
SOURCES = [c if isinstance(c, bytes) else c.encode("utf-8") for c in py27_cases.CASES + py27_cases.RAW]

with io.open(FIXTURE, encoding="ascii") as f:
    RECORD = json.load(f)


def key(source):
    return hashlib.sha256(source).hexdigest()


def test_every_case_is_recorded():
    assert sorted(RECORD) == sorted(set(key(source) for source in SOURCES))


@pytest.mark.parametrize("source", SOURCES, ids=["case%03d" % i for i in range(len(SOURCES))])
def test_the_front_end_computes_what_python_2_7_does(source):
    cst, tree = mine(source)
    assert same(RECORD[key(source)]["ast"], tree), tree[:2000]
    assert RECORD[key(source)]["cst"] == digest(cst)


def test_a_tree_deeper_than_the_recursion_limit_walks():
    tree = ast27.parse(b"x = " + b" + ".join([b"a"] * 5000) + b"\n")
    assert sum(isinstance(node, ast27.BinOp) for node in ast27.walk(tree)) == 4999


def test_numbers_keep_their_text_past_the_int_digit_limit():
    tree = ast27.parse(b"x = -1" + b"0" * 5000 + b"L\n")
    assert tree.body[0].value.n == "-1" + "0" * 5000 + "L"
