import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://localhost:${process.env.UI_PORT ?? "3100"}`,
    extraHTTPHeaders: { Authorization: "Bearer dev-token" },
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "npx tsx stubs/compiler-stub.ts",
      port: 8001,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: { COMPILER_STUB_PORT: "8001" },
    },
    {
      command: "npx tsx stubs/runtime-stub.ts",
      port: 8002,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: { RUNTIME_STUB_PORT: "8002" },
    },
    {
      // Production build avoids first-hit JIT compile delays that flake the e2e timing.
      command: `sh -c "npx next build && npx next start -p ${process.env.UI_PORT ?? "3100"}"`,
      port: Number(process.env.UI_PORT ?? "3100"),
      reuseExistingServer: !process.env.CI,
      timeout: 240_000,
      env: {
        AUTH_TOKEN: "dev-token",
        COMPILER_URL: "http://localhost:8001",
        RUNTIME_URL: "http://localhost:8002",
      },
    },
  ],
});
