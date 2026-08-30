import { useMemo } from 'react'

interface CodeComparisonProps {
  vulnerableCode: string
  fixedCode: string
}

// Python keywords to highlight
const KEYWORDS = new Set([
  'def', 'class', 'import', 'from', 'return', 'if', 'else', 'elif',
  'try', 'except', 'finally', 'with', 'as', 'for', 'while', 'break',
  'continue', 'pass', 'raise', 'yield', 'lambda', 'global', 'nonlocal',
  'assert', 'del', 'in', 'is', 'not', 'and', 'or', 'None', 'True',
  'False', 'await', 'async', 'self', 'cls',
])

interface Token {
  type: 'comment' | 'string' | 'keyword' | 'danger' | 'added' | 'removed' | 'text'
  value: string
}

/**
 * Detect whether code content is Python.
 * Heuristic: check for Python-specific patterns (def, import, class, # comments).
 * If neither panel looks like Python, render as plain monospace.
 */
function isPythonLike(code: string): boolean {
  if (!code || code.trim().length === 0) return true // default to Python for empty
  const lines = code.split('\n').slice(0, 20) // check first 20 lines
  let pySignals = 0
  let nonPySignals = 0
  for (const line of lines) {
    if (/^\s*#/.test(line)) pySignals++
    if (/\bdef\s+\w+\s*\(/.test(line)) pySignals++
    if (/\bimport\s+\w+/.test(line) || /\bfrom\s+\w+\s+import/.test(line)) pySignals++
    if (/\bclass\s+\w+/.test(line)) pySignals++
    if (/^\s*\/\//.test(line)) nonPySignals++ // JS/TS comment
    if (/^\s*(const|let|interface|export|function|type)\s/.test(line)) nonPySignals++
    if (/^\s*<\/?\w+>/.test(line)) nonPySignals++ // JSX/HTML
    if (/^\s*[\w-]+:/.test(line) && !line.includes('(')) nonPySignals++ // YAML key: value
  }
  return pySignals >= nonPySignals
}

/**
 * Simple regex-based Python syntax highlighter.
 * Not a full parser — handles comments (#...), strings ("..." and '...'),
 * and keywords. Also highlights lines with "DENY" as added and "allow" as danger.
 */
function highlightCode(code: string): Token[] {
  const tokens: Token[] = []
  const lines = code.split('\n')

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const line = lines[lineIdx]
    let i = 0

    while (i < line.length) {
      // Comment: # to end of line
      if (line[i] === '#') {
        tokens.push({ type: 'comment', value: line.slice(i) })
        i = line.length
        break
      }

      // String: "..." or '...' (handle triple quotes too)
      if (line[i] === '"' || line[i] === "'") {
        const quote = line[i]
        // Check for triple quote
        if (line.slice(i, i + 3) === quote.repeat(3)) {
          const end = line.indexOf(quote.repeat(3), i + 3)
          const strEnd = end === -1 ? line.length : end + 3
          tokens.push({ type: 'string', value: line.slice(i, strEnd) })
          i = strEnd
          continue
        }
        // Single/double quote string
        let j = i + 1
        while (j < line.length && line[j] !== quote) {
          if (line[j] === '\\') j++ // skip escaped char
          j++
        }
        const strEnd = j < line.length ? j + 1 : line.length
        tokens.push({ type: 'string', value: line.slice(i, strEnd) })
        i = strEnd
        continue
      }

      // Identifier / keyword
      if (/[a-zA-Z_]/.test(line[i])) {
        let j = i
        while (j < line.length && /[a-zA-Z0-9_]/.test(line[j])) j++
        const word = line.slice(i, j)

        if (KEYWORDS.has(word)) {
          tokens.push({ type: 'keyword', value: word })
        } else if (word === 'DENY' || word === 'deny') {
          tokens.push({ type: 'added', value: word })
        } else if (word === 'allow') {
          tokens.push({ type: 'danger', value: word })
        } else {
          tokens.push({ type: 'text', value: word })
        }
        i = j
        continue
      }

      // Default: single char
      tokens.push({ type: 'text', value: line[i] })
      i++
    }

    // Add newline between lines (except after last)
    if (lineIdx < lines.length - 1) {
      tokens.push({ type: 'text', value: '\n' })
    }
  }

  return tokens
}

function renderTokens(tokens: Token[]): React.ReactNode[] {
  return tokens.map((token, i) => {
    if (token.type === 'text') return token.value
    return (
      <span key={i} className={token.type}>
        {token.value}
      </span>
    )
  })
}

export function CodeComparison({ vulnerableCode, fixedCode }: CodeComparisonProps) {
  const vulnIsPython = useMemo(() => isPythonLike(vulnerableCode), [vulnerableCode])
  const fixedIsPython = useMemo(() => isPythonLike(fixedCode), [fixedCode])

  const vulnTokens = useMemo(
    () => (vulnIsPython ? highlightCode(vulnerableCode) : []),
    [vulnerableCode, vulnIsPython],
  )
  const fixedTokens = useMemo(
    () => (fixedIsPython ? highlightCode(fixedCode) : []),
    [fixedCode, fixedIsPython],
  )

  return (
    <div className="code-comparison">
      <div className="code-panel">
        <div className="code-panel-header">
          <span className="code-panel-title vulnerable">⚠ Vulnerable</span>
        </div>
        <pre className="code-block">
          {vulnIsPython ? renderTokens(vulnTokens) : vulnerableCode}
        </pre>
      </div>
      <div className="code-panel">
        <div className="code-panel-header">
          <span className="code-panel-title fixed">✓ Fixed</span>
        </div>
        <pre className="code-block">
          {fixedIsPython ? renderTokens(fixedTokens) : fixedCode}
        </pre>
      </div>
    </div>
  )
}
