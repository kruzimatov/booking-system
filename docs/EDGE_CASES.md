# Edge cases

Every case below is handled in code and covered by a test (test files are under `backend/tests/`).

## Double booking and concurrency

| Case | What happens | Test |
|---|---|---|
| Ten clients book the same slot at the same moment | Exactly one booking succeeds; the other nine get `409 SLOT_TAKEN` | `concurrency/test_race.py::test_ten_clients_racing_for_one_slot` |
| Two requests overlap only partly (10:00 and 10:30 for 60 minutes) | One succeeds, one gets `SLOT_TAKEN` | `test_partially_overlapping_requests_in_parallel` |
| One client books two specialists at the same time, in parallel | One succeeds, one gets `CLIENT_OVERLAP` | `test_one_client_booking_two_providers_at_once` |
| A client at the booking limit sends two requests at once | The limit holds: one succeeds, one gets `ACTIVE_LIMIT_REACHED` | `test_active_limit_holds_under_parallel_requests` |
| A booking and a time-off entry for the same hour arrive together | Exactly one wins; the other is refused | `test_booking_and_time_off_for_the_same_hour` |
| A client cancels while an admin confirms | Applied one after the other; the final state matches the last event | `test_client_cancel_and_admin_confirm_at_the_same_moment` |
| An overlapping row is inserted directly, bypassing the app | PostgreSQL rejects it (exclusion violation) | `test_database_rejects_overlap_even_without_the_application` |
| A cancelled booking exists for a time | The time can be booked again | `test_cancelled_bookings_do_not_block_the_database_constraint`, `test_client_cancels_in_time_and_the_slot_is_free_again` |

## Choosing a time

| Case | What happens | Test |
|---|---|---|
| Back-to-back bookings (10:00 to 11:00, then 11:00 to 12:00) | Allowed: ranges are half-open | `unit/test_domain.py::test_back_to_back_bookings_are_allowed` |
| Partial overlap with an existing booking | Rejected as taken | `test_partial_overlap_is_taken` |
| Start inside another booking's cleanup buffer | Rejected as taken | `test_existing_buffer_blocks_the_next_start`, `test_taken_slot_and_buffer_are_blocked_for_others` |
| A booking's own buffer runs past closing time | Allowed; it may not run into the next booking | `test_own_buffer_may_run_past_closing_but_not_into_the_next_booking` |
| Lunch break (09:00 to 13:00 and 14:00 to 18:00) | No appointment spans the break; the last slot ends exactly at closing | `test_lunch_break_splits_the_day_and_last_slot_ends_at_closing` |
| Two touching windows (09:00 to 13:00 and 13:00 to 18:00) | Treated as one continuous day | `test_touching_windows_are_merged` |
| Start not on the 15-minute grid (10:10, or with seconds) | `422 SLOT_OFF_GRID`, checked first | `test_off_grid_starts_are_rejected_first` |
| Start in the past or less than 60 minutes ahead | `422 SLOT_TOO_SOON` | `test_minimum_notice_from_now`, `test_start_in_the_past_is_too_soon` |
| More than 60 days ahead | `422 SLOT_TOO_FAR` | `test_booking_window_ends_after_max_advance_days` |
| Outside working hours or during the break | `422 OUTSIDE_WORKING_HOURS` | `test_outside_working_hours_and_during_lunch` |
| Specialist on time off | Those times disappear; booking gets `PROVIDER_UNAVAILABLE` | `test_time_off_removes_overlapping_slots`, `test_time_off_removes_slots_and_deleting_it_restores_them` |
| A day the specialist does not work | An empty list, not an error | `test_day_off_returns_empty_list`, `test_day_without_windows_has_no_slots` |
| Same instant sent with a different offset (`05:00Z` vs `10:00+05:00`) | Recognized as the same slot | `test_same_instant_in_another_offset_is_the_same_slot` |
| Time without an offset (`2030-01-07T10:00`) | `422`: ambiguous times are refused | `test_naive_start_time_is_rejected` |
| Late evening: UTC is still "yesterday" when Tashkent is already "today" | The business date is used | `test_business_today_rolls_over_before_utc_midnight` |
| Slots requested for a past date or beyond the horizon | `422 DATE_OUT_OF_RANGE` | `test_dates_outside_the_booking_window_are_rejected` |
| Absurd years (`9999-12-31T23:45-12:00`), which would overflow date arithmetic | `422` before any calculation, for bookings, time off, slots and admin filters | `test_absurd_years_are_rejected_before_any_date_arithmetic`, `test_slots_reject_absurd_dates`, `test_date_filters_reject_absurd_years` |

## Data integrity

| Case | What happens | Test |
|---|---|---|
| Client sends `price`, `ends_at` or `status` | `422`: server-owned fields are rejected | `test_client_cannot_send_server_owned_fields` |
| Service price changes after booking | The booking keeps its original price | `test_price_is_a_snapshot` |
| Working hours changed so an upcoming booking falls outside them | `409 SCHEDULE_CONFLICT` with the booking IDs | `test_schedule_changes_cannot_orphan_bookings` |
| Time off added over an existing booking | `409 SCHEDULE_CONFLICT` | same test |
| Specialist deactivated (DELETE or PATCH) with upcoming bookings | `409 PROVIDER_HAS_BOOKINGS` | same test |
| Past bookings only | Schedule changes are allowed | `test_past_bookings_do_not_block_schedule_changes` |
| Inactive specialist or service, or a service the specialist does not offer | `404`, or `422 SERVICE_NOT_OFFERED` | `test_unknown_inactive_or_unoffered_resources`, `test_slots_require_an_active_provider_offering_the_service` |
| Duration off the grid inserted directly into the database | Rejected by a CHECK constraint | `test_database_rejects_duration_off_the_grid` |
| Overlapping or off-grid working hours | `422` | `test_availability_validation` |
| PATCH sets a required field to null | `422` | `test_patch_rejects_null_for_required_field` |

## Status rules

| Case | What happens | Test |
|---|---|---|
| Client cancels less than 2 hours before | `409 CANCEL_TOO_LATE`; the Cancel button is not offered | `test_client_cannot_cancel_inside_the_cutoff` |
| Admin completes before the appointment ended | `409 TOO_EARLY_TO_COMPLETE` | `test_admin_confirms_then_completes_after_the_end` |
| Any change to a cancelled or completed booking | `409 INVALID_TRANSITION` | `test_terminal_bookings_cannot_change` |
| Client tries to confirm, or acts on someone else's booking | `403`, or `404` for a foreign booking | `test_clients_cannot_use_admin_actions_or_touch_other_bookings` |
| The full matrix of action, status, role and time | Checked as a table | `unit/test_policies.py::test_transition_rules` |

## Accounts and access

| Case | What happens | Test |
|---|---|---|
| Same email in a different letter case | `409 EMAIL_TAKEN` | `test_register_rejects_duplicate_email_in_any_case` |
| `role: admin` sent at registration | `422`; everyone registers as a client | `test_register_rejects_role_field` |
| Wrong password vs unknown email | Identical responses | `test_login_failure_does_not_reveal_whether_email_exists` |
| User deactivated after logging in | The next request is refused | `test_me_rejects_user_deactivated_after_login` |
| Expired, unsigned or foreign token | `401` | `test_me_rejects_expired_token`, `test_me_rejects_unsigned_token`, `test_token_signed_with_another_secret_is_rejected` |
| Admin tries to book | `403` | `test_admins_cannot_book` |
| Client reads another client's booking | `404` (existence not revealed) | `test_booking_visibility` |
| Calendar file for another client's booking, or without login | `404`, or `401` | `test_client_downloads_a_calendar_file_for_own_booking_only` |
| Notes with commas, semicolons, new lines or long Cyrillic text in the calendar file | Escaped and folded per RFC 5545 without splitting characters | `unit/test_calendar.py` |
| Public views of specialists | Email and phone are never included | `test_admin_creates_provider_and_public_view_hides_contacts` |
| Unexpected server error | `500` with a generic message; no internal details | `test_unexpected_error_hides_internal_details` |
| A POST from another website or sibling subdomain, using the victim's cookie | `403 CROSS_ORIGIN_REQUEST` | `test_state_changing_requests_from_another_origin_are_rejected` |
| Stats requested with only an end date | Starts at the first day of that month | `test_stats_with_only_an_end_date_use_that_month` |

## Checked manually

| Case | Result |
|---|---|
| Login brute force through nginx | After 10 quick attempts, `429 RATE_LIMITED` in the standard error format |
| Many page loads from one shared IP | `/auth/me` is not under the strict login limit, so users behind mobile carrier NAT are not logged out |
| Login expires while the app is open | Any `401` marks the user as logged out; guarded pages go to the login page |
| A slot is taken while the user is on the confirm step | A message, fresh times, and the user stays on the time step (browser check) |
| Refresh or log in in the middle of booking | The selection is kept in the URL (browser check) |
| Phone-width screen (375px) | No horizontal scrolling (browser check) |
