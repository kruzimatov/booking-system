import { type APIRequestContext, expect, test } from "@playwright/test";

import {
  ACCOUNTS,
  apiAs,
  bookingUrl,
  cancelAsAdmin,
  findFreeSlot,
  logInThroughUi,
  useSession,
} from "./support";

let admin: APIRequestContext;
let shahzod: APIRequestContext;
let madina: APIRequestContext;

test.beforeAll(async ({ baseURL }) => {
  admin = await apiAs(baseURL!, ACCOUNTS.admin);
  shahzod = await apiAs(baseURL!, ACCOUNTS.shahzod);
  madina = await apiAs(baseURL!, ACCOUNTS.madina);
});

test.afterAll(async () => {
  await Promise.all([admin.dispose(), shahzod.dispose(), madina.dispose()]);
});

test("a client books a free time, sees it in My bookings and cancels it", async ({ page }) => {
  const slot = await findFreeSlot(admin, "Classic haircut", "Temurbek Xolmatov");

  await logInThroughUi(page, ACCOUNTS.madina);
  await page.goto(bookingUrl(slot));
  const times = page.getByRole("group", { name: "Free start times" });
  await expect(times).toBeVisible();
  await times.getByRole("button").first().click();

  await expect(page.getByText("with Temurbek Xolmatov")).toBeVisible();
  await page.getByLabel("Notes for the specialist").fill("Booked by the end-to-end test");
  const [created] = await Promise.all([
    page.waitForResponse((response) => response.url().endsWith("/api/v1/bookings") && response.request().method() === "POST"),
    page.getByRole("button", { name: "Book appointment" }).click(),
  ]);
  expect(created.status()).toBe(201);
  const bookingId: string = (await created.json()).id;

  await expect(page).toHaveURL(/\/bookings$/);
  const card = page.locator(`[data-booking-id="${bookingId}"]`);
  await expect(card).toContainText("Classic haircut");
  await expect(card).toContainText("pending");

  // Calendar export: the link downloads a valid iCalendar file for this booking.
  const calendarLink = card.getByRole("link", { name: "Add to calendar" });
  const calendar = await page.request.get((await calendarLink.getAttribute("href"))!);
  expect(calendar.headers()["content-type"]).toContain("text/calendar");
  const ics = await calendar.text();
  expect(ics).toContain("BEGIN:VCALENDAR");
  expect(ics).toContain(`UID:${bookingId}@booking-system`);

  await card.getByRole("button", { name: "Cancel" }).click();
  await page.getByRole("button", { name: "Cancel booking" }).click();
  await expect(page.getByText("Your booking was cancelled.")).toBeVisible();

  // The cancelled time is free again for everyone.
  const again = await findFreeSlot(admin, "Classic haircut", "Temurbek Xolmatov");
  expect(again.startsAt).toBe(slot.startsAt);
});

test("a slot taken by someone else while confirming shows a clear message", async ({ page }) => {
  const slot = await findFreeSlot(admin, "Skin fade", "Farrux Ergashev");

  await useSession(page, madina);
  await page.goto(bookingUrl(slot, true));
  await expect(page.getByRole("button", { name: "Book appointment" })).toBeVisible();

  // Another client takes the same time while this user is still on the confirm step.
  const taken = await shahzod.post("/api/v1/bookings", {
    data: { provider_id: slot.providerId, service_id: slot.serviceId, starts_at: slot.startsAt },
  });
  expect(taken.status()).toBe(201);
  const takenId: string = (await taken.json()).id;

  try {
    await page.getByRole("button", { name: "Book appointment" }).click();
    await expect(page.getByText("This time is no longer free")).toBeVisible();
    // Back on the time step, and the lost time is no longer offered.
    const times = page.getByRole("group", { name: "Free start times" });
    await expect(times).toBeVisible();
    const lostLabel = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Tashkent",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(slot.startsAt));
    await expect(times.getByRole("button", { name: lostLabel, exact: true })).toHaveCount(0);
  } finally {
    await cancelAsAdmin(admin, takenId);
  }
});

test("an admin confirms a pending booking from the dashboard", async ({ page }) => {
  const slot = await findFreeSlot(admin, "Kids haircut", "Sevara Mahmudova");
  const created = await shahzod.post("/api/v1/bookings", {
    data: { provider_id: slot.providerId, service_id: slot.serviceId, starts_at: slot.startsAt },
  });
  expect(created.status()).toBe(201);
  const bookingId: string = (await created.json()).id;

  try {
    await useSession(page, admin);
    await page.goto("/admin");
    const row = page.locator(`tr[data-booking-id="${bookingId}"]`);
    await expect(row).toContainText("Shahzod Tursunov");
    await expect(row).toContainText("pending");

    await row.getByRole("button", { name: "Confirm" }).click();
    await expect(page.getByText("Booking confirmed.")).toBeVisible();

    const stored = await (await admin.get(`/api/v1/admin/bookings/${bookingId}`)).json();
    expect(stored.status).toBe("confirmed");
    expect(stored.events.map((event: { to_status: string }) => event.to_status)).toEqual([
      "pending",
      "confirmed",
    ]);
  } finally {
    await cancelAsAdmin(admin, bookingId);
  }
});
