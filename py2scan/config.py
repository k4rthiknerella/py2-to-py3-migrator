# -*- coding: utf-8 -*-
"""--config FILE: YAML that turns rules off and overrides their severities.

    disable: [PY3-DIVISION]
    severity:
      PY3-METACLASS: blocker
"""
import yaml

from py2scan.rules import BLOCKER, RULES, WARNING


class ConfigError(ValueError):
    pass


class Config(object):
    def __init__(self, disable=(), severity=None):
        self.disable = frozenset(disable)
        self.severity = dict(severity or {})

    def apply(self, findings):
        """The findings of enabled rules, at their configured severities."""
        return [f.with_severity(self.severity.get(f.rule, f.severity))
                for f in findings if f.rule not in self.disable]


def _known(rule_id):
    if rule_id not in RULES:
        raise ConfigError(u"unknown rule %s; rules are %s" % (rule_id, u", ".join(RULES)))
    return rule_id


def parse_config(data):
    if data is None:  # an empty file
        return Config()
    if not isinstance(data, dict):
        raise ConfigError(u"expected a mapping with disable and severity keys")
    for key in sorted(data):
        if key not in ("disable", "severity"):
            raise ConfigError(u"unknown key %s; expected disable or severity" % key)
    disable = data.get("disable") or []
    severity = data.get("severity") or {}
    if not isinstance(disable, list):
        raise ConfigError(u"disable must be a list of rule ids")
    if not isinstance(severity, dict):
        raise ConfigError(u"severity must map rule ids to blocker or warning")
    for rule_id, level in sorted(severity.items()):
        if level not in (BLOCKER, WARNING):
            raise ConfigError(u"severity of %s must be blocker or warning, not %s" % (rule_id, level))
    return Config([_known(r) for r in disable], dict((_known(r), l) for r, l in severity.items()))


def load_config(path):
    try:
        with open(path, "rb") as f:
            data = yaml.safe_load(f)  # never yaml.load: it can construct arbitrary objects
    except yaml.YAMLError as e:
        raise ConfigError(u"not valid YAML: %s" % e)
    return parse_config(data)
