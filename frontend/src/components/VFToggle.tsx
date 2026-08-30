import type { CodeState } from '../types'

interface VFToggleProps {
  codeState: CodeState
  onChange: (state: CodeState) => void
}

export function VFToggle({ codeState, onChange }: VFToggleProps) {
  return (
    <div className="vf-toggle">
      <div
        className={`vf-option ${codeState === 'vulnerable' ? 'active vulnerable' : ''}`}
        onClick={() => onChange('vulnerable')}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onChange('vulnerable')
          }
        }}
      >
        <span className="vf-icon">⚠</span> Vulnerable
      </div>
      <div
        className={`vf-option ${codeState === 'fixed' ? 'active fixed' : ''}`}
        onClick={() => onChange('fixed')}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onChange('fixed')
          }
        }}
      >
        <span className="vf-icon">✓</span> Fixed
      </div>
    </div>
  )
}
