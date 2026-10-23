from setuptools import setup, find_packages

setup(
    name="py2scan",
    version="0.1.0",
    description="Find what stops a Python 2 codebase from running on Python 3",
    packages=find_packages(exclude=["tests"]),
    python_requires="==2.7.*",
    install_requires=["click==7.1.2", "Jinja2==2.11.3", "PyYAML==5.4.1", "futures==3.3.0", "six==1.16.0"],
    entry_points={"console_scripts": ["py2scan=py2scan.cli:main"]},
)
