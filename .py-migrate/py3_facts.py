# -*- coding: utf-8 -*-
"""Facts about a real interpreter that py2scan's verdicts depend on (rulings R6,
R7, R8, R10), printed as one JSON object.

  python .py-migrate/py3_facts.py probe MODULES   with MODULES a JSON list of
                                                  top-level module names

Run with -I -S on 3.x (no site-packages: a stdlib module is one the interpreter
ships) and also without -S, so the record shows what site.py adds. The facts:
the exact version, keywords, soft keywords, __future__ features, the builtins
module's names, the Unicode version, the integer digit limit, and which of
MODULES the interpreter can find without importing them.

  python .py-migrate/py3_facts.py modules27       on 2.7.18: every top-level module
                                                  of its stdlib, with whether it is
                                                  pure Python
"""
import json
import os
import sys


def probe(modules_path):
    import keyword
    import unicodedata
    import __future__
    try:
        import builtins
    except ImportError:
        import __builtin__ as builtins
    with open(modules_path) as f:
        modules = json.load(f)
    if sys.version_info[0] >= 3:
        import importlib.util
        found = sorted(m for m in modules if m in sys.builtin_module_names or importlib.util.find_spec(m) is not None)
    else:
        import imp
        found = []
        for m in modules:
            try:
                imp.find_module(m)
                found.append(m)
            except ImportError:
                if m in sys.builtin_module_names:
                    found.append(m)
    facts = {
        "python": "%d.%d.%d" % sys.version_info[:3],
        "releaselevel": sys.version_info[3],
        "site": "site" in sys.modules,
        "keywords": sorted(keyword.kwlist),
        "soft_keywords": sorted(getattr(keyword, "softkwlist", [])),
        "future": list(__future__.all_feature_names),
        "builtins": sorted(dir(builtins)),
        "unicode": unicodedata.unidata_version,
        "max_str_digits": getattr(getattr(sys, "int_info", None), "default_max_str_digits", None),
        "modules": found,
    }
    print(json.dumps(facts, sort_keys=True))
    return 0


def modules27():
    """Top-level modules of 2.7's stdlib: .py files and packages in the library
    directories on its own sys.path (python2.7, plat-linux2, lib-tk, lib-old)
    are pure Python; extension modules in lib-dynload and modules built into
    the interpreter are C."""
    lib = os.path.dirname(os.__file__)
    found = {}
    for directory in sys.path:
        if not directory.startswith(lib) or not os.path.isdir(directory) or directory.endswith("lib-dynload"):
            continue
        for name in os.listdir(directory):
            path = os.path.join(directory, name)
            if name.endswith(".py") and name.count(".") == 1:  # not __phello__.foo.py, which is no module name
                found[name[:-3]] = "python"
            elif os.path.isfile(os.path.join(path, "__init__.py")) and name != "site-packages":
                found[name] = "python"
    dynload = os.path.join(lib, "lib-dynload")
    for name in os.listdir(dynload):
        if name.endswith(".so"):
            found.setdefault(name.split(".")[0], "c")
    for name in sys.builtin_module_names:
        if name != "__main__":  # the running script, not a library module
            found.setdefault(name, "c")
    print(json.dumps(found, sort_keys=True))
    return 0


def main(argv):
    if argv[:1] == ["probe"] and len(argv) == 2:
        return probe(argv[1])
    if argv == ["modules27"] and sys.version_info[:2] == (2, 7):
        return modules27()
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
