# -*- coding: utf-8 -*-
"""What py2scan relies on from each dependency whose pin differs between the
2.7 and 3.14 sides of requirements.txt, checked on whichever side runs it.

None of these import py2scan, so they hold the new pins to the old behaviour
before py2scan itself runs on 3.14.
"""
import io
import os
from concurrent.futures import ProcessPoolExecutor

import click
import pytest
import yaml
from click.testing import CliRunner
from jinja2 import Environment
from markupsafe import Markup


def test_yaml_safe_load_reads_a_config_from_bytes():
    text = b"disable: [PY3-PRINT]\nseverity: {PY3-DIVISION: blocker}\n"
    assert yaml.safe_load(io.BytesIO(text)) == {"disable": ["PY3-PRINT"], "severity": {"PY3-DIVISION": "blocker"}}
    assert yaml.safe_load(io.BytesIO(b"")) is None


@pytest.mark.parametrize("text", [b"disable: [", b"!!python/object/apply:os.system [echo]\n"])
def test_yaml_safe_load_rejects_invalid_yaml_and_python_tags(text):
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(io.BytesIO(text))


def test_jinja2_escapes_values_but_not_markup_and_trims_block_lines():
    env = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)
    env.filters["bold"] = lambda value: Markup(u"<b>%s</b>" % value)
    template = env.from_string(u"<p>{{ value }}|{{ 'x'|bold }}</p>\n  {% if true %}\nline\n  {% endif %}\nend")
    assert template.render(value=u"<&\"'>") == u"<p>&lt;&amp;&#34;&#39;&gt;|<b>x</b></p>\nline\nend"


def test_markup_is_text_and_escapes_what_is_added_to_it():
    assert isinstance(Markup(u"<i>"), type(u""))
    assert Markup(u"<i>") + u"<" == u"<i>&lt;"


class Failed(click.ClickException):
    exit_code = 2


@click.group()
def cli():
    pass


@cli.command("run")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.option("--jobs", type=click.IntRange(min=1), default=4)
@click.option("--fail", is_flag=True)
@click.pass_context
def run(ctx, path, fmt, jobs, fail):
    if fail:
        raise Failed(u"failed")
    click.echo(u"%s %s %d" % (os.path.basename(path), fmt, jobs))
    ctx.exit(1)


def test_click_parses_options_and_keeps_exit_codes(tmpdir):
    folder, missing = str(tmpdir.mkdir("d")), str(tmpdir.join("missing"))
    tmpdir.join("f.py").write("")
    runner = CliRunner()
    result = runner.invoke(cli, ["run", folder, "--format", "json", "--jobs", "2"])
    assert (result.exit_code, result.output) == (1, "d json 2\n")
    bad = [[folder, "--fail"], [str(tmpdir.join("f.py"))], [missing], [folder, "--jobs", "0"],
           [folder, "--format", "xml"]]
    assert [runner.invoke(cli, ["run"] + args).exit_code for args in bad] == [2] * len(bad)


def test_process_pool_map_keeps_order_with_bytes_arguments():
    with ProcessPoolExecutor(max_workers=2) as pool:
        joined = list(pool.map(os.path.join, [b"a", b"b", b"c"], [b"x", b"y", b"z"]))
    assert joined == [b"a/x", b"b/y", b"c/z"]
