---
target: [python 3.14]
units: {py2scan: ["py2scan/**", "setup.py"]}
test: "pytest"
compat: straddle
---
# Python migration
As of 2026-10-23 · commit 1a9359a · path: 2.7 -> 3.14

py2scan migrates itself (not the codebases it scans) from its historical
Python 2.7 runtime to Python 3.14, straddling both for as long as any
2.7-only user needs it. "Target" above is py2scan's own interpreter, a
separate question from the Python 3 versions py2scan *judges other
codebases against* (3.6 through 3.15, via `--py3`; see README.md and
py2scan/versions.py). The ladder below tracks py2scan's own readiness,
not any scanned codebase's.

## Units
| Unit | Owner | Runtime today | Effective target | Step | Level | Blockers (auto / manual) | Size | Next |
|---|---|---|---|---|---|---|---|---|
| py2scan | k4rthik.nerella@gmail.com | 2.7.18 (straddled with 3.14) | 3.14.9 | 1/1 | L4 Verified | 0 / 0 | S | `flip` prepared on `py-migrate/py2scan-flip` (commit adcedd4); not merged, not pushed |

## Path
1. **2.7 -> 3.14** (single step, no bridge release needed: py2scan has no
   framework/runtime major coupling, only its own interpreter and a short
   dependency list). No waves: one unit, no import graph.

## Blockers
### py2scan
None open. `.py-migrate/compile_check.py` passes on both interpreters
(receipt below); the test suite (136 tests) passes on both (134 passed,
2 skipped under 2.7.18 -- the skips are the two permission-bit tests
that root inside Docker bypasses, same as always); flake8 is clean on
both (`max-complexity = 10`, `max-line-length = 100`, see `setup.cfg`).

## Dependencies

Runtime (`requirements.txt`, also `install_requires` in `setup.py`):

| Package | Pinned (2.7 side) | Pinned (3.x side) | Supports 3.14? | Source |
|---|---|---|---|---|
| click | 7.1.2 | 8.5.0 | yes | PyPI wheels published for 3.14 |
| Jinja2 | 2.11.3 | 3.1.6 | yes | PyPI wheels published for 3.14 |
| MarkupSafe | 1.1.1 | 3.0.4 | yes | PyPI wheels published for 3.14 |
| PyYAML | 5.4.1 | 6.0.3 | yes | PyPI wheels published for 3.14 |
| futures | 3.3.0 | n/a (stdlib `concurrent.futures`) | n/a | backport only needed under 2.7 |
| six | 1.16.0 | 1.16.0 (same pin both sides) | yes | PyPI wheel |
| parso | 0.7.1 | 0.7.1 (same pin both sides) | yes | pure-Python, see py2scan/parsing.py for why this exact version is load-bearing on both sides |

**Observed, not actioned:** `six` is declared in `requirements.txt` and
`setup.py`'s `install_requires` on both sides but `grep -rn "^import
six\|^from six\|\bsix\."` across `py2scan/*.py` and `py2scan/rules/*.py`
finds zero real uses (the one textual hit, in `ast_rules.py`, is the
substring inside `"posixfile"`, not an import). Left in place rather
than removed on my own authority -- an unused dependency isn't a
migration blocker, and dropping a declared dependency is the kind of
change the skill says to ask before making outside the running
command's declared scope. Flagging for the owner to decide, likely at
`cleanup`.

Dev-only (`requirements-dev.txt`): pytest (4.6.11 / 8.4.2), mock (3.0.5 /
5.2.0), flake8 (3.9.2 / 7.1.1) -- never installed for an end user, only
for running py2scan's own test suite.

Build-time only (`constraints-build.txt`): `cython<3`, pinned so pip's
isolated build env for PyYAML 5.4.1 doesn't pull Cython 3 (which removed
`cython_sources` and breaks that build) on platforms needing a source
build (no PyYAML 5.4.1 aarch64 wheel). Never installed at runtime.

### Security triage (Phase 2 item 4, scoped per ruling R11)

**Superseded pass.** This section replaces the prior triage in full. An
independent check found it incomplete on every count that matters: the
dependency side covered 9 directly-pinned packages, not the full
transitive closure (19 distinct advisories on 6 packages the old pass
never queried at all); the interpreter side used a web-search candidate
list, not a query, and the one proposal with an expiry note
(pytest, 2.7 side) reasoned its way to "no expiry possible" instead of
giving one, which the owner has separately declared incomplete. Every
"accept" row from the superseded pass is void, not carried forward as
valid-pending -- this pass reissues the ones that still hold, each with
the expiry/revisit date R11 requires, as new proposals.

**Scope, stated per R11:** "environment" here means what py2scan
installs and runs with -- the interpreter and the Python packages, on
both the source (2.7) and target (3.14) side. Out of scope: OS packages
inside the Docker test image (`Dockerfile.test`), and the ten judged-version
interpreters (3.6-3.15) used only as test equipment to verify PY3-STDLIB
/ PY3-BUILTIN facts (R6/R7/R9) -- those never run py2scan's own code or
any package from `requirements.txt`.

**How queried -- dependencies:** `pip list --format=json` run inside
`Dockerfile.test`'s actual 2.7.18 image (35 packages: every direct *and*
transitive install, not just the 9 pinned directly in
`requirements.txt`/`requirements-dev.txt`) and inside a matching 3.14.9
build of the same requirements (17 packages -- fewer because
`importlib-metadata`/`zipp`/several other 2.7 backports drop out once
`importlib.metadata` and friends are stdlib). Each package+exact-version
pair was batch-queried against OSV.dev
(`POST https://api.osv.dev/v1/querybatch`, `ecosystem: PyPI`), then every
hit re-fetched via the single-query endpoint to get each advisory's
`aliases` list (a GHSA and a PYSEC ID are routinely the same underlying
advisory under two identifiers) and deduplicated by alias group before
counting "distinct advisories."

**How queried -- interpreter:** NVD's CPE-match endpoint
(`services.nvd.nist.gov/rest/json/cves/2.0?cpeName=cpe:2.3:a:python:python:<version>:*...`),
once for `2.7.18` and once for `3.14.9` -- a single authoritative query
per interpreter version, not a per-CVE lookup or a web-search candidate
list. **Methodological trap found and corrected:** a raw match on this
endpoint is not the same as "this CVE is a CPython vulnerability." NVD's
`cpeMatch` entries carry their own `vulnerable: true/false` flag per
entry; a `false` entry means that CPE is a *required co-occurring
platform*, not the vulnerable product. The 3.14.9 query's 4 raw hits
(CVE-2009-2940, CVE-2009-3720, CVE-2020-29396, CVE-2021-32052) are all
`vulnerable: false` for `python:python` -- they are pygresql, Expat,
Odoo, and Django CVEs whose configuration happens to AND-in "running
under some Python version" as an environment precondition. The 2.7.18
query's 38 raw hits include 3 of the same shape. Filtering on `vulnerable:
true` is what turns a noisy raw match list into the real advisory set;
the first attempt at this interpreter query (the superseded pass) didn't
have this check at all and only got as far as a web-search list because
of it.

**What this query can't see, and a second query that closed the gap:**
NVD's CPE enrichment lags a fresh CVE's own publication by days to
weeks, so a brand-new interpreter CVE can exist in the CVE feed before
the CPE-match query above can find it at all. autosteer-architect named
the fix: OSV.dev also supports querying by commit
(`POST api.osv.dev/v1/query`, `{"commit": <sha>}`), using the exact
commit each release tag points to (resolved via GitHub's API: `v3.14.9`
-> `ead82c07...`, `v2.7.18` -> `8d21aa21...`). Its own blind spot: OSV
maps only some CPython advisories to a commit, so it's a lower bound,
not a replacement for the CPE-match query -- the two methods disagree
in both directions (each finds some the other doesn't), so both are now
run and merged rather than either alone.

**Interpreter results, reconciled:** NVD CPE-match (`vulnerable: true`)
found 35 for 2.7.18, 0 for 3.14.9. OSV-by-commit added `CVE-2026-19672`
and the disputed `CVE-2026-3479` for 2.7.18 (its other 2 hits,
`CVE-2023-27043` and `CVE-2026-4519`, were already in the 35), and
`CVE-2026-114583` for 3.14.9. Merged: **37 for 2.7.18, 1 for 3.14.9** --
both now match autosteer-architect's stated counts exactly. The earlier
"open discrepancy" in this section is closed.

Every genuine 2.7.18-interpreter CVE, plus the one found for 3.14.9, was
checked against py2scan's own exercised stdlib surface (`collections`,
`concurrent.futures`, `errno`, `functools`, `io`, `json`, `os`, `re`,
`stat`, `subprocess`, `sys`, `tokenize` -- the full `grep` receipt is in
Evidence). None of the 37 touch a module py2scan imports (they cluster
in `tarfile`, `webbrowser`, `urllib.parse`, `email`, `plistlib`,
`heapq`, `hmac`, `http.cookies`, `xml.*`, `base64`, `configparser`,
`html.parser`, `shutil`, `pkgutil`, and Windows installer/venv-CLI code
-- none of which py2scan ever imports or invokes); the one that looked
closest, `os.path.expandvars` quadratic cost (CVE-2025-6075), is not
reachable either since py2scan never calls `expandvars`, `expanduser`,
or anything in `shutil` (confirmed by the same `grep`). The 3.14.9
finding, `CVE-2026-114583` (`tarfile.tar_filter` bypass via crafted
symlink entries), is not reachable for the same reason as every other
`tarfile` CVE here: `tarfile` is never imported.

| Finding | Affects | Reachable in py2scan? | Decision | Revisit by |
|---|---|---|---|---|
| CVE-2025-27516 / CVE-2024-22195 / CVE-2024-34064 / CVE-2024-56326 (Jinja2 sandbox breakout via `attr`/indirect `format`; HTML attribute injection via `xmlattr`) | Jinja2 2.11.3 (2.7-side pin; 3.x-side 3.1.6 has zero OSV records, both direct and transitive closure) | No. All four need either a user-controlled *template string*, `jinja2.sandbox.SandboxedEnvironment`, or the `xmlattr`/`attr` filter. `py2scan/report.py` uses a plain `Environment(autoescape=True)` (never `SandboxedEnvironment`) rendering one hardcoded template string; `grep` confirms no `xmlattr`, `attr(`, or dynamic filter selection anywhere in the file. Untrusted data flows in only as autoescaped context values, never as template source. | Accept, not reachable. New proposal (reissues the superseded pass's Jinja2 row with a date). | 2027-04-22: re-run this OSV query against whatever Jinja2 is pinned to then, regardless of whether report.py has changed. |
| 8 distinct pip CVEs (GHSA-4xh5-x5gv-qwph, GHSA-58qw-9mgm-455v, GHSA-5xp3-jfq3-5q8x, GHSA-6vgw-5pg2-w6jp, GHSA-jp4c-xjxw-mgf9, GHSA-mq26-g339-26xf, GHSA-qwm4-qh6w-59xr, GHSA-wf93-45jw-7689 -- archive-extraction path traversal, tar/zip confusion, Mercurial command injection, doubly-encoded index URLs, malicious-entry-point path traversal) | pip 20.0.2, transitively installed into the 2.7 test image (not pinned by py2scan itself); confirmed still present, unfixed, in 20.3.4, the newest pip release that still supports 2.7 at all | No. Every one of these needs `pip install`/`pip download` to process an attacker-controlled package source (a malicious sdist/wheel/VCS URL, or a compromised index). py2scan's own install (`pip install -r requirements.txt`/`requirements-dev.txt`) names exact, pinned, trusted PyPI packages only -- no VCS requirements, no alternate index, no untrusted archive ever reaches pip here. | Accept, not reachable; no fix exists in any 2.7-compatible pip release (checked: 20.0.2 through 20.3.4, the last one, carry the identical 8). | 2027-04-22: re-run against whatever pip is in the test image then. |
| 4 distinct setuptools CVEs (GHSA-5rjg-fvgr-3xxf path traversal in `PackageIndex.download`, GHSA-cx63-2mw6-8hw5 command injection via package URL, GHSA-h35f-9h28-mq5c MANIFEST.in exclusion bypass via NFC/NFD collision, GHSA-r9hx-vwmv-q579 ReDoS) | setuptools 44.1.0, transitive; confirmed still present, unfixed, in 44.1.1, the newest 2.7-compatible release | No, same shape as pip above -- each needs installing or building from an attacker-controlled package/sdist. py2scan's build/install never does. | Accept, not reachable; no fix exists in any 2.7-compatible setuptools release. | 2027-04-22 |
| 1 wheel CVE (GHSA-qwmp-2cf2-g9g6, ReDoS) | wheel 0.34.2, transitive; confirmed still present, unfixed, in 0.37.1, the newest 2.7-compatible release | No, same shape. | Accept, not reachable; no fix exists in any 2.7-compatible wheel release. | 2027-04-22 |
| 1 zipp CVE (GHSA-jfmj-5v4g-7637, DoS via a crafted zip) | zipp 1.2.0, transitive (pulled in by `importlib-metadata`, itself a 2.7-compat backport some dev tool needs); 1.2.0 is already the newest 2.7-compatible zipp release -- no newer version to check | No. py2scan never imports `importlib.metadata` or `zipp`; nothing in py2scan's own code ever asks either to open a zip. | Accept, not reachable; no fix exists in any 2.7-compatible zipp release (there is none newer at all). | 2027-04-22 |
| CVE-2025-71176 / GHSA-6w46-j5rx-g56g (pytest predictable `/tmp/pytest-of-{user}`) | pytest 4.6.11 (2.7-side, dev-only) | `tmp_path`/`tempfile.mkdtemp()` fixtures do execute throughout `tests/`, but the attacker precondition (another untrusted local account on the same machine racing to pre-create/symlink that path) doesn't hold for this repo's current usage (solo-maintainer local/Docker/CI, no other local principals). | Already handled on the 3.x side (bumped to 9.0.3, commit c133712). 2.7 side: accept, no fix exists in the 2.7-compatible pytest line (4.x is the last one; pytest dropped 2.7 support before 9.0.3). | 2027-04-22: re-check whether any 2.7-compatible pytest release ever backports this (unlikely, but this is the scheduled check regardless of how unlikely it seems now -- that's the point of a revisit date instead of reasoning "no expiry possible"). |
| 37 genuine CPython 2.7.18 interpreter CVEs (35 via NVD CPE-match + CVE-2026-19672 and the disputed CVE-2026-3479 via OSV-by-commit; full list in Evidence) | CPython 2.7.18 itself | No, for any of them, through py2scan's own exercised stdlib surface (`collections`, `concurrent.futures`, `errno`, `functools`, `io`, `json`, `os`, `re`, `stat`, `subprocess`, `sys`, `tokenize`) -- see paragraph above for the module-by-module check, including the one (`os.path.expandvars`) that shares an imported module. | Accept, not reachable. New proposal (reissues the superseded pass's interpreter row, now from NVD+OSV-by-commit queries instead of a web-search list, with a date). | 2027-04-22: re-run both the NVD CPE-match and OSV-by-commit queries against whatever 2.7.18 patch/successor is still in use then. |
| CVE-2026-114583 (`tarfile.tar_filter` bypass via crafted symlink entries) -- found via OSV-by-commit, not NVD CPE-match (enrichment lag); matches autosteer-architect's stated "1 open advisory for 3.14.9" exactly | CPython 3.14.9 | No. `tarfile` is never imported by py2scan (same as every other `tarfile` CVE in the 2.7.18 row above). | Accept, not reachable. New proposal. | 2027-04-22: re-run OSV-by-commit against whatever 3.14.9 patch/successor's tag commit is current then. |

**Action taken from this pass:** none beyond the pytest 3.x bump already
committed (c133712, before this pass). Confirmed empirically rather than
assumed: the newest 2.7-compatible release of pip, setuptools, and wheel
each still carries the identical advisory set as the version actually
installed, and zipp's installed version is already the newest
2.7-compatible one -- so there is no mechanical dependency bump available
anywhere in this pass, only accept proposals. Every accept row above is a
new proposal pending the owner's explicit acceptance per R11, each dated;
none of the superseded pass's accept rows carry forward as valid on their
own.

## Runtime surfaces
| File | Pins | Unit | Changes at flip |
|---|---|---|---|
| `setup.py` | `python_requires` excludes every 3.x minor except 3.14; `install_requires` version markers on `python_version` | py2scan | Drop the 2.7 markers and the `<3` pins at `cleanup`, once no 2.7 user remains |
| `requirements.txt` / `requirements-dev.txt` | Same `python_version` markers, mirrored | py2scan | Same as above |
| `Dockerfile.test` | `FROM python:2.7.18-slim` -- the *source-side* test image; test equipment, not a deployed runtime surface (R4/R9) | py2scan | Retired at `cleanup`, not at `flip` |
| console entry point (`py2scan=py2scan.cli:main`) | Whatever interpreter `pip install`/`pipx` resolves at install time -- not pinned by py2scan itself | py2scan (end users) | Nothing to change; this is the property R9 requires to hold under either interpreter already |

No scheduler, CI, or cloud/IaC runtime surface exists for py2scan itself
(R4: it runs nowhere outside this repository today; R9: that describes
today's execution, not its open-source users, who may run it under
either interpreter with no network).

## Stored data
None. py2scan is a stateless scanner: it reads source files and a config
file from disk and writes a report (text/JSON/HTML) to stdout or a given
path. No cache, session, queue, or pickle format crosses the flip.

## Flip (prepared, not shipped)

Branch `py-migrate/py2scan-flip`, commit `adcedd4`, forked from this
branch at `8803218`. Drops py2scan's own Python 2.7 *runtime* support
only -- `python_requires=">=3.14"`, and the `python_version<"3"` pins
removed from `requirements.txt`/`requirements-dev.txt`/`setup.py`. It
deliberately does **not** touch `parso==0.7.1` or the PY3-* rules:
py2scan's ability to *scan* Python 2.7 source is the product and stays
regardless of which interpreter runs py2scan itself -- those are two
different "2.7" questions (see this file's header note). Verified
clean (97 tests, flake8) under Python 3.14 with no source changes, only
metadata; not tested under 2.7 on purpose, since the branch's whole
point is declaring that unsupported going forward.

**Canary:** py2scan isn't released yet, so there's no download-by-
interpreter-version signal to watch. Recommended sequencing before this
branch ever merges: ship one more straddling release that adds a
`DeprecationWarning` when py2scan itself runs under 2.7, then watch for
user reports for some number of releases the owner picks -- not a date
this triage can compute, since it depends on real adoption data that
doesn't exist yet.

**Rollback:** revert the commit (or restore the three `python_version`
markers and the three 2.7-side pins). The straddle commits stay in
history regardless, so re-enabling py2scan's own 2.7 runtime support
later is a revert, not a rewrite.

Never merged into this branch or `main`; never pushed.

## Breaking changes in scope
| Step | Change | Source link | Searched with | Hits |
|---|---|---|---|---|
| 2.7 -> 3.14 | Every syntax/semantic break py2scan itself might hit, same list its own rules check for scanned code (print stmt, exec stmt, backticks, `<>`, bare except-comma, raise-comma, octal literals, `L` suffix, dict iterators, removed builtins, removed/renamed stdlib, `__metaclass__`, tuple-param unpacking, `async`/`await` reservation, `True`/`False` as keywords) | Each rule's own docstring/comment in `py2scan/rules/ast_rules.py` and `py2scan/rules/token_rules.py` cites its primary source (PEP 3107/3109/3110/238/3151/3108/492, What's New per version) | `.py-migrate/compile_check.py` against py2scan's own 22 files on both interpreters; py2scan's own test suite running on both interpreters (it is, unusually, both the tool and one of its own test subjects) | 0 (clean on both sides) |
| 3.x patch range (3.6-3.15) that py2scan *judges* scanned code against | Not a breaking change *to py2scan*; this is PY3-STDLIB/PY3-BUILTIN's subject matter, derived empirically per R6/R7/R8/R10 from real final-release interpreters (Docker `python:X-slim` images), not from py2scan's own migration | n/a (different question, see header note) | n/a | n/a |

## Evidence
| Date | Commit | Unit | Step | Level | Command | Result |
|---|---|---|---|---|---|---|
| 2026-10-22 | 8803218 | py2scan | 2.7->3.14 | L2 | `python .py-migrate/compile_check.py .py-migrate/out/files` (target, 3.14.3 via uv venv) | `checked 22, failed 0, unreadable 0`, exit 0 |
| 2026-10-22 | 8803218 | py2scan | 2.7->3.14 | L2 | same, source (2.7.18, Docker `py2scan-test-sonnet-worker`) | `checked 22, failed 0, unreadable 0`, exit 0 |
| 2026-10-22 | 8803218 | py2scan | 2.7->3.14 | L3 | `pip install -r requirements-dev.txt` resolves on both a 2.7.18 Docker image and a 3.14.3 uv venv, macOS arm64 / Linux x86_64 | Installs cleanly both sides, no resolver conflicts |
| 2026-10-22 | 8803218 | py2scan | 2.7->3.14 | L4 | `pytest -q` under Python 2.7.18 (Docker) | `95 passed` |
| 2026-10-22 | 8803218 | py2scan | 2.7->3.14 | L4 | `pytest -q` under Python 3.14.3 (uv venv) | `95 passed` |
| 2026-10-22 | 8803218 | py2scan | 2.7->3.14 | L3/L4 | `flake8` under both interpreters (`max-complexity=10`, `max-line-length=100` from `setup.cfg`) | clean, exit 0, both sides |
| 2026-10-22 | 8803218 | py2scan | 2.7->3.14 | security (item 4) | OSV.dev query per pinned package+version (runtime + dev), merged aliases | See Security triage table above; 1 proposed dependency bump (pytest dev pin) |
| 2026-10-22 | 8803218 | py2scan | 2.7->3.14 | security (item 4) | `grep` for py2scan's own direct import surface; NVD spot-checks of CVE IDs surfaced by web search | See Security triage table; reachability argued, not exhaustively traced transitively |
| 2026-10-22 | c133712 | py2scan | 2.7->3.14 | security (item 4) | bumped dev-only pytest pin 8.4.2 -> 9.0.3 (3.x side); `pip install -r requirements-dev.txt` then `pytest -q` and `flake8 py2scan tests setup.py`, Python 3.14.3 (uv venv) | Installs clean, `95 passed`, flake8 exit 0 |
| 2026-10-22 | 63dec51 | py2scan | 2.7->3.14 | L4 | added PEP 263 BOM handling (`py2scan/encoding.py`) + 2 tests; `pytest -q` and `flake8` both interpreters | `97 passed` both sides, flake8 exit 0 both sides |
| 2026-10-22 | adcedd4 | py2scan | 2.7->3.14 | flip (prepared) | branch `py-migrate/py2scan-flip`: dropped `python_version<"3"` pins, `python_requires=">=3.14"`; `pytest -q` and `flake8`, Python 3.14.3 only (2.7 deliberately not tested -- that's the point of this branch) | `97 passed`, flake8 exit 0 |
| 2026-10-22 | 1cb4a2c | py2scan | 2.7->3.14 | L3 (R5 gap found + closed) | found R5's exit(2)/unreadable-file path had no end-to-end test (only a report.py test feeding a hand-built `ScanResult`); added a scanner-level test (`chmod 0o000`) and a CLI-level test; `pytest -q` and `flake8`, both interpreters (both new tests correctly `skip` under Docker root, which bypasses the permission bits they need) | `99 passed` under 3.14.3; `97 passed, 2 skipped` under 2.7.18 (skips explained, not silent); flake8 exit 0 both sides |
| 2026-10-22 | 5504259 | py2scan | 2.7->3.14 | docs | Committed this file. Receipt: `/Users/karthik/.claude/CLAUDE.md`, re-read into this session's context after compaction, now contains "Exception (owner decision 2026-10-22, AutoSteer Phase 2): in ... py27/sonnet/py2scan ... MIGRATION.md and README.md may be committed." No independent receipt for who made that edit or exactly when, beyond the file's own self-reported date -- observed the file's new content, not a commit log or an attributed message. autosteer-architect's message 541c7e89 is NOT a confirmation that this is the owner's decision: it says "[o]nly the owner can confirm that the exception is the owner's own decision... [a]ny answer comes from the owner in your session, not from me" -- an explicit refusal to confirm, not a confirmation. Correcting an earlier version of this row that misstated that message as a confirmation (flagged by autosteer-architect, trigger T10) | Committed, on the strength of the CLAUDE.md file content itself |
| 2026-10-22 | 2b0f53c | py2scan | 2.7->3.14 | docs | README.md was stale (said py2scan "runs on Python 2.7" and parses with 2.7's own ast/tokenize, true before the parso rewrite, false now; "do not upgrade" dependencies; listed 14 rules, not 17; no mention of --py3/--py3-interpreter). Corrected and committed under the same exception | Committed |
| 2026-10-22 | a73822b | py2scan | 2.7->3.14 | rule correctness (R1, found via AutoSteer CI) | AutoSteer CI's automated per-commit run (new as of this notice) caught `tests.test_rules::test_ne_op_is_found` failing under real Python 3.14.9 while this branch's own commits had only ever been checked against 3.14.3. Root cause: native `tokenize` lexing of `<>` as one OP token vs. two adjacent ones is not a stable per-version fact -- checked all ten judged minors' current patch plus two different 3.14 patches via `docker run python:X-slim`: only 3.12.15 and 3.14.3 keep it combined, every other one (3.6.15, 3.7.17, 3.8.20, 3.9.25, 3.10.22, 3.11.17, 3.13.17, 3.14.9, 3.15.0rc3) splits it. Fixed `check_ne_op` to match both shapes; added two host-independent tests (direct token-list construction, not dependent on the test-runner's own tokenize behavior) | Verified clean (`pytest -q` + `flake8`) under real 3.14.9 via `python:3.14-slim` (AutoSteer's exact environment), plus 3.14.3 and 2.7.18: `101 passed` (3.14.3), `99 passed, 2 skipped` (2.7.18 and 3.14.9 under Docker root) |
| 2026-10-22 | a73822b-cbdebe4-f6ace63-0702387 | py2scan | 2.7->3.14 | R1 violated, found by independent check (item 1: `ur"..."` tokenize loss; item 2: `print(x, file=y)` under `print_function`) | Independent check against the real MoinMoin 1.9.11 / Trac 1.4.4 sdists and the real CPython 2.7.18 stdlib found two compounding R1 violations, already fixed in commits predating this check's own notice: (1) native `tokenize` raises `TokenError` on a `ur"..."` literal on a Python 3 host, silently losing every token-based finding for the rest of that file (fixed: blank the 2-char prefix to same-width spaces before tokenize, plus incremental token collection as defense-in-depth; added `PY3-UR-STRING` so the construct itself is still caught by the AST pass regardless); (2) parso's static "2.7" grammar has no concept of `__future__` imports, so `print(x, file=y)` -- valid under `print_function` -- hard-fails parso's grammar (fixed: textual pre-scan for the future import, then same-width `print`->`pr1nt` substitution before the grammar parse only) | Byte-for-byte identical parse/scan behavior verified against the real repro files (`MoinMoin/config/multiconfig.py`, `trac/web/main.py`) on real CPython 2.7.18, 3.14.3, and 3.14.9 (Docker) |
| 2026-10-22 | c085781 | py2scan | 2.7->3.14 | PY3-BUILTIN false positives, found by independent check (item 3) | 165+ findings on the real CPython 2.7.18 stdlib were attribute-access or keyword-argument names matching a builtin's spelling (repro: `aifc.py:480`, `chunk.file.read(1)` -- `file` there is the attribute half of a `.` trailer, not a reference). `check_builtin`'s leaf walk had no exclusion for either shape (distinct from function *parameter* names, already excluded). Added `_is_attribute_name`/`_is_keyword_argument_name` structural checks; extracted the pre-existing scope-shadowing loops into `_resolve_shadowing_scopes` to keep `check_builtin` under flake8's complexity gate after adding the check | Scanned the real stdlib before/after: 823 -> 581 PY3-BUILTIN findings (242 false positives removed, 0 new, 0 regressions -- spot-checked that genuine bare uses like `file(...)` in `pstats.py` and `buffer(...)` in `hashlib.py` are still flagged); full suite + flake8 clean on 2.7.18 (Docker), 3.14.3 (uv venv), and real 3.14.9 (Docker) |
| 2026-10-22 | 6fbefe3 | py2scan | 2.7->3.14 | JSON byte-parity, found by independent check (item 4) | `json.dumps(to_json(...))` had no `sort_keys`. `to_json`'s and `Finding.to_dict()`'s dict literals always write the same keys in the same source order, but that only guarantees matching serialized order on Python 3.7+ -- a plain dict's iteration order on 2.7 is hash-bucket layout, not source order, so the identical literal produced different JSON bytes per host even for the trivial repro (a directory holding one file, `x = 1`). List ordering was already deterministic (scanner.py sorts the walk; findings sort by `Finding.key()`), so `sort_keys=True` on the one `json.dumps` call was the whole fix | Byte-identical JSON confirmed on: the trivial repro; the real MoinMoin 1.9.11 and Trac 1.4.4 corpora (2.7.18 vs. 3.14.3). The corpora runs also resolved the separately reported "49 findings differ between the two" -- a side effect of items 1-3's host-dependent bugs, not a fourth distinct bug: once those made finding *content* match, the only remaining difference was key order |
| 2026-10-22 | fe75125 | py2scan | 2.7->3.14 | security (item 4/item 5 under R11), superseded the prior security triage pass | Full `pip list` transitive closure queried (35 packages, 2.7-side; 17, 3.x-side; not just the 9 directly-pinned packages the superseded pass checked) via OSV.dev batch query, alias-deduplicated -- 19 distinct advisories on 6 packages (Jinja2, pip, pytest, setuptools, wheel, zipp), matching the independent check's stated "19" exactly. Interpreter advisories re-queried via NVD's CPE-match endpoint instead of a web-search list, with a newly-found-and-corrected methodological trap: NVD `cpeMatch` entries carry their own `vulnerable: true/false` flag, and ignoring it (as the superseded pass effectively did by relying on web search instead of this endpoint) lets an unrelated product's CVE (pygresql, Odoo, Django -- each merely requiring "some Python version" as an environment precondition) masquerade as a CPython CVE | 35 genuine 2.7.18 CVEs after `vulnerable:true` filtering (vs. the independent check's stated 37); 0 genuine 3.14.9 CVEs found via NVD -- left open and reported to autosteer-architect rather than guessed at |
| 2026-10-22 | 7517bf8 | py2scan | 2.7->3.14 | security (item 5 under R11), discrepancy closed | autosteer-architect named the fix for the open discrepancy above: OSV.dev's query-by-commit (`{"commit": <sha>}`, using the real sha each release tag points to, resolved via GitHub's API) finds advisories NVD's CPE-match can't see yet (enrichment lag) and vice versa, so both are now run and merged. For 2.7.18: added `CVE-2026-19672` and the disputed `CVE-2026-3479` (its other 2 hits were already in the 35). For 3.14.9: found `CVE-2026-114583` (`tarfile.tar_filter` bypass via crafted symlinks) | Merged counts: 37 for 2.7.18, 1 for 3.14.9 -- both now match autosteer-architect's stated figures exactly. Neither new finding is reachable (`tarfile`/`pkgutil` are never imported by py2scan, same `grep` receipt as the rest of this table) |
| 2026-10-23 | 37ec7c2 | py2scan | 2.7->3.14 | R1 violated, found by AutoSteer CI (new hostile/stdlib checks) | Two more R1 gaps the backstop couldn't cover (same root cause as always: it only speaks for py2scan's own running version). (1) `PY3-BAD-ESCAPE`: real CPython 2.7's `json/__init__.py` docstring writes literal "\uXXXX" text; Python 2's plain str never treats `\u`/`\U`/`\N` as escapes, Python 3's always does, and "XXXX" isn't valid hex -- a SyntaxError on every judged version. New AST rule, excludes `r"..."`/`b"..."` prefixes, only flags incomplete escapes (not well-formed ones, a separate meaning-drift question). (2) `PY3-DEEP-NESTING`: CPython 3.6-3.8's old pgen2 compiler has a fixed symtable stack depth that 3.9's PEG parser removed; empirically bounded via `docker run python:X-slim` across depths 50-200 on every judged minor (3.6/3.7/3.8 fail around 95-99, everything else compiles 200 fine) -- new token rule flags above a conservative threshold (50) for 3.6-3.8 only | Real stdlib's `json` module: byte-identical findings and JSON output between 2.7.18 and 3.14.3 (closes the separately reported "stdlib JSON differs" symptom too). 150-deep nested-parens hostile case: flagged for 3.6/3.7/3.8 only, matching real per-version compile results. Full suite + flake8 clean on 2.7.18, 3.14.3, real 3.14.9 |
| 2026-10-23 | f0388aa | py2scan | 2.7->3.14 | R5 violated, found by AutoSteer CI (hostile/non_utf8_name) | A file named with a raw non-UTF-8 byte crashed the *entire* scan under Python 2.7 with an unhandled `UnicodeDecodeError` from `json.dumps()` (Python 2's json encoder decodes `str` dict keys/values as UTF-8), not an unreadable-file entry for just that file -- R5's "never dropped silently" broken for every other file in the same run too. Fix is display-boundary only, not discovery/scanning: `encoding.display_path()` decodes with `errors="replace"` on Python 2 only, applied at the three places a path becomes output (JSON, `Finding.to_dict()`, text echo, `render_html`'s displayed name) and nowhere that opens a file (`render_html` opens with the original bytes first, displays the sanitized form separately) | Verified end to end on real 2.7.18 (Docker): `--format json`, `--format text`, and `--html` all now report the file's real finding instead of crashing. New integration test passes on Linux under both 2.7.18 and real 3.14.9, skips cleanly on macOS (which refuses to create the file at all). Full suite + flake8 clean on 2.7.18, 3.14.3, real 3.14.9 |
| 2026-10-23 | 1a9359a | py2scan | 2.7->3.14 | R2 violated, found by AutoSteer CI (hostile/non_utf8_name, next notice) | f0388aa fixed Python 2's crash but left Python 3 untouched on the reasoning that os.walk already returns valid unicode there -- true, but incomplete: it gets there via surrogateescape, round-tripping the byte through a lone surrogate, not through the same U+FFFD Python 2's "replace" produces. `json.dumps()` doesn't raise on a lone surrogate, so nothing crashed, but the identical real file produced different JSON bytes per host. Fixed: `display_path` on Python 3 now undoes the surrogateescape round-trip (encode utf-8/surrogateescape) and re-applies the same utf-8/"replace" step, converging both hosts on the same text. Also fixed the Python-2-only test AutoSteer flagged as asymmetric (skipped entirely on 3.14) -- rewrote it to assert the identical result on both interpreters instead of skipping one | Byte-identical JSON confirmed on real CPython 2.7.18 and real 3.14.9 (Docker) for the actual repro. Full suite + flake8 clean on all three; the rewritten test passes on both sides with no skip |

## Decisions
None accepted yet. The security triage's first pass proposed several
accept-as-is rows with no expiry date; the owner declared that pass
incomplete for lacking one, so none of those rows carry forward as
valid-pending -- they are void, not decided either way. The current
pass (Dependencies > Security triage above) reissues the ones that
still hold reachability-wise, each with an explicit 2027-04-22 revisit
date, as new proposals. All are pending the repo owner's explicit
acceptance (R11) and are not recorded here as closed until that
happens.
