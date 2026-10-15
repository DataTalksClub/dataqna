.PHONY: install test requirements build deploy validate verify dakit

install:
	uv sync

test:
	uv run pytest

# SAM's Python builder only understands requirements.txt, so generate one from
# the lockfile rather than maintaining a second list by hand. Generated, not
# committed — `make build` always refreshes it.
requirements:
	uv export --frozen --no-dev --no-emit-project --no-hashes \
		--format requirements-txt -o src/requirements.txt

validate:
	sam validate --lint

build: requirements
	sam build --config-env sandbox

deploy:
	scripts/deploy.sh

verify:
	uv run python scripts/verify_deployment.py

# Vendor the dakit build (bundle, helpers, fonts, checkers and the lock) from a
# sibling checkout. Build dakit first; commit src/web/dakit/ with whatever app
# change adapts to it.
DAKIT ?= ../dakit
dakit:
	node $(DAKIT)/scripts/sync.mjs --dest src/web/dakit \
		--files dakit.css dialogs.js tabs.js collection.js shell.js split.js
