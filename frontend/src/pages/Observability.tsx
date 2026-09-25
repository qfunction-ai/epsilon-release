import { useObservability } from '../hooks/useObservability';
import type { RunRecord } from '../types';
import { buildDistribution, runFlags, flagLabel } from '../lib/obsStats';

export function Observability() {
  const { data, toolCalls, runs, isLoading, error, refresh } = useObservability();

  if (isLoading) {
    return (
      <>
        <h1 className="page-title">Observability</h1>
        <div style={{ color: 'var(--text-tertiary)', padding: '2rem' }}>Loading…</div>
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        <h1 className="page-title">Observability</h1>
        <div className="card" style={{ color: 'var(--danger)', padding: '2rem' }}>
          Error: {error ?? 'No data'}
        </div>
      </>
    );
  }

  // Tool-call distribution from row data (scoped to the caller's agents)
  const dist = buildDistribution(toolCalls);
  const maxCount = Math.max(1, ...dist.map((d) => d.count));
  const flagCount = runs.filter((r) => Array.isArray(runFlags(r)) && runFlags(r)!.length > 0).length;

  return (
    <>
      <h1 className="page-title">Observability</h1>
      <p className="page-subtitle">
        Run, tool, and security telemetry — the durable record behind the live badge
      </p>

      {/* Stat chips */}
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
        <StatChip label="Runs" value={String(data.total_runs)} />
        {data.completed_runs !== undefined && (
          <StatChip label="Completed" value={String(data.completed_runs)} tone="ok" />
        )}
        {data.failed_runs !== undefined && (
          <StatChip label="Failed" value={String(data.failed_runs)} tone={data.failed_runs > 0 ? 'danger' : undefined} />
        )}
        <StatChip label="Success rate" value={`${data.success_rate.toFixed(1)}%`} />
        <StatChip label="Tool calls" value={String(data.tool_calls)} />
        <StatChip label="Security events" value={String(data.security_events)} tone={data.security_events > 0 ? 'warn' : undefined} />
        <StatChip label="Flagged runs" value={String(flagCount)} tone={flagCount > 0 ? 'warn' : undefined} />
        {data.token_usage && (
          <StatChip label="Tokens (prompt/completion)" value={`${data.token_usage.prompt_tokens} / ${data.token_usage.completion_tokens}`} />
        )}
      </div>

      {/* Tool-call distribution */}
      <div className="card" style={{ padding: '1rem 1.25rem', marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '0.9rem', margin: '0 0 0.75rem' }}>Tool-call distribution</h2>
        {dist.length === 0 ? (
          <div style={{ color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>No tool calls recorded yet.</div>
        ) : (
          dist.map((d) => (
            <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.4rem' }}>
              <div style={{ width: '15rem', fontFamily: 'var(--font-mono, monospace)', fontSize: '0.78rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {d.name}
              </div>
              <div style={{ flex: 1, height: '0.7rem', background: 'rgba(127,127,127,0.15)', borderRadius: '2px', overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${(d.count / maxCount) * 100}%`,
                    height: '100%',
                    background: d.failureRate > 0.5 ? 'var(--danger)' : 'var(--accent)',
                  }}
                />
              </div>
              <div style={{ width: '6.5rem', textAlign: 'right', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                {d.count} calls
              </div>
              <div style={{ width: '7rem', textAlign: 'right', fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
                {d.avgMs ? `${Math.round(d.avgMs)}ms avg` : ''}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Recent runs */}
      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '1rem 1.25rem 0.5rem' }}>
          <h2 style={{ fontSize: '0.9rem', margin: 0 }}>Recent runs</h2>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: '0.25rem 0 0' }}>
            Run metadata carries security flags (0.16.32+) — the durable record for runs whose live chat badge is gone after reload
          </p>
        </div>
        {runs.length === 0 ? (
          <div style={{ padding: '1.5rem', color: 'var(--text-tertiary)' }}>No runs recorded yet.</div>
        ) : (
          <table className="events-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Vuln</th>
                <th>Status</th>
                <th>Stop reason</th>
                <th>Flags</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <RunRow key={r.id} run={r} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div style={{ marginTop: '1rem' }}>
        <button className="btn btn-secondary" onClick={refresh}>Refresh</button>
      </div>
    </>
  );
}


function RunRow({ run }: { run: RunRecord }) {
  const flags = runFlags(run);
  return (
    <tr>
      <td>{run.created_at ? formatTime(run.created_at) : '—'}</td>
      <td>
        {run.vuln_id ? (
          <span className="badge badge-danger">{run.vuln_id}</span>
        ) : (
          <span className="badge badge-muted">—</span>
        )}
      </td>
      <td>{run.status ?? '—'}</td>
      <td>{run.stop_reason ?? '—'}</td>
      <td>
        {flags && flags.length > 0 ? (
          flags.map((f, i) => {
            const label = flagLabel(f);
            return (
              <span key={i} className="badge badge-warning" style={{ marginRight: '0.3rem' }}>
                {label}
              </span>
            );
          })
        ) : (
          <span style={{ color: 'var(--text-tertiary)' }}>—</span>
        )}
      </td>
    </tr>
  );
}

function StatChip({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: 'ok' | 'warn' | 'danger';
}) {
  const color =
    tone === 'danger'
      ? 'var(--danger)'
      : tone === 'warn'
        ? 'var(--warning, #d4a017)'
        : tone === 'ok'
          ? 'var(--success, #3a7d44)'
          : 'var(--text-primary)';
  return (
    <div className="card" style={{ padding: '0.5rem 0.9rem', minWidth: '7rem' }}>
      <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </div>
      <div style={{ fontSize: '1.1rem', fontWeight: 600, color }}>{value}</div>
    </div>
  );
}



function formatTime(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { hour12: false });
  } catch {
    return timestamp;
  }
}
