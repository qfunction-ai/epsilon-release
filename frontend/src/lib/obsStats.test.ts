import { describe, it, expect } from 'vitest';
import { buildDistribution, runFlags, flagLabel } from './obsStats';
import type { RunRecord, ToolCallRecord } from '../types';

function tc(over: Partial<ToolCallRecord>): ToolCallRecord {
  return { id: 'x', step_id: 's', tool_name: 't', success: true, ...over };
}

describe('buildDistribution', () => {
  it('aggregates count, avg duration, and failure rate per tool, sorted by count', () => {
    const rows = buildDistribution([
      tc({ tool_name: 'archival_memory_search', duration_ms: 100, success: true }),
      tc({ tool_name: 'archival_memory_search', duration_ms: 300, success: false }),
      tc({ tool_name: 'file_read' }),
    ]);
    expect(rows[0]).toEqual({
      name: 'archival_memory_search',
      count: 2,
      avgMs: 200,
      failureRate: 0.5,
    });
    expect(rows[1].name).toBe('file_read');
    expect(rows[1].avgMs).toBeNull();
    expect(rows[1].failureRate).toBe(0);
  });

  it('returns empty for no calls', () => {
    expect(buildDistribution([])).toEqual([]);
  });

  it('ignores null durations in the average', () => {
    const rows = buildDistribution([
      tc({ tool_name: 'a', duration_ms: 100 }),
      tc({ tool_name: 'a' }),
    ]);
    expect(rows[0].avgMs).toBe(100);
  });
});

describe('runFlags', () => {
  it('extracts security_flags array from 0.16.32 run metadata', () => {
    const run = {
      id: 'r1',
      metadata: { security_flags: [{ flag: 'instruction_override', tool_name: 'archival_memory_search' }] },
    } as RunRecord;
    expect(runFlags(run)).toEqual([
      { flag: 'instruction_override', tool_name: 'archival_memory_search' },
    ]);
  });

  it('returns null for runs without flags', () => {
    expect(runFlags({ id: 'r1', metadata: null } as RunRecord)).toBeNull();
    expect(runFlags({ id: 'r1' } as RunRecord)).toBeNull();
    expect(runFlags({ id: 'r1', metadata: { error: 'x' } } as RunRecord)).toBeNull();
  });
});

describe('flagLabel', () => {
  it('reads .flag from dict entries', () => {
    expect(flagLabel({ flag: 'instruction_override' })).toBe('instruction_override');
  });
  it('passes through plain strings', () => {
    expect(flagLabel('raw')).toBe('raw');
  });
});
