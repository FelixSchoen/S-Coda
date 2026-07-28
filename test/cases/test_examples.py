"""Keep every executable documentation example synchronised with the API."""

import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize("example", sorted(Path("examples").glob("*.py")))
def test_documentation_example(example: Path):
    namespace = runpy.run_path(example)
    namespace["main"]()
