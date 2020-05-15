dev-setup:
	python pip install -e ".[test]"

tests:
	pytest tests --cov=gql -vv

clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" | xargs -I {} rm -rf {}
	rm -rf ./htmlcov
	rm -rf ./.mypy_cache
	rm -rf ./.pytest_cache
	rm -rf ./.tox
	rm -rf ./gql.egg-info
	rm -rf ./dist
	rm -rf ./build
	rm -f ./.coverage
