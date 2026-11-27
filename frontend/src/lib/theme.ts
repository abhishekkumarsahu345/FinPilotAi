/**
 * theme.ts — Dark mode hook for FinPilot AI
 *
 * Strategy:
 *   1. On first visit: read system prefers-color-scheme.
 *   2. After user picks a theme: persist to localStorage.
 *   3. `index.html` runs an inline script BEFORE React loads to set
 *      `data-theme` on <html> — this prevents any flash of the wrong theme.
 *   4. This hook reads/writes that attribute and keeps it in sync.
 */

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'finpilot_theme'

/**
 * Read the effective theme from localStorage or the system.
 * This runs synchronously (no React) and is also called by the inline
 * script in index.html.
 */
export function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // localStorage unavailable (private browsing edge case)
  }
  // Fall back to system preference
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Persist and apply a theme choice. */
export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme)
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // ignore
  }
  // Update the browser theme-color meta tag so mobile chrome bars match
  const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
  if (meta) {
    meta.content = theme === 'dark' ? '#131c18' : '#f5f7f6'
  }
}

/** React hook: returns [currentTheme, toggleFn] */
import { useState, useCallback, useEffect } from 'react'

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    // Read from the attribute already set by the inline script.
    const attr = document.documentElement.getAttribute('data-theme')
    if (attr === 'light' || attr === 'dark') return attr
    return getStoredTheme()
  })

  // Keep the HTML attribute in sync with React state on mount
  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const toggle = useCallback(() => {
    setTheme(prev => {
      const next = prev === 'light' ? 'dark' : 'light'
      applyTheme(next)
      return next
    })
  }, [])

  return [theme, toggle]
}
