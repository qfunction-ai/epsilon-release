import { useCallback, useEffect, useState } from 'react';
import type { ObservabilityData, RunRecord, ToolCallRecord } from '../types';
import { apiFetch, extractApiError } from '../lib/api';

export interface UseObservabilityReturn {
  data: ObservabilityData | null;
  toolCalls: ToolCallRecord[];
  runs: RunRecord[];
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useObservability(): UseObservabilityReturn {
  const [data, setData] = useState<ObservabilityData | null>(null);
  const [toolCalls, setToolCalls] = useState<ToolCallRecord[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    setIsLoading(true);
    // Overview (aggregate) + scoped row data: tool calls and recent runs.
    // Run metadata carries security_flags since 0.16.32 — the durable
    // companion to the live chat badge.
    const overviewP = apiFetch('/observability/overview')
      .then(async (res) => {
        if (res.ok) return (await res.json()) as ObservabilityData;
        const msg = await extractApiError(res, 'Failed to load observability data');
        throw new Error(msg);
      });
    const toolCallsP = apiFetch('/observability/tool-calls?limit=100')
      .then(async (res) => {
        if (res.ok) return (await res.json()) as { tool_calls: ToolCallRecord[] };
        // Row endpoints failing must not kill the page (overview still renders)
        return { tool_calls: [] as ToolCallRecord[] };
      })
      .catch(() => ({ tool_calls: [] as ToolCallRecord[] }));
    const runsP = apiFetch('/observability/runs?limit=20')
      .then(async (res) => {
        if (res.ok) return (await res.json()) as { runs: RunRecord[] };
        return { runs: [] as RunRecord[] };
      })
      .catch(() => ({ runs: [] as RunRecord[] }));

    Promise.all([overviewP, toolCallsP, runsP])
      .then(([overview, calls, runData]) => {
        setData(overview);
        setToolCalls(calls.tool_calls);
        setRuns(runData.runs);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [refreshKey]);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  return {
    data,
    toolCalls,
    runs,
    isLoading,
    error,
    refresh,
  };
}
