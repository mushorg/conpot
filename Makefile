.PHONY: docker
build-docker:
	docker build -t conpot:latest .

run-docker:
	docker run --rm -it -p 80:8800 -p 102:10201 -p 502:5020 -p 161:16100/udp -p 47808:47808/udp -p 623:6230/udp -p 21:2121 -p 69:6969/udp -p 44818:44818 --network=bridge --name conpot conpot:latest

format:
	uv run black .

.PHONY: install
install:
	uv sync --frozen --group dev

.PHONY: test
test:
	uv run pytest --junitxml=junit/test-results.xml

.PHONY: lint
lint:
	uv run black --check .

.PHONY: docs
docs:
	uv run sphinx-build -b html docs/source docs/build

.PHONY: clean
clean:
	rm -rf .venv .pytest_cache .cache .tox .mypy_cache .ruff_cache
	rm -rf .coverage htmlcov coverage.xml nosetests.xml junit
	rm -rf dist build eggs parts sdist develop-eggs
	rm -rf *.egg *.egg-info
	rm -rf docs/build
	rm -rf log fs_test ConpotTempFS
	rm -f .coverage.* docs/source/conpot_version.py conpot.db *.log
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type f \( -name '*.py[cod]' -o -name '*.so' -o -name '*.bak' \) -delete
