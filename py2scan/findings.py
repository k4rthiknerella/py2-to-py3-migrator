# -*- coding: utf-8 -*-
from collections import OrderedDict

from py2scan.versions import ALL, VERSIONS, label


class Finding(object):
    """One occurrence of a rule in one file."""

    def __init__(self, file, line, rule, severity, message, col=0, source=None, versions=ALL):
        self.file = file
        self.line = line
        self.rule = rule
        self.severity = severity
        self.message = message
        self.col = col  # orders findings that share a line and a rule
        self.source = source  # the decoded offending line, for the HTML report
        self.versions = versions  # the Python 3 versions it applies to (ruling R6)

    def key(self):
        return (self.file, self.line, self.rule, self.col)

    def replace(self, **changes):
        fields = dict(vars(self), **changes)
        return Finding(**fields)

    def with_severity(self, severity):
        return self.replace(severity=severity)

    def to_dict(self):
        return OrderedDict([("file", self.file), ("line", self.line), ("rule", self.rule),
                            ("severity", self.severity), ("message", self.message),
                            ("versions", labels(self.versions))])


def labels(versions):
    return [label(v) for v in VERSIONS if v in versions]


def judge(findings, versions):
    """The findings that apply to any of versions, each narrowed to them."""
    return [f.replace(versions=f.versions & versions) for f in findings if f.versions & versions]
