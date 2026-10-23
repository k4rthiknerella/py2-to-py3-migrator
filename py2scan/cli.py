# -*- coding: utf-8 -*-
import click

from py2scan.config import Config, ConfigError, load_config
from py2scan.report import Report
from py2scan.scanner import ScanError, display_path, scan


class ScanFailed(click.ClickException):
    exit_code = 2  # 1 means "blockers found"


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
@click.pass_context
def scan_cmd(ctx, path, fmt, html_path, config, jobs):
    """Scan every .py file under PATH. Exits 1 if any blocker is found."""
    try:
        files, findings = scan(path, jobs=jobs)
    except ScanError as e:
        raise ScanFailed(str(e))
    report = Report(display_path(path), files, config.apply(findings))
    click.echo(report.to_json() if fmt == "json" else report.to_text())
    if html_path:
        try:
            with open(html_path, "wb") as f:
                f.write(report.to_html().encode("utf-8"))
        except EnvironmentError as e:
            raise ScanFailed(u"cannot write %s: %s" % (click.format_filename(html_path), e.strerror or e))
    ctx.exit(1 if report.has_blockers else 0)
