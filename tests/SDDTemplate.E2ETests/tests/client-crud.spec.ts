import { expect, request, test, type APIRequestContext, type Page } from "@playwright/test";
import {
  assertDeployedQaTarget,
  assertSeparateServiceTargets,
  createQaEvidenceRecorder
} from "../support/qa-evidence";

type ClientRecord = {
  id: number;
  name: string;
  lastName: string;
  address: string;
  bornDate: string;
  city: string;
  country: string;
  zipCode: string;
};

const siteUrl = assertDeployedQaTarget("E2E_SITE_URL", process.env.E2E_SITE_URL);
const apiUrl = assertDeployedQaTarget("E2E_API_URL", process.env.E2E_API_URL);
assertSeparateServiceTargets(siteUrl, apiUrl);

const uniqueSuffix = `${Date.now()}-${Math.floor(Math.random() * 1000)}`;
const testClient = {
  name: `QA E2E ${uniqueSuffix}`,
  lastName: "Client",
  address: "100 Automation Way",
  bornDate: "1990-01-15",
  city: "Cordoba",
  country: "Argentina",
  zipCode: "QA-123"
};

const updatedClient = {
  ...testClient,
  address: "200 Verified Avenue",
  city: "Mendoza",
  zipCode: "QA-456"
};

test.describe("Client CRUD deployed QA E2E", () => {
  let api: APIRequestContext;
  const createdIds: number[] = [];
  let initialClients: Array<Omit<ClientRecord, "id">> = [];

  test.beforeAll(async () => {
    api = await request.newContext({ baseURL: apiUrl });
  });

  test.afterAll(async () => {
    for (const id of createdIds.reverse()) {
      await api.delete(`/api/clients/${id}`);
    }

    for (const client of initialClients) {
      await api.post("/api/clients", { data: client });
    }

    await api.dispose();
  });

  test("validates deployed API health and client CRUD through the QA site", async ({ page }) => {
    const evidence = createQaEvidenceRecorder(page);

    await assertApiHealth(api);
    await expect(await api.get("/api/clients")).toBeOK();
    initialClients = await clearClients(api);

    await page.goto("/");
    const blazorConnected = waitForBlazorConnection(page);
    await page.getByRole("link", { name: "Clients" }).click();
    await blazorConnected;
    await expect(page).toHaveTitle(/Clients|SDD Template/);
    await expect(page.getByRole("heading", { name: "Clients" })).toBeVisible();
    await expect(page.locator("#client-form")).toBeVisible();
    await expect(page.locator("#clients-list")).toBeVisible();
    await expect(saveClientButton(page)).toBeEnabled();

    const invalidResponse = await api.post("/api/clients", {
      data: {
        ...testClient,
        bornDate: futureDate()
      }
    });
    expect(invalidResponse.status()).toBe(400);
    expect(await invalidResponse.text()).toContain("Born date cannot be in the future.");

    await fillClientForm(page, testClient);
    await saveClientButton(page).click();
    await expect(page.locator("#client-errors")).toBeEmpty();
    await expect(page.locator("#clients-list")).toContainText(`${testClient.name} ${testClient.lastName}`);
    await expect(page.locator("#clients-list")).toContainText(testClient.city);

    const created = await findClient(api, testClient.name, testClient.lastName);
    expect(created, "created client should be available through the deployed API").toBeTruthy();
    createdIds.push(created!.id);

    const createdRow = rowForClient(page, testClient.name);
    await createdRow.getByRole("button", { name: "Edit" }).click();
    await expect(page.locator("#client-id")).toHaveValue(String(created!.id));
    await fillClientForm(page, updatedClient);
    await saveClientButton(page).click();
    await expect(page.locator("#clients-list")).toContainText(updatedClient.address);
    await expect(page.locator("#clients-list")).toContainText(updatedClient.city);

    const updated = await findClient(api, updatedClient.name, updatedClient.lastName);
    expect(updated?.address).toBe(updatedClient.address);
    expect(updated?.zipCode).toBe(updatedClient.zipCode);

    const updatedRow = rowForClient(page, updatedClient.name);
    evidence.allowRequestFailure((requestInfo, failureText) =>
      requestInfo.method() === "DELETE" &&
      requestInfo.url().includes("/api/clients/") &&
      failureText.includes("ERR_ABORTED"));
    await updatedRow.getByRole("button", { name: "Delete" }).click();
    await expect(page.locator("#clients-list")).not.toContainText(updatedClient.name);
    await expect(await api.get(`/api/clients/${created!.id}`)).not.toBeOK();
    createdIds.splice(createdIds.indexOf(created!.id), 1);

    evidence.assertClean();
  });
});

async function assertApiHealth(api: APIRequestContext): Promise<void> {
  const response = await api.get("/health");
  await expect(response).toBeOK();
  const body = await response.json();
  expect(body.status).toBe("ok");
}

async function fillClientForm(page: Page, client: Omit<ClientRecord, "id">): Promise<void> {
  await page.locator("#client-born-date").fill(client.bornDate);
  await page.locator("#client-name").fill(client.name);
  await page.locator("#client-last-name").fill(client.lastName);
  await page.locator("#client-address").fill(client.address);
  await page.locator("#client-city").fill(client.city);
  await page.locator("#client-country").fill(client.country);
  await page.locator("#client-zip-code").fill(client.zipCode);
}

async function findClient(api: APIRequestContext, name: string, lastName: string): Promise<ClientRecord | undefined> {
  const response = await api.get("/api/clients");
  await expect(response).toBeOK();
  const clients = await response.json() as ClientRecord[];

  return clients.find(client => client.name === name && client.lastName === lastName);
}

async function clearClients(api: APIRequestContext): Promise<Array<Omit<ClientRecord, "id">>> {
  const response = await api.get("/api/clients");
  await expect(response).toBeOK();
  const clients = await response.json() as ClientRecord[];

  for (const client of clients) {
    const deleteResponse = await api.delete(`/api/clients/${client.id}`);
    await expect(deleteResponse).toBeOK();
  }
  return clients.map(({ id: _, ...client }) => client);
}

function rowForClient(page: Page, name: string) {
  return page.locator("#clients-list tr").filter({ hasText: name }).first();
}

function saveClientButton(page: Page) {
  return page.getByRole("button", { name: "Save client" });
}

async function waitForBlazorConnection(page: Page): Promise<void> {
  await page.waitForEvent("websocket", websocket => websocket.url().includes("/_blazor"), { timeout: 15_000 });
  await page.waitForTimeout(250);
}

function futureDate(): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + 1);

  return date.toISOString().slice(0, 10);
}
