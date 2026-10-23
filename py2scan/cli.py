# -*- coding: utf-8 -*-
import json
import sys

import click

from py2scan.config import load_config
from py2scan.report import render_html, to_json
from py2scan.scanner import scan
from py2scan.versions import ALL_VERSION_STRS, parse_versions


def _parse_extra_interpreters(entries, versions):
    """Each entry is 'VERSION=PATH', e.g. '3.11=/usr/bin/python3.11'."""
    result = {}
    for entry in entries:
        version_str, sep, path = entry.partition("=")
        if not sep:
            raise click.BadParameter(
                "expected VERSION=PATH, got %r" % entry, param_hint="--py3-interpreter")
        parsed = parse_versions(version_str)
        if len(parsed) != 1:
            raise click.BadParameter(
                "expected exactly one version, got %r" % version_str,
                param_hint="--py3-interpreter")
        result[parsed[0]] = path
    return result


@click.group()
def main():
    """Find what stops a Python 2 codebase from running on Python 3."""


@main.command("scan")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False),
              help="YAML file with disable/severity overrides.")
@click.option("--jobs", type=int, default=4, help="Parallel workers (default 4).")
@click.option("--html", "html_path", type=click.Path(dir_okay=False),
              help="Write a self-contained HTML report to this path.")
@click.option("--py3", "py3_versions", default=None,
              help="Comma-separated Python 3 versions to judge against, e.g. 3.9,3.11. "
                   "Default: every supported version (%s)." % ", ".join(ALL_VERSION_STRS))
@click.option("--py3-interpreter", "extra_interpreters", multiple=True,
              help="VERSION=PATH to a locally-installed interpreter py2scan may use as an "
                   "extra check for that version (optional; never required, never fetched).")
def scan_cmd(path, fmt, config_path, jobs, html_path, py3_versions, extra_interpreters):
    """Scan every .py file under PATH."""
    try:
        versions = parse_versions(py3_versions)
        extra = _parse_extra_interpreters(extra_interpreters, versions)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="--py3")

    config = load_config(config_path)
    result = scan(path, jobs=jobs, versions=versions, extra_interpreters=extra)
    findings = config.apply(result.findings)

    if html_path:
        with open(html_path, "wb") as fh:
            fh.write(render_html(path, result.files, findings, versions).encode("utf-8"))

    if fmt == "json":
        click.echo(json.dumps(to_json(result, findings, versions)))
    else:
        for f in findings:
            click.echo(u"%s:%d: %s %s" % (f.file, f.line, f.rule, f.message))
        for rel, reason in result.unreadable:
            click.echo(u"%s: unreadable: %s" % (rel, reason))
        click.echo(u"%d files, %d findings" % (len(result.files), len(findings)))

    if result.incomplete:
        sys.exit(2)
    sys.exit(1 if any(f.severity == "blocker" for f in findings) else 0)
