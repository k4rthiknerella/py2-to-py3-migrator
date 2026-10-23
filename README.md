# py2scan

Find what stops a Python 2 codebase from running on Python 3, before you
migrate it.

py2scan runs on Python 2.7. It parses Python 2 source with 2.7's own `ast` and
`tokenize` modules, which Python 3 cannot do (a print statement is a syntax
error there), so run it where the legacy code lives. Dependencies are pinned in
requirements.txt to the last releases that support Python 2.7; do not upgrade
them.

    python -m py2scan scan path/to/code

Status: two rules so far, PY3-PRINT and PY3-EXEC-STMT.
