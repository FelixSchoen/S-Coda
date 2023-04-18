# Guide

To freeze the requirements run:

- `pip freeze > requirements.txt`

Execute the following commands to bundle S-Coda:

- `python setup.py sdist bdist_wheel`
- `twine check dist/*`
- `twine upload dist/*`

To install the package locally, run

- `pip install path/to/S-Coda.whl`