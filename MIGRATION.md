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

**Update, 2026-10-23: confirmed at real-stdlib scale by AutoSteer CI,
and two more rules and two more hostile inputs join this same defect
category — not new defects, the same one, observed on more inputs.**
AutoSteer's own real-interpreter diff against the full stdlib tree
reported "findings: 3144 only on 2.7, 243 only on 3.14" — every single
one of those 243 "only on 3.14" findings is `PY3-PARSE` (confirmed via a
direct reproduction: `scanner.scan()` against the same real tree on both
interpreters, diffed by `(file, line, rule)`), and every one of the
3144 "only on 2.7" findings is one of: `PY3-PRINT` (1163),
`PY3-RAISE-COMMA` (742), `PY3-BUILTIN` (298), `PY3-STDLIB` (277),
`PY3-EXCEPT-COMMA` (226), `PY3-LONG-SUFFIX` (102), `PY3-DICT-ITER` (89),
`PY3-OCTAL` (88), `PY3-DIVISION` (77), `PY3-EXEC-STMT` (63),
`PY3-UR-STRING` (13), `PY3-PARSE` (3, the `platform.python_version()`
message-text-only cases already in item 2a's entry below),
`PY3-UNICODE-ESCAPE` (2), `PY3-METACLASS` (1) — every rule already named
above, plus the two new ones from this session's R1 fix
(`PY3-UR-STRING`, `PY3-UNICODE-ESCAPE`). `ast.parse` stops at the first
syntax error per file, which is why one file with several 2-vs-3
constructs produces several granular findings on 2.7 but only ever one
`PY3-PARSE` on 3.x. The `PY3-UR-STRING`/`PY3-UNICODE-ESCAPE` case differs
from the original 7 in its underlying mechanism (a lexer/constant-
folding rejection, not an absent `ast` node type), but the operational
conclusion is identical: the source-side rule exists specifically to
detect the construct that becomes `PY3-PARSE` on the target, so no code
change on either side can close this while straddling.

AutoSteer also named two hostile-input cases with the same shape, both
confirmed via direct reproduction to be this exact defect, not a new
one: `hostile/nul_byte` (2.7's message is `TypeError`-derived -
`"compile() expected string without null bytes"`; 3.x's is its own
native `SyntaxError` text - `"source code string cannot contain null
bytes"` - same rule, same severity, different message, so not
byte-identical) and `hostile/invalid_coding` (both sides report the
identical "unknown encoding: ..." text, but with the exact running
interpreter's own version number embedded via `platform.python_version()`
- "Python 2.7.18" vs "Python 3.14.9" - the very precision item 2a's own
entry below found missing and fixed; losing that precision to force
byte-identical JSON would reintroduce the problem item 2a just closed).

**Correction, 2026-10-23 (flagged by AutoSteer's third review): the
"no code change on either side can close this while straddling" claim
above was wrong for 5 of its 7 original inputs, and for most of the
stdlib-scale totals quoted above - narrowed, not withdrawn; see
"Resolved, commit `64ced43`: scanner.scan_file runs SOURCE_RULES and
TOKEN_RULES independent of ast.parse" below for the fix and full
before/after counts.** The claim conflated two different reasons a
rule's finding can be missing on the target: (a) the rule needs a real
`ast` tree and none exists once `ast.parse` fails (true, structural,
still unfixable without a Python 2 parser) and (b) the rule only needed
*tokens*, which `scanner.scan_file` was discarding anyway whenever
`ast.parse` failed, for no reason connected to whether tokenizing
itself had succeeded. `check_except_comma` already proved this
distinction mattered (it was correctly excluded from the original 7
precisely because it does not need a tree), but the same reasoning was
never applied to `check_ne_op`, `check_octal`, `check_long_suffix`,
`check_unicode_escape`, or `check_raise_comma` (the last one AST-based
at the time, not yet converted - see below). Checked directly against
real 2.7.18 and real 3.14.9, on the same real-stdlib tree AutoSteer used
(excluding `site-packages/`, which is this test fleet's own installed
dependencies, not stdlib): `PY3-EXCEPT-COMMA` 271/271, `PY3-OCTAL`
91/91, `PY3-LONG-SUFFIX` 116/116, `PY3-UNICODE-ESCAPE` 2/2, `PY3-NE-OP`
0/0 in this corpus but confirmed fixed directly (`x <> y` now reports
both `PY3-PARSE` and `PY3-NE-OP` on 3.14.9, not `PY3-PARSE` alone), and
`PY3-RAISE-COMMA` 741/741 (0 lost, down from 100% lost - this was the
single largest category in the stdlib-scale total above). Genuinely
still unfixable, confirmed by direct reproduction below the fix:
`PY3-BACKTICK` (backtick is not valid Python 3 at the lexical level at
all - `ast.parse` and `tokenize.tokenize` both reject it), the bare,
no-parens forms of `print x` and `exec 'x = 1'` (these are a flat
`SyntaxError` on Python 3's own grammar regardless of tokens - nothing
to recover, and R1's guarantee is already satisfied by `PY3-PARSE`
alone), `PY3-BUILTIN`/`PY3-DICT-ITER`/`PY3-DIVISION`/`PY3-STDLIB`/
`PY3-METACLASS` (genuinely `AST_RULES`, need a real tree), and
`PY3-UR-STRING` (Python 3.9+'s own tokenizer rejects a `ur`-prefixed
string directly, confirmed - like backtick, this fails before any
token-based rule could see it). The "no second interpreter once there
is no straddle" framing in the paragraph above still holds for exactly
this narrower, now-correctly-scoped remainder.

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

**Resolved, commit `858728c`: `file_readiness`, closing R6's "for each
file, the report says which versions it is ready for" - AutoSteer CI's
own gloss on R6, confirmed as a real gap, not a misreading.** Before
this: `summarize()`'s `"findings"` list only ever contains files that
have at least one finding, and `"files"` is a count, not a list - a
clean file (no findings at all) was named *nowhere* in the JSON output,
with no way for a consumer to tell "this file was scanned and is ready
for every version" apart from "this file was never scanned at all."
Confirmed at scale by AutoSteer against the real stdlib: 623/1104 files
on the 2.7 side, 640/1104 on the 3.14 side, and all 11/11 hostile test
cases' `ok.py` (which has zero findings by construction) were affected.

Added a new key, `file_readiness`: `{relpath: [the judged versions that
file is ready for]}`, built in `report.py:summarize()` by reusing the
same per-version `blocker_files` set the existing `readiness` percentage
loop already computes (no duplicated blocker-finding logic) and
inverting it per file. An empty list means blocked on every judged
version; a file with no entry never happens, since every file in `files`
always gets a `file_readiness` entry regardless of whether it has any
findings. Did not bump `SCHEMA_VERSION`: this is a strictly additive new
key, not a change to any existing key's shape, so an existing consumer
that ignores unknown keys keeps working unchanged - `SCHEMA_VERSION`'s
own stated purpose (see its addition above) is to flag a *breaking*
shape change, which this is not.

**Scope, stated explicitly:** only the JSON output gained this key.
AutoSteer's own hostile-input reproduction command
(`python -m py2scan scan --format json <case dir>`) is JSON-only, and
JSON is the machine-checkable "report" data contract R6 is about; the
existing HTML report already shows a per-version readiness table and a
per-finding versions column, and a file with zero findings never having
its own HTML row is a reasonable property of human-readable output (no
news is good news), not something this fix changed.

4 new tests (`tests/test_report.py`), including the empty-findings case
that was previously impossible to express at all through this key, the
version-scoped-blocker case, a warning not blocking any version, and a
version-invariant blocker blocking every version. Verified directly
against a real reproduction of AutoSteer's own `hostile/nul_byte` case
(`ok.py` + `t.py`): `{"ok.py": [... all 10 judged versions ...], "t.py":
[]}`.

Full suite: 146 passed, 2 skipped (2.7.18); 139 passed, 9 skipped
(3.14.7, 3.14.9). flake8 `--max-complexity 10` clean on all three.

**Resolved, commit `04f2aa1`: `hostile/deep_nesting` (R1), via a new
rule, `PY3-NESTING-DEPTH`.** AutoSteer: "real 3.6-3.8 cannot compile [a
file with 150 nested parentheses], and the scan on 3.14 reports no
blocker for 3.6-3.8." A prior pass here investigated this and declined
to ship a rule, reasoning that the crossover depth is a pathological-
input *parser resource limit*, not a fixed language-grammar fact, and
that it did not track "parser generation" cleanly across 2.7.18, 3.6.15,
3.7 and 3.8. The architect's reply pointed back to the existing rulings
rather than issuing a new one: R1 requires every such input recorded as
a defect with the input attached, not accepted as a divergence; "accept
with an expiry" is item 4's mechanism for security advisories only, not
a general escape hatch; and R6/R7 already say version facts come from
the interpreters themselves, tested against a final release of each one
- which is exactly what this project's other per-version tables
(`BUILTIN_NAMES`, `STDLIB_REMOVED_SINCE`) already do. Redone properly
against all 10 judged versions' own final releases (3.6.15, 3.7.17,
3.8.20, 3.9.25, 3.10.19, 3.11.14, 3.12.12, 3.13.12, 3.14.7, 3.15.1 - the
same releases `BUILTIN_NAMES`/`STDLIB_REMOVED_SINCE` were measured
against) rather than the mixed, partial set used the first time:

| Version | `()` crossover | `[]` crossover | `{}` crossover |
|---|---|---|---|
| 2.7.18 (source, not judged) | 98 / 99 | 98 / 99 | 98 / 99 |
| 3.6.15 | 92 / 93 | 92 / 93 | 92 / 93 |
| 3.7.17 | 92 / 93 | 92 / 93 | 92 / 93 |
| 3.8.20 | 98 / 99 | 98 / 99 | **104 / 105** |
| 3.9.25 | 200 / 201 | 200 / 201 | 200 / 201 |
| 3.10.19 | 200 / 201 | 200 / 201 | 200 / 201 |
| 3.11.14 | 200 / 201 | 200 / 201 | 200 / 201 |
| 3.12.12 | 200 / 201 | 200 / 201 | 200 / 201 |
| 3.13.12 | 200 / 201 | 200 / 201 | 200 / 201 |
| 3.14.7 | 200 / 201 | 200 / 201 | 200 / 201 |
| 3.15.1 | 200 / 201 | 200 / 201 | 200 / 201 |

("crossover" = last depth that compiles / first depth that fails, each
measured by binary search directly against `python:<version>-slim`.)

This is a cleaner result than the first pass found, for a concrete
reason: 3.9 through 3.15 (the PEG parser, introduced in 3.9) all hit the
*exact same* depth, 201, for every bracket shape, and the `SyntaxError`
each one raises literally says `"too many nested parentheses"` even when
the source nests `[]` or `{}` instead - a single hardcoded, shape-
agnostic constant, not a resource limit, confirmed identical across
three final releases spanning the whole range (3.9.25, 3.14.7, 3.15.1).
That qualifies as the kind of static, version-level fact R9 asks for.
The old pgen parser (2.7, 3.6-3.8) is still a real stack-depth resource
limit, not a constant, and 3.8.20 proves it: `()`/`[]` fail at 99, but
`{}` (a nested dict literal, `{0:{0:{0:...}}}`) fails only at 105,
confirmed deterministic across three repeated runs. Using the *lower* of
the two measured shapes per version, rather than either alone, is the
direction that can never under-report a real blocker (R1) - at the cost
of a narrow, already-disclosed over-block for 3.8-only dict nesting
between depth 99 and 104, which R1 does not forbid.

`check_nesting_depth` (`py2scan/rules.py`) counts `(`, `[` and `{`
together as one depth from the token stream (matching the tokenizer's
own combined accounting - confirmed directly that alternating bracket
kinds reach the same combined crossover as either kind alone, on both
a pgen version and a PEG version) and, for each judged version whose
measured limit the file's max depth exceeds, adds a `PY3-NESTING-DEPTH`
blocker scoped to exactly that subset - the same per-version scoping
`check_stdlib_import` already does for `PY3-STDLIB`. It runs as a new
`VERSION_AWARE_TOKEN_RULES` list, parallel to the existing
`VERSION_AWARE_AST_RULES`; `scanner.scan_file` gained one more dispatch
loop for it, which pushed its own McCabe complexity to 11 - fixed by
pulling all four rule-dispatch loops into a new `_run_rules` helper
(`scanner.py`), dropping `scan_file` back under the `--max-complexity
10` limit. Item 5's "two files" claim is unaffected for a rule added to
an *existing* list; introducing a new list is the same, already-
established exception `VERSION_AWARE_AST_RULES` itself is.

The token stream can only ever hand this rule a depth up to the running
interpreter's own limit: on 3.9+, the C tokenizer enforces the identical
200 the parser does (confirmed directly - tokenizing depth 201 itself
raises `TokenError("too many nested parentheses")` on 3.14.7, independent
of `ast.parse`), so `scanner.scan_file`'s own `_tokenize` call would
already have raised before this rule could run. The gap it closes is
exactly between a judged version's own, possibly lower, limit and the
running interpreter's - which is where `hostile/deep_nesting`'s 150
sits relative to 3.14 (200) and 3.6-3.8 (<=98).

Verified directly against a real reproduction of `hostile/deep_nesting`
(`ok.py` + a 150-deep-nested `t.py`), scanned under the 3.14.7 venv:
`file_readiness` now reads `{"ok.py": [...all 10...], "t.py": [3.9
through 3.15]}` - `t.py` is correctly excluded from 3.6, 3.7 and 3.8,
closing the exact gap AutoSteer reported, with one `PY3-NESTING-DEPTH`
finding naming all three.

This does not fully close the `file_readiness` divergence between a 2.7
scan and a 3.14 scan of the same file, reported separately below (the
2.7-side scan still fails `ast.parse` outright at depth 150 - its own
limit is 98 - and so still reports the blanket, every-judged-version
PY3-PARSE fallback, over-blocking 3.9-3.15 where the 3.14-side scan now
correctly does not); that remainder is the same open defect against item
2b, not a new one, and R1 does not forbid the over-block direction.

8 new tests (`tests/test_rules.py`): within every judged limit, at the
exact measured boundary (92, not blocked) and one past it (93, blocked),
scoped to only the versions actually exceeded, every queried version
blocked when all are exceeded, mixed bracket kinds counted as one shared
depth, and no brackets at all. One new integration test
(`tests/test_scanner.py`), skipped below Python 3.9 (needs a running
interpreter whose own parser can reach depth 150 to exercise this
rule at all): the exact `hostile/deep_nesting` shape, confirming
`PY3-NESTING-DEPTH` fires scoped to `("3.8",)` out of
`("3.8", "3.9", "3.14")`.

Full suite: 153 passed, 3 skipped (2.7.18); 147 passed, 9 skipped
(3.14.7, 3.14.9). flake8 `--max-complexity 10` clean on all three.
compile_check clean (17 files, 0 failed, 0 unreadable) on 2.7.18 and
3.14.7.

**Resolved, commit `04f2aa1`: a held-back AutoSteer CI input, a non-text
PEP 263 coding declaration (R1), via a new rule,
`PY3-NON-TEXT-CODING`.** Repro: a file starting `# -*- coding: rot13
-*-` followed by `k = 1`. Real 2.7.18 compiles this cleanly - 2.7 runs no
check on the coding declaration's codec beyond "can I look it up," and
rot13-decoding "k" produces "x", so the whole file decodes to the valid
statement `x = 1`. Every real Python 3.6-3.15 rejects it outright
(confirmed directly on 3.6.15 and 3.14.7): `SyntaxError: 'rot13' is not
a text encoding; use codecs.decode() to handle arbitrary codecs`. Python
3's codec registry marks a specific set of codecs `_is_text_encoding =
False` and refuses to use them as a source-file encoding; 2.7's codec
registry has the same attribute but marks `rot13` `True` there, so the
rejection is a real Python-3-wide fact, not a build quirk - confirmed
identical across three final releases spanning the whole judged range
(3.6.15, 3.9.25, 3.15.1) via direct introspection
(`codecs.lookup(name)._is_text_encoding`), and identical canonical
names (`codecs.lookup(name).name`) on 2.7.18 and 3.14.7 for every alias:
`base64`, `bz2`, `hex`, `quopri`, `rot-13`, `uu`, `zlib`.

`check_non_text_coding_declaration` (`py2scan/rules.py`) calls the
existing `py2scan.encoding.detect_encoding` directly on the raw source
bytes and checks the resolved codec's canonical name against that set.
It runs as a new `SOURCE_RULES` list (rules reading raw source bytes,
rather than the AST or token stream) - another case, like
`VERSION_AWARE_TOKEN_RULES` above, where a genuinely new rule *category*
needs `scanner.py` wiring beyond item 5's "two files" claim for an
existing list. An unrecognized codec name entirely (`detect_encoding`
itself raising) is the already-documented item 2b divergence
(`invalid_coding`), not this rule's concern, and is excluded explicitly.
On an interpreter where `lib2to3` is gone (3.13+, where
`py2scan.encoding` falls back to the real `tokenize.detect_encoding`),
that real implementation runs this same non-text check itself and
raises `LookupError` before this rule's own check would even run
(confirmed directly on 3.14.7) - harmless in the real pipeline, since
`scan_file`'s own `ast.parse` already raises for the identical input on
any such interpreter, so this rule is never reached there outside a
direct call (which is what the two tests gated on this - skipped on
3.13+ - exercise).

Verified end to end against a real reproduction of the exact repro,
scanned under `scan_file`: `PY3-NON-TEXT-CODING` fires on 2.7.18;
`PY3-PARSE` fires on 3.14.7 (its own `ast.parse` already rejects the
coding declaration) - R1 holds on both sides, same recorded shape as
`print`/`exec`/backtick/raise-comma. 7 new tests (`tests/test_rules.py`):
the exact repro, every non-text alias, an ordinary `utf-8` declaration
and no declaration at all (both not found), and an unrecognized codec
name (not found - the other rule's job). 1 new integration test
(`tests/test_scanner.py`) confirming the cross-interpreter R1 shape.

**Resolved, commit `04f2aa1`: R8, `STDLIB_REMOVED_SINCE` missing 10
real modules.** AutoSteer CI repro: stdlib `sunau.py` line 395, `import
audioop`, got no finding on a 2.7 scan at all. Re-derived the whole
table properly this time against all 10 judged versions' own final
releases (3.6.15 through 3.15.1 - the same releases `BUILTIN_NAMES` was
already measured against), rather than the mixed, partial set a
previous pass used, and found 10 names genuinely missing:
`future_builtins`, `gdbm`, `linuxaudiodev` and `strop` (gone at the
2-vs-3 boundary, the same "3.6" bucket as `urllib2`); `parser` (removed
in 3.10, replaced by the PEG-based `ast` module); and `audioop`,
`crypt`, `nis`, `ossaudiodev`, `spwd` (removed in 3.13, PEP 594 - sitting
right alongside `aifc`/`cgi`/`cgitb`/... already correctly in that same
batch).

Those last five needed real care: testing each by directly importing it
against the slim test images makes every one of them look removed as
early as 3.9, well before their real PEP 594 removal - because each
needs a system library (NIS, crypt, an audio device) the slim images
never ship, for any version, not because Python stopped shipping the
module. Caught by cross-checking `sys.stdlib_module_names` instead
(3.10+, a list of what CPython's own distribution ships, independent of
whether the optional C extension actually built in this environment):
all five are `True` at 3.10 and 3.12 and `False` starting at 3.13,
matching PEP 594 and the already-correct batch exactly - confirming the
slim images' earlier-looking import failures were a build artifact of
that image, not a removal. All 10 names confirmed to genuinely import on
real 2.7.18 first (R8 only applies to something that actually worked
there).

Verified directly against the exact repro (`import audioop` compiled
against real `sunau.py:395`'s surrounding code) and 9 new tests
(`tests/test_rules.py`) covering all 10 names, including the version-
scoping check for the PEP 594 batch (`("3.12", "3.13")` judged -> blocked
only on `3.13`).

**Resolved, commit `04f2aa1`: R3/R10, `PY3-BUILTIN` missing a default
value's and a decorator's own enclosing scope.** AutoSteer CI repro:
stdlib `json/encoder.py` line 276, `def _make_iterencode(..., \`\`
basestring=basestring, ..., long=long, ...):` - a real, deliberate hand-
optimization ("turn globals into locals" for speed) that this rule
missed both builtin uses on. This is exactly the gap `check_builtin_use`'s
own docstring already named and chose not to fix ("a parameter default
value or a decorator is real Python's enclosing scope, not the
function's own... rare enough... not fixed here") - the real stdlib
proved it is not rare enough to leave open. Real Python evaluates a
default value (and a decorator) at `def`-time, in the scope the `def`
statement itself sits in - the parameter named `basestring` does not
exist yet when its own default value `basestring` is evaluated, so that
reference resolves to the builtin, which is gone on Python 3 (a real
`NameError` at def time, confirmed by the stdlib miss itself needing
exactly this fix).

Fixed in `_builtin_use_in_function` and `_builtin_use_in_lambda`
(`py2scan/rules.py`): a new `_default_value_exprs` helper collects every
default-value expression (`args.defaults` and non-`None` entries of
`args.kw_defaults`), and both are now walked with the *enclosing*
`scope_chain` passed in - not the new, inner one built for the
function's own body - exactly like the existing decorator-list walk
added alongside it. `check_builtin_use`'s docstring no longer calls this
an accepted gap, since it no longer is one.

5 new tests (`tests/test_rules.py`): the exact repro shape (two
builtins, same signature, each its own name as its default - both
found), a different parameter shadowing an unrelated builtin's default
(found), the ordinary case where a same-named parameter really does
shadow its own body (not found - unaffected), a decorator (found), and
the lambda-default equivalent (found - the same gap existed there too,
unprompted but adjacent, since lambda parameter defaults are the
identical enclosing-scope case and were not walked at all before this
fix).

Full suite after both of the above: 167 passed, 3 skipped (2.7.18); 159
passed, 11 skipped (3.14.7). flake8 `--max-complexity 10` clean on both.

**Corrected, commit `04f2aa1`: item 2b, `nul_byte` and `invalid_coding`
were not R1-forced divergences - the architect's reply pointed out that
R1 only allows a difference the compile guarantee actually requires, and
requires neither of these; the record's "no code change is possible"
claim had no receipt.** Checked directly against real 2.7.18 and real
3.14.7: for `invalid_coding` (an unrecognized codec name), the raw
`SyntaxError.msg` text is **byte-identical** on both interpreters -
`unknown encoding: no-such-codec` - and was only ever made to differ by
this code's own wrapper, `"does not parse under Python %s: %s" %
(platform.python_version(), message)`, which named the exact running
interpreter. That naming was added earlier this session for a real,
separate reason (the `check_ne_op` regression proved 3.14.7 and 3.14.9
can disagree about tokenizing identical source, so the exact patch
version seemed worth keeping), but R1's guarantee never required it, so
it was an unforced, avoidable divergence - removed. For `nul_byte`, the
raw message genuinely differs (2.7 raises `TypeError: compile()
expected string without null bytes`; 3.x raises `SyntaxError: source
code string cannot contain null bytes` - a real, built-in difference,
not this code's own decoration), so it now gets a fixed, interpreter-
independent message instead of passing either one through:
`does not parse: source contains an embedded NUL byte`.

Verified with the real receipt the previous record said didn't exist: a
real reproduction of both `hostile/nul_byte` and `hostile/invalid_coding`
(`ok.py` + `t.py` each), scanned under real 2.7.18 (Docker) and real
3.14.7 (Homebrew venv) and diffed byte-for-byte - **identical JSON on
both sides for both cases**, where before this fix both differed. 3 of
the previously-passing tests needed updating for the new message
wording (`tests/test_scanner.py`): the message-precision test is now a
message-stability test (asserts "Python" is absent, not present), plus
2 new tests pinning the exact byte-identical message text for each
case.

Full suite: 169 passed, 3 skipped (2.7.18); 161 passed, 11 skipped
(3.14.7). flake8 `--max-complexity 10` clean on both.

**Not resolved - a genuine, newly-found manual blocker, not yet in the
Units table: `MarkupSafe==1.1.1` does not resolve with a wheel for the
3.14 target (L3).** Flagged by AutoSteer CI pointing out the previous L3
Evidence row recorded no resolver output. Getting the real resolver
output this time (see Evidence, 2026-10-23) surfaced a genuine gap the
aggregated check had missed: `uv pip compile requirements.txt
--python-version 3.14 --python-platform linux --only-binary :all:`
reports "No solution found" because `MarkupSafe==1.1.1` has no usable
wheel for 3.14 - confirmed against PyPI's own file listing directly
(wheels only through cp39). It still installs today via a source build
that happens to degrade gracefully to a pure-Python wheel (see the
corrected Dependencies row), which is why the earlier "verified: imports"
check missed this - import success after a build already happened is
not the same evidence as a wheel-only resolve succeeding.

Not fixed here: the only real fix is bumping the pin, a dependency
version change this project's own standing rule reserves for explicit
owner approval ("Dependencies are pinned for 2.7 in requirements.txt:
never upgrade or add one"). This is the architect's call, not a worker
implementation choice - flagging it rather than guessing. The Units
table's "0 auto / 0 manual" and L4 status above predate this finding and
have not been changed here; whether this should move the blocker count
to "0 auto / 1 manual," hold the unit at L3 instead of L4, or be
accepted with a documented reason is for the architect to decide.

**Resolved, commit `64ced43`: `scanner.scan_file` runs `SOURCE_RULES`
and `TOKEN_RULES` independent of `ast.parse`'s outcome, closing most of
the item 2b defect above - AutoSteer's third review, item 2.** Repro:
stdlib `aifc.py` - 68 findings on 2.7.18, 1 (`PY3-PARSE`) on 3.14.9. Root
cause: `scan_file` tried `ast.parse` first and, on failure, returned
*only* a `PY3-PARSE` finding - skipping `TOKEN_RULES` and `SOURCE_RULES`
entirely, even though tokenizing a file is a strictly weaker requirement
than parsing it (CPython tokenizes `except X, e:`, `raise E, v`, `x <>
y`, `0777`, `10L` and an invalid `\u` escape without raising; only the
grammar stage rejects them). On `aifc.py` specifically, `ast.parse`
fails on 3.14.9 over an unrelated line (`0xA2805140L`, "invalid
hexadecimal literal") elsewhere in the file - which used to discard the
file's other, unrelated findings too (`PY3-PRINT`, `PY3-RAISE-COMMA`,
`PY3-BUILTIN`, `PY3-STDLIB`), none of which have anything to do with
why `ast.parse` failed.

Fix: `scan_file` now runs `SOURCE_RULES` unconditionally before
attempting `ast.parse`, and separately attempts to tokenize the source
regardless of whether `ast.parse` succeeded - `AST_RULES`/
`VERSION_AWARE_AST_RULES` still need a real tree and stay gated on
`ast.parse` succeeding (there is no tree to walk when it does not, on
any interpreter), but `TOKEN_RULES`/`VERSION_AWARE_TOKEN_RULES` now run
whenever tokenizing succeeds, on its own. A `PY3-PARSE` finding is
still added whenever `ast.parse` fails - not replaced, added alongside
whatever `TOKEN_RULES` also found, so a file can now carry both. Also
converted `check_raise_comma` from `ast.Raise.inst`-based (an
`AST_RULE`, needing a tree) to token-based (mirroring
`check_except_comma`, which this file already used as a precedent) -
`raise` is a real keyword on Python 3 too, so `raise E, v` still fails
`ast.parse` there, but it always tokenizes cleanly, so there was no
reason left to need a tree for it.

Evidence, the same real stdlib tree (excluding `site-packages/`, 1394
files, 3574 findings on 2.7.18) scanned on both real interpreters,
before and after, findings grouped by rule (`2.7.18 / 3.14.9`, lost
count): `PY3-EXCEPT-COMMA` 271/271 (0, already token-based before this
fix), `PY3-OCTAL` 91/91 (0), `PY3-LONG-SUFFIX` 116/116 (0),
`PY3-UNICODE-ESCAPE` 2/2 (0), `PY3-RAISE-COMMA` 741/741 (0, was 741/0 -
every one recovered), `PY3-NE-OP` 0 occurrences in this corpus but
confirmed fixed by direct reproduction (`x <> y` now reports both
`PY3-PARSE` and `PY3-NE-OP` on 3.14.9). `aifc.py` itself: 3.14.9 now
reports 3 findings (`PY3-PARSE` plus 2 `PY3-LONG-SUFFIX`, both correct -
confirmed against the source, `0xA2805140L` at line 145 and
`0x100000000L` at line 197), up from 1. Total findings recovered on
this one corpus: 1221 (`271+91+116+2+741`), on top of the separate
print/exec and `sys.maxint` fixes below. Structurally unrecoverable
(needs `AST_RULES`, confirmed by direct reproduction, not assumed):
`PY3-BUILTIN` 499/202 (297 lost), `PY3-DICT-ITER` 100/11 (89),
`PY3-DIVISION` 111/29 (82), `PY3-STDLIB` 498/148 (350), `PY3-METACLASS`
11/10 (1), and the bare (no-parens) forms of `print`/`exec`/backtick,
which already get `PY3-PARSE` on 3.x with nothing to recover (see the
correction above). Re-run: `docker cp` the real `/usr/local/lib/python2.7`
tree out of the `py2scan-test` image once, mount it read-only into both
`py2scan-test` and `py2scan-test314`, and run `scanner.scan()` directly
against it on each, excluding `site-packages/`.

Full suite: 180 passed, 9 skipped (2.7.18); 179 passed, 10 skipped
(3.14.9, 3.14.7). flake8 `--max-complexity 10` clean on all three.
compile_check: 17/0/0 on both real interpreters.

**Resolved, commit `64ced43`: `print >> file, ...` and `exec(code) in
g` are silently reinterpreted, not rejected, by Python 3's parser - a
more severe case than the one above, since `ast.parse` succeeds and
reports nothing at all, not even `PY3-PARSE` - AutoSteer's third
review, item 2 (the aifc.py repro's category), found independently
against stdlib `abc.py`.** `check_print`/`check_exec` key off
`ast.Print`/`ast.Exec` node types that do not exist on Python 3's `ast`
module at all - correct and complete there for every print/exec-
statement shape that fails to parse under Python 3, which is every
shape *except* two: `print` followed by `>>` (file-redirect - Python 2's
grammar recognizes this specially; once `print` is an ordinary name on
Python 3, `print >> file, "x"` is just a legal right-shift expression
followed by a tuple), and `exec(...)` followed by `in` (globals/locals
redirect - `exec(code) in g` is a legal containment expression: call
`exec(code)`, discard the `None` result, check membership in `g`).
Both parse to something harmless-looking instead of raising, so
`scan_file` reports the file completely blocker-free on a 3.x run.
Confirmed directly against the real stdlib: `abc.py:121-126`
(`print >> file, "..."` in `_dump_registry`) got zero findings on
3.14.9, `100%` readiness, before this fix.

Fix: two new token-based rules, `check_print_redirect` and
`check_exec_in_clause`, gated on `ast.Print`/`ast.Exec` being absent (so
they add nothing on 2.7, where `check_print`/`check_exec` already cover
this) - tokens lex the same way regardless of whether `print`/`exec` are
keywords, so this needs no tree at all. Deliberately narrow: the other
`print(...)`/`exec(...)` shapes (a bare single-argument call, or a
parenthesized tuple for `exec`'s globals/locals) run identically on
both Python 2 and 3 and need no fix - `bsddb/db.py`'s and
`bsddb/dbutils.py`'s `exec("from . import db")` and
`lib2to3/btm_matcher.py`'s `print("...")` are exactly this safe shape,
confirmed by direct reproduction (still flagged on 2.7, since
`check_exec`/`check_print` do not distinguish the safe single-argument
shape from a genuine statement - conservative, consistent with this
project's existing bias toward over-blocking rather than under - and
correctly not flagged on 3.14.9, since they are not blockers there).
This is the one deliberate, accepted asymmetry left in the real-stdlib
comparison after this fix (3 files: `bsddb/db.py`, `bsddb/dbutils.py`,
`lib2to3/btm_matcher.py` - down from 4 before this fix, `abc.py` now
resolved) - not an R1 violation, since none of these three files fail
to compile on any real Python 3.

Evidence: `abc.py` scanned on 3.14.9 before/after this fix: 0 findings
→ 1 (`PY3-PRINT` at line 121, matching 2.7's own finding exactly).
Real-stdlib file-readiness diff (excluding `site-packages/`) dropped
from 4 non-site-packages divergences to 3 (`abc.py` resolved; the three
listed above are the accepted, safe-shape asymmetry). Re-run: scan
`abc.py` from the real stdlib tree with both real interpreters and diff
`file_readiness`.

**Resolved, commit `64ced43`: R8, `STDLIB_REMOVED_NAMES` - a name
removed from a module that itself survives into Python 3 - AutoSteer's
third review, item 3.** Repro: stdlib `idlelib/CodeContext.py:15`,
`from sys import maxint as INFINITY` - `sys` is not itself in
`STDLIB_REMOVED_SINCE` (it never left), but the name `maxint` did, in
3.0; `check_stdlib_import`'s `ImportFrom` handling only ever checked the
module name, never the imported names themselves, so this got no
finding at all. Derived empirically, not from memory: every `from
<module> import <name>` the real 2.7 stdlib actually uses (941 unique
pairs, via an AST walk over the same real stdlib tree, excluding
`site-packages/`), checked with `__import__`/`hasattr` against real
3.14.9 for modules that are not themselves in `STDLIB_REMOVED_SINCE` (so
a genuinely missing name, not a casualty of its whole module being
gone) - 101 true "no attribute" misses, narrowed by hand to 37 a
migrating application is actually likely to use: dropped private
(leading-underscore) modules and names, `idlelib`'s own internal
submodule layout (renamed wholesale on Python 3, but nothing outside
`idlelib` itself imports those names), and platform-conditional names
this Linux-only test fleet cannot check either way (`sys.getwindowsversion`).
Added: `sys.maxint`; `itertools.{imap,izip,ifilter,ifilterfalse}`;
`string.{join,split,strip,rstrip,find,rfind,lower,expandtabs}`;
`types.{StringType,DictType,ListType,TupleType,ClassType,InstanceType}`;
`urllib.{quote,unquote,getproxies,proxy_bypass,splittype,splithost,
splitport,splituser,splitpasswd,splitattr,splitvalue,splittag,toBytes,
unwrap,url2pathname,addinfourl,ftpwrapper,localhost}`;
`warnings.warnpy3k` - all removed in Python 3.0, well before R6's judged
range starts, so every entry uses the "3.6" floor like the existing
pre-3.6 entries in `STDLIB_REMOVED_SINCE` do.

Known, explicitly not-fixed gap: this only covers the `from <module>
import <name>` form - `import sys; sys.maxint` (attribute access after
a plain import) is the more common real-world spelling (39 of 40 real-
stdlib `sys.maxint` hits in the corpus are this form, not `ImportFrom`)
and needs tracking which name a plain import bound and then walking for
`Attribute` access on it - the same scope `check_builtin_use` already
does for bare names, which this rule does not do. Pinned by
`tests/test_rules.py::test_stdlib_attribute_access_after_a_plain_import_is_a_known_gap`
so a future fix changes that assertion rather than silently regressing
it.

Evidence: `idlelib/CodeContext.py` scanned on both real interpreters -
`PY3-STDLIB` at line 15, `"import of sys.maxint; removed on Python 3.6"`,
identical on both sides (this check is a pure AST/dict lookup, with no
dependency on the running interpreter's own `sys.maxint`). Re-run:
`python -m py2scan scan --format json idlelib` against the real stdlib
tree on either interpreter.

**Resolved, commit `64ced43`: a new rule, `PY3-TAB-SPACE` - ambiguous
tab/space indentation, a genuine item 3/R1 violation (a file no real
Python 3 compiles, reported free of blockers on 2.7) independently
confirmed, not the architect's held-back repro for item 4 (which names
no input).** Python 3 has rejected this, as `TabError`, since 3.0;
Python 2.7's own tokenizer and compiler never check it by default (only
`-tt` makes the real CPython binary strict, and 2.7's `tokenize` module
does not implement the check at all) - so a real 2.7 codebase can and
does contain indentation that parses silently on 2.7 and is rejected
outright by every real Python 3. Confirmed directly: a line indented
with one tab, followed by a line at the real (tabsize-8) same level
indented with eight spaces, parses on 2.7.18 and raises
`TabError: inconsistent use of tabs and spaces in indentation` on
3.14.9's tokenizer alone - before the parser even runs.

Fix: `check_ambiguous_indentation`, a token-based rule, a direct port of
CPython's own dual-stack check - every logical line's leading
whitespace is measured two ways, `col` (a tab advances to the next
multiple of 8, the real rule) and `altcol` (a tab counts as one column,
like a space); a real indent, dedent or same-level match must agree
under both, or it is exactly what makes Python 3 raise `TabError`.
Applies to every judged version uniformly (3.6-3.15), since this has
been true since 3.0. Verified against 6 cases on real 2.7.18: the
ambiguous case above (flags, at the exact line `TabError` names);
consistent tabs-only and consistent spaces-only, including across a
dedent (does not flag); two sibling blocks each internally consistent
but in a different style from each other (does not flag - no
interaction between them); no indentation at all (does not flag).

Residual, accepted gap, the same shape as the architecture fix above:
this is a `TOKEN_RULE`, so it needs tokenizing to succeed - which it
does on 2.7.18 for the ambiguous case (2.7's tokenizer does not check
this at all), but does not on 3.x, where the real tokenizer raises
`TabError` directly, before this rule would ever run. The gap this
closes is therefore exactly the primary, intended runtime (2.7.18,
where this rule now correctly blocks the file for every judged
version) - a 3.x scan of the same file still gets only `PY3-PARSE`,
which is R1-sufficient (a blocker is still reported, for every judged
version) but coarser, the same already-accepted direction of residual
divergence as elsewhere in this document.

Full suite, this round combined: 180 passed, 9 skipped (2.7.18); 179
passed, 10 skipped (3.14.9 Docker, 3.14.7 Homebrew venv). flake8
`--max-complexity 10` clean on all three. compile_check: 17/0/0 on both
real interpreters. README's rule table and count (17 → 19) updated for
`PY3-NON-TEXT-CODING` (added an earlier session, never added to the
table) and this session's `PY3-TAB-SPACE`; `PY3-PARSE`'s row corrected
to drop the now-false "exclusive" claim.

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
| MarkupSafe | 1.1.1 | source + target | 2.7: yes (wheel). 3.14: **no wheel** - PyPI ships wheels for this pin only through cp39; `uv pip compile --only-binary :all:` for 3.14 fails outright ("has no usable wheels"), confirmed against PyPI's own file listing, not just this one resolver. It still *installs* on 3.14 today because pip's default (non-`--only-binary`) behavior falls back to the sdist, and that sdist's C speedup extension degrades gracefully to a pure-Python wheel when it can't build one - confirmed directly on a bare `python:3.14-slim` with no extra setup. That is not the same as resolving with a wheel; it depends on every future build environment reaching the same graceful-degradation path, which is exactly the fragility L3's wheel requirement exists to catch. Corrected this session - the original "Yes, both (verified)" row only proved the import succeeded somewhere a source build had already happened, not that a fresh, wheel-only resolve would | empirical, this session (see Evidence and Blockers) |
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
| 2026-10-22 | 0f40071 | py2scan | 2.7.18→3.14 | L3 (flagged missing by AutoSteer CI after the fact; added here, not re-dated) | aggregation, not a single command: Units table blocker count (0 auto / 0 manual, confirmed by this session's R6–R10/R11/sweep closures above), every `requirements.txt` pin re-checked against the Dependencies table's own "Yes, both (verified)" rows (actual installs/imports, not a resolver dry-run), Runtime surfaces table's existing plan, no stored data for this CLI tool | **Corrected 2026-10-23 (flagged by AutoSteer CI): wrong.** The skill's own level table requires L3's proof to be "Resolver output and MIGRATION.md" - this row recorded no resolver output at all, and the aggregation it did record rested on "verified: imports," which is weaker than resolves-with-a-wheel (see the row below, and the corrected MarkupSafe row in Dependencies) |
| 2026-10-23 | n/a (research, no code change; correction of the row above) | py2scan | 2.7.18→3.14 | (real L3 resolver output) | `uv pip compile requirements.txt --python-version 3.14 --python-platform linux --only-binary :all:` | **No solution found**: `markupsafe==1.1.1 has no usable wheels and you require markupsafe==1.1.1` ("Wheels are required... because building from source is disabled"). Isolated: `click==7.1.2`, `Jinja2==2.11.3` and `PyYAML==6.0.3` each resolve alone with a wheel for 3.14; `MarkupSafe==1.1.1` alone does not - it is the one pin blocking the whole file. Cross-checked against PyPI's own file listing for `MarkupSafe==1.1.1` directly (`GET pypi.org/pypi/MarkupSafe/1.1.1/json`): wheels exist only for cp27/cp34 through cp39, no cp310+ at all, so this isn't a resolver quirk - the real L3 precondition ("dependencies resolve with wheels for the step") does not hold for the current pin. Not fixed here: bumping the pin is a dependency-version change, which this project's own standing rule reserves for explicit owner approval ("Dependencies are pinned for 2.7 in requirements.txt: never upgrade or add one") - flagging the corrected status for the architect's call, not re-leveling the Units table unilaterally |
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
| 2026-10-23 | n/a (AutoSteer CI notice, no code change yet) | py2scan | (AutoSteer CI finding, R6 "named nowhere") | AutoSteer CI run against the real stdlib and the 11-case hostile input set | stdlib: 623/1104 files (2.7 side), 640/1104 (3.14 side) named nowhere in the JSON report; hostile: 11/11 cases' `ok.py` named nowhere |
| 2026-10-23 | 858728c | py2scan | (`file_readiness` fix) | real reproduction of `hostile/nul_byte` (`ok.py` + `t.py`), `python -m py2scan scan --format json` | `file_readiness` = `{"ok.py": [all 10 judged versions], "t.py": []}` — both files now named |
| 2026-10-23 | 858728c | py2scan | (`file_readiness` fix, full suite) | full suite on 2.7.18 (Docker `py2scan-test`), 3.14.7 (Homebrew venv), 3.14.9 (Docker `py2scan-test314`) | `146 passed, 2 skipped` on 2.7.18; `139 passed, 9 skipped` on 3.14.7 and 3.14.9 |
| 2026-10-23 | 858728c | py2scan | (`file_readiness` fix, flake8) | `flake8 --max-complexity 10 py2scan tests` on 2.7.18 (Docker, ad hoc `flake8<4`), 3.14.7 (Homebrew venv), and 3.14.9 (Docker `py2scan-test314`, ad hoc `flake8`) | 0 violations, all three |
| 2026-10-23 | n/a (research, no code change) | py2scan | (item 2b, stdlib-scale confirmation) | real `scanner.scan()` against the same real stdlib tree on 2.7.18 and 3.14.9, diffed by `(file, line, rule)` | 3144 only on 2.7 (every one of 14 already-known rules), 243 only on 3.14 (100% `PY3-PARSE`) — the same already-documented defect, not a new one, now confirmed at 1333-file scale |
| 2026-10-23 | n/a (research, no code change) | py2scan | (item 2b, `hostile/nul_byte`/`hostile/invalid_coding` reproduction) | `python -m py2scan scan --format json` on both real interpreters against each hostile case | `nul_byte`: `TypeError`-derived message (2.7) vs native `SyntaxError` text (3.14) for the same rule/severity; `invalid_coding`: identical text apart from the embedded exact interpreter version - same defect shape, not a new one |
| 2026-10-23 | n/a (research, no code change; investigated, not fixed) | py2scan | (AutoSteer CI finding, `hostile/deep_nesting` on 3.14, R1) | real `ast.parse` on real `python:2.7.18-slim`/`3.6.15-slim`/`3.7-slim`/`3.8-slim`/`3.14-slim` across a depth sweep (50, 90, 95, 96, 97, 98, 99, 100, 110, 120, 150 nested parens) | crossover depth: 2.7.18 and 3.8 both 98 OK / 99 fails; 3.6.15 and 3.7 both already fail at 95; 3.14.9 has no failure found up to 150 — does not cleanly track "parser generation"; no rule shipped, flagged for an architect ruling instead of a guessed threshold |

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
