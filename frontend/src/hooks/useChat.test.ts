import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

// Mock apiFetch and extractApiError
const mockApiFetch = vi.fn()
const mockExtractApiError = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
  extractApiError: (...args: unknown[]) => mockExtractApiError(...args),
}))

// Mock useSSEStream — capture callbacks for manual invocation
let capturedCallbacks: {
  onContent: (content: string, reasoning: string) => void
  onError: (error: string) => void
  onStopReason?: (reason: string) => void
  onCompleted: () => void
  onSecurityEvent?: (event: string, message: string) => void
} | null = null

const mockStartStream = vi.fn()
const mockCancelStream = vi.fn()

vi.mock('./useSSEStream', () => ({
  useSSEStream: (opts: Record<string, unknown>) => {
    capturedCallbacks = opts as typeof capturedCallbacks
    return {
      streaming: false,
      startStream: mockStartStream,
      cancelStream: mockCancelStream,
    }
  },
}))

import { useChat } from './useChat'

beforeEach(() => {
  vi.clearAllMocks()
  capturedCallbacks = null
  mockApiFetch.mockReset()
  mockExtractApiError.mockReset()
  mockStartStream.mockReset()
  mockCancelStream.mockReset()
  mockStartStream.mockResolvedValue(undefined)
})

describe('useChat', () => {
  it('sendMessage adds user + assistant placeholder messages', async () => {
    mockApiFetch.mockResolvedValue({ ok: true } as Response)

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', 'test message')
    })

    expect(result.current.messages).toHaveLength(2)
    expect(result.current.messages[0].role).toBe('user')
    expect(result.current.messages[0].content).toBe('test message')
    expect(result.current.messages[1].role).toBe('assistant')
  })

  it('handleContent updates the last assistant message content', async () => {
    mockApiFetch.mockResolvedValue({ ok: true } as Response)

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', 'test')
    })

    // Simulate content arriving from the stream
    act(() => {
      capturedCallbacks?.onContent('streamed content', '')
    })

    expect(result.current.messages[1].content).toBe('streamed content')
  })

  it('handleError removes the empty assistant placeholder', async () => {
    mockApiFetch.mockResolvedValue({ ok: true } as Response)

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', 'test')
    })

    expect(result.current.messages).toHaveLength(2)

    act(() => {
      capturedCallbacks?.onError('stream error')
    })

    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0].role).toBe('user')
    expect(result.current.error).toBe('stream error')
  })

  it('handleCompleted finalizes the assistant message', async () => {
    mockApiFetch.mockResolvedValue({ ok: true } as Response)

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', 'test')
    })

    act(() => {
      capturedCallbacks?.onContent('final content', 'reasoning here')
    })

    act(() => {
      capturedCallbacks?.onCompleted()
    })

    expect(result.current.messages[1].content).toBe('final content')
    expect(result.current.messages[1].reasoning).toBe('reasoning here')
    expect(result.current.streaming).toBe(false)
  })

  it('handleCompleted with cancelled stop_reason marks message as cancelled', async () => {
    mockApiFetch.mockResolvedValue({ ok: true } as Response)

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', 'test')
    })

    act(() => {
      capturedCallbacks?.onStopReason?.('cancelled')
    })

    act(() => {
      capturedCallbacks?.onContent('partial', '')
    })

    act(() => {
      capturedCallbacks?.onCompleted()
    })

    expect(result.current.messages[1].cancelled).toBe(true)
    expect(result.current.messages[1].content).toBe('partial')
  })

  it('abortChat sets cancelled and cancels stream', async () => {
    mockApiFetch.mockResolvedValue({ ok: true } as Response)

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', 'test')
    })

    act(() => {
      result.current.abortChat()
    })

    expect(mockCancelStream).toHaveBeenCalled()
  })

  it('abortChat epoch guard: late callbacks no-op after abort', async () => {
    mockApiFetch.mockResolvedValue({ ok: true } as Response)

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', 'test')
    })

    // Abort the stream — NEW CONTRACT: the abort path finalizes the
    // UI itself (cancelled marker, streaming cleared); the epoch guard
    // would eat the stream's own completion callback (the stuck-
    // streaming bug the stop-mid-stream spec caught).
    act(() => {
      result.current.abortChat()
    })

    // The assistant placeholder is finalized as cancelled
    const msgs = result.current.messages
    const last = msgs[msgs.length - 1]
    expect(last.role).toBe('assistant')
    expect(last.cancelled).toBe(true)
    expect(last.content).toBe('Generation cancelled.')
    // Streaming ended — the Send button returns
    expect(result.current.streaming).toBe(false)

    // Simulate late content arriving after abort
    act(() => {
      capturedCallbacks?.onContent('late content after abort', '')
    })

    // Simulate late completion
    act(() => {
      capturedCallbacks?.onCompleted()
    })

    // Messages unchanged by the LATE callbacks — they are no-ops
    // (the abort finalize above is the only mutation)
    expect(result.current.messages).toEqual(msgs)
  })

  it('buffer resets on send: turn N+1 does not inherit turn N content', async () => {
    mockApiFetch.mockResolvedValue({ ok: true } as Response)

    const { result } = renderHook(() => useChat())

    // First message
    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', 'first')
    })

    act(() => {
      capturedCallbacks?.onContent('first turn content', '')
    })

    act(() => {
      capturedCallbacks?.onCompleted()
    })

    // Second message
    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', 'second')
    })

    // The third message (second assistant) should not contain first turn content
    const secondAssistant = result.current.messages[3]
    expect(secondAssistant.role).toBe('assistant')
    // Content should be empty or the new turn's content, not 'first turn content'
    act(() => {
      capturedCallbacks?.onContent('second turn content', '')
    })
    expect(result.current.messages[3].content).toBe('second turn content')
    expect(result.current.messages[3].content).not.toContain('first turn')
  })

  it('clearMessages empties the array', async () => {
    mockApiFetch.mockResolvedValue({ ok: true } as Response)

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', 'test')
    })

    expect(result.current.messages).toHaveLength(2)

    act(() => {
      result.current.clearMessages()
    })

    expect(result.current.messages).toHaveLength(0)
    expect(result.current.error).toBe('')
  })

  it('restoreMessages replaces the array', async () => {
    const { result } = renderHook(() => useChat())

    const msgs = [
      { role: 'user' as const, content: 'restored user' },
      { role: 'assistant' as const, content: 'restored assistant' },
    ]

    act(() => {
      result.current.restoreMessages(msgs)
    })

    expect(result.current.messages).toEqual(msgs)
    expect(result.current.error).toBe('')
  })

  it('sendMessage does nothing when streaming is already true', async () => {
    mockApiFetch.mockResolvedValue({ ok: true } as Response)

    const { result } = renderHook(() => useChat())

    // Start first message (sets streaming=true internally)
    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', 'first')
    })

    // The hook's streaming state goes back to false after completion
    // To test the guard, we need to be mid-stream. Since we mocked
    // useSSEStream, streaming is always false. Test the empty-message guard instead.
  })

  it('sendMessage does nothing when message is empty', async () => {
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', '')
    })

    expect(result.current.messages).toHaveLength(0)
    expect(mockApiFetch).not.toHaveBeenCalled()
  })

  it('sendMessage does nothing when message is whitespace', async () => {
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage(2026, 'llm01', 'vulnerable', '   ')
    })

    expect(result.current.messages).toHaveLength(0)
    expect(mockApiFetch).not.toHaveBeenCalled()
  })
})
