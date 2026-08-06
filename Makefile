.PHONY: install test build deploy validate verify

install:
	uv sync

test:
	uv run pytest

validate:
	sam validate --lint

build:
	sam build --config-env sandbox

deploy:
	sam deploy --config-env sandbox

verify:
	uv run python scripts/verify_deployment.py
