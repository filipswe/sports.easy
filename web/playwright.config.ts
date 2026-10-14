import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  timeout: 45_000,
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command:
        "../.venv/bin/alembic upgrade head && ../.venv/bin/python -m app.cli seed && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100 --no-access-log",
      cwd: "../backend",
      url: "http://127.0.0.1:8100/api/ready",
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        DATABASE_URL:
          "sqlite:///" + join(tmpdir(), `sports-easy-e2e-${process.pid}.db`),
        PUBLIC_ORIGIN: "http://127.0.0.1:3100",
        APP_DATA_MODE: "demo",
        GROQ_API_KEY: "",
      },
    },
    {
      command: "npm run dev -- --port 3100",
      url: "http://127.0.0.1:3100",
      reuseExistingServer: false,
      timeout: 90_000,
      env: {
        API_INTERNAL_URL: "http://127.0.0.1:8100",
        NEXT_TELEMETRY_DISABLED: "1",
      },
    },
  ],
});
