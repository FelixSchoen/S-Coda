Execute the following commands:

`python setup.py sdist bdist_wheel`

`twine check dist/*`

`twine upload dist/*`

To install the package locally, run

`pip install path/to/sCoda.whl`