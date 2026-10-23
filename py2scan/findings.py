# -*- coding: utf-8 -*-


class Finding(object):
    """One occurrence of a rule in one file."""

    def __init__(self, file, line, rule, severity, message):
        self.file = file
        self.line = line
        self.rule = rule
        self.severity = severity
        self.message = message

    def key(self):
        return (self.file, self.line, self.rule)

    def to_dict(self):
        return {"file": self.file, "line": self.line, "rule": self.rule,
                "severity": self.severity, "message": self.message}
