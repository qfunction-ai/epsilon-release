import { useState, useCallback, useRef, useEffect } from 'react'
import { parseSSEStream } from '../lib/sse'

interface UseSSEStreamOptions {
  /** Called with accumulated content/reasoning at most once per animation frame. */
  onContent: (content: string, reasoning: string) => void
  /** Called when the stream sends an error event. */
  onError: (error: string) => void
  /** Called with the stop_reason value when the stream terminates (e.g. 'cancelled' from run-abort). */
  onStopReason?: (reason: string) => void
  /** Called after the stream ends (completed, error, or reader done). */
  onCompleted?: () => void
  /** Called when a security event is detected in the stream. */
  onSecurityEvent?: (event: string, message: string) => void
  /** Called when a secret is detected in the user's message. */
  onSecretWarning?: (warnings: string[]) => void
}

/**
 * Hook for consuming an SSE stream with rAF-throttled content updates.
 *
 * Buffers incoming SSE content chunks in a ref and flushes to state
 * at most once per animation frame via `onContent`. This prevents
 * rapid re-renders from high-frequency streaming chunks.
 *
 * Copied from Delta's useSSEStream.ts (gotcha #2 — rAF throttling).
 */
export function useSSEStream({
  onContent,
  onError,
  onStopReason,
  onCompleted,
  onSecurityEvent,
  onSecretWarning,
}: UseSSEStreamOptions) {
  const [streaming, setStreaming] = useState(false)
  const bufferRef = useRef({ content: '', reasoning: '' })
  const rafIdRef = useRef<number | null>(null)
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null)

  const flush = useCallback(() => {
    const { content, reasoning } = bufferRef.current
    if (!content && !reasoning) {
      rafIdRef.current = null
      return
    }
    bufferRef.current = { content: '', reasoning: '' }
    onContent(content, reasoning)
    rafIdRef.current = null
  }, [onContent])

  const cancelStream = useCallback(() => {
    readerRef.current?.cancel()
    readerRef.current = null
  }, [])

  // Cancel the reader on unmount
  useEffect(() => {
    return () => {
      readerRef.current?.cancel()
      readerRef.current = null
    }
  }, [])

  const startStream = useCallback(
    async (response: Response) => {
      setStreaming(true)
      const reader = response.body?.getReader() as
        | ReadableStreamDefaultReader<Uint8Array>
        | undefined
      const decoder = new TextDecoder()

      if (!reader) {
        setStreaming(false)
        return
      }

      readerRef.current = reader

      try {
        for await (const data of parseSSEStream(reader, decoder)) {
          const msgType = data.message_type

          if (msgType === 'assistant_message') {
            // Token streaming: content comes in pieces
            const content = typeof data.content === 'string' ? data.content : ''
            if (content) {
              bufferRef.current.content += content
              if (!rafIdRef.current) {
                rafIdRef.current = requestAnimationFrame(flush)
              }
            }
          } else if (msgType === 'reasoning_message') {
            // Token streaming: reasoning comes in pieces
            const reasoning = typeof data.reasoning === 'string' ? data.reasoning : ''
            if (reasoning) {
              bufferRef.current.reasoning += reasoning
              if (!rafIdRef.current) {
                rafIdRef.current = requestAnimationFrame(flush)
              }
            }
          } else if (msgType === 'stop_reason') {
            // Surface the termination cause (0.16.29 abort API adds
            // 'cancelled'); break-then-flush behavior unchanged.
            const reason = typeof data.stop_reason === 'string' ? data.stop_reason : ''
            if (reason) onStopReason?.(reason)
            break
          } else if (msgType === 'error_message') {
            onError(String(data.message || data.detail || 'Stream error'))
            break
          }
          // Ignore ping, usage_statistics, and other non-content message types
        }

        // Final flush — drain any remaining buffered content
        if (rafIdRef.current) {
          cancelAnimationFrame(rafIdRef.current)
          rafIdRef.current = null
        }
        flush()
      } finally {
        reader.cancel()
        readerRef.current = null
        setStreaming(false)
        onCompleted?.()
      }
    },
    [flush, onError, onStopReason, onCompleted, onSecurityEvent, onSecretWarning]
  )

  return { streaming, startStream, cancelStream }
}
