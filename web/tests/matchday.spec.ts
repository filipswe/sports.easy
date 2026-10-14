import { test, expect } from "@playwright/test";

test("homepage analyst uses accessible inputs and a labelled data-backed answer", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Your match")).toHaveCount(0);
  await page
    .getByLabel("What would you like to know?")
    .fill("What are the current odds for Arsenal’s next game?");
  await page
    .getByRole("button", { name: "Ask our analyst", exact: true })
    .click();
  await expect(page.locator(".analyst-answer")).toContainText("Match insight");
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

test("goal lines keep distinct prices and BTTS/double chance can enter a parlay", async ({
  page,
}) => {
  await page.goto("/predictions");
  await page
    .getByRole("button", { name: "Under/over goals", exact: true })
    .click();
  await page.getByLabel("Goal line").selectOption("1.5");
  await expect(page).toHaveURL(/line=1.5/);
  const first = page.locator(".fixture-outcomes button").first();
  await expect(first).toContainText("Over 1.5");
  const price = await first.locator("b").textContent();
  expect(Number(price)).toBeGreaterThan(1);
  await first.click();
  await expect(page.locator(".slip-leg").first()).toContainText(
    "Over 1.5 goals",
  );
  await page.getByLabel("Goal line").selectOption("3.5");
  await expect(first).toContainText("Over 3.5");
  await expect(first.locator("b")).not.toHaveText(price!);
  await page.getByRole("button", { name: "BTTS", exact: true }).click();
  await expect(first).toContainText("Yes");
  await first.click();
  await expect(page.locator(".slip-leg").first()).toContainText(
    "Both teams to score",
  );
  await page
    .getByRole("button", { name: "Double chance", exact: true })
    .click();
  await expect(first).toContainText("or draw");
  await first.click();
  await expect(page.locator(".slip-leg").first()).toContainText("or draw");
  await page
    .getByRole("button", { name: "First-half goals", exact: true })
    .click();
  await page.getByLabel("Goal line").selectOption("1.5");
  await expect(first).toContainText("Over 1.5");
});
