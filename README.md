# py2scan

Find what stops a Python 2 codebase from running on Python 3, before you
migrate it.

py2scan runs on either Python 2.7 or Python 3.14 (install its matching
`requirements.txt` pins for whichever you have). It parses Python 2 source
with its own grammar via `parso`, not the host interpreter's `ast`, so it
can scan 2.7 code from a pure Python 3 process with no 2.7 interpreter
installed anywhere, and no network access at any point. Dependencies are
pinned per side in requirements.txt, by `python_version` marker; upgrade
each side independently of the other.

py2scan judges readiness against any Python 3 minor version from 3.6 to
3.15, not a single implicit target: a blocker's version range matters,
since a module removed in 3.13 says nothing about 3.10. Use `--py3` to
pick which minors to judge against; the default is every one above.

    python -m py2scan scan path/to/code
    python -m py2scan scan path/to/code --format json
    python -m py2scan scan path/to/code --html report.html
    python -m py2scan scan path/to/code --config py2scan.yml
    python -m py2scan scan path/to/code --jobs 8
    python -m py2scan scan path/to/code --py3 3.9,3.11
    python -m py2scan scan path/to/code --py3-interpreter 3.11=/usr/bin/python3.11

`--py3-interpreter` lets you point py2scan at a locally-installed
interpreter for one of the judged versions, as an extra live-compile check
for that version. It is optional and never fetched over the network: a
missing or wrong path is harmless (py2scan just runs without that extra
check), and a present one can only ever add a blocker finding a static
rule hadn't already caught, never remove one.

`--config` reads YAML:

    disable: [PY3-DIVISION]
    severity:
      PY3-METACLASS: blocker

The exit code is 2 if anything under the scanned path could hold Python
source but could not be read (nothing is ever dropped silently -- each
is listed with a reason), 1 if any blocker finding remains, 0 otherwise.

Status: 20 rules -- PY3-PRINT, PY3-EXEC-STMT, PY3-BACKTICK, PY3-NE-OP,
PY3-EXCEPT-COMMA, PY3-RAISE-COMMA, PY3-OCTAL, PY3-LONG-SUFFIX,
PY3-DICT-ITER, PY3-BUILTIN, PY3-STDLIB, PY3-TUPLE-PARAM,
PY3-ASYNC-RESERVED, PY3-KEYWORD-BINDING, PY3-UR-STRING,
PY3-BAD-ESCAPE, PY3-DEEP-NESTING, PY3-DIVISION (warning), PY3-METACLASS
(warning), PY3-PARSE (a live-compile backstop, not a static rule -- see
`--py3-interpreter` above).

See MIGRATION.md for py2scan's own migration from Python 2.7 to 3.14 --
a separate question from the Python 3 versions it judges scanned code
against, described here.
