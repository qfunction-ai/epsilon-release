import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ChatInterface } from './ChatInterface'
import type { ChatMessage, CodeState } from '../types'

// The repo's first COMPONENT test (hook tests came first). Assert on
// rendered output, not hook-call sequences. setup.ts already stubs
// scrollIntoView (ChatInterface uses it on mount effect).

const baseProps = {
  messages: [] as ChatMessage[],
  streaming: false,
  onSend: vi.fn(),
  codeState: 'vulnerable' as CodeState,
  onReset: vi.fn(),
  onAbort: vi.fn(),
}

describe('ChatInterface Send/Stop swap', () => {
  it('renders Send (not Stop) when not streaming', () => {
    render(<ChatInterface {...baseProps} />)
    expect(screen.getByRole('button', { name: 'Send' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull()
  })

  it('renders Stop (not Send) while streaming; click fires onAbort', () => {
    render(<ChatInterface {...baseProps} streaming />)
    const stop = screen.getByRole('button', { name: 'Stop' })
    expect(screen.queryByRole('button', { name: 'Send' })).toBeNull()
    // Stop is always enabled while streaming (no input-required logic)
    expect(stop.hasAttribute('disabled')).toBe(false)
    fireEvent.click(stop)
    expect(baseProps.onAbort).toHaveBeenCalledTimes(1)
  })

  it('Send behavior unchanged when not streaming: disabled on empty input, fires onSend with text', () => {
    render(<ChatInterface {...baseProps} />)
    const send = screen.getByRole('button', { name: 'Send' }) as HTMLButtonElement
    expect(send.disabled).toBe(true) // empty input
    const input = screen.getByPlaceholderText('Try an attack...')
    fireEvent.change(input, { target: { value: 'hello' } })
    expect(send.disabled).toBe(false)
    fireEvent.click(send)
    expect(baseProps.onSend).toHaveBeenCalledWith('hello')
  })
})
