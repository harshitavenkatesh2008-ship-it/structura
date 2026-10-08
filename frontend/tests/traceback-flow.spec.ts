import { expect, test } from "@playwright/test";

async function expectExactDebtRow(page: import("@playwright/test").Page) {
  const overlay = page.getByTestId("bbox-overlay");
  await expect(overlay).toBeVisible();
  await expect(overlay).toHaveAttribute(
    "aria-label",
    "Source bounding box for block_010",
  );
  await expect(async () => {
    const box = await overlay.boundingBox();
    const row = await page.locator(".source-table .total-row").boundingBox();
    expect(box).not.toBeNull();
    expect(row).not.toBeNull();
    for (const key of ["x", "y", "width", "height"] as const) {
      expect(Math.abs(box![key] - row![key])).toBeLessThan(2);
    }
  }).toPass();
}

test("Trace Total Debt restores visibility, focuses the source and synchronizes all provenance", async ({
  page,
}) => {
  await page.goto("/#/structured");
  await page.getByLabel("Search extracted blocks").fill("approval");
  await page.getByLabel("Filter block type").selectOption("image");
  await page.getByRole("button", { name: "Trace Total Debt" }).click();
  await expect(page).toHaveURL(/#\/document$/);
  const source = page.getByRole("region", { name: "Document source viewer" });
  await expect(source).toBeFocused();
  await expect(source).toHaveClass(/source-linked/);
  await expect(page.getByTestId("source-page-number")).toHaveText("2");
  await expect(page.getByLabel("Search extracted blocks")).toHaveValue("");
  await expect(page.getByLabel("Filter block type")).toHaveValue("all");
  await expect(page.getByTestId("block-block_010")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  const panel = page.getByRole("region", { name: "TraceBack provenance" });
  await expect(panel.getByTestId("traceback-result")).toContainText(
    "Total Debt — $425M",
  );
  await expect(page.getByTestId("provenance-block-id")).toHaveText("block_010");
  await expect(panel).toContainText("table_engine");
  await expect(panel).toContainText("Page 2");
  await expect(panel).toContainText("low risk");
  await expect(panel).toContainText("Yes — source mapped");
  await expect(page.getByTestId("provenance-bbox")).toHaveText(
    "[0.10, 0.60, 0.90, 0.65]",
  );
  await expect(page.getByLabel("Provenance path").locator(".path-node")).toHaveText([
    "01", "02", "03", "04",
  ]);
  await expectExactDebtRow(page);
  const sourceBox = await source.boundingBox();
  const outputBox = await page.locator(".inspection-output").boundingBox();
  expect(sourceBox!.width).toBeGreaterThan(outputBox!.width * 1.2);

  await page.locator(".workspace-tabs").getByRole("button", { name: "Structured" }).click();
  await expect(page).toHaveURL(/#\/structured$/);
  await expect(page.getByTestId("block-block_010")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("source-page-number")).toHaveText("2");
  await expect(page.getByTestId("provenance-block-id")).toHaveText("block_010");
  await page.locator(".workspace-tabs").getByRole("button", { name: "Document", exact: true }).click();
  await expect(source).not.toBeFocused();

  // Repeating the same demo still focuses the source; no stale one-shot request.
  await page.getByRole("button", { name: "Trace Total Debt" }).click();
  await expect(source).toBeFocused();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expectExactDebtRow(page);
});

test("empty state is truthful and mobile demo respects reduced motion", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/#/document");
  const panel = page.getByRole("region", { name: "TraceBack provenance" });
  await expect(panel).toContainText(
    "Select an extracted block to trace it to its source.",
  );
  await expect(page.getByTestId("bbox-overlay")).toHaveCount(0);
  await page.getByRole("button", { name: "Trace Total Debt" }).click();
  await expect(page.getByRole("region", { name: "Document source viewer" })).toBeFocused();
  await expectExactDebtRow(page);
  expect(await page.getByTestId("bbox-overlay").evaluate(
    (element) => getComputedStyle(element).animationName,
  )).toBe("none");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole("button", { name: "Clear selected block" }).click();
  await expect(page.getByTestId("bbox-overlay")).toHaveCount(0);
  await expect(panel).toContainText(
    "Select an extracted block to trace it to its source.",
  );
});
