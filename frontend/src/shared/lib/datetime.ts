import dayjs from "dayjs";
import timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";

dayjs.extend(utc);
dayjs.extend(timezone);

// All times are shown in the business's timezone (from GET /meta), not the browser's,
// because the appointment happens at the business. Dates sent to the API are plain
// YYYY-MM-DD strings, never Date.toISOString(), which would shift the day in UTC+5.

export function todayIn(tz: string): string {
  return dayjs().tz(tz).format("YYYY-MM-DD");
}

export function addDays(day: string, days: number): string {
  return dayjs(day).add(days, "day").format("YYYY-MM-DD");
}

/** Backend weekday for a YYYY-MM-DD date: 0 = Monday ... 6 = Sunday. */
export function weekdayOf(day: string): number {
  return (dayjs(day).day() + 6) % 7;
}

export function formatTime(iso: string, tz: string): string {
  return dayjs(iso).tz(tz).format("HH:mm");
}

export function formatDate(iso: string, tz: string): string {
  return dayjs(iso).tz(tz).format("ddd, D MMM YYYY");
}

export function formatDateTime(iso: string, tz: string): string {
  return dayjs(iso).tz(tz).format("ddd, D MMM YYYY, HH:mm");
}

export function formatDay(day: string): string {
  return dayjs(day).format("dddd, D MMMM");
}
