# py2scan

Find what stops a Python 2 codebase from running on Python 3, before you
migrate it.

py2scan runs on Python 2.7. It parses Python 2 source with 2.7's own `ast` and
`tokenize` modules, which Python 3 cannot do (a print statement is a syntax
error there), so run it where the legacy code lives. Dependencies are pinned in
requirements.txt to the last releases that support Python 2.7; do not upgrade
them.

    python -m py2scan scan path/to/code

Options:

- `--format text|json` - `json` prints `{"files", "readiness", "rules", "findings"}`.
  `findings` is sorted by file, then line, then rule. Exit code is 1 if any
  blocker was found, else 0.
- `--html FILE` - writes a self-contained HTML report (readiness score, a table
  of rule counts, and each file's findings with the offending source line).
- `--config FILE` - a YAML file with `disable: [rule ids]` and
  `severity: {rule id: blocker|warning}`; readiness and the exit code follow it.
- `--jobs N` - scan files in parallel (default 4); output is identical for any N.

Status: 14 rules.

| Rule | Severity |
|---|---|
| PY3-PRINT | blocker |
| PY3-EXEC-STMT | blocker |
| PY3-BACKTICK | blocker |
| PY3-NE-OP | blocker |
| PY3-EXCEPT-COMMA | blocker |
| PY3-RAISE-COMMA | blocker |
| PY3-OCTAL | blocker |
| PY3-LONG-SUFFIX | blocker |
| PY3-DICT-ITER | blocker |
| PY3-BUILTIN | blocker |
| PY3-STDLIB | blocker |
| PY3-DIVISION | warning |
| PY3-METACLASS | warning |
| PY3-PARSE | blocker (exclusive: a file that fails to parse gets only this finding) |
