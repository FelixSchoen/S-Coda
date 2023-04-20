# Guide

In order to build S-Coda using its `pyproject.toml` file run the following command:

`python -m build`

This will create a `scoda.whl` file, which can be used to install S-Coda locally or upload it to PyPI.
S-Coda can be installed locally by running the following command:

`pip install path/to/S-Coda.whl`

In order to upload S-Coda to PyPI run the following commands:

```
twine check dist/*
twine upload dist/*
```