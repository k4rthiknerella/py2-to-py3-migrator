# -*- coding: utf-8 -*-
import json
import sys

import io

import click

from py2scan.config import load_config
from py2scan.report import render_html, summarize
from py2scan.scanner import scan


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
def scan_cmd(path, output_format, config_path, jobs, html_path):
    """Scan every .py file under PATH."""
    config = load_config(config_path) if config_path else None
    files, findings, problems = scan(path, jobs=jobs, config=config)
    summary = summarize(files, findings, problems)

    if output_format == "json":
        # sort_keys: CPython 2.7 dict order is hash-bucket order, 3.7+ is
        # insertion order - without this the same input produces different
        # (though equally valid) JSON text on each interpreter.
        click.echo(json.dumps(summary, sort_keys=True))
    else:
        for f in findings:
            click.echo(u"%s:%d: %s %s" % (f.file, f.line, f.rule, f.message))
        for path_, reason in problems:
            click.echo(u"%s: could not be read: %s" % (path_, reason))
        click.echo(u"%d files, %d findings" % (len(files), len(findings)))

    if html_path:
        with io.open(html_path, "w", encoding="utf-8") as f:
            f.write(render_html(path, findings, summary))

    # R5: a scan root with an unreadable entry always exits 2, marking the
    # report incomplete, even when blockers were also found.
    if problems:
        sys.exit(2)
    if any(f.severity == "blocker" for f in findings):
        sys.exit(1)
