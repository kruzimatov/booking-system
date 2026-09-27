# Roadmap

Version 1 is a booking system for **one** small business, which is what the task asks for. This page describes how it would grow into a platform for many businesses, in the order that avoids rewriting work. The detailed working notes are in [PLAN.md](PLAN.md) (section "V2 roadmap").

## Principle

**Businesses first, then operations, then integrations.** Every later feature (payments, notifications, reports) belongs to a business. Adding the business boundary after those features would mean revisiting every query, so it comes first.

## Where version 1 already stands

| Area | Already in version 1 |
|---|---|
| Correctness | Double booking impossible at database level (exclusion constraints), row locks, concurrency tests |
| Booking lifecycle | pending, confirmed, cancelled, completed; cancellation reasons; audit events for every change |
| Rules | Minimum notice, booking horizon, cancellation cutoff, per-client limit (configurable per deployment) |
| Time | Business timezone, UTC storage, business-day logic |
| Admin | Bookings dashboard with filters, stats, confirm / complete / cancel; services, specialists, hours and time off through the API |
| Calendar | `.ics` download per booking (works with Google, Apple and Outlook calendars) |
| Quality | 146 backend tests, browser end-to-end tests, CI, Docker, API documentation |

The slot engine already receives its rules as a parameter instead of reading global settings, so per-business rules need no change to the engine itself.

## Phases

### 1. Businesses and memberships (the foundation)

- `organizations`, and `memberships` linking users to organizations with a role: owner, manager, receptionist, provider, client. Memberships replace today's single global `users.role`, which every admin check currently relies on, so the migration moves those checks in one step.
- `organization_id` on services, providers, availability, time off and bookings. The existing demo data moves into one organization through a migration.
- **Isolation enforced by the database, not only by queries.** Foreign keys include the organization (a booking references "provider P *of organization O*"), so a booking can never point at another business's provider or service. PostgreSQL row-level security is the second option. A forgotten `WHERE organization_id = ...` is the most likely serious bug in a multi-business system, and this makes it impossible rather than unlikely.
- Per-business settings move from environment variables into the organization: name, timezone, currency, notice, horizon, cancellation cutoff, client limit.
- Tests proving that a user of one business can never read or change another business's data.
- Public URLs per business, for example `/b/{business-slug}`, decided here because routing and branding depend on it.

### 2. Business workspace

Management screens for what is API-only today: services, specialists, weekly hours, time off, team members and roles, business settings. A day and week calendar with specialist and status filters, and quick booking for walk-ins and phone calls.

### 3. Booking lifecycle

- **Rescheduling** as one operation that keeps the booking's history (today a client must cancel and book again).
- **No-show** status for clients who did not come.
- Separate notes for the client and for the business.

### 4. Notifications (outbox and worker)

- An **outbox table**: the booking change and "notify about it" are saved in the same transaction; a background worker sends the message and retries on failure. No email for a booking that was rolled back, and no lost email for a booking that was saved.
- Events: created, confirmed, cancelled, rescheduled, reminder before the appointment.
- One channel first (email), then Telegram or SMS behind the same interface.
- The existing `.ics` export attached to confirmation emails.

### 5. Waitlist

Clients join a waitlist for a full day and are told when a time frees up. This needs the notifications from phase 4, so it comes after them.

### 6. Payments

- Payment status is a **separate** state machine from booking status: unpaid, pending, paid, failed, refunded.
- Only verified webhooks from the payment provider mark a booking as paid; the browser never does.
- Idempotency keys, refunds tied to the cancellation policy, one provider and one currency first.

### 7. Client experience

Rebook a previous appointment, favourite specialists, reminders, Uzbek and Russian translations, business branding on the public booking page.

### 8. Reports and operations

Business reports (bookings, revenue, cancellation and no-show rates, specialist utilisation, busy hours) in their own query module; request IDs, error tracking, a view of failed notifications, and the deployed version on the health endpoint.

## Deliberately not planned yet

Microservices, event sourcing, a plugin system, recurring appointments and two-way calendar sync. Each is useful only once the phases above exist, and each adds lasting complexity.
