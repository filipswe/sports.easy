import { test, expect } from "@playwright/test";

test("homepage analyst uses accessible inputs and a labelled data-backed answer", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Your match")).not.toHaveValue("");
  await page
    .getByLabel("What would you like to know?")
    .fill("What are the current odds?");
  await page
    .getByRole("button", { name: "Ask our analyst", exact: true })
    .click();
  await expect(page.locator(".analyst-answer")).toContainText(
    "Data-backed answer",
  );
  await expect(page.locator(".analyst-answer")).toContainText(
    "Demo Sportsbook",
  );
  await expect(page.getByText("HOW ODDS COMBINE", { exact: true })).toHaveCount(
    0,
  );
  await page
    .getByRole("button", { name: "What is the recent form?", exact: true })
    .click();
  await expect(page.getByLabel("What would you like to know?")).toHaveValue(
    "What is the recent form?",
  );
  await page
    .getByRole("button", { name: "Ask our analyst", exact: true })
    .click();
  await expect(page.locator(".analyst-answer")).toContainText(
    "latest verified results",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page
    .locator(".analyst-card")
    .screenshot({ path: "test-results/analyst-mobile.png" });
});
