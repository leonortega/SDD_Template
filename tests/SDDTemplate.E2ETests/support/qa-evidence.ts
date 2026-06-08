import { expect, type Page, type Request, type Response } from "@playwright/test";

export const qaScenarioCategories = [
  "navigation-rendering",
  "user-workflow",
  "api-backend-effect",
  "state-verification",
  "validation-boundaries",
  "error-handling",
  "environment-correctness",
  "evidence-integrity"
] as const;

export type QaScenarioCategory = typeof qaScenarioCategories[number];

type ExpectedConsole = (text: string) => boolean;
type ExpectedRequestFailure = (request: Request, failureText: string) => boolean;
type ExpectedResponse = (response: Response) => boolean;

export function assertDeployedQaTarget(label: string, rawUrl: string | undefined): string {
  expect(rawUrl, `${label} URL must be configured for deployed QA E2E`).toBeTruthy();

  const url = new URL(rawUrl!);
  expect(
    ["localhost", "127.0.0.1", "::1"],
    `${label} URL must target deployed QA, not a local server`
  ).not.toContain(url.hostname);
  expect(url.hostname.toLowerCase(), `${label} URL must not target DEV`).not.toContain("dev");

  return rawUrl!.replace(/\/$/, "");
}

export function assertSeparateServiceTargets(siteUrl: string, apiUrl: string): void {
  const siteOrigin = new URL(siteUrl).origin;
  const apiOrigin = new URL(apiUrl).origin;

  expect(apiOrigin, "QA browser/API tests must not rely on same-origin API fallback").not.toBe(siteOrigin);
}

export function createQaEvidenceRecorder(page: Page) {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  const unexpectedResponses: string[] = [];
  const expectedConsoleErrors: ExpectedConsole[] = [];
  const expectedRequestFailures: ExpectedRequestFailure[] = [];
  const expectedResponses: ExpectedResponse[] = [];

  page.on("console", message => {
    if (message.type() !== "error") {
      return;
    }

    const text = message.text();
    const expectedIndex = expectedConsoleErrors.findIndex(predicate => predicate(text));
    if (expectedIndex >= 0) {
      expectedConsoleErrors.splice(expectedIndex, 1);
      return;
    }

    consoleErrors.push(text);
  });

  page.on("requestfailed", requestInfo => {
    const failureText = requestInfo.failure()?.errorText ?? "";
    const expectedIndex = expectedRequestFailures.findIndex(predicate => predicate(requestInfo, failureText));
    if (expectedIndex >= 0) {
      expectedRequestFailures.splice(expectedIndex, 1);
      return;
    }

    failedRequests.push(`${requestInfo.method()} ${requestInfo.url()} ${failureText}`.trim());
  });

  page.on("response", response => {
    const expectedIndex = expectedResponses.findIndex(predicate => predicate(response));
    if (expectedIndex >= 0) {
      expectedResponses.splice(expectedIndex, 1);
      return;
    }

    if (response.status() >= 400) {
      const requestInfo = response.request();
      unexpectedResponses.push(`${response.status()} ${requestInfo.method()} ${response.url()}`);
    }
  });

  return {
    allowConsoleError(predicate: ExpectedConsole): void {
      expectedConsoleErrors.push(predicate);
    },
    allowRequestFailure(predicate: ExpectedRequestFailure): void {
      expectedRequestFailures.push(predicate);
    },
    allowResponse(predicate: ExpectedResponse): void {
      expectedResponses.push(predicate);
    },
    assertClean(): void {
      expect(expectedConsoleErrors, "expected browser console errors were not observed").toEqual([]);
      expect(expectedRequestFailures, "expected browser request failures were not observed").toEqual([]);
      expect(expectedResponses, "expected browser responses were not observed").toEqual([]);
      expect(consoleErrors, "unexpected browser console errors").toEqual([]);
      expect(failedRequests, "unexpected browser request failures").toEqual([]);
      expect(unexpectedResponses, "unexpected non-success browser API responses").toEqual([]);
    }
  };
}
