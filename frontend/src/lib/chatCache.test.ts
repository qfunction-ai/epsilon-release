import { describe, it, expect, beforeEach } from 'vitest'
import { chatCache } from './chatCache'
import type { ChatMessage } from '../types'

describe('chatCache', () => {
  const key = '2026:llm01_prompt_injection'
  const msgs: ChatMessage[] = [
    { role: 'user', content: 'Hello' },
    { role: 'assistant', content: 'Hi there' },
  ]

  beforeEach(() => {
    // Clear cache before each test
    chatCache.drop(key)
  })

  it('load returns undefined for missing key', () => {
    expect(chatCache.load('nonexistent')).toBeUndefined()
  })

  it('save then load returns the messages', () => {
    chatCache.save(key, msgs)
    expect(chatCache.load(key)).toEqual(msgs)
  })

  it('drop removes the key', () => {
    chatCache.save(key, msgs)
    chatCache.drop(key)
    expect(chatCache.load(key)).toBeUndefined()
  })

  it('save overwrites previous value', () => {
    chatCache.save(key, msgs)
    const newMsgs: ChatMessage[] = [{ role: 'user', content: 'New' }]
    chatCache.save(key, newMsgs)
    expect(chatCache.load(key)).toEqual(newMsgs)
  })

  it('different keys are independent', () => {
    const key2 = '2026:llm02_sensitive_info'
    chatCache.save(key, msgs)
    chatCache.save(key2, [{ role: 'user', content: 'Other' }])
    expect(chatCache.load(key)).toEqual(msgs)
    expect(chatCache.load(key2)).toEqual([{ role: 'user', content: 'Other' }])
    chatCache.drop(key2)
  })
})
