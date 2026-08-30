import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/api'

interface LoginProps {
  onLogin: (username: string, password: string) => Promise<void>
  onRegister: (username: string, password: string) => Promise<void>
}

interface SetupStatus {
  needs_setup: boolean
}

export function Login({ onLogin, onRegister }: LoginProps) {
  const navigate = useNavigate()
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Check if first-run setup is needed
  useEffect(() => {
    apiFetch('/auth/setup-status')
      .then((res) => res.json())
      .then((data: SetupStatus) => setNeedsSetup(data.needs_setup))
      .catch(() => setNeedsSetup(false))
  }, [])

  // Don't render until we know whether setup is needed
  if (needsSetup === null) return null

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (needsSetup) {
      if (password !== confirmPassword) {
        setError('Passwords do not match')
        return
      }
      if (password.length < 8) {
        setError('Password must be at least 8 characters')
        return
      }
    }

    setIsSubmitting(true)
    try {
      if (needsSetup) {
        await onRegister(username, password)
      } else {
        await onLogin(username, password)
      }
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : needsSetup ? 'Registration failed' : 'Login failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-container">
        {/* Logo */}
        <div className="login-logo">
          <div className="epsilon-symbol">ε</div>
          <div className="epsilon-name">Epsilon</div>
          <div className="epsilon-tagline">Every epsilon of defense matters.</div>
        </div>

        {/* Login/Register Form */}
        <form className="login-form" onSubmit={handleSubmit}>
          <input
            className="input"
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <input
            className="input"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={needsSetup ? 'new-password' : 'current-password'}
            required
          />
          {needsSetup && (
            <input
              className="input"
              type="password"
              placeholder="Confirm password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          )}
          {error && (
            <div style={{
              color: 'var(--danger)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.75rem',
              textAlign: 'center',
            }}>
              {error}
            </div>
          )}
          <button
            className="btn btn-primary"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? (needsSetup ? 'Creating account…' : 'Entering…')
              : (needsSetup ? 'Create Admin Account' : 'Enter the Classroom')
            }
          </button>
        </form>
      </div>
    </div>
  )
}
