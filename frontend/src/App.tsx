import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { useVulnerabilities } from './hooks/useVulnerabilities';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { VulnerabilityMenu } from './pages/VulnerabilityMenu';
import { VulnerabilityDetail } from './pages/VulnerabilityDetail';
import { SecurityEvents } from './pages/SecurityEvents';
import { Observability } from './pages/Observability';
import { Settings } from './pages/Settings';

export default function App() {
  const { isAuthenticated, currentUser, loading, login, register, logout } = useAuth();
  const {
    years,
    selectedYear,
    selectYear,
    vulnerabilities,
  } = useVulnerabilities();
  const navigate = useNavigate();

  // Show nothing while checking auth
  if (loading) {
    return null;
  }

  // Not authenticated — show login
  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/login" element={
          <Login
            onLogin={async (u, p) => { await login(u, p); }}
            onRegister={async (u, p) => { await register(u, p); }}
          />
        } />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  // Authenticated — show app
  const username = currentUser?.username ?? 'user';

  function handleSelectVuln(year: number, vulnId: string) {
    navigate(`/vuln/${year}/${vulnId}`);
  }

  async function handleLogout() {
    await logout();
  }

  return (
    <Routes>
      <Route
        path="/"
        element={
          <Layout
            vulnerabilities={vulnerabilities}
            years={years}
            selectedYear={selectedYear ?? 0}
            onSelectYear={selectYear}
            onSelectVuln={handleSelectVuln}
            activeVulnId={null}
            username={username}
            onLogout={handleLogout}
          >
            <VulnerabilityMenu
              vulnerabilities={vulnerabilities}
              selectedYear={selectedYear ?? 0}
              years={years}
              onSelectVuln={handleSelectVuln}
            />
          </Layout>
        }
      />
      <Route
        path="/vuln/:year/:vuln_id"
        element={
          <Layout
            vulnerabilities={vulnerabilities}
            years={years}
            selectedYear={selectedYear ?? 0}
            onSelectYear={selectYear}
            onSelectVuln={handleSelectVuln}
            activeVulnId={null}
            username={username}
            onLogout={handleLogout}
          >
            <VulnerabilityDetail />
          </Layout>
        }
      />
      <Route
        path="/security"
        element={
          <Layout
            vulnerabilities={vulnerabilities}
            years={years}
            selectedYear={selectedYear ?? 0}
            onSelectYear={selectYear}
            onSelectVuln={handleSelectVuln}
            activeVulnId={null}
            username={username}
            onLogout={handleLogout}
          >
            <SecurityEvents />
          </Layout>
        }
      />
      <Route
        path="/observability"
        element={
          <Layout
            vulnerabilities={vulnerabilities}
            years={years}
            selectedYear={selectedYear ?? 0}
            onSelectYear={selectYear}
            onSelectVuln={handleSelectVuln}
            activeVulnId={null}
            username={username}
            onLogout={handleLogout}
          >
            <Observability />
          </Layout>
        }
      />
      <Route
        path="/settings"
        element={
          <Layout
            vulnerabilities={vulnerabilities}
            years={years}
            selectedYear={selectedYear ?? 0}
            onSelectYear={selectYear}
            onSelectVuln={handleSelectVuln}
            activeVulnId={null}
            username={username}
            onLogout={handleLogout}
          >
            <Settings username={username} onLogout={handleLogout} />
          </Layout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
