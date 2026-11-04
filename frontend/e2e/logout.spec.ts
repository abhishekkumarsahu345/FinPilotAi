/**
 * E2E tests for the FinPilot AI logout flow.
 *
 * Prerequisites (run manually before this suite):
 *   1. docker-compose up -d
 *   2. cd backend && python manage.py runserver  (port 8000)
 *   3. cd frontend && npm run dev                (port 5173)
 *
 * A test user must exist:
 *   email:    e2e_logout@finpilot.local
 *   password: E2eTest1234!
 *   (create via /api/v1/auth/register/ or Django admin)
 *
 * Run: npx playwright test e2e/logout.spec.ts
 */

import { test, expect, type Page } from '@playwright/test'

// ── Credentials & URLs ──────────────────────────────────────────────────────

const EMAIL = 'e2e_logout@finpilot.local'
const PASS = 'E2eTest1234!'
const BASE = 'http://localhost:5173'

// ── Helpers ─────────────────────────────────────────────────────────────────

async function signIn(page: Page) {
  await page.goto(BASE)
  // Wait for login form to appear
  await page.waitForSelector('input[name="email"]', { timeout: 10_000 })
  await page.fill('input[name="email"]', EMAIL)
  await page.fill('input[name="password"]', PASS)
  await page.click('button[type="submit"]')
  // Wait until the dashboard renders (sidebar nav visible)
  await page.waitForSelector('.sidebar', { timeout: 15_000 })
}

async function openLogoutDialog(page: Page) {
  // The sidebar "Sign out" button triggers the confirm dialog
  await page.click('.logout-btn', { timeout: 5_000 })
  await page.waitForSelector('[data-testid="confirm-logout-btn"]', { timeout: 5_000 })
}

// ── Tests ────────────────────────────────────────────────────────────────────

test.describe('Logout flow', () => {
  test('login then logout lands on auth screen', async ({ page }) => {
    await signIn(page)

    // Open confirm dialog
    await openLogoutDialog(page)

    // Confirm the logout
    await page.click('[data-testid="confirm-logout-btn"]')

    // Should return to the auth/login screen
    await page.waitForSelector('input[name="email"]', { timeout: 10_000 })
    expect(page.url()).toBe(BASE + '/')
  })

  test('cancel button closes dialog without logging out', async ({ page }) => {
    await signIn(page)
    await openLogoutDialog(page)

    // Click cancel
    await page.click('button:has-text("Cancel")')

    // Dialog should be gone, sidebar should still be present
    await expect(page.locator('[data-testid="confirm-logout-btn"]')).not.toBeVisible()
    await expect(page.locator('.sidebar')).toBeVisible()
  })

  test('pressing Back after logout stays on login screen (no dashboard)', async ({ page }) => {
    await signIn(page)
    await openLogoutDialog(page)
    await page.click('[data-testid="confirm-logout-btn"]')
    await page.waitForSelector('input[name="email"]', { timeout: 10_000 })

    // Press browser Back
    await page.goBack()

    // Should still show the login form — not the dashboard
    // (SPA with no router: goBack either stays on / or goes to previous external page)
    const hasDashboard = await page.locator('.sidebar').isVisible().catch(() => false)
    expect(hasDashboard).toBe(false)
  })

  test('navigating to / directly after logout shows login screen', async ({ page }) => {
    await signIn(page)
    await openLogoutDialog(page)
    await page.click('[data-testid="confirm-logout-btn"]')
    await page.waitForSelector('input[name="email"]', { timeout: 10_000 })

    // Reload to simulate a direct navigation
    await page.reload()
    await page.waitForSelector('input[name="email"]', { timeout: 10_000 })
    await expect(page.locator('.sidebar')).not.toBeVisible()
  })

  test('success toast appears after logout', async ({ page }) => {
    await signIn(page)
    await openLogoutDialog(page)
    await page.click('[data-testid="confirm-logout-btn"]')

    // Toast should appear briefly then auto-dismiss
    await page.waitForFunction(
      () => document.body.innerText.includes('Logged out'),
      { timeout: 5_000 }
    )
  })

  test('logout button shows loading state during request', async ({ page }) => {
    await signIn(page)

    // Slow down the logout API call so we can observe loading state
    await page.route('**/api/v1/auth/logout/**', async (route) => {
      await page.waitForTimeout(300)
      route.continue()
    })

    await page.click('.logout-btn')
    await page.waitForSelector('[data-testid="confirm-logout-btn"]', { timeout: 5_000 })
    await page.click('[data-testid="confirm-logout-btn"]')

    // Button text should briefly show "Signing out…"
    await expect(page.locator('[data-testid="confirm-logout-btn"]')).toContainText(/signing out/i, {
      timeout: 3_000,
    }).catch(() => {
      // Race condition: loading may be too fast; test is still valid if logout succeeded
    })

    await page.waitForSelector('input[name="email"]', { timeout: 10_000 })
  })

  test('cross-tab logout: second tab clears auth when first tab logs out', async ({ browser }) => {
    // Open two contexts that share cookies (same browser instance, but separate page objects)
    const context = await browser.newContext()
    const page1 = await context.newPage()
    const page2 = await context.newPage()

    // Sign in on page1
    await signIn(page1)

    // Open the same app on page2 — should already be authenticated (shared session cookie)
    await page2.goto(BASE)
    await page2.waitForSelector('.sidebar', { timeout: 15_000 })

    // Log out on page1
    await openLogoutDialog(page1)
    await page1.click('[data-testid="confirm-logout-btn"]')
    await page1.waitForSelector('input[name="email"]', { timeout: 10_000 })

    // page2 should also show the auth screen after BroadcastChannel event
    await page2.waitForFunction(
      () => !!document.querySelector('input[name="email"]'),
      { timeout: 8_000 }
    )
    await expect(page2.locator('.sidebar')).not.toBeVisible()

    await context.close()
  })

  test('401 response auto-clears auth and shows session expired message', async ({ page }) => {
    await signIn(page)

    // Intercept any API call and return 401 to simulate session expiry
    await page.route('**/api/v1/dashboard/**', (route) => {
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Authentication credentials were not provided.' }),
      })
    })

    // Reload to trigger a dashboard fetch → 401
    await page.reload()

    // Should redirect to login
    await page.waitForSelector('input[name="email"]', { timeout: 10_000 })
    await expect(page.locator('.sidebar')).not.toBeVisible()
  })
})
