# -*- coding: utf-8 -*-
import os
from collections import Counter, OrderedDict

from jinja2 import Environment

from py2scan.encoding import decode_source_lines
from py2scan.versions import version_str

# Bumped whenever the JSON shape changes, so consumers can detect a field
# like "unreadable" (added for exit-code-2 / incomplete-scan reporting) or
# "versions_judged"/"file_readiness" (added for R6 multi-version judging)
# before they rely on it.
SCHEMA_VERSION = 3


def compute_summary(files, findings, versions):
    """Returns (file_readiness, readiness_by_version, rule_counts).
    file_readiness: {relpath: [version_str, ...]} - the judged versions
    that file has zero blockers for (R6: "for each file, [report] which of
    those versions it is ready for"). readiness_by_version: {version_str:
    percent of files ready for it}. rule_counts: {rule: total finding
    count}, same across every version (a count of findings, not of
    file/version pairs)."""
    blocked_versions_by_file = {}
    for f in findings:
        if f.severity == "blocker":
            blocked_versions_by_file.setdefault(f.file, set()).update(f.versions)

    file_readiness = {}
    for rel in files:
        blocked = blocked_versions_by_file.get(rel, ())
        file_readiness[rel] = [version_str(v) for v in versions if v not in blocked]

    readiness_by_version = {}
    for v in versions:
        if not files:
            readiness_by_version[version_str(v)] = 100.0
            continue
        ready = sum(1 for rel in files if v not in blocked_versions_by_file.get(rel, ()))
        readiness_by_version[version_str(v)] = round(100.0 * ready / len(files), 1)

    rule_counts = dict(Counter(f.rule for f in findings))
    return file_readiness, readiness_by_version, rule_counts


def to_json(scan_result, findings, versions):
    file_readiness, readiness_by_version, rules = compute_summary(
        scan_result.files, findings, versions)
    return {
        "schema": SCHEMA_VERSION,
        "versions_judged": [version_str(v) for v in versions],
        "files": len(scan_result.files),
        "readiness": readiness_by_version,
        "file_readiness": file_readiness,
        "rules": rules,
        "findings": [f.to_dict() for f in findings],
        "unreadable": [{"path": path, "reason": reason}
                       for path, reason in scan_result.unreadable],
    }


_HTML_TEMPLATE = u"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>py2scan report</title>
<style>
body { font-family: sans-serif; margin: 2em; color: #222; }
table { border-collapse: collapse; width: 100%; margin-bottom: 2em; }
th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
tr.blocker { background: #fdecea; }
tr.warning { background: #fff8e1; }
code { background: #f5f5f5; padding: 2px 4px; }
</style>
</head>
<body>
<h1>py2scan report</h1>
<p>Judged against Python {{ versions_judged|join(", ") }} ({{ files }} files scanned)</p>
<table>
<tr><th>Python 3</th><th>Readiness</th></tr>
{% for version, pct in readiness_by_version %}
<tr><td>{{ version }}</td><td>{{ pct }}%</td></tr>
{% endfor %}
</table>
<table>
<tr><th>Rule</th><th>Count</th></tr>
{% for rule, count in rule_counts %}
<tr><td>{{ rule }}</td><td>{{ count }}</td></tr>
{% endfor %}
</table>
{% for file, file_findings in findings_by_file %}
<h2>{{ file }}</h2>
<table>
<tr><th>Line</th><th>Rule</th><th>Severity</th><th>Message</th><th>Versions</th><th>Source</th></tr>
{% for f in file_findings %}
<tr class="{{ f.severity }}">
<td>{{ f.line }}</td><td>{{ f.rule }}</td><td>{{ f.severity }}</td><td>{{ f.message }}</td>
<td>{{ f.versions|join(", ") }}</td>
<td><code>{{ f.source }}</code></td>
</tr>
{% endfor %}
</table>
{% endfor %}
</body>
</html>
"""


def render_html(root, files, findings, versions):
    _, readiness_by_version, rule_counts = compute_summary(files, findings, versions)
    by_file = OrderedDict()
    for f in findings:
        by_file.setdefault(f.file, []).append(f)

    findings_by_file = []
    for rel, file_findings in sorted(by_file.items()):
        with open(os.path.join(root, rel), "rb") as fh:
            lines = decode_source_lines(fh.read())
        rows = []
        for f in file_findings:
            source = lines[f.line - 1] if 0 < f.line <= len(lines) else u""
            rows.append({"line": f.line, "rule": f.rule, "severity": f.severity,
                         "message": f.message, "source": source,
                         "versions": [version_str(v) for v in f.versions]})
        findings_by_file.append((rel, rows))

    env = Environment(autoescape=True)
    template = env.from_string(_HTML_TEMPLATE)
    return template.render(
        versions_judged=[version_str(v) for v in versions], files=len(files),
        readiness_by_version=sorted(readiness_by_version.items()),
        rule_counts=sorted(rule_counts.items()),
        findings_by_file=findings_by_file)
