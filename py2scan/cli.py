# -*- coding: utf-8 -*-
import json
import sys

import io

import click

from py2scan.config import load_config
from py2scan.report import render_html, summarize
from py2scan.rules import ALL_TARGET_VERSIONS
from py2scan.scanner import scan


def _version_sort_key(version):
    return tuple(int(part) for part in version.split("."))


def _parse_target_version(ctx, param, value):
    """R6: "all" (the default) or a comma-separated subset of
    ALL_TARGET_VERSIONS, e.g. "3.9,3.12"."""
    if value == "all":
        return ALL_TARGET_VERSIONS
    requested = [v.strip() for v in value.split(",")]
    unknown = [v for v in requested if v not in ALL_TARGET_VERSIONS]
    if unknown:
        raise click.BadParameter(
            "unknown target version(s) %s; must be 'all' or a "
            "comma-separated subset of %s"
            % (", ".join(unknown), ", ".join(ALL_TARGET_VERSIONS)))
    return tuple(sorted(set(requested), key=_version_sort_key))


@click.group()
def main():
    """Find what stops a Python 2 codebase from running on Python 3."""


@main.command("scan")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--format", "output_format", type=click.Choice(["text", "json"]),
              default="text")
@click.option("--config", "config_path",
              type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--jobs", type=int, default=4)
@click.option("--html", "html_path",
              type=click.Path(dir_okay=False), default=None)
@click.option("--target-version", "judged_versions", default="all",
              callback=_parse_target_version,
              help="'all' (default) or a comma-separated subset of "
                   "Python 3 versions to judge readiness against, e.g. "
                   "3.9,3.12.")
def scan_cmd(path, output_format, config_path, jobs, html_path,
             judged_versions):
    """Scan every .py file under PATH."""
    config = load_config(config_path) if config_path else None
    files, findings, problems = scan(
        path, jobs=jobs, config=config, judged_versions=judged_versions)
    summary = summarize(files, findings, problems, judged_versions)

    if output_format == "json":
        # sort_keys: CPython 2.7 dict order is hash-bucket order, 3.7+ is
        # insertion order - without this the same input produces different
        # (though equally valid) JSON text on each interpreter.
        click.echo(json.dumps(summary, sort_keys=True))
    else:
        for f in findings:
            click.echo(u"%s:%d: %s %s [%s]" % (
                f.file, f.line, f.rule, f.message,
                ", ".join(f.versions or ())))
        for path_, reason in problems:
            click.echo(u"%s: could not be read: %s" % (path_, reason))
        click.echo(u"%d files, %d findings" % (len(files), len(findings)))
        for version in sorted(judged_versions, key=_version_sort_key):
            click.echo(u"readiness for Python %s: %.1f%%"
                       % (version, summary["readiness"][version]))

    if html_path:
        with io.open(html_path, "w", encoding="utf-8") as f:
            f.write(render_html(path, findings, summary))

    # R5: a scan root with an unreadable entry always exits 2, marking the
    # report incomplete, even when blockers were also found.
    if problems:
        sys.exit(2)
    if any(f.severity == "blocker" for f in findings):
        sys.exit(1)
