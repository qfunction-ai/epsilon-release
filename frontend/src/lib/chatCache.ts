import type { ChatMessage } from '../types'

/**
 * In-memory per-vulnerability chat transcript cache.
 *
 * Survives client-side navigation (module state lives as long as the SPA
 * session); lost on browser refresh by design — v1 scope. Persisted
 * history would need a backend endpoint and Letta message reconstruction,
 * decided separately (see PER_VULN_STATE_PLAN.md).
 *
 * Keyed by `${year}:${vuln_id}` — vulnerabilities in different years may
 * share a vuln_id.
 */
const cache = new Map<string, ChatMessage[]>()

export const chatCache = {
  save: (key: string, msgs: ChatMessage[]) => {
    cache.set(key, msgs)
  },
  load: (key: string): ChatMessage[] | undefined => cache.get(key),
  drop: (key: string) => {
    cache.delete(key)
  },
}
