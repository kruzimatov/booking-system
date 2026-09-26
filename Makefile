.PHONY: dev-db db-shell migrate api web test lint format seed openapi create-admin

BACKEND = cd backend &&
FRONTEND = cd frontend &&

dev-db:
	docker compose up -d --wait db

db-shell:
	docker compose exec db psql -U booking -d booking

migrate:
	$(BACKEND) uv run alembic upgrade head

api:
	$(BACKEND) uv run uvicorn app.main:app --reload

web:
	$(FRONTEND) npm run dev

test:
	$(BACKEND) uv run pytest

lint:
	$(BACKEND) uv run ruff check . && uv run ruff format --check . && uv run mypy app
	$(FRONTEND) npm run lint && npx tsc -b

format:
	$(BACKEND) uv run ruff format . && uv run ruff check --fix .

seed:
	$(BACKEND) uv run python -m scripts.seed --reset

openapi:
	$(BACKEND) uv run python -m scripts.export_openapi
	$(FRONTEND) npm run gen:api

create-admin:
	$(BACKEND) uv run python -m scripts.create_admin
