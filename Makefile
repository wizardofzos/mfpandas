build:
	python -m build

upload:
	python -m twine upload --skip-existing --repository pypi dist/*

test:
	PYTHONPATH=src python -m unittest discover -s tests -v