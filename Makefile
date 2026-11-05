# Speakle developer tasks. Run `make help`.
# Local development only: nothing here deploys, and no target deletes data.

PYTHON ?= python3.11
VENV   ?= .venv
PY     := $(VENV)/bin/python
HOST   ?= 127.0.0.1
PORT   ?= 8000

export DEBUG ?= True

.DEFAULT_GOAL := help
.PHONY: help venv install migrate languages superuser run runserver test check migrations-check ci css clean compose-up compose-down compose-logs

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

$(PY):
	$(PYTHON) -m venv $(VENV)

venv: $(PY) ## Create the virtualenv (.venv)

install: venv ## Install Python requirements into the virtualenv
	$(PY) -m pip install -r requirements.txt

migrate: ## Apply database migrations (SQLite unless configured otherwise)
	$(PY) manage.py migrate

languages: ## Load the language list (not created by migrations)
	$(PY) manage.py populate_languages

superuser: ## Create an admin user (interactive)
	$(PY) manage.py createsuperuser

run: ## Run with Daphne (needed for calls, chat and notifications)
	$(VENV)/bin/daphne -b $(HOST) -p $(PORT) config.asgi:application

runserver: ## Run Django's dev server (no WebSockets)
	$(PY) manage.py runserver $(HOST):$(PORT)

test: ## Run the test suite (takes a few minutes)
	$(PY) manage.py test

check: ## Django system checks
	$(PY) manage.py check

migrations-check: ## Fail if a model change has no migration
	$(PY) manage.py makemigrations --check --dry-run

ci: check migrations-check test ## Same steps as the GitHub CI workflow

css: ## Rebuild static/css/tailwind.css (needs Node; creates local node_modules, do not commit)
	npm i --no-save tailwindcss@3
	npx tailwindcss -c tailwind.config.js -i static/css/tailwind.src.css -o static/css/tailwind.css --minify

clean: ## Remove Python bytecode caches only
	find . -name __pycache__ -type d -not -path './$(VENV)/*' -prune -exec rm -rf {} +

compose-up: ## Start the Docker stack (needs .env, see env.example)
	docker compose up -d

compose-down: ## Stop the Docker stack (keeps volumes and data)
	docker compose down

compose-logs: ## Follow Docker logs
	docker compose logs -f
