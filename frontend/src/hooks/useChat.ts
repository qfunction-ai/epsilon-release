import { useState, useCallback, useRef } from 'react'
import { apiFetch, extractApiError } from '../lib/api'
import { useSSEStream } from './useSSEStream'
import type { ChatMessage, ToolCall, SecurityWarning, CodeState } from '../types'

// aislop-ignore-next-line narrative-comment — load-bearing pattern docs
/**
 * Hook for the Exploit tab chat interface.
 *
 * Manages the message array, streaming state, and sending messages to the
 * /agent/stream SSE endpoint. Uses rAF-throttled content updates via useSSEStream.
 *
 * Message update pattern:
 *   1. On send: append user message + empty assistant placeholder
 *   2. During stream: update the last assistant message's content
 *   3. On completion: finalize the assistant message
 *   4. On error: remove the placeholder (prev.slice(0, -1))
 *
 * Stick-to-bottom scrolling is handled by ChatInterface.tsx (isAtBottomRef,
 * scrollContainerRef, onScroll). This hook does not manage scroll.
 *
 * Usage:
 *   const { messages, streaming, error, sendMessage } = useChat()
 */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState('')

  // Buffer for accumulating assistant content during stream
  const contentBufferRef = useRef('')
  const reasoningBufferRef = useRef('')
  // Accumulate tool calls and security warnings during stream
  const toolCallsRef = useRef<ToolCall[]>([])
  const securityWarningsRef = useRef<SecurityWarning[]>([])
  // Cancel epoch: set by abortChat(), checked by all stream callbacks.
  // After an abort, useSSEStream's async finally block still fires
  // handleCompleted on a later microtask — without this guard it would
  // patch the last message of whatever transcript is mounted by then
  // (post-switch: the NEW vulnerability's) with the aborted run's buffers.
  const cancelledRef = useRef(false)
  // Termination cause from the stream's stop_reason event. 'cancelled'
  // means the run was aborted server-side (0.16.29 run-abort API) —
  // informational, not an error.
  const stopReasonRef = useRef('')

  const handleContent = useCallback(
    (content: string, reasoning: string) => {
      if (cancelledRef.current) return
      if (content) {
        contentBufferRef.current += content
      }
      if (reasoning) {
        reasoningBufferRef.current += reasoning
      }
      if (!content && !reasoning) return
      // Capture buffer values BEFORE setMessages — the callback may run
      // after refs change (React batching; known Epsilon pitfall)
      const contentNow = contentBufferRef.current
      const reasoningNow = reasoningBufferRef.current
      setMessages((prev) => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last && last.role === 'assistant') {
          updated[updated.length - 1] = {
            ...last,
            content: contentNow,
            reasoning: reasoningNow,
          }
        }
        return updated
      })
    },
    [],
  )

  const handleError = useCallback((err: string) => {
    if (cancelledRef.current) return
    setError(err)
    // Remove the empty assistant placeholder on error
    setMessages((prev) => {
      const last = prev[prev.length - 1]
      if (last && last.role === 'assistant' && !last.content) {
        return prev.slice(0, -1)
      }
      return prev
    })
  }, [])

  const handleCompleted = useCallback(() => {
    if (cancelledRef.current) return
    // Capture buffer values BEFORE resetting — setMessages callback may
    // run after the refs are cleared, which would set content to empty.
    const finalContent = contentBufferRef.current
    const finalReasoning = reasoningBufferRef.current
    const finalToolCalls = [...toolCallsRef.current]
    const finalSecurityWarnings = [...securityWarningsRef.current]
    const wasCancelled = stopReasonRef.current === 'cancelled'

    // Finalize the assistant message with any accumulated tool calls / warnings
    setMessages((prev) => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last && last.role === 'assistant') {
        const finalized: ChatMessage = {
          ...last,
          // Model sometimes emits only thinking tokens and no answer.
          // Keep the reasoning block and mark empty content honestly —
          // do NOT promote reasoning to content (the distinction is the
          // teaching point). An aborted run gets an explicit terminal
          // note instead of silence.
          content: wasCancelled
            ? finalContent || 'Generation cancelled.'
            : finalContent || (finalReasoning ? '(no response)' : ''),
          ...(wasCancelled ? { cancelled: true } : {}),
        }
        if (finalReasoning) {
          finalized.reasoning = finalReasoning
        }
        if (finalToolCalls.length > 0) {
          finalized.toolCalls = finalToolCalls
        }
        if (finalSecurityWarnings.length > 0) {
          finalized.securityWarnings = finalSecurityWarnings
        }
        updated[updated.length - 1] = finalized
      }
      return updated
    })

    // Reset buffers
    contentBufferRef.current = ''
    reasoningBufferRef.current = ''
    toolCallsRef.current = []
    securityWarningsRef.current = []
    setStreaming(false)
  }, [])

  const handleStopReason = useCallback((reason: string) => {
    stopReasonRef.current = reason
  }, [])

  const handleSecurityEvent = useCallback((event: string, message: string) => {
    securityWarningsRef.current.push({ type: event, message })
    // Also push a tool call entry for denied tools
    if (event === 'tool_denied') {
      toolCallsRef.current.push({
        name: message.split(':')[0] || 'unknown',
        args: '',
        status: 'denied',
        reason: message,
      })
    }
  }, [])

  const { startStream, cancelStream } = useSSEStream({
    onContent: handleContent,
    onError: handleError,
    onStopReason: handleStopReason,
    onCompleted: handleCompleted,
    onSecurityEvent: handleSecurityEvent,
  })

  /** Abort an in-flight stream. Late stream callbacks become no-ops. */
  const abortChat = useCallback(() => {
    cancelledRef.current = true
    cancelStream()
  }, [cancelStream])

  /** Empty the transcript and clear the chat error state. */
  const clearMessages = useCallback(() => {
    setMessages([])
    setError('')
  }, [])

  /** Replace the transcript (e.g. restore a cached per-vuln history). */
  const restoreMessages = useCallback((msgs: ChatMessage[]) => {
    setMessages(msgs)
    setError('')
  }, [])

  /**
   * Send a message to the agent and start streaming the response.
   *
   * Creates a user message and an empty assistant placeholder, then
   * POSTs to /agent/stream and starts the SSE stream.
   */
  const sendMessage = useCallback(
    async (
      year: number,
      vulnId: string,
      codeState: CodeState,
      message: string,
    ) => {
      if (!message.trim() || streaming) return

      setError('')
      setStreaming(true)
      // New run: re-arm the stream callbacks
      cancelledRef.current = false

      const now = new Date().toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })

      // Reset buffers
      contentBufferRef.current = ''
      reasoningBufferRef.current = ''
      toolCallsRef.current = []
      securityWarningsRef.current = []
      stopReasonRef.current = ''

      // Append user message + empty assistant placeholder (with unique IDs)
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'user', content: message, timestamp: now },
        { id: crypto.randomUUID(), role: 'assistant', content: '', timestamp: now },
      ])

      try {
        const res = await apiFetch('/agent/stream', {
          method: 'POST',
          body: JSON.stringify({
            year,
            vuln_id: vulnId,
            code_state: codeState,
            message,
          }),
        })

        if (!res.ok) {
          const msg = await extractApiError(res, 'Failed to start agent stream')
          // Remove the empty assistant placeholder
          setMessages((prev) => prev.slice(0, -1))
          setError(msg)
          setStreaming(false)
          return
        }

        await startStream(res)
      } catch (err) {
        // Network error — remove the empty assistant placeholder
        setMessages((prev) => prev.slice(0, -1))
        setError(
          err instanceof Error ? err.message : 'Connection error',
        )
        setStreaming(false)
      }
    },
    [streaming, startStream],
  )

  return {
    messages,
    streaming,
    error,
    sendMessage,
    abortChat,
    clearMessages,
    restoreMessages,
  }
}
