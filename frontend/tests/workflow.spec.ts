import { test, expect } from "@playwright/test";
// Integration: real API and installed OCR/embedding weights. Not part of routine isolated CI.
test("uploaded image travels through actual API, OCR, history, corrections and offline chat", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "Read the details. Understand the tire.",
    }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/workspace-desktop.png",
    fullPage: true,
  });
  await page
    .locator("input[type=file]")
    .setInputFiles("../data/synthetic-ocr-smoke.png");
  await expect(page.getByAltText("Selected image preview")).toBeVisible();
  const request = page.waitForRequest(
    (r) => r.url().endsWith("/api/scans") && r.method() === "POST",
  );
  await page.getByRole("button", { name: "Analyze image" }).click();
  expect((await request).headers()["content-type"]).toContain(
    "multipart/form-data",
  );
  await expect(page.getByRole("heading", { name: "205/55 R16" })).toBeVisible({
    timeout: 110000,
  });
  await expect(page.getByText("205/55 R16 91V", { exact: true })).toBeVisible();
  await expect(page.getByAltText("Uploaded tire sidewall")).toBeVisible();
  expect(await page.locator(".viewer svg polygon").count()).toBeGreaterThan(0);
  await page.getByLabel("Brand", { exact: true }).fill("TOYO");
  await page.getByRole("button", { name: "Save corrections" }).click();
  await expect(
    page.getByText("Corrections saved. Future answers use these fields."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Explain this scan" }).click();
  await expect(
    page.getByText(
      "Generated answer unavailable. Review the retrieved excerpts below.",
      { exact: true },
    ),
  ).toBeVisible({ timeout: 110000 });
  await page.screenshot({ path: "../docs/scan-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "../docs/scan-mobile.png", fullPage: true });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: /Scan history/ }).click();
  await expect(page.getByText("TOYO", { exact: true })).toBeVisible();
  page.once("dialog", (d) => d.accept());
  await page
    .getByRole("button", { name: /Delete synthetic-ocr-smoke.png/ })
    .click();
  await expect(page.getByText("Scan deleted.", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
test("invalid file is rejected and camera denial leaves upload enabled", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .locator("input[type=file]")
    .setInputFiles({
      name: "invalid.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("invalid"),
    });
  await expect(page.getByRole("alert")).toContainText("Choose JPEG");
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
      value: () =>
        Promise.reject(
          new DOMException("Camera permission denied", "NotAllowedError"),
        ),
    });
  });
  await page.reload();
  await page.getByRole("button", { name: "Start Camera" }).click();
  await expect(page.getByRole("alert")).toContainText("denied");
  await page
    .locator("input[type=file]")
    .setInputFiles("../data/synthetic-ocr-smoke.png");
  await expect(
    page.getByRole("button", { name: "Analyze image" }),
  ).toBeEnabled();
});

test("knowledge interface ingests a real text reference", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Knowledge base" }).click();
  await page
    .locator("input[type=file]")
    .setInputFiles({
      name: "ui-integration-reference.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "Project-authored UI test reference: R denotes radial tire construction.",
      ),
    });
  await expect(page.getByRole("status")).toContainText("Reference ingested");
});
