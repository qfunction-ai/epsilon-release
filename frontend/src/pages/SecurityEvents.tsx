import { useSecurityEvents } from '../hooks/useSecurityEvents';
import type { SecurityEventType } from '../types';

// Map event types to dot colors
const EVENT_DOT_CLASS: Record<string, string> = {
  tool_denied: 'danger',
  canary_detected: 'warning',
  secret_detected: 'warning',
  injection_detected: 'warning',
  tool_executed: 'info',
  message_sent: 'success',
};

// Filter options
const FILTERS: { label: string; value: SecurityEventType | null }[] = [
  { label: 'All Events', value: null },
  { label: 'Tool Denied', value: 'tool_denied' },
  { label: 'Canary Detected', value: 'canary_detected' },
  { label: 'Secret Detected', value: 'secret_detected' },
  { label: 'Injection Detected', value: 'injection_detected' },
];

export function SecurityEvents() {
  const { events, isLoading, error, filter, setFilter } = useSecurityEvents();

  return (
    <>
      <h1 className="page-title">Security Events</h1>
      <p className="page-subtitle">Append-only audit log — incident reconstruction timeline</p>

      {/* Filter buttons */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {FILTERS.map((f) => (
          <button
            key={f.label}
            className="btn btn-secondary"
            style={{
              fontSize: '0.75rem',
              ...(filter === f.value
                ? {
                    borderColor: 'var(--accent)',
                    color: 'var(--accent)',
                  }
                : {}),
            }}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Events table */}
      <div className="card" style={{ padding: 0 }}>
        {isLoading && (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
            Loading events…
          </div>
        )}
        {error && (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--danger)' }}>
            Error: {error}
          </div>
        )}
        {!isLoading && !error && events.length === 0 && (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
            No security events recorded.
          </div>
        )}
        {!isLoading && !error && events.length > 0 && (
          <table className="events-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Event Type</th>
                <th>Tool</th>
                <th>Reason</th>
                <th>Vuln</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>{formatTime(event.timestamp)}</td>
                  <td>
                    <span className="event-type">
                      <span className={`event-dot ${EVENT_DOT_CLASS[event.event_type] || 'info'}`} />
                      {event.event_type}
                    </span>
                  </td>
                  <td>{event.tool_name}</td>
                  <td>{event.reason}</td>
                  <td>
                    {event.vuln_id ? (
                      <span className="badge badge-danger">{event.vuln_id}</span>
                    ) : (
                      <span className="badge badge-muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
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
