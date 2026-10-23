# -*- coding: utf-8 -*-
"""Reachability evidence for the advisory triage in .py-migrate/advisories.py.

Each test checks a fact that an accept or mitigate decision there rests on, so
a change that makes an accepted advisory reachable fails here.
"""
import ast
import io
import os
import re
import subprocess
import sys

import jinja2
import pytest
from jinja2 import nodes

from py2scan import report

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Modules with an advisory in either environment that a py2scan run must never load.
NEVER_LOADED = (
    "email", "tarfile", "webbrowser",  # CPython 2.7.18 and 3.14.9
    "pip", "setuptools", "pkg_resources", "wheel",  # build tools in the test images
    "pytest", "_pytest", "zipp", "importlib_metadata",  # test tools
    "jinja2.sandbox",  # the Jinja2 sandbox breakouts
)
# Loaded on 2.7 (the futures backport's concurrent/__init__.py calls extend_path),
# so the claim is about the function: CVE-2026-3479 is in pkgutil.get_data.
NEVER_CALLED = (("pkgutil", "get_data"),)
WATCH = NEVER_LOADED + ("pkgutil", "py2scan.report", "py2scan.scanner")

# Installed as sitecustomize, so every process of the run records itself, the
# scan workers included: forked ones inherit the profiler, and forkserver's
# server runs site at startup. A module is loaded when its code runs, which the
# profiler sees as a call to <module>; modules imported before site finished
# are listed from sys.modules.
RECORDER = """\
import os
import sys
import threading

_WATCH = %r
_seen = {}
_log = open(os.environ["PY2SCAN_REACH_LOG"], "a")


def _watched(module):
    if module not in _seen:
        _seen[module] = any(module == w or module.startswith(w + ".") for w in _WATCH)
    return _seen[module]


def _write(*fields):
    _log.write(" ".join((str(os.getpid()),) + fields) + "\\n")
    _log.flush()


for _name in sorted(sys.modules):
    if _watched(_name):
        _write("loaded", _name)


def _profile(frame, event, arg):
    if event == "call":
        module = frame.f_globals.get("__name__") or ""
        if _watched(module):
            _write("call", module, frame.f_code.co_name)


sys.setprofile(_profile)
threading.setprofile(_profile)
""" % (WATCH,)

# What pip writes for the console_scripts entry point in setup.py.
ENTRY_POINT = "import sys\nfrom py2scan.cli import main\nsys.exit(main())\n"


@pytest.fixture(scope="module")
def recorded(tmpdir_factory):
    """Run the CLI with every output option and return the records, split into fields."""
    tmp = tmpdir_factory.mktemp("reach")
    tmp.mkdir("site").join("sitecustomize.py").write(RECORDER)
    src = tmp.mkdir("src")
    for name, text in [("a.py", "print 'a'\n"), ("b.py", "import urllib2\n"), ("c.py", "x = 1 / 2\n")]:
        src.join(name).write(text)
    tmp.join("cfg.yml").write("severity: {PY3-DIVISION: blocker}\n")
    log, html = tmp.join("reach.log"), tmp.join("report.html")
    env = dict(os.environ, PY2SCAN_REACH_LOG=str(log),
               PYTHONPATH=os.pathsep.join([str(tmp.join("site")), ROOT]))
    with open(os.devnull, "wb") as null:
        code = subprocess.call(
            [sys.executable, "-c", ENTRY_POINT, "scan", str(src), "--format", "json",
             "--html", str(html), "--config", str(tmp.join("cfg.yml")), "--jobs", "2"],
            env=env, stdout=null)
    assert code == 1 and html.check(file=1), "the run did not complete"
    return [line.split() for line in log.read().splitlines()]


def test_the_recorder_sees_the_main_process_and_the_scan_workers(recorded):
    reporters = set(r[0] for r in recorded if r[1:] == ["call", "py2scan.report", "to_html"])
    scanners = set(r[0] for r in recorded if r[1:] == ["call", "py2scan.scanner", "_scan_batch"])
    assert reporters and scanners and not reporters & scanners


def test_a_run_never_loads_a_module_with_an_advisory(recorded):
    loaded = sorted(set(r[2] for r in recorded if r[2] != "pkgutil" and not r[2].startswith("py2scan.")))
    assert loaded == []


def test_a_run_never_calls_pkgutil_get_data(recorded):
    calls = set(tuple(r[2:4]) for r in recorded if r[1] == "call")
    assert calls.isdisjoint(NEVER_CALLED)


def _py2scan_sources():
    for top, dirs, files in os.walk(os.path.join(ROOT, "py2scan")):
        for name in sorted(files):
            if name.endswith(".py"):
                path = os.path.join(top, name)
                with open(path, "rb") as f:
                    yield os.path.relpath(path, ROOT).replace(os.sep, "/"), ast.parse(f.read())


TEMPLATE_LOADERS = ("from_string", "get_template", "select_template", "get_or_select_template",
                    "Template", "compile_expression")


def test_py2scan_renders_only_its_own_constant_template_without_a_sandbox():
    # CVE-2024-56326 and CVE-2025-27516 need an attacker-written template in a SandboxedEnvironment.
    loads, assigned = [], []
    for path, tree in _py2scan_sources():
        for node in ast.walk(tree):
            func = getattr(node, "func", None)
            if isinstance(node, ast.Call) and getattr(func, "attr", getattr(func, "id", None)) in TEMPLATE_LOADERS:
                loads.append((path, [getattr(a, "id", None) for a in node.args]))
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "TEMPLATE" for t in node.targets):
                assigned.append((path, ast.literal_eval(node.value)))
    assert loads == [("py2scan/report.py", ["TEMPLATE"])]
    assert assigned == [("py2scan/report.py", report.TEMPLATE)]
    assert type(report._template().environment) is jinja2.Environment


def test_the_report_template_applies_neither_xmlattr_nor_attr():
    # CVE-2024-22195 and CVE-2024-34064 are in xmlattr; CVE-2025-27516 uses attr.
    tree = report._template().environment.parse(report.TEMPLATE)
    used = set(n.name for n in tree.find_all(nodes.Filter))
    assert used and used.isdisjoint(["xmlattr", "attr"])


PIN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*(==|<)[0-9][0-9A-Za-z.]*'
                 r'( *; *python_version *[<>]=? *"[0-9.]+")?$')


def _requirement_lines():
    for name in ("requirements.txt", "requirements-dev.txt", "constraints-build.txt"):
        with io.open(os.path.join(ROOT, name), encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line and line != "-r requirements.txt":
                    yield name, line
    with open(os.path.join(ROOT, "setup.py"), "rb") as f:
        for node in ast.walk(ast.parse(f.read())):
            if isinstance(node, ast.keyword) and node.arg == "install_requires":
                for line in ast.literal_eval(node.value):
                    yield "setup.py", line


def test_requirements_name_only_packages_from_the_default_index():
    # pip CVE-2021-3572 and CVE-2023-5752 need a VCS URL; CVE-2026-13346 needs another index.
    lines = list(_requirement_lines())
    assert len(lines) > 10 and [l for l in lines if not PIN.match(l[1])] == []


def test_the_test_image_uses_the_default_index_and_skips_pips_self_check():
    # pip CVE-2026-6357 is in the self-update check that runs after installing wheels.
    with io.open(os.path.join(ROOT, "Dockerfile.test"), encoding="utf-8") as f:
        text = f.read()
    assert "PIP_DISABLE_PIP_VERSION_CHECK=1" in text
    assert [o for o in ("index-url", "find-links", "trusted-host", "PIP_INDEX", "PIP_EXTRA", "PIP_FIND")
            if o in text] == []


def test_there_is_no_manifest_in():
    # setuptools CVE-2026-59890 lets files that MANIFEST.in excludes into an sdist.
    assert not os.path.exists(os.path.join(ROOT, "MANIFEST.in"))


def test_pytest_temp_directories_are_closed_to_other_users(tmpdir_factory):
    # pytest CVE-2025-71176 (fixed in 9.0.3; 4.6.11 on 2.7): another user who owns or can
    # write /tmp/pytest-of-USER can redirect the tests' temporary files.
    parent = os.path.dirname(str(tmpdir_factory.getbasetemp()))
    stat = os.stat(parent)
    assert not os.path.basename(parent).startswith("pytest-of-") or (
        stat.st_uid == os.getuid() and stat.st_mode & 0o022 == 0)
