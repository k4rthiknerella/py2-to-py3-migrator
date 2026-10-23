# -*- coding: utf-8 -*-
"""Turns a scan's (files, findings) into the JSON summary and HTML report."""
from __future__ import division

import collections
import os

import jinja2

from py2scan.encoding import read_lines

_ENV = jinja2.Environment(autoescape=True)

_TEMPLATE = u"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>py2scan report</title>
<style>
body { font-family: sans-serif; margin: 2em; }
table { border-collapse: collapse; margin-bottom: 1.5em; }
td, th { border: 1px solid #ccc; padding: 4px 10px; text-align: left; }
.blocker { color: #a00000; }
.warning { color: #a06000; }
code { white-space: pre; }
</style>
</head>
<body>
<h1>py2scan report</h1>
<p>Readiness: <strong>{{ "%.1f"|format(summary.readiness) }}%</strong>
   ({{ summary.files }} files scanned)</p>
<table>
<tr><th>Rule</th><th>Findings</th></tr>
{% for rule, count in rule_counts %}
<tr><td>{{ rule }}</td><td>{{ count }}</td></tr>
{% endfor %}
</table>
{% for file, file_findings in findings_by_file %}
<h2>{{ file }}</h2>
<table>
<tr><th>Line</th><th>Rule</th><th>Message</th><th>Source</th></tr>
{% for f in file_findings %}
<tr class="{{ f.severity }}">
<td>{{ f.line }}</td>
<td>{{ f.rule }}</td>
<td>{{ f.message }}</td>
<td><code>{{ source_line(f) }}</code></td>
</tr>
{% endfor %}
</table>
{% endfor %}
</body>
</html>
"""


def summarize(files, findings):
    findings = sorted(findings, key=lambda f: (f.file, f.line, f.rule, f.message))

    if files:
        blocker_files = set(f.file for f in findings if f.severity == "blocker")
        readiness = 100.0 * (len(files) - len(blocker_files)) / len(files)
    else:
        readiness = 100.0

    rule_counts = collections.Counter(f.rule for f in findings)

    return {
        "files": len(files),
        "readiness": readiness,
        "rules": dict(rule_counts),
        "findings": [f.to_dict() for f in findings],
    }


def render_html(root, findings, summary):
    lines_by_file = {}

    def source_line(finding):
        if finding.file not in lines_by_file:
            lines_by_file[finding.file] = read_lines(os.path.join(root, finding.file))
        return lines_by_file[finding.file][finding.line - 1]

    findings_by_file = collections.OrderedDict()
    for f in sorted(findings, key=lambda f: (f.file, f.line, f.rule, f.message)):
        findings_by_file.setdefault(f.file, []).append(f)

    template = _ENV.from_string(_TEMPLATE)
    return template.render(
        summary=summary,
        rule_counts=sorted(summary["rules"].items()),
        findings_by_file=list(findings_by_file.items()),
        source_line=source_line,
    )
