import { expect, test } from "@playwright/test";

test("routes three RTC tickets and keeps support open after a confirmed handoff", async ({ page, request }, testInfo) => {
  const ticketsResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/tickets" && response.ok(),
  );
  await page.goto("/");
  expect(await (await ticketsResponse).json()).toHaveLength(3);

  await page.getByRole("button", { name: /RTC-1040|Cedarline Media/ }).click();
  await expect(page.getByText("Do you have a planned launch date?", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /confirm handoff/i })).toHaveCount(0);

  await page.getByRole("button", { name: /RTC-1041|Northwind Studio/ }).click();
  await expect(page.getByText(/Check the token expiry/)).toBeVisible();
  await expect(page.getByRole("button", { name: /confirm handoff/i })).toHaveCount(0);

  await page.getByRole("button", { name: /RTC-1042|Harborline Labs/ }).click();
  await expect(page.getByText(/Ask for the failure time/)).toBeVisible();
  await expect(page.getByText(/evaluating a move from Twilio Video/i).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("mixed-ticket.png"), fullPage: true });

  const confirm = page.getByRole("button", { name: /confirm handoff/i });
  await expect(confirm).toBeDisabled();
  await page.getByRole("combobox", { name: /assign|engineer/i }).selectOption({ label: "Maya Chen" });
  const saved = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/tickets/RTC-1042/handoff" &&
    response.request().method() === "POST",
  );
  await confirm.click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toMatchObject({ status: "open", handoff: { owner: "Maya Chen" } });
  await expect(page.getByText("Follow-up assigned to Maya Chen", { exact: true })).toBeVisible();

  const repeated = await request.post("/api/tickets/RTC-1042/handoff", { data: { owner: "Jordan Lee" } });
  expect(await repeated.json()).toMatchObject({ status: "open", handoff: { owner: "Maya Chen" } });
  await page.reload();
  await expect(page.getByText("Follow-up assigned to Maya Chen", { exact: true })).toBeVisible();
  await expect(page.getByText(/Ask for the failure time/)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("confirmed-handoff.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText("Follow-up assigned to Maya Chen", { exact: true })).toBeVisible();
  const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(hasOverflow).toBe(false);
});
