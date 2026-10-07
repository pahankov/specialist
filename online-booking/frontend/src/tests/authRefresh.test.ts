/** Regression tests for the 401/refresh interceptor (P1-2).
 *
 * Covered bugs:
 * 1. Refresh went through apiClient itself -> its 401 re-entered the
 *    interceptor while isRefreshing=true and queued behind itself (hang).
 * 2. Queued retries had no _retry flag -> second 401 caused refresh storms.
 * 3. isRefreshing reset lived inside processQueue (no finally).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { InternalAxiosRequestConfig } from 'axios'
import apiClient, { refreshClient } from '../api/client'

interface StubBehavior {
  refreshCalls: number
  refreshSucceeds: boolean
}

function installStubs(behavior: StubBehavior) {
  const requestAdapter = (config: InternalAxiosRequestConfig) => {
    const auth = (config.headers?.Authorization as string) ?? ''
    if (auth.includes('Bearer new-token')) {
      return Promise.resolve({
        data: 'ok',
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      })
    }
    return Promise.reject({ config, response: { status: 401 } })
  }
  const refreshAdapter = (config: InternalAxiosRequestConfig) => {
    behavior.refreshCalls += 1
    if (behavior.refreshSucceeds) {
      return Promise.resolve({
        data: { access_token: 'new-token' },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      })
    }
    return Promise.reject({ config, response: { status: 401 } })
  }
  refreshClient.defaults.adapter = refreshAdapter as never
  return requestAdapter as never
}

beforeEach(() => {
  vi.unstubAllGlobals()
  // Drop the cached Authorization default: success-path tests set it and
  // it would leak into other tests (requests would skip the 401 flow)
  delete apiClient.defaults.headers.common.Authorization
})

describe('refresh interceptor', () => {
  it('refreshes once and retries the original request', async () => {
    const behavior = { refreshCalls: 0, refreshSucceeds: true }
    const adapter = installStubs(behavior)

    const resp = await apiClient.get('/x', { adapter })
    expect(resp.data).toBe('ok')
    expect(behavior.refreshCalls).toBe(1)
  })

  it('concurrent 401s share a single refresh (no storm)', async () => {
    const behavior = { refreshCalls: 0, refreshSucceeds: true }
    const adapter = installStubs(behavior)

    const [a, b] = await Promise.all([
      apiClient.get('/a', { adapter }),
      apiClient.get('/b', { adapter }),
    ])
    expect(a.data).toBe('ok')
    expect(b.data).toBe('ok')
    expect(behavior.refreshCalls).toBe(1)
  })

  it('failed refresh rejects instead of hanging (no self-deadlock)', async () => {
    const behavior = { refreshCalls: 0, refreshSucceeds: false }
    const adapter = installStubs(behavior)

    // Avoid jsdom navigation on logout redirect
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
      configurable: true,
    })
    try {
      await expect(apiClient.get('/x', { adapter })).rejects.toBeDefined()
      expect(behavior.refreshCalls).toBe(1)
    } finally {
      Object.defineProperty(window, 'location', {
        value: originalLocation,
        writable: true,
        configurable: true,
      })
    }
  }, 10000)
})
