# -*- coding: utf-8 -*-
"""The record of what real interpreters make of tests/py3_cases.py.

  dump CASES_JSON        the cases, in order, as a JSON list of hex strings, for
                         .py-migrate/compile3_oracle.py cases
  merge DIR RECORD       DIR/<version>.jsonl (the oracle's output on 2.7.18 with
                         --ast, and on each 3.x) into RECORD, keyed by case name

Rerun, with the images AutoSteer CI uses, one interpreter at a time (run in
parallel, workers die for want of memory, and a death is recorded as a crash):
  sh .py-migrate/py3_verdicts.sh OUT
which runs
  python .py-migrate/py3_verdicts.py dump OUT/cases.json
  docker run --rm -m 1g ... python:2.7.18-slim python .py-migrate/compile3_oracle.py --ast \
      cases OUT/cases.json OUT/2.7.18.jsonl
  docker run --rm -m 1g ... python:<v>-slim python .py-migrate/compile3_oracle.py cases OUT/cases.json OUT/<v>.jsonl
      for v in 3.6.15 3.7.17 3.8.20 3.9.25 3.10.19 3.11.14 3.12.12 3.13.12 3.14.9 3.15.1
  python .py-migrate/py3_verdicts.py merge OUT tests/data/py3_verdicts.json
"""
import binascii
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE)]

from tests.py3_cases import ALL_CASES as CASES  # noqa: E402


def verdict(result):
    if result["ok"]:
        return "ok"
    return "%s@%s: %s" % (result["error"], result["line"], result["msg"])


def dump(path):
    with io.open(path, "w", encoding="ascii") as f:
        f.write(json.dumps([binascii.hexlify(source).decode("ascii") for _, source in CASES]))
    print("%d cases" % len(CASES))
    return 0


def merge(directory, path):
    names = [name for name, _ in CASES]
    assert len(set(names)) == len(names), "case names repeat"
    record = dict((name, {}) for name in names)
    pythons = []
    for entry in sorted(os.listdir(directory)):
        if not entry.endswith(".jsonl"):
            continue
        with io.open(os.path.join(directory, entry), encoding="ascii") as f:
            results = [json.loads(line) for line in f]
        assert len(results) == len(names), entry
        python = results[0]["python"]
        pythons.append(python)
        for name, result in zip(names, results):
            record[name][".".join(python.split(".")[:2])] = verdict(result)
    lines = [u"{", u'"pythons": %s,' % json.dumps(sorted(pythons, key=lambda v: [int(p) for p in v.split(".")])),
             u'"cases": {']
    lines.append(u",\n".join(u"  %s: %s" % (json.dumps(name), json.dumps(record[name], sort_keys=True))
                             for name in names))
    lines.append(u"}}")
    with io.open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(u"\n".join(lines) + u"\n")
    print("%d cases on %s" % (len(names), ", ".join(pythons)))
    return 0


def main(argv):
    if argv[:1] == ["dump"] and len(argv) == 2:
        return dump(argv[1])
    if argv[:1] == ["merge"] and len(argv) == 3:
        return merge(argv[1], argv[2])
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
