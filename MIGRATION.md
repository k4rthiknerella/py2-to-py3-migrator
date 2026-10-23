---
compat: straddle
test: "docker build -q -f Dockerfile.test -t py2scan-test . && docker run --rm -v \"$PWD\":/app -w /app py2scan-test python -m pytest -q -p no:cacheprovider tests"
---
# Python migration
As of 2026-10-22 · commit 0e39731 · path: 2.7.18 → 3.14

`compat: straddle` is set explicitly (default detection would say `direct` for a
single-owner CLI tool) because the architect's spec requires byte-identical JSON
between the source and target interpreters during the transition, which only
makes sense if both sides keep running.

`test` is set explicitly because the project's test command needs a Docker
wrapper around pytest; no bare `tox`/`nox`/`pytest` invocation runs this
project's tests standalone (PyYAML 5.4.1 needs a build constraint — see
Dependencies). It is the *source*-side command; a target-side counterpart does
not exist yet (see Blockers).

`target` and `units` are not listed because they match detection: target is
Python 3.14 (the newest Python in bugfix support for 6+ months as of
2026-10-22 — Python 3.14 entered bugfix on 2025-10-07, Python 3.15 entered
bugfix on 2026-10-09, four months before today; source: [devguide.python.org/versions](https://devguide.python.org/versions/)).
Units is the single `py2scan` package rooted at this repo's `setup.py`.

**R6 note (owner decision, 2026-10-22):** this `target` is the version py2scan
*itself* runs on, which R6 confirms is a separate question from which Python
3.x version(s) py2scan *judges scanned code's readiness against* (3.6–3.15,
user-selectable, all by default). The rules-engine work for R6 is scoped under
Breaking changes in scope and is not yet implemented — see Blockers.

## Units
| Unit | Owner | Runtime today | Effective target | Step | Level | Blockers (auto / manual) | Size | Next |
|---|---|---|---|---|---|---|---|---|
| py2scan | Karthik Nerella | 2.7.18 | 3.14 | 2.7.18 → 3.14 | L2 | 3 auto / 2 manual | L | `fix py2scan` |

L2 is proved by `.py-migrate/compile_check.py`, committed, run on both sides —
see Evidence. No consumers import py2scan as a library (it is a CLI-only
unit), so there is no import-graph wave ordering to apply.

## Path
One step: 2.7.18 → 3.14, straddling. There is no bridge release to find: the
version floor py2scan's own code needs is driven entirely by stdlib/library
availability, not by a framework major with its own multi-Python support
window (py2scan depends on no framework, only `click`, `Jinja2`/`MarkupSafe`,
`PyYAML`, and the `futures`/`six` backports). The library-major bumps this
step forces (PyYAML; see Dependencies) are bundled into this single step
rather than given their own path entry, per the architect's explicit
authorization to change dependency majors the target needs without asking.

Waves: none — one unit, no import graph.

## Blockers
### py2scan
- `py2scan/rules.py` (9 functions: `check_print`, `check_exec`,
  `check_backtick`, `check_raise_comma`, `check_dict_iter`, `check_metaclass`,
  `check_division`, `check_builtin_use`, `check_stdlib_import`) and
  `py2scan/scanner.py:scan_file`'s `ast.parse` call · **the core blocker**:
  every one of these reads a Python 2.7 `ast` tree, and under Python 3.14,
  `ast.parse`/`compile()` raise `SyntaxError` on the Python-2-only syntax
  py2scan exists to detect (verified: `ast.parse('print "hi"')` under 3.14 →
  `SyntaxError: Missing parentheses in call to 'print'`), and `ast.Print`,
  `ast.Exec`, `ast.Repr` do not exist as attributes of Python 3.14's `ast`
  module at all (verified: `hasattr(ast, 'Print')` → `False` on 3.14) · fix is
  manual — see Strategy below, this is the item `fix` must design before
  touching code · Size L.
- `py2scan/encoding.py:5` · `from lib2to3.pgen2.tokenize import detect_encoding`
  · `lib2to3` was removed from the stdlib in Python 3.13 (verified:
  `ModuleNotFoundError: No module named 'lib2to3'` on 3.14.7) · auto-fixable:
  Python 3's own `tokenize` module has had `detect_encoding` natively since
  3.2 and behaves identically (verified side by side on both the cookie and
  no-cookie cases) · Size S.
- `py2scan/rules.py:check_long_suffix` (reads `tokenize.NUMBER` tokens for a
  trailing `L`/`l`) · under Python 3's tokenizer, `10L` lexes as two tokens,
  `NUMBER '10'` then `NAME 'L'`, not one `NUMBER '10L'` token (verified) · fix
  is mechanical (match a `NUMBER` token immediately followed, with no gap, by
  a bare `NAME` token `'L'` or `'l'`) but changes the rule's shape, so it's
  manual with a test, not purely auto · Size S.
- `py2scan/report.py:summarize` → `cli.py`'s `json.dumps(summary)` · **not
  byte-identical across interpreters today**, verified: the same
  `Finding.to_dict()` dict literal serializes with different key order on
  2.7 (`{"line":...,"message":...,"rule":...,"file":...,"severity":...}`,
  hash-order) vs 3.14 (`{"file":...,"line":...,"rule":...,"severity":...,"message":...}`,
  insertion order) because CPython 2.7 dict iteration order is hash-bucket
  order, not insertion order, and 3.7+ guarantees insertion order. This is a
  real defect against item 2b ("the same input gives byte-identical JSON
  under 2.7 and under the target"), recorded per R1's instruction, not an
  accepted divergence · auto-fixable: `json.dumps(..., sort_keys=True)` ·
  Size S.
- R6 (owner decision, 2026-10-22): py2scan's rules currently carry no
  per-Python-3-version applicability data. Reporting "which of 3.6–3.15 this
  file is ready for" and "which versions this blocker applies to" needs each
  rule annotated with the version range it is true for, each annotation
  sourced from a primary source and tested against a real interpreter of
  that version. Not started. This is the largest remaining item; it is
  `fix`-phase work, scoped here, not assessed line-by-line yet · Size L.

## Dependencies
| Package | Pinned | Needed for step | Supports it? | Source |
|---|---|---|---|---|
| click | 7.1.2 | source + target | Yes, both (verified: imports under 2.7.18 and 3.14.7 unchanged) | empirical, this session |
| Jinja2 | 2.11.3 | source + target | Yes, both (verified) | empirical, this session |
| MarkupSafe | 1.1.1 | source + target | Yes, both (verified) | empirical, this session |
| PyYAML | 5.4.1 | source | Yes, 2.7 only, and only with the existing `constraints-build.txt` (`cython<3`) — already documented in this repo | project's own `constraints-build.txt` + empirical |
| PyYAML | 5.4.1 | target | **No** — fails to build on 3.14.7 even with `cython<3`; `AttributeError: 'build_ext' object has no attribute 'cython_sources'` regardless of Cython pin (verified) | empirical, this session |
| PyYAML | 6.0.3 | target | Yes (verified: installs and imports cleanly on 3.14.7, no build-from-source needed) | empirical, this session |
| futures | 3.3.0 | source only | N/A on target — `concurrent.futures` has been in the stdlib since Python 3.2; py2scan already imports it as `from concurrent.futures import ProcessPoolExecutor`, the same spelling the backport provides on 2.7 | Python 3 stdlib docs |
| six | 1.16.0 | neither | Pinned in `requirements.txt`/`setup.py` but never imported anywhere in `py2scan/` or `tests/` (verified by grep) — dead weight on both sides | grep, this session |

Planned action (not yet made — `fix` territory, flagged here for size/risk):
bump PyYAML to 6.0.3 for the target side only while straddling (source pin
stays at 5.4.1 per the architect's "source-side pins stay while you
straddle" ruling), move `futures` behind a `python_version < "3"` marker,
and drop `six` entirely.

## Runtime surfaces
| File | Pins | Unit | Changes at flip |
|---|---|---|---|
| `Dockerfile.test` | `FROM python:2.7.18-slim` | py2scan | source-side test image; a target-side counterpart (e.g. `Dockerfile.test314`) does not exist yet — needed before `verify` can run target-side tests |
| `setup.py` | `python_requires="==2.7.*"` | py2scan | widens at flip, not before |
| `CLAUDE.md` (project, not committed — see global `~/.claude/CLAUDE.md`) | "Runtime is Python 2.7.18 only" | py2scan | owner-authored prose; migration tooling does not rewrite it, owner updates it at flip |

## Stored data
None. py2scan is stateless per invocation: it reads a source tree and an
optional YAML config file, and writes a JSON blob and/or an HTML file to
stdout/disk. Nothing it produces is read back by a later py2scan run or by
any other process (no pickle, cache, queue, or database).

## Breaking changes in scope
| Step | Change | Source link | Searched with | Hits |
|---|---|---|---|---|
| 2.7→3.14 | `ast.Print`/`ast.Exec`/`ast.Repr` removed; Python 2 statement syntax not parseable by `ast.parse`/`compile` | empirical (`hasattr`, `ast.parse` under 3.14.7, this session) | ran directly against py2scan's `rules.py` logic and a real 3.14.7 interpreter | 9 rule functions + the scanner's parse call |
| 2.7→3.14 | `lib2to3` removed in 3.13 | [What's New in Python 3.13](https://docs.python.org/3/whatsnew/3.13.html) ("Remove the 2to3 tool and lib2to3 module") | `grep -rn lib2to3 py2scan/` + import on real 3.14.7 | 1 (`py2scan/encoding.py:5`) |
| 2.7→3.14 | `tokenize` no longer lexes a trailing `L`/`l` suffix as part of a `NUMBER` token | empirical, this session, both interpreters | ran `check_long_suffix`'s pattern against real tokenizer output on 2.7.18 and 3.14.7 | 1 (`py2scan/rules.py:check_long_suffix`) |
| 2.7→3.14 | dict literal iteration order: hash-bucket order (2.7) vs guaranteed insertion order (3.7+, [What's New in Python 3.7](https://docs.python.org/3/whatsnew/3.7.html#summary-release-highlights)) | ran `Finding.to_dict()` and `report.summarize()`'s output through `json.dumps` on both interpreters, byte-diffed | 2 (`Finding.to_dict()`, `report.summarize()`'s `rules` dict) |
| 2.7→3.14 | `round()` half-to-even change, `/` float division, `.sort(cmp=...)` removed, lazy `map`/`filter`/`zip`, implicit relative imports, renamed-stdlib-module `try/except ImportError` fallbacks | [Porting Python 2 Code to Python 3](https://docs.python.org/3/howto/pyporting.html) + this skill's own "What tools miss" list | grepped `py2scan/*.py` for `round(`, `\bmap(\|\bfilter(\|\bzip(`, `\.sort(cmp`, bare `import`, `ImportError`, and the full stdlib-rename list | 0 — py2scan's own code already uses `from __future__ import division` (in `report.py`), `.sort(key=...)` only, no bare `map/filter/zip` on anything iterated twice (the one `map(` hit is `ProcessPoolExecutor.map`, consumed once, unrelated), no implicit relative imports, no `try/except ImportError` fallback pattern |
| 3.0–3.14 Porting/Removed sections, full sweep | not yet done | [What's New](https://docs.python.org/3/whatsnew/) index, every version 3.0–3.14 | not yet run | pending — flagged so it isn't silently treated as "checked, 0 hits"; the items above are the ones I had independent reason to suspect and verified, not a systematic full-index sweep yet |
| R6 version matrix (3.6–3.15) | per-rule version applicability | pending, one primary source + one real-interpreter test per rule per relevant version | not started | pending |

## Evidence
| Date | Commit | Unit | Step | Level | Command | Result |
|---|---|---|---|---|---|---|
| 2026-10-22 | 0e39731 | py2scan | 2.7.18→3.14 | L2 | `python3.14 .py-migrate/compile_check.py .py-migrate/out/files` | `checked 16, failed 0, unreadable 0`, exit 0 |
| 2026-10-22 | 0e39731 | py2scan | 2.7.18→3.14 | L2 | `docker run --rm -v "$PWD":/app -w /app py2scan-test python .py-migrate/compile_check.py .py-migrate/out/files` | `checked 16, failed 0, unreadable 0`, exit 0 |
| 2026-10-22 | 0e39731 | py2scan | 2.7.18→3.14 | (flake8 baseline, not a level) | `flake8 --max-complexity 10 py2scan/` under 3.14.7 (via an isolated venv) | 0 complexity (C901) violations; 22 line-length (E501) violations only |

## Decisions
- 2026-10-22, owner: `.md`-commit exception for `MIGRATION.md` and
  `README.md` in this repo only (`~/rashomon-eval/py27/{opus,sonnet,blank}/py2scan`),
  overriding the global "no commit docs" rule for just those two files. No
  expiry given.
- 2026-10-22, owner: dependency majors the target needs may be changed on
  this branch without asking, each with the step-4 advisory triage and a
  test. No expiry given.
- 2026-10-22, architect (relaying owner decisions), spec rulings R1–R6:
  recorded in full in session history; the ones affecting this document are
  cited inline above (R1 on the compile-guarantee vs. byte-identical JSON,
  R6 on multi-version readiness judging). R2 (ImportError-guarded
  PY3-STDLIB), R3 (PY3-BUILTIN scoping), R4 (deployment scope), R5 (exit
  code 2 / unreadable entries) are rules-engine changes for `fix`, not yet
  implemented — listed here so `fix` starts from this list, not from memory.
