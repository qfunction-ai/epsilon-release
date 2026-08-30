import { useState, useEffect, useCallback, useRef } from 'react'
import { apiFetch, extractApiError } from '../lib/api'
import type {
  YearInfo,
  VulnerabilitySummary,
  VulnerabilityDetail,
  CodeComparison,
} from '../types'

export function useVulnerabilities() {
  const [years, setYears] = useState<YearInfo[]>([])
  const [selectedYear, setSelectedYear] = useState<number | null>(null)
  const [vulnerabilities, setVulnerabilities] = useState<
    VulnerabilitySummary[]
  >([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  // Fetch all years on mount
  useEffect(() => {
    const controller = new AbortController()
    abortRef.current = controller

    apiFetch('/vulns', { signal: controller.signal })
      .then(async (res) => {
        if (controller.signal.aborted) return
        if (res.ok) {
          const data = (await res.json()) as YearInfo[]
          if (!controller.signal.aborted) {
            setYears(data)
            // Default to the latest year
            const latest = data.find((y) => y.latest) ?? data[0]
            if (latest) {
              setSelectedYear(latest.year)
              setVulnerabilities(latest.entries)
            }
          }
        } else {
          const msg = await extractApiError(res, 'Failed to load vulnerabilities')
          if (!controller.signal.aborted) {
            setError(msg)
          }
        }
      })
      .catch((err) => {
        if (
          err instanceof DOMException &&
          err.name === 'AbortError'
        )
          return
        if (!controller.signal.aborted) {
          setError('Connection error')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      })

    return () => {
      if (abortRef.current) {
        abortRef.current.abort()
      }
    }
  }, [])

  /**
   * Change the selected year. Updates the vulnerability list to that year's entries.
   */
  const selectYear = useCallback(
    (year: number) => {
      setSelectedYear(year)
      const yearInfo = years.find((y) => y.year === year)
      setVulnerabilities(yearInfo?.entries ?? [])
    },
    [years],
  )

  /**
   * Fetch full details for a specific vulnerability.
   */
  const getVulnerability = useCallback(
    async (year: number, id: string): Promise<VulnerabilityDetail | null> => {
      try {
        const res = await apiFetch(`/vulns/${year}/${id}`)
        if (res.ok) {
          return (await res.json()) as VulnerabilityDetail
        }
        return null
      } catch {
        return null
      }
    },
    [],
  )

  /**
   * Fetch the side-by-side code comparison for a vulnerability.
   */
  const getCodeComparison = useCallback(
    async (year: number, id: string): Promise<CodeComparison | null> => {
      try {
        const res = await apiFetch(`/vulns/${year}/${id}/code`)
        if (res.ok) {
          return (await res.json()) as CodeComparison
        }
        return null
      } catch {
        return null
      }
    },
    [],
  )

  return {
    years,
    selectedYear,
    selectYear,
    vulnerabilities,
    loading,
    error,
    getVulnerability,
    getCodeComparison,
  }
}
