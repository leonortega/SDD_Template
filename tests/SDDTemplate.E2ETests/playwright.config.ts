import { defineConfig, devices } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const localQaTargets = readLocalQaTargets();
const siteUrl = process.env.E2E_SITE_URL ?? localQaTargets.siteUrl;
const apiUrl = process.env.E2E_API_URL ?? localQaTargets.apiUrl;

if (siteUrl) {
  process.env.E2E_SITE_URL = siteUrl;
}

if (apiUrl) {
  process.env.E2E_API_URL = apiUrl;
}

if (!siteUrl || !apiUrl) {
  throw new Error("E2E_SITE_URL and E2E_API_URL are required. QA E2E tests run only against deployed QA apps.");
}

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  workers: 1,
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

function readLocalQaTargets(): { siteUrl?: string; apiUrl?: string } {
  const configPath = resolve(process.cwd(), "../../.codex/client-tools.local.json");
  if (!existsSync(configPath)) {
    return {};
  }

  const config = JSON.parse(readFileSync(configPath, "utf8"));
  return {
    siteUrl: config?.azure?.qa?.siteUrl,
    apiUrl: config?.azure?.qa?.apiUrl
  };
}
