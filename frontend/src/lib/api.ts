/**
 * Centralized API access for the Epsilon frontend.
 *
 * All pages should use `apiFetch()` instead of raw `fetch()`.
 * It automatically prepends the base URL and sends credentials (cookies)
 * with every request. The JWT is stored in an httpOnly cookie set by the
 * server — JavaScript cannot access it, preventing token theft via XSS.
 */

/// <reference types="vite/client" />

const API_URL: string = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Block mixed-content requests: if the page is HTTPS but the API URL is HTTP,
// the cookie would be sent in cleartext. Throw instead of silently proceeding.
let _mixedContentBlocked = false
if (
  typeof window !== 'undefined' &&
  window.location.protocol === 'https:' &&
  API_URL.startsWith('http://')
) {
  _mixedContentBlocked = true
  console.error(
    'SECURITY: VITE_API_URL is using HTTP while the page is served over HTTPS. ' +
      'All API requests are blocked. Set VITE_API_URL to an HTTPS URL in production.',
  )
}

/**
 * Normalize RequestInit.headers into a plain Record<string, string>.
 */
function normalizeHeaders(
  headers: RequestInit['headers'] | undefined,
): Record<string, string> {
  if (!headers) return {}
  if (headers instanceof Headers) {
    const out: Record<string, string> = {}
    headers.forEach((value, key) => {
      out[key] = value
    })
    return out
  }
  if (Array.isArray(headers)) {
    const out: Record<string, string> = {}
    for (const [key, value] of headers) {
      out[key] = value
    }
    return out
  }
  return headers as Record<string, string>
}

/**
 * Fetch wrapper that prepends the API base URL and sends credentials (cookies).
 *
 * The JWT httpOnly cookie is sent automatically — no Authorization header needed.
 *
 * On 401 responses, dispatches an `api:unauthorized` event so the auth
 * hook can redirect to login.
 *
 * Usage: `apiFetch('/vulns')` instead of `fetch('http://localhost:8000/vulns', ...)`
 */
export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  if (_mixedContentBlocked) {
    throw new Error(
      'Blocked: API URL uses HTTP while page is served over HTTPS. ' +
        'Set VITE_API_URL to an HTTPS URL.',
    )
  }
  const url = `${API_URL}${path}`
  const isFormData = init.body instanceof FormData
  const baseHeaders: Record<string, string> = isFormData
    ? {}
    : { 'Content-Type': 'application/json' }
  const headers = { ...baseHeaders, ...normalizeHeaders(init.headers) }
  const response = await fetch(url, {
    ...init,
    headers,
    credentials: 'include',
  })

  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent('api:unauthorized'))
  }

  return response
}

/**
 * Extract an error message from an API response.
 */
export async function extractApiError(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const data = await response.json()
    // aislop-ignore-next-line hidden-fallback — fallback IS the API contract
    return data.detail || fallback
  } catch {
    // aislop-ignore-next-line hidden-fallback — non-JSON responses expected
    return fallback
  }
}

export { API_URL }

/** @internal Test-only hook to simulate mixed-content detection */
export function _setMixedContentBlocked(value: boolean) {
  _mixedContentBlocked = value
}
