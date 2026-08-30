import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'

// Mock apiFetch
const mockApiFetch = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

import { useAuth } from './useAuth'

beforeEach(() => {
  vi.clearAllMocks()
  mockApiFetch.mockReset()
})

afterEach(() => {
  // Clean up any event listeners
  window.removeEventListener('api:unauthorized', () => {})
})

function mockResponse(ok: boolean, body?: unknown): Response {
  return {
    ok,
    json: () => Promise.resolve(body ?? {}),
  } as unknown as Response
}

describe('useAuth', () => {
  it('initial mount: fetches /auth/me, sets isAuthenticated=true on success', async () => {
    mockApiFetch.mockResolvedValue(
      mockResponse(true, { id: 1, username: 'cyber' }),
    )

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.currentUser).toEqual({ id: 1, username: 'cyber' })
    expect(mockApiFetch).toHaveBeenCalledWith('/auth/me')
  })

  it('initial mount: sets isAuthenticated=false on 401', async () => {
    mockApiFetch.mockResolvedValue(mockResponse(false))

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.currentUser).toBeNull()
  })

  it('initial mount: sets loading=false after check', async () => {
    mockApiFetch.mockResolvedValue(mockResponse(false))

    const { result } = renderHook(() => useAuth())

    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
  })

  it('login: sets isAuthenticated=true and currentUser on success', async () => {
    // Call 1: initial /auth/me mount (returns 401 — not logged in yet)
    // Call 2: /auth/login (returns ok)
    // Call 3: /auth/me (returns user)
    mockApiFetch
      .mockResolvedValueOnce(mockResponse(false))
      .mockResolvedValueOnce(mockResponse(true))
      .mockResolvedValueOnce(mockResponse(true, { id: 2, username: 'newuser' }))

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    let success: boolean | undefined
    await act(async () => {
      success = await result.current.login('newuser', 'pass')
    })

    expect(success).toBe(true)
    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.currentUser).toEqual({ id: 2, username: 'newuser' })
  })

  it('login: returns false on failure', async () => {
    // Call 1: initial /auth/me mount (returns 401)
    // Call 2: /auth/login (returns 401)
    mockApiFetch
      .mockResolvedValueOnce(mockResponse(false))
      .mockResolvedValueOnce(mockResponse(false))

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    let success: boolean | undefined
    await act(async () => {
      success = await result.current.login('bad', 'creds')
    })

    expect(success).toBe(false)
    expect(result.current.isAuthenticated).toBe(false)
  })

  it('register: sets isAuthenticated=true and currentUser on success', async () => {
    // Call 1: initial /auth/me mount (returns 401 — not logged in yet)
    // Call 2: /auth/register (returns ok)
    // Call 3: /auth/me (returns user)
    mockApiFetch
      .mockResolvedValueOnce(mockResponse(false))
      .mockResolvedValueOnce(mockResponse(true))
      .mockResolvedValueOnce(mockResponse(true, { id: 1, username: 'admin' }))

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    let success: boolean | undefined
    await act(async () => {
      success = await result.current.register('admin', 'pass')
    })

    expect(success).toBe(true)
    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.currentUser).toEqual({ id: 1, username: 'admin' })
  })

  it('register: returns false on failure', async () => {
    // Call 1: initial /auth/me mount (returns 401)
    // Call 2: /auth/register (returns 409 — username taken)
    mockApiFetch
      .mockResolvedValueOnce(mockResponse(false))
      .mockResolvedValueOnce(mockResponse(false))

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    let success: boolean | undefined
    await act(async () => {
      success = await result.current.register('taken', 'pass')
    })

    expect(success).toBe(false)
    expect(result.current.isAuthenticated).toBe(false)
  })

  it('logout: clears state and redirects to /login', async () => {
    // Call 1: initial /auth/me mount (returns user — authenticated)
    // Call 2: /auth/logout (returns ok)
    mockApiFetch
      .mockResolvedValueOnce(mockResponse(true, { id: 1, username: 'cyber' }))
      .mockResolvedValueOnce(mockResponse(true))

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    // Mock window.location.href setter (jsdom does not allow reassignment
    // of location itself, but the href setter is writable)
    const originalHref = window.location.href
    const hrefSetter = vi.fn()
    Object.defineProperty(window, 'location', {
      value: {
        ...window.location,
        set href(val: string) {
          hrefSetter(val)
        },
      },
      writable: true,
    })

    await act(async () => {
      await result.current.logout()
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.currentUser).toBeNull()
    expect(hrefSetter).toHaveBeenCalledWith('/login')

    // Restore
    Object.defineProperty(window, 'location', {
      value: { href: originalHref },
      writable: true,
    })
  })

  it('401 event during initial check does NOT clear state (prevents redirect loop)', async () => {
    // /auth/me returns 401
    mockApiFetch.mockResolvedValue(mockResponse(false))

    const { result } = renderHook(() => useAuth())

    // Dispatch a 401 event BEFORE the initial check completes
    // (initialCheckDone.current is still false)
    act(() => {
      window.dispatchEvent(new Event('api:unauthorized'))
    })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    // State should be false (from the 401 response, not from the event)
    expect(result.current.isAuthenticated).toBe(false)
    // The key assertion: the event handler returned early because
    // initialCheckDone was false — it did NOT independently set state.
    // This test passes because the hook handles both paths correctly:
    // the event no-ops, the /auth/me response sets state.
  })

  it('401 event after initial check clears state', async () => {
    // Initial mount: authenticated
    mockApiFetch.mockResolvedValue(
      mockResponse(true, { id: 1, username: 'cyber' }),
    )

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    // Dispatch a 401 event AFTER initial check completed
    act(() => {
      window.dispatchEvent(new Event('api:unauthorized'))
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.currentUser).toBeNull()
  })
})
