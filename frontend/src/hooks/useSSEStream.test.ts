import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSSEStream } from './useSSEStream'

// Mock parseSSEStream so we control the event stream
vi.mock('../lib/sse', () => ({
  parseSSEStream: vi.fn(),
}))

import { parseSSEStream } from '../lib/sse'

// rAF mock — vi.useFakeTimers does NOT include rAF by default
let rafCallbacks: Map<number, () => void>
let rafCounter: number

beforeEach(() => {
  rafCallbacks = new Map()
  rafCounter = 0
  vi.spyOn(globalThis, 'requestAnimationFrame').mockImplementation((cb: FrameRequestCallback) => {
    const id = ++rafCounter
    rafCallbacks.set(id, () => cb(id))
    return id
  })
  vi.spyOn(globalThis, 'cancelAnimationFrame').mockImplementation((id: number) => {
    rafCallbacks.delete(id)
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

function flushRAF() {
  const callbacks = Array.from(rafCallbacks.values())
  rafCallbacks.clear()
  for (const cb of callbacks) cb()
}

function makeMockResponse(): Response {
  const reader = {
    read: vi.fn(),
    cancel: vi.fn(),
  }
  return {
    body: { getReader: () => reader },
  } as unknown as Response
}

function makeAsyncGenerator(events: object[]) {
  return async function* () {
    for (const event of events) {
      yield event
    }
  }
}

describe('useSSEStream', () => {
  it('sets streaming=true when startStream is called', async () => {
    const mockParse = parseSSEStream as ReturnType<typeof vi.fn>
    mockParse.mockReturnValue(makeAsyncGenerator([])())

    const { result } = renderHook(() =>
      useSSEStream({
        onContent: vi.fn(),
        onError: vi.fn(),
      }),
    )

    expect(result.current.streaming).toBe(false)

    const response = makeMockResponse()
    await act(async () => {
      await result.current.startStream(response)
    })

    expect(result.current.streaming).toBe(false) // back to false after stream ends
  })

  it('calls onContent with buffered content after rAF flush', async () => {
    const onContent = vi.fn()
    const mockParse = parseSSEStream as ReturnType<typeof vi.fn>
    mockParse.mockReturnValue(
      makeAsyncGenerator([
        { message_type: 'assistant_message', content: 'Hello ' },
        { message_type: 'assistant_message', content: 'world' },
      ])(),
    )

    const { result } = renderHook(() =>
      useSSEStream({ onContent, onError: vi.fn() }),
    )

    await act(async () => {
      await result.current.startStream(makeMockResponse())
    })

    // rAF was scheduled — flush it
    act(() => flushRAF())

    expect(onContent).toHaveBeenCalledWith('Hello world', '')
  })

  it('calls onError on error_message event', async () => {
    const onError = vi.fn()
    const mockParse = parseSSEStream as ReturnType<typeof vi.fn>
    mockParse.mockReturnValue(
      makeAsyncGenerator([
        { message_type: 'error_message', message: 'Something broke' },
      ])(),
    )

    const { result } = renderHook(() =>
      useSSEStream({ onContent: vi.fn(), onError }),
    )

    await act(async () => {
      await result.current.startStream(makeMockResponse())
    })

    expect(onError).toHaveBeenCalledWith('Something broke')
  })

  it('calls onStopReason on stop_reason event', async () => {
    const onStopReason = vi.fn()
    const mockParse = parseSSEStream as ReturnType<typeof vi.fn>
    mockParse.mockReturnValue(
      makeAsyncGenerator([
        { message_type: 'stop_reason', stop_reason: 'cancelled' },
      ])(),
    )

    const { result } = renderHook(() =>
      useSSEStream({
        onContent: vi.fn(),
        onError: vi.fn(),
        onStopReason,
      }),
    )

    await act(async () => {
      await result.current.startStream(makeMockResponse())
    })

    expect(onStopReason).toHaveBeenCalledWith('cancelled')
  })

  it('calls onCompleted after stream ends', async () => {
    const onCompleted = vi.fn()
    const mockParse = parseSSEStream as ReturnType<typeof vi.fn>
    mockParse.mockReturnValue(makeAsyncGenerator([])())

    const { result } = renderHook(() =>
      useSSEStream({
        onContent: vi.fn(),
        onError: vi.fn(),
        onCompleted,
      }),
    )

    await act(async () => {
      await result.current.startStream(makeMockResponse())
    })

    expect(onCompleted).toHaveBeenCalled()
  })

  it('cancelStream cancels the reader', async () => {
    const mockParse = parseSSEStream as ReturnType<typeof vi.fn>
    // Create a generator that never yields (hangs)
    mockParse.mockReturnValue(
      (async function* () {
        yield await new Promise(() => {}) // never resolves
      })(),
    )

    const reader = { read: vi.fn(), cancel: vi.fn() }
    const response = {
      body: { getReader: () => reader },
    } as unknown as Response

    const { result } = renderHook(() =>
      useSSEStream({ onContent: vi.fn(), onError: vi.fn() }),
    )

    // Start the stream (don't await — it hangs)
    act(() => {
      result.current.startStream(response)
    })

    // Cancel it
    act(() => {
      result.current.cancelStream()
    })

    expect(reader.cancel).toHaveBeenCalled()
  })

  it('cleans up reader on unmount', async () => {
    const mockParse = parseSSEStream as ReturnType<typeof vi.fn>
    mockParse.mockReturnValue(
      (async function* () {
        yield await new Promise(() => {}) // never resolves
      })(),
    )

    const reader = { read: vi.fn(), cancel: vi.fn() }
    const response = {
      body: { getReader: () => reader },
    } as unknown as Response

    const { result, unmount } = renderHook(() =>
      useSSEStream({ onContent: vi.fn(), onError: vi.fn() }),
    )

    act(() => {
      result.current.startStream(response)
    })

    // Unmount should cancel the reader
    unmount()
    expect(reader.cancel).toHaveBeenCalled()
  })

  it('final flush drains remaining buffer', async () => {
    const onContent = vi.fn()
    const mockParse = parseSSEStream as ReturnType<typeof vi.fn>
    mockParse.mockReturnValue(
      makeAsyncGenerator([
        { message_type: 'assistant_message', content: 'final content' },
      ])(),
    )

    const { result } = renderHook(() =>
      useSSEStream({ onContent, onError: vi.fn() }),
    )

    await act(async () => {
      await result.current.startStream(makeMockResponse())
    })

    // The final flush in the finally block should have called onContent
    // even without an explicit rAF flush
    expect(onContent).toHaveBeenCalledWith('final content', '')
  })
})
