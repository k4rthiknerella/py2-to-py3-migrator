---
target: [python 3.14]
units: {py2scan: ["py2scan/**", "setup.py"]}
test: "pytest"
compat: straddle
---
# Python migration
As of 2026-10-22 · commit a73822b · path: 2.7 -> 3.14

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
(receipt below); the test suite (95 tests) passes on both; flake8 is
clean on both (`max-complexity = 10`, `max-line-length = 100`, see
`setup.cfg`).

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

**Scope, stated per R11:** "environment" here means what py2scan
installs and runs with -- the interpreter and the Python packages, on
both the source (2.7) and target (3.14) side. Out of scope: OS packages
inside the Docker test image (`Dockerfile.test`), and the ten judged-version
interpreters (3.6-3.15) used only as test equipment to verify PY3-STDLIB
/ PY3-BUILTIN facts (R6/R7/R9) -- those never run py2scan's own code or
any package from `requirements.txt`.

**How queried:** every pinned package+version above (runtime and dev; a
build-time tool is a thinner case and is called out separately) was
queried directly against the OSV.dev API
(`POST https://api.osv.dev/v1/query`, `ecosystem: PyPI`, exact pinned
version) on 2026-10-22, aliases (CVE/GHSA/PYSEC for the same advisory)
merged by OSV itself. Interpreter advisories (CPython 2.7.18, CPython
3.14.9) have no equivalent single-query feed; the python.org downloads
page confirmed 3.14.9 (released 2026-10-21) and 2.7.18 as the current
final releases, and specific CVE IDs surfaced by web search were each
cross-checked against the NVD API (`services.nvd.nist.gov`) as the
primary source before being trusted, not taken on the search summary's
word alone.

**What this query can't see:** OSV can lag a very recent disclosure;
it has no record type for "the interpreter itself" the way it does for
a PyPI package, so interpreter coverage here is a web-search-generated
candidate list spot-checked against NVD, not an exhaustive one -- a
systematic pass would instead walk python.org's security-announce
archive release by release, which this triage did not do. Reachability
below is argued from py2scan's own direct `import`/`from` surface
(receipt: `grep` across `py2scan/*.py py2scan/rules/*.py`, listed in
Evidence) plus one level into each dependency's own typical import
graph by inspection, not a traced transitive import of every dependency's
internals.

| Finding | Affects | Reachable in py2scan? | Decision |
|---|---|---|---|
| CVE-2025-27516 / CVE-2024-22195 / CVE-2024-34064 / CVE-2024-56326 (Jinja2 sandbox breakout via `attr`/indirect `format`, HTML attribute injection via `xmlattr`) | Jinja2 2.11.3 (2.7-side pin only; 3.x-side 3.1.6 has no OSV records) | No. All four need either a user-controlled *template string* or the `xmlattr`/`attr` filter. `py2scan/report.py` renders one hardcoded template string (`_HTML_TEMPLATE`) with `Environment(autoescape=True)`; `grep` confirms no `xmlattr`, `attr(`, or dynamic filter selection anywhere in the file. Untrusted data (scanned file paths, source lines, finding messages) only ever flows in as autoescaped context *values*, never as template source. | Accept, no fix needed -- not reachable. Proposal, pending owner acceptance (R11). |
| CVE-2025-71176 / GHSA-6w46-j5rx-g56g (pytest predictable `/tmp/pytest-of-{user}`, local DoS/privilege-escalation, fixed in pytest 9.0.3) | pytest 4.6.11 (2.7-side, dev-only) and pytest 8.4.2 (3.x-side, dev-only) | Code path does execute (`tmp_path`/`tempfile.mkdtemp()` fixtures are used throughout `tests/`), but the attacker precondition (another untrusted local account racing to pre-create/symlink that directory on the *same* machine) doesn't hold in this repo's current usage -- a solo-maintainer local/Docker/CI run, no other local principals (same framing as R4/R9: describes where this runs today). | 3.x side: upgrade to pytest>=9.0.3 -- cheap, no 2.7 constraint on that side, no reason to carry a fixed bug. 2.7 side: no fix exists or ever will (pytest dropped 2.7 support after the 4.x line) -- accept, pending owner acceptance (R11), no expiry (there is no future pytest release to re-check against). |
| CVE-2026-7210 (expat/`xml.etree` hash-flooding), CVE-2026-19445 (SSL `sni_callback` use-after-free), CVE-2026-19553 (cert verification bypass in `wrap_bio()`), CVE-2026-4786 (`webbrowser.open()` RCE), CVE-2026-5713 (asyncio introspection / profiling.sampling privilege escalation), CVE-2026-3298 (Windows `asyncio.ProactorEventLoop` buffer overflow), CVE-2026-11972/CVE-2026-11940 (`tarfile` streaming/filter bypass), CVE-2026-15308 (`html.parser` CPU DoS), CVE-2026-6879 (`Element.findall`/`iterfind` quadratic time) | CPython interpreter, various versions overlapping 2.7.18 and/or 3.14.x per-CVE ranges (see NVD for exact ranges; not re-derived here) | No for any of these through py2scan's own code: py2scan's direct import surface is `collections`, `concurrent.futures`, `jinja2`, `parso`, `click`, `errno`, `functools`, `io`, `json`, `os`, `re`, `stat`, `subprocess`, `sys`, `tokenize`, `yaml` -- no `xml`, `ssl`, `socket`, `webbrowser`, `asyncio`, `tarfile`, `zipfile`, or `html.parser` anywhere, and none of py2scan's dependencies (click, Jinja2, MarkupSafe, PyYAML, six, parso) pull those subsystems in for py2scan's usage of them (`yaml.safe_load`, not `yaml.load`; Jinja2's `Environment(autoescape=True)` with no XML/network extensions). | Accept, no fix needed -- not reachable through py2scan. Proposal, pending owner acceptance (R11). Each CVE ID here was individually confirmed real against NVD (not taken on a web search summary's word), but the *list itself* is not claimed exhaustive -- see "what this query can't see" above. |
| CVE-2026-12003 (Windows-only VPATH uncontrolled search path, in-tree builds; fixed in 3.14.7) | CPython 3.14.0-3.14.6, Windows in-tree builds only | No. Needs building CPython from source in an in-tree layout on Windows; py2scan's users install Python normally (python.org installer, a distro package, or `uv`/`pyenv`), never build CPython itself. Also moot at the recommended pin: 3.14.9 already has this fix. | Accept, no fix needed -- not reachable, and already fixed in the recommended target patch anyway. |
| Historical 2.7-line CVEs from pre-2.7.18 CPython (CVE-2017-1000158, CVE-2016-5636, CVE-2018-1000802, CVE-2018-1000030, etc.) | CPython before 2.7.12-2.7.14; **not 2.7.18**, the only 2.7.x release and the one actually pinned here | N/A -- already fixed in 2.7.18 by version, listed only because a web search surfaces them under "Python 2.7" broadly; excluded from the findings above since they don't affect the pinned patch. | No decision needed. |

**Action taken from this pass:** bumped `requirements-dev.txt`'s 3.x-side
pytest pin from `8.4.2` to `9.0.3`, verified it installs cleanly and all
95 tests still pass under Python 3.14 (Evidence below). No other pin
changes indicated. All "accept" rows above remain proposals awaiting the
repo owner's explicit acceptance per R11 -- they are not recorded as
closed decisions just because this one dependency bump was mechanical
and low-risk enough to apply directly.

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

## Decisions
None accepted yet. The security triage above proposes several
accept-as-is rows and one dependency bump; all are pending the repo
owner's explicit acceptance (R11) and are not recorded here as closed
until that happens.
