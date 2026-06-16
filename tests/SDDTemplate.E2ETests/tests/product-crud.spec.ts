import { expect, request, test, type APIRequestContext, type Page } from "@playwright/test";
import {
  assertDeployedQaTarget,
  assertSeparateServiceTargets,
  createQaEvidenceRecorder
} from "../support/qa-evidence";

type ProductRecord = {
  id: number;
  name: string;
  sku: string;
  status: string;
  price: number;
  category: string;
  lastUpdated: string;
};

type ProductForm = Omit<ProductRecord, "id" | "lastUpdated" | "price"> & {
  price: string;
};

const siteUrl = assertDeployedQaTarget("E2E_SITE_URL", process.env.E2E_SITE_URL);
const apiUrl = assertDeployedQaTarget("E2E_API_URL", process.env.E2E_API_URL);
assertSeparateServiceTargets(siteUrl, apiUrl);

const uniqueSuffix = `${Date.now()}-${Math.floor(Math.random() * 1000)}`;
const testProduct = {
  name: `QA Product ${uniqueSuffix}`,
  sku: `qa-prod-${uniqueSuffix}`,
  status: "Active",
  price: "19.99",
  category: "QA"
};

const updatedProduct = {
  ...testProduct,
  name: `${testProduct.name} Updated`,
  status: "Inactive",
  price: "29.99",
  category: "Verified"
};

test.describe("Product CRUD deployed QA E2E", () => {
  let api: APIRequestContext;
  const createdIds: number[] = [];
  let initialProducts: Array<Omit<ProductRecord, "id" | "lastUpdated">> = [];

  test.beforeAll(async () => {
    api = await request.newContext({ baseURL: apiUrl });
  });

  test.afterAll(async () => {
    for (const id of createdIds.reverse()) {
      await api.delete(`/api/products/${id}`);
    }

    for (const product of initialProducts) {
      await api.post("/api/products", { data: product });
    }

    await api.dispose();
  });

  test("validates deployed API health and product CRUD through the QA site", async ({ page }) => {
    const evidence = createQaEvidenceRecorder(page);

    await assertApiHealth(api);
    await expect(await api.get("/api/products")).toBeOK();
    initialProducts = await clearProducts(api);

    const blazorConnected = waitForBlazorConnection(page);
    await page.goto("/");
    await blazorConnected;
    await page.getByRole("link", { name: "Products" }).click();
    await expect(page).toHaveTitle(/Products|SDD Template/);
    await expect(page.getByRole("heading", { name: "Products" })).toBeVisible();
    await expect(page.locator("#product-form")).toBeVisible();
    await expect(page.locator("#products-list")).toBeVisible();
    await expect(page.locator("#products-list")).toContainText("No products exist yet.");

    const invalidResponse = await api.post("/api/products", {
      data: {
        ...testProduct,
        name: "   ",
        sku: "@@",
        status: "Archived",
        price: -1
      }
    });
    expect(invalidResponse.status()).toBe(400);
    const invalidBody = await invalidResponse.text();
    expect(invalidBody).toContain("Name is required.");
    expect(invalidBody).toContain("SKU must be 3 to 40 letters, digits, dots, underscores, or hyphens.");
    expect(invalidBody).toContain("Price cannot be negative.");

    await fillProductForm(page, testProduct);
    await page.getByRole("button", { name: "Save product" }).click();
    await expect(page.locator("#product-errors")).toContainText("Product saved.");
    await expect(page.locator("#products-list")).toContainText(testProduct.name);
    await expect(page.locator("#products-list")).toContainText(testProduct.sku.toUpperCase());
    await expect(page.locator("#products-list")).toContainText(testProduct.category);

    const created = await findProduct(api, testProduct.sku);
    expect(created, "created product should be available through the deployed API").toBeTruthy();
    createdIds.push(created!.id);

    const createdRow = rowForProduct(page, testProduct.name);
    await createdRow.getByRole("button", { name: "Edit" }).click();
    await expect(page.locator("#product-id")).toHaveValue(String(created!.id));
    await fillProductForm(page, updatedProduct);
    await page.getByRole("button", { name: "Save product" }).click();
    await expect(page.locator("#products-list")).toContainText(updatedProduct.name);
    await expect(page.locator("#products-list")).toContainText(updatedProduct.status);
    await expect(page.locator("#products-list")).toContainText(updatedProduct.category);

    const updated = await findProduct(api, updatedProduct.sku);
    expect(updated?.name).toBe(updatedProduct.name);
    expect(updated?.price).toBe(Number(updatedProduct.price));
    expect(updated?.category).toBe(updatedProduct.category);

    const updatedRow = rowForProduct(page, updatedProduct.name);
    evidence.allowRequestFailure((requestInfo, failureText) =>
      requestInfo.method() === "DELETE" &&
      requestInfo.url().includes("/api/products/") &&
      failureText.includes("ERR_ABORTED"));
    await updatedRow.getByRole("button", { name: "Delete" }).click();
    await updatedRow.getByRole("button", { name: "Confirm delete" }).click();
    await expect(page.locator("#product-errors")).toContainText("Product deleted.");
    await expect(page.locator("#products-list")).not.toContainText(updatedProduct.name);
    await expect(await api.get(`/api/products/${created!.id}`)).not.toBeOK();
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

async function fillProductForm(page: Page, product: ProductForm): Promise<void> {
  await page.locator("#product-status").selectOption(product.status);
  await page.locator("#product-price").fill(String(product.price));
  await page.locator("#product-name").fill(product.name);
  await page.locator("#product-sku").fill(product.sku);
  await page.locator("#product-category").fill(product.category);
}

async function findProduct(api: APIRequestContext, sku: string): Promise<ProductRecord | undefined> {
  const response = await api.get("/api/products");
  await expect(response).toBeOK();
  const products = await response.json() as ProductRecord[];

  return products.find(product => product.sku === sku.toUpperCase());
}

async function clearProducts(api: APIRequestContext): Promise<Array<Omit<ProductRecord, "id" | "lastUpdated">>> {
  const response = await api.get("/api/products");
  await expect(response).toBeOK();
  const products = await response.json() as ProductRecord[];

  for (const product of products) {
    const deleteResponse = await api.delete(`/api/products/${product.id}`);
    await expect(deleteResponse).toBeOK();
  }

  return products.map(({ id: _, lastUpdated: __, ...product }) => product);
}

function rowForProduct(page: Page, name: string) {
  return page.locator("#products-list tr").filter({ hasText: name }).first();
}

async function waitForBlazorConnection(page: Page): Promise<void> {
  await page.waitForEvent("websocket", websocket => websocket.url().includes("/_blazor"), { timeout: 15_000 });
  await page.waitForTimeout(250);
}
