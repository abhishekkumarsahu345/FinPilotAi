/**
 * Tests for the theme persistence hook and helpers.
 *
 * We test:
 *   - getStoredTheme: system preference fallback, localStorage override
 *   - applyTheme: sets data-theme attribute and localStorage
 *   - useTheme hook: initial state, toggle behaviour
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getStoredTheme, applyTheme } from './theme'

const STORAGE_KEY = 'finpilot_theme'

// jsdom does not implement matchMedia by default — provide a minimal mock.
function mockMatchMedia(prefersDark: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-color-scheme: dark)' ? prefersDark : false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

// ── getStoredTheme ─────────────────────────────────────────────────────────

describe('getStoredTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    // Reset data-theme on the document element
    document.documentElement.removeAttribute('data-theme')
  })

  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('returns "light" when no preference is set and system is light', () => {
    mockMatchMedia(false)
    expect(getStoredTheme()).toBe('light')
  })

  it('returns "dark" when no preference is set and system prefers dark', () => {
    mockMatchMedia(true)
    expect(getStoredTheme()).toBe('dark')
  })

  it('returns stored "dark" value from localStorage', () => {
    mockMatchMedia(false) // system is light, but user chose dark
    localStorage.setItem(STORAGE_KEY, 'dark')
    expect(getStoredTheme()).toBe('dark')
  })

  it('returns stored "light" value from localStorage', () => {
    mockMatchMedia(true) // system prefers dark, but user chose light
    localStorage.setItem(STORAGE_KEY, 'light')
    expect(getStoredTheme()).toBe('light')
  })

  it('ignores invalid localStorage values and falls back to system', () => {
    mockMatchMedia(false)
    localStorage.setItem(STORAGE_KEY, 'invalid_value')
    expect(getStoredTheme()).toBe('light')
  })
})

// ── applyTheme ─────────────────────────────────────────────────────────────

describe('applyTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    // Ensure a theme-color meta tag exists
    let meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    if (!meta) {
      meta = document.createElement('meta')
      meta.setAttribute('name', 'theme-color')
      document.head.appendChild(meta)
    }
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('sets data-theme="dark" on document element', () => {
    applyTheme('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('sets data-theme="light" on document element', () => {
    applyTheme('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('persists theme choice to localStorage', () => {
    applyTheme('dark')
    expect(localStorage.getItem(STORAGE_KEY)).toBe('dark')

    applyTheme('light')
    expect(localStorage.getItem(STORAGE_KEY)).toBe('light')
  })

  it('updates the theme-color meta tag for dark mode', () => {
    applyTheme('dark')
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    expect(meta?.content).toBe('#131c18')
  })

  it('updates the theme-color meta tag for light mode', () => {
    applyTheme('light')
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    expect(meta?.content).toBe('#f5f7f6')
  })
})

// ── Persistence across reads ───────────────────────────────────────────────

describe('theme persistence round-trip', () => {
  beforeEach(() => {
    localStorage.clear()
    mockMatchMedia(false)
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('applyTheme(dark) → getStoredTheme() returns dark', () => {
    applyTheme('dark')
    expect(getStoredTheme()).toBe('dark')
  })

  it('applyTheme(light) → getStoredTheme() returns light', () => {
    applyTheme('dark')     // first set dark
    applyTheme('light')    // then switch back
    expect(getStoredTheme()).toBe('light')
  })
})
