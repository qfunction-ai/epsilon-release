import { useState, useCallback, useRef, useEffect } from 'react'
import { apiFetch, extractApiError } from '../lib/api'

export function useApiFetch<T>(
  url: string,
  options?: {
    /** Error message for non-ok API responses (e.g. "Failed to load dashboard") */
    errorMessage?: string
    /** Error message for network/connection failures (e.g. "Connection error") */
    connectionErrorMessage?: string
    /** Whether to fetch immediately on mount (default: true) */
    immediate?: boolean
  },
) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(options?.immediate !== false)
  const [error, setError] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  const fetch = useCallback(
    async (overrideUrl?: string) => {
      const targetUrl = overrideUrl ?? url

      // Abort any in-flight request
      if (abortRef.current) {
        abortRef.current.abort()
      }
      const controller = new AbortController()
      abortRef.current = controller

      setLoading(true)
      setError('')

      try {
        const res = await apiFetch(targetUrl, { signal: controller.signal })
        if (controller.signal.aborted) return

        if (res.ok) {
          const json = await res.json()
          if (!controller.signal.aborted) {
            setData(json)
          }
        } else {
          const msg = await extractApiError(
            res,
            options?.errorMessage || 'Failed to load data',
          )
          if (!controller.signal.aborted) {
            setError(msg)
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        if (!controller.signal.aborted) {
          setError(
            options?.connectionErrorMessage ||
              options?.errorMessage ||
              'Connection error',
          )
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    },
    [url, options?.errorMessage, options?.connectionErrorMessage],
  )

  useEffect(() => {
    if (options?.immediate !== false) {
      fetch()
    }
    return () => {
      if (abortRef.current) {
        abortRef.current.abort()
      }
    }
  }, [fetch, options?.immediate])

  return { data, loading, error, refetch: fetch, setData, setError }
}
