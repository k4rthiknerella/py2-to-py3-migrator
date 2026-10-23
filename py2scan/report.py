# -*- coding: utf-8 -*-
"""Turns a scan's (files, findings) into the JSON summary and HTML report."""
from __future__ import division

import collections
import os

import jinja2

from py2scan.encoding import read_lines
from py2scan.rules import ALL_TARGET_VERSIONS

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
<p>{{ summary.files }} files scanned.</p>
<table>
<tr><th>Python 3 version</th><th>Readiness</th></tr>
{% for version, pct in readiness_rows %}
<tr><td>{{ version }}</td><td>{{ "%.1f"|format(pct) }}%</td></tr>
{% endfor %}
</table>
{% if not summary.complete %}
<p class="blocker"><strong>Incomplete scan</strong>:
   {{ summary.problems|length }} entries under the scan root could not
   be read.</p>
<table>
<tr><th>Path</th><th>Reason</th></tr>
{% for p in summary.problems %}
<tr><td>{{ p.path }}</td><td>{{ p.reason }}</td></tr>
{% endfor %}
</table>
{% endif %}
<table>
<tr><th>Rule</th><th>Findings</th></tr>
{% for rule, count in rule_counts %}
<tr><td>{{ rule }}</td><td>{{ count }}</td></tr>
{% endfor %}
</table>
{% for file, file_findings in findings_by_file %}
<h2>{{ file }}</h2>
<table>
<tr><th>Line</th><th>Rule</th><th>Message</th><th>Versions</th>
    <th>Source</th></tr>
{% for f in file_findings %}
<tr class="{{ f.severity }}">
<td>{{ f.line }}</td>
<td>{{ f.rule }}</td>
<td>{{ f.message }}</td>
<td>{{ (f.versions or [])|join(", ") }}</td>
<td><code>{{ source_line(f) }}</code></td>
</tr>
{% endfor %}
</table>
{% endfor %}
</body>
</html>
"""


def _sort_key(f):
    return (f.file, f.line, f.rule, f.message)


def summarize(files, findings, problems=None, judged_versions=None):
    """R6: readiness is per Python 3 version, not one scalar - a file can
    be ready for 3.9 while still blocked on 3.12. A finding with
    versions=None (only possible when a caller builds a Finding directly,
    bypassing scanner.scan_file's fill-in) is treated as applying to
    every version judged_versions asks about."""
    problems = problems or []
    judged_versions = judged_versions or ALL_TARGET_VERSIONS
    findings = sorted(findings, key=_sort_key)

    readiness = {}
    for version in judged_versions:
        if files:
            blocker_files = set(
                f.file for f in findings
                if f.severity == "blocker"
                and (f.versions is None or version in f.versions))
            readiness[version] = (
                100.0 * (len(files) - len(blocker_files)) / len(files))
        else:
            readiness[version] = 100.0

    rule_counts = collections.Counter(f.rule for f in findings)

    return {
        "files": len(files),
        "readiness": readiness,
        "rules": dict(rule_counts),
        "findings": [f.to_dict() for f in findings],
        "complete": not problems,
        "problems": [{"path": path, "reason": reason}
                     for path, reason in sorted(problems)],
    }


def render_html(root, findings, summary):
    lines_by_file = {}

    def source_line(finding):
        if finding.file not in lines_by_file:
            lines_by_file[finding.file] = read_lines(
                os.path.join(root, finding.file))
        return lines_by_file[finding.file][finding.line - 1]

    findings_by_file = collections.OrderedDict()
    for f in sorted(findings, key=_sort_key):
        findings_by_file.setdefault(f.file, []).append(f)

    readiness_rows = sorted(
        summary["readiness"].items(),
        key=lambda item: tuple(int(p) for p in item[0].split(".")))

    template = _ENV.from_string(_TEMPLATE)
    return template.render(
        summary=summary,
        readiness_rows=readiness_rows,
        rule_counts=sorted(summary["rules"].items()),
        findings_by_file=list(findings_by_file.items()),
        source_line=source_line,
    )
