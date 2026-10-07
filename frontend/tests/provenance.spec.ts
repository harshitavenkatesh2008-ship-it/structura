import { expect, test } from "@playwright/test";

test("TraceBack distinguishes verified bounds from unverified candidate coordinates", async ({
  page,
}) => {
  await page.goto("/#/document");
  const panel = page.getByRole("region", { name: "TraceBack provenance" });

  await page.getByTestId("block-block_010").click();
  await expect(panel.getByText("BOUNDING BOX", { exact: true })).toHaveCount(2);
  await expect(panel.getByText("Source verified", { exact: true })).toBeVisible();
  await expect(page.getByTestId("provenance-bbox")).toHaveText(
    "[0.10, 0.60, 0.90, 0.65]",
  );
  await expect(page.getByTestId("bbox-overlay")).toBeVisible();

  await page.getByTestId("block-block_017").click();
  const candidateLabel = panel.getByText("CANDIDATE BOX · UNVERIFIED", {
    exact: true,
  });
  await expect(candidateLabel).toBeVisible();
  await expect(candidateLabel).toHaveAttribute(
    "title",
    /no verified source mapping exists/,
  );
  await expect(panel.getByText("MAPPING UNAVAILABLE", { exact: true })).toBeVisible();
  await expect(panel.getByText("BOUNDING BOX", { exact: true })).toHaveCount(0);
  await expect(panel.getByText("Source verified", { exact: true })).toHaveCount(0);
  await expect(page.getByTestId("provenance-bbox")).toContainText("[");
  await expect(page.getByTestId("bbox-overlay")).toHaveCount(0);
});
