import io
import os
from os import path

from setuptools import find_packages, setup

NAME = "sCoda"
DESCRIPTION = "A library for handling and modifying MIDI files"
AUTHOR = "Felix Schön"
VERSION = "0.9.1"

# Load long description
LOCATION = path.abspath(path.dirname(__file__))
try:
    with io.open(os.path.join(LOCATION, 'README.md'), encoding='utf-8') as f:
        long_description = '\n' + f.read()
except FileNotFoundError:
    long_description = DESCRIPTION

setup(
    name=NAME,
    packages=find_packages(exclude=["test", "*.test", "*.test.*", "test.*"]),
    version=VERSION,
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=AUTHOR,
    license="MIT",
    install_requires=["mido ~= 1.2.10", "numpy ~= 1.22.2", "matplotlib ~= 3.5.1", "pandas ~= 1.4.1"],
    setup_requires=["pytest-runner >= 6.0.0", "twine >= 3.8.0", "pdoc3 >= 0.10.0"],
    tests_require=["pytest >= 7.0.1", "coverage >= 6.3.2"],
    test_suite="test",
)
