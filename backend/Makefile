.PHONY: help db-up db-down dev test lint typecheck format migrate makemigration seed openapi

COMPOSE := docker compose -f ../docker-compose.yml

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-15s %s\n", $$1, $$2}'

db-up: ## Start dev and test Postgres containers
	$(COMPOSE) up -d --wait postgres postgres-test

db-down: ## Stop Postgres containers
	$(COMPOSE) down

dev: ## Run the API with auto-reload on :8000
	uv run fastapi dev --entrypoint app.asgi:app

test: ## Run the test suite (needs postgres-test)
	$(COMPOSE) up -d --wait postgres-test
	uv run pytest

lint: ## Lint and check formatting
	uv run ruff check .
	uv run ruff format --check .

typecheck: ## mypy --strict
	uv run mypy .

format: ## Auto-format and fix lint
	uv run ruff format .
	uv run ruff check --fix .

migrate: ## Apply all migrations
	uv run alembic upgrade head

makemigration: ## Autogenerate a migration: make makemigration name="add users"
	@test -n "$(name)" || (echo 'usage: make makemigration name="..."' && exit 1)
	uv run alembic revision --autogenerate -m "$(name)"

seed: ## Load seed data
	uv run python -m app.seeds

openapi: ## Export the OpenAPI schema to openapi.json
	uv run python -c "import json; from app.main import create_app; print(json.dumps(create_app().openapi(), indent=2))" > openapi.json
