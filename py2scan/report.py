# -*- coding: utf-8 -*-
"""The results of a scan as text, JSON, and a self-contained HTML page."""
import itertools
import json
from collections import Counter, OrderedDict

from jinja2 import Environment
from markupsafe import Markup

from py2scan.rules import BLOCKER, RULES, WARNING


class Report(object):
    def __init__(self, root, files, findings):
        self.root = root
        self.files = files
        self.findings = findings
        blocked = set(f.file for f in findings if f.severity == BLOCKER)
        self.ready = len(files) - len(blocked)
        self.readiness = 100.0 * self.ready / len(files) if files else 100.0
        self.rules = OrderedDict(sorted(Counter(f.rule for f in findings).items()))
        self.has_blockers = bool(blocked)

    def to_text(self):
        lines = [u"%s:%d: %s [%s] %s" % (f.file, f.line, f.rule, f.severity, f.message)
                 for f in self.findings]
        lines.append(u"%d files, %d findings, readiness %.1f%%" % (
            len(self.files), len(self.findings), self.readiness))
        return u"\n".join(lines)

    def to_json(self):
        return json.dumps(OrderedDict([
            ("files", len(self.files)),
            ("readiness", self.readiness),
            ("rules", self.rules),
            ("findings", [f.to_dict() for f in self.findings]),
        ]), indent=2, separators=(",", ": "))

    def to_html(self):
        severities = dict((f.rule, f.severity) for f in self.findings)
        by_file = OrderedDict((path, list(group)) for path, group in
                              itertools.groupby(self.findings, key=lambda f: f.file))
        return _template().render(
            root=self.root,
            files=len(self.files),
            ready=self.ready,
            readiness=u"%.1f%%" % self.readiness,
            readiness_exact=repr(self.readiness),
            blockers=sum(1 for f in self.findings if f.severity == BLOCKER),
            warnings=sum(1 for f in self.findings if f.severity == WARNING),
            rules=[(RULES[r], severities[r], n) for r, n in self.rules.items()],
            by_file=by_file,
            clean=[path for path in sorted(self.files) if path not in by_file],
        )


def _text(value):
    """Escape for an HTML text node: only & < > need it, so quotes stay readable."""
    if value is None:
        return Markup(u"")
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return Markup(unicode(value).replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;"))


# C0 controls and DEL as their visible Control Pictures (U+2400 block); tab stays a tab.
_CONTROLS = dict((c, 0x2400 + c) for c in range(0x20) if c != 0x09)
_CONTROLS[0x7f] = 0x2421


def _code(value):
    return _text(value.translate(_CONTROLS) if value is not None else None)


_TEMPLATE = None


def _template():
    global _TEMPLATE
    if _TEMPLATE is None:
        env = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)
        env.filters["text"] = _text
        env.filters["code"] = _code
        _TEMPLATE = env.from_string(TEMPLATE)
    return _TEMPLATE


TEMPLATE = u"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>py2scan: Python 3 readiness</title>
<style>
:root {
  color-scheme: light dark;
  --fg: #1f2329; --muted: #626b77; --bg: #ffffff; --panel: #f4f5f7; --rule: #dfe2e7;
  --blocker: #b3261e; --warning: #8a5a00; --ok: #1d7a3a;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fg: #e4e6ea; --muted: #9aa2ae; --bg: #15181d; --panel: #1d2128; --rule: #2e343d;
    --blocker: #ff8a80; --warning: #f0c050; --ok: #6fd28f;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0 auto; max-width: 70rem; padding: 2.5rem 1.5rem 4rem;
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  color: var(--fg); background: var(--bg);
}
h1 { font-size: 1.5rem; margin: 0; }
h2 { font-size: 1.1rem; margin: 2.5rem 0 0.75rem; }
h3 { font-size: 0.95rem; margin: 0; padding: 0.6rem 0.9rem; background: var(--panel);
     border-bottom: 1px solid var(--rule); display: flex; justify-content: space-between; gap: 1rem; }
code, pre, .path { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.85rem; }
.path { color: var(--muted); margin: 0.25rem 0 1.5rem; word-break: break-all; }
.score { display: flex; align-items: baseline; gap: 1rem; flex-wrap: wrap; }
.score .value { font-size: 3rem; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
.score .detail { color: var(--muted); }
.meter { height: 0.5rem; background: var(--rule); border-radius: 0.25rem; overflow: hidden; margin: 1rem 0 0.5rem; }
.meter span { display: block; height: 100%; background: var(--ok); }
.totals { color: var(--muted); margin: 0; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 0.4rem 0.9rem; vertical-align: top; }
thead th { font-size: 0.8rem; color: var(--muted); font-weight: 600; border-bottom: 1px solid var(--rule); }
tbody tr + tr td { border-top: 1px solid var(--rule); }
.count, .line { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.line { color: var(--muted); width: 3.5rem; }
.sev { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; }
.sev.blocker { color: var(--blocker); }
.sev.warning { color: var(--warning); }
.file { border: 1px solid var(--rule); border-radius: 0.4rem; margin: 0 0 1rem; overflow: hidden; }
.file h3 .sev { font-weight: 500; text-transform: none; letter-spacing: 0; }
.findings { table-layout: fixed; }
.findings .c-line { width: 4rem; }
.findings .c-rule { width: 11.5rem; }
.findings .c-sev { width: 6.5rem; }
.finding td { border-top: 1px solid var(--rule); }
.finding:first-child td { border-top: 0; }
.src td { border-top: 0 !important; padding-top: 0; }
pre { margin: 0; padding: 0.4rem 0.6rem; background: var(--panel); border-radius: 0.25rem;
      overflow-x: auto; white-space: pre; tab-size: 8; }
.missing { color: var(--muted); font-style: italic; }
details { margin-top: 1rem; }
summary { cursor: pointer; color: var(--muted); }
details ul { columns: 2 20rem; padding-left: 1.2rem; }
</style>
</head>
<body>
<header>
<h1>Python 3 readiness</h1>
<p class="path">{{ root|text }}</p>
<div class="score" data-readiness="{{ readiness_exact }}">
<span class="value">{{ readiness }}</span>
<span class="detail">{{ ready }} of {{ files }} files have no blockers</span>
</div>
<div class="meter"><span style="width: {{ readiness }}"></span></div>
<p class="totals">{{ blockers }} blocker{{ "s" if blockers != 1 }} and
{{- " " }}{{ warnings }} warning{{ "s" if warnings != 1 }}</p>
</header>

<h2>Findings by rule</h2>
{% if rules %}
<table class="rules">
<thead><tr><th>Rule</th><th>What it finds</th><th>Severity</th><th class="count">Findings</th></tr></thead>
<tbody>
{% for rule, severity, count in rules %}
<tr><td><code>{{ rule.id }}</code></td><td>{{ rule.title|text }}</td>
{{- "" }}<td><span class="sev {{ severity }}">{{ severity }}</span></td><td class="count">{{ count }}</td></tr>
{% endfor %}
</tbody>
</table>
{% else %}
<p>No findings.</p>
{% endif %}

{% if by_file %}
<h2>Findings by file</h2>
{% for path, findings in by_file.items() %}
<section class="file">
<h3><code>{{ path|text }}</code>
{{- "" }}<span class="sev">{{ findings|length }} finding{{ "s" if findings|length != 1 }}</span></h3>
<table class="findings">
<colgroup><col class="c-line"><col class="c-rule"><col class="c-sev"><col></colgroup>
<tbody>
{% for f in findings %}
<tr class="finding"><td class="line">{{ f.line }}</td><td><code>{{ f.rule }}</code></td>
{{- "" }}<td><span class="sev {{ f.severity }}">{{ f.severity }}</span></td><td>{{ f.message|text }}</td></tr>
<tr class="src"><td></td><td colspan="3">
{{- "" }}{% if f.source is none %}<span class="missing">line {{ f.line }} is past the end of the file</span>
{{- "" }}{% else %}<pre><code>{{ f.source|code }}</code></pre>{% endif %}</td></tr>
{% endfor %}
</tbody>
</table>
</section>
{% endfor %}
{% endif %}

{% if clean %}
<details>
<summary>{{ clean|length }} file{{ "s" if clean|length != 1 }} with no findings</summary>
<ul>
{% for path in clean %}
<li><code>{{ path|text }}</code></li>
{% endfor %}
</ul>
</details>
{% endif %}
</body>
</html>
"""
