import type { ReactNode } from 'react';
import type { VulnerabilitySummary, YearInfo } from '../types';
import { Sidebar } from './Sidebar';

interface LayoutProps {
  children: ReactNode;
  vulnerabilities: VulnerabilitySummary[];
  years: YearInfo[];
  selectedYear: number;
  onSelectYear: (year: number) => void;
  onSelectVuln: (year: number, vulnId: string) => void;
  activeVulnId: string | null;
  username: string;
  onLogout: () => void;
}

// Ghost equations for the chalkboard background
const GHOST_EQUATIONS = [
  { text: 'ε = lim(n→∞) 1/n', style: { top: '8%', left: '5%', fontSize: '3rem', transform: 'rotate(-5deg)' } },
  { text: '∀x ∈ S', style: { top: '35%', right: '8%', fontSize: '2.5rem', transform: 'rotate(3deg)' } },
  { text: 'P(A|B) = P(B|A)P(A) / P(B)', style: { top: '60%', left: '3%', fontSize: '2rem', transform: 'rotate(-2deg)' } },
  { text: '∑ᵢ εᵢ ≤ ε', style: { bottom: '10%', right: '15%', fontSize: '2.5rem', transform: 'rotate(4deg)' } },
];

export function Layout({
  children,
  vulnerabilities,
  years,
  selectedYear,
  onSelectYear,
  onSelectVuln,
  activeVulnId,
  username,
  onLogout,
}: LayoutProps) {
  return (
    <div className="layout-root">
      <Sidebar
        vulnerabilities={vulnerabilities}
        years={years}
        selectedYear={selectedYear}
        onSelectYear={onSelectYear}
        onSelectVuln={onSelectVuln}
        activeVulnId={activeVulnId}
        username={username}
        onLogout={onLogout}
      />
      <main className="main-content">
        {/* Ghost equations in background */}
        {GHOST_EQUATIONS.map((eq, i) => (
          <div
            key={i}
            className="ghost-equation"
            style={eq.style}
          >
            {eq.text}
          </div>
        ))}
        {/* Page content */}
        <div style={{ position: 'relative', zIndex: 1 }}>
          {children}
        </div>
      </main>
    </div>
  );
}
