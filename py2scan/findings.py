# -*- coding: utf-8 -*-
from py2scan.encoding import safe_text


class Finding(object):
    """One occurrence of a rule in one file.

    versions is the subset of the scan's judged Python 3 versions (R6)
    this finding actually applies to - None until scanner.scan_file fills
    it in with the full judged set, for rules (all but PY3-STDLIB) whose
    applicability doesn't vary by version and so don't set it themselves.
    """

    def __init__(self, file, line, rule, severity, message, versions=None):
        self.file = file
        self.line = line
        self.rule = rule
        self.severity = severity
        self.message = message
        self.versions = versions

    def key(self):
        return (self.file, self.line, self.rule)

    def to_dict(self):
        return {"file": safe_text(self.file), "line": self.line,
                "rule": self.rule, "severity": self.severity,
                "message": self.message, "versions": list(self.versions or ())}
