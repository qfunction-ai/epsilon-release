import { useNavigate, useLocation } from 'react-router-dom';
import type { VulnerabilitySummary, YearInfo, VulnState } from '../types';
import { YearSelector } from './YearSelector';

interface SidebarProps {
  vulnerabilities: VulnerabilitySummary[];
  years: YearInfo[];
  selectedYear: number;
  onSelectYear: (year: number) => void;
  onSelectVuln: (year: number, vulnId: string) => void;
  activeVulnId: string | null;
  username: string;
  onLogout: () => void;
}

// Derive the vuln state dot from the summary
function getVulnState(vuln: VulnerabilitySummary): VulnState {
  if (!vuln.has_runtime_defense) return 'no-defense';
  // We can't know if it's "fixed" or "vulnerable" from the summary alone.
  // The sidebar dot reflects whether a runtime defense exists.
  // "fixed" means the defense is active (green), "vulnerable" means exploitable (red).
  // Since the summary only has has_runtime_defense, we use:
  //   - no-defense (gray) when no runtime defense
  //   - vulnerable (red) as default — the student sees the vulnerable state first
  // The detail page toggles between vulnerable/fixed.
  return 'vulnerable';
}

export function Sidebar({
  vulnerabilities,
  years,
  selectedYear,
  onSelectYear,
  onSelectVuln,
  activeVulnId,
  username,
  onLogout,
}: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();

  function handleVulnClick(vuln: VulnerabilitySummary) {
    onSelectVuln(selectedYear, vuln.id);
  }

  function handleNavClick(path: string) {
    navigate(path);
  }

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <span className="epsilon">ε</span>
        <span className="name">Epsilon</span>
      </div>

      {/* Year Selector */}
      <YearSelector
        years={years}
        selectedYear={selectedYear}
        onSelectYear={onSelectYear}
      />

      {/* Vulnerability List */}
      <div className="sidebar-section-label">
        LLM Top 10 — {selectedYear}
      </div>
      <nav className="sidebar-nav vuln-list">
        {vulnerabilities.map((vuln) => {
          const state = getVulnState(vuln);
          const isActive = activeVulnId === vuln.id;
          return (
            <div
              key={vuln.id}
              className={`nav-item${isActive ? ' active' : ''}`}
              onClick={() => handleVulnClick(vuln)}
            >
              <span className="vuln-num">{vuln.owasp_id}</span>
              <span className="vuln-name">{vuln.title}</span>
              <span className={`vuln-state ${state}`} />
            </div>
          );
        })}
      </nav>

      {/* System Section */}
      <div className="sidebar-section-label" style={{ marginTop: '1rem' }}>
        System
      </div>
      <nav className="sidebar-nav">
        <div
          className={`nav-item${location.pathname === '/security' ? ' active' : ''}`}
          onClick={() => handleNavClick('/security')}
        >
          ⚠ Security Events
        </div>
        <div
          className={`nav-item${location.pathname === '/observability' ? ' active' : ''}`}
          onClick={() => handleNavClick('/observability')}
        >
          📊 Observability
        </div>
        <div
          className={`nav-item${location.pathname === '/settings' ? ' active' : ''}`}
          onClick={() => handleNavClick('/settings')}
        >
          ⚙ Settings
        </div>
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <span className="user-name">{username}</span>
        <span
          style={{ color: 'var(--text-tertiary)', fontSize: '0.7rem', cursor: 'pointer' }}
          onClick={onLogout}
          title="Logout"
        >
          ⎋
        </span>
      </div>
    </aside>
  );
}
