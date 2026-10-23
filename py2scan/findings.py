# -*- coding: utf-8 -*-
from collections import OrderedDict


class Finding(object):
    """One occurrence of a rule in one file."""

    def __init__(self, file, line, rule, severity, message, col=0, source=None):
        self.file = file
        self.line = line
        self.rule = rule
        self.severity = severity
        self.message = message
        self.col = col  # orders findings that share a line and a rule
        self.source = source  # the decoded offending line, for the HTML report

    def key(self):
        return (self.file, self.line, self.rule, self.col)

    def with_severity(self, severity):
        return Finding(self.file, self.line, self.rule, severity, self.message, self.col, self.source)

    def to_dict(self):
        return OrderedDict([("file", self.file), ("line", self.line), ("rule", self.rule),
                            ("severity", self.severity), ("message", self.message)])
