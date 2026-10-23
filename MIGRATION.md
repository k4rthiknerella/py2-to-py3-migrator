---
---
# Python migration
As of 2026-10-22 · commit bf6499e · path: python 2.7 → python 3.14

## Units
| Unit | Owner | Runtime today | Effective target | Step | Level | Blockers (auto / manual) | Size | Next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| py2scan (`**`, setup.py at the root) | repository owner (no CODEOWNERS; sole git author) | python 2.7.18 (Dockerfile.test, setup.py) | python 3.14 | 1 | L2 | 0 / 10 | M | `fix py2scan` |

## Path
1. python 2.7 → python 3.14, straddling. The unit keeps running and passing its tests on 2.7 until flip.
   The bridge is a split dependency set: the 2.7 pins stay as they are behind `python_version < "3"`,
   and the 3.14 pins sit behind `python_version >= "3"`. No library is shared across the step, so no
   library bridge release is needed.

Target: 3.14 is the newest Python that has been in bugfix support for at least 6 months
(devguide.python.org/versions, fetched 2026-10-22 20:48 PDT): 3.14 has been in bugfix since 2025-10-07;
3.15 entered bugfix on 2026-10-09, 13 days before this assessment.

Waves: one unit, one wave.

## Blockers
### py2scan
- `py2scan/scanner.py:4` · `import parser` · removed in 3.10 · manual: a Python 2.7 front end that runs on both interpreters
- `py2scan/scanner.py:47` · `ast.parse(source)` of Python 2 source · Python 3's `ast` parses only Python 3 · manual (same front end)
- `py2scan/rules.py:10` · `import symbol` · removed in 3.10 · manual (front end supplies the symbol numbers)
- `py2scan/rules.py:66`, `:72`, `:78` · `ast.Print`, `ast.Exec`, `ast.Repr` · Python 2 node classes, absent from Python 3's `ast` · manual (front end supplies 2.7's node classes)
- `py2scan/rules.py:238` · `ast.Str` · removed in 3.14 · manual (same)
- `py2scan/rules.py:46` · CST walk compares the `encoding_decl` string child with an int · TypeError on 3 (`python -3` warning, .py-migrate/out/py3k-warnings.txt:538) · manual
- `py2scan/source.py:51` · `unicode` · not a builtin on 3 · manual
- `py2scan/report.py:63` · `unicode` · not a builtin on 3 · manual
- `requirements.txt:2-4` · Jinja2 2.11.3, MarkupSafe 1.1.1, PyYAML 5.4.1, futures 3.3.0 · no 3.14 wheels for MarkupSafe, PyYAML, futures; Jinja2 2.11 imports `markupsafe.soft_unicode`, which MarkupSafe 2.1 removed · manual (target-side pins)
- `requirements-dev.txt:2` · pytest 4.6.11 · imports `imp`, removed in 3.12 · manual (target-side pin)

## Dependencies
| Package | Pinned | Needed for step | Supports it? | Source |
| --- | --- | --- | --- | --- |
| click | 7.1.2 | 7.1.2 | yes: py2.py3 wheel resolves for 3.14 | .py-migrate/out/resolve-per-pin.txt |
| Jinja2 | 2.11.3 | 3.1.x | no: needs `markupsafe.soft_unicode` | Jinja2 3.0 changelog; MarkupSafe 2.1 changelog |
| MarkupSafe | 1.1.1 | 3.0.x | no: no 3.14 wheel | .py-migrate/out/resolve-current.log |
| PyYAML | 5.4.1 | 6.0.x | no: no 3.14 wheel | .py-migrate/out/resolve-per-pin.txt |
| futures | 3.3.0 | none (stdlib `concurrent.futures`) | no: 2.7-only backport | .py-migrate/out/resolve-per-pin.txt |
| six | 1.16.0 | none | unused (`git grep -n six -- '*.py'` has no hits) | |
| pytest (dev) | 4.6.11 | 9.x | no: imports `imp` | pytest 5.0 changelog (drops 2.7) |
| mock (dev) | 3.0.5 | none | unused | |

## Runtime surfaces
| File | Pins | Unit | Changes at flip |
| --- | --- | --- | --- |
| `Dockerfile.test:1` | `FROM python:2.7.18-slim` | py2scan | default base image becomes `python:3.14-slim` |
| `setup.py:8` | `python_requires="==2.7.*"` | py2scan | `>=3.14` at cleanup; straddle range until then |

No shebangs, crontabs, CI, IaC or schedulers. py2scan runs nowhere outside this repository (owner, via the architect, ruling R4).

## Stored data
| Data | Written by | Read by | Format and protocol | Plan |
| --- | --- | --- | --- | --- |
| none | | | py2scan writes reports to stdout and an optional HTML file; it stores nothing between runs | none needed |

## Breaking changes in scope
| Step | Change | Source link | Searched with | Hits |
| --- | --- | --- | --- | --- |
| 1 | print, exec, backticks, `<>`, `unicode`, removed builtins and renamed modules | https://docs.python.org/3/whatsnew/3.0.html | `git grep -nwE 'unicode\|basestring\|xrange\|unichr\|raw_input' -- 'py2scan/*.py'` | source.py:51, report.py:63 |
| 1 | Comparing unequal types raises TypeError | https://docs.python.org/3/whatsnew/3.0.html#ordering-comparisons | `python -3 -m pytest` | rules.py:46 |
| 1 | `parser` and `symbol` modules removed | https://docs.python.org/3/whatsnew/3.10.html#removed | `git grep -nE '^(import\|from) +(parser\|symbol)( \|$)' -- '*.py'` | scanner.py:4, rules.py:10 |
| 1 | Integer string conversion limited to 4300 digits | https://docs.python.org/3/whatsnew/3.11.html#other-cpython-implementation-changes | `git grep -nE '(^\|[^A-Za-z_.])(int\|long)\(' -- 'py2scan/*.py'` | none; the new front end must not convert literals |
| 1 | `imp` and `distutils` removed | https://docs.python.org/3/whatsnew/3.12.html#removed | `git grep -nE '^import imp$' -- '*.py'`; `git grep -nw distutils` | none in the unit; pytest 4.6.11 imports `imp` |
| 1 | `lib2to3` removed | https://docs.python.org/3/whatsnew/3.13.html#removed-modules-and-apis | `git grep -nw lib2to3 -- '*.py'` | none; rules it out as the front end |
| 1 | `ast.Num`, `ast.Str`, `ast.Bytes`, `ast.NameConstant`, `ast.Ellipsis` removed | https://docs.python.org/3/whatsnew/3.14.html#removed | `git grep -nE 'ast\.(Print\|Exec\|Repr\|Str\|Num\|Bytes\|NameConstant\|Ellipsis)([^A-Za-z]\|$)' -- '*.py'` | rules.py:66, 72, 78, 238 |
| 1 | `except A, B:` without parentheses is valid syntax (PEP 758) | https://docs.python.org/3/whatsnew/3.14.html#pep-758-allow-except-and-except-expressions-without-brackets | (scanner semantics, not py2scan's own code) | PY3-EXCEPT-COMMA must not rely on 3.14 rejecting it |
| 1 | multiprocessing defaults to forkserver on Linux | https://docs.python.org/3/whatsnew/3.14.html#multiprocessing | `git grep -nE 'ProcessPoolExecutor\|multiprocessing' -- '*.py'` | scanner.py:7, 91: worker function and arguments must be importable and picklable |
| 1 | `\w`, `\d`, `\s` match non-ASCII in str patterns | https://docs.python.org/3/library/re.html#regular-expression-syntax | `git grep -nE '\\[wds]' -- 'py2scan/*.py'` | source.py:10 (a bytes pattern: ASCII on both) |

## Evidence
| Date | Commit | Unit | Step | Level | Command | Result |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-22 | bf6499e | py2scan | 1 | L1 | `git ls-files -z > .py-migrate/out/files`; the runtime-surface `git grep`s from the skill | 21 tracked files, 15 Python; surfaces Dockerfile.test:1, setup.py:8; no shebangs |
| 2026-10-22 | bf6499e | py2scan | 1 | L2 | `docker run --rm -v "$PWD":/app -w /app python:3.14-slim python .py-migrate/compile_check.py .py-migrate/out/files`, and the same with `python:2.7.18-slim` | 3.14.9: checked 15, failed 0, unreadable 0, exit 0; 2.7.18: the same |
| 2026-10-22 | bf6499e | py2scan | 1 | L2 (L3 not met) | `uv pip compile requirements-dev.txt --python-version 3.14 --python-platform linux --only-binary :all: -o .py-migrate/out/resolved-3.14` | exit 1: markupsafe==1.1.1 has no usable wheels |

## Decisions
- 2026-10-22, owner via the architect session: dependency majors the target needs may change on the migration branch without asking, each with advisory triage and a test; source-side pins stay while straddling. Expires 2027-04-22.
- 2026-10-22, owner via the architect session: MIGRATION.md and README.md may be committed in this repository; no other .md file and nothing under `.claude/`. Expires 2027-04-22.
