# Testing guide

The project has three testing layers:

1. **Automated backend tests** cover domain rules, API behavior, database
   constraints, permissions, and real-thread concurrency. Run them with
   `make test`.
2. **Automated quality checks** cover formatting, linting, strict typing,
   frontend compilation, and the production frontend build. Run them with
   `make lint`. CI runs the same checks plus migrations, coverage, dependency
   auditing, and the frontend audit.
3. **Environment smoke checks** verify that a running stack exposes the
   health, policy, and public catalog endpoints. Run `make smoke`, or set
   `BASE_URL` for a deployed environment:

   ```bash
   BASE_URL=https://booking-api.veraflow.uz make smoke
   ```

## Local verification

For a full local stack:

```bash
make env
make up
make demo
make smoke
```

For split development, start the database and API with `make dev-db`,
`make migrate`, and `make api`, then start the frontend with `make web`.
The frontend can use the local API or the configured remote proxy in
`frontend/.env.local`.

## Manual browser checklist

Run this checklist against a fresh demo database and at a viewport of 375px
wide and 1440px wide. Record failures with the route, browser, viewport,
steps, expected result, and actual result.

### Client flow

- [ ] Open the booking page while logged out; services load or show a useful
      retry state.
- [ ] Select each service; the selected state is visible and the next step
      loads the matching providers.
- [ ] Select a provider; choose a working day and an available time.
- [ ] Confirm a booking with and without notes; the success message and
      upcoming booking appear.
- [ ] Open another browser tab, take the selected slot in one tab, and submit
      it in the other; the second tab receives a conflict and refreshed slots.
- [ ] Cancel an upcoming booking before the cutoff; it moves to history and
      the slot becomes available again.
- [ ] Attempt to cancel inside the cutoff; the action is hidden or the
      server returns the documented conflict.
- [ ] Refresh at every booking step; service, provider, date, and time remain
      encoded in the URL where applicable.

### Authentication and accessibility

- [ ] Register, log out, and log back in.
- [ ] Submit invalid login and registration fields; errors are attached to
      the correct fields without exposing account existence.
- [ ] Complete the client flow using only the keyboard.
- [ ] Confirm the skip link, visible focus ring, labels, and button names.
- [ ] Verify there is no horizontal scroll at 375px.

### Admin flow

- [ ] Log in as admin and confirm the dashboard shows stats and bookings.
- [ ] Filter bookings by status, provider, and date.
- [ ] Confirm a pending booking.
- [ ] Complete a confirmed booking whose end time has passed.
- [ ] Cancel a pending or confirmed booking and verify its event appears.
- [ ] Confirm that client-only routes and actions are not available to admins.

### Deployment

- [ ] Run `BASE_URL=https://booking-api.veraflow.uz make smoke`.
- [ ] Verify HTTPS, the API health response, login, and one complete booking.
- [ ] Verify the deployed frontend build matches the reviewed commit.
