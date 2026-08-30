interface SuggestionChipsProps {
  prompts: string[]
  onSelect: (prompt: string) => void
}

export function SuggestionChips({ prompts, onSelect }: SuggestionChipsProps) {
  if (!prompts || prompts.length === 0) return null

  return (
    <div className="exploit-suggestions">
      {prompts.map((prompt, i) => (
        <div
          key={i}
          className="suggestion-chip"
          onClick={() => onSelect(prompt)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onSelect(prompt)
            }
          }}
        >
          {prompt}
        </div>
      ))}
    </div>
  )
}
