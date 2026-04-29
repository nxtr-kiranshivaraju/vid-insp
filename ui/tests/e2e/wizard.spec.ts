import { expect, test } from "@playwright/test";

const PARAGRAPH =
  "Workers in the loading bay must wear hard hats and hi-vis vests at all times.\n\nForklifts must not operate within 3 metres of a person on foot.";

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    {
      name: "auth_token",
      value: "dev-token",
      domain: "localhost",
      path: "/",
      httpOnly: false,
    },
  ]);
});

test("full wizard happy path against stubs", async ({ page }) => {
  // Step 1
  await page.goto("/inspections/new");
  await page.getByRole("textbox").fill(PARAGRAPH);
  await page.getByRole("button", { name: /extract intents/i }).click();

  // Step 2 — intents
  await expect(page.getByRole("heading", { name: /Step 2/i })).toBeVisible();
  await expect(page.getByTestId("intent-0")).toBeVisible();
  await page.getByRole("button", { name: /^Approve intents$/i }).click();

  // Step 3 — questions
  await expect(page.getByRole("heading", { name: /Step 3/i })).toBeVisible();
  await expect(page.getByTestId("violator-badge-0")).toContainText("violator_description");
  await page.getByRole("button", { name: /^Approve questions$/i }).click();

  // Step 4 — rules
  await expect(page.getByRole("heading", { name: /Step 4/i })).toBeVisible();
  await expect(page.getByTestId("rule-0")).toBeVisible();
  await page.getByRole("button", { name: /^Approve rules$/i }).click();

  // Step 5 — cameras
  await expect(page.getByRole("heading", { name: /Step 5/i })).toBeVisible();
  await page.getByLabel("Friendly name").fill("Loading bay");
  await page.getByLabel("Timezone").fill("UTC");
  await page.getByLabel("RTSP URL").fill("rtsp://user:pass@cam.local:554/stream");
  await page.getByRole("button", { name: /test connectivity/i }).click();
  await expect(page.getByTestId("probe-result")).toContainText("Connected");
  await page.getByRole("button", { name: /^Add camera$/i }).click();
  await page.getByRole("button", { name: /^Next: Channels$/i }).click();

  // Step 6 — channels
  await expect(page.getByRole("heading", { name: /Step 6/i })).toBeVisible();
  await page.getByLabel("Friendly name").fill("#safety-alerts");
  await page.getByLabel("Webhook URL").fill("https://hooks.slack.com/services/T1/B1/abc");
  await page.getByRole("button", { name: /^Add channel$/i }).click();
  await page.getByRole("button", { name: /^Next: Preview$/i }).click();

  // Step 7 — preview
  await expect(page.getByRole("heading", { name: /Step 7/i })).toBeVisible();
  await expect(page.getByTestId("dsl-preview")).toContainText("apiVersion: vid-insp/v1");
  await expect(page.getByTestId("g1-badge")).toContainText("pass");
  await expect(page.getByTestId("g2-badge")).toContainText("pass");
  await page.getByRole("button", { name: /^Next: Deploy$/i }).click();

  // Step 8 — deploy
  await expect(page.getByRole("heading", { name: /Step 8/i })).toBeVisible();
  await page.getByRole("button", { name: /commit and create deployment/i }).click();
  await expect(page.getByText(/Customer:/)).toBeVisible();
  await page.getByRole("button", { name: /run preflight/i }).click();
  await expect(page.getByTestId("gate-G3_dsl_signature")).toContainText("pass");
  await page.getByTestId("go-live").click();

  // Lands on monitor.
  await expect(page).toHaveURL(/\/monitor\/dep_/);
  await expect(page.getByRole("heading", { name: /Live monitor/i })).toBeVisible();
  await expect(page.getByTestId("status-state")).toContainText("running");
});
