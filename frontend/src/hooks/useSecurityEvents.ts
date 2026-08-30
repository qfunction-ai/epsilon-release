import { useCallback, useEffect, useState } from 'react';
import type { SecurityEvent, SecurityEventType } from '../types';
import { apiFetch, extractApiError } from '../lib/api';

export interface UseSecurityEventsReturn {
  events: SecurityEvent[];
  isLoading: boolean;
  error: string | null;
  filter: SecurityEventType | null;
  setFilter: (filter: SecurityEventType | null) => void;
  refresh: () => void;
}

export function useSecurityEvents(): UseSecurityEventsReturn {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<SecurityEventType | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    setIsLoading(true);
    const params = new URLSearchParams();
    if (filter) params.set('event_type', filter);
    params.set('limit', '200');
    const query = params.toString();

    apiFetch(`/security/events${query ? `?${query}` : ''}`)
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json();
          return data.events as SecurityEvent[];
        }
        const msg = await extractApiError(res, 'Failed to load security events');
        throw new Error(msg);
      })
      .then((events) => setEvents(events))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [filter, refreshKey]);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  return {
    events,
    isLoading,
    error,
    filter,
    setFilter,
    refresh,
  };
}
