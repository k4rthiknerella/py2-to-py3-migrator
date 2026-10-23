# -*- coding: utf-8 -*-
"""The Python 3 versions a scan judges Python 2 source against (ruling R6)."""

VERSIONS = tuple((3, minor) for minor in range(6, 16))


def label(version):
    return "%d.%d" % version


def parse(text):
    """The version a --python value names, or ValueError."""
    for version in VERSIONS:
        if label(version) == text:
            return version
    raise ValueError("%s is not a version py2scan judges; choose from %s" % (
        text, ", ".join(label(v) for v in VERSIONS)))


def since(version):
    """The judged versions from version on: what a removal in version blocks."""
    return frozenset(v for v in VERSIONS if v >= version)


ALL = frozenset(VERSIONS)


def ranges(versions):
    """3.6-3.15, or 3.6, 3.8-3.9: the versions as runs of consecutive judged versions."""
    runs = []
    for version in VERSIONS:
        if version not in versions:
            continue
        if runs and VERSIONS.index(runs[-1][1]) == VERSIONS.index(version) - 1:
            runs[-1][1] = version
        else:
            runs.append([version, version])
    return ", ".join(label(a) if a == b else "%s-%s" % (label(a), label(b)) for a, b in runs)
