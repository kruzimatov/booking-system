.PHONY: env up demo down dev-db db-shell migrate api web test lint format seed openapi create-admin smoke

BACKEND = cd backend &&
FRONTEND = cd frontend &&

# Creates .env from the example with a fresh random JWT secret (never overwrites).
env:
	@test -f .env && echo ".env already exists" || (sed "s/^JWT_SECRET=$$/JWT_SECRET=$$(openssl rand -hex 32)/" .env.example > .env && echo "Created .env")

up:
	docker compose up -d --build --wait

# Replaces all data with the demo shop. Never run this on a server with real bookings.
demo:
	docker compose exec api python -m scripts.seed --reset

down:
	docker compose down

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

smoke:
	BASE_URL=$${BASE_URL:-http://localhost:8081} ./scripts/smoke.sh
