import type { RunRecord, ToolCallRecord } from '../types';

/** One row of the tool-call distribution. */
export interface DistRow {
  name: string;
  count: number;
  avgMs: number | null;
  failureRate: number;
}

/**
 * Aggregate tool-call records into a per-tool distribution:
 * call count, average duration, failure rate. Sorted by count desc.
 */
export function buildDistribution(calls: ToolCallRecord[]): DistRow[] {
  const byName = new Map<string, { count: number; totalMs: number; msCount: number; failures: number }>();
  for (const c of calls) {
    const entry = byName.get(c.tool_name) ?? { count: 0, totalMs: 0, msCount: 0, failures: 0 };
    entry.count += 1;
    if (typeof c.duration_ms === 'number') {
      entry.totalMs += c.duration_ms;
      entry.msCount += 1;
    }
    if (!c.success) entry.failures += 1;
    byName.set(c.tool_name, entry);
  }
  return Array.from(byName.entries())
    .map(([name, e]) => ({
      name,
      count: e.count,
      avgMs: e.msCount > 0 ? e.totalMs / e.msCount : null,
      failureRate: e.count > 0 ? e.failures / e.count : 0,
    }))
    .sort((a, b) => b.count - a.count);
}

/**
 * Extract security_flags from run metadata (0.16.32+). Returns null
 * when the run carries none — the live chat badge's durable record.
 */
export function runFlags(run: RunRecord): unknown[] | null {
  const md = run.metadata;
  if (!md || typeof md !== 'object') return null;
  const flags = (md as Record<string, unknown>).security_flags;
  return Array.isArray(flags) ? (flags as unknown[]) : null;
}

/** Render a flag entry as its label string ('instruction_override' etc). */
export function flagLabel(flag: unknown): string {
  if (typeof flag === 'object' && flag !== null && 'flag' in (flag as Record<string, unknown>)) {
    return String((flag as Record<string, unknown>).flag);
  }
  return String(flag);
}
