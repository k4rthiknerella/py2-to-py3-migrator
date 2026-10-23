# py2scan

Find what stops a Python 2 codebase from running on Python 3, before you
migrate it.

py2scan runs on Python 2.7. It parses Python 2 source with 2.7's own `ast` and
`parser` modules, which Python 3 cannot do (a print statement is a syntax
error there), so run it where the legacy code lives. Dependencies are pinned in
requirements.txt to the last releases that support Python 2.7; do not upgrade
them.

    python -m py2scan scan path/to/code

## Options

    python -m py2scan scan PATH [--format text|json] [--html FILE] [--config FILE] [--jobs N]

- Scans every `.py` file under PATH, skipping directories whose name starts with a dot.
- `--format json` prints `files`, `readiness` (percent of scanned files with no
  blocker), `rules` (finding count per rule that has findings) and `findings`
  (`file`, `line`, `rule`, `severity`, `message`, sorted by file, line, rule).
- `--html FILE` also writes a self-contained report: no external CSS, JS, fonts or images.
- `--config FILE` reads YAML:

      disable: [PY3-DIVISION]
      severity:
        PY3-METACLASS: blocker

- `--jobs N` scans files in N worker processes (default 4). The output is the same for any N.

Exit code: 1 if any blocker was found, 0 if not, 2 for a usage error (such as a
bad config) or a file that cannot be read.

## Rules

Every occurrence is one finding, at the line where it starts.

| Rule | Severity | Finds |
| --- | --- | --- |
| PY3-PRINT | blocker | a print statement |
| PY3-EXEC-STMT | blocker | an exec statement |
| PY3-BACKTICK | blocker | a backtick repr expression |
| PY3-NE-OP | blocker | the `<>` operator |
| PY3-EXCEPT-COMMA | blocker | `except X, e:` |
| PY3-RAISE-COMMA | blocker | `raise E, value` |
| PY3-OCTAL | blocker | an old-style octal literal such as `0777` |
| PY3-LONG-SUFFIX | blocker | an integer literal with an `L` or `l` suffix |
| PY3-DICT-ITER | blocker | a call of `.iteritems()`, `.iterkeys()`, `.itervalues()` or `.has_key()` |
| PY3-BUILTIN | blocker | a use of a builtin removed in Python 3 (`unicode`, `xrange`, `file`, ...), unless the module binds that name itself |
| PY3-STDLIB | blocker | an import of a module renamed or removed in Python 3 (`urllib2`, `cPickle`, `Queue`, ...) |
| PY3-DIVISION | warning | every `/` and `/=` in a module without `from __future__ import division` |
| PY3-METACLASS | warning | a `__metaclass__` assignment in a class body |
| PY3-PARSE | blocker | a file that does not parse under Python 2.7; it gets only this finding |

## Tests

    docker build -f Dockerfile.test -t py2scan-test .
    docker run --rm -v "$PWD":/app -w /app py2scan-test python -m pytest -q
