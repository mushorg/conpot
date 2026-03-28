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
	uv run pytest --junitxml=junit/test-results.xml --cov=conpot --cov-report=xml --cov-report=html

.PHONY: lint
lint:
	uv run black --check .

.PHONY: docs
docs:
	uv run sphinx-build -b html docs/source docs/build
