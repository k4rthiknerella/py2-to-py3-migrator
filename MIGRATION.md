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
Dependencies). It is still only the *source*-side command (the frontmatter
holds one `test` string, and `assess`/`status` own it, not `fix`/`verify`/
`flip`); the target-side counterpart used for `verify` this session is the
same command with `Dockerfile.test314` in place of `Dockerfile.test` — see
Runtime surfaces.

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
| py2scan | Karthik Nerella | 2.7.18 | 3.14 | 2.7.18 → 3.14 | L4 | 0 auto / 0 manual | S | owner: review Flip preparation section, merge/ship when ready (L5 only on confirmation) |

L2 is proved by `.py-migrate/compile_check.py`, committed, run on both sides
— see Evidence. L3 (this session): dependencies resolve on both sides (see
Dependencies — every pin verified to actually install and import, not just
believed to resolve), no stored data for this CLI tool, runtime surfaces
have a plan (see Runtime surfaces), and the 0/0 blocker count above is
itself the "no open blockers" proof. No consumers import py2scan as a
library (it is a CLI-only unit), so there is no import-graph wave ordering
to apply. L4 (this session, deliberate `verify` pass at commit `0f40071`,
not the informal evidence accumulated along the way): full suite, 2.7.18
(source) and 3.14.7 + 3.14.9 (target, two patch versions on purpose — see
the check_ne_op defect this session for why one patch version isn't
trustworthy alone) — all clean; `compile_check.py` clean on both;
`flake8 --max-complexity 10` clean on both. No data jobs, so no parity run
applies. See Evidence for the exact commands and results.

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

**Resolved, commit `41792b8`:**
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

**Resolved, commit `2f33844`:** AutoSteer CI (new this session — runs on
every commit to this branch, on `python:2.7.18-slim` and `python:3.14-slim`,
no network, uid 1000) reported `tests.test_rules::test_ne_op_is_found`
failing on its 3.14 image. That image resolves to Python 3.14.9; every
3.14 test run earlier in this session used Homebrew 3.14.7 — a patch-version
gap that had gone unnoticed because nothing before now exercised 3.14.9.
Root cause, confirmed by comparing real `tokenize.tokenize()` output for
`b'x = 1 <> 2\n'` on both patch releases: 2.7.18 and 3.14.7 both lex `<>` as
one compound `OP` token (`"<>"`); starting at 3.14.9, the tokenizer no
longer recognizes `<>` as a compound operator and instead emits two
adjacent single-character `OP` tokens, `"<"` immediately followed by `">"`
(`end` of the first == `start` of the second). `py2scan/rules.py:check_ne_op`
only matched the one-token form, so it silently stopped detecting `<>` on
3.14.9 specifically — not on 3.14.7, not on 2.7.18, not on any other
3.x version checked for R6–R10. Fixed by tracking token adjacency
(`start == prev_end`) across the two-token form, the same pattern
`check_long_suffix` already uses for `10L` splitting into `NUMBER '10'` +
`NAME 'L'` on Python 3. Verified both forms are now detected, and that
chained/adjacent `<`/`>` tokens that aren't actually `<>` (e.g.
`a < b > c`, `def f() -> None`) are not misdetected, by re-running the
full suite (not just the one test) on all three tokenizer behaviors:
2.7.18, 3.14.7, and 3.14.9 (the exact image CI uses) — see Evidence. This
is the first defect this session's own manual local testing missed and an
automated CI catch found instead: "3.14" as a reference version is not
precise enough once tokenizer behavior can change between patch releases.
Decision (mine — the architect confirmed local interpreter choice is an
implementation choice, not something requiring a ruling): 3.14.9 (Docker
`python:3.14-slim`) is now a required local check alongside 3.14.7 going
forward, not a Decisions-section entry since it's a testing-practice
choice, not an owner-approved exception.

**Resolved, commit `b58a732`: security advisory scanning (item 4, R11
scope).** R11's scope: "environment" means what py2scan installs and runs
with — the interpreter and the Python packages it depends on, both source
and target side. Explicitly out of scope per R11: OS packages inside test
images, and the judged-version interpreters used only as R9 test
equipment. Extending that same already-ruled boundary one step further
(not a new ruling, a direct application of its own logic): dev/test-only
Python packages that never ship with an installed `py2scan` — `pytest`
and anything pulled in only by `pytest` — are also out of scope, for the
identical reason OS-packages-in-test-images are: they are not part of
what a user's py2scan installation runs with in production.

Runtime dependency scan (OSV.dev REST API, `POST
https://api.osv.dev/v1/query` with `{"version": ..., "package": {"name":
..., "ecosystem": "PyPI"}}`, queried directly this session):
- `click` 7.1.2, `MarkupSafe` 1.1.1, `PyYAML` 5.4.1, `PyYAML` 6.0.3,
  `futures` 3.3.0: 0 known vulnerabilities each.
- `Jinja2` 2.11.3: 4 real, distinct CVEs (CVE-2025-27516, CVE-2024-22195,
  CVE-2024-34064, CVE-2024-56326 — OSV lists each under both a GHSA and a
  PYSEC id, 8 raw hits collapsing to 4). All four are fixed only in
  Jinja2 3.1.x (3.1.3 through 3.1.6); none were ever backported to any
  2.x release, and 2.11.3 is confirmed the last 2.x release at all
  (PyPI JSON API's full release list, verified earlier this session) —
  Jinja2 3.0+ requires Python ≥3.6, so there is no in-place version bump
  available while straddling 2.7.
  **Reachability, checked against py2scan's actual usage, not just the
  package version:** two of the four (CVE-2025-27516, CVE-2024-56326) are
  sandbox-escape bugs in `jinja2.sandbox.SandboxedEnvironment` /
  `ImmutableSandboxedEnvironment`; `py2scan/report.py:13` constructs a
  plain `jinja2.Environment(autoescape=True)` — no sandbox in use, so
  there is no sandbox to escape. The other two (CVE-2024-22195,
  CVE-2024-34064) are HTML-attribute-injection bugs reachable only through
  the `xmlattr` filter with attacker-controlled dict keys; `grep -n
  xmlattr py2scan/report.py` finds no use of that filter anywhere in
  `_TEMPLATE`. All four CVEs exist in the pinned version string but have
  no reachable path through py2scan's own template or environment
  construction. **Proposal, pending owner acceptance per R11 (not
  recorded as a Decision — R11 is explicit that a proposal is not a
  Decision until the owner actually accepts it):** accept these 4 as
  not applicable given current usage, re-check at `flip` (when Python 2.7
  support drops and Jinja2 can move to a patched 3.1.x release), expiring
  at that step or in 6 months, whichever comes first.
- `pytest` 4.6.11 (source-side test runner only, out of R11 scope per
  above, checked anyway for completeness): 1 real CVE, CVE-2025-71176
  (GHSA-6w46-j5rx-g56g), local-attacker tmpdir-handling issue
  (CVSS 3.1 `AV:L/AC:L/PR:N/UI:N/S:C/C:L/I:L/A:L`), fixed in 9.0.3.
  `pytest` 9.1.1 (target-side test runner): 0 known vulnerabilities.
  Informational only — this is test tooling, never installed by a
  py2scan user.
- `six` 1.17.0: present in the 2.7.18 test image, but as a transitive
  dependency of `pytest` (not of py2scan) — out of scope for the same
  reason `pytest` itself is; see the corrected Dependencies table row.

Interpreter advisory scan (NVD CVE API 2.0,
`https://services.nvd.nist.gov/rest/json/cves/2.0?cpeName=<cpe>`, queried
directly this session for both `cpe:2.3:a:python:python:2.7.18:...` and
`cpe:2.3:a:python:python:3.14.7:...`):
- 2.7.18: 38 raw CPE-name matches. Of those, 3 (CVE-2009-2940, CVE-2009-3720,
  CVE-2021-28667) are confirmed methodology false positives by inspecting
  NVD's own `configurations` data: the `python:python` CPE node in each of
  those 3 records is itself marked `"vulnerable": false` — it is present
  only as platform/context alongside a *different* product's CPE node
  marked `vulnerable: true` (pygresql, libexpat, and a StackStorm issue,
  respectively). The `cpeName` query matches on any CPE mentioned anywhere
  in a record's configuration, not just ones marked vulnerable — a receipt
  for exactly the false-positive pattern suspected earlier this session,
  now confirmed with the specific field that proves it, not just circumstantial description-reading.
- Of the remaining 35: every single one has its lowest version-range
  segment with no `versionStartIncluding`/`versionStartExcluding` set at
  all (just an upper bound such as `versionEndExcluding: 3.7.17`) — i.e.
  the range is implicitly "from version 0," not an asserted lower bound.
  Checked systematically across all 35, not sampled: 35/35, zero
  exceptions. This means NVD's own data cannot distinguish "confirmed to
  affect 2.7.18" from "nobody ever bothered to set a floor because 2.7 is
  EOL and unmaintained" — the open question from earlier this session now
  has a precise, structural explanation and a receipt, not just a
  hypothesis. This is not itself proof these 35 don't affect 2.7.18 (some,
  like the decades-old `tarfile` path-traversal bug, almost certainly do);
  it is proof that the raw NVD match alone is not a receipt of 2.7.18
  applicability either way.
- Checked what the 35 are actually about regardless: `tarfile`, `email`,
  `urllib.parse`, `plistlib`, `hmac`, `wave`, `webbrowser`, `html.parser`,
  `xml`/`expat`, `http.cookies`, `configparser`, `shutil`, `venv`,
  `os.path.expandvars`, `base64`. py2scan's own source imports exactly
  `json`, `sys`, `io`, `collections`, `os` (never `expandvars`), `ast`,
  `functools`, `platform`, `stat`, `tokenize`, `concurrent.futures`, `re`
  (`grep -n "^import \|^from " py2scan/*.py`, this session) — none of
  which any of the 35 CVEs concern. **Conclusion: not "2.7.18 has no
  vulnerabilities" (several of the 35 are real, well-known CPython bugs);
  specifically, none of them have a reachable path through py2scan's own
  code**, because py2scan never calls the affected functions.
- 3.14.7: 4 raw CPE-name matches, and all 4 are the same false-positive
  pattern (`vulnerable: false` on the `python:python` node) — 2 of the 3
  from the 2.7.18 list plus CVE-2020-29396 (Odoo) and CVE-2021-32052
  (Django, context-dependent on Python ≥3.9.5, hence absent from the
  2.7.18 query but present here). Zero genuine matches for 3.14.7.
- Blind spot, recorded per R11: this method only surfaces what NVD has
  already catalogued against the `python:python` CPE; it would miss a
  vulnerability disclosed through a channel NVD hasn't indexed yet, and it
  cannot assess 3.14.9 differently from 3.14.7 (NVD CPE matching is
  patch-version-aware in principle, re-queried separately if the 3.14.9
  local-check decision above matters here later).

**Resolved, commit `cc12b90`: full systematic Python 3.0–3.14 What's New
Removed/Porting sweep.** Fetched every `docs.python.org/3/whatsnew/<v>.html`
page for v in 3.0 through 3.14 this session, stripped to plain text, and
grepped each version's Removed/Deprecated/Porting sections against
py2scan's own exact stdlib footprint — `json`, `sys`, `io`, `collections`,
`os`, `ast`, `functools`, `platform`, `stat`, `tokenize`,
`concurrent.futures`, `re` (`grep -n "^import \|^from " py2scan/*.py`),
plus the precise attributes/functions py2scan's own code actually calls
on each (e.g. `ast.Print`/`Raise.inst`, not every `ast` attribute that
exists; `os.listdir`/`os.stat`/`stat.S_ISDIR`/`S_ISREG`, not every `os`
function) — not the full module, since an unrelated removed function in
a module py2scan imports is not a defect if py2scan never calls it.

Found and fixed one genuine, previously-undiscovered defect this way, not
just confirmed-clean coverage:
- `py2scan/*.py` (`findings.py:to_dict`, `report.py:summarize`/
  `render_html`, `cli.py`'s text-mode output) · **Discovered from reading
  What's New in Python 3.0's note that `os.listdir()` can return raw,
  undecoded bytes for a filename on a byte-oriented (POSIX) filesystem.**
  Verified on real Linux containers (not theorized): a `.py` file whose
  name contains a byte invalid in UTF-8 (a legacy-encoded name, plausible
  in exactly the kind of old codebase py2scan scans) is read, tokenized,
  and ast.parse'd completely correctly by `scan_file` on every
  interpreter — the scan itself was never the problem. The crash was
  downstream, in *output*, and took two different forms depending on the
  interpreter, discovered one empirical test at a time:
  - **Python 2.7.18** (verified via a real Docker `python:2.7.18-slim`
    fixture): `os.listdir()` returns such a filename exactly as stored,
    with no decoding attempted at all (`str` is bytes on 2.7). The raw
    byte string then reaches `json.dumps()`, the `u"%s" %` text-mode
    formatting, and the Jinja2 HTML template — all three crash with an
    uncaught `UnicodeDecodeError`/`UnicodeEncodeError`, a real-traceback
    hard crash, not an R5 "problem" (the file was read successfully; this
    is a different failure mode R5 was never written to catch).
  - **Python 3.14.9** (verified via a real Docker `python:3.14-slim`
    fixture, the same image CI uses): `os.listdir()` instead decodes with
    the `surrogateescape` error handler (PEP 383), producing a `str`
    that holds a lone surrogate code point. `json.dumps()`'s default
    `ensure_ascii=True` tolerated this (it emits a literal ASCII escape,
    never actually encoding the surrogate) — which is why an earlier,
    narrower manual test of JSON output only looked clean and nearly
    became the final answer. Re-testing text-mode and `--html` output
    specifically (not just JSON) surfaced the real, parallel crash:
    `click.echo()` and the HTML file write both have to actually encode
    the string as UTF-8 to produce bytes for a stream, and a lone
    surrogate cannot be UTF-8-encoded — `UnicodeEncodeError`, caught only
    because the new test in `tests/test_cli.py` exercises all three
    output formats against the same fixture, not just one.

  Fixed with one helper, `py2scan/encoding.py:safe_text`, applied only at
  display/serialization boundaries, never to the value scanner.py uses to
  actually re-open a file (`Finding.file` itself stays the raw,
  disk-accurate value throughout, since `report.py:render_html`'s
  `source_line()` needs it to reopen the file for the HTML report's code
  snippet) — `safe_text` is called on a copy only in `Finding.to_dict()`,
  `report.summarize()`'s problems list, `render_html()`'s per-file
  heading, and `cli.py`'s text-mode finding/problem lines. On Python 2,
  it decodes raw bytes as UTF-8, falling back to `'replace'` (→ U+FFFD)
  on failure; on Python 3, it round-trips through a UTF-8 encode/decode
  with `'replace'` specifically to catch and clean up lone surrogates,
  since Python 3's `str` can already hold ones that aren't safe to
  encode. Net effect: output is now not just crash-free but *identical*
  across both interpreters for this case (both show the same U+FFFD),
  which the straddle's own byte-identical-JSON goal did not originally
  ask for but turns out to fall out of the fix for free.

  2 new tests, one per crash site: `tests/test_scanner.py:
  test_bad_byte_filename_is_scanned_and_stays_safe_to_serialize` (the
  scan itself works, `to_dict()` never raises) and `tests/test_cli.py:
  test_scan_handles_a_bad_byte_filename_in_every_format` (all three
  output formats, end to end, on the real CLI — this second test is what
  caught the Python 3 surrogate crash the first fix attempt missed, since
  an earlier, narrower manual check had only tried JSON output). Both
  skip (not xfail, not hard-coded to a platform name) if the host
  filesystem itself refuses to create the fixture — confirmed to happen
  on macOS (HFS+/APFS enforce valid UTF-8 filenames; this is genuinely
  impossible to reproduce there), via a real `OSError` caught at fixture
  creation, not a platform-name guess.

  Full suite after the fix: `117 passed, 2 skipped` on 2.7.18 (Docker,
  root); `112 passed, 7 skipped` on 3.14.7 (the 2 new tests skip here —
  this is the Mac host); `112 passed, 7 skipped` on 3.14.9 (Docker
  `python:3.14-slim`, matching CI — the 2 new tests pass here, on Linux).
  flake8 `--max-complexity 10` clean on 2.7.18 and 3.14.7.

  Everything else in the sweep checked clean against py2scan's own
  footprint, with the specific reasoning recorded so "checked, 0 hits"
  isn't just asserted: `tokenize.generate_tokens`→`tokenize.tokenize`
  split (3.0, bytes-mode) — already handled, predates this sweep
  (`scanner.py:_tokenize`); implicit trailing `NEWLINE` token (3.8) — no
  rule inspects `NEWLINE`; PEP 701 `STRING`→`FSTRING_START/MIDDLE/END`
  split (3.12) — no rule inspects `STRING`, and f-strings can appear in
  neither py2scan's own straddle-compatible source nor the Python-2-only
  code it scans; `json.loads(encoding=...)` removed (3.9) — py2scan only
  calls `json.dumps`; `sys.getcheckinterval`/`setcheckinterval`/
  `callstats`/`getcounts` removed (3.9) — none called; `collections`'s
  deprecated ABC aliases removed (3.10) — py2scan only uses
  `collections.Counter`/`OrderedDict`, never an ABC alias;
  `concurrent.futures`/asyncio restriction (3.11) — py2scan uses
  `ProcessPoolExecutor.map` directly, no asyncio involved; `functools`
  changes (3.2, 3.3) — all additions (`lru_cache`, `wraps`,
  `total_ordering`), no change to `functools.partial`, the only thing
  py2scan calls; `io.BytesIO` — zero Removed/Deprecated/behavior-change
  mentions across all 15 pages; `os.stat`/`stat.S_ISDIR`/`S_ISREG` —
  changes found (3.3, 3.7, 3.8, 3.12) are all about `st_mode`/`st_ctime`
  precision and symlink traversal detail, not about the two `S_IS*`
  predicates py2scan actually calls; `token.h` C header removed (3.12) —
  C API only, py2scan is pure Python.

**Resolved, commit `91d8bd1` (retroactive write-up — added after the
commit itself, closing a documentation gap AutoSteer's Units-level
Evidence check would otherwise have caught the same way it caught the
L2 to L3 gap above): two more item-3 crashes, found by testing every
input item 3 lists against the real scanner, not just the ones the
`cc12b90` sweep above happened to cover.**

- Embedded NUL byte: Python 2.7's `compile()` raises `TypeError`
  (confirmed empirically via a standalone probe — not `SyntaxError`),
  uncaught by the original `except SyntaxError` clause in
  `scanner.py:scan_file`, crashing the entire scan via
  `ProcessPoolExecutor`, not just the one file. Python 3.14 already
  raises `SyntaxError` for the same input.
- Deeply nested expression (3000 nested parens, tested directly):
  Python 2.7's C parser raises `MemoryError` ("s_push: parser stack
  overflow", printed to stderr by the C parser itself), same
  uncaught-crash shape. Python 3.14's PEG parser already raises
  `SyntaxError` ("too many nested parentheses").
- Invalid coding declaration naming a codec that doesn't exist:
  `lib2to3.pgen2.tokenize.detect_encoding` (used only by
  `encoding.py:read_lines`, for HTML rendering) raises `SyntaxError:
  unknown encoding: <name>` — confirmed directly against the real
  function on 2.7.18. JSON/text output already handled this (via
  `scan_file`'s own `ast.parse`), but HTML output crashed, since
  `render_html`'s `source_line()` calls `read_lines` directly with no
  exception handling of its own.

Fixed by broadening `scan_file`'s except clause to `(SyntaxError,
TypeError, ValueError, MemoryError, RuntimeError)` — `RuntimeError`
covers `RecursionError` (a subclass added in Python 3.5) without
referencing a name that doesn't exist on Python 2 — and by wrapping
`read_lines`'s `detect_encoding` call in `try`/`except SyntaxError`,
falling back to `utf-8`.

Checked and confirmed already correct, no fix needed, for the rest of
item 3's list: symlink loops (bounded by the OS's own `ELOOP`, already
caught by `_walk_entries`'s per-entry `OSError` handler — R5), byte-order
marks, CRLF line endings, empty files, and a directory literally named
`*.py` (`_walk_entries` checks `stat.S_ISDIR` before the `.py` extension
check, so it is always recursed into, never mistaken for a file). These
five were verified working this session via live runs against real
interpreters, but manual verification during a session is not itself a
receipt; dedicated committed tests for exactly these five follow in the
next entry.

3 new tests in this commit: `tests/test_scanner.py:
test_embedded_nul_byte_is_a_parse_blocker_not_a_crash`,
`test_deeply_nested_expression_is_a_parse_blocker_not_a_crash`;
`tests/test_report.py:
test_read_lines_falls_back_to_utf8_for_an_unknown_codec`. (The commit
message at the time said "5 new tests" — that count was wrong, corrected
here to the actual 3, confirmed via `git show 91d8bd1 -- tests/ | grep
"^+def test_"`.) Full suite at the time: 120 passed, 2 skipped (2.7.18);
115 passed, 7 skipped (3.14.7, 3.14.9). flake8 clean on 2.7.18 and
3.14.7.

**Resolved, commit `fe764df`: item 3's remaining edge-case receipts, the
JSON schema version, item 2c's never-executes guarantee, and item 5's
two-file claim.** Triggered by autosteer-architect resending the
verbatim task text and rulings after an earlier handoff turned out to be
premature — several "What done means" items had no committed receipt at
all. Closed four of them:

- **Item 3, edge-case test receipts.** The entry above's five
  "checked and confirmed already correct" cases (symlink loop, BOM,
  CRLF, empty file, directory named `*.py`) were only manually verified
  during a session, never committed as tests — not a receipt under this
  task's own rule ("an item without a receipt is not done"). Added 5
  tests to `tests/test_scanner.py`:
  `test_symlink_loop_is_a_problem_not_a_crash` (a self-referencing
  symlink inside its own directory; asserts exactly one problem whose
  reason contains `os.strerror(errno.ELOOP)`, written platform-tolerantly
  since the exact errno/text differs between Linux and macOS),
  `test_byte_order_mark_is_scanned_cleanly`,
  `test_crlf_line_endings_are_scanned_cleanly`,
  `test_empty_file_is_scanned_cleanly`,
  `test_directory_named_dot_py_is_recursed_into_not_scanned_as_a_file`.

- **Item 3, JSON schema version.** "The JSON output carries a schema
  version" had zero implementation (`grep -n "schema" py2scan/*.py
  tests/*.py` returned nothing before this commit). Added `report.py:
  SCHEMA_VERSION = 1`, included as `summarize()`'s first returned key,
  `"schema_version"`. Checked every existing call site of `summarize()`'s
  result (`tests/test_report.py`, `tests/test_cli.py`) for whole-dict
  equality assertions this new key could break — none exist; every
  assertion accesses a specific key. New test: `tests/test_report.py:
  test_summary_carries_a_schema_version`.

- **Item 2c: "the scanner never imports or executes the code it
  scans."** Previously true by architecture (`scanner.py` only calls
  `ast.parse`/`tokenize` — confirmed via grepping for `exec`, `eval(`,
  `__import__`, `importlib`, and `imp.` across `py2scan/*.py`: the only
  matches are `exec` inside rule names/strings that *detect* the `exec`
  statement in scanned code, never execute it) but never affirmatively
  tested. New test: `tests/test_scanner.py:
  test_scanner_never_executes_the_code_it_scans` — writes a file whose
  only statement is `open(<sentinel path>, 'w').close()`, which would
  create the sentinel file the instant the module were imported or
  exec'd, then asserts the sentinel is never created, through both
  `scan_file` directly and the full `scan()` pipeline (which runs each
  file in a separate worker process via `ProcessPoolExecutor` — a naive
  implementation that tried to `import` the scanned file by path in a
  worker would have executed it there).

- **Item 5: "adding a new rule touches at most two files."** True for
  the code path, with one caveat, not just asserted. `scanner.py`
  dispatches generically over `rules.AST_RULES`,
  `VERSION_AWARE_AST_RULES`, and `TOKEN_RULES` (confirmed: `grep -n
  "check_" py2scan/scanner.py` has zero hits — it never names a rule
  function), so a new rule needs only its function plus a one-line
  append to the matching list — both in `py2scan/rules.py` — and a test
  in `tests/test_rules.py`: two files. New test `tests/test_rules.py:
  test_adding_a_rule_touches_at_most_two_files` proves the structural
  half by appending a throwaway rule straight to `rules.AST_RULES` at
  runtime and confirming `scan_file` picks it up with zero change to
  `scanner.py`. **Caveat, reported rather than hidden:** `README.md` also
  documents every rule ID in a user-facing table (`grep -n "PY3-"
  README.md`); keeping that table current is a third file, for
  documentation only — the rule is fully functional and tested without
  it. No commit in this repository's history adds a single brand-new rule
  in isolation to check this claim against (the original 14 rules landed
  together in commit `0e39731`; every rule-touching commit since changes
  an existing rule's logic, not its registration), so this item's
  receipt is the structural test above, not a historical example commit.

8 new tests in this commit (5 + 1 + 1 + 1 above). One flake8 fix needed
during this work and worth recording as its own small lesson: the first
version of the item-5 test reused the loop variable name `f` for both the
file handle (`with open(...) as f:`) and the list-comprehension result
(`[f.rule for f in findings]`) in the same function — flake8 caught it as
`F812 list comprehension redefines 'f'`, and only on **2.7.18**, not on
3.14.7 or 3.14.9, because Python 2 list comprehensions leak their loop
variable into the enclosing scope while Python 3's do not. This is
exactly the kind of interpreter-version-dependent scoping difference
this whole migration is about — caught by testing the new test itself
against both interpreters, not assumed safe. Fixed by renaming the
comprehension variable to `finding`.

Full suite after every fix in this entry: 128 passed, 2 skipped
(2.7.18); 123 passed, 7 skipped (3.14.7); 123 passed, 7 skipped (3.14.9,
Docker `py2scan-test314`, matching CI). flake8 `--max-complexity 10`
clean on all three.

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

**Resolved, commit `a66f578`: item 2a, real-stdlib parity.** "Findings
after migration match findings before it except for changes the spec
items require, each covered by a test." Ran the pre-migration commit
(`0e39731`, the last commit before `py-migrate assess` started — see
`git log --all -S "def check_except_comma" --oneline` and
`git diff --stat 0e39731 HEAD -- py2scan/`) and the current `HEAD`
against the identical real tree at `/usr/local/lib/python2.7` inside the
`py2scan-test` (2.7.18) image — 1333 real files, including
`site-packages` (the task names "the real Python 2.7 stdlib
(`/usr/local/lib/python2.7` in the repo's 2.7 image)" — whatever that
path actually contains, including installed packages, is in scope; this
was not filtered down to only files under `lib/python2.7` itself, not
`site-packages`). Checked out the old commit into a disposable
`git worktree` (not the working tree), ran both through a small driver
calling `scanner.scan()` directly (bypassing the CLI, whose argument
surface changed between the two commits), and diffed every
`(file, line, rule)` triple's severity and message.

Full diff: old = 3704 findings, new = 3950. 0 findings disappeared (no
regressions - every (file, line, rule) the old scanner found, the new
one still finds). 243 new findings, all attributable to R8/R10's
expanded, interpreter-derived module/builtin lists replacing the
original small hardcoded ones: 209 `PY3-STDLIB` (e.g. `mimetools`,
`rexec`, `markupbase`, `SimpleXMLRPCServer` - never in the original
25-module `STDLIB_MODULES` set from commit `0e39731`, now caught via
`STDLIB_REMOVED_SINCE`'s full derivation) and 34 `PY3-BUILTIN` (18
`StandardError`, R10's one builtin-list addition, commit `6f3c07c`; the
other 16 - `unicode` x12, `file` x2, `basestring` x1, `raw_input` x1 -
are not new vocabulary but a real scoping bug the old flat,
whole-module `_module_bound_names` had: `gettext.py` defines
`def install(self, unicode=False, ...)`, and the old scanner's
module-wide `bound` set let that one parameter's name suppress every
unrelated `unicode(...)` call anywhere else in the same file, including
inside `ugettext`/`ungettext`, two entirely different methods - a real,
silent false-negative on real-world code, not a synthetic case. R3's
scoping rewrite (commit `054d2b2`) fixes exactly this, and already has
its own unit test (`tests/test_rules.py:
test_builtin_use_in_one_function_does_not_leak_to_another`) - this stdlib
run is independent, real-world confirmation that the same bug was live
in production-shaped code, not just the test's synthetic two-function
example.

311 changed findings (message and/or severity, same `(file, line, rule)`
key): 308 `PY3-STDLIB` - 72 blocker→warning (R2's ImportError-guard fix;
sampled `Cookie.py:213`, `SimpleHTTPServer.py:23`, `SocketServer.py:726`
directly against the real source, all three genuine
`try: from cPickle import ... except ImportError: from pickle import ...`-
shaped guards, already covered by `tests/test_rules.py`'s existing
ImportError-guard tests) and 236 message-text-only (R6's version-specific
wording: `"renamed or removed on Python 3"` → `"removed on Python 3.6"`,
etc. - already covered by R6's existing tests); 3 `PY3-PARSE` -
message-only, all three `site-packages/*` files whose message changed
from the literal hard-coded string `"does not parse under Python 2.7:
..."` (commit `0e39731`) to `"does not parse under Python 2.7.18: ..."`
(`platform.python_version()`, added in the straddle fix, commit
`5b75c6e`) - this exact patch version precision is what this session's
own `check_ne_op` 3.14.7-vs-3.14.9 regression already proved matters,
and it had no dedicated test of its own until now.

Two real test-coverage gaps surfaced by this exercise, closed in this
commit: no test exercised a `PY3-STDLIB` module outside the original
25-item hardcoded set (new test:
`test_stdlib_import_derived_beyond_the_original_hardcoded_list`,
`tests/test_rules.py`, using `mimetools`/`rexec`/`markupbase`/
`SimpleXMLRPCServer`), and no test asserted `PY3-PARSE`'s message names
the exact running interpreter rather than a hard-coded string (new test:
`test_parse_blocker_message_names_the_exact_running_interpreter`,
`tests/test_scanner.py`).

**Scope limit of this check, stated plainly:** this diff only compares
py2scan's own output across two of its own commits - it proves no
regression was introduced migrating py2scan itself, but it cannot by
construction detect a case where py2scan is simply wrong against a real
interpreter's actual behavior on *both* sides of the diff (a bug present
before and after). AutoSteer CI's independent real-interpreter check
(3.6.15–3.15.1, run against this same real stdlib tree) is the stronger
check for that failure mode and is tracked separately below, where it is
currently failing - see Blockers.

Driver scripts and the comparison tool live in `.py-migrate/out/`
(gitignored, not committed - per-session scratch, reproducible from the
commands above) rather than as a committed script, since the "before"
side requires a disposable `git worktree` at a specific historical
commit, which only makes sense run once per parity check, not as a
standing CI-run script.

2 new tests in this commit (the two gap closures above). Full suite:
130 passed, 2 skipped (2.7.18); 125 passed, 7 skipped (3.14.7, 3.14.9).
flake8 `--max-complexity 10` clean on all three.

**Resolved, commit `4e52811`: two new rules, `PY3-UR-STRING` and
`PY3-UNICODE-ESCAPE`, closing an R1 violation AutoSteer CI's own
real-interpreter check found on real stdlib files that this session's
own item-2a diff (above) could not, by construction - that check only
compares py2scan's output against its own earlier commit, so it cannot
catch a defect present on both sides.** AutoSteer reported, against the
real stdlib tree at `/usr/local/lib/python2.7`: real 3.6.15 through
3.15.1 cannot compile `json/__init__.py`, `lib2to3/fixes/fix_unicode.py`,
or `posixpath.py`, yet the 2.7 scan reported no blocker for any of
3.6–3.15 on any of the three — a direct violation of R1's "never
reported free of blockers" guarantee.

Root cause, two distinct Python-2-only lexical constructs, neither
caught by any existing rule:
- `posixpath.py:299` and `fix_unicode.py` (4 occurrences) use a
  raw-unicode string prefix (`ur'...'`). Confirmed empirically on real
  2.7.18: only the `u`-before-`r` ordering is valid (`ur`/`Ur`/`uR`/`UR`;
  `ru`/`Ru`/`rU`/`RU` is a `SyntaxError` even on 2.7.18). Confirmed on
  real 3.14.9: every one of those 4 orderings is `'u' and 'r' prefixes
  are incompatible` — and not just at `ast.parse`, but inside
  `tokenize` itself (confirmed empirically: `tokenize.tokenize()` on
  `ur'test'` under 3.14.7 raises `TokenError`, not just a later
  `SyntaxError`) - `ur` has never been valid in Python 3, even after
  3.3 restored `u` as a no-op prefix.
- `json/__init__.py`'s own docstring (line 133) uses `` \uXXXX `` as
  human-readable placeholder text inside a bare (unprefixed) string
  literal. Confirmed empirically: a bare string's `\u`/`\U`/`\N{...}`
  escape is inert, unprocessed text on 2.7.18 (Python 2 only processes
  those escapes inside a `u`-prefixed string), but every non-raw,
  non-bytes string on Python 3 is unicode and always processes them, so
  an invalid one (`\uXXXX` is not 4 hex digits) is a `SyntaxError`.
  Confirmed empirically that a `b'...'`-prefixed string behaves
  identically on both interpreters (neither processes `\u`), so it must
  not be flagged - only a fully bare string (no `u`, `r`, or `b` in its
  prefix) has this 2-vs-3 difference.

Both added as new `TOKEN_RULES` in `py2scan/rules.py`
(`check_ur_string`, `check_unicode_escape`), following the existing
`check_ne_op`/`check_octal` pattern - both are 2-vs-3 boundary issues
(every judged version, not R6-scoped to a specific one), and both can
only ever fire when `ast.parse` already succeeded, i.e. only on the 2.7
side of a straddle, since every Python 3.x already rejects both
constructs at `ast.parse` (or earlier, for `ur`-strings). Verified the
fix directly against the exact 3 real files AutoSteer named, inside the
2.7.18 image: `posixpath.py` → 1 `PY3-UR-STRING` blocker;
`fix_unicode.py` → 4 `PY3-UR-STRING` blockers; `json/__init__.py` → 1
`PY3-UNICODE-ESCAPE` blocker. 12 new tests (`tests/test_rules.py`),
including the exact `ur`-ordering matrix, the byte/raw/u-prefix
exclusions, an escaped-backslash-before-`u` non-match, and the
`\N{...}` name-escape form. The two `ur`-string "found" tests are marked
with the existing `PY2_ONLY_SYNTAX` skip (same reasoning as the
print/exec/backtick/raise-comma tests already using it): calling
`_tokenize()` directly on `ur'...'` source fails on Python 3 for a
reason that has nothing to do with this rule's own logic, and the real
`scan_file` pipeline never reaches a `TOKEN_RULE` for this input on
Python 3 anyway, since `ast.parse` already raises first.

Full suite: 142 passed, 2 skipped (2.7.18); 135 passed, 9 skipped
(3.14.7, 3.14.9). flake8 `--max-complexity 10` clean on all three.

## Flip preparation (prepared, not executed — see commit `09a45fd` for the
one piece of infra this added; nothing below was merged, shipped, or
changed outside this branch)

py2scan is a CLI tool, not a running service — there is no fleet, no
canary host pool, and no deploy manifest to speak of, so this section
adapts `flip`'s checklist (runtime pins, canary, rollback) to what that
actually means for a `pip install`-able package rather than forcing the
server-migration framing where it doesn't fit.

**What would change at flip** (drafted here, not applied — these are the
owner's edits to make and merge):
- `setup.py:python_requires` currently reads
  `">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*,!=3.5.*"` — this already
  allows 2.7 *and* 3.6+ simultaneously (straddle), not 3-only. At flip this
  narrows to `">=3.6"` and drops 2.7 and the `!=3.x.*` exclusions
  entirely, since R6–R10 already fixed 3.6 as the lowest judged version.
  (Corrected a stale Runtime surfaces table entry this session, which had
  claimed this field was still `"==2.7.*"` — it was already widened, in
  commit `5b75c6e`, before this session started; the table just hadn't
  caught up. Not a flip-prep change itself, a documentation fix.)
- `requirements.txt`/`setup.py`'s `install_requires`: drop the
  `python_version<"3"` pins (`PyYAML==5.4.1`, `futures==3.3.0`) and their
  markers, keeping only the `>=3` side of each already-present split.
- `Dockerfile.test`: swaps role from primary to legacy/compat-check, or
  retires outright at `cleanup`, once no supported step still needs 2.7.18
  — not decided here; that is a `cleanup`-stage call, past flip.
- `CLAUDE.md` (project, not committed): "Runtime is Python 2.7.18 only" —
  owner-authored prose, explicitly the owner's edit per the existing
  Runtime surfaces table row, not touched by this prep.

**Canary, adapted for a CLI tool (no server fleet to stage against):**
parity-check real scan roots, not synthetic ones — run both the pinned
2.7.18 install and the 3.14 install of the *same* py2scan commit against
several real external codebases (not just this repo's own tiny fixture
set) and diff the JSON output. Expect exactly the one known, already
-recorded divergence (item 2b: `PY3-PRINT`/`PY3-EXEC-STMT`/
`PY3-BACKTICK`/`PY3-RAISE-COMMA`/`PY3-NE-OP`/`PY3-OCTAL`/
`PY3-LONG-SUFFIX` findings on 2.7.18 report as a single `PY3-PARSE` on
3.14, since Python 3's own `ast.parse` can't produce the specific node
types those rules look for) — any *other* diff found during this check is
a new, real regression, not a known/accepted one, and blocks flip until
explained.

**Rollback:** a `pip install py2scan==<last-2.7-compatible-version>` (or
the matching git tag) reinstalls the pre-flip package on a 2.7
environment; nothing server-side to roll back since nothing is deployed.

**Mixed-fleet data:** N/A — py2scan has no stored data (see Stored data,
below) and no shared state between installs; each user's install is
independent, so there is no mixed-version-fleet consistency concern the
way a running service would have.

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
| six | (not pinned; 1.17.0 installed transitively) | neither | Not in `requirements.txt`/`setup.py` at all as of commit `5b75c6e` (the row below was stale — corrected this session). It still appears installed in the 2.7.18 test image (`pip show six` → `Required-by: pytest, pathlib2, more-itertools`): a transitive dependency of `pytest==4.6.11` itself, not of py2scan. Out of R11 scope — see Blockers, R11 writeup | `pip show six`, this session |

Done, commit `5b75c6e`: PyYAML pinned to 6.0.3 for the target side only
(`python_version >= "3"`) while the source pin stays at 5.4.1 per the
architect's "source-side pins stay while you straddle" ruling; `futures`
moved behind `python_version < "3"`; `six` dropped entirely. Verified: both
pins install and import cleanly on their respective interpreters.

## Runtime surfaces
| File | Pins | Unit | Changes at flip |
|---|---|---|---|
| `Dockerfile.test` | `FROM python:2.7.18-slim` | py2scan | source-side test image |
| `Dockerfile.test314` | `FROM python:3.14-slim` | py2scan | target-side test image, added this session (flip prep) — same `requirements.txt`/`requirements-dev.txt` as the source image, since both already carry `python_version` markers; resolves to 3.14.9 (matches CI), used for this session's `verify` pass instead of the ad hoc pip install used earlier |
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
| 3.0–3.14 Porting/Removed sections, full sweep | done, this session | [What's New](https://docs.python.org/3/whatsnew/) index, every version 3.0–3.14, fetched and grepped against py2scan's own exact stdlib footprint | `curl` each page, strip tags, grep against `json`/`sys`/`io`/`collections`/`os`/`ast`/`functools`/`platform`/`stat`/`tokenize`/`concurrent.futures`/`re` and the exact attributes py2scan calls on each | 1 genuine, previously-undiscovered defect found and fixed (`os.listdir` raw-bytes/surrogateescape filenames crashing output on both interpreters, two different ways) — see Blockers, Resolved; everything else checked clean with reasoning recorded, not just asserted |
| R6 version matrix (3.6–3.15) | per-rule version applicability | one primary source + one real-interpreter test per rule per relevant version | done, this session (R6–R10) | implemented — see Blockers, Resolved (`STDLIB_REMOVED_SINCE`, `BUILTIN_NAMES`, `Finding.versions`) |

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
| 2026-10-22 | 41792b8 | py2scan | 2.7.18→3.14 | (R6-R10 implementation) | full suite on both real interpreters after implementing `--target-version`, `STDLIB_REMOVED_SINCE`, per-finding `versions`, and per-version `readiness` | `115 passed, 2 skipped` on 2.7.18 (Docker, root); `112 passed, 5 skipped` on 3.14.7 |
| 2026-10-22 | 41792b8 | py2scan | 2.7.18→3.14 | (flake8, not a level) | `flake8 --max-complexity 10 py2scan tests` under both real interpreters | 0 violations of any kind, both interpreters |
| 2026-10-22 | 41792b8 | py2scan | 2.7.18→3.14 | (manual CLI smoke test) | invoked `py2scan.cli.main` directly (text/json/html) against a scan root with `import distutils` + `import urllib2` + `unicode('hi')`, with `--target-version 3.9,3.12` and with the `all` default | distutils scoped to `["3.12"]` only; urllib2/unicode scoped to every judged version; JSON `readiness` keyed by version; HTML report rendered the per-version table and per-finding Versions column without template errors; unknown `--target-version` rejected with `click.BadParameter`, exit code 2 |
| 2026-10-22 | n/a (CI notice, no code change yet) | py2scan | 2.7.18→3.14 | (AutoSteer CI finding) | AutoSteer CI run on commit `d343999`, `python:2.7.18-slim` + `python:3.14-slim` | 2.7: `117 passed`; 3.14 (resolves to 3.14.9): `1 failed, 111 passed, 5 skipped` — `tests.test_rules::test_ne_op_is_found` |
| 2026-10-22 | n/a (research, no code change) | py2scan | (check_ne_op root cause) | `tokenize.tokenize()` on `b'x = 1 <> 2\n'`, compared directly between real 3.14.7 (Homebrew venv) and real 3.14.9 (Docker `python:3.14-slim`, confirmed via `python3 --version`) | 3.14.7: one `OP` token `"<>"`; 3.14.9: two adjacent `OP` tokens, `"<"` then `">"`, with `end` of the first == `start` of the second |
| 2026-10-22 | 2f33844 | py2scan | (check_ne_op fix) | `pytest tests/test_rules.py -k ne_op -v` on 2.7.18 (Docker `py2scan-test`), 3.14.7 (Homebrew venv), and 3.14.9 (Docker `python:3.14-slim`, ad hoc `click==7.1.2 Jinja2==2.11.3 MarkupSafe==1.1.1 PyYAML==6.0.3 pytest==9.1.1`) | `1 passed` on all three |
| 2026-10-22 | 2f33844 | py2scan | (check_ne_op fix, full suite) | full suite on 2.7.18 (Docker `py2scan-test`), 3.14.7 (Homebrew venv), and 3.14.9 (Docker `python:3.14-slim`) | `115 passed, 2 skipped` on 2.7.18; `112 passed, 5 skipped` on 3.14.7; `110 passed, 7 skipped` on 3.14.9 (2 extra skips vs. 3.14.7 are the same root-dependent tests already skipped non-root — no new skip category) |
| 2026-10-22 | 2f33844 | py2scan | (check_ne_op fix, flake8) | `flake8 --max-complexity 10 py2scan tests` on 2.7.18 (Docker `python:2.7.18-slim`, ad hoc `flake8<4`) and 3.14.7 (Homebrew venv) | 0 violations of any kind, both interpreters |
| 2026-10-22 | n/a (research, no code change) | py2scan | (R11, runtime deps) | `POST https://api.osv.dev/v1/query` for click 7.1.2, Jinja2 2.11.3, MarkupSafe 1.1.1, PyYAML 5.4.1, PyYAML 6.0.3, futures 3.3.0, six 1.17.0, pytest 4.6.11, pytest 9.1.1 | 0 vulns: click, MarkupSafe, both PyYAML pins, futures, six, pytest 9.1.1; Jinja2 2.11.3: 4 real CVEs (CVE-2025-27516, CVE-2024-22195, CVE-2024-34064, CVE-2024-56326); pytest 4.6.11: 1 real CVE (CVE-2025-71176) |
| 2026-10-22 | n/a (research, no code change) | py2scan | (R11, Jinja2 reachability) | `grep -n "xmlattr\|sandbox\|Environment" py2scan/report.py` against the 4 Jinja2 CVEs' actual trigger conditions | `py2scan/report.py:13` uses a plain `jinja2.Environment(autoescape=True)`, never `SandboxedEnvironment`; `_TEMPLATE` never uses the `xmlattr` filter — none of the 4 CVEs have a reachable path through py2scan's own code |
| 2026-10-22 | n/a (research, no code change) | py2scan | (R11, interpreter advisories) | `GET https://services.nvd.nist.gov/rest/json/cves/2.0?cpeName=cpe:2.3:a:python:python:2.7.18:...` and the same for `3.14.7` | 2.7.18: 38 raw matches, 3 confirmed false positives (`vulnerable: false` on the `python:python` CPE node in NVD's own `configurations` data), 35 remaining all have an unbounded (from-version-0) lower range bound, none concern a module py2scan's own code imports; 3.14.7: 4 raw matches, all 4 the same false-positive pattern, 0 genuine |
| 2026-10-22 | n/a (research, no code change) | py2scan | (full sweep) | fetched and grepped `docs.python.org/3/whatsnew/{3.0..3.14}.html` against py2scan's own stdlib footprint | 1 genuine defect found (`os.listdir` undecodable filenames); everything else checked clean, reasoning recorded per item |
| 2026-10-22 | n/a (research, no code change) | py2scan | (bad-byte filename, root cause) | real Docker fixture, a `.py` file named with a byte invalid in UTF-8, scanned via the actual CLI (text/json/html) on `python:2.7.18-slim` and `python:3.14-slim` | scan itself always correct; 2.7.18 output crashes with `UnicodeDecodeError` in all 3 formats; 3.14.9 output crashes with `UnicodeEncodeError` in text/html only (not json, whose `ensure_ascii=True` tolerates the lone surrogate) |
| 2026-10-22 | cc12b90 | py2scan | (bad-byte filename fix) | same fixture, all 3 formats, after adding `encoding.py:safe_text` | 0 crashes on either interpreter; output identical across both (`bad_�_name.py`) |
| 2026-10-22 | cc12b90 | py2scan | (bad-byte filename fix, full suite) | full suite on 2.7.18 (Docker `py2scan-test`), 3.14.7 (Homebrew venv), 3.14.9 (Docker `python:3.14-slim`) | `117 passed, 2 skipped` on 2.7.18; `112 passed, 7 skipped` on 3.14.7 (2 new tests skip - Mac host filesystem rejects the fixture); `112 passed, 7 skipped` on 3.14.9 (2 new tests pass - Linux) |
| 2026-10-22 | cc12b90 | py2scan | (bad-byte filename fix, flake8) | `flake8 --max-complexity 10 py2scan tests` on 2.7.18 (Docker `python:2.7.18-slim`, ad hoc `flake8<4`) and 3.14.7 (Homebrew venv) | 0 violations of any kind, both interpreters |
| 2026-10-22 | 0f40071 | py2scan | 2.7.18→3.14 | L3 (flagged missing by AutoSteer CI after the fact; added here, not re-dated) | aggregation, not a single command: Units table blocker count (0 auto / 0 manual, confirmed by this session's R6–R10/R11/sweep closures above), every `requirements.txt` pin re-checked against the Dependencies table's own "Yes, both (verified)" rows (actual installs/imports, not a resolver dry-run), Runtime surfaces table's existing plan, no stored data for this CLI tool | all four L3 preconditions hold; no single command produces this level, which is why the row was easy to miss — recorded explicitly now so the next level transition doesn't repeat the gap |
| 2026-10-22 | 0f40071 | py2scan | 2.7.18→3.14 | L4 (`verify`, deliberate pass, not incidental) | `docker build -q -f Dockerfile.test -t py2scan-test . && docker run --rm -v "$PWD":/app -w /app py2scan-test python -m pytest -q -p no:cacheprovider tests` | `117 passed, 2 skipped` |
| 2026-10-22 | 0f40071 | py2scan | 2.7.18→3.14 | L4 (`verify`) | `python3.14 -m pytest -q -p no:cacheprovider tests` (3.14.7, Homebrew venv) | `112 passed, 7 skipped` |
| 2026-10-22 | 0f40071 | py2scan | 2.7.18→3.14 | L4 (`verify`) | same command inside `python:3.14-slim` (3.14.9, matching CI) | `112 passed, 7 skipped` |
| 2026-10-22 | 0f40071 | py2scan | 2.7.18→3.14 | L4 (`verify`, compile_check) | `.py-migrate/compile_check.py` against every tracked file (`git ls-files`), on 2.7.18 (Docker) and 3.14.7 | `checked 17, failed 0, unreadable 0` on both |
| 2026-10-22 | 0f40071 | py2scan | 2.7.18→3.14 | L4 (`verify`, flake8) | `flake8 --max-complexity 10 py2scan tests` on 2.7.18 (Docker, ad hoc `flake8<4`) and 3.14.7 | 0 violations, both interpreters |
| 2026-10-22 | n/a (research, no code change) | py2scan | (item 3, NUL byte / deep nesting / bad codec, root cause) | an embedded NUL byte and a 3000-deep nested-paren expression fed directly to `ast.parse` on real 2.7.18 (Docker) and 3.14.9 (Docker); a coding declaration naming a nonexistent codec fed directly to `lib2to3.pgen2.tokenize.detect_encoding` on real 2.7.18 | 2.7.18 raises `TypeError` (NUL byte) and `MemoryError` (deep nesting), both uncaught by the original `except SyntaxError`; 3.14.9 raises plain `SyntaxError` for both; `detect_encoding` raises `SyntaxError: unknown encoding: bogus-nonexistent-codec`, uncaught in `encoding.py:read_lines`, crashing HTML rendering only |
| 2026-10-22 | 91d8bd1 | py2scan | (item 3, NUL byte / deep nesting / bad codec, fix) | full suite on 2.7.18 (Docker `py2scan-test`), 3.14.7 (Homebrew venv), 3.14.9 (Docker `py2scan-test314`) | `120 passed, 2 skipped` on 2.7.18; `115 passed, 7 skipped` on 3.14.7 and 3.14.9 |
| 2026-10-22 | 91d8bd1 | py2scan | (item 3, NUL byte / deep nesting / bad codec, flake8) | `flake8 --max-complexity 10 py2scan tests` on 2.7.18 (Docker, ad hoc `flake8<4`) and 3.14.7 | 0 violations, both interpreters |
| 2026-10-22 | n/a (research, no code change) | py2scan | (item 3, symlink loop / BOM / CRLF / empty file / `*.py` directory) | a self-referencing symlink, a BOM-prefixed file, a CRLF file, a 0-byte file, and a directory literally named `weird.py`, each scanned via real `scan`/`scan_file` calls on 2.7.18 | all 5 already handled correctly with no crash and no code change — confirms the manual verification claimed in the `91d8bd1` writeup above, closing the gap before committing dedicated tests for each |
| 2026-10-22 | fe764df | py2scan | (item 3 edge-case tests, item 3 schema version, item 2c, item 5) | full suite on 2.7.18 (Docker `py2scan-test`), 3.14.7 (Homebrew venv), 3.14.9 (Docker `py2scan-test314`) | `128 passed, 2 skipped` on 2.7.18; `123 passed, 7 skipped` on 3.14.7 and 3.14.9 |
| 2026-10-22 | fe764df | py2scan | (item 3 edge-case tests, item 3 schema version, item 2c, item 5, flake8) | `flake8 --max-complexity 10 py2scan tests` on 2.7.18 (Docker, ad hoc `flake8<4`), 3.14.7 (Homebrew venv), and 3.14.9 (Docker `py2scan-test314`, ad hoc `flake8`) | first pass: 1 violation, 2.7.18 only (`F812 list comprehension redefines 'f'` in the new item-5 test — a real Python-2-only scoping difference, not a false positive); 0 violations on 3.14.7/3.14.9; after renaming the comprehension variable, 0 violations on all three |
| 2026-10-23 | n/a (research, no code change) | py2scan | (item 2a, real stdlib parity, root cause) | `git worktree add --detach .py-migrate/out/before_worktree 0e39731`; two driver scripts calling `scanner.scan()` directly against `/usr/local/lib/python2.7` inside `py2scan-test` (2.7.18), once per commit (`0e39731`, `HEAD`); a Python diff script keyed on `(file, line, rule)` | old: 1333 files, 3704 findings; new: 1333 files, 3950 findings; 0 removed, 243 added (209 `PY3-STDLIB`, 34 `PY3-BUILTIN`), 311 changed message/severity (308 `PY3-STDLIB`, 3 `PY3-PARSE`) — full breakdown in Blockers, Resolved |
| 2026-10-23 | a66f578 | py2scan | (item 2a, two new regression tests) | full suite on 2.7.18 (Docker `py2scan-test`), 3.14.7 (Homebrew venv), 3.14.9 (Docker `py2scan-test314`) | `130 passed, 2 skipped` on 2.7.18; `125 passed, 7 skipped` on 3.14.7 and 3.14.9 |
| 2026-10-23 | a66f578 | py2scan | (item 2a, two new regression tests, flake8) | `flake8 --max-complexity 10 py2scan tests` on 2.7.18 (Docker, ad hoc `flake8<4`), 3.14.7 (Homebrew venv), and 3.14.9 (Docker `py2scan-test314`, ad hoc `flake8`) | 0 violations, all three |
| 2026-10-23 | n/a (AutoSteer CI notice, no code change yet) | py2scan | (AutoSteer CI finding, R1 on real stdlib) | AutoSteer CI run against the real stdlib tree, 3.6.15–3.15.1 | 3 real files (`json/__init__.py`, `lib2to3/fixes/fix_unicode.py`, `posixpath.py`) that real 3.6–3.15 cannot compile, with no blocker reported on the 2.7 scan for any of them — R1 violation |
| 2026-10-23 | n/a (research, no code change) | py2scan | (root cause, `ur`-string and invalid `\u` escape) | `ast.parse`/`tokenize.tokenize` on real 2.7.18 and 3.14.7/3.14.9 for all 8 u/r prefix orderings, and for a bare string with `\uXXXX` vs. `b'\uXXXX'` vs. `r'\uXXXX'` vs. `u'\uXXXX'` | 2.7.18 accepts exactly `ur`/`Ur`/`uR`/`UR` (not `ru` etc); every Python 3.x rejects all 8, and 3.14.7's own `tokenize` module raises `TokenError` for it, not just a later `SyntaxError`; a bare string's invalid `\u` escape is inert on 2.7.18 but a `SyntaxError` on every Python 3.x; `b'...'` behaves identically on both (never flagged) |
| 2026-10-23 | 4e52811 | py2scan | (`PY3-UR-STRING`/`PY3-UNICODE-ESCAPE` fix) | `scan_file` against the exact 3 real files AutoSteer named, inside `py2scan-test` (2.7.18) | `posixpath.py` → 1 `PY3-UR-STRING` blocker; `fix_unicode.py` → 4 `PY3-UR-STRING` blockers; `json/__init__.py` → 1 `PY3-UNICODE-ESCAPE` blocker — all 3 R1 violations closed |
| 2026-10-23 | 4e52811 | py2scan | (`PY3-UR-STRING`/`PY3-UNICODE-ESCAPE` fix, full suite) | full suite on 2.7.18 (Docker `py2scan-test`), 3.14.7 (Homebrew venv), 3.14.9 (Docker `py2scan-test314`) | `142 passed, 2 skipped` on 2.7.18; `135 passed, 9 skipped` on 3.14.7 and 3.14.9 |
| 2026-10-23 | 4e52811 | py2scan | (`PY3-UR-STRING`/`PY3-UNICODE-ESCAPE` fix, flake8) | `flake8 --max-complexity 10 py2scan tests` on 2.7.18 (Docker, ad hoc `flake8<4`), 3.14.7 (Homebrew venv), and 3.14.9 (Docker `py2scan-test314`, ad hoc `flake8`) | 0 violations, all three |

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
