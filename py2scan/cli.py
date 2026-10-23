# -*- coding: utf-8 -*-
import click

from py2scan.config import Config, ConfigError, load_config
from py2scan.findings import judge
from py2scan.report import Report
from py2scan.scanner import display_path, scan
from py2scan.versions import ALL, parse


class ScanFailed(click.ClickException):
    exit_code = 2  # 1 means "blockers found"


INCOMPLETE = 2  # an entry under PATH could not be read (ruling R5), even when blockers were found


def _versions(ctx, param, value):
    try:
        return frozenset(parse(text) for text in value) or ALL
    except ValueError as e:
        raise click.BadParameter(str(e))


def _config(ctx, param, value):
    if value is None:
        return Config()
    try:
        return load_config(value)
    except ConfigError as e:
        raise click.BadParameter(u"%s: %s" % (click.format_filename(value), e))


@click.group()
def main():
    """Find what stops a Python 2 codebase from running on Python 3."""


@main.command("scan")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", show_default=True,
              help="What to print on stdout.")
@click.option("--html", "html_path", type=click.Path(dir_okay=False),
              help="Also write a self-contained HTML report to this file.")
@click.option("--config", type=click.Path(exists=True, dir_okay=False), callback=_config,
              help="YAML with disable: [rule ids] and severity: {rule id: blocker or warning}.")
@click.option("--jobs", type=click.IntRange(min=1), default=4, show_default=True,
              help="Files to scan in parallel.")
@click.option("--python", "versions", multiple=True, callback=_versions, metavar="X.Y",
              help="A Python 3 version to judge against, 3.6 to 3.15; repeat for more. Default: all of them.")
@click.pass_context
def scan_cmd(ctx, path, fmt, html_path, config, jobs, versions):
    """Scan every .py file under PATH. Exits 1 if any blocker is found, and 2 if
    anything under PATH could not be read."""
    result = scan(path, jobs=jobs)
    report = Report(display_path(path), result.files, judge(config.apply(result.findings), versions), versions,
                    result.skipped, result.errors)
    for entry in result.errors:
        click.echo(u"py2scan: %s: %s" % entry, err=True)
    click.echo(report.to_json() if fmt == "json" else report.to_text())
    if html_path:
        try:
            with open(html_path, "wb") as f:
                f.write(report.to_html().encode("utf-8"))
        except EnvironmentError as e:
            raise ScanFailed(u"cannot write %s: %s" % (click.format_filename(html_path), e.strerror or e))
    ctx.exit(INCOMPLETE if not report.complete else 1 if report.has_blockers else 0)
