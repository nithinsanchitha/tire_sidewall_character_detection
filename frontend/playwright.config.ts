import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests",
  timeout: 120000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    launchOptions: { executablePath: process.env.CHROMIUM_PATH },
  },
  webServer: [
    {
      command: `${process.env.PYTHON_BIN || ".venv/bin/python"} -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log`,
      cwd: "..",
      port: 8000,
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173",
      port: 5173,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
