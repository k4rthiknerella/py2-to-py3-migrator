# py2scan

Find what stops a Python 2 codebase from running on Python 3, before you
migrate it.

py2scan runs on Python 2.7. It parses Python 2 source with 2.7's own `ast` and
`tokenize` modules, which Python 3 cannot do (a print statement is a syntax
error there), so run it where the legacy code lives. Dependencies are pinned in
requirements.txt to the last releases that support Python 2.7; do not upgrade
them.

    python -m py2scan scan path/to/code
    python -m py2scan scan path/to/code --format json
    python -m py2scan scan path/to/code --html report.html
    python -m py2scan scan path/to/code --config py2scan.yml
    python -m py2scan scan path/to/code --jobs 8

`--config` reads YAML:

    disable: [PY3-DIVISION]
    severity:
      PY3-METACLASS: blocker

Status: 14 rules — PY3-PRINT, PY3-EXEC-STMT, PY3-BACKTICK, PY3-NE-OP,
PY3-EXCEPT-COMMA, PY3-RAISE-COMMA, PY3-OCTAL, PY3-LONG-SUFFIX, PY3-DICT-ITER,
PY3-BUILTIN, PY3-STDLIB, PY3-DIVISION (warning), PY3-METACLASS (warning),
PY3-PARSE.
