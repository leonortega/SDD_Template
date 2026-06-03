import { defineConfig, devices } from "@playwright/test";

const siteUrl = process.env.E2E_SITE_URL;
const apiUrl = process.env.E2E_API_URL;

if (!siteUrl || !apiUrl) {
  throw new Error("E2E_SITE_URL and E2E_API_URL are required. QA E2E tests run only against deployed QA apps.");
}

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: {
    timeout: 10_000
  },
  reporter: [
    ["list"],
    ["junit", { outputFile: "test-results/junit.xml" }],
    ["html", { outputFolder: "playwright-report", open: "never" }]
  ],
  use: {
    baseURL: siteUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  metadata: {
    apiUrl,
    siteUrl
  },
  outputDir: "test-results/artifacts"
});
