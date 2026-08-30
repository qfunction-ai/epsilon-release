import { describe, it, expect } from 'vitest'
import { parseSSEStream } from './sse'
import type { SSEEvent } from './sse'

function mockStream(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(new TextEncoder().encode(chunk))
      }
      controller.close()
    },
  })
}

describe('parseSSEStream', () => {
  it('parses single SSE event', async () => {
    const reader = mockStream(['data: {"type":"test","content":"hello"}\n\n']).getReader()
    const decoder = new TextDecoder()
    const events: SSEEvent[] = []
    for await (const event of parseSSEStream(reader, decoder)) {
      events.push(event)
    }
    expect(events).toHaveLength(1)
    expect(events[0]).toEqual({ type: 'test', content: 'hello' })
  })

  it('parses multiple events in single chunk', async () => {
    const reader = mockStream([
      'data: {"type":"a"}\n\ndata: {"type":"b"}\n\n',
    ]).getReader()
    const decoder = new TextDecoder()
    const events: SSEEvent[] = []
    for await (const event of parseSSEStream(reader, decoder)) {
      events.push(event)
    }
    expect(events).toHaveLength(2)
    expect(events[0].type).toBe('a')
    expect(events[1].type).toBe('b')
  })

  it('handles events split across chunks', async () => {
    const reader = mockStream([
      'data: {"type":"test"',
      ',"content":"hello"}\n\n',
    ]).getReader()
    const decoder = new TextDecoder()
    const events: SSEEvent[] = []
    for await (const event of parseSSEStream(reader, decoder)) {
      events.push(event)
    }
    expect(events).toHaveLength(1)
    expect(events[0]).toEqual({ type: 'test', content: 'hello' })
  })

  it('ignores non-data lines', async () => {
    const reader = mockStream([
      'event: message\ndata: {"type":"test"}\n\n',
    ]).getReader()
    const decoder = new TextDecoder()
    const events: SSEEvent[] = []
    for await (const event of parseSSEStream(reader, decoder)) {
      events.push(event)
    }
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('test')
  })

  it('handles malformed JSON gracefully', async () => {
    const reader = mockStream([
      'data: {invalid}\n\ndata: {"type":"ok"}\n\n',
    ]).getReader()
    const decoder = new TextDecoder()
    const events: SSEEvent[] = []
    for await (const event of parseSSEStream(reader, decoder)) {
      events.push(event)
    }
    // Malformed event is skipped, valid event parsed
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('ok')
  })

  it('handles empty stream', async () => {
    const reader = mockStream([]).getReader()
    const decoder = new TextDecoder()
    const events: SSEEvent[] = []
    for await (const event of parseSSEStream(reader, decoder)) {
      events.push(event)
    }
    expect(events).toHaveLength(0)
  })

  it('preserves extra fields', async () => {
    const reader = mockStream([
      'data: {"type":"test","custom":"value","nested":{"a":1}}\n\n',
    ]).getReader()
    const decoder = new TextDecoder()
    const events: SSEEvent[] = []
    for await (const event of parseSSEStream(reader, decoder)) {
      events.push(event)
    }
    expect(events[0].custom).toBe('value')
    expect(events[0].nested).toEqual({ a: 1 })
  })
})
