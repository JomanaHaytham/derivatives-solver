import { useCallback, useEffect, useState } from 'react'
import { SAMPLE_CONVERSATION } from '../data/samples'
import type { ChatMessage, Conversation } from './types'

const KEY = 'deriveit.conversations.v1'
const ACTIVE_KEY = 'deriveit.active.v1'

export const newId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`

function load(): Conversation[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Conversation[]
      if (Array.isArray(parsed)) return parsed
    }
  } catch {
    /* storage unavailable or corrupted: start fresh */
  }
  return [SAMPLE_CONVERSATION]
}

function save(conversations: Conversation[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(conversations))
  } catch {
    /* quota exceeded or private mode: keep working in memory */
  }
}

export function titleFrom(text: string) {
  const clean = text.replace(/\s+/g, ' ').replace(/^(please\s+)?(find|differentiate|compute)\s+(the\s+)?(derivative\s+of\s+)?/i, '').trim()
  return clean.length > 42 ? `${clean.slice(0, 40)}…` : clean || 'New chat'
}

/** Conversation history, persisted in the browser's localStorage. */
export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>(load)
  const [activeId, setActiveId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(ACTIVE_KEY)
    } catch {
      return null
    }
  })

  useEffect(() => save(conversations), [conversations])
  useEffect(() => {
    try {
      if (activeId) localStorage.setItem(ACTIVE_KEY, activeId)
      else localStorage.removeItem(ACTIVE_KEY)
    } catch {
      /* ignore */
    }
  }, [activeId])

  const active = conversations.find((c) => c.id === activeId) ?? null

  const startNew = useCallback(() => setActiveId(null), [])

  const createWith = useCallback((first: ChatMessage): string => {
    const id = newId()
    const now = Date.now()
    setConversations((cs) => [{ id, title: titleFrom(first.content), messages: [first], createdAt: now, updatedAt: now }, ...cs])
    setActiveId(id)
    return id
  }, [])

  const append = useCallback((id: string, message: ChatMessage) => {
    setConversations((cs) =>
      cs.map((c) => (c.id === id ? { ...c, messages: [...c.messages, message], updatedAt: Date.now() } : c)),
    )
  }, [])

  const setFailed = useCallback((id: string, messageId: string, failed: boolean) => {
    setConversations((cs) =>
      cs.map((c) =>
        c.id === id ? { ...c, messages: c.messages.map((m) => (m.id === messageId ? { ...m, failed } : m)) } : c,
      ),
    )
  }, [])

  const remove = useCallback((id: string) => {
    setConversations((cs) => cs.filter((c) => c.id !== id))
    setActiveId((cur) => (cur === id ? null : cur))
  }, [])

  const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt)

  return { conversations: sorted, active, activeId, setActiveId, startNew, createWith, append, setFailed, remove }
}
