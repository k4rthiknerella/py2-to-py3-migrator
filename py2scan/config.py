# -*- coding: utf-8 -*-
"""Loads a YAML config that disables rules or overrides their severity."""
import yaml

from py2scan.findings import Finding


class Config(object):
    def __init__(self, disabled, severity):
        self.disabled = frozenset(disabled)
        self.severity = dict(severity)


def load_config(path):
    with open(path, "rb") as f:
        data = yaml.safe_load(f) or {}
    return Config(data.get("disable") or [], data.get("severity") or {})


def apply(findings, config):
    if config is None:
        return findings
    result = []
    for finding in findings:
        if finding.rule in config.disabled:
            continue
        severity = config.severity.get(finding.rule, finding.severity)
        if severity != finding.severity:
            finding = Finding(finding.file, finding.line, finding.rule,
                              severity, finding.message)
        result.append(finding)
    return result
