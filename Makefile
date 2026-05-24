VENV ?= .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

.PHONY: help dev run test lint format app clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

dev: ## Create a venv and install with dev + build extras
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip "setuptools>=68,<81"
	$(PIP) install -e ".[dev,build]"

run: ## Launch the menu-bar app
	$(PY) -m army_light

test: ## Run the test suite
	$(PY) -m pytest -q

lint: ## Static checks (ruff)
	$(PY) -m ruff check army_light tests packaging

format: ## Auto-format (ruff)
	$(PY) -m ruff format army_light tests packaging

app: ## Build dist/ARMY Light.app
	cd packaging && PYTHONPATH=$(CURDIR) $(CURDIR)/$(PY) setup_app.py py2app \
		--dist-dir=$(CURDIR)/dist --bdist-base=$(CURDIR)/build

clean: ## Remove build artifacts
	rm -rf build dist *.egg-info army_light.egg-info .pytest_cache
