import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  // Run tests sequentially (avoids DB state conflicts with shared dev server)
  workers: 1,
  retries: 0,
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    // Preserve cookies/session between steps inside each test
    storageState: undefined,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // We don't auto-start the server; the user starts it manually.
  // The tests skip gracefully if the server is not running.
  webServer: undefined,
})
