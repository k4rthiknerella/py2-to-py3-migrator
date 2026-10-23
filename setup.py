from setuptools import setup, find_packages

setup(
    name="py2scan",
    version="0.2.0",
    description="Find what stops a Python 2 codebase from running on Python 3",
    packages=find_packages(exclude=["tests"]),
    # Tested and supported on 2.7 and 3.14 only (the migration path's source
    # and target); the exclusions say "untested", not "known broken".
    python_requires=(
        ">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*,!=3.5.*,!=3.6.*,"
        "!=3.7.*,!=3.8.*,!=3.9.*,!=3.10.*,!=3.11.*,!=3.12.*,!=3.13.*"
    ),
    install_requires=[
        # Used on both sides: see py2scan/parsing.py for why.
        "parso==0.7.1",
        "six==1.16.0",
        # Source-side pins (2.7) stay put while straddling; target-side (3.x)
        # majors were bumped for wheel availability on 3.14. See MIGRATION.md.
        "click==7.1.2; python_version<'3'",
        "click==8.5.0; python_version>='3'",
        "Jinja2==2.11.3; python_version<'3'",
        "Jinja2==3.1.6; python_version>='3'",
        "PyYAML==5.4.1; python_version<'3'",
        "PyYAML==6.0.3; python_version>='3'",
        "futures==3.3.0; python_version<'3'",
    ],
    entry_points={"console_scripts": ["py2scan=py2scan.cli:main"]},
)
