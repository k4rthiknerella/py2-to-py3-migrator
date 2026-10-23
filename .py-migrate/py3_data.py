# -*- coding: utf-8 -*-
"""Facts about each judged Python 3 version that py2scan's verdicts depend on
and cannot compute on 2.7 (rulings R1, R6, R7, R9), and the data modules made
from them.

  probe ALIASES OUT     on a 3.x interpreter: OUT gets its \\N{...} names and
                        source-encoding facts as JSON. ALIASES is Unicode's
                        NameAliases.txt (17.0.0, the newest any judged
                        version uses).
  build DIR TABLES      from DIR/<version>.json for every judged version, and
                        TABLES/<version>.json from .py-migrate/codec_tables.py
                        on 2.7.18 and each of them: py2scan/py3/names_data.py
                        and codecs_data.py

Rerun, with the images AutoSteer CI uses, one interpreter at a time:
  sh .py-migrate/py3_data.sh OUT
"""
import io
import json
import os
import sys
import unicodedata
import zlib
import base64

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE)]

# Names an algorithm derives from the code point in some judged version.
FAMILIES = ("CJK UNIFIED IDEOGRAPH-", "TANGUT IDEOGRAPH-", "CJK COMPATIBILITY IDEOGRAPH-", "NUSHU CHARACTER-",
            "KHITAN SMALL SCRIPT CHARACTER-", "EGYPTIAN HIEROGLYPH-")


def escape_ok(name):
    try:
        eval(compile('"\\N{%s}"' % name, "t.py", "eval", dont_inherit=True))
        return True
    except SyntaxError:
        return False


def ranges(codes):
    out = []
    for code in sorted(codes):
        if out and out[-1][1] == code - 1:
            out[-1][1] = code
        else:
            out.append([code, code])
    return out


def probe_names(aliases_path):
    named, families = {}, {}
    for code in range(0x110000):
        name = unicodedata.name(chr(code), None)
        if name is None or name.startswith("HANGUL SYLLABLE "):
            continue
        family = next((f for f in FAMILIES if name == "%s%04X" % (f, code)), None)
        if family:
            families.setdefault(family, []).append(code)
        else:
            named[name] = code
    rejected = sorted(n for n in named if not escape_ok(n))
    aliases = []
    with io.open(aliases_path, encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                aliases.append(line.split(";")[1])
    return {
        "regular": sorted(n for n in named if n not in rejected),
        "regular_rejected": rejected,
        "aliases": sorted(a for a in aliases if escape_ok(a)),
        "families": dict((f, ranges(codes)) for f, codes in families.items()),
        "families_ok": dict((f, escape_ok("%s%04X" % (f, codes[0]))) for f, codes in families.items()),
    }


def probe_codecs():
    """For every name 2.7's registry knows (its aliases and its modules), whether
    this interpreter's tokenizer accepts it in a coding declaration."""
    from py2scan.py27 import codecs27_data
    names = sorted(set(codecs27_data.ALIASES) | set(codecs27_data.MODULES))
    accepted = {}
    for name in names:
        for spelling in (name, name.replace("_", "-")):
            try:
                compile(("# coding: %s\nx = 1\n" % spelling).encode("ascii"), "t.py", "exec", dont_inherit=True)
                ok = True
            except SyntaxError:
                ok = False
            accepted[spelling] = ok
    return accepted


def probe(aliases_path, out):
    facts = {"python": "%d.%d.%d" % sys.version_info[:3], "unicode": unicodedata.unidata_version}
    facts.update(probe_names(aliases_path))
    facts["codecs"] = probe_codecs()
    with io.open(out, "w", encoding="ascii") as f:
        f.write(json.dumps(facts, sort_keys=True))
    print("%s: %d regular names, %d aliases" % (facts["python"], len(facts["regular"]), len(facts["aliases"])))
    return 0


PYTHONS = ("3.6.15", "3.7.17", "3.8.20", "3.9.25", "3.10.19", "3.11.14", "3.12.12", "3.13.12", "3.14.9", "3.15.1")
# makeunicodedata.py derived_name_range_names (3.14.9), and in 3.15.1 also every
# name that ends in its own code point.
DERIVED = {"3.14": ["CJK UNIFIED IDEOGRAPH-", "TANGUT IDEOGRAPH-"],
           "3.15": ["CJK UNIFIED IDEOGRAPH-", "TANGUT IDEOGRAPH-", "CJK COMPATIBILITY IDEOGRAPH-",
                    "NUSHU CHARACTER-", "KHITAN SMALL SCRIPT CHARACTER-", "EGYPTIAN HIEROGLYPH-"]}


def _label(python):
    return ".".join(python.split(".")[:2])


def _wrap(text, width=100):
    return "\n".join("    %r" % text[i:i + width] for i in range(0, len(text), width))


def _first_versions(facts, key, known52):
    first = {}
    for python in PYTHONS:
        for name in facts[python][key]:
            if name not in first and not known52(name):
                first[name] = _label(python)
    return first


def build_names(facts, tables, out):
    from py2scan.py27 import codecs27
    labels = [_label(p) for p in PYTHONS]
    regular = _first_versions(facts, "regular", lambda n: codecs27.lookup_name(n) is not None)
    aliases = _first_versions(facts, "aliases", lambda n: False)
    families = {}
    for python in PYTHONS:
        found = dict(facts[python]["families"])
        if tables[python]["tangut"]:
            found["TANGUT IDEOGRAPH-"] = tables[python]["tangut"]
        for family, ranges in found.items():
            families.setdefault(family, {})[_label(python)] = [tuple(r) for r in ranges]
    text = "".join("%d %s\n" % (labels.index(v), n) for n, v in sorted(regular.items()))
    packed = base64.b64encode(zlib.compress(text.encode("ascii"), 9)).decode("ascii")
    lines = ['# -*- coding: utf-8 -*-',
             '"""Generated by .py-migrate/py3_data.py from %s; do not edit.' % ", ".join(PYTHONS),
             '',
             'UNICODE: the version of each judged interpreter\'s Unicode database.',
             'FAMILIES: for names a rule derives from the code point, the code points',
             'each version names that way. DERIVED: the prefixes 3.14 and 3.15 match by',
             'rule (makeunicodedata.py). ALIASES and REGULAR (packed: "<index of the',
             'first version> NAME" lines): beyond Unicode 5.2, each name the version',
             'resolves in \\\\N{...} and the first judged version that does."""',
             '',
             'VERSIONS = %r' % (tuple(labels),),
             'PYTHONS = %r' % (PYTHONS,),
             'UNICODE = {%s}' % ", ".join("%r: %r" % (_label(p), str(facts[p]["unicode"])) for p in PYTHONS),
             'DERIVED = {"3.14": %r, "3.15": %r}' % (tuple(DERIVED["3.14"]), tuple(DERIVED["3.15"])),
             'FAMILIES = {']
    for family in sorted(families):
        lines.append('    %r: {' % str(family))
        for version in labels:
            if version in families[family]:
                spans = ", ".join("(0x%X, 0x%X)" % r for r in families[family][version])
                lines.append("        %r: (%s,)," % (version, spans))
        lines.append('    },')
    lines.append('}')
    lines.append('ALIASES = {')
    for name in sorted(aliases):
        lines.append('    %r: %r,' % (str(name), aliases[name]))
    lines.append('}')
    lines.append('REGULAR = (')
    lines.append(_wrap(packed))
    lines.append(')')
    with io.open(out, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("%s: %d names, %d aliases" % (out, len(regular), len(aliases)))


def build_codecs(facts, tables, out):
    labels = [_label(p) for p in PYTHONS]
    rejected = {}
    for name in sorted(facts[PYTHONS[0]]["codecs"]):
        versions = [_label(p) for p in PYTHONS if not facts[p]["codecs"][name]]
        if versions:
            rejected[name] = versions
    base = tables["2.7.18"]["codecs"]
    differs = {}
    for module in sorted(base):
        versions = [_label(p) for p in PYTHONS if tables[p]["codecs"][module] != base[module]]
        if versions:
            differs[module] = versions
    lines = ['# -*- coding: utf-8 -*-',
             '"""Generated by .py-migrate/py3_data.py from %s; do not edit.' % ", ".join(PYTHONS),
             '',
             'REJECTED: the judged versions whose compile() refuses a coding declaration',
             'naming each of 2.7\'s codec names, spelled with _ and with -. DIFFERS: the',
             'judged versions in which a stateless codec decodes some input of up to four',
             'bytes otherwise than 2.7.18 (.py-migrate/codec_tables.py)."""',
             '',
             'VERSIONS = %r' % (tuple(labels),),
             'REJECTED = {']
    for name in sorted(rejected):
        lines.append('    %r: %r,' % (str(name), tuple(rejected[name])))
    lines.append('}')
    lines.append('DIFFERS = {')
    for module in sorted(differs):
        lines.append('    %r: %r,' % (str(module), tuple(differs[module])))
    lines.append('}')
    lines.append('FINGERPRINTED = (')
    for module in sorted(base):
        lines.append('    %r,' % str(module))
    lines.append(')')
    with io.open(out, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("%s: %d rejected names, %d codecs that differ" % (out, len(rejected), len(differs)))


def build(directory, tables_directory):
    facts, tables = {}, {}
    for python in PYTHONS:
        with io.open(os.path.join(directory, python + ".json"), encoding="ascii") as f:
            facts[python] = json.load(f)
    for python in ("2.7.18",) + PYTHONS:
        with io.open(os.path.join(tables_directory, python + ".json"), encoding="ascii") as f:
            tables[python] = json.load(f)
    package = os.path.join(os.path.dirname(HERE), "py2scan", "py3")
    build_names(facts, tables, os.path.join(package, "names_data.py"))
    build_codecs(facts, tables, os.path.join(package, "codecs_data.py"))
    return 0


def main(argv):
    if argv[:1] == ["probe"] and len(argv) == 3:
        return probe(argv[1], argv[2])
    if argv[:1] == ["build"] and len(argv) == 3:
        return build(argv[1], argv[2])
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
