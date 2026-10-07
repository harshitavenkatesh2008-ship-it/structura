import { expect, test } from "@playwright/test";
import { mockDocument, DEMO_DEBT_ID } from "../src/data/mockDocument";
import { getBlocks } from "../src/utils/document";

test("mock graph is internally consistent and represents all requested block types", () => {
  const blocks = getBlocks(mockDocument);
  expect(new Set(blocks.map((block) => block.id)).size).toBe(blocks.length);
  expect(new Set(blocks.map((block) => block.type)).size).toBe(8);
  expect(mockDocument.page_count).toBe(mockDocument.pages.length);
  expect(mockDocument.metrics.traceable_blocks).toBe(
    blocks.filter((block) => block.traceable).length,
  );
  for (const page of mockDocument.pages)
    for (const block of page.blocks) {
      expect(block.page).toBe(page.page);
      expect(
        block.bbox.every((value) => value >= 0 && value <= 1),
      ).toBeTruthy();
      expect(block.bbox[2]).toBeGreaterThan(block.bbox[0]);
      expect(block.bbox[3]).toBeGreaterThan(block.bbox[1]);
      if (block.parent)
        expect(
          blocks.find((parent) => parent.id === block.parent)?.children,
        ).toContain(block.id);
      for (const child of block.children)
        expect(blocks.find((item) => item.id === child)?.parent).toBe(block.id);
    }
  expect(blocks.find((block) => block.id === DEMO_DEBT_ID)?.bbox).toEqual([
    0.1, 0.6, 0.9, 0.65,
  ]);
});

test("dashboard opens, Total Debt selects page 2 and matches the exact source row", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Document Intelligence Workspace" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/overview-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Open document", exact: true })
    .click();
  await expect(page.getByTestId("source-page-number")).toHaveText("1");
  await expect(page.getByTestId("bbox-overlay")).toHaveCount(0);
  await page.getByTestId("block-block_010").click();
  await expect(page.getByTestId("block-block_010")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByTestId("source-page-number")).toHaveText("2");
  await expect(page.getByTestId("provenance-block-id")).toHaveText("block_010");
  await expect(page.getByTestId("provenance-bbox")).toHaveText(
    "[0.10, 0.60, 0.90, 0.65]",
  );
  const overlay = await page.getByTestId("bbox-overlay").boundingBox();
  const row = await page.locator(".source-table .total-row").boundingBox();
  expect(overlay).not.toBeNull();
  expect(row).not.toBeNull();
  for (const key of ["x", "y", "width", "height"] as const)
    expect(Math.abs(overlay![key] - row![key])).toBeLessThan(2);
  await page.screenshot({
    path: "test-results/traceback-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "block_009", exact: true }).click();
  await expect(page.getByTestId("provenance-block-id")).toHaveText("block_009");
  await page.getByRole("button", { name: "Clear selected block" }).click();
  await expect(page.getByTestId("bbox-overlay")).toHaveCount(0);
  await page.getByRole("button", { name: "Next source page" }).click();
  await expect(page.getByTestId("source-page-number")).toHaveText("3");
  await page.getByTestId("block-block_017").click();
  await expect(page.getByTestId("provenance-block-id")).toHaveText("block_017");
  await expect(page.getByTestId("bbox-overlay")).toHaveCount(0);
  await expect(page.getByText("No — mapping unavailable")).toBeVisible();
  expect(errors).toEqual([]);
});

test("all routes, block filters, and browser back work", async ({ page }) => {
  await page.goto("/");
  const routes = [
    ["Documents", "Northstar Acquisition Report"],
    ["Structured", "Northstar Acquisition Report"],
    ["Markdown", "Readable by people. Ready for tools."],
    ["JSON", "The whole document. Structured."],
    ["Analytics", "A clearer picture of your document"],
    ["Overview", "Document Intelligence Workspace"],
  ];
  for (const [name, heading] of routes) {
    await page
      .getByRole("navigation")
      .getByRole("link", { name, exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("navigation").getByRole("link", { name, exact: true }),
    ).toHaveAttribute("aria-current", "page");
  }
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "A clearer picture of your document" }),
  ).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Structured", exact: true })
    .click();
  await page.getByLabel("Search extracted blocks").fill("Total Debt —");
  await expect(page.locator(".block-card")).toHaveCount(1);
  await page.getByTestId("block-block_010").click();
  await expect(page.getByTestId("source-page-number")).toHaveText("2");
  await page.getByLabel("Search extracted blocks").fill("");
  await page.getByLabel("Filter block type").selectOption("table");
  await expect(page.locator(".block-card")).toHaveCount(2);
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "Northstar Acquisition Report",
      exact: true,
    }),
  ).toBeVisible();
});

test("local upload validates files and simulated stages open the sample without parsing", async ({
  page,
}) => {
  await page.goto("/#/upload");
  await expect(
    page.getByRole("button", { name: "Start Parsing" }),
  ).toBeDisabled();
  await page
    .locator("#file-upload")
    .setInputFiles({
      name: "unsupported.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("demo"),
    });
  await expect(page.getByRole("alert")).toContainText("Choose a PDF");
  await page
    .locator("#file-upload")
    .setInputFiles({
      name: "my-example.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF mock file"),
    });
  await expect(page.locator(".selected-file")).toContainText("my-example.pdf");
  await page.getByRole("button", { name: "Start Parsing" }).click();
  await expect(page.getByRole("progressbar")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Open document", exact: true }),
  ).toBeVisible({ timeout: 10000 });
  await expect(page.locator(".processing-stage.complete")).toHaveCount(4);
  await page
    .getByRole("button", { name: "Open document", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Northstar Acquisition Report",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator(".workspace-title")).toContainText(
    "Northstar_Acquisition_Report.pdf",
  );
});

test("JSON and Markdown downloads contain the same mock report", async ({
  page,
}) => {
  await page.goto("/#/json");
  const jsonDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download", exact: true }).click();
  const json = await jsonDownload;
  expect(json.suggestedFilename()).toBe("northstar-document-graph.json");
  const stream = await json.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(chunk as Buffer);
  const graph = JSON.parse(Buffer.concat(chunks).toString());
  expect(
    graph.pages[1].blocks.find(
      (block: { id: string }) => block.id === DEMO_DEBT_ID,
    ).content,
  ).toBe("Total Debt — $425M");
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Markdown", exact: true })
    .click();
  await page.getByRole("button", { name: "Source", exact: true }).click();
  await expect(page.getByLabel("markdown output")).toContainText(
    "| Total Debt | $425M |",
  );
  const markdownDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download", exact: true }).click();
  expect((await markdownDownload).suggestedFilename()).toBe(
    "northstar-report.md",
  );
});

test("mobile navigation and TraceBack work without viewport overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "test-results/overview-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Documents", exact: true })
    .click();
  await page.getByRole("button", { name: "Trace Total Debt" }).click();
  await expect(page.getByTestId("source-page-number")).toHaveText("2");
  await expect(page.getByTestId("bbox-overlay")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.getByTestId("provenance-block-id").scrollIntoViewIfNeeded();
  await expect(page.getByTestId("provenance-block-id")).toHaveText("block_010");
  await page.screenshot({
    path: "test-results/traceback-mobile.png",
    fullPage: true,
  });
});
