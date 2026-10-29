import { Menu, Plus } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Composer } from './components/Composer'
import { EmptyState } from './components/EmptyState'
import { MessageBubble, TypingIndicator } from './components/MessageBubble'
import { Sidebar } from './components/Sidebar'
import { FOLLOW_UP_CHIPS } from './data/samples'
import { BROWSER_ENGINE, getHealth, sendChat } from './lib/api'
import type { ChatMessage, Health, SolutionContext } from './lib/types'
import { newId, useConversations } from './lib/useConversations'

type Theme = 'light' | 'dark'

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem('deriveit.theme')
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    /* ignore */
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function lastContext(messages: ChatMessage[]): SolutionContext | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const ctx = messages[i].context
    if (messages[i].role === 'assistant' && ctx) return ctx
  }
  return null
}

export default function App() {
  const store = useConversations()
  const { active } = store
  const [draft, setDraft] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [health, setHealth] = useState<Health | null | undefined>(undefined)
  const [theme, setTheme] = useState<Theme>(initialTheme)
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('deriveit.theme', theme)
    } catch {
      /* ignore */
    }
  }, [theme])

  const [engineStage, setEngineStage] = useState<string | null>(null)

  useEffect(() => {
    let unsubscribe: (() => void) | undefined
    if (BROWSER_ENGINE) {
      void import('./engine/client').then(({ onEngineProgress }) => {
        unsubscribe = onEngineProgress(setEngineStage) as () => void
      })
    }
    getHealth().then(setHealth)
    return () => unsubscribe?.()
  }, [])

  const messages = active?.messages ?? []
  const busy = busyId !== null

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    if (messages.length === 0) el.scrollTo({ top: 0 })
    else el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages.length, busyId, active?.id])

  const dispatch = useCallback(
    async (conversationId: string, userMsg: ChatMessage, previous: ChatMessage[]) => {
      setBusyId(conversationId)
      store.setFailed(conversationId, userMsg.id, false)
      const controller = new AbortController()
      abortRef.current = controller
      try {
        const res = await sendChat(userMsg.content, previous, lastContext(previous), controller.signal)
        store.append(conversationId, {
          id: newId(),
          role: 'assistant',
          createdAt: Date.now(),
          content: res.content,
          kind: res.kind,
          source: res.source,
          verified: res.verified,
          context: res.context,
          warnings: res.warnings,
          practice: res.practice,
        })
      } catch (err) {
        if ((err as Error).name !== 'AbortError') store.setFailed(conversationId, userMsg.id, true)
      } finally {
        setBusyId(null)
        abortRef.current = null
      }
    },
    [store],
  )

  const send = useCallback(
    (text: string) => {
      const content = text.trim()
      if (!content || busy) return
      const userMsg: ChatMessage = { id: newId(), role: 'user', content, createdAt: Date.now() }
      setDraft('')
      setSidebarOpen(false)
      if (!active) {
        const id = store.createWith(userMsg)
        void dispatch(id, userMsg, [])
      } else {
        const previous = active.messages.filter((m) => !m.failed)
        store.append(active.id, userMsg)
        void dispatch(active.id, userMsg, previous)
      }
    },
    [active, busy, dispatch, store],
  )

  const retry = (msg: ChatMessage) => {
    if (!active || busy) return
    const idx = active.messages.findIndex((m) => m.id === msg.id)
    void dispatch(active.id, msg, active.messages.slice(0, idx).filter((m) => !m.failed))
  }

  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')
  const newChat = () => {
    abortRef.current?.abort()
    store.startNew()
    setSidebarOpen(false)
  }

  return (
    <div className="flex h-dvh overflow-hidden">
      <Sidebar
        conversations={store.conversations}
        activeId={store.activeId}
        onSelect={(id) => {
          store.setActiveId(id)
          setSidebarOpen(false)
        }}
        onNew={newChat}
        onDelete={store.remove}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        health={health}
        engineStage={engineStage}
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-line px-3 py-2.5 md:hidden">
          <button onClick={() => setSidebarOpen(true)} className="rounded-md p-2 text-muted hover:bg-sidebar" aria-label="Open conversations">
            <Menu size={20} />
          </button>
          <div className="flex-1 truncate font-serif text-[16px] font-semibold">{active?.title ?? 'DeriveIt'}</div>
          <button onClick={newChat} className="rounded-md p-2 text-muted hover:bg-sidebar" aria-label="New conversation">
            <Plus size={20} />
          </button>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {!active || messages.length === 0 ? (
            <EmptyState onPick={send} />
          ) : (
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-3 py-6 sm:px-6">
              {messages.map((m) => (
                <MessageBubble
                  key={m.id}
                  message={m}
                  onSend={send}
                  onRetry={() => retry(m)}
                  disabled={busy}
                  followUps={FOLLOW_UP_CHIPS}
                  showFollowUps={!busy && m === lastAssistant && m.kind === 'solution' && m === messages[messages.length - 1]}
                />
              ))}
              {busyId === active.id && (
                <TypingIndicator
                  label={
                    BROWSER_ENGINE && health === undefined
                      ? `${engineStage ?? 'Loading the math engine…'} (first visit only, ~10 s)`
                      : undefined
                  }
                />
              )}
            </div>
          )}
        </div>

        <div className="border-t border-line bg-paper/90 px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur sm:px-6">
          <div className="mx-auto max-w-3xl">
            <Composer value={draft} onChange={setDraft} onSubmit={() => send(draft)} busy={busy} />
            <p className="mt-2 text-center text-[11px] text-muted">
              Answers are computed and checked with SymPy. Explanations can still contain wording mistakes — ask if
              something is unclear.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
