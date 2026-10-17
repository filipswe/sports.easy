import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

test("club badges retry their provider image and recover when a failed team changes", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".app-status")).toContainText("Sample data");
  await page.clock.install();
  const arsenalImage = await readFile("public/clubs/arsenal.png");
  const providerImage = "https://crests.football-data.org/57.png";
  let cachedAttempts = 0;
  let stage = 0;
  await page.route("**/clubs/football-data-team-57.png", async (route) => {
    if (stage === 2) {
      await route.fulfill({ contentType: "image/png", body: arsenalImage });
    } else {
      cachedAttempts += 1;
      await route.abort("failed");
    }
  });
  await page.route(providerImage, (route) =>
    route.fulfill({ contentType: "image/png", body: arsenalImage }),
  );
  await page.route("**/clubs/missing-test-crest.png", (route) =>
    route.abort("failed"),
  );
  await page.route("**/api/matchday?**", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    const fixture = data.items.find(
      (item: { home: string }) => item.home === "Arsenal",
    );
    expect(fixture).toBeTruthy();
    fixture.home = stage === 2 ? "Arsenal FC" : "Arsenal";
    fixture.home_logo =
      stage === 0
        ? providerImage
        : stage === 1
          ? "/clubs/missing-test-crest.png"
          : "/clubs/football-data-team-57.png";
    await route.fulfill({ response, json: { ...data, items: [fixture] } });
  });
  await page.getByRole("link", { name: "All matches", exact: true }).click();
  await expect(page.locator(".fixture-row")).toHaveCount(1);
  const badge = page.locator(".fixture-row .team-badge").first();
  await expect(badge.locator("img")).toHaveAttribute("src", providerImage);
  await expect.poll(() => cachedAttempts).toBeGreaterThan(0);
  await expect
    .poll(() =>
      badge
        .locator("img")
        .evaluate((image: HTMLImageElement) => image.naturalWidth),
    )
    .toBeGreaterThan(0);

  stage = 1;
  await page.clock.fastForward(60000);
  await expect(badge.locator("img")).toHaveCount(0);
  await expect(badge.locator('[aria-label="Arsenal"]')).toBeVisible();

  stage = 2;
  await page.clock.fastForward(60000);
  await expect(badge.locator("img")).toHaveAttribute("alt", "Arsenal FC crest");
  await expect(badge.locator("img")).toHaveAttribute(
    "src",
    "/clubs/football-data-team-57.png",
  );
  await expect
    .poll(() =>
      badge
        .locator("img")
        .evaluate((image: HTMLImageElement) => image.naturalWidth),
    )
    .toBeGreaterThan(0);
});
