# Booking System

[![CI](https://github.com/kruzimatov/booking-system/actions/workflows/ci.yml/badge.svg)](https://github.com/kruzimatov/booking-system/actions/workflows/ci.yml)

Appointment booking for a small service business, such as a barbershop. Clients pick a service, a specialist and a free time, then book. The business manages services, specialists, working hours, time off and bookings.

**Live demo:** https://booking-api.veraflow.uz · API documentation: https://booking-api.veraflow.uz/api/docs
Demo accounts for the live site are shared with reviewers privately (the public repository only contains local demo passwords).

The focus is correctness: **a time slot can never be booked twice**, even when many people press "Book" at the same moment. The database enforces this itself, and concurrency tests prove it.

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [Local development](#local-development)
- [Architecture](#architecture)
- [How double booking is prevented](#how-double-booking-is-prevented)
- [Business rules](#business-rules)
- [Edge cases](#edge-cases)
- [API](#api)
- [Tests](#tests)
- [Testing guide](docs/TESTING.md)
- [Security](#security)
- [Deployment](#deployment)
- [How AI was used](#how-ai-was-used)
- [Limitations and next steps](#limitations-and-next-steps)

## Features

**Clients**
- Browse services with duration and price, and the specialists who offer each one.
- See real free times for a day. Days the specialist does not work are disabled.
- Book with an optional note. Bookings start as *pending* until the business confirms them.
- See upcoming bookings and history, and cancel up to 2 hours before the start.

**Business (admin)**
- Services, specialists, weekly working hours with breaks, and time off (via the API; see `/api/docs`).
- A bookings dashboard: monthly numbers, a "needs action" queue, filters, and confirm / complete / cancel.
- An audit trail for every booking: who changed its status, when, and why.

Bonus items from the task that are included: timezone support, cancellation policy, admin dashboard, tests, Docker, API documentation.

## Quick start

Requirements: Docker with Compose, `make` and `openssl` (standard on macOS and Linux).

```bash
git clone https://github.com/kruzimatov/booking-system.git
cd booking-system
make env   # creates .env with a random JWT secret
make up    # builds and starts database, API and web app
make demo  # loads the demo shop (replaces all data)
```

- App: http://localhost:8081
- API documentation (Swagger): http://localhost:8081/api/docs

Demo accounts created by the seed script on your machine (local only: the seed script refuses these passwords on an HTTPS deployment, where `SEED_ADMIN_PASSWORD` and `SEED_CLIENT_PASSWORD` must be set):

| Role | Email | Password |
|---|---|---|
| Admin | `admin@example.com` | `demo-admin-password` |
| Client | `client@example.com` | `demo-client-password` |
| Client | `jasur@example.com` | `demo-client-password` |

Without `make`: copy `.env.example` to `.env`, set `JWT_SECRET` to a random value of at least 32 characters (`openssl rand -hex 32`), run `docker compose up -d --build --wait`, then `docker compose exec api python -m scripts.seed --reset`.

`make down` stops everything. The database volume is kept; `docker compose down -v` removes it.

## Local development

Requirements: Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22.

```bash
make env       # .env with a random secret
make dev-db    # PostgreSQL 16 on localhost:5433 (dev and test databases)
make migrate   # apply migrations
make seed      # demo data
make api       # FastAPI on http://localhost:8000 (docs at /api/docs)
make web       # Vite on http://localhost:5173, proxies /api to the backend
make test      # backend test suite
make lint      # ruff, mypy, oxlint, TypeScript
make openapi   # regenerate frontend API types after changing the backend
```

To run the local frontend against the deployed API instead of a local FastAPI
process, create `frontend/.env.local` from `frontend/.env.example` and set:

```bash
VITE_API_PROXY_TARGET=https://booking-api.veraflow.uz
```

Restart `make web` after changing this value. Vite keeps the browser on
`localhost:5173` and proxies `/api` server-side; the remote production cookie
is rewritten for this local development origin. Do not commit `.env.local`.

## Architecture

```
Browser ──► nginx (web) ──► /api/*  ──► FastAPI (api) ──► PostgreSQL 16
              │
              └──► React app (static files)
```

One origin serves both the app and the API, so the login cookie works without CORS.

| Part | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| Database | PostgreSQL 16 with `btree_gist` exclusion constraints |
| Frontend | React 19, TypeScript, Mantine, TanStack Query, types generated from the OpenAPI schema |
| Infrastructure | Docker Compose, nginx, GitHub Actions |

The backend is split by feature (`auth`, `catalog`, `providers`, `scheduling`, `bookings`, `admin`). Each feature has the same layers, and dependencies only point one way:

| Layer | Responsibility |
|---|---|
| `router.py` | HTTP only: parse the request, call the service, return a schema |
| `service.py` | Use cases: locking, business rules, transactions |
| `repository.py` | SQLAlchemy queries |
| `domain.py`, `policies.py` | Pure business rules with no database, clock or I/O, so they are unit-tested directly |

Details, the database diagram and the design decisions are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## How double booking is prevented

Two clients see 14:00 as free and press "Book" at the same moment. Three things make sure only one of them gets it:

1. **One shared rule for "free".** A pure function `check_start` decides whether a start time is bookable. The slots endpoint lists exactly the times that pass it, and booking re-checks the requested time with the same function. Listing and booking can never disagree.
2. **Row locks.** Creating a booking locks the client's row, then the specialist's row. A second request for the same specialist waits, then re-reads the schedule and sees the first booking. The lock order is always the same (user, then specialist, then booking), so requests cannot deadlock.
3. **The database refuses overlaps.** PostgreSQL `EXCLUDE` constraints forbid two active bookings for the same specialist whose time ranges overlap, and the same for one client. If any code path ever skipped the checks above, the insert would still fail and be reported as `409 SLOT_TAKEN`.

The test suite runs ten real parallel transactions for the same slot: exactly one succeeds and nine get `SLOT_TAKEN`. It passed 20 runs in a row.

## Business rules

| Rule | Value |
|---|---|
| Timezone | `Asia/Tashkent`. Times are stored in UTC and shown with the `+05:00` offset |
| Time grid | Bookings start every 15 minutes |
| Minimum notice | 60 minutes |
| Booking horizon | 60 days ahead |
| Client cancellation | Up to 2 hours before the start; admins can cancel at any time |
| Upcoming bookings per client | At most 5 |
| Cleanup buffer | Per service (for example 15 minutes after a haircut); blocks the specialist, not shown to clients |

The frontend reads these values from `GET /api/v1/meta`, so they are defined only once.

Booking statuses:

```
pending ──confirm──► confirmed ──complete (after the end)──► completed
   │                     │
   └──────cancel─────────┴──────────► cancelled
```

Cancelled and completed are final. Every response includes `allowed_actions` for the current user, so the app only shows buttons that will work.

## Edge cases

The full list, with the test that covers each case, is in [docs/EDGE_CASES.md](docs/EDGE_CASES.md). Highlights:

- Two users book the same slot at the same moment: one wins, the other gets a clear "just booked by someone else" message and fresh times.
- A time that overlaps an existing booking only partly, or falls inside its cleanup buffer, is rejected. Back-to-back bookings (10:00 to 11:00, then 11:00 to 12:00) are allowed.
- "Today" is the business's calendar day. At 23:00 in Tashkent the server's UTC clock still shows the previous date; the code uses the business date.
- The price is copied into the booking, so changing a service price never changes existing bookings.
- Changing working hours, adding time off or deactivating a specialist is refused if it would leave client bookings stranded. The response lists the affected booking IDs.
- A client cannot book two appointments at the same time with two different specialists.
- A cancel and a confirm that arrive at the same moment are applied one after the other; neither update is lost.

## API

Interactive documentation is at `/api/docs`. All errors use one format:

```json
{"error": {"code": "SLOT_TAKEN", "message": "This time was just booked by someone else.", "details": {}}}
```

`409` means a conflict with the current state (try another time); `422` means the request itself is invalid.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| Browse | `GET /services`, `GET /providers?service_id=`, `GET /providers/{id}/availability`, `GET /providers/{id}/slots?service_id=&date=` |
| Client bookings | `POST /bookings`, `GET /bookings?scope=upcoming\|history`, `GET /bookings/{id}`, `POST /bookings/{id}/cancel` |
| Admin | `/admin/services`, `/admin/providers` (and their availability, time off and services), `/admin/bookings`, `POST /admin/bookings/{id}/{confirm\|complete\|cancel}`, `GET /admin/stats` |
| System | `GET /meta`, `GET /health` |

All paths are under `/api/v1`. A short walkthrough with curl:

```bash
curl -c jar -X POST localhost:8081/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"client@example.com","password":"demo-client-password"}'
curl localhost:8081/api/v1/services
curl "localhost:8081/api/v1/providers/<provider_id>/slots?service_id=<service_id>&date=2026-10-05"
curl -b jar -X POST localhost:8081/api/v1/bookings -H 'Content-Type: application/json' \
  -d '{"provider_id":"<provider_id>","service_id":"<service_id>","starts_at":"2026-10-05T10:00:00+05:00"}'
```

## Tests

The full testing workflow, including automated checks, environment smoke
checks, and the manual browser checklist, is in
[docs/TESTING.md](docs/TESTING.md).

```bash
make dev-db && make test
```

- 141 backend tests: unit tests for the pure rules, API tests for every endpoint, and concurrency tests with real parallel transactions.
- Tests run the real migrations on a separate `booking_test` database, so the database constraints are tested too.
- Time is controlled with an injected clock, so rules like "2 hours before" and "after the end" are tested exactly.
- Coverage: 98% of backend lines. The slot engine and the status rules are at 100%.
- CI runs linting, type checks, migrations, tests, dependency audits and the frontend build on every push.

## Security

- Passwords are hashed with Argon2. Login gives the same answer, in the same time, for an unknown email and a wrong password.
- The auth token lives in an `httpOnly`, `SameSite=Lax` cookie and is never visible to JavaScript. Swagger and curl can use a Bearer header instead.
- The user is re-read from the database on every request, so deactivation and role changes apply immediately.
- The JWT algorithm is pinned; unsigned or foreign tokens are rejected. The app refuses to start without a strong secret.
- Request schemas reject unknown fields, so nobody can register as an admin or send their own price or status.
- Clients never see another client's data; a foreign booking returns 404. Specialists' contact details are admin-only.
- nginx sets a Content Security Policy and other security headers, and rate-limits login and registration (10 per minute) and the API.
- State-changing requests from another origin are rejected (`403 CROSS_ORIGIN_REQUEST`), which also covers sibling subdomains that `SameSite` cookies do not.
- An expired login is detected everywhere at once: any `401` logs the user out in the app and guarded pages send them to the login page.
- The API container runs as a non-root user; database and app ports are bound to localhost only.

## Deployment

The app runs on any Linux server with Docker. A host nginx terminates HTTPS and forwards to the `web` container:

1. Point a DNS record at the server, clone the repository, run `make env`, then edit `.env`: set `COOKIE_SECURE=true`, a strong `POSTGRES_PASSWORD`, and (for a demo) private `SEED_ADMIN_PASSWORD` and `SEED_CLIENT_PASSWORD`.
2. `make up`, then either create an admin with `docker compose exec api python -m scripts.create_admin`, or load the demo shop with `make demo`.
3. Add the host nginx site from [deploy/nginx-host.conf](deploy/nginx-host.conf) and enable HTTPS with `certbot --nginx`.
4. Schedule a daily database backup, for example: `docker compose exec -T db pg_dump -U booking booking | gzip > backup-$(date +%F).sql.gz`.

## How AI was used

This project was built with an AI coding assistant (Claude Code) in agentic mode. The working method:

1. **Plan first.** Before any code, a written plan ([docs/PLAN.md](docs/PLAN.md)) fixed the schema, the concurrency design, the API and the edge cases. A review of the plan found 34 problems before any code was written. For example, the first draft locked booking rows, which does not stop two inserts into an empty slot (there is no row to lock yet).
2. **Rules for the assistant.** [CLAUDE.md](CLAUDE.md) states the architecture and the invariants that must never break: the server computes prices and end times, times are always timezone-aware, and the lock order is fixed.
3. **One phase at a time.** Each phase ended with linting, type checks, the full test suite and a manual run against the real API or browser, and only then a commit.
4. **Verify, do not trust.** Generated code was checked against the database and in the browser. Real problems found this way are listed in [docs/AI_LOG.md](docs/AI_LOG.md). Two examples: autogenerated migrations created the same CHECK constraint twice, and an early status-change response returned a stale event list.

I can explain every file and every decision in this repository.

## Limitations and next steps

- No email or Telegram notifications yet. Status changes are already recorded as events, which is where notifications would hook in.
- Working hours cannot cross midnight, and daylight-saving gaps are not handled specially (Tashkent has no DST).
- Logging out clears the cookie, but a copied token stays valid until it expires (60 minutes). A server-side token denylist would close this.
- Specialists do not have their own accounts; the business admin manages everything.
- Admin screens for editing services, specialists and schedules are API-only for now.
