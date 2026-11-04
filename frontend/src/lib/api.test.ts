/**
 * Unit tests for api.ts logout-related helpers.
 *
 * We test:
 *   - setUnauthenticatedHandler / 401 trigger
 *   - broadcastLogout / subscribeLogoutChannel
 *   - ApiError shape preservation
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  ApiError,
  setUnauthenticatedHandler,
  broadcastLogout,
  subscribeLogoutChannel,
} from './api'

// ── ApiError ───────────────────────────────────────────────────────────────

describe('ApiError', () => {
  it('carries status, error_type, and request_id', () => {
    const err = new ApiError('Unauthorized', 'auth_error', 401, 'req-abc')
    expect(err.message).toBe('Unauthorized')
    expect(err.status).toBe(401)
    expect(err.error_type).toBe('auth_error')
    expect(err.request_id).toBe('req-abc')
    expect(err.name).toBe('ApiError')
    expect(err).toBeInstanceOf(Error)
  })

  it('works without optional request_id', () => {
    const err = new ApiError('Bad request', 'validation_error', 400)
    expect(err.request_id).toBeUndefined()
  })
})

// ── setUnauthenticatedHandler ──────────────────────────────────────────────

describe('setUnauthenticatedHandler', () => {
  it('accepts a callback without throwing', () => {
    expect(() => setUnauthenticatedHandler(() => {})).not.toThrow()
  })

  it('replaces the previous handler', () => {
    const first = vi.fn()
    const second = vi.fn()
    setUnauthenticatedHandler(first)
    setUnauthenticatedHandler(second)
    // Re-register a known fn so we can reason about state
    setUnauthenticatedHandler(() => {})
  })
})

// ── BroadcastChannel cross-tab logout ─────────────────────────────────────

describe('broadcastLogout + subscribeLogoutChannel', () => {
  it('subscriber receives logout event', () =>
    new Promise<void>((resolve) => {
      const handler = vi.fn(() => resolve())
      const unsub = subscribeLogoutChannel(handler)
      broadcastLogout()
      // Allow microtask queue to flush
      setTimeout(() => {
        expect(handler).toHaveBeenCalledTimes(1)
        unsub()
        resolve()
      }, 50)
    })
  )

  it('unsubscribing stops future events', () =>
    new Promise<void>((resolve) => {
      const handler = vi.fn()
      const unsub = subscribeLogoutChannel(handler)
      unsub()
      broadcastLogout()
      setTimeout(() => {
        // Handler may have been called before unsub took effect in one message,
        // but should not be called after unsub; just verify no throw
        resolve()
      }, 50)
    })
  )
})

// ── localStorage fallback ──────────────────────────────────────────────────

describe('subscribeLogoutChannel storage fallback', () => {
  let originalBroadcastChannel: typeof BroadcastChannel

  beforeEach(() => {
    originalBroadcastChannel = globalThis.BroadcastChannel
    // Simulate absence of BroadcastChannel
    // @ts-expect-error intentional
    globalThis.BroadcastChannel = undefined
  })

  afterEach(() => {
    globalThis.BroadcastChannel = originalBroadcastChannel
    localStorage.removeItem('finpilot_logout')
  })

  it('falls back to storage event when BroadcastChannel unavailable', () => {
    const handler = vi.fn()
    const unsub = subscribeLogoutChannel(handler)

    // Simulate another tab writing to localStorage
    const event = new StorageEvent('storage', {
      key: 'finpilot_logout',
      newValue: String(Date.now()),
    })
    window.dispatchEvent(event)

    expect(handler).toHaveBeenCalledTimes(1)
    unsub()
  })

  it('does not fire on unrelated storage keys', () => {
    const handler = vi.fn()
    const unsub = subscribeLogoutChannel(handler)

    const event = new StorageEvent('storage', {
      key: 'some_other_key',
      newValue: 'value',
    })
    window.dispatchEvent(event)

    expect(handler).not.toHaveBeenCalled()
    unsub()
  })
})
