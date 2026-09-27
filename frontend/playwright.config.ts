import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against the full stack (nginx, API, PostgreSQL) started with
// `make up && make demo`. They create and cancel real bookings, so they must never be
// pointed at a deployment with real users; the default is the local stack.
export default defineConfig({
  testDir: "./e2e",
  // Tests share one database and look for free times, so they run one at a time.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8081",
    timezoneId: "Asia/Tashkent",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
