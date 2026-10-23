# -*- coding: utf-8 -*-
"""The Python 3 minor versions py2scan can judge readiness against (R6).

3.6 and 3.7 are included because R6 sets the floor at 3.6, even though
upstream has since stopped building installers for them; 3.15 is the
newest release as of this writing. Each is a tuple (major, minor) so they
sort and compare without string parsing.
"""

SUPPORTED_VERSIONS = (
    (3, 6), (3, 7), (3, 8), (3, 9), (3, 10),
    (3, 11), (3, 12), (3, 13), (3, 14), (3, 15),
)


def version_str(version):
    return "%d.%d" % version


ALL_VERSION_STRS = tuple(version_str(v) for v in SUPPORTED_VERSIONS)

_BY_STR = dict((version_str(v), v) for v in SUPPORTED_VERSIONS)


def parse_versions(text):
    """Parse a comma-separated '3.9,3.11' value into a sorted tuple of
    (major, minor) tuples, validated against SUPPORTED_VERSIONS. None or
    an empty string means every supported version (R6: "with no choice
    given, py2scan reports every supported version")."""
    if not text:
        return SUPPORTED_VERSIONS
    result = set()
    for part in text.split(","):
        part = part.strip()
        if part not in _BY_STR:
            raise ValueError(
                "unsupported Python 3 version %r; supported versions are %s"
                % (part, ", ".join(ALL_VERSION_STRS)))
        result.add(_BY_STR[part])
    return tuple(sorted(result))
