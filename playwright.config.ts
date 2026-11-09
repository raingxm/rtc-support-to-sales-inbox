import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";

const python = process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python";

export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: "http://127.0.0.1:3100",
    channel: "chrome",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: JSON.stringify(resolve(python)) + " -m uvicorn tests.letter_analyzer:app --host 127.0.0.1 --port 8100",
      url: "http://127.0.0.1:8100/tickets",
    },
    {
      command: "npm run dev -- --port 3100",
      url: "http://127.0.0.1:3100",
      env: { RTC_API_ORIGIN: "http://127.0.0.1:8100", RTC_NEXT_DIST_DIR: ".next-verify" },
    },
  ],
});
