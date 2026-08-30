import { useObservability } from '../hooks/useObservability';
import type { ObservabilityData } from '../types';

export function Observability() {
  const { data, isLoading, error } = useObservability();

  if (isLoading) {
    return (
      <>
        <h1 className="page-title">Observability</h1>
        <p className="page-subtitle">Real-time telemetry — runs, tokens, tools, and security events</p>
        <div style={{ color: 'var(--text-tertiary)', padding: '2rem' }}>Loading…</div>
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        <h1 className="page-title">Observability</h1>
        <p className="page-subtitle">Real-time telemetry — runs, tokens, tools, and security events</p>
        <div style={{ color: 'var(--danger)', padding: '2rem' }}>
          {error || 'No data available'}
        </div>
      </>
    );
  }

  return (
    <>
      <h1 className="page-title">Observability</h1>
      <p className="page-subtitle">Real-time telemetry — runs, tokens, tools, and security events</p>

      {/* Stat cards */}
      <div className="grid-4" style={{ marginBottom: '1.5rem' }}>
        <div className="stat-card">
          <div className="stat-label">Total Runs</div>
          <div className="stat-value">{data.total_runs}</div>
          <div className="stat-sub">
            {data.completed_runs ?? 0} completed · {data.failed_runs ?? 0} failed
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Success Rate</div>
          <div className="stat-value success">{data.success_rate.toFixed(1)}%</div>
          <div className="stat-sub">
            {data.completed_runs ?? 0} of {data.total_runs} runs completed
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Tool Calls</div>
          <div className="stat-value">{data.tool_calls}</div>
          <div className="stat-sub">
            {data.tool_calls_denied ?? 0} denied · {data.tool_calls_executed ?? 0} executed
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Security Events</div>
          <div className="stat-value danger">{data.security_events}</div>
          <div className="stat-sub">
            {data.canary_count ?? 0} canary · {data.secret_count ?? 0} secret · {data.denied_count ?? 0} denied
          </div>
        </div>
      </div>

      {/* Token usage + Tool distribution */}
      <div className="grid-2">
        <TokenUsageCard data={data} />
        <ToolDistributionCard data={data} />
      </div>
    </>
  );
}

function TokenUsageCard({ data }: { data: ObservabilityData }) {
  if (!data.token_usage) {
    return (
      <div className="card">
        <div className="section-header" data-symbol="∂">Token Usage</div>
        <div className="code-block">
          <span className="comment">{'# No token data available'}</span>
        </div>
      </div>
    );
  }

  const { prompt_tokens, completion_tokens, total, total_tokens, budget } = data.token_usage;
  const totalVal = total_tokens ?? total ?? (prompt_tokens + completion_tokens);
  const budgetVal = budget ?? 0;
  const budgetUsed = budgetVal > 0 ? (totalVal / budgetVal) * 100 : 0;

  // Bar chart proportions
  const maxTokens = Math.max(prompt_tokens, completion_tokens, 1);
  const promptBarWidth = (prompt_tokens / maxTokens) * 100;
  const completionBarWidth = (completion_tokens / maxTokens) * 100;
  const budgetBarWidth = Math.min(budgetUsed, 100);

  return (
    <div className="card">
      <div className="section-header" data-symbol="∂">Token Usage</div>
      <div className="code-block">
        <span className="comment">{'# This run (step-by-step)'}</span>
        {'\n'}
        <span className="keyword">prompt_tokens:</span>
        {'     '}
        {prompt_tokens.toLocaleString()}
        {'  '}
        <span style={{ color: 'var(--text-tertiary)' }}>{'─'.repeat(Math.ceil(promptBarWidth / 5))}</span>
        {'\n'}
        <span className="keyword">completion_tokens:</span>
        {' '}
        {completion_tokens.toLocaleString()}
        {'  '}
        <span style={{ color: 'var(--text-tertiary)' }}>{'─'.repeat(Math.ceil(completionBarWidth / 5))}</span>
        {'\n'}
        <span className="keyword">total:</span>
        {'             '}
        {totalVal.toLocaleString()}
        {'\n'}
        <span className="comment">{'# Budget: '}{budgetVal.toLocaleString()}{' tokens per run'}</span>
        {'\n'}
        <span className="comment">{'# Used: '}{budgetUsed.toFixed(1)}%{'  '}</span>
        <span style={{ color: 'var(--accent)' }}>{'█'.repeat(Math.ceil(budgetBarWidth / 5))}{'░'.repeat(20 - Math.ceil(budgetBarWidth / 5))}</span>
      </div>
    </div>
  );
}

function ToolDistributionCard({ data }: { data: ObservabilityData }) {
  if (!data.tool_distribution) {
    return (
      <div className="card">
        <div className="section-header" data-symbol="∑">Tool Distribution</div>
        <div className="code-block">
          <span className="comment">{'# No tool call data available'}</span>
        </div>
      </div>
    );
  }

  const entries = Object.entries(data.tool_distribution);
  const maxCount = Math.max(...entries.map(([, count]) => count), 1);

  return (
    <div className="card">
      <div className="section-header" data-symbol="∑">Tool Distribution</div>
      <div className="code-block">
        {entries.map(([toolName, count], i) => (
          <div key={toolName}>
            <span className={toolName.includes('denied') ? 'danger' : 'keyword'}>
              {toolName}
            </span>
            {'  '}
            {count}
            {' calls  '}
            <span style={{ color: toolName.includes('denied') ? 'var(--danger)' : 'var(--accent)' }}>
              {'█'.repeat(Math.ceil((count / maxCount) * 12))}
            </span>
            {i < entries.length - 1 && '\n'}
          </div>
        ))}
      </div>
    </div>
  );
}
