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

# Advisory -> where its vulnerable code is: "module" (and its submodules) or
# "module:function". A py2scan run must reach none of it, on either interpreter;
# names cover both the 2.7 and the 3 spelling of a module. On 2.7, jinja2._compat
# imports urllib, which loads socket, _ssl, ssl, base64 and urlparse, so for those
# the entries name the vulnerable functions. .py-migrate/advisories.py
# reads this map, so an advisory triaged as never reached always has a test here.
NOT_REACHED = {
    # CPython 2.7.18
    "CVE-2007-4559": ["tarfile"],
    "CVE-2009-3720": ["pyexpat", "xml"],
    "CVE-2017-17522": ["webbrowser"],
    "CVE-2017-18207": ["wave"],
    "CVE-2021-23336": ["urlparse:parse_qs", "urlparse:parse_qsl", "urllib.parse:parse_qs",
                       "urllib.parse:parse_qsl", "cgi"],
    "CVE-2021-3733": ["urllib2", "urllib.request"],
    "CVE-2022-0391": ["urlparse:urlsplit", "urllib.parse:urlsplit"],
    "CVE-2022-45061": ["encodings.idna"],
    "CVE-2022-48560": ["heapq:heappushpop", "_heapq:heappushpop"],
    "CVE-2022-48564": ["plistlib"],
    "CVE-2022-48565": ["plistlib"],
    "CVE-2022-48566": ["hmac:compare_digest", "operator:_compare_digest", "_operator:_compare_digest"],
    "CVE-2023-24329": ["urlparse:urlsplit", "urllib.parse:urlsplit"],
    "CVE-2023-27043": ["email"],
    "CVE-2023-36632": ["email"],
    "CVE-2023-40217": ["ssl:wrap_socket", "ssl:__init__", "_SSLContext:_wrap_socket", "_SSLContext:_wrap_bio"],
    "CVE-2024-6232": ["tarfile"],
    "CVE-2024-7592": ["Cookie", "http.cookies"],
    "CVE-2024-9287": ["venv"],
    "CVE-2025-12084": ["xml"],
    "CVE-2025-12781": ["base64:b64decode", "base64:standard_b64decode", "base64:urlsafe_b64decode"],
    "CVE-2025-13462": ["tarfile"],
    "CVE-2025-13836": ["httplib", "http.client"],
    "CVE-2025-13837": ["plistlib"],
    "CVE-2025-6075": ["posixpath:expandvars", "ntpath:expandvars"],
    "CVE-2026-0864": ["ConfigParser", "configparser"],
    "CVE-2026-15308": ["HTMLParser", "html.parser"],
    "CVE-2026-19672": ["tarfile"],
    "CVE-2026-3087": ["shutil:unpack_archive"],
    "CVE-2026-3479": ["pkgutil:get_data"],  # pkgutil itself loads: futures' namespace shim calls extend_path
    "CVE-2026-3644": ["Cookie", "http.cookies"],
    "CVE-2026-4224": ["pyexpat", "xml"],
    "CVE-2026-4360": ["tarfile"],
    "CVE-2026-4519": ["webbrowser"],
    "CVE-2026-6019": ["Cookie", "http.cookies"],
    "CVE-2026-7210": ["pyexpat", "xml"],
    # CPython 3.14.9
    "CVE-2026-114583": ["tarfile"],
    # Packages
    "CVE-2024-22195": ["jinja2.filters:do_xmlattr"],
    "CVE-2024-34064": ["jinja2.filters:do_xmlattr"],
    "CVE-2024-56326": ["jinja2.sandbox"],
    "CVE-2025-27516": ["jinja2.sandbox", "jinja2.filters:do_attr"],
    "CVE-2024-5569": ["zipp"],
}
# Build and test tools: in the images, never part of a run.
TOOLS = ["pip", "setuptools", "pkg_resources", "wheel", "pytest", "_pytest", "importlib_metadata", "zipp"]

# Installed as sitecustomize, so every process of the run records itself, the
# scan workers included: forked ones inherit the profiler, and forkserver's
# server runs site at startup. Each process writes every distinct function it
# calls: Python ("call", with <module> for a module's own code), C module
# functions ("c_call") and C methods ("c_method", under their type's name), and
# the modules already imported when site finished.
RECORDER = """\
import os
import sys
import threading

_log = open(os.environ["PY2SCAN_REACH_LOG"], "a")
_seen = set()


def _write(*fields):
    _log.write(" ".join((str(os.getpid()),) + fields) + "\\n")
    _log.flush()


for _name in sorted(sys.modules):
    if sys.modules[_name] is not None:
        _write("loaded", _name)


def _profile(frame, event, arg):
    if event == "call":
        key = ("call", frame.f_globals.get("__name__") or "?", frame.f_code.co_name)
    elif event == "c_call" and getattr(arg, "__module__", None):
        key = ("c_call", arg.__module__, arg.__name__)
    elif event == "c_call":
        key = ("c_method", type(getattr(arg, "__self__", None)).__name__, arg.__name__)
    else:
        return
    if (os.getpid(), key) not in _seen:
        _seen.add((os.getpid(), key))
        _write(*key)


sys.setprofile(_profile)
threading.setprofile(_profile)
"""

# What pip writes for the console_scripts entry point in setup.py.
ENTRY_POINT = "import sys\nfrom py2scan.cli import main\nsys.exit(main())\n"


@pytest.fixture(scope="module")
def recorded(tmpdir_factory):
    """Run the CLI with every output option; (modules seen, (module, function) pairs called, records)."""
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
    records = [line.split() for line in log.read().splitlines()]
    calls = set((r[2], r[3]) for r in records if r[1] in ("call", "c_call", "c_method"))
    modules = set(r[2] for r in records if r[1] in ("loaded", "call", "c_call"))
    return modules, calls, records


def _reached(entry, modules, calls):
    module, _, function = entry.partition(":")
    if function:
        return sorted("%s:%s" % c for c in calls if c == (module, function))
    return sorted(m for m in modules if m == module or m.startswith(module + "."))


def test_the_recorder_sees_the_main_process_and_the_scan_workers(recorded):
    records = recorded[2]
    reporters = set(r[0] for r in records if r[1:] == ["call", "py2scan.report", "to_html"])
    scanners = set(r[0] for r in records if r[1:] == ["call", "py2scan.scanner", "_scan_batch"])
    assert reporters and scanners and not reporters & scanners
    assert ("posix", "stat") in recorded[1] and ("list", "append") in recorded[1]  # and C calls


@pytest.mark.parametrize("advisory", sorted(NOT_REACHED))
def test_a_run_never_reaches_the_code_an_advisory_is_in(recorded, advisory):
    modules, calls, _ = recorded
    assert [hit for entry in NOT_REACHED[advisory] for hit in _reached(entry, modules, calls)] == []


def test_a_run_never_loads_a_build_or_test_tool(recorded):
    modules, calls, _ = recorded
    assert [hit for entry in TOOLS for hit in _reached(entry, modules, calls)] == []


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
    assert len(lines) > 10 and [entry for entry in lines if not PIN.match(entry[1])] == []


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
