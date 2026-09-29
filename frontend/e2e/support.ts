import { type APIRequestContext, type Page, expect, request } from "@playwright/test";

// Login is rate-limited (10 per minute per IP), so each account logs in once per run
// and the session cookie is reused; only the first test goes through the login form.

// Local demo accounts from backend/scripts/seed.py (refused by the seed on HTTPS deployments).
export const ACCOUNTS = {
  admin: { email: "admin@veraflow.uz", password: process.env.E2E_ADMIN_PASSWORD ?? "demo-admin-password" },
  madina: { email: "lazizbek1234@gmail.com", password: process.env.E2E_CLIENT_PASSWORD ?? "demo-client-password" },
  shahzod: { email: "shahzod@example.com", password: process.env.E2E_CLIENT_PASSWORD ?? "demo-client-password" },
} as const;

type Account = (typeof ACCOUNTS)[keyof typeof ACCOUNTS];

export interface Slot {
  serviceId: string;
  providerId: string;
  day: string;
  startsAt: string;
}

/** An API client logged in as the given account (its own cookie jar). */
export async function apiAs(baseURL: string, account: Account): Promise<APIRequestContext> {
  const api = await request.newContext({ baseURL });
  const response = await api.post("/api/v1/auth/login", { data: account });
  expect(response.status(), `login as ${account.email}`).toBe(200);
  return api;
}

/** The first free start time from tomorrow on, found through the public API. */
export async function findFreeSlot(
  api: APIRequestContext,
  serviceName: string,
  providerName: string,
): Promise<Slot> {
  const services: { id: string; name: string }[] = await (await api.get("/api/v1/services")).json();
  const service = services.find((item) => item.name === serviceName);
  expect(service, `service ${serviceName}`).toBeDefined();
  const providers: { id: string; full_name: string }[] = await (
    await api.get(`/api/v1/providers?service_id=${service!.id}`)
  ).json();
  const provider = providers.find((item) => item.full_name === providerName);
  expect(provider, `provider ${providerName}`).toBeDefined();

  for (let offset = 1; offset <= 21; offset++) {
    const day = businessDate(offset);
    const response = await api.get(
      `/api/v1/providers/${provider!.id}/slots?service_id=${service!.id}&date=${day}`,
    );
    const slots: { starts_at: string }[] = await response.json();
    if (slots.length > 0) {
      return { serviceId: service!.id, providerId: provider!.id, day, startsAt: slots[0].starts_at };
    }
  }
  throw new Error(`No free time for ${serviceName} with ${providerName} in the next 3 weeks`);
}

/** YYYY-MM-DD in the business timezone, `offset` days from today. */
export function businessDate(offset: number): string {
  const moment = new Date(Date.now() + offset * 86_400_000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tashkent" }).format(moment);
}

/** The wizard keeps its state in the URL, so a test can open any step directly. */
export function bookingUrl(slot: Slot, withStart = false): string {
  const params = new URLSearchParams({ service: slot.serviceId, provider: slot.providerId, date: slot.day });
  if (withStart) params.set("start", slot.startsAt);
  return `/?${params.toString()}`;
}

export async function logInThroughUi(page: Page, account: Account): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(account.email);
  // The label reads "Password *" (required), and password inputs have no ARIA role.
  await page.locator('input[type="password"]').fill(account.password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

/** Cancels a booking as admin; used to leave the database as the test found it. */
export async function cancelAsAdmin(admin: APIRequestContext, bookingId: string): Promise<void> {
  const response = await admin.post(`/api/v1/admin/bookings/${bookingId}/cancel`, {
    data: { reason: "E2E cleanup" },
  });
  expect([200, 409]).toContain(response.status());
}

/** Opens the app in the page already logged in, reusing an API session's cookie. */
export async function useSession(page: Page, api: APIRequestContext): Promise<void> {
  await page.context().addCookies((await api.storageState()).cookies);
}
