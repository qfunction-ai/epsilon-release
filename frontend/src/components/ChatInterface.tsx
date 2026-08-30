import { useRef, useEffect, useState, useCallback } from 'react'
import type { ChatMessage, CodeState } from '../types'

interface ChatInterfaceProps {
  messages: ChatMessage[]
  streaming: boolean
  onSend: (text: string) => void
  codeState: CodeState
  onReset?: () => void
}

export function ChatInterface({ messages, streaming, onSend, codeState, onReset }: ChatInterfaceProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const [inputValue, setInputValue] = useState('')

  // Scroll to bottom only when user is already at bottom.
  // Use behavior: 'auto' NOT 'smooth' — smooth causes jank during high-frequency streaming.
  useEffect(() => {
    if (isAtBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' })
    }
  }, [messages])

  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current
    if (!container) return
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    isAtBottomRef.current = distanceFromBottom < 50
  }, [])

  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = '40px'
    const scrollH = textarea.scrollHeight
    if (scrollH > 40) {
      textarea.style.height = Math.min(scrollH, 120) + 'px'
    }
  }, [])

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value)
    adjustTextareaHeight()
  }

  const handleSend = () => {
    const trimmed = inputValue.trim()
    if (!trimmed || streaming) return
    onSend(trimmed)
    setInputValue('')
    // Reset textarea height after send
    if (textareaRef.current) {
      textareaRef.current.style.height = '40px'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const formatTime = (timestamp: number | string | undefined): string => {
    if (timestamp === undefined) return ''
    const d = typeof timestamp === 'number' ? new Date(timestamp) : new Date(timestamp)
    if (isNaN(d.getTime())) return String(timestamp)
    const h = d.getHours().toString().padStart(2, '0')
    const m = d.getMinutes().toString().padStart(2, '0')
    return `${h}:${m}`
  }

  return (
    <div className="chat-container">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-left">
          <div className="message-avatar agent">ε</div>
          <div className="chat-agent-name">Epsilon Agent</div>
          {codeState === 'vulnerable' ? (
            <span className="badge badge-danger">vulnerable</span>
          ) : (
            <span className="badge badge-success">fixed</span>
          )}
        </div>
        {onReset && (
          <div className="chat-header-right">
            {/* Disabled while streaming: deleting the agent under an
                in-flight run aborts the SSE messily (review gap fix). */}
            <button
              className="btn btn-secondary"
              style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
              disabled={streaming || messages.length === 0}
              onClick={onReset}
              title="Start a fresh conversation for this vulnerability"
            >
              Reset chat
            </button>
          </div>
        )}
      </div>

      {/* Messages — scroll container with onScroll handler */}
      <div
        className="chat-messages"
        ref={scrollContainerRef}
        onScroll={handleScroll}
      >
        {messages.length === 0 && !streaming && (
          <div style={{ textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8125rem', padding: '2rem 0' }}>
            Try an attack prompt to exploit this vulnerability.
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`message-row ${msg.role}`}>
            <div className={`message-avatar ${msg.role}`}>
              {msg.role === 'user' ? 'U' : 'ε'}
            </div>
            <div className="message-content">
              {/* Tool call blocks */}
              {msg.toolCalls?.map((tc, i) => (
                <div key={i} className="tool-call-block">
                  <span className="tool-call-name">{tc.name}</span>
                  <span style={{ color: 'var(--text-tertiary)' }}>→</span>
                  {tc.args && (
                    <span style={{ color: 'var(--text-secondary)' }}>
                      {typeof tc.args === 'string' ? tc.args : JSON.stringify(tc.args)}
                    </span>
                  )}
                  {tc.status === 'executed' && (
                    <span className="tool-call-status">{tc.statusText || '✓ executed'}</span>
                  )}
                  {tc.status === 'denied' && (
                    <span className="tool-call-denied">{tc.statusText || '✗ DENIED'}</span>
                  )}
                </div>
              ))}

              {/* Security warning blocks */}
              {msg.securityWarnings?.map((w, i) => (
                <div key={i} className="security-warning">
                  ⚠ {w.text || w.message}
                </div>
              ))}

              {/* Reasoning block — model's thinking tokens, streams live.
                  Rendered as React node (no dangerouslySetInnerHTML). */}
              {msg.role === 'assistant' && msg.reasoning && (
                <details className="reasoning-block" open>
                  <summary className="reasoning-label">REASONING</summary>
                  <div className="reasoning-content">{msg.reasoning}</div>
                </details>
              )}

              {/* Message bubble */}
              {msg.content && (
                <div
                  className="message-bubble"
                  style={msg.cancelled ? { opacity: 0.65, fontStyle: 'italic' } : undefined}
                >
                  {msg.content}
                </div>
              )}

              {/* Timestamp */}
              <div className="message-meta">{formatTime(msg.timestamp)}</div>
            </div>
          </div>
        ))}

        {/* Streaming indicator */}
        {streaming && (
          <div className="message-row agent">
            <div className="message-avatar agent">ε</div>
            <div className="message-content">
              <div className="message-bubble" style={{ opacity: 0.6 }}>
                <span style={{ fontFamily: 'var(--font-mono)' }}>●●●</span>
              </div>
            </div>
          </div>
        )}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        <textarea
          ref={textareaRef}
          className="chat-input"
          placeholder="Try an attack..."
          rows={1}
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          disabled={streaming}
          style={{
            minHeight: '40px',
            maxHeight: '120px',
          }}
        />
        <button
          className="btn btn-primary"
          onClick={handleSend}
          disabled={streaming || !inputValue.trim()}
        >
          Send
        </button>
      </div>
    </div>
  )
}
