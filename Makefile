.PHONY: dev-db db-shell migrate api test lint format create-admin

BACKEND = cd backend &&

dev-db:
	docker compose up -d --wait db

db-shell:
	docker compose exec db psql -U booking -d booking

migrate:
	$(BACKEND) uv run alembic upgrade head

api:
	$(BACKEND) uv run uvicorn app.main:app --reload

test:
	$(BACKEND) uv run pytest

lint:
	$(BACKEND) uv run ruff check . && uv run ruff format --check . && uv run mypy app

format:
	$(BACKEND) uv run ruff format . && uv run ruff check --fix .

create-admin:
	$(BACKEND) uv run python -m scripts.create_admin
