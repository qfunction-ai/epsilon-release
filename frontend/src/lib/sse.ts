export interface SSEEvent {
  type: string
  content?: string
  status?: string
  steps?: number
  message_type?: string
  error?: string
  event?: string
  message?: string
  warnings?: string[]
  [key: string]: unknown
}

export async function* parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  decoder: TextDecoder
): AsyncGenerator<SSEEvent> {
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          yield JSON.parse(line.slice(6))
        } catch (e) {
          console.warn('Malformed SSE data:', line, e)
        }
      }
    }
  }
}
