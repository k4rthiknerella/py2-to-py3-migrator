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

**R9 note (architect ruling, 2026-10-22):** R4 describes where py2scan runs
*today* (this repo only), not its users — py2scan is open-source and must
work for a user with only the one Python it runs on and no network. The
R1/R6 "never reported blocker-free" guarantee is a property of the report,
not of any one mechanism, and must hold under that condition: a scan never
downloads anything, and at scan time py2scan may opportunistically use any
judged-version interpreter that happens to be installed, but a missing one
must never weaken a verdict. Practical effect on the still-unstarted R6/R7/R8
work: the per-version blocker logic must be static knowledge shipped in
py2scan (grammar/stdlib/builtin facts baked in), not a runtime dependency on
having e.g. a real 3.9 interpreter on PATH — real interpreters are test
equipment used to *prove* those static facts during development (R6, R7),
never a scan-time requirement.

**R10 note (architect ruling, 2026-10-22):** parallel to R8's PY3-STDLIB
scope, PY3-BUILTIN must cover every name in Python 2.7's `__builtin__`
missing from a judged version's `builtins`, not just the original fixed
`BUILTIN_NAMES` list — derived from the interpreters (R6, R7), with the
derivation recorded. Not started; folded into the same R6/R7/R8 matrix work.

## Units
| Unit | Owner | Runtime today | Effective target | Step | Level | Blockers (auto / manual) | Size | Next |
|---|---|---|---|---|---|---|---|---|
| py2scan | Karthik Nerella | 2.7.18 | 3.14 | 2.7.18 → 3.14 | L2 | 0 auto / 6 manual (R2, R3, R5, R6-R10 matrix, security scan, full What's New sweep) | L | `fix py2scan` |

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

**Resolved, commit `5b75c6e`:**
- `py2scan/rules.py` (`check_print`, `check_exec`, `check_backtick`) ·
  referenced `ast.Print`/`ast.Exec`/`ast.Repr` directly, which don't exist as
  attributes on Python 3's `ast` module at all — crashed any file that
  successfully `ast.parse`d, not just ones containing the construct (proven:
  `AttributeError: module 'ast' has no attribute 'Print'` reached from inside
  a `ProcessPoolExecutor` worker scanning a file with no print statement at
  all) · fixed with a `getattr(ast, name, None)` guard per rule, each a safe
  no-op when the attribute is absent (the tree could never contain that node
  type on an interpreter where parsing it would have raised `SyntaxError`
  first) · test: full suite, both interpreters.
- `py2scan/rules.py:check_raise_comma` · Python 3's `ast.Raise` has no
  `.inst` attribute at all · fixed with `getattr(node, "inst", None)`.
- `py2scan/rules.py:_module_bound_names` · Python 3 represents function
  parameters as `ast.arg` nodes, not `ast.Name(ctx=ast.Param())` · fixed with
  a version-guarded `_ARG_TYPE = getattr(ast, "arg", None)` branch.
- `py2scan/rules.py:check_long_suffix` · Python 3's tokenizer splits `10L`
  into `NUMBER '10'` + `NAME 'L'`, not one token · fixed by tracking
  token-adjacency (`start == prev_end`) across the two-token form.
- `py2scan/encoding.py:5` · `lib2to3` removed in Python 3.13 · fixed with a
  `try/except ImportError` falling back to stdlib `tokenize.detect_encoding`
  (present natively since 3.2) · verified identical behavior on both the
  cookie and no-cookie cases.
- `py2scan/report.py`/`cli.py`'s `json.dumps(summary)` · not byte-identical
  across interpreters (2.7 hash-bucket dict order vs 3.7+ insertion order) ·
  fixed with `json.dumps(summary, sort_keys=True)` in `cli.py`.
- `tests/test_scanner.py`, `tests/test_cli.py` · fixtures using print
  statements could never produce their original granular findings on Python
  3 (ast.parse fails before the rule ever runs) · switched to constructs
  that parse on both interpreters so these tests exercise what they're
  actually about; added a dedicated cross-interpreter test
  (`test_print_statement_is_a_blocker_on_whichever_interpreter_is_running`)
  asserting the R1 never-blocker-free guarantee directly, regardless of
  which rule fires. This is **not** the same as closing the underlying
  defect — see "Open defect against item 2b" below.
- `tests/test_rules.py:token_rules` · called `tokenize.generate_tokens`
  directly on a `str`, which Python 3's `io.BytesIO` rejects · fixed by
  routing through `scanner._tokenize` (the same production tokenizer), after
  encoding the source to bytes.
- flake8 E501 (36 violations across `py2scan/` and `tests/`) · fixed by line
  wrapping only, no logic changes · verified `flake8 --max-complexity 10`
  clean (0 complexity, 0 line-length) on both real interpreters.

**Still open:**
- R2 (ImportError-guarded PY3-STDLIB → warning, not blocker) — not started.
- R3 (PY3-BUILTIN scoping per Python 2.7's real compiler semantics,
  including `del` and bare `global`) — not started.
- R5 (exit code 2 and incomplete-report marking for unreadable entries) —
  not started.
- R6/R7/R8/R9/R10 (multi-version readiness matrix, 3.6–3.15, final-release
  interpreters only with exact patch versions recorded, expanded PY3-STDLIB
  and PY3-BUILTIN derivation, static-knowledge-not-runtime-dependency
  constraint) — not started. This is the largest remaining item; it is
  `fix`-phase work, scoped here, not assessed line-by-line yet · Size L.
- Security advisory scanning (item 4) — not started.
- Full systematic Python 3.0–3.14 What's New Removed/Porting sweep — not
  started; only targeted/suspected items have been checked so far (see
  Breaking changes in scope).

**Open defect against item 2b (not an accepted divergence — flagged by
AutoSteer trigger T12, corrected 2026-10-22):** R1 states that when the
never-blocker-free guarantee conflicts with byte-identical JSON across the
two interpreters, the guarantee wins, and every such conflicting input must
be recorded as a defect, with the input attached — explicitly *not* called
an accepted divergence. An earlier version of this document and of code
comments in `tests/test_rules.py`/`tests/test_scanner.py` wrongly called
this "R1's accepted divergence"; that wording has been corrected (see
commit history). The defect itself: for any of the 8 inputs below, `scan`
reports a single `PY3-PARSE` blocker on the target and a different,
granular blocker (with a different `rule` and `message`) on the source —
the JSON is not byte-identical, and per R1 it stays that way, because
`ast.Print`/`Exec`/`Repr` do not exist on Python 3's `ast` module and the
syntax cannot reach `ast.parse` successfully there at all. This cannot be
closed while straddling; it is open until flip (when there is no longer a
2.7 side to diverge from). Inputs, each verified on both real interpreters:
  - `print x` (or any print statement) → `PY3-PRINT` (2.7) / `PY3-PARSE` (3.x)
  - `exec 'x = 1'` → `PY3-EXEC-STMT` (2.7) / `PY3-PARSE` (3.x)
  - `` `x` `` (backtick) → `PY3-BACKTICK` (2.7) / `PY3-PARSE` (3.x)
  - `raise E, v` / `raise E, v, tb` → `PY3-RAISE-COMMA` (2.7) / `PY3-PARSE` (3.x)
  - `x <> y` → `PY3-NE-OP` (2.7) / `PY3-PARSE` (3.x)
  - `x = 0777` (old octal) → `PY3-OCTAL` (2.7) / `PY3-PARSE` (3.x)
  - `x = 10L` (long suffix) → `PY3-LONG-SUFFIX` (2.7) / `PY3-PARSE` (3.x)
  - `except Exception, e:` → `PY3-EXCEPT-COMMA` (2.7) / `PY3-PARSE` (3.x)

  These are exactly the 8 of 14 rules whose detected construct is itself
  syntax Python 3's grammar rejects: `scan_file` runs `ast.parse` before any
  rule, so for these 8, the SyntaxError branch always wins the race on the
  target, regardless of what the rule function would have found.

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

Done, commit `5b75c6e`: PyYAML pinned to 6.0.3 for the target side only
(`python_version >= "3"`) while the source pin stays at 5.4.1 per the
architect's "source-side pins stay while you straddle" ruling; `futures`
moved behind `python_version < "3"`; `six` dropped entirely. Verified: both
pins install and import cleanly on their respective interpreters.

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
| 2026-10-22 | 5b75c6e | py2scan | 2.7.18→3.14 | L2 | `python3.14 .py-migrate/compile_check.py .py-migrate/out/files` | `checked 17, failed 0, unreadable 0`, exit 0 |
| 2026-10-22 | 5b75c6e | py2scan | 2.7.18→3.14 | L2 | `docker run --rm -v "$PWD":/app -w /app py2scan-test python .py-migrate/compile_check.py .py-migrate/out/files` | `checked 17, failed 0, unreadable 0`, exit 0 |
| 2026-10-22 | 5b75c6e | py2scan | 2.7.18→3.14 | (full suite) | `docker build -q -f Dockerfile.test -t py2scan-test . && docker run --rm -v "$PWD":/app -w /app py2scan-test python -m pytest -q -p no:cacheprovider tests` | `74 passed` |
| 2026-10-22 | 5b75c6e | py2scan | 2.7.18→3.14 | (full suite) | `python3.14 -m pytest -q -p no:cacheprovider tests` (isolated venv wrapping the real installed interpreter) | `69 passed, 5 skipped` (skips are the R1-sanctioned Python-2-only-syntax tests; see `tests/test_rules.py`'s `PY2_ONLY_SYNTAX` marker) |
| 2026-10-22 | 5b75c6e | py2scan | 2.7.18→3.14 | (flake8, not a level) | `flake8 --max-complexity 10 py2scan tests` under both 2.7.18 (Docker, flake8 3.9.2 pinned ad hoc — last release supporting 2.7, not added to requirements-dev.txt) and 3.14.7 | 0 violations of any kind, both interpreters |

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
- 2026-10-22, architect (relaying owner decisions), spec rulings R7–R10:
  recorded in full in session history; cited inline above where they refine
  R1/R6/R8 (R9's "no network, no required extra interpreter at scan time"
  constraint on the still-unstarted R6/R7/R8 matrix work; R10's PY3-BUILTIN
  scope expansion, parallel to R8's PY3-STDLIB expansion). None of R7–R10
  are implemented yet.
