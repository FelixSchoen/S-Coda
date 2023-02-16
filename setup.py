from pathlib import Path

from setuptools import find_packages, setup

metadata = dict(
    name="s-coda",
    version="1.0",
    author="Felix Schön",
    author_email="schoen@kr.tuwien.ac.at",
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    download_url="https://pypi.org/project/s-coda/",
    project_urls={
        "Bug Tracker": "https://github.com/FelixSchoen/S-Coda/issues",
        "Documentation": "https://doi.org/10.34726/hss.2023.103585",
        "Source Code": "https://github.com/FelixSchoen/S-Coda",
    },
    license="MIT",
    packages=find_packages(exclude=["test", "*.test", "*.test.*", "test.*"]),
    install_requires=["mido >= 1.2.10", "numpy >= 1.22.2", "matplotlib >= 3.5.1", "pandas >= 1.4.1"],
    setup_requires=["pytest-runner >= 6.0.0", "twine >= 3.8.0", "pdoc3 >= 0.10.0"],
    tests_require=["pytest >= 7.0.1", "coverage >= 6.3.2"],
    test_suite="test",
)

setup(**metadata)
