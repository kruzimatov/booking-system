# Task requirements checklist

Every line of the task, with where it is implemented. ✅ done · ❌ not done (only email notifications).

## Minimum requirements

| Requirement | Status | Where |
|---|---|---|
| Service creation: name, description, duration, price | ✅ | `POST /api/v1/admin/services`; `backend/app/modules/catalog/`. Also a cleanup buffer per service |
| Provider / employee creation | ✅ | `POST /api/v1/admin/providers`, `PUT /admin/providers/{id}/services`; `modules/providers/` |
| Availability | ✅ | Weekly hours with breaks (`PUT /admin/providers/{id}/availability`) and time off (`/time-off`); `modules/scheduling/` |
| User sees available times | ✅ | `GET /api/v1/providers/{id}/slots?service_id=&date=`; the booking wizard in the web app |
| User can book | ✅ | `POST /api/v1/bookings`; web app confirm step |
| Statuses Pending, Confirmed, Cancelled, Completed | ✅ | `bookings/models.py`, rules in `bookings/policies.py`, admin actions and client cancel |
| No double booking | ✅ | PostgreSQL `EXCLUDE` constraints, row locks, one shared slot rule; proven by concurrency tests |
| Backend API | ✅ | FastAPI under `/api/v1`, one error format, Swagger at `/api/docs` |
| Authentication | ✅ | Register, login, logout; httpOnly cookie or Bearer token; admin and client roles |
| Basic validation | ✅ | Pydantic schemas (unknown fields rejected), database CHECK constraints, business-rule errors with codes |
| Booking history | ✅ | Client: upcoming and history with pagination. Admin: filtered list and an audit trail per booking |

## What the candidate is expected to do

| Expectation | Status | Where |
|---|---|---|
| Find edge cases (for example two users booking one slot at once) | ✅ | [EDGE_CASES.md](EDGE_CASES.md): 57 cases, each tied to a test or a manual check |
| AI tools allowed | ✅ | Built with Claude Code |
| Explain where AI was used | ✅ | README "How AI was used", [AI_LOG.md](AI_LOG.md) |
| Understand the generated code | ✅ | Verified phase by phase; interview questions in [PLAN.md](PLAN.md) §15 |
| Explain architecture decisions | ✅ | [ARCHITECTURE.md](ARCHITECTURE.md) "Decisions" |

## Bonus

| Bonus | Status | Where |
|---|---|---|
| Timezone support | ✅ | Business timezone (`Asia/Tashkent`), UTC storage, business-day logic, `+05:00` in responses |
| Email notification | ❌ | Not built. Design: outbox table and worker, see [ROADMAP.md](ROADMAP.md) phase 4 |
| Calendar integration | ✅ | "Add to calendar" on each upcoming booking downloads an iCalendar (`.ics`) file for Google Calendar, Apple Calendar or Outlook: `GET /api/v1/bookings/{id}/calendar.ics`, built by the pure `bookings/calendar.py` (RFC 5545 escaping and line folding, stable UID) |
| Cancellation policy | ✅ | Clients cannot cancel less than 2 hours before; admins can; `allowed_actions` in responses |
| Admin dashboard | ✅ | `/admin`: monthly stats, needs-action queue, filters, confirm / complete / cancel, history |
| Tests | ✅ | 146 backend tests (unit, API, concurrency) and browser end-to-end tests (Playwright) |
| Docker | ✅ | `compose.yaml`: database, API, web; `make up` |
| API documentation | ✅ | Swagger at `/api/docs`, generated from the code |

## Deliverables

| Deliverable | Status | Where |
|---|---|---|
| Working application | ✅ | Live and local (`make up && make demo`) |
| Source code | ✅ | This repository |
| README and setup instructions | ✅ | [README.md](../README.md) |
| Architecture explanation | ✅ | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Edge cases explanation | ✅ | [EDGE_CASES.md](EDGE_CASES.md) |
| Public GitHub repository | ✅ | https://github.com/kruzimatov/booking-system |
| Deployed / demo URL | ✅ | https://booking-api.veraflow.uz |

## Main evaluation points

| Point | How it is addressed |
|---|---|
| Database design | Constraint naming convention, CHECK constraints, exclusion constraints, restrictive foreign keys, price snapshot, audit events ([ARCHITECTURE.md](ARCHITECTURE.md) "Database") |
| Business logic and validation | Pure, fully tested rule modules (`scheduling/domain.py`, `bookings/policies.py`) |
| Race conditions and edge cases | Lock order, isolation level and constraints explained; 8 concurrency tests; [EDGE_CASES.md](EDGE_CASES.md) |
| API architecture | Router, service, repository and domain layers with one-way imports; action endpoints for status changes |
| Product thinking | Server-side `allowed_actions`, business-day dates, "slot just taken" recovery, schedule changes that never strand a client, [ROADMAP.md](ROADMAP.md) |
| Git history | One commit per phase or feature, conventional messages |
| Documentation quality | README, architecture, edge cases, testing guide, roadmap, this checklist |
| AI usage and verification | [AI_LOG.md](AI_LOG.md): what was generated, how problems were caught, what changed |
