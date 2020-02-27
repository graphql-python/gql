dev-setup:
	python pip install -e ".[test]"

tests:
	pytest tests --cov=gql -vv