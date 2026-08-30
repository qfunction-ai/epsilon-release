import { useState } from 'react';

interface SettingsProps {
  username: string;
  onLogout: () => void;
}

const KEEP_HISTORY_KEY = 'epsilon.keepChatHistory';

export function Settings({ username, onLogout }: SettingsProps) {
  const [keepHistory, setKeepHistory] = useState(() =>
    localStorage.getItem(KEEP_HISTORY_KEY) === '1',
  );

  const toggleKeepHistory = () => {
    const next = !keepHistory;
    setKeepHistory(next);
    localStorage.setItem(KEEP_HISTORY_KEY, next ? '1' : '0');
  };

  return (
    <>
      <h1 className="page-title">Settings</h1>
      <p className="page-subtitle">Account and application configuration</p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '480px' }}>
        {/* Account card */}
        <div className="card">
          <div className="section-header" data-symbol="⊕">Account</div>
          <div style={{ marginBottom: '1rem' }}>
            <label
              style={{
                display: 'block',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.625rem',
                color: 'var(--text-tertiary)',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                marginBottom: '0.375rem',
              }}
            >
              Username
            </label>
            <input className="input" type="text" value={username} readOnly />
          </div>
        </div>

        {/* Model info card */}
        <div className="card">
          <div className="section-header" data-symbol="∂">Model</div>
          <div style={{ marginBottom: '0.75rem' }}>
            <label
              style={{
                display: 'block',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.625rem',
                color: 'var(--text-tertiary)',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                marginBottom: '0.375rem',
              }}
            >
              LLM Provider
            </label>
            <input className="input" type="text" value="Ollama (local)" readOnly />
          </div>
          <div style={{ marginBottom: '0.75rem' }}>
            <label
              style={{
                display: 'block',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.625rem',
                color: 'var(--text-tertiary)',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                marginBottom: '0.375rem',
              }}
            >
              Default Model
            </label>
            <input className="input" type="text" value="nemotron-3-nano:4b" readOnly />
          </div>
        </div>

        {/* Chat behavior card — functional */}
        <div className="card">
          <div className="section-header" data-symbol="≡">Chat</div>
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: '1rem',
            }}
          >
            <div>
              <label
                htmlFor="keep-history-toggle"
                style={{
                  display: 'block',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.625rem',
                  color: 'var(--text-tertiary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  marginBottom: '0.375rem',
                }}
              >
                Keep chat history between vulnerabilities
              </label>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                Off: each vulnerability starts with a clean transcript. On:
                transcripts are restored when you switch back. Applies to
                this browser session only.
              </div>
            </div>
            <button
              id="keep-history-toggle"
              role="switch"
              aria-checked={keepHistory}
              onClick={toggleKeepHistory}
              className={`toggle-switch ${keepHistory ? 'on' : ''}`}
              style={{ flexShrink: 0, marginTop: '0.25rem' }}
            >
              <span className="toggle-knob" />
            </button>
          </div>
        </div>

        {/* Appearance card */}
        <div className="card">
          <div className="section-header" data-symbol="✦">Appearance</div>
          <div>
            <label
              style={{
                display: 'block',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.625rem',
                color: 'var(--text-tertiary)',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                marginBottom: '0.375rem',
              }}
            >
              Theme
            </label>
            <input className="input" type="text" value="Mathematical Chalkboard" readOnly />
          </div>
        </div>

        {/* Logout button */}
        <button className="btn btn-danger" onClick={onLogout} style={{ alignSelf: 'flex-start' }}>
          ⎋ Logout
        </button>
      </div>
    </>
  );
}
