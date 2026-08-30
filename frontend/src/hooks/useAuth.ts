import { useState, useEffect, useCallback, useRef } from 'react'
import { apiFetch } from '../lib/api'

interface CurrentUser {
  id: number
  username: string
}

/**
 * Auth hook for the Epsilon frontend.
 *
 * JWT is stored in an httpOnly cookie set by the server. JavaScript cannot
 * access the token directly — credentials are sent automatically via
 * `credentials: 'include'` in apiFetch. This is the secure pattern a
 * security teaching app should model.
 *
 * Usage:
 *   const { isAuthenticated, currentUser, loading, login, logout } = useAuth()
 */
export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false)
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(true)

  // Track whether the initial /auth/me check has completed.
  // Prevents the 401 event handler from causing a redirect loop
  // during the initial mount when the user is simply not logged in yet.
  const initialCheckDone = useRef(false)

  // On mount, validate the cookie by fetching /auth/me
  useEffect(() => {
    apiFetch('/auth/me')
      .then((res) => {
        if (res.ok) {
          return res.json().then((data) => {
            setIsAuthenticated(true)
            setCurrentUser(data)
          })
        } else {
          setIsAuthenticated(false)
          setCurrentUser(null)
        }
      })
      .catch(() => {
        // Network error — might be transient, keep current state
      })
      .finally(() => {
        initialCheckDone.current = true
        setLoading(false)
      })
  }, [])

  // Listen for centralized 401 events from apiFetch().
  // Only redirect if the user was previously authenticated —
  // a 401 on initial mount is just "not logged in yet", not a session expiry.
  useEffect(() => {
    const handleUnauthorized = () => {
      if (!initialCheckDone.current) return
      setIsAuthenticated(false)
      setCurrentUser(null)
      // Use React state, not window.location, to avoid reload loops.
      // App.tsx will redirect to /login when isAuthenticated is false.
    }
    window.addEventListener('api:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('api:unauthorized', handleUnauthorized)
  }, [])

  /**
   * Log in with username/password. Server sets httpOnly cookie.
   * Returns true on success, false on failure.
   */
  const login = useCallback(
    async (username: string, password: string): Promise<boolean> => {
      try {
        const res = await apiFetch('/auth/login', {
          method: 'POST',
          body: JSON.stringify({ username, password }),
        })

        if (res.ok) {
          setIsAuthenticated(true)
          // Fetch user info
          const meRes = await apiFetch('/auth/me')
          if (meRes.ok) {
            const meData = await meRes.json()
            setCurrentUser(meData)
          }
          return true
        }
        return false
      } catch {
        return false
      }
    },
    [],
  )

  /**
   * Register the initial admin account (first-run setup only).
   * Server sets httpOnly cookie on success.
   * Returns true on success, false on failure.
   */
  const register = useCallback(
    async (username: string, password: string): Promise<boolean> => {
      try {
        const res = await apiFetch('/auth/register', {
          method: 'POST',
          body: JSON.stringify({
            username,
            password,
            confirm_password: password,
          }),
        })

        if (res.ok) {
          setIsAuthenticated(true)
          const meRes = await apiFetch('/auth/me')
          if (meRes.ok) {
            const meData = await meRes.json()
            setCurrentUser(meData)
          }
          return true
        }
        return false
      } catch {
        return false
      }
    },
    [],
  )

  /**
   * Log out. Call server to clear cookie, then redirect to /login.
   */
  const logout = useCallback(async () => {
    try {
      await apiFetch('/auth/logout', { method: 'POST' })
    } catch {
      // Even if the server call fails, clear client-side state
    }
    setIsAuthenticated(false)
    setCurrentUser(null)
    window.location.href = '/login'
  }, [])

  return {
    isAuthenticated,
    currentUser,
    loading,
    login,
    register,
    logout,
  }
}
