import { expect, test } from "@playwright/test";

// Functional additions remain presentation-only and use the original graph.
test("JSON tree, source scopes, tokens, and complete-graph copy work", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/#/json");
  await expect(page.locator(".json-key").first()).toBeVisible();
  await expect(page.locator(".json-number").first()).toBeVisible();
  await page.getByLabel("JSON source page").selectOption("2");
  await page.getByLabel("JSON block").selectOption("block_010");
  await expect(page.getByLabel("json output")).toContainText(
    "Total Debt — $425M",
  );
  await expect(page.getByLabel("json output")).not.toContainText("block_017");
  await page.getByRole("button", { name: "Tree", exact: true }).click();
  const root = page.locator(".json-tree-toggle").first();
  await expect(root).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByLabel("Document Graph tree")).toContainText(
    "table_engine",
  );
  await root.click();
  await expect(root).toHaveAttribute("aria-expanded", "false");
  await root.click();
  await expect(root).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("button", { name: "Copy", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Copied", exact: true }),
  ).toBeVisible();
  const copied = JSON.parse(
    await page.evaluate(() => navigator.clipboard.readText()),
  );
  expect(copied.pages).toHaveLength(3);
  expect(copied.metrics.block_count).toBe(18);
  expect(
    copied.pages[2].blocks.some(
      (block: { id: string }) => block.id === "block_017",
    ),
  ).toBeTruthy();
});

test("source regions, keyboard inspection, page strip and unmapped mapping stay coherent", async ({
  page,
}) => {
  await page.goto("/#/document");
  await page.getByRole("button", { name: "Show extraction regions" }).click();
  await expect(page.locator(".document-paper")).toHaveClass(/show-regions/);
  const heading = page.getByRole("button", {
    name: "Inspect source block block_001",
    exact: true,
  });
  await heading.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("provenance-block-id")).toHaveText("block_001");
  await expect(page.getByTestId("block-block_001")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(
    page.getByText("Source verified", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Go to source page 3" }).click();
  await expect(page.getByTestId("source-page-number")).toHaveText("3");
  await expect(page.getByTestId("bbox-overlay")).toHaveCount(0);
  await page
    .getByRole("button", {
      name: "Inspect source block block_017",
      exact: true,
    })
    .click();
  await expect(page.getByText("No — mapping unavailable")).toBeVisible();
  await expect(page.getByText("Source verified", { exact: true })).toHaveCount(
    0,
  );
  await expect(page.getByTestId("bbox-overlay")).toHaveCount(0);
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect(page.locator(".zoom-controls")).toContainText("110%");
});

test("command center actions and frontend-only workspace controls work", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Document Intelligence Workspace" }),
  ).toBeVisible();
  await expect(page.locator(".intelligence-rail")).toContainText("17/18");
  await expect(page.locator(".connection-status")).toContainText(
    "Backend not connected",
  );
  await page.getByRole("button", { name: "Select workspace" }).click();
  await expect(page.locator(".workspace-popover")).toContainText(
    "one workspace",
  );
  await page.locator(".workspace-popover button").click();
  await page.getByRole("button", { name: "Workspace settings" }).click();
  await expect(page.locator(".settings-popover")).toContainText(
    "Mock-only frontend",
  );
  await page.getByRole("button", { name: "Workspace settings" }).click();
  await page
    .getByRole("button", { name: "Try TraceBack", exact: true })
    .click();
  await expect(page.getByTestId("source-page-number")).toHaveText("2");
  await expect(page.getByTestId("provenance-bbox")).toHaveText(
    "[0.10, 0.60, 0.90, 0.65]",
  );
  await expect(page.getByLabel("Provenance path")).toContainText(
    "BOUNDING BOX",
  );
});

test("all presentation surfaces fit phone and tablet viewports", async ({
  page,
}) => {
  for (const width of [390, 820]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of [
      "overview",
      "document",
      "structured",
      "json",
      "markdown",
      "analytics",
      "upload",
      "processing",
    ]) {
      await page.goto(`/#/${route}`);
      await expect(page.locator("main")).not.toBeEmpty();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth),
        `${route} at ${width}px`,
      ).toBeLessThanOrEqual(width);
    }
  }
});

test("mobile navigation is inert while closed and tablet metadata remains visible", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto("/");
  const sidebar = page.locator("#workspace-navigation-panel");
  const menu = page.getByRole("button", { name: "Open navigation" });
  await expect(sidebar).toHaveJSProperty("inert", true);
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await menu.click();
  await expect(sidebar).toHaveJSProperty("inert", false);
  await expect(
    page.getByRole("button", { name: "Close navigation", exact: true }).first(),
  ).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("Escape");
  await expect(sidebar).toHaveJSProperty("inert", true);
  await page.setViewportSize({ width: 820, height: 900 });
  await expect(sidebar).toHaveJSProperty("inert", false);
  await page.goto("/#/structured");
  await expect(page.locator(".block-source-page").first()).toBeVisible();
  await expect(page.locator(".block-id").first()).toBeVisible();
  await page.getByTestId("block-block_010").click();
  await expect(
    page.getByText("0–1 · TOP-LEFT ORIGIN", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Provenance path")).toBeVisible();
  await page.goto("/#/json");
  await expect(
    page.getByRole("button", { name: "Raw JSON", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Tree", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Tree", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
});
