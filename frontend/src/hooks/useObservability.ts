import { useCallback, useEffect, useState } from 'react';
import type { ObservabilityData } from '../types';
import { apiFetch, extractApiError } from '../lib/api';

export interface UseObservabilityReturn {
  data: ObservabilityData | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useObservability(): UseObservabilityReturn {
  const [data, setData] = useState<ObservabilityData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    setIsLoading(true);
    apiFetch('/observability/overview')
      .then(async (res) => {
        if (res.ok) {
          return (await res.json()) as ObservabilityData;
        }
        const msg = await extractApiError(res, 'Failed to load observability data');
        throw new Error(msg);
      })
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [refreshKey]);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  return {
    data,
    isLoading,
    error,
    refresh,
  };
}
