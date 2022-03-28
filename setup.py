from os import path

from setuptools import find_packages, setup

# Load long description
LOCATION = path.abspath(path.dirname(__file__))
with open(path.join(LOCATION, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="sCoda",
    packages=find_packages(include=["sCoda"]),
    version="0.1.0",
    description="A music library for judging difficulty of pieces",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Felix Schön",
    license="MIT",
    install_requires=["mido ~= 1.2.10", "numpy ~= 1.22.2", "matplotlib ~= 3.5.1", "pandas ~= 1.4.1"],
    setup_requires=["pytest-runner >= 6.0.0", "twine >= 3.8.0", "pdoc3 >= 0.10.0"],
    tests_require=["pytest >= 7.0.1"],
    test_suite="test",
)
