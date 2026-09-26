# Booking System: rules for Claude

Appointment booking API (FastAPI) + SPA (React). The plan in `docs/PLAN.md` is the source of truth.
Work one phase at a time (`docs/PLAN.md` §12). Do not build anything from a later phase.

## Workflow

- Before editing, say in one line which files you will touch and why.
- Implement only the current phase. If the plan is wrong or unclear, stop and say so; don't improvise.
- After changes, run `make lint test` (plus the frontend checks in Phase 6+). Report the real output. Never claim something passes without running it.
- Do not commit, push, run `docker compose down`, or touch the server unless asked.
- Never invent numbers (coverage, timings, counts). Report only what was measured.

## Architecture (required by the task; this is not over-engineering)

```
backend/app/
  core/               config, db, base, security, clock, timezone, errors
  api/                deps (Annotated dependencies), router (mounts /api/v1)
  modules/<feature>/  router.py  schemas.py  service.py  repository.py  models.py
                      scheduling/domain.py and bookings/policies.py are pure
```

| Layer | Does | Never |
|---|---|---|
| router | HTTP parsing, auth dependencies, response_model | queries, rules, commit |
| schemas | Pydantic in/out, `extra="forbid"` on every request model | DB access |
| service | use case: locks, rules, `db.commit()`, IntegrityError translation | HTTP types |
| repository | SQLAlchemy queries, `with_for_update`, eager loading | rules, commit |
| domain / policies | pure functions, `now` passed in | DB, I/O, clock, settings |

Import rules:
- Routers import their own service and schemas.
- A service may import any repository and any domain module, but never another service.
- A repository imports models only.

Frontend: `src/app`, `src/shared` (api, lib, ui, hooks), `src/features/<feature>`. Features import from `shared`, never from each other.

Size: files 200–400 lines typical, 800 max. One responsibility per file.

## Invariants that must never break

1. The server computes `ends_at`, `blocked_until`, `price`, `status`, `allowed_actions`. Never read them from client input.
2. Datetimes are timezone-aware everywhere. Store UTC. Business-local logic goes only through `core/timezone.py`.
3. Never call `datetime.now()`, `datetime.utcnow()` or `date.today()`. Use the injected `Clock`.
4. App overlap checks use the same ranges as the DB constraints:
   - provider: `[starts_at, blocked_until)`
   - client: `[starts_at, ends_at)`
5. Lock order inside one transaction: users → providers → bookings. Never the reverse.
6. Don't use `with session.begin()`. Write services end with `self.db.commit()`.
7. Errors: raise `AppError` subclasses with codes from `core/errors.py`. Every error response is `{"error": {"code", "message", "details"}}`.
8. 409 = conflict with current state. 422 = invalid request.
9. Public schemas never expose client data or provider contact fields.
10. Policy numbers come from `Settings`. No literals like `120`, `60`, `15` in logic.
11. Schema changes go through Alembic only. Raw SQL (extensions, exclusion constraints) via `op.execute` with a matching downgrade. Never `Base.metadata.create_all`.
12. Tests run migrations on `booking_test` and TRUNCATE between tests. Concurrency tests use real threads, separate sessions, and a `threading.Barrier`.
13. No secrets in code, logs or commits. Never log passwords, tokens, or request bodies.

## Commands

```
make dev-db    start postgres (localhost:5433)
make migrate   alembic upgrade head
make api       uvicorn with reload (localhost:8000, docs at /api/docs)
make web       vite dev server (proxies /api to :8000)
make test      pytest
make lint      ruff check + ruff format --check + mypy
make seed      demo data (--reset)
make openapi   export openapi.json and regenerate frontend types
```

## Style

- Python 3.12. Type hints everywhere. SQLAlchemy 2.0 typed `Mapped[]`. Pydantic v2.
- Full-word names; no abbreviations like `cfg`, `svc`, `usr`.
- No comments that repeat the code. Comment only on why (e.g. why a lock exists). No emojis. No TODO scaffolding, no dead code.
- Frontend: TypeScript strict. Server state only in TanStack Query. Dates only through `shared/lib/datetime.ts`. Never `toISOString()` for calendar dates.
- UI: Mantine defaults, one accent color, no gradients, no pill buttons, no fake data. Every input has a label.
- README and `docs/*` are written in full, plain English prose.
