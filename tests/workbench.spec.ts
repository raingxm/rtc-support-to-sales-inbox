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

test("checks a new letter against the source before adding it to the queue", async ({ page, request }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const queue = page.getByRole("complementary", { name: "Ticket queue" });
  const customer = page.getByRole("textbox", { name: "Customer name" });
  const message = page.getByRole("textbox", { name: "Customer message" });
  const analyze = page.getByRole("button", { name: "Analyze letter" });
  const body = "📹 Our recordings sometimes fail.\nWe want to launch a pilot next month.";
  const before = await (await request.get("/api/tickets")).json();

  await page.goto("/");
  await page.getByText("New letter", { exact: true }).click();
  await customer.fill("Cypress Video");

  const rejectedBody = "📹 Our recordings sometimes fail.\nWe want to launch a pilot next quarter.";
  await message.fill(rejectedBody);
  const rejected = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/tickets" && response.request().method() === "POST",
  );
  await analyze.click();
  expect((await rejected).status()).toBe(422);
  await expect(page.getByRole("main").getByRole("alert")).toContainText("could not find this quote");
  await expect(message).toHaveValue(rejectedBody);
  expect(await (await request.get("/api/tickets")).json()).toEqual(before);
  await expect(queue.getByRole("button")).toHaveCount(before.length);

  await message.fill(body);
  await analyze.click();
  await expect(queue.getByRole("button", { name: /RTC-1043.*Cypress Video/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("heading", { name: "Recording failures and pilot" })).toBeVisible();
  await expect(page.getByText("Live analysis", { exact: true })).toBeVisible();
  await expect(page.getByText("Check the recording failures and follow up on the pilot.")).toBeVisible();
  await expect(page.locator("blockquote")).toHaveText("launch a pilot next month");
  await expect(page.locator(".message mark")).toHaveText("launch a pilot next month");
  await expect(page.locator(".message p")).toHaveJSProperty("textContent", body);
  await expect(queue.getByRole("button")).toHaveCount(before.length + 1);
  const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(hasOverflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("live-letter.png"), fullPage: true });
});
