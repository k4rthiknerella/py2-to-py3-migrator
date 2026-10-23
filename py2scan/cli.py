# -*- coding: utf-8 -*-
import json
import sys

import click

from py2scan.config import load_config
from py2scan.report import to_json
from py2scan.scanner import scan


@click.group()
def main():
    """Find what stops a Python 2 codebase from running on Python 3."""


@main.command("scan")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False),
              help="YAML file with disable/severity overrides.")
@click.option("--jobs", type=int, default=4, help="Parallel workers (default 4).")
def scan_cmd(path, fmt, config_path, jobs):
    """Scan every .py file under PATH."""
    config = load_config(config_path)
    files, raw_findings = scan(path, jobs=jobs)
    findings = config.apply(raw_findings)

    if fmt == "json":
        click.echo(json.dumps(to_json(files, findings)))
    else:
        for f in findings:
            click.echo(u"%s:%d: %s %s" % (f.file, f.line, f.rule, f.message))
        click.echo(u"%d files, %d findings" % (len(files), len(findings)))

    sys.exit(1 if any(f.severity == "blocker" for f in findings) else 0)
