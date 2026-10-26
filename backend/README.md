# Forever Service Board — backend

FastAPI + SQLModel + PostgreSQL. Product spec: [`../docs/spec.md`](../docs/spec.md).

## Requirements

- [uv](https://docs.astral.sh/uv/) (installs Python 3.13 for you; the project supports 3.12+)
- Docker with Compose (for PostgreSQL)
- `make`

## First run

```sh
cd backend
uv sync                      # create .venv and install dependencies
cp .env.example .env         # then set SESSION_SECRET and TOKEN_ENCRYPTION_KEY
make db-up                   # start postgres (:5433) and postgres-test (:5434)
make dev                     # API on http://localhost:8000
```

- Health check: <http://localhost:8000/api/health>
- API docs: <http://localhost:8000/docs> (schema at `/openapi.json`)

`BLIZZARD_MODE=mock` (the default) runs without any Battle.net credentials.

## Everyday commands

| Command | What it does |
|---------|--------------|
| `make dev` | Run the API with auto-reload |
| `make test` | Start the test database if needed and run pytest |
| `make lint` | `ruff check` + format check |
| `make typecheck` | `mypy --strict` |
| `make format` | Auto-format and auto-fix lint |
| `make migrate` | Apply migrations (`alembic upgrade head`) |
| `make makemigration name="add users"` | Autogenerate a migration — always review it by hand |
| `make seed` | Load mock data from `seeds/` |
| `make openapi` | Write `openapi.json` for the frontend type generator |
| `make db-up` / `make db-down` | Start / stop the Postgres containers |

## Tests

Tests run against a real Postgres (`postgres-test` in `../docker-compose.yml`, data in RAM).
They never read your `.env`: settings are built in `tests/conftest.py`. Point them at another
database with `TEST_DATABASE_URL`.

## Pre-commit

```sh
uv run pre-commit install --install-hooks -t pre-commit -t pre-push
```

ruff and mypy run on every commit; pytest runs on push (it needs the test database).

## Layout

```
app/
  main.py          create_app(): routers, lifespan
  asgi.py          module-level `app` for servers
  api.py           mounts every feature router under /api
  core/            config, db, shared schemas and dependencies
  features/<name>/ router → service → schemas/models, one folder per feature
  integrations/    external APIs (Blizzard)
  worker/          scheduled jobs
seeds/             mock data
tests/             mirrors app/features
```
