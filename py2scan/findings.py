# -*- coding: utf-8 -*-
from py2scan.encoding import display_path


class Finding(object):
    """One occurrence of a rule in one file. versions is the subset of the
    judged versions (py2scan.versions) this finding applies to - never
    empty, never a sentinel for "all": a universal rule just copies in the
    full judged set a caller passes it (R6: "for each blocker, [the report]
    says which versions the blocker applies to")."""

    def __init__(self, file, line, rule, severity, message, versions):
        self.file = file
        self.line = line
        self.rule = rule
        self.severity = severity
        self.message = message
        self.versions = versions

    def key(self):
        return (self.file, self.line, self.rule)

    def to_dict(self):
        return {"file": display_path(self.file), "line": self.line, "rule": self.rule,
                "severity": self.severity, "message": self.message,
                "versions": ["%d.%d" % v for v in self.versions]}
