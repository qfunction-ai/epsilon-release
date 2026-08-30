import type { DefenseRef } from '../types'

interface DefenseListProps {
  defenses: DefenseRef[]
}

/**
 * Renders defense explanations from config.yaml defense_refs.
 *
 * Each defense_ref is organized by OWASP prevention strategy:
 *   1. Strategy number + title (from the OWASP document)
 *   2. Strategy description (from the OWASP document)
 *   3. Implementation description (how LettaLocal does it)
 *   4. Code snippet (trimmed from the actual framework source)
 *
 * No dangerouslySetInnerHTML — all text rendered through React node rendering.
 * Code snippets rendered as plain monospace <pre> text.
 */
export function DefenseList({ defenses }: DefenseListProps) {
  if (!defenses || defenses.length === 0) {
    return (
      <div style={{ color: 'var(--text-tertiary)', fontSize: '0.8125rem' }}>
        No runtime defenses documented for this vulnerability.
      </div>
    )
  }

  return (
    <div className="defense-list">
      {defenses.map((defense, i) => (
        <DefenseBlock key={i} defense={defense} />
      ))}
    </div>
  )
}

function DefenseBlock({ defense }: { defense: DefenseRef }) {
  return (
    <div className="defense-item">
      {/* Control name */}
      <div className="defense-item-title">
        {defense.control}
      </div>

      {/* OWASP Strategies — titles carry their own numbering
          ("Strategy #N: ..." / "Tier 1, Strategy #N: ...") set by
          scripts/verbatim_rewrite.py; no prefix added here */}
      {defense.owasp_strategies.map((strategy, i) => (
        <div key={i} style={{ marginBottom: '0.75rem' }}>
          <div className="defense-strategy-title">
            {strategy.title}
          </div>
          {strategy.description && (
            <div className="defense-strategy-desc">
              {strategy.description}
            </div>
          )}
        </div>
      ))}

      {/* Implementation */}
      {defense.implementation && (
        <div className="defense-item-body">
          {defense.implementation}
        </div>
      )}

      {/* Code snippet */}
      {defense.code_snippet && (
        <pre className="defense-code-snippet">
          {defense.code_snippet}
        </pre>
      )}
    </div>
  )
}
