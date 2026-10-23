# -*- coding: utf-8 -*-
import click

from py2scan.scanner import scan


@click.group()
def main():
    """Find what stops a Python 2 codebase from running on Python 3."""


@main.command("scan")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
def scan_cmd(path):
    """Scan every .py file under PATH."""
    files, findings = scan(path)
    for f in findings:
        click.echo(u"%s:%d: %s %s" % (f.file, f.line, f.rule, f.message))
    click.echo(u"%d files, %d findings" % (len(files), len(findings)))
