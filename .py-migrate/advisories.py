# -*- coding: utf-8 -*-
"""Known advisories for the interpreter and every package in the source and target test images.

    for v in 2.7 3.14; do docker run --rm py2scan-test:$v sh -c \
        'python -c "import platform; print(\"python==\" + platform.python_version())"; \
         pip list --format=freeze 2>/dev/null' > .py-migrate/out/env-$v.txt; done
    docker run --rm -v "$PWD":/app -w /app python:3.14-slim \
        python .py-migrate/advisories.py .py-migrate/out/env-2.7.txt .py-migrate/out/env-3.14.txt

Queries OSV (api.osv.dev), which merges the PyPA, GitHub and PSF databases.
Packages are queried by PyPI name and version. The interpreter is queried by
the commit its release tag points to, since the PSF advisories give CPython
ranges as git commits; the tag is resolved through the GitHub API. Each
advisory's aliases merge into one row, so a CVE with a GHSA and a PYSEC id is
counted once. Raw responses go to .py-migrate/out/osv/.

Exits 1 if any advisory has no row in TRIAGE or its row has expired, so a new
advisory or a lapsed acceptance cannot pass unnoticed.
"""
import datetime
import json
import os
import sys
import urllib.request

OSV = "https://api.osv.dev/v1"
CPYTHON = "https://api.github.com/repos/python/cpython/git"
OUT = os.path.join(".py-migrate", "out", "osv")

UPGRADE, MITIGATE, ACCEPT = "upgrade", "mitigate", "accept"
# The 2.7 side is deleted at flip; until then its packages are the last
# releases that support 2.7, so no fixed version can be installed there.
STRADDLE = "2027-04-22"
SDISTS = ".py-migrate/out/pip-download-2.7.txt lists the five sdists pip builds on aarch64"
TRUSTED = ("archives come only from PyPI at the pinned versions (test_requirements_name_only_packages_"
           "from_the_default_index); a crafted archive there could already run code in its setup.py")

# Primary id (a CVE where there is one) -> (decision, expires, why). Tests named
# here are in tests/test_advisories.py.
TRIAGE = {
    # Jinja2 2.11.3, 2.7 side. Fixed in 3.1.3 to 3.1.6, which need Python 3.7.
    "CVE-2024-22195": (ACCEPT, STRADDLE, "xmlattr is never applied: test_the_report_template_applies_"
                                         "neither_xmlattr_nor_attr"),
    "CVE-2024-34064": (ACCEPT, STRADDLE, "xmlattr is never applied (same test)"),
    "CVE-2024-56326": (ACCEPT, STRADDLE, "needs an attacker-written template in a sandbox; py2scan renders "
                                         "only its constant template, unsandboxed: test_py2scan_renders_only_"
                                         "its_own_constant_template_without_a_sandbox"),
    "CVE-2025-27516": (ACCEPT, STRADDLE, "needs an attacker-written template in a sandbox (same tests)"),
    # pip 20.0.2, 2.7 image: used only by docker build. 20.3.4, the last for 2.7, fixes none.
    "CVE-2021-3572": (ACCEPT, STRADDLE, "git references: no VCS requirement (test_requirements_name_only_"
                                        "packages_from_the_default_index)"),
    "CVE-2023-5752": (ACCEPT, STRADDLE, "Mercurial URLs: no VCS requirement (same test)"),
    "CVE-2025-8869": (ACCEPT, STRADDLE, "fallback tar extraction, reached for sdists; " + SDISTS + "; " + TRUSTED),
    "CVE-2026-1703": (ACCEPT, STRADDLE, "wheel path traversal; " + TRUSTED),
    "CVE-2026-3219": (ACCEPT, STRADDLE, "tar and ZIP polyglots; " + TRUSTED),
    "CVE-2026-8643": (ACCEPT, STRADDLE, "entry point names; " + TRUSTED),
    "CVE-2026-13346": (ACCEPT, STRADDLE, "needs a malicious index; only PyPI is configured (test_requirements_"
                                         "name_only_packages_from_the_default_index, test_the_test_image_uses_"
                                         "the_default_index_and_skips_pips_self_check)"),
    "CVE-2026-6357": (MITIGATE, STRADDLE, "PIP_DISABLE_PIP_VERSION_CHECK=1 in Dockerfile.test turns the "
                                          "self-update check off (test_the_test_image_uses_the_default_index_"
                                          "and_skips_pips_self_check); the build log's 'You are using pip "
                                          "version' line is gone (.py-migrate/out/build-*.log)"),
    # setuptools 44.1.0, 2.7 image: pip builds the five sdists with it. 44.1.1 is the last for 2.7.
    "CVE-2022-40897": (ACCEPT, STRADDLE, "package_index runs only for easy_install, setup_requires and "
                                         "dependency_links, which no sdist uses (.py-migrate/out/sdists-2.7.txt)"),
    "CVE-2024-6345": (ACCEPT, STRADDLE, "package_index (same evidence)"),
    "CVE-2025-47273": (ACCEPT, STRADDLE, "package_index (same evidence)"),
    "CVE-2026-59890": (ACCEPT, STRADDLE, "MANIFEST.in on macOS file systems; there is no MANIFEST.in "
                                         "(test_there_is_no_manifest_in) and this setuptools runs only on Linux"),
    # wheel 0.34.2, 2.7 image. 0.37.1 is the last for 2.7 and is affected too.
    "CVE-2022-40898": (ACCEPT, STRADDLE, "ReDoS on file names given to the wheel CLI, which is never run; "
                                         "pip names only the five pinned sdists' wheels"),
    # pytest 4.6.11, 2.7 side (pytest 9.1.1 on 3.14 is fixed).
    "CVE-2025-71176": (ACCEPT, STRADDLE, "tests run in a throwaway container with no other user; "
                                         "test_pytest_temp_directories_are_closed_to_other_users checks it"),
    # zipp 1.2.0, 2.7 side: importlib_metadata loads it inside pytest and flake8.
    "CVE-2024-5569": (ACCEPT, STRADDLE, "a py2scan run never loads it (test_a_run_never_loads_a_module_with_"
                                        "an_advisory), and the only zip on sys.path, python27.zip, does not exist"),
    # CPython 2.7.18: end of life, no fixed release will exist.
    "CVE-2023-27043": (ACCEPT, STRADDLE, "email is never loaded (test_a_run_never_loads_a_module_with_an_advisory)"),
    "CVE-2026-3479": (ACCEPT, STRADDLE, "disputed; pkgutil is loaded for extend_path, get_data never runs "
                                        "(test_a_run_never_calls_pkgutil_get_data)"),
    "CVE-2026-4519": (ACCEPT, STRADDLE, "webbrowser is never loaded (same test as email)"),
    "CVE-2026-19672": (ACCEPT, STRADDLE, "tarfile is never loaded (same test as email)"),
    # CPython 3.14.9: fixed by 0901ad4f on the 3.14 branch, 52 commits after v3.14.9, in no release yet.
    "CVE-2026-114583": (ACCEPT, "2027-01-22", "tarfile is never loaded (test_a_run_never_loads_a_module_with_"
                                              "an_advisory, on 3.14 once py2scan runs there); upgrade the "
                                              "target image when 3.14.10 ships"),
}


def request(url, body=None):
    headers = {"User-Agent": "py2scan-advisories", "Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data, headers), timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def tag_commit(version):
    """The commit CPython's release tag vVERSION points to."""
    target = request(CPYTHON + "/ref/tags/v" + version)["object"]
    while target["type"] == "tag":
        target = request(CPYTHON + "/tags/" + target["sha"])["object"]
    return target["sha"]


def read_env(path):
    label = os.path.basename(path)[len("env-"):-len(".txt")]
    pins = []
    with open(path) as f:
        for line in f:
            name, _, version = line.strip().partition("==")
            if name and version:
                pins.append((label, name, version))
    return pins


def query(name, version):
    if name == "python":
        return {"commit": tag_commit(version)}
    return {"package": {"name": name, "ecosystem": "PyPI"}, "version": version}


def fixed_versions(vuln, name):
    fixed = set()
    for affected in vuln.get("affected", []):
        package = affected.get("package", {}).get("name", "").lower()
        for rng in affected.get("ranges", []):
            if package == name.lower() or (name == "python" and rng.get("type") == "GIT"):
                fixed.update(e["fixed"][:12] if rng.get("type") == "GIT" else e["fixed"]
                             for e in rng.get("events", []) if "fixed" in e)
    return fixed


def collect(pins):
    batch = request(OSV + "/querybatch", {"queries": [query(name, version) for _, name, version in pins]})
    with open(os.path.join(OUT, "querybatch.json"), "w") as f:
        json.dump(batch, f, indent=1, sort_keys=True)
    rows = {}
    for (env, name, version), result in zip(pins, batch["results"]):
        for hit in result.get("vulns", []):
            vuln = request(OSV + "/vulns/" + hit["id"])
            with open(os.path.join(OUT, hit["id"] + ".json"), "w") as f:
                json.dump(vuln, f, indent=1, sort_keys=True)
            ids = sorted(set([vuln["id"]] + vuln.get("aliases", [])))
            cves = [i for i in ids if i.startswith("CVE-")]
            row = rows.setdefault((env, name, version, cves[0] if cves else ids[0]),
                                  {"ids": set(), "summary": "", "fixed": set()})
            row["ids"].update(ids)
            row["summary"] = row["summary"] or " ".join((vuln.get("summary") or vuln.get("details", "")).split())
            row["fixed"].update(fixed_versions(vuln, name))
    return rows


def verdict(ids, today):
    """(decision text, ok) for an advisory's merged ids."""
    key = next((i for i in sorted(ids) if i in TRIAGE), None)
    if key is None:
        return "UNTRIAGED", False
    decision, expires, why = TRIAGE[key]
    if decision not in (UPGRADE, MITIGATE, ACCEPT):
        return "INVALID DECISION " + decision, False
    if datetime.datetime.strptime(expires, "%Y-%m-%d").date() < today:
        return "EXPIRED %s %s" % (decision, expires), False
    return "%s until %s: %s" % (decision, expires, why), True


def main(paths):
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    pins = [pin for path in paths for pin in read_env(path)]
    rows = collect(pins)
    failing = 0
    for (env, name, version, primary), row in sorted(rows.items()):
        text, ok = verdict(row["ids"], datetime.date.today())
        failing += not ok
        print("%-5s %-11s %-9s %-16s fixed %-14s %s | %s\n      %s" % (
            env, name, version, primary, ",".join(sorted(row["fixed"])) or "-",
            " ".join(sorted(row["ids"] - set([primary]))), row["summary"][:80], text))
    print("%d packages and interpreters, %d advisories after merging aliases, %d untriaged or expired" % (
        len(pins), len(rows), failing))
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
