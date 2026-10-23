# -*- coding: utf-8 -*-
import os
from collections import Counter, OrderedDict

from jinja2 import Environment

from py2scan.encoding import decode_source_lines


def compute_summary(files, findings):
    if not files:
        return 100.0, {}
    blocker_files = set(f.file for f in findings if f.severity == "blocker")
    clean = len(files) - len(blocker_files)
    readiness = round(100.0 * clean / len(files), 1)
    counts = dict(Counter(f.rule for f in findings))
    return readiness, counts


def to_json(files, findings):
    readiness, rules = compute_summary(files, findings)
    return {
        "files": len(files),
        "readiness": readiness,
        "rules": rules,
        "findings": [f.to_dict() for f in findings],
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
<p>Readiness: {{ readiness }}% ({{ files }} files scanned)</p>
<table>
<tr><th>Rule</th><th>Count</th></tr>
{% for rule, count in rule_counts %}
<tr><td>{{ rule }}</td><td>{{ count }}</td></tr>
{% endfor %}
</table>
{% for file, file_findings in findings_by_file %}
<h2>{{ file }}</h2>
<table>
<tr><th>Line</th><th>Rule</th><th>Severity</th><th>Message</th><th>Source</th></tr>
{% for f in file_findings %}
<tr class="{{ f.severity }}">
<td>{{ f.line }}</td><td>{{ f.rule }}</td><td>{{ f.severity }}</td><td>{{ f.message }}</td>
<td><code>{{ f.source }}</code></td>
</tr>
{% endfor %}
</table>
{% endfor %}
</body>
</html>
"""


def render_html(root, files, findings):
    readiness, rule_counts = compute_summary(files, findings)
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
                        "message": f.message, "source": source})
        findings_by_file.append((rel, rows))

    env = Environment(autoescape=True)
    template = env.from_string(_HTML_TEMPLATE)
    return template.render(readiness=readiness, files=len(files),
                           rule_counts=sorted(rule_counts.items()),
                           findings_by_file=findings_by_file)
