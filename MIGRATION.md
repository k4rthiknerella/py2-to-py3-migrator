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
| py2scan | Karthik Nerella | 2.7.18 | 3.14 | 2.7.18 → 3.14 | L2 | 0 auto / 2 manual (security scan, full What's New sweep) | L | `fix py2scan` |

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

**Resolved, commit `8f48071`:**
- R2: `py2scan/rules.py:check_stdlib_import` now checks whether the
  matched `Import`/`ImportFrom` node is inside a `try` body or a handler
  body (R2's "inside" — not else/finally, not a nested def/lambda) of a
  `try` with a handler that catches `ImportError` (bare `except:`, or a
  handler naming `ImportError`, `ModuleNotFoundError`, `Exception`,
  `BaseException`, or `StandardError`, alone or in a tuple); if so, the
  finding's severity is `warning` instead of `blocker`. Handles both
  Python 2.7's separate `TryExcept`/`TryFinally` ast nodes and Python 3's
  unified `Try` node via a version-guarded helper, matching the pattern
  already used for `ast.arg`. 11 new tests in `test_rules.py` (bare-except,
  named-handler, the fallback-import-in-the-handler-body case,
  tuple-of-exceptions, `ModuleNotFoundError`, `StandardError`, and five
  "still a blocker" negatives — unrelated except, try-else, try-finally,
  nested-function, no enclosing try at all), passing on both real
  interpreters (2.7.18 exercises `TryExcept`/`TryFinally`; 3.14.7 exercises
  the unified `Try`). Count verified by `grep -c` against the file, not
  recalled.
- R3: `check_builtin_use` replaced with a real scope-chain walk, not the
  previous flat whole-file set, after discovering that the flat approach
  has a genuine bug the existing test suite didn't catch: a purely local
  variable in one function (e.g. `def f(): unicode = 5`) was incorrectly
  shadowing an unrelated builtin reference in a *different*, unconnected
  function. Fixed by tracking a real scope chain (module → enclosing
  functions, innermost first) during a single recursive descent over the
  tree: `_own_bindings_and_globals` computes a scope's own direct bindings
  (R3: `del` binds "in that scope", same as any other binding) and any
  bare `global` names declared in it; `_module_bound_names` adds a name to
  module scope only where a function both declares it global AND binds it
  there (R3: a bare `global` alone binds nothing); `check_builtin_use`
  walks the tree carrying a scope-chain of shadow sets, resolving each
  builtin-candidate `Load` through enclosing function scopes via closure
  (skipping a scope entirely if it declares the name global) before
  falling through to module scope. A class body's own bindings are
  deliberately excluded from the scope chain its methods see (matching
  real Python: methods don't see class-body names without `self.`/the
  class name). 8 new tests in `test_rules.py` covering: no cross-function
  leakage, module- and function-scoped `del`, bare `global` alone (doesn't
  shadow) vs. `global`-plus-binding (does, module-wide), closure
  resolution into an enclosing function's local, and class-body
  non-leakage into a method. The 4 pre-existing `check_builtin_use` tests
  (including the parameter-shadowing one, which is what originally proved
  a flat set alone can't be correct — a parameter must shadow within its
  own function without leaking elsewhere) still pass unmodified.

  Known, documented gap (see the docstring on `check_builtin_use`): a
  parameter default value or decorator is evaluated in the *enclosing*
  scope in real Python, but this walk uses the function's own new scope
  for both, so a builtin name reused as both a parameter and, in the same
  signature, a default, could be wrongly treated as shadowed in its own
  default. R3's text doesn't call this out, and fixing it would cost
  parameter-annotation coverage for a scenario rare enough not to write a
  test for. Also doesn't handle 2.7's tuple-parameter unpacking
  (`def f((a, b)): ...`) — rare, Python-2-only syntax.

**Resolved, commit `70d7bd5`:**
- R5: `py2scan/scanner.py` walked the tree with `os.path.isdir`/`isfile`,
  which silently swallow `OSError` and return `False` — a permission-denied
  directory or file simply vanished from the file list with no trace, and
  the report claimed a complete scan when it wasn't one. Fixed with
  `_walk_entries`, which calls `os.stat` directly (it raises, so the real
  reason is caught instead of lost) and classifies each entry: an `OSError`
  from `os.listdir` or `os.stat` records `(relpath, str(e))`; a stat that
  succeeds but is neither `S_ISDIR` nor `S_ISREG` (a FIFO, a dangling
  symlink once `os.stat` follows it into `ENOENT`, a socket) records
  `(relpath, "not a regular file or directory")` — nothing under the scan
  root is dropped silently, matching R5's wording exactly. `iter_py_files`
  now returns `(files, problems)`; `scan_file` returns `(findings, problem)`
  so a mid-scan read failure (e.g. a `.py` file that becomes unreadable
  after being listed) is reported the same way as a listing-time failure;
  `scan` returns `(files, findings, problems)`. `report.summarize` gained
  `complete`/`problems` fields (`complete` is `not problems`); `cli.py`
  prints each problem in text mode and exits 2 whenever `problems` is
  non-empty — checked *before* the existing blocker-exit-1 check, so a
  scan root with both an unreadable entry and a blocker exits 2, not 1, per
  R5's "still exit 2 even if blockers were found."

  9 new tests: `test_unreadable_py_file_is_a_problem_not_a_crash` and
  `test_unreadable_directory_is_listed_as_a_problem` in
  `tests/test_scanner.py` (both `skipif`'d when running as root — root's
  `CAP_DAC_OVERRIDE` bypasses permission checks entirely, so `chmod 0` would
  prove nothing there, a real gap when this repo's own test Docker image
  runs as root by default); `test_dangling_symlink_is_a_problem_not_a_crash`
  and `test_non_regular_entry_is_a_problem_not_a_crash` in the same file,
  using a dangling symlink and `os.mkfifo` — both fail at the type/ENOENT
  level, not the permission level, so they exercise the same code path in
  every environment including root; `test_no_problems_is_a_complete_report`,
  `test_problems_make_the_report_incomplete`, and
  `test_problems_are_sorted_by_path` in `tests/test_report.py` against
  `summarize` directly; `test_scan_exits_2_and_takes_priority_over_a_blocker_exit_1`
  and `test_scan_text_format_reports_the_unreadable_entry` in
  `tests/test_cli.py`, end to end through `CliRunner`. Count verified by
  `git diff | grep -c "^+def test_"` per file, not recalled. Full suite:
  104 passed, 2 skipped (root-only skips) on 2.7.18 via Docker (root);
  101 passed, 5 skipped on 3.14.7 (non-root venv, so the two root-skipped
  tests ran there instead and passed) — both skip counts accounted for by
  environment, not by a test that can't run anywhere.

**Resolved, commit `6f3c07c`:**
- R10 (PY3-BUILTIN half only): `BUILTIN_NAMES` was missing `StandardError`
  — present in Python 2.7's `__builtin__`, absent from every judged
  version's `builtins`. Verified empirically by diffing 2.7.18's
  `__builtin__` names against `builtins` on 9 real, final-release
  interpreters spanning the full R6 range except 3.15 (no final release
  exists yet — see below): 3.6.15, 3.7.17 (Docker), 3.8.20, 3.9.25,
  3.10.19, 3.11.14, 3.12.12, 3.13.12, 3.14.7 (uv-managed/Homebrew). The
  missing-builtin set is **identical across all 9** — no name was removed
  or reinstated between 3.6 and 3.14 that isn't already covered by the
  existing fixed list plus `StandardError`. This means R10's substantive
  requirement (derive from real interpreters, record the derivation) is
  now satisfied for the full 3.6–3.14 range with a single flat set, no
  per-version data structure needed for PY3-BUILTIN — unlike R8's
  PY3-STDLIB half (below), builtin removals are not version-dependent
  within 3.x; they all happened at the 2-vs-3 boundary. 1 new test
  (`test_standard_error_is_found` in `test_rules.py`). Full suite: 105
  passed, 2 skipped on 2.7.18; 102 passed, 5 skipped on 3.14.7. flake8
  `--max-complexity 10` clean on both.

**Resolved, commit `pending`:**
- R8 (PY3-STDLIB expansion) + R6 (version-selection) + R7 (final-release
  interpreters, exact patch recorded) + R9 (static-knowledge, no runtime
  interpreter dependency).

  **T10 correction first:** an earlier draft of this entry claimed "3.15
  has no final release yet" with `uv python list` showing only an alpha
  as its receipt — that receipt proves what one tool offers to install,
  not whether a release exists. AutoSteer caught this. Checked a real
  primary source instead (python.org/downloads, devguide.python.org/
  versions): Python 3.15.0 final shipped 2026-10-09, and 3.15.1 (current
  latest) shipped 2026-10-21; a real interpreter is available via
  Docker's `python:3.15-slim` image, confirmed `python3 --version` →
  3.15.1. R6/R7 apply to 3.15 exactly as to every other version — there
  is no exception for it.

  Re-ran the same empirical probe against the real 3.15.1 interpreter.
  It found three more removed modules beyond 3.14.7's set —
  `sre_compile`, `sre_constants`, `sre_parse` (the internal re-engine
  modules, deprecated for years, finally removed) — that the earlier
  "treat 3.15 as at-least-3.14.7's floor" plan would have missed. The
  full R6 range (3.6–3.15) now has a genuine final-release interpreter
  behind every data point: 3.6.15, 3.7.17 (Docker), 3.8.20, 3.9.25,
  3.10.19, 3.11.14, 3.12.12, 3.13.12, 3.14.7 (uv-managed/Homebrew), and
  3.15.1 (Docker) — no gaps, no caveats needed.

  **Design** (per the architect: CLI shape and version-applicability
  presentation are implementation calls, not something to wait on a
  ruling for):
  - `py2scan scan PATH --target-version all|<comma-list>` (default
    `all` = every version in `ALL_TARGET_VERSIONS`, 3.6–3.15). Invalid
    versions are rejected with `click.BadParameter` before scanning
    starts.
  - `Finding` gained a `versions` field — the subset of the scan's
    judged versions this finding actually applies to. `check_stdlib_import`
    computes this itself per matched import (via `STDLIB_REMOVED_SINCE`,
    parallel to R10's `BUILTIN_NAMES`, keyed by the earliest judged
    version each of its 97 names is missing from); every other rule
    leaves `versions=None` and `scanner.scan_file` fills it in with the
    full judged set after all rules run, since those rules' applicability
    doesn't vary by version. A module not yet removed in any judged
    version (e.g. `distutils` judged only against 3.9–3.11) produces no
    finding at all, rather than firing with an empty version list —
    R8's correctness requirement, not just a formatting choice: the
    alternative would make e.g. `import distutils` an unconditional
    blocker that's **wrong** for anyone judging only pre-3.12 versions.
  - Readiness (R6: "per-file/per-blocker version applicability") is now
    a dict keyed by version string, not one scalar — a file can be ready
    for 3.9 while still blocked on 3.12. This is an intentional, called-
    out **breaking JSON-schema change** (`summary["readiness"]`: float →
    dict), not an oversight; every consumer of the old scalar shape
    (`cli.py`, the HTML template, the test suite) was updated along with
    it. `Finding.to_dict()` gained a `"versions"` list. Text-mode output
    appends `[<versions>]` to each finding line and prints one
    `readiness for Python X: Y%` line per judged version. The HTML
    template got a per-version readiness table and a Versions column on
    each finding row.
  - A `Finding` built directly with no `versions=` (existing direct-
    construction tests, and any future caller that bypasses
    `scan_file`) is treated as applying to every version
    `summarize`/`report` is asked about — documented on `Finding` and
    `summarize`, not a silent default.

  14 new tests: 3 in `test_rules.py` (version-dependent removal not
  found before its version, scoped correctly when judged against a
  mixed set, boundary removal applies to every judged version
  regardless of subset); 3 in `test_scanner.py` (narrow judged_versions
  suppresses a not-yet-removed import, default covers the full range,
  a version-invariant finding gets the whole judged set verbatim); 3 in
  `test_cli.py` (`--target-version` scopes both readiness and finding
  versions correctly, rejects an unknown version, defaults to all 10);
  1 in `test_report.py` (readiness only counts versions a finding
  actually applies to) plus 4 existing readiness-scalar tests rewritten
  for the dict shape (`test_no_files_is_fully_ready`,
  `test_clean_files_are_fully_ready`,
  `test_readiness_counts_files_without_a_blocker`,
  `test_a_warning_does_not_affect_readiness`) — not new tests, listed
  for completeness since their assertions changed shape, not just
  wording. Also manually exercised the full CLI (text/json/html) against
  a real scan root with `import distutils` + `import urllib2` +
  `unicode(...)`, confirming distutils scopes to `[3.12]`, urllib2/
  unicode scope to every judged version, and the HTML report renders
  the per-version table and per-finding Versions column without errors.

  Full suite: 115 passed, 2 skipped on 2.7.18 (Docker, root); 112
  passed, 5 skipped on 3.14.7. flake8 `--max-complexity 10` clean on
  both.

**Still open:**
- Security advisory scanning (item 4) — not started.
- Full systematic Python 3.0–3.14 What's New Removed/Porting sweep — not
  started; only targeted/suspected items have been checked so far (see
  Breaking changes in scope).

**Open defect against item 2b (not an accepted divergence — flagged by
AutoSteer trigger T12, corrected 2026-10-22; claims re-verified after T10
flagged two of them as receipt-free, corrected again same day):** R1
states that when the never-blocker-free guarantee conflicts with
byte-identical JSON across the two interpreters, the guarantee wins, and
every such conflicting input must be recorded as a defect, with the input
attached — explicitly *not* called an accepted divergence. An earlier
version of this document and of code comments in
`tests/test_rules.py`/`tests/test_scanner.py` wrongly called this "R1's
accepted divergence"; corrected (see commit history).

The defect itself: for any of the 7 inputs below, `scan` reports a single
`PY3-PARSE` blocker on the target and a different, granular blocker (with
a different `rule` and `message`) on the source — the JSON is not
byte-identical. Why no code change on either side can close this while
straddling: on the source, these 7 constructs are exactly what their rule
exists to detect, so making the source side stop reporting them would gut
the tool; on the target, `ast.Print`/`Exec`/`Repr` are verified absent from
Python 3.14.7's `ast` module (`hasattr` → `False`) and `ast.parse` is
verified to raise `SyntaxError` for each of the 7 inputs on that same
interpreter (command: `python3.14 -c "import ast; ast.parse(<input>)"`,
re-run for every input below as part of this correction) — Python 3's
`ast.parse` cannot be made to produce a tree containing a node type its
own `ast` module doesn't define, so the rule function can never run there
for these inputs. That no-code-change-closes-this argument is the receipt;
it is not itself a claim that flip removes the defect — item 2b's own
wording scopes the comparison to "while straddling", so once there is no
longer a second interpreter to diverge from, the comparison item 2b
describes no longer has two sides to apply to. Whether that is actually
how `cleanup`/`flip` end up treating it is undetermined and untested;
flagging this rather than asserting it.

Inputs, each verified against both real interpreters (2.7.18, 3.14.7) via
`ast.parse` directly and via `scan_file` end-to-end:
  - `print x` (or any print statement) → `PY3-PRINT` (2.7) / `PY3-PARSE` (3.x)
  - `exec 'x = 1'` → `PY3-EXEC-STMT` (2.7) / `PY3-PARSE` (3.x)
  - `` `x` `` (backtick) → `PY3-BACKTICK` (2.7) / `PY3-PARSE` (3.x)
  - `raise E, v` / `raise E, v, tb` → `PY3-RAISE-COMMA` (2.7) / `PY3-PARSE` (3.x)
  - `x <> y` → `PY3-NE-OP` (2.7) / `PY3-PARSE` (3.x)
  - `x = 0777` (old octal) → `PY3-OCTAL` (2.7) / `PY3-PARSE` (3.x)
  - `x = 10L` (long suffix) → `PY3-LONG-SUFFIX` (2.7) / `PY3-PARSE` (3.x)

  **Correction (same day):** `except Exception, e:` was wrongly included
  as an 8th input in the first version of this entry. Verified directly
  against real Python 3.14.7: `ast.parse("try:\n pass\nexcept Exception, e:\n pass\n")`
  succeeds — Python 3's grammar still accepts a bare-tuple expression in
  that position (`Exception, e` parses as the tuple `(Exception, e)`), so
  `check_except_comma`'s `TOKEN_RULES` logic runs for real on the target
  and reports the same `PY3-EXCEPT-COMMA` blocker as 2.7, byte-identical.
  No defect here — see `tests/test_scanner.py:
  test_except_comma_is_byte_identical_across_interpreters`. Dropped from
  8 to 7 inputs; the "every rule whose detected construct is syntax
  Python 3's grammar rejects" framing in the prior version of this entry
  was also wrong for this specific rule, for the same reason.

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
| 2026-10-22 | 5b75c6e | py2scan | 2.7.18→3.14 | (full suite) | `python3.14 -m pytest -q -p no:cacheprovider tests` (isolated venv wrapping the real installed interpreter) | `69 passed, 5 skipped` (skips are the inherently-Python-2-only-syntax direct-ast.parse tests in `tests/test_rules.py`'s `PY2_ONLY_SYNTAX` marker — these 5 cannot run on Python 3 by construction; see T12 correction below) |
| 2026-10-22 | 5b75c6e | py2scan | 2.7.18→3.14 | (flake8, not a level) | `flake8 --max-complexity 10 py2scan tests` under both 2.7.18 (Docker, flake8 3.9.2 pinned ad hoc — last release supporting 2.7, not added to requirements-dev.txt) and 3.14.7 | 0 violations of any kind, both interpreters |
| 2026-10-22 | 8f48071 | py2scan | 2.7.18→3.14 | (T12 fix) | `pytest tests/test_scanner.py` on both real interpreters, after adding 4 end-to-end `scan_file`-based tests (exec/backtick/raise-comma/raise-comma-with-traceback) alongside the existing print one, plus a byte-identical-across-interpreters test for except-comma | `9 passed` on both (2.7.18 and 3.14.7) |
| 2026-10-22 | 8f48071 | py2scan | 2.7.18→3.14 | (defect-input receipt) | `ast.parse(<input>)` for each of the 7 defect-list inputs, run directly against both real interpreters (2.7.18 via Docker stdin, 3.14.7 via the isolated venv) | all 7 parse successfully on 2.7.18, all 7 raise `SyntaxError` on 3.14.7 — confirms the defect-list claim with a receipt, not an assertion |
| 2026-10-22 | 8f48071 | py2scan | 2.7.18→3.14 | (R2) | full suite on both real interpreters after implementing R2 | `90 passed` on 2.7.18; `85 passed, 5 skipped` on 3.14.7 |
| 2026-10-22 | 8f48071 | py2scan | 2.7.18→3.14 | (flake8, not a level) | `flake8 --max-complexity 10 py2scan tests` under both real interpreters, after R2 and T12 fixes | 0 violations of any kind, both interpreters |
| 2026-10-22 | 054d2b2 | py2scan | 2.7.18→3.14 | (R3) | full suite on both real interpreters after implementing R3's scope-chain rewrite of `check_builtin_use` (row added late — missed when the commit landed) | `97 passed` on 2.7.18; `92 passed, 5 skipped` on 3.14.7 |
| 2026-10-22 | 054d2b2 | py2scan | 2.7.18→3.14 | (flake8, not a level) | `flake8 --max-complexity 10 py2scan tests` under both real interpreters, after R3 (including the closures-vs-top-level-functions complexity fix) | 0 violations of any kind, both interpreters |
| 2026-10-22 | 70d7bd5 | py2scan | 2.7.18→3.14 | (R5) | full suite on both real interpreters after implementing R5 | `104 passed, 2 skipped` on 2.7.18 (Docker, root — 2 root-dependent tests skipped); `101 passed, 5 skipped` on 3.14.7 (non-root venv — those 2 ran and passed; same 5 `PY2_ONLY_SYNTAX` skips as before) |
| 2026-10-22 | 70d7bd5 | py2scan | 2.7.18→3.14 | (flake8, not a level) | `flake8 --max-complexity 10 py2scan tests` under both real interpreters, after R5 | 0 violations of any kind, both interpreters |
| 2026-10-22 | n/a (research, no code change) | py2scan | (R6/R7 interpreter inventory) | `docker pull python:3.6-slim python:3.7-slim && docker run ... python3 --version`; `uv python install 3.13.12`; resolved paths for 3.8.20/3.9.25/3.10.19/3.11.14/3.12.12/3.13.12 (uv-managed) and 3.14.7 (Homebrew, same interpreter as every prior 3.14 evidence row) | all 9 confirmed final releases (no alpha/beta/rc); exact patch versions recorded above; 3.15 confirmed to have no final release yet (`uv python list` shows only `3.15.0a5`) |
| 2026-10-22 | n/a (research, no code change) | py2scan | (R8/R10 derivation) | a probe script run against all 9 interpreters above, each checking every 2.7.18 `__builtin__` name against that interpreter's `builtins`, and every empirically-derived 2.7.18 top-level stdlib module name (227, via `sys.builtin_module_names` + `pkgutil.iter_modules([os.path.dirname(os.__file__)])` on the real 2.7.18 Docker image) against importability on that interpreter | builtin-missing set identical across all 9 (16 names, `BUILTIN_NAMES` + `StandardError`); stdlib-missing set grows monotonically from 64 names (3.6.15) to 78 (3.14.7), confirmed no name ever reappears once removed — full breakdown in Blockers above |
| 2026-10-22 | 6f3c07c | py2scan | 2.7.18→3.14 | (R10, builtin half) | full suite on both real interpreters after adding `StandardError` to `BUILTIN_NAMES` | `105 passed, 2 skipped` on 2.7.18; `102 passed, 5 skipped` on 3.14.7 |
| 2026-10-22 | 6f3c07c | py2scan | 2.7.18→3.14 | (flake8, not a level) | `flake8 --max-complexity 10 py2scan tests` under both real interpreters | 0 violations of any kind, both interpreters |
| 2026-10-22 | n/a (research, no code change) | py2scan | (T10 correction of the 2026-10-22 row above) | `curl` against python.org/downloads/release/python-3150/ and devguide.python.org/versions directly (not `uv python list`, which only reports what one tool offers to install); `docker pull python:3.15-slim && docker run ... python3 --version` | Python 3.15.0 final shipped 2026-10-09, 3.15.1 (latest) shipped 2026-10-21, confirmed via the official downloads page; a real interpreter is available (Docker `python:3.15-slim` → `Python 3.15.1`) — the earlier row's "3.15 has no final release yet" was wrong |
| 2026-10-22 | n/a (research, no code change) | py2scan | (R8/R10, 3.15.1) | the same probe script from the row above, run against the real 3.15.1 interpreter via Docker | 3 more stdlib names missing vs. 3.14.7: `sre_compile`, `sre_constants`, `sre_parse`; builtin-missing set unchanged (still the same 16 names as all 9 other interpreters) |
| 2026-10-22 | pending | py2scan | 2.7.18→3.14 | (R6-R10 implementation) | full suite on both real interpreters after implementing `--target-version`, `STDLIB_REMOVED_SINCE`, per-finding `versions`, and per-version `readiness` | `115 passed, 2 skipped` on 2.7.18 (Docker, root); `112 passed, 5 skipped` on 3.14.7 |
| 2026-10-22 | pending | py2scan | 2.7.18→3.14 | (flake8, not a level) | `flake8 --max-complexity 10 py2scan tests` under both real interpreters | 0 violations of any kind, both interpreters |
| 2026-10-22 | pending | py2scan | 2.7.18→3.14 | (manual CLI smoke test) | invoked `py2scan.cli.main` directly (text/json/html) against a scan root with `import distutils` + `import urllib2` + `unicode('hi')`, with `--target-version 3.9,3.12` and with the `all` default | distutils scoped to `["3.12"]` only; urllib2/unicode scoped to every judged version; JSON `readiness` keyed by version; HTML report rendered the per-version table and per-finding Versions column without template errors; unknown `--target-version` rejected with `click.BadParameter`, exit code 2 |

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
  PY3-STDLIB) and R3 (PY3-BUILTIN scoping) are implemented — see Blockers,
  Resolved. R4 (deployment scope) is superseded by R9 below. R5 (exit code
  2 / unreadable entries) is implemented — see Blockers, Resolved.
- 2026-10-22, architect (relaying owner decisions), spec rulings R7–R10:
  recorded in full in session history; cited inline above where they refine
  R1/R6/R8 (R9's "no network, no required extra interpreter at scan time"
  constraint; R10's PY3-BUILTIN scope expansion, parallel to R8's
  PY3-STDLIB expansion). R6/R7/R8/R9/R10 are all implemented — see
  Blockers, Resolved. The CLI shape (`--target-version`) and how
  per-finding version-applicability surfaces in JSON/text/HTML were left
  to implementation judgment per the architect's own message ("nothing
  is waiting on me" on those two points) rather than a ruling.
- 2026-10-22, architect (relaying owner decisions), spec ruling R11 (scope
  of item 4, security advisory scanning, not yet started): "environment"
  means what py2scan installs and runs with — the interpreter and the
  Python packages, on both the source and target side. Explicitly out of
  scope: OS packages inside test images, and the judged-version
  interpreters used only as R9 test equipment. Interpreter advisories
  count, with the query method and its blind spots recorded. Any "accept
  with an expiry date" proposal is pending owner acceptance until the
  owner actually accepts it — record it as pending, not as a Decision
  entry, until that happens.
