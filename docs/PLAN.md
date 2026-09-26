# Booking System: Implementation Plan (v4, reviewed)

Mohirlar AI Product Engineer internship, Task 3.
The 72h clock starts when you submit the application. Plan now; write code only after you submit.

Contents
- §0 Review: what was wrong in v3 and how v4 fixes it
- §1 Principles
- §2 Stack and tools
- §3 Domain rules
- §4 Database
- §5 Concurrency
- §6 Scheduling algorithm
- §7 API contract
- §8 Backend architecture
- §9 Frontend architecture
- §10 Testing strategy
- §11 Infrastructure and deploy
- §12 Phases (0–8), in detail
- §13 Edge case matrix
- §14 Claude Code workflow and tools
- §15 Must-understand list (interview)
- §16 README outline

---

## 0. Review: where v3 failed

Each row is a bug or gap that would have shipped with v3.

| # | Problem in v3 | Why it breaks | Fix in v4 |
|---|---|---|---|
| 1 | `ends_at` included the buffer | Client sees 10:00–11:15 for a 60-min service. The constraint can't compute `ends_at + buffer` either, because `timestamptz + interval` is not IMMUTABLE and index expressions must be | Separate `blocked_until` column. `ends_at` = real end |
| 2 | App overlap check and DB constraint could use different ranges | App says free while DB says taken (or the reverse), giving random 500s | One rule: provider conflicts use `[starts_at, blocked_until)` in both places |
| 3 | Client self-overlap only checked in app | Provider lock doesn't cover the same client booking two providers in parallel, so both pass | Second exclusion constraint on `client_id`, plus a user-row lock |
| 4 | `with db.begin()` inside services | `current_user` already queried on the same session, so SQLAlchemy autobegin started a transaction and `begin()` raises | Services call `db.commit()` explicitly; `get_db` only closes (which rolls back anything uncommitted) |
| 5 | Tests would use `create_all` | No `btree_gist` and no raw-SQL constraints, so the race test passes by luck or fails for the wrong reason | Tests run `alembic upgrade head`; truncate between tests |
| 6 | Race test through `TestClient` threads | TestClient isn't built for parallel threads, so results are flaky | Threads call the service directly, each with its own session, started together by `threading.Barrier` |
| 7 | "Today" and day bounds computed in UTC | Tashkent is UTC+5. After 19:00 UTC the server thinks it's yesterday, and slot queries miss bookings | All date logic in the business timezone; day bounds converted to UTC |
| 8 | Frontend date sent via `toISOString()` | Classic off-by-one day in UTC+5 | Send `YYYY-MM-DD` strings; Mantine v8 dates are strings |
| 9 | Naive datetimes accepted | `2026-10-01T10:00` is ambiguous | Pydantic `AwareDatetime`, otherwise 422 |
| 10 | Two error shapes | FastAPI's 422 is `{"detail":[...]}` while ours was `{"detail":{...}}`, so the frontend needs two parsers | One envelope `{"error":{code,message,details}}` for every error, including validation and 404 |
| 11 | Availability change kept orphaned bookings, time off ignored bookings | Customer has a booking during a vacation or outside the new hours, and nobody is told | 409 `SCHEDULE_CONFLICT` with the booking ids; admin resolves first |
| 12 | Deactivating a provider with future bookings | Same orphan problem | 409 `PROVIDER_HAS_BOOKINGS` |
| 13 | Public provider endpoint returned email and phone | Leaks employee contact data | Separate public and admin schemas |
| 14 | Cancel policy duplicated in the frontend | Two sources of truth, plus client clock skew | Server returns `allowed_actions` per booking |
| 15 | Admin confirm and client cancel at the same time | Lost update | Transitions lock the booking row |
| 16 | One user can book every slot | Abuse | `MAX_ACTIVE_BOOKINGS_PER_CLIENT`, enforced under the user lock |
| 17 | Pending never confirmed | Booking is stuck: can't be completed, slot blocked | Admin can confirm at any time; "needs action" filter; documented |
| 18 | "Re-run slot algorithm" on create | Only yes/no, so there's no precise error message | `check_start()` returns a reason; `compute_slots()` is built from it |
| 19 | Native PostgreSQL enums | Adding a status later needs painful migrations | `VARCHAR` + `CHECK` (`native_enum=False`) |
| 20 | Unnamed constraints | Can't map an `IntegrityError` to an error code | Naming convention + explicit constraint names |
| 21 | Magic numbers in the frontend (2h, 60 days, 15 min) | Frontend and backend drift apart | `GET /api/v1/meta` returns the policy |
| 22 | `citext` | Needs an extension plus a custom SQLAlchemy type | Lowercase the email in the schema; plain unique constraint |
| 23 | Role read from the JWT | Stale role; a deactivated user keeps access | Load the user from the DB every request, check `is_active`, pin `HS256`, require the secret |
| 24 | Login leaks which emails exist, via message and timing | User enumeration | Same error for both cases; verify against a dummy hash when the user is missing |
| 25 | Cascade FKs from bookings | Deleting a service would wipe booking history | `RESTRICT` on booking FKs; soft delete only |
| 26 | No rate limiting or security headers | Brute force on login, clickjacking | nginx `limit_req` + headers |
| 27 | nginx rate limit behind host nginx | Every request appears to come from 127.0.0.1, so all users share one bucket | `real_ip` module in the container nginx |
| 28 | DB port exposed | Postgres reachable from the internet on the server | Bind `127.0.0.1:5433` |
| 29 | No CI | Git history shows no quality gate | GitHub Actions from Phase 1 |
| 30 | Seed with fixed dates | Demo bookings end up in the past | Dates relative to now; `--reset` flag |
| 31 | Init SQL runs only on an empty volume | Test DB silently missing | Documented `docker compose down -v` |
| 32 | "Booking history" was ambiguous | Reviewer may mean an audit trail | Both: history list + `booking_events` table |
| 33 | Availability at 09:10 | Slots misaligned with the grid | Validate that times are 15-min multiples (DB check + schema) |
| 34 | Availability conflict check planned in the scheduling phase | Needs the bookings table, which doesn't exist yet, so the build order was wrong | Conflict checks move to Phase 4 |

---

## 1. Principles

1. **The database guarantees the invariants.** Overlaps, uniqueness and valid statuses are enforced by constraints, so app code can have a bug and data stays correct.
2. **Each rule lives in one place.**
   - Slot validity: `scheduling/domain.py`
   - Status transitions: `bookings/policies.py`
   - Policy numbers: `Settings`
   - Error codes: `core/errors.py`
3. **Pure core, thin edges.** Domain logic has no DB, no I/O and no clock calls, and `now` is passed in, so it can be unit-tested in milliseconds.
4. **Layers with one direction.** router → service → repository → model. Details in §8.
5. **The server computes everything derived:** `ends_at`, `blocked_until`, `price`, `allowed_actions`, `status`.
6. **Explicit time.** Every datetime is timezone-aware and stored in UTC. Business logic runs in `BUSINESS_TIMEZONE`.
7. **Follow CLAUDE_RULES.** Security checklist 2.6, reliability 2.7, accessibility 2.8 and polish 2.2 are applied where they fit (mapped in §11 and §12).

---

## 2. Stack and tools

### Backend

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12 | Runtime |
| uv | latest | Dependency management, lockfile, `uv run` |
| FastAPI | latest | HTTP layer, OpenAPI, dependency injection |
| Uvicorn | `uvicorn[standard]` | ASGI server, `--proxy-headers` behind nginx |
| SQLAlchemy | 2.0, sync, typed `Mapped[]` | ORM and query builder |
| psycopg | 3 (`psycopg[binary]`) | PostgreSQL driver; exposes `diag.constraint_name` |
| Alembic | latest | Migrations, including the raw-SQL constraints |
| Pydantic | v2 + `pydantic-settings` | Schemas, `AwareDatetime`, env config |
| email-validator | latest | `EmailStr` |
| PyJWT | latest | Access tokens (HS256 pinned) |
| pwdlib[argon2] | latest | Password hashing (current FastAPI docs recommendation) |
| pytest, pytest-cov, httpx | latest | Tests and coverage |
| ruff | latest | Lint and format |
| mypy | latest | Type check (`app/` strict-ish config) |
| pip-audit | latest | Dependency vulnerability scan in CI |

### Frontend

| Tool | Purpose |
|---|---|
| Vite + React 19 + TypeScript (strict) | App |
| Mantine v8 (`core`, `dates`, `form`, `notifications`) | UI kit; accessible components; date values are `YYYY-MM-DD` strings |
| dayjs + `utc` + `timezone` plugins | Display times in the business timezone (Mantine dates already depend on dayjs) |
| TanStack Query v5 | Server state, cache, invalidation |
| React Router v7 | Routing |
| openapi-typescript + openapi-fetch | Types generated from the backend, so front and back can't drift |
| ESLint (Vite template) + `tsc --noEmit` | Quality gate |
| Playwright (tier 3) | One end-to-end test of the booking flow; you already know it |

### Infrastructure

| Tool | Purpose |
|---|---|
| Docker Compose | `db`, `api`, `web` services |
| postgres:16-alpine | Database with `btree_gist` included |
| nginx (in `web` container) | Serves the SPA, proxies `/api`, rate limits, security headers |
| Host nginx + certbot (your GCP server) | TLS for `booking.khayrullo.uz` |
| GitHub Actions | CI: lint, types, migrations, tests, audits, frontend build |
| Makefile | One-word commands for you, reviewers and Claude |

---

## 3. Domain rules

### Time
- `BUSINESS_TIMEZONE=Asia/Tashkent`, from config.
- Availability is stored as local wall-clock `time`, per weekday.
- Bookings and time off are stored as UTC `timestamptz`.
- The API accepts any offset (a naive datetime gets 422) and returns datetimes in the business timezone with the offset (`+05:00`).
- Date parameters (`date=2026-10-05`) mean a **business-local** calendar date.
- Windows cannot cross midnight. The latest end time is 23:45. Documented limitation.
- DST: Tashkent has none. `zoneinfo` would still convert correctly for another timezone, but DST gaps and overlaps are not specially handled. Documented.

### Grid and ranges
- Slot step is `SLOT_STEP_MINUTES=15`, aligned to local midnight. A start is on the grid when local minutes since midnight divide by 15 and seconds and microseconds are 0.
- Availability start and end must be on the grid (DB check + schema).
- `duration_minutes`: 15–480, multiple of 15. `buffer_minutes`: 0–120, multiple of 5.
- For a booking or candidate starting at `t`:
  - **appointment** = `[t, t + duration)`, which must fit inside one availability window
  - **blocked** = `[t, t + duration + buffer)`, which must not overlap other bookings' blocked ranges or any time off
  - The buffer may run past closing time (cleanup after the last client).
- All ranges are half-open `[start, end)`, so back-to-back bookings are allowed.

### Booking window
- `MIN_NOTICE_MINUTES=60`: the start must be ≥ now + 60 min.
- `MAX_ADVANCE_DAYS=60`: the local date of the start must be ≤ local today + 60.
- `MAX_ACTIVE_BOOKINGS_PER_CLIENT=5`: count of bookings with status pending/confirmed and `ends_at > now`.

### Status machine

```
            confirm (admin)            complete (admin, ends_at <= now)
  pending ─────────────────► confirmed ──────────────────────────────► completed
     │                           │
     │ cancel                    │ cancel
     ▼                           ▼
  cancelled ◄────────────────────┘

  cancelled and completed are terminal.
```

| Action | Actor | Allowed from | Condition | Error when not allowed |
|---|---|---|---|---|
| confirm | admin | pending | none (late confirmation allowed) | 409 `INVALID_TRANSITION` |
| cancel | client (owner) | pending, confirmed | `starts_at - now >= CANCEL_CUTOFF_MINUTES` (120) | 409 `CANCEL_TOO_LATE` or `INVALID_TRANSITION` |
| cancel | admin | pending, confirmed | none (covers no-shows) | 409 `INVALID_TRANSITION` |
| complete | admin | confirmed | `ends_at <= now` | 409 `TOO_EARLY_TO_COMPLETE` or `INVALID_TRANSITION` |

- **Active** = `pending` or `confirmed`. Only active bookings block slots.
- New bookings start as `pending`.
- `allowed_actions(booking, actor, now)` in `policies.py` is the single source. The endpoints enforce it, and the response exposes it.
- Every create and every transition writes a `booking_events` row: from status, to status, actor, reason, time.

### Visibility
- Clients see active services and active providers (public fields only), and only their own bookings.
- Admins see everything, including inactive records and contact fields.
- An inactive or non-existent resource is 404 for clients.
- Another client's booking is 404, not 403, so its existence isn't revealed.

---

## 4. Database

### Conventions
- UUID v4 primary keys, generated in Python.
- `created_at` and `updated_at` are `timestamptz` (`server_default now()`, `onupdate now()`), via a `TimestampMixin`.
- Status and role are `VARCHAR` + `CHECK` (SQLAlchemy `Enum(..., native_enum=False, create_constraint=True)`).
- Naming convention on `MetaData`, so every constraint has a stable name:

```python
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

### Tables

```
users
  id             uuid pk
  email          varchar(254) not null      uq_users_email   (stored lowercase)
  password_hash  varchar(255) not null
  full_name      varchar(120) not null
  phone          varchar(32)  null
  role           varchar(16)  not null  check in ('client','admin')   default 'client'
  is_active      boolean not null default true
  created_at, updated_at

services
  id, name varchar(120) not null, description text null
  duration_minutes int not null  check (duration_minutes between 15 and 480 and duration_minutes % 15 = 0)
  buffer_minutes   int not null default 0  check (buffer_minutes between 0 and 120 and buffer_minutes % 5 = 0)
  price            numeric(12,2) not null  check (price >= 0)
  is_active        boolean not null default true
  created_at, updated_at

providers
  id, full_name varchar(120) not null, bio text null
  email varchar(254) null, phone varchar(32) null        -- admin-only fields
  is_active boolean not null default true
  created_at, updated_at

provider_services
  provider_id uuid fk → providers on delete cascade
  service_id  uuid fk → services  on delete cascade
  pk (provider_id, service_id)

availability_windows
  id
  provider_id uuid fk → providers on delete cascade
  weekday     smallint not null check (weekday between 0 and 6)     -- 0 = Monday
  start_time  time not null
  end_time    time not null
  check (end_time > start_time)
  check (extract(minute from start_time)::int % 15 = 0 and extract(second from start_time) = 0)
  check (extract(minute from end_time)::int % 15 = 0 and extract(second from end_time) = 0)
  -- overlapping windows on the same weekday are rejected in the service (full-replace PUT under provider lock)

time_off
  id
  provider_id uuid fk → providers on delete cascade
  starts_at timestamptz not null, ends_at timestamptz not null  check (ends_at > starts_at)
  reason varchar(200) null
  created_at

bookings
  id
  client_id    uuid fk → users     on delete restrict
  provider_id  uuid fk → providers on delete restrict
  service_id   uuid fk → services  on delete restrict
  starts_at      timestamptz not null
  ends_at        timestamptz not null          -- starts_at + duration
  blocked_until  timestamptz not null          -- ends_at + buffer
  price          numeric(12,2) not null        -- snapshot at booking time
  status         varchar(16) not null default 'pending'
                 check in ('pending','confirmed','cancelled','completed')
  notes          varchar(500) null
  cancelled_at   timestamptz null
  cancel_reason  varchar(200) null
  created_at, updated_at
  check (ends_at > starts_at)
  check (blocked_until >= ends_at)

booking_events
  id
  booking_id  uuid fk → bookings on delete cascade
  actor_id    uuid fk → users    on delete restrict
  from_status varchar(16) null        -- null on creation
  to_status   varchar(16) not null
  reason      varchar(200) null
  created_at
```

### Exclusion constraints (hand-written migration)

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE bookings ADD CONSTRAINT ex_bookings_provider_overlap
  EXCLUDE USING gist (
    provider_id WITH =,
    tstzrange(starts_at, blocked_until, '[)') WITH &&
  ) WHERE (status IN ('pending', 'confirmed'));

ALTER TABLE bookings ADD CONSTRAINT ex_bookings_client_overlap
  EXCLUDE USING gist (
    client_id WITH =,
    tstzrange(starts_at, ends_at, '[)') WITH &&
  ) WHERE (status IN ('pending', 'confirmed'));
```

- `btree_gist` lets a GiST index handle `uuid =`. Without it, `CREATE` fails.
- `tstzrange(..., '[)')` is IMMUTABLE, so it's allowed in an index. `blocked_until` is a stored column for exactly this reason (see §0 #1).
- Partial `WHERE`: cancelled and completed bookings never block.
- Write these in the migration with `op.execute`. Alembic autogenerate doesn't round-trip exclusion constraints, so leave them out of the models and add a comment pointing to the migration file.
- The SQLSTATE for a violation is `23P01` (`ExclusionViolation`).

### Indexes

```
ix_bookings_client_starts        bookings (client_id, starts_at desc)
ix_bookings_provider_starts      bookings (provider_id, starts_at)
ix_bookings_status_starts        bookings (status, starts_at)
ix_availability_provider_weekday availability_windows (provider_id, weekday)
ix_time_off_provider_starts      time_off (provider_id, starts_at)
ix_booking_events_booking        booking_events (booking_id, created_at)
```

### IntegrityError mapping (`core/errors.py`)

| Constraint | Error code | HTTP |
|---|---|---|
| `uq_users_email` | `EMAIL_TAKEN` | 409 |
| `ex_bookings_provider_overlap` | `SLOT_TAKEN` | 409 |
| `ex_bookings_client_overlap` | `CLIENT_OVERLAP` | 409 |
| any other | re-raise, which becomes a 500 `INTERNAL_ERROR`, logged | 500 |

Read the constraint name with `exc.orig.diag.constraint_name` (psycopg 3).

---

## 5. Concurrency

### Isolation level
PostgreSQL default, **READ COMMITTED**. Each statement sees a fresh snapshot. After a transaction waits on a `FOR UPDATE` lock, its next `SELECT` sees what the lock holder committed. That's what makes the "lock, then read, then check" pattern correct.
Do not switch to REPEATABLE READ: the snapshot would be taken before the lock wait, and you'd get serialization errors instead.

### Lock order: always this order, never the reverse, so no deadlocks

```
users row  →  providers row  →  bookings row
```

| Transaction | Locks | Why |
|---|---|---|
| Create booking | user (client) → provider | User lock: per-client limit and self-overlap. Provider lock: schedule consistency |
| Replace availability | provider | Checked against future bookings |
| Add time off | provider | Checked against future bookings |
| Deactivate provider | provider | Checks for future bookings |
| Confirm / cancel / complete | booking | Stops lost updates between admin and client |

No transaction takes provider → user, so there's no lock cycle.

### Create booking: exact steps (`BookingService.create`)

```
1. SELECT users     WHERE id = :client_id                    FOR UPDATE
2. SELECT providers WHERE id = :provider_id AND is_active    FOR UPDATE     → 404 if missing
3. service = active service offered by provider                           → 404 / 422 SERVICE_NOT_OFFERED
4. load, now that the locks are held (fresh snapshot):
     windows   for local weekday of starts_at
     time_off  overlapping [day_start - 1 day, day_end + 1 day)
     bookings  active, same provider, same range
5. reason = domain.check_start(...)          → mapped error (422 or 409 SLOT_TAKEN)
6. client rules:
     active future bookings of client >= limit       → 409 ACTIVE_LIMIT_REACHED
     own active booking overlapping [start, end)     → 409 CLIENT_OVERLAP
7. INSERT booking (pending, price = service.price, ends_at, blocked_until)
   INSERT booking_event (null → pending, actor = client)
8. COMMIT
   IntegrityError → rollback → map by constraint name (safety net)
```

### Why both locks and constraints
- **Constraints** guarantee what a database can express: no overlaps. They hold even for a buggy script or a future endpoint.
- **Locks** protect rules a constraint can't express: working hours, time off, the per-client limit, and admin schedule edits happening at the same moment as a booking.
- The race test (§10) proves each layer on its own.

---

## 6. Scheduling algorithm (`modules/scheduling/domain.py`, pure)

```python
@dataclass(frozen=True, slots=True)
class TimeRange:
    start: datetime   # aware, UTC
    end: datetime

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: "TimeRange") -> bool:
        return self.start <= other.start and other.end <= self.end


class SlotRejection(StrEnum):
    OFF_GRID = "SLOT_OFF_GRID"                    # 422
    TOO_SOON = "SLOT_TOO_SOON"                    # 422 (past or < min notice)
    TOO_FAR = "SLOT_TOO_FAR"                      # 422
    OUTSIDE_HOURS = "OUTSIDE_WORKING_HOURS"       # 422
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE" # 422 (time off)
    TAKEN = "SLOT_TAKEN"                          # 409


@dataclass(frozen=True, slots=True)
class ScheduleRules:
    tz: ZoneInfo
    step: timedelta
    min_notice: timedelta
    max_advance_days: int


@dataclass(frozen=True, slots=True)
class ProviderDay:
    windows: list[TimeRange]    # UTC, for one local date
    time_off: list[TimeRange]
    busy: list[TimeRange]       # other active bookings' [starts_at, blocked_until)
```

### `check_start(start, duration, buffer, day, rules, now) -> SlotRejection | None`

Checks run in this order, so the first failing check decides the error:

1. `OFF_GRID`: local time not aligned to `step` from local midnight
2. `TOO_SOON`: `start < now + min_notice`
3. `TOO_FAR`: `local_date(start) > local_date(now) + max_advance_days`
4. `OUTSIDE_HOURS`: no window `contains` the appointment `[start, start + duration)`
5. `PROVIDER_UNAVAILABLE`: blocked `[start, start + duration + buffer)` overlaps any time off
6. `TAKEN`: blocked overlaps any busy range
7. otherwise `None`

### `compute_slots(duration, buffer, day, rules, now) -> list[TimeRange]`

```
for window in day.windows (sorted):
    t = window.start
    while t + duration <= window.end:
        if check_start(t, ...) is None:
            yield TimeRange(t, t + duration)      # returned to client as appointment range
        t += rules.step
```

The same function validates both listing and booking, so they can't disagree.

### Helpers (`core/timezone.py`)
- `local_day_bounds(date, tz) -> TimeRange`: local 00:00 to next local 00:00, as UTC
- `windows_for_date(rows, date, tz) -> list[TimeRange]`: `datetime.combine(date, t, tzinfo=tz)` then `.astimezone(UTC)`
- `to_business_tz(dt)`: for serialization

### Slots endpoint pre-checks (`scheduling/service.py`)
- The date must be in `[local today, local today + MAX_ADVANCE_DAYS]`, otherwise 422 `DATE_OUT_OF_RANGE`.
- Provider inactive: 404. Service inactive: 404. Service not offered by provider: 422 `SERVICE_NOT_OFFERED`.
- A day with no windows returns `[]` with 200 (a day off is not an error).

---

## 7. API contract

Base path `/api/v1`. JSON only. Datetimes are ISO 8601 with offset.

### Error envelope (every non-2xx)

```json
{"error": {"code": "SLOT_TAKEN", "message": "This time was just booked by someone else.", "details": {}}}
```

Validation errors: `code = "VALIDATION_ERROR"`, `details.fields = {"body.starts_at": "Input should have timezone info"}`.

### Error codes

| HTTP | Codes |
|---|---|
| 401 | `UNAUTHENTICATED` |
| 403 | `FORBIDDEN` |
| 404 | `NOT_FOUND` |
| 409 | `EMAIL_TAKEN`, `SLOT_TAKEN`, `CLIENT_OVERLAP`, `ACTIVE_LIMIT_REACHED`, `INVALID_TRANSITION`, `CANCEL_TOO_LATE`, `TOO_EARLY_TO_COMPLETE`, `SCHEDULE_CONFLICT`, `PROVIDER_HAS_BOOKINGS` |
| 422 | `VALIDATION_ERROR`, `SLOT_OFF_GRID`, `SLOT_TOO_SOON`, `SLOT_TOO_FAR`, `OUTSIDE_WORKING_HOURS`, `PROVIDER_UNAVAILABLE`, `SERVICE_NOT_OFFERED`, `DATE_OUT_OF_RANGE`, `INVALID_SCHEDULE` |
| 429 | `RATE_LIMITED` (from nginx) |
| 500 | `INTERNAL_ERROR` (no stack trace in the body) |

**Rule:** 409 means a conflict with current state (retrying later or choosing differently may work). 422 means the request itself is invalid.

### Auth

| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/auth/register` | public | Role is always `client`. All request schemas use `extra="forbid"`, so sending `role` gets 422. Password 8–128 chars |
| POST | `/auth/login` | public | Sets `access_token` cookie (httpOnly, SameSite=Lax, Secure in prod, Path=/api) and returns `{access_token, token_type, user}` |
| POST | `/auth/logout` | any | Clears the cookie. Stateless JWT stays valid until expiry (60 min); documented |
| GET | `/auth/me` | user | Current user |

- `current_user`: reads the `Authorization: Bearer` header first (Swagger, curl), then the cookie. Decodes with `algorithms=["HS256"]`, loads the user by `sub`, and requires `is_active`.
- Swagger's "Authorize" button uses `HTTPBearer(auto_error=False)`.
- Login returns the same 401 `UNAUTHENTICATED` for an unknown email and a wrong password, and verifies against a dummy hash when the user is missing so timing matches.
- CSRF: SameSite=Lax blocks cross-site POSTs from carrying the cookie. The API only accepts `application/json`, so a cross-site form post can't produce a valid request.

### Catalog (services)

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/services` | public | Active only. Admin: `?include_inactive=true` |
| GET | `/services/{id}` | public | Inactive = 404 for non-admins |
| POST | `/services` | admin | |
| PATCH | `/services/{id}` | admin | Existing bookings keep their price and time snapshot |
| DELETE | `/services/{id}` | admin | Soft (`is_active=false`); existing bookings still honored |

### Providers

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/providers?service_id=` | public | `ProviderPublic`: id, full_name, bio, service ids |
| GET | `/providers/{id}` | public | Admin gets `ProviderAdmin` (with contacts and is_active) |
| POST | `/providers` | admin | |
| PATCH | `/providers/{id}` | admin | Setting `is_active=false` follows the DELETE rule |
| DELETE | `/providers/{id}` | admin | Soft. 409 `PROVIDER_HAS_BOOKINGS` if future active bookings exist |
| PUT | `/providers/{id}/services` | admin | Body `{service_ids: []}`. Removing a service keeps existing bookings |

### Scheduling

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/providers/{id}/availability` | public | Weekly windows |
| PUT | `/providers/{id}/availability` | admin | Full replace. 422 `INVALID_SCHEDULE` (overlap or off-grid). 409 `SCHEDULE_CONFLICT` + `details.booking_ids` if a future active booking would fall outside the new hours |
| GET | `/providers/{id}/time-off` | admin | Upcoming |
| POST | `/providers/{id}/time-off` | admin | `ends_at > now`, at most 365 days long. 409 `SCHEDULE_CONFLICT` if active bookings overlap |
| DELETE | `/providers/{id}/time-off/{time_off_id}` | admin | Hard delete |
| GET | `/providers/{id}/slots?service_id=&date=` | public | `[{starts_at, ends_at}]` |

### Bookings

| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/bookings` | client | Body: `provider_id, service_id, starts_at (aware), notes?`. 201 → `BookingOut` |
| GET | `/bookings` | user | Client: own only, `scope=upcoming\|history`. Admin: plus `status[]`, `provider_id`, `from`, `to`, `needs_action=true`. Paginated |
| GET | `/bookings/{id}` | owner/admin | Includes `events` timeline |
| POST | `/bookings/{id}/cancel` | owner/admin | Body `{reason?}` |
| POST | `/bookings/{id}/confirm` | admin | |
| POST | `/bookings/{id}/complete` | admin | |
| GET | `/bookings/{id}/calendar.ics` | owner/admin | Tier 3 bonus: calendar integration |

- `upcoming` = active and `ends_at > now`, sorted by `starts_at` ascending. `history` = the rest, sorted by `starts_at` descending. Ties are broken by `id`.
- `BookingOut`: id, status, starts_at, ends_at, price, notes, service {id, name, duration_minutes}, provider {id, full_name}, allowed_actions, created_at.
- `BookingAdminOut` adds client {id, full_name, email, phone} and cancel fields.
- Pagination: `page ≥ 1`, `size` 1–100 (default 20). Response `{items, total, page, size}`.
- Lists use `selectinload` for service and provider, so there's no N+1 query problem.

### Admin and meta

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/admin/stats?from=&to=` | admin | Local dates. Counts by status, revenue (completed), bookings per provider, top 5 services |
| GET | `/meta` | public | `{timezone, slot_step_minutes, min_notice_minutes, max_advance_days, cancel_cutoff_minutes, currency}` |
| GET | `/health` | public | Runs `SELECT 1`. 200 `{status:"ok"}` or 503 |

FastAPI `generate_unique_id_function` = route name, so the generated TypeScript has readable operation names.

---

## 8. Backend architecture

### Tree

```
backend/
├── pyproject.toml  uv.lock  alembic.ini  Dockerfile  .env.example
├── alembic/
│   ├── env.py                      reads Settings.database_url; target_metadata from app.models
│   └── versions/
├── app/
│   ├── main.py                     create_app(): routers, exception handlers, openapi ids
│   ├── models.py                   imports every module's models (Alembic + relationship registry)
│   ├── core/
│   │   ├── config.py               Settings (pydantic-settings), get_settings() with lru_cache
│   │   ├── db.py                   engine, SessionLocal, get_db()
│   │   ├── base.py                 DeclarativeBase + naming convention, UUIDPrimaryKey, TimestampMixin
│   │   ├── security.py             hash_password, verify_password, create_token, decode_token
│   │   ├── clock.py                Clock protocol, SystemClock, get_clock()
│   │   ├── timezone.py             local_day_bounds, windows_for_date, to_business_tz
│   │   └── errors.py               AppError + subclasses, codes, handlers, translate_integrity_error
│   ├── api/
│   │   ├── deps.py                 DbSession, CurrentUser, OptionalUser, AdminUser, ClockDep, SettingsDep
│   │   └── router.py               include every module router under /api/v1
│   └── modules/
│       ├── auth/        router.py  schemas.py  service.py
│       ├── users/       models.py  repository.py
│       ├── catalog/     models.py  schemas.py  repository.py  service.py  router.py
│       ├── providers/   models.py  schemas.py  repository.py  service.py  router.py
│       ├── scheduling/  models.py  schemas.py  repository.py  domain.py  service.py  router.py
│       ├── bookings/    models.py  schemas.py  repository.py  policies.py  service.py  router.py
│       ├── admin/       schemas.py  repository.py  service.py  router.py
│       └── system/      router.py                 (/meta, /health)
├── scripts/
│   ├── seed.py                     demo data relative to now; --reset
│   ├── create_admin.py             interactive admin creation for prod
│   └── export_openapi.py           writes openapi.json without running a server
└── tests/
    ├── conftest.py
    ├── factories.py                make_user, make_service, make_provider, make_window, make_booking
    ├── unit/          test_domain.py  test_policies.py  test_security.py  test_timezone.py
    ├── api/           test_auth.py  test_catalog.py  test_providers.py  test_scheduling.py
    │                  test_bookings_create.py  test_bookings_lifecycle.py  test_bookings_list.py
    │                  test_admin.py  test_errors.py
    └── concurrency/   test_race.py
```

`scheduling` owns `availability_windows` and `time_off`. `providers` owns `providers` and `provider_services`.

### Layer responsibilities

| Layer | Does | Never does |
|---|---|---|
| `router.py` | HTTP: path/query/body parsing, auth dependencies, status codes, `response_model` | Queries, business rules, commits |
| `schemas.py` | Pydantic in/out, field validation, normalization (lowercase email) | DB access |
| `service.py` | Use cases: orchestration, locks, rules, `commit()`, IntegrityError translation | HTTP types (`Request`, `HTTPException`) |
| `repository.py` | SQLAlchemy `select/insert/update`, `with_for_update`, eager loading | Rules, commits, HTTP |
| `domain.py` / `policies.py` | Pure functions and dataclasses | DB, I/O, clock, settings lookups |
| `models.py` | Tables, relationships | Logic |

### Import rules
- `router` imports its own `service` and `schemas`, plus `api/deps`.
- A `service` may import **any module's repository** and domain code. Services never import other services, which prevents cycles.
- A `repository` imports models only.
- `domain`/`policies` import only the stdlib and `core/timezone`.
- Nothing imports a router except `api/router.py`.

### Dependency injection pattern

```python
# api/deps.py
DbSession = Annotated[Session, Depends(get_db)]
ClockDep = Annotated[Clock, Depends(get_clock)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]

# modules/bookings/router.py
def get_booking_service(db: DbSession, clock: ClockDep, settings: SettingsDep) -> BookingService:
    return BookingService(db, clock, settings)

BookingServiceDep = Annotated[BookingService, Depends(get_booking_service)]

@router.post("", status_code=201, response_model=BookingOut)
def create_booking(body: BookingCreate, user: CurrentUser, service: BookingServiceDep) -> BookingOut:
    return service.create(actor=user, command=body)
```

Tests override `get_clock` with a `FrozenClock`.

### Transactions
- `get_db()` yields a `Session` and closes it in `finally`. Closing rolls back anything uncommitted.
- A write use case ends with `self.db.commit()`. Read-only use cases never commit.
- Don't use `with session.begin()`: the auth dependency has already started a transaction (autobegin).
- Services catch `IntegrityError` around `flush()`/`commit()`, roll back, and raise the translated `AppError`.

### Error handling (`core/errors.py`)
- `AppError(code, message, status, details=None)` with subclasses: `NotFound`, `Forbidden`, `Unauthenticated`, `Conflict`, `Unprocessable`.
- Handlers registered for `AppError`, `RequestValidationError`, `StarletteHTTPException` (unknown routes → envelope) and `Exception` (→ 500 `INTERNAL_ERROR`, logged with the request path, no body or PII).

### Example: `POST /api/v1/bookings` through the layers

```
router.create_booking      validates body (AwareDatetime, UUIDs, notes ≤ 500), gets user + service
  → BookingService.create  steps from §5
      → UserRepository.lock(client_id)
      → ProviderRepository.lock_active(provider_id)
      → CatalogRepository.get_offered(provider_id, service_id)
      → ScheduleRepository.windows / time_off_between
      → BookingRepository.active_between(provider_id, range)
      → domain.check_start(...)                     pure
      → BookingRepository.count_active_future / client_overlap
      → BookingRepository.add(booking) + add_event(...)
      → db.commit()
  ← BookingOut.from_model(booking, actions=policies.allowed_actions(booking, user, now))
```

---

## 9. Frontend architecture

### Tree

```
frontend/src/
├── app/
│   ├── main.tsx              providers: MantineProvider, QueryClientProvider, Notifications, Router
│   ├── router.tsx            routes + lazy pages
│   └── theme.ts              one primary color (teal), default radius (not pill), system font
├── shared/
│   ├── api/
│   │   ├── schema.d.ts       generated (npm run gen:api); never edited
│   │   ├── client.ts         openapi-fetch, baseUrl '/api/v1', credentials 'include'
│   │   ├── errors.ts         ApiError type, message per error code
│   │   └── queryClient.ts    retry: skip 4xx; 401 → auth reset
│   ├── lib/
│   │   ├── datetime.ts       dayjs tz setup; formatDateTime, formatTime, toApiDate ('YYYY-MM-DD')
│   │   └── money.ts          formatPrice(decimalString, currency)
│   ├── hooks/useMeta.ts      GET /meta (staleTime Infinity)
│   └── ui/                   StatusBadge, ConfirmModal, EmptyState, PageTitle (document.title), ErrorState
├── features/
│   ├── auth/                 api.ts, AuthProvider.tsx, useAuth.ts, RequireAuth.tsx, RequireAdmin.tsx,
│   │                         LoginPage.tsx, RegisterPage.tsx
│   ├── booking/              api.ts, BookPage.tsx, ServiceStep.tsx, ProviderStep.tsx, DateStep.tsx,
│   │                         SlotStep.tsx, ConfirmStep.tsx, useBookingParams.ts
│   ├── my-bookings/          api.ts, MyBookingsPage.tsx, BookingList.tsx, CancelButton.tsx
│   └── admin/                api.ts, AdminLayout.tsx, AdminBookingsPage.tsx, StatsCards.tsx,
│                             BookingFilters.tsx, BookingActions.tsx
│                             tier 3: ServicesPage.tsx, ProvidersPage.tsx, ScheduleEditor.tsx
└── pages/NotFoundPage.tsx
```

Rule: features import from `shared`, never from each other. `api.ts` in each feature holds its query keys, queries and mutations.

### Routes

| Path | Page | Guard |
|---|---|---|
| `/login`, `/register` | auth pages | guest |
| `/` | BookPage | public browsing; login required at the confirm step |
| `/bookings` | MyBookingsPage | client |
| `/admin` | AdminBookingsPage | admin |
| `/admin/services`, `/admin/providers` | tier 3 | admin |
| `*` | NotFoundPage | — |

### Booking flow (`BookPage`)
- Wizard state lives in URL params `?service=&provider=&date=`, so refresh and back button keep the selection.
- Steps:
  1. Service cards: name, duration, price.
  2. Providers offering it.
  3. DatePicker: `minDate` today, `maxDate` today + `meta.max_advance_days`. Weekdays with no availability are disabled (from `GET /availability`).
  4. Slot grid: `<button>`s with `aria-pressed`, labeled "10:00–11:00". Empty state: "No free time on this day, try another date."
  5. Confirm: summary, notes textarea, Book button (disabled while pending, so double-clicks don't send twice).
- 409 `SLOT_TAKEN`: toast, invalidate the slots query, stay on step 4.
- 401: send to `/login?next=…`, then return.
- Success: toast, then `/bookings`.

### My bookings
- Upcoming / History tabs using `scope`.
- The Cancel button shows only if `allowed_actions` includes `cancel`, and opens a confirm modal with an optional reason.
- Times are shown in the business timezone with a "Tashkent time" label.

### Admin bookings
- Stats cards (today, pending, revenue this month).
- Filters: status, provider, date range, "needs action".
- Table with client name and phone.
- Action buttons come from `allowed_actions`.
- A row expands to show the events timeline.

### Datetime rules (all through `shared/lib/datetime.ts`)
- Display: `dayjs(iso).tz(meta.timezone).format(...)`.
- Date params: Mantine v8 gives `'YYYY-MM-DD'`, which is sent as is. Never `toISOString()` for dates.
- `starts_at` sent back exactly as the slot's ISO string from the API; never rebuilt on the client.

### Polish and accessibility (CLAUDE_RULES 2.2, 2.8)
- Page title per route, favicon, custom 404, `<html lang="en">`.
- No purple gradients, no pill buttons, no fake numbers.
- Every input has a visible label; errors under fields from `details.fields`; focus visible; keyboard-reachable slot grid; contrast via the Mantine default palette.
- Loading skeletons, empty states, error states on every data view.

---

## 10. Testing strategy

### Layers

| Layer | What | DB | Speed |
|---|---|---|---|
| Unit | `domain.py`, `policies.py`, `timezone.py`, `security.py` | no | ms |
| API | Every endpoint via `TestClient`, auth, permissions, error envelope | yes | s |
| Concurrency | Real parallel transactions | yes | s |
| E2E (tier 3) | Playwright: register → book → cancel | full stack | 10s |

### Database strategy
- A separate DB `booking_test`, created by `docker/initdb/01-create-test-db.sql`.
- Session fixture: `alembic downgrade base` then `alembic upgrade head` against `TEST_DATABASE_URL`, so migrations are tested too.
- Autouse function fixture after each test:
  `TRUNCATE users, services, providers, provider_services, availability_windows, time_off, bookings, booking_events RESTART IDENTITY CASCADE`.
  Not rollback isolation, because concurrency tests need real commits across connections.
- `conftest.py` sets `DATABASE_URL = TEST_DATABASE_URL` **before** importing the app. The engine is created at import time.

### Clock
- `FrozenClock(now)` fixture; `app.dependency_overrides[get_clock]`.
- Default frozen time: Monday 2030-01-07 08:00 Tashkent, so fixtures are stable and far from real dates.

### Race tests (`tests/concurrency/test_race.py`)

```python
def run_concurrently(n, fn):
    barrier = threading.Barrier(n)
    def worker(i):
        with SessionLocal() as session:
            barrier.wait()
            return fn(session, i)
    with ThreadPoolExecutor(n) as pool:
        return list(pool.map(worker, range(n)))
```

| Test | Setup | Assert |
|---|---|---|
| `test_same_slot_ten_clients` | 10 clients, same provider and start | exactly 1 `ok`, 9 `SLOT_TAKEN`; 1 active row |
| `test_partial_overlap_parallel` | 10:00 and 10:30 (60 min) in parallel | 1 ok, 1 `SLOT_TAKEN` |
| `test_same_client_two_providers` | one client, two providers, same time | 1 ok, 1 `CLIENT_OVERLAP` |
| `test_active_limit_parallel` | client at limit − 1, two parallel bookings | 1 ok, 1 `ACTIVE_LIMIT_REACHED` |
| `test_constraint_without_app` | raw INSERT of an overlapping row bypassing the service | `IntegrityError`, SQLSTATE 23P01 |
| `test_booking_vs_time_off_parallel` | booking and time off for the same hour in parallel | exactly one succeeds |
| `test_cancel_vs_confirm_parallel` | client cancel and admin confirm at once | final status is consistent; two events at most, no lost update |

The engine's `pool_size` in tests must be ≥ the thread count.

### Coverage target
`domain.py` and `policies.py`: 100% line coverage. Overall: report the real number, never invent one.

---

## 11. Infrastructure and deploy

### Environment (`.env.example`)

| Variable | Dev value | Notes |
|---|---|---|
| `ENV` | `dev` | `prod` turns on `COOKIE_SECURE` and hides error details |
| `DATABASE_URL` | `postgresql+psycopg://booking:booking@localhost:5433/booking` | In compose: host `db:5432` |
| `TEST_DATABASE_URL` | `.../booking_test` | |
| `JWT_SECRET` | *(empty)* | **Required**; app refuses to start. `openssl rand -hex 32` |
| `JWT_TTL_MINUTES` | 60 | |
| `COOKIE_SECURE` | false | true in prod |
| `BUSINESS_TIMEZONE` | Asia/Tashkent | |
| `SLOT_STEP_MINUTES` | 15 | |
| `MIN_NOTICE_MINUTES` | 60 | |
| `MAX_ADVANCE_DAYS` | 60 | |
| `CANCEL_CUTOFF_MINUTES` | 120 | |
| `MAX_ACTIVE_BOOKINGS_PER_CLIENT` | 5 | |
| `CURRENCY` | UZS | |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | demo values | Demo only; prod admin via `scripts/create_admin.py` |

`.env` is in `.gitignore`. Only `.env.example` is committed.

### `compose.yaml`

```
db:   postgres:16-alpine
      ports "127.0.0.1:5433:5432"  (localhost only, also on the server)
      volume pgdata; ./docker/initdb mounted to /docker-entrypoint-initdb.d
      healthcheck pg_isready; restart unless-stopped
api:  build ./backend; env_file .env; depends_on db (service_healthy)
      command: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
               --proxy-headers --forwarded-allow-ips="*"
      healthcheck curl /api/v1/health; restart unless-stopped; non-root user
web:  build ./frontend (multi-stage: node build → nginx:alpine)
      ports "127.0.0.1:8081:80"; depends_on api; restart unless-stopped
```

The init SQL only runs on an empty volume. If `booking_test` is missing: `docker compose down -v`.

### Container nginx (`frontend/nginx.conf`)

```
set_real_ip_from 172.16.0.0/12;  real_ip_header X-Real-IP;      # true client IP from host nginx
limit_req_zone $binary_remote_addr zone=api:10m  rate=20r/s;
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;
limit_req_status 429;

location /api/v1/auth/ { limit_req zone=auth burst=5 nodelay;  proxy_pass http://api:8000; }
location /api/         { limit_req zone=api  burst=40 nodelay; proxy_pass http://api:8000; }
location /             { try_files $uri /index.html; }
error_page 429 = @rate_limited;
location @rate_limited { default_type application/json;
  return 429 '{"error":{"code":"RATE_LIMITED","message":"Too many requests"}}'; }

add_header X-Content-Type-Options nosniff always;
add_header Referrer-Policy strict-origin-when-cross-origin always;
add_header X-Frame-Options DENY always;
add_header Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'" always;
```

`style-src 'unsafe-inline'` is needed because Mantine injects CSS variables. Documented.

### Deploy to `booking.khayrullo.uz` (you run these; Claude doesn't touch the server)
1. DNS: `A booking → 35.238.169.98`.
2. On the server, clone the repo into `/var/www/booking`, create `.env` with a prod secret and `ENV=prod`, then run `docker compose up -d --build`.
3. Host nginx server block: `server_name booking.khayrullo.uz; location / { proxy_pass http://127.0.0.1:8081; proxy_set_header X-Real-IP $remote_addr; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; }`
4. `sudo certbot --nginx -d booking.khayrullo.uz`
5. `docker compose exec api python -m scripts.seed --reset` (demo data)
6. Backup cron, daily: `docker compose exec -T db pg_dump -U booking booking | gzip > /var/backups/booking/$(date +%F).sql.gz`, keeping 7 days. Test one restore.
7. Check: `curl https://booking.khayrullo.uz/api/v1/health`

### CI (`.github/workflows/ci.yml`)
- **backend** job: postgres:16 service, then:
  - `uv sync`
  - `ruff check`, `ruff format --check`, `mypy app`
  - `alembic upgrade head`
  - `pytest --cov`
  - `pip-audit`
- **frontend** job (added in Phase 6): `npm ci`, `npm run lint`, `tsc --noEmit`, `npm run build`, `npm audit --audit-level=high`.
- Add the CI badge to the README.

### Makefile

```
make dev-db      docker compose up -d db
make migrate     cd backend && uv run alembic upgrade head
make api         cd backend && uv run uvicorn app.main:app --reload
make web         cd frontend && npm run dev
make test        cd backend && uv run pytest
make lint        ruff check, ruff format --check, mypy
make seed        cd backend && uv run python -m scripts.seed --reset
make openapi     export openapi.json + npm run gen:api
make up          docker compose up -d --build
```

---

## 12. Phases

Every phase has the same shape: goal → files → steps → tools → tests → done-when → commits.
Don't start phase N+1 until "done when" passes. Push after every commit.

Time budget: about 24h of work inside the 72h window, leaving room for sleep and a buffer.

| Phase | Work | Hours |
|---|---|---|
| 0 | Repo, rules, CI skeleton | 0.5 |
| 1 | Backend core + auth | 3 |
| 2 | Catalog + providers | 2 |
| 3 | Scheduling domain + slots | 3 |
| 4 | Bookings create + concurrency | 3.5 |
| 5 | Lifecycle, lists, admin, meta, seed | 2.5 |
| 6 | Frontend | 5.5 |
| 7 | Ship: docker, nginx, docs, deploy | 2.5 |
| 8 | Review, fixes, interview prep | 1.5 |

---

### Phase 0: Repository and rules (right after submitting)

**Goal:** empty but disciplined repo, public on GitHub, CI green on the first commit.

**Files:** `README.md` (title + one line), `CLAUDE.md` (from the companion file), `docs/PLAN.md` (this file), `docs/AI_LOG.md` (empty table), `.gitignore` (Python, Node, `.env`, `.venv`, `node_modules`, `dist`), `.claude/settings.json` (permissions allowlist, §14), `Makefile`, `compose.yaml` (db only), `docker/initdb/01-create-test-db.sql`, `.github/workflows/ci.yml` (backend job placeholder: checkout + `uv --version`).

**Steps:**
1. `gh repo create booking-system --public --clone`
2. Add the files. `docker compose up -d db`, then `psql -h localhost -p 5433 -U booking -c '\l'` shows `booking` and `booking_test`.
3. Commit and push. Check that CI is green.

**Done when:** repo public, CI green, both databases exist.

**Commits:**
- `chore: repository setup, rules, compose database`
- `ci: add workflow skeleton`

---

### Phase 1: Backend core and auth

**Goal:** a running API with config, DB, error envelope, clock, health, JWT auth, and a migrated `users` table.

**Files:**
- `backend/pyproject.toml`, `uv.lock`, `alembic.ini`, `alembic/env.py`
- `app/main.py`, `app/models.py`
- `app/core/`: `config.py`, `db.py`, `base.py`, `security.py`, `clock.py`, `timezone.py`, `errors.py`
- `app/api/`: `deps.py`, `router.py`
- `app/modules/users/`: `models.py`, `repository.py`
- `app/modules/auth/`: `schemas.py`, `service.py`, `router.py`
- `app/modules/system/router.py` (`/health` now, `/meta` in Phase 5)
- `scripts/create_admin.py`
- `tests/`: `conftest.py`, `factories.py`, `unit/test_security.py`, `api/test_auth.py`, `api/test_errors.py`

**Steps:**
1. `uv init backend`; add the dependencies from §2; ruff and mypy config in `pyproject.toml`.
2. `Settings`: every variable in §11; `jwt_secret: SecretStr` with no default, so a missing secret makes startup fail.
3. `base.py`: naming convention, `UUIDPrimaryKey`, `TimestampMixin`.
4. `errors.py`: `AppError` hierarchy, the four handlers, `translate_integrity_error` (starts with `uq_users_email` only).
5. `security.py`: pwdlib argon2; JWT `sub`, `exp`, `iat`; decode pinned to `HS256`; a `DUMMY_HASH` for timing-safe login.
6. `deps.py`: `get_current_user` (Bearer, then cookie; DB load; `is_active`), `OptionalUser`, `require_admin`.
7. Auth service: register (normalized email, role=client), login (same error for both failures), logout; router sets and clears the cookie.
8. Alembic: first migration `users` (autogenerate, then **read and clean it by hand**).
9. `create_admin.py`: prompts for email, name and password (`getpass`) and creates the admin.
10. CI backend job: postgres service, `uv sync`, lint, mypy, migrate, pytest.

**Tests:**
- register ok
- email case-insensitive duplicate → 409 `EMAIL_TAKEN`
- `role` in the body → 422 (`extra="forbid"`), so nobody can register as admin
- short password → 422 envelope
- login ok returns a token and sets the cookie
- wrong password vs unknown email: identical 401 body
- `/auth/me` with Bearer, with cookie, with none (401), with an expired token (401), with a deactivated user (401)
- token with `alg: none` or another algorithm → 401
- unknown route → 404 envelope
- `/health` → 200

**Done when:** `make lint test` is green locally and in CI. In `/api/docs`: register, Authorize, `/auth/me`.

**Commits:**
- `feat(api): app factory, settings, database session, error envelope`
- `feat(api): users table and first migration`
- `feat(auth): register, login, logout with JWT cookie and bearer`
- `test(auth): auth flows and error envelope`
- `ci: backend lint, type check, migrate, test`

---

### Phase 2: Catalog and providers

**Goal:** admin manages services and providers; the public reads them without private fields.

**Files:**
- `modules/catalog/*`: model `Service`, `CatalogRepository`, `CatalogService`, schemas `ServiceCreate`, `ServiceUpdate`, `ServicePublic`, `ServiceAdmin`
- `modules/providers/*`: `Provider`, `provider_services` table, `ProviderRepository`, `ProviderService`, schemas `ProviderPublic`, `ProviderAdmin`, `ProviderCreate`, `ProviderUpdate`, `ProviderServicesUpdate`
- migration `services, providers, provider_services`
- `tests/api/test_catalog.py`, `test_providers.py`

**Steps:**
1. Models with the checks from §4 (duration and buffer checks as named `CheckConstraint`s).
2. Repositories: `list_active`, `list_all`, `get`, `get_active`, `add`, and `ProviderRepository.lock_active(id)` (`with_for_update`).
3. Services: soft delete; `set_services` replaces the M2M after validating every service id exists (422 otherwise).
4. Routers: public GET with `OptionalUser` (admin sees inactive and admin schemas), admin writes.
5. Provider deactivation is a plain soft delete for now. The future-bookings check is added in Phase 4, because the bookings table doesn't exist yet (§0 #34).

**Tests:**
- CRUD happy paths
- client calling an admin endpoint → 403; no token → 401
- inactive service is 404 for public, visible for admin
- duration 20 or 0 → 422; negative price → 422
- public provider response has no `email`/`phone` keys
- `?service_id=` filter
- `set_services` with an unknown id → 422

**Done when:** tests green; `/api/docs` shows public vs admin shapes.

**Commits:**
- `feat(catalog): services with admin CRUD and soft delete`
- `feat(providers): providers, offered services, public and admin views`

---

### Phase 3: Scheduling domain and slots

**Goal:** a correct, fully unit-tested slot engine and endpoints for availability, time off and slots.

**Files:**
- `modules/scheduling/models.py` (`AvailabilityWindow`, `TimeOff`), `repository.py`, `domain.py`, `schemas.py`, `service.py`, `router.py`
- `core/timezone.py` (filled in)
- migration `availability_windows, time_off`
- `tests/unit/test_domain.py`, `tests/unit/test_timezone.py`, `tests/api/test_scheduling.py`

**Steps:**
1. **Write the unit tests for `domain.py` first** (superpowers TDD fits here), then implement until green.
2. `domain.py` exactly as in §6: `TimeRange`, `SlotRejection`, `ScheduleRules`, `ProviderDay`, `check_start`, `compute_slots`.
3. `timezone.py`: `local_day_bounds`, `windows_for_date`, `to_business_tz`, `local_today(now, tz)`.
4. Availability PUT: validate (grid, `start < end`, no overlap within a weekday, at most 6 windows per day), then delete and insert under the provider lock. (The booking conflict check comes in Phase 4.)
5. Time off: POST (`ends_at > now`, ≤ 365 days) and DELETE under the provider lock. (The booking conflict check comes in Phase 4.)
6. Slots endpoint: pre-checks (§6), then build `ProviderDay` from the repositories, then `compute_slots`, then serialize in the business timezone.

**Unit tests (`test_domain.py`), each a small named case:**
- 60-min service, window 09–13, 14–18 → 09:00, 09:15 … 12:00, 14:00 … 17:00; none starting 12:15–13:45
- window end exactly fits (17:00–18:00 included; 17:15 excluded)
- 15-min buffer: a booking 10:00–11:00 blocks until 11:15, so a new start at 11:00 is rejected and 11:15 is allowed
- buffer spilling past closing is allowed (17:00–18:00 + buffer)
- back-to-back without buffer allowed (half-open)
- partial overlap rejected (10:30 vs 10:00–11:00)
- time off 12:00–15:00 removes the overlapping slots, with reason `PROVIDER_UNAVAILABLE`
- `now` = 09:20 with 60 min notice → first slot 10:30
- date > today + 60 → `TOO_FAR`; start 09:10 → `OFF_GRID`
- empty windows → `[]`
- rejection order: off-grid **and** taken → `OFF_GRID` reported first
- timezone: `now` = 2030-01-07 20:00 UTC is already 01:00 on the 8th in Tashkent, so "today" = the 8th

**API tests:**
- availability PUT: overlap → 422 `INVALID_SCHEDULE`; 09:10 → 422; public GET works
- time off in the past → 422
- slots: inactive provider → 404; service not offered → 422 `SERVICE_NOT_OFFERED`; past date → 422 `DATE_OUT_OF_RANGE`; Sunday → `[]`
- response datetimes end with `+05:00`

**Done when:** `test_domain.py` covers every rejection, with 100% coverage of `domain.py`. The Phase 2 → 3 "done when" example from v3 (Monday lunch break) passes as an API test.

**Commits:**
- `test(scheduling): slot engine specification`
- `feat(scheduling): pure slot engine and timezone helpers`
- `feat(scheduling): weekly availability and time off management`
- `feat(scheduling): available slots endpoint`

---

### Phase 4: Bookings creation and concurrency

**Goal:** booking creation that is correct under concurrency, plus the schedule conflict checks that depend on bookings.

**Files:**
- `modules/bookings/models.py` (`Booking`, `BookingEvent`), `repository.py`, `schemas.py`, `policies.py` (only `allowed_actions` for now), `service.py` (`create`), `router.py` (POST, GET by id)
- migration `bookings, booking_events, btree_gist, exclusion constraints` (hand-written `op.execute`, with a matching `downgrade`)
- `core/errors.py`: add the two exclusion constraint mappings
- `modules/scheduling/service.py` and `modules/providers/service.py`: `SCHEDULE_CONFLICT`, `PROVIDER_HAS_BOOKINGS`
- `tests/api/test_bookings_create.py`, `tests/concurrency/test_race.py`

**Steps:**
1. Migration first; verify in `psql`: `\d bookings` shows both `EXCLUDE` constraints.
2. Repositories:
   - `UserRepository.lock(id)`
   - `BookingRepository.active_between(provider_id, range)`
   - `count_active_future(client_id, now)`
   - `client_overlap(client_id, range)`
   - `add`, `add_event`
   - `future_active_for_provider(provider_id, now)`
3. `BookingService.create`: exactly the 8 steps in §5; build the `ProviderDay` with the same helper the slots endpoint uses (extract `ScheduleReader` in `scheduling/service.py` or a shared function in `scheduling/repository.py`, so both reuse it).
4. Map `SlotRejection` to `AppError`: `TAKEN` → 409, the rest → 422.
5. Conflict checks:
   - availability PUT: future active bookings whose appointment range isn't contained in any new window of their local weekday → 409 with ids
   - time off: overlapping active bookings (blocked range) → 409 with ids
   - provider deactivate (DELETE, and PATCH `is_active=false`): any future active booking → 409
6. `GET /bookings/{id}` with the owner/admin scope (404 otherwise).

**Tests (create):**
- happy path: 201, status pending, price copied, `ends_at`/`blocked_until` correct, one event row
- `ends_at` or `price` in the body → 422 (`extra="forbid"`)
- naive datetime → 422
- every `SlotRejection` → its code
- inactive provider/service → 404; not offered → 422
- `CLIENT_OVERLAP`, `ACTIVE_LIMIT_REACHED`
- another client's booking → 404; admin can read it
- service price changed after booking → booking price unchanged
- schedule conflicts:
  - availability change that orphans a booking → 409 with the correct id
  - time off over a booking → 409
  - deactivate a provider with bookings → 409

**Race tests:** all 7 from §10.

**Done when:** race tests pass 20 times in a row (`for i in $(seq 20); do uv run pytest tests/concurrency -q || break; done`), so they are proven not flaky. `psql` shows the constraints.

**Commits:**
- `feat(bookings): bookings and events tables with exclusion constraints`
- `feat(bookings): create booking with locks, slot validation and client limits`
- `feat(scheduling): reject schedule changes that would orphan bookings`
- `test(bookings): concurrency tests for double booking and client limits`

---

### Phase 5: Lifecycle, lists, admin, meta, seed

**Goal:** the complete backend feature set.

**Files:**
- `bookings/policies.py` (full), `bookings/service.py` (`cancel`, `confirm`, `complete`, `list`), `bookings/router.py`
- `admin/*` (stats)
- `system/router.py` (`/meta`)
- `scripts/seed.py`, `scripts/export_openapi.py`
- tests: `test_policies.py`, `test_bookings_lifecycle.py`, `test_bookings_list.py`, `test_admin.py`

**Steps:**
1. `policies.py`: `Action` enum; `allowed_actions(booking, actor, now, cancel_cutoff) -> frozenset[Action]`; `ensure_allowed(...)` raising the precise code (`CANCEL_TOO_LATE` or `TOO_EARLY_TO_COMPLETE` when the status allows the action but time doesn't).
2. Transitions: `BookingRepository.lock(id)` (FOR UPDATE), then `ensure_allowed`, update status (plus `cancelled_at` and reason), `add_event`, commit.
3. List: client scope vs admin filters, pagination, `selectinload`, stable ordering.
4. Every `BookingOut` includes `allowed_actions` for the requesting user.
5. Stats: one grouped query per metric; the date range is local dates converted to UTC bounds.
6. `/meta` from `Settings`.
7. Seed:
   - admin + 2 clients
   - 4 services (with and without buffer)
   - 3 providers with different weekly schedules, including a lunch break
   - one time off next week
   - 8 bookings in mixed statuses, all relative to `now`
   - `--reset` truncates first
   - prints the demo logins
8. `export_openapi.py`: writes `frontend/openapi.json` from `create_app().openapi()`.

**Tests:**
- `test_policies.py`: the full matrix (status × actor × time) as a parametrized table
- lifecycle:
  - client cancels 3h before (ok); 1h before → `CANCEL_TOO_LATE`
  - admin cancels anytime
  - confirm pending; confirm confirmed → `INVALID_TRANSITION`
  - complete before `ends_at` → `TOO_EARLY_TO_COMPLETE`
  - any action on cancelled/completed → `INVALID_TRANSITION`
  - client confirm → 403
  - a cancelled slot becomes bookable again
  - events recorded with the actor
- list:
  - client never sees others
  - upcoming/history split at `now`
  - pagination totals
  - admin filters, `needs_action`
  - naive `from` → 422
- admin stats numbers match seeded fixtures
- meta values match settings

**Done when:** tests green; `make seed` on an empty DB prints logins that work in `/api/docs`; coverage of `policies.py` is 100%.

**Commits:**
- `feat(bookings): status transitions with policy and audit events`
- `feat(bookings): booking history with filters and pagination`
- `feat(admin): booking statistics endpoint`
- `feat(api): meta endpoint exposing booking policy`
- `feat: demo seed script`

---

### Phase 6: Frontend

**Goal:** a clean, accessible SPA covering tiers 1 and 2, with types generated from the API.

**Tools:** `frontend-design` skill for the visual direction (restrained: one accent, no gradients); the browser pane for checking each page; Mantine docs.

**Steps:**
1. `npm create vite@latest frontend -- --template react-ts`. Add Mantine v8 (`core`, `hooks`, `dates`, `form`, `notifications`), dayjs, TanStack Query, React Router, openapi-fetch, openapi-typescript (dev).
2. `vite.config.ts` proxy `/api` → `http://localhost:8000`. Script `gen:api`: `openapi-typescript openapi.json -o src/shared/api/schema.d.ts`.
3. The `shared/` layer: client, errors map, queryClient (no retry on 4xx; 401 clears auth), datetime and money helpers, `useMeta`, UI primitives.
4. Auth: `AuthProvider` from the `/auth/me` query (401 → logged out), login/register pages with `@mantine/form`, server field errors from `details.fields`, `RequireAuth`/`RequireAdmin`, `?next=` redirect.
5. Booking wizard (§9), URL-param state, slot grid, confirm, 409 handling.
6. My bookings: tabs, list, cancel via `allowed_actions`.
7. Admin bookings: stats cards, filters, table, action buttons, events timeline.
8. Not-found page, page titles, favicon, `index.html` title "Booking".
9. CI frontend job.

**Checks (in the browser pane, not assumed):**
- Register → book a slot → it appears in Upcoming → cancel → it moves to History, and the slot is free again.
- Two tabs, same slot: the second gets the toast and the slot grid refreshes.
- Admin: confirm, then complete on a past booking (use seed data).
- Mobile width 375px: no horizontal scroll; the wizard is usable.
- Keyboard only: can complete a booking.
- Times shown with "Tashkent time". A booking at 23:30 local shows the right date.

**Done when:** all checks pass; `npm run lint && npx tsc --noEmit && npm run build` is clean; CI green.

**Commits:**
- `feat(web): scaffold with Mantine, query client and generated API types`
- `feat(web): authentication pages and route guards`
- `feat(web): booking wizard with live slots`
- `feat(web): my bookings with cancellation`
- `feat(web): admin bookings dashboard`
- `ci: frontend lint, type check and build`

Tier 3, only if time allows:
- `feat(web): admin services and providers management`
- `test(web): end-to-end booking flow with Playwright`
- `feat(bookings): calendar export (.ics)`

---

### Phase 7: Ship

**Goal:** anyone can run it with one command; it's live; the docs explain every decision.

**Steps:**
1. Backend `Dockerfile`: `python:3.12-slim`, uv install from the lockfile, non-root user, `HEALTHCHECK`.
2. Frontend `Dockerfile`: multi-stage node → nginx; `nginx.conf` from §11.
3. `compose.yaml`: db + api + web as in §11. Test from a **fresh clone** in `/tmp`: `docker compose up -d --build`, then `docker compose exec api python -m scripts.seed --reset`, then open `localhost:8081`.
4. Run `/security-review` and fix its findings. Then run through CLAUDE_RULES 2.6 item by item, reporting each as pass, fail, or n/a.
5. Docs: `README.md` (§16), `docs/ARCHITECTURE.md` (mermaid ER + layer diagram + decision table), `docs/EDGE_CASES.md` (the §13 matrix with test names), `docs/AI_LOG.md` (finalized).
6. Deploy (§11, you run the server commands). Put the demo URL and demo logins in the README.

**Done when:** the fresh-clone run works; `https://booking.khayrullo.uz/api/v1/health` returns ok; the README's steps work exactly as written.

**Commits:**
- `build: Dockerfiles, nginx config with rate limits and security headers`
- `build: full compose stack`
- `docs: README, architecture, edge cases, AI usage`
- `chore: production deployment notes`

---

### Phase 8: Final review and interview prep

1. `/code-review` on the whole diff since Phase 0; fix what's real.
2. Run `/simplify` once; accept only the changes you can explain.
3. Read every file yourself. For each file, explain it out loud in one sentence. If you can't, rewrite or ask.
4. Go through §15 without notes.
5. Check the git log shows one feature per commit, messages in conventional style, no "wip" or "fix fix".
6. Submit the GitHub URL + demo URL.

---

## 13. Edge case matrix

| # | Case | Handled in | Result | Test |
|---|---|---|---|---|
| 1 | Ten users book the same slot at once | user/provider locks + `ex_bookings_provider_overlap` | 1× 201, 9× 409 `SLOT_TAKEN` | `test_same_slot_ten_clients` |
| 2 | Partial overlap (10:30 vs 10:00–11:00) | range overlap | 409 | `test_partial_overlap_parallel`, `test_domain::partial_overlap` |
| 3 | Back-to-back 10–11, 11–12 | half-open ranges | 201 | `test_domain::back_to_back` |
| 4 | Buffer: 11:00 after 10–11 + 15 min | blocked range | 409 | `test_domain::buffer_blocks_next` |
| 5 | Buffer past closing time | appointment-only window fit | allowed | `test_domain::buffer_after_close` |
| 6 | Start in the past or < 60 min | `check_start` | 422 `SLOT_TOO_SOON` | `test_domain::min_notice` |
| 7 | > 60 days ahead | `check_start` | 422 `SLOT_TOO_FAR` | `test_domain::too_far` |
| 8 | 10:07 start | grid check | 422 `SLOT_OFF_GRID` | `test_domain::off_grid` |
| 9 | During lunch / outside hours | window containment | 422 `OUTSIDE_WORKING_HOURS` | `test_domain::lunch_break` |
| 10 | Provider on time off | time off overlap | 422 `PROVIDER_UNAVAILABLE` | `test_domain::time_off` |
| 11 | Day off (no windows) | empty windows | slots `[]` | `test_scheduling::day_off_empty` |
| 12 | Provider doesn't offer service | catalog check | 422 `SERVICE_NOT_OFFERED` | `test_bookings_create::not_offered` |
| 13 | Inactive provider/service | `get_active` | 404 | `test_bookings_create::inactive` |
| 14 | Client sends `price`/`ends_at` | `extra="forbid"` | 422 | `test_bookings_create::extra_fields` |
| 15 | Naive datetime | `AwareDatetime` | 422 | `test_bookings_create::naive_datetime` |
| 16 | Client double-books self across providers | client lock + `ex_bookings_client_overlap` | 409 `CLIENT_OVERLAP` | `test_same_client_two_providers` |
| 17 | Client exceeds active limit (also in parallel) | user lock + count | 409 `ACTIVE_LIMIT_REACHED` | `test_active_limit_parallel` |
| 18 | Service price changes later | price snapshot | old price kept | `test_bookings_create::price_snapshot` |
| 19 | Service duration changes later | stored `ends_at` | booking unchanged | `test_bookings_create::duration_snapshot` |
| 20 | Availability change orphans a booking | conflict check under lock | 409 `SCHEDULE_CONFLICT` + ids | `test_scheduling::availability_conflict` |
| 21 | Time off over existing booking | conflict check under lock | 409 `SCHEDULE_CONFLICT` | `test_scheduling::time_off_conflict` |
| 22 | Booking and time off at the same moment | provider lock | exactly one wins | `test_booking_vs_time_off_parallel` |
| 23 | Deactivate provider with future bookings | check | 409 `PROVIDER_HAS_BOOKINGS` | `test_providers::deactivate_with_bookings` |
| 24 | Client cancels < 2h before | policy | 409 `CANCEL_TOO_LATE` | `test_bookings_lifecycle::cancel_too_late` |
| 25 | Complete before end | policy | 409 `TOO_EARLY_TO_COMPLETE` | `test_bookings_lifecycle::complete_early` |
| 26 | Any action on a terminal booking | policy | 409 `INVALID_TRANSITION` | `test_policies` matrix |
| 27 | Client tries to confirm | role | 403 | `test_bookings_lifecycle::client_confirm_forbidden` |
| 28 | Cancel and confirm at the same moment | booking row lock | consistent final state | `test_cancel_vs_confirm_parallel` |
| 29 | Cancelled slot rebooked | partial constraint | 201 | `test_bookings_lifecycle::rebook_after_cancel` |
| 30 | Read another client's booking | scoped query | 404 | `test_bookings_create::other_client_404` |
| 31 | Overlapping availability windows | validation | 422 `INVALID_SCHEDULE` | `test_scheduling::overlapping_windows` |
| 32 | Late evening UTC = next day in Tashkent | business-tz "today" | correct day | `test_timezone::today_rolls_over` |
| 33 | Duplicate email, different case | lowercase + unique | 409 `EMAIL_TAKEN` | `test_auth::duplicate_email_case` |
| 34 | Unknown email vs wrong password | same response + dummy hash | identical 401 | `test_auth::no_enumeration` |
| 35 | Deactivated user with a valid token | DB lookup per request | 401 | `test_auth::deactivated_user` |
| 36 | Forged token (`alg: none`) | pinned algorithm | 401 | `test_auth::alg_none` |
| 37 | Brute-force login | nginx `limit_req` | 429 `RATE_LIMITED` | manual check with curl, documented |
| 38 | Double-click Book | button disabled + client overlap | one booking | frontend check + #16 |
| 39 | Stale slot list in the browser | 409 → toast + refetch | user picks again | Phase 6 check |
| 40 | Pending never confirmed | admin "needs action" filter; late confirm allowed | no stuck booking | `test_bookings_list::needs_action` |

---

## 14. Claude Code workflow and tools

### Per phase

1. `/clear`, so each phase starts with a clean context.
2. **Plan mode** (Shift+Tab). Prompt:
   > Read `docs/PLAN.md` §12 Phase N and the sections it references, plus `CLAUDE.md`. List every file you will create or change and the order. Don't write code yet.
3. Approve the list, leave plan mode, and say "Implement Phase N."
4. Claude runs `make lint test` and reports the real output.
5. **You read every changed file.** Ask "why" about anything unclear. Log real corrections in `docs/AI_LOG.md`.
6. Run `/code-review` on the phase diff and fix the real findings.
7. Commit using the phase's commit messages, one logical change per commit, and push.

### Tools mapped to phases

| Tool | Where | Why |
|---|---|---|
| Plan mode | start of every phase | Agree on files before code |
| superpowers (installed) | Phases 3 and 5: TDD for `domain.py` and `policies.py`; systematic debugging when a race test flakes | Tests first for the parts that must be correct |
| `/code-review` (built in) | end of every phase | Catches bugs while the phase is fresh |
| `/security-review` (built in) | Phase 7 | Required by CLAUDE_RULES 2.6 before shipping |
| `/simplify` (built in) | Phase 8, once | Removes accidental complexity |
| frontend-design (installed) | Phase 6 | Visual direction that doesn't look templated |
| Browser pane | Phase 6 checks, Phase 7 demo check | Verify for real; never assume |
| ponytail (installed) | Always on | Keeps code small; `CLAUDE.md` states that the layers are required, so it doesn't strip the architecture |
| caveman (installed) | Chat only | Say "stop caveman" before writing README/docs, which need full prose |

### `.claude/settings.json` in the repo

```json
{
  "permissions": {
    "allow": [
      "Bash(make:*)",
      "Bash(uv run:*)",
      "Bash(uv sync:*)",
      "Bash(docker compose ps:*)",
      "Bash(docker compose logs:*)",
      "Bash(docker compose up -d db:*)",
      "Bash(npm run:*)",
      "Bash(npx tsc:*)",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)"
    ]
  }
}
```

Commits, pushes, `docker compose down` and anything on the server stay manual (your rule: never kill or restart services unasked).

### AI_LOG format (`docs/AI_LOG.md`)

| Phase | What I asked | What AI produced | What I checked or changed | Why |
|---|---|---|---|---|

Only real entries. The README's AI section is written from this table.

---

## 15. Must-understand list

Explain each without notes:

1. What `EXCLUDE USING gist (provider_id WITH =, tstzrange(...) WITH &&) WHERE (...)` does, word by word, and why `btree_gist` is needed.
2. Why `blocked_until` is a stored column (IMMUTABLE index expressions).
3. Why locking the provider row works and locking booking rows doesn't (no rows to lock when the slot is empty, the phantom problem).
4. Why READ COMMITTED makes "lock, then read" correct.
5. The lock order and why it prevents deadlocks.
6. Why constraints *and* locks: which rules each protects.
7. `check_start` order of checks, and why `compute_slots` reuses it.
8. The half-open interval `[start, end)` and the back-to-back example.
9. Where UTC ↔ Tashkent conversion happens and the "today" bug it prevents.
10. JWT flow: login, then cookie or Bearer, then `get_current_user`, then a DB load. Why the role isn't trusted from the token.
11. Why SameSite=Lax + JSON-only prevents CSRF here.
12. Why `allowed_actions` comes from the server.
13. How FastAPI `Depends` builds `BookingService` per request, and how tests override the clock.
14. Why services commit instead of `with session.begin()` (autobegin).
15. How the race test works (Barrier, separate sessions) and what it proves.
16. Why tests use migrations and TRUNCATE instead of `create_all` and rollback.
17. Why action endpoints instead of `PATCH status`.
18. Why 409 vs 422.
19. What you'd add next: notifications, provider accounts, multi-location, a waitlist.

---

## 16. README outline

1. **Booking System**: two lines, CI badge, demo URL, demo logins (from seed)
2. **Features**: client flow, admin flow, bonuses done
3. **Quick start**: `docker compose up -d --build`, then seed, then URLs. Local dev without Docker: `make` targets
4. **Architecture**: layer diagram, module map, dependency rules, decision table (FastAPI, SQLAlchemy sync, computed slots, locks + constraints, cookie auth)
5. **Database**: mermaid ER, constraints explained
6. **Business rules**: status machine, policies (from `/meta`), time rules
7. **Edge cases**: link to `docs/EDGE_CASES.md` with the top 10 inline
8. **API**: `/api/docs` link, a curl walkthrough (register → login → slots → book → cancel)
9. **Testing**: how to run, what each layer covers, the real coverage number
10. **Security**: checklist results (CLAUDE_RULES 2.6)
11. **AI usage**: tools, how each phase was driven, real corrections from `AI_LOG.md`
12. **Limitations and next steps**: DST handling, overnight shifts, email/Telegram notifications, provider self-service, stateless logout
