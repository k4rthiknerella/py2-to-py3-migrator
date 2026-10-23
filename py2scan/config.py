# -*- coding: utf-8 -*-
import yaml

from py2scan.findings import Finding

VALID_SEVERITIES = ("blocker", "warning")


class Config(object):
    def __init__(self, disabled=None, severity_overrides=None):
        self.disabled = frozenset(disabled or [])
        self.severity_overrides = dict(severity_overrides or {})

    def apply(self, findings):
        result = []
        for f in findings:
            if f.rule in self.disabled:
                continue
            severity = self.severity_overrides.get(f.rule, f.severity)
            if severity != f.severity:
                f = Finding(f.file, f.line, f.rule, severity, f.message)
            result.append(f)
        return result


def load_config(path):
    if path is None:
        return Config()
    with open(path, "rb") as fh:
        data = yaml.safe_load(fh) or {}
    disabled = data.get("disable") or []
    severities = data.get("severity") or {}
    for rule, severity in severities.items():
        if severity not in VALID_SEVERITIES:
            raise ValueError("invalid severity %r for rule %s; must be blocker or warning"
                              % (severity, rule))
    return Config(disabled, severities)
