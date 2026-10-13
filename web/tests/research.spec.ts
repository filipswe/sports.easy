import { test, expect } from "@playwright/test";

test("recommended picks, match browsing, own analysis and a persistent parlay", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Our recommended picks" }),
  ).toBeVisible();
  await expect(page.locator("article.prediction-card")).toHaveCount(5);
  await expect(page.locator(".teams img").first()).toBeVisible();
  expect(
    await page
      .locator(".teams img")
      .first()
      .evaluate((el: HTMLImageElement) => el.naturalWidth),
  ).toBeGreaterThan(0);
  await page
    .getByRole("link", { name: "Explore matches", exact: true })
    .click();
  await expect(page.locator(".fixture-row")).toHaveCount(12);
  await page.locator(".fixture-row").nth(0).getByRole("button").first().click();
  await page.locator(".fixture-row").nth(1).getByRole("button").first().click();
  await page.locator(".fixture-row").nth(2).getByRole("button").first().click();
  await expect(page.locator(".slip-leg")).toHaveCount(3);
  await page.getByRole("link", { name: "Review parlay" }).click();
  await expect(
    page.getByRole("heading", { name: "Make it your parlay." }),
  ).toBeVisible();
  await expect(page.locator(".slip-totals")).toContainText("Sample prices");
  const inputs = page.getByLabel("Your decimal odds (optional)");
  for (let i = 0; i < 3; i++) await inputs.nth(i).fill("2.00");
  await expect(page.locator(".slip-totals strong")).toHaveText("8.00");
  await page
    .getByRole("button", { name: "Save this parlay", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Saved on this device" }),
  ).toBeDisabled();
  await page.reload();
  await expect(page.locator(".slip-leg")).toHaveCount(3);
  await page
    .getByRole("button", { name: "Saved parlays", exact: true })
    .click();
  await expect(page.locator(".saved-parlay")).toHaveCount(1);
  await page.getByRole("button", { name: "Clear parlay" }).click();
  await page.getByRole("button", { name: "Open parlay", exact: true }).click();
  await expect(page.locator(".slip-leg")).toHaveCount(3);
  await expect(page.locator(".slip-totals strong")).toHaveText("8.00");
});

test("first-half and form markets, search and empty results", async ({
  page,
}) => {
  await page.goto("/predictions");
  await page.getByLabel("Search teams").fill("Arsenal");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/team=Arsenal/);
  await expect(page.locator(".fixture-row")).toHaveCount(2);
  await page
    .getByRole("button", { name: "First-half goals", exact: true })
    .click();
  await expect(page.locator(".fixture-outcomes button").first()).toContainText(
    "Over 0.5",
  );
  await page.locator(".match-more").first().click();
  await page.getByRole("button", { name: "First half", exact: true }).click();
  await expect(page.locator(".market-panel")).toHaveCount(3);
  await page
    .locator(".market-panel")
    .first()
    .getByRole("button")
    .first()
    .click();
  await expect(page.locator(".insight-card h2")).toHaveText(
    "1st half: Over 0.5 goals",
  );
  await page.getByRole("button", { name: "Form & stats" }).click();
  await expect(page.locator(".recent-row")).toHaveCount(10);
  await page.getByRole("button", { name: "Head to head", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Previous meetings" }),
  ).toBeVisible();
  await page.goto("/predictions?team=not-a-club");
  await expect(
    page.getByRole("heading", { name: "No matches found" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Reset filters", exact: true })
    .click();
  await expect(page.locator(".fixture-row")).toHaveCount(12);
  await page.goto("/admin");
  await expect(page.locator(".notice.error")).toContainText(
    "Sign in to continue",
  );
});

test("model suggestions respect the requested range, performance contains only official picks", async ({
  page,
}) => {
  await page.goto("/parlays");
  await expect(page.locator(".parlay-suggestion").first()).toBeVisible();
  await page.getByLabel("Min. combined odds").fill("6");
  await page.getByLabel("Max. combined odds").fill("10");
  await page.getByRole("button", { name: "Find parlays", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Find parlays", exact: true }),
  ).toBeEnabled();
  const prices = await page
    .locator(".suggestion-footer>div:first-child>b")
    .allTextContents();
  expect(prices.length).toBeGreaterThan(0);
  for (const price of prices) expect(Number(price)).toBeGreaterThanOrEqual(6);
  for (const price of prices) expect(Number(price)).toBeLessThanOrEqual(10);
  await page
    .getByRole("button", { name: "Use this parlay", exact: true })
    .first()
    .click();
  await expect(page.locator(".slip-leg")).toHaveCount(3);
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Performance", exact: true })
    .click();
  await expect(page.locator(".archive-panel tbody tr")).toHaveCount(5);
  await expect(
    page.getByText("5 picks tracked", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("This record uses sample fixtures and prices.", {
      exact: false,
    }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/performance-desktop.png",
    fullPage: true,
  });
});

test("registration, verification and saving a pick", async ({ page }) => {
  await page.goto("/account");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  const email = `matchday-${Date.now()}@example.com`;
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel(/^Password/).fill("matchday-test-password-123");
  await page.getByRole("checkbox").check();
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .last()
    .click();
  await page
    .getByRole("link", { name: "Open verification / reset link" })
    .click();
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(
    page.getByText("Email verified. You can now sign in."),
  ).toBeVisible();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel(/^Password/).fill("matchday-test-password-123");
  await page
    .getByRole("button", { name: "Sign in", exact: true })
    .last()
    .click();
  await expect(
    page.getByRole("heading", { name: "Your account", exact: true }),
  ).toBeVisible();
  await page.goto("/");
  await page
    .locator("article.prediction-card")
    .first()
    .getByRole("button", { name: /^Save / })
    .click();
  await expect(
    page
      .locator("article.prediction-card")
      .first()
      .getByRole("button", { name: /^Save / }),
  ).toBeDisabled();
  await page.getByRole("link", { name: "Saved picks", exact: true }).click();
  await expect(page.locator("article.prediction-card")).toHaveCount(1);
  await page.reload();
  await expect(page.locator("article.prediction-card")).toHaveCount(1);
});

test("light desktop and mobile layouts, club logos and navigation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.locator("article.prediction-card")).toHaveCount(5);
  await page.screenshot({
    path: "test-results/home-desktop.png",
    fullPage: true,
  });
  await page.goto("/predictions");
  await expect(page.locator(".fixture-row")).toHaveCount(12);
  await page.screenshot({
    path: "test-results/matches-desktop.png",
    fullPage: true,
  });
  await page.locator(".match-more").first().click();
  await expect(page.locator(".market-panel").first()).toBeVisible();
  await page.screenshot({
    path: "test-results/match-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  for (const url of [
    "/",
    "/predictions",
    "/parlays",
    "/performance",
    "/how-it-works",
    "/account",
  ]) {
    await page.goto(url);
    if (url === "/")
      await expect(page.locator("article.prediction-card")).toHaveCount(5);
    if (url === "/predictions")
      await expect(page.locator(".fixture-row")).toHaveCount(12);
    if (url === "/parlays")
      await expect(page.locator(".parlay-suggestion").first()).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    await page.screenshot({
      path: `test-results/mobile-${url.replaceAll("/", "") || "home"}.png`,
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "All matches", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Find your next pick." }),
  ).toBeVisible();
});
