import { MessageSquare, Moon, Plus, Sun, Trash2, X } from 'lucide-react'
import type { Conversation, Health } from '../lib/types'

interface Props {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  open: boolean
  onClose: () => void
  health: Health | null | undefined
  engineStage?: string | null
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}

function groupLabel(ts: number) {
  const days = Math.floor((Date.now() - ts) / 86_400_000)
  if (days < 1) return 'Today'
  if (days < 7) return 'Previous 7 days'
  return 'Older'
}

export function Sidebar({ conversations, activeId, onSelect, onNew, onDelete, open, onClose, health, engineStage, theme, onToggleTheme }: Props) {
  const browserEngine = import.meta.env.VITE_ENGINE === 'browser'
  const status =
    health === undefined
      ? (engineStage ?? 'Connecting…')
      : health === null
        ? browserEngine
          ? 'Engine failed to load — refresh'
          : 'Server offline'
        : health.ai_enabled
          ? 'AI tutor + SymPy engine'
          : browserEngine
            ? 'SymPy engine (in your browser)'
            : 'SymPy engine (AI off)'

  const groups: [string, Conversation[]][] = []
  for (const c of conversations) {
    const label = groupLabel(c.updatedAt)
    const g = groups.find(([l]) => l === label)
    if (g) g[1].push(c)
    else groups.push([label, [c]])
  }

  return (
    <>
      <div
        aria-hidden
        onClick={onClose}
        className={`fixed inset-0 z-30 bg-black/30 transition-opacity md:hidden ${open ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[280px] flex-col border-r border-line bg-sidebar transition-transform
          md:static md:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
        aria-label="Conversations"
      >
        <div className="flex items-center justify-between px-4 pt-4 pb-3">
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-accent font-serif text-[15px] italic text-white dark:text-paper">f′</div>
            <div>
              <div className="font-serif text-[17px] font-semibold leading-tight">DeriveIt</div>
              <div className="text-[11px] text-muted">Derivatives tutor</div>
            </div>
          </div>
          <button onClick={onClose} className="rounded-md p-1.5 text-muted hover:bg-panel md:hidden" aria-label="Close sidebar">
            <X size={18} />
          </button>
        </div>

        <div className="px-3">
          <button
            onClick={onNew}
            className="flex w-full items-center gap-2 rounded-xl border border-line bg-panel px-3 py-2.5 text-sm font-medium hover:border-accent hover:text-accent"
          >
            <Plus size={16} /> New conversation
          </button>
        </div>

        <nav className="mt-3 flex-1 overflow-y-auto px-2 pb-3">
          {conversations.length === 0 && <p className="px-3 py-6 text-center text-xs text-muted">No conversations yet.</p>}
          {groups.map(([label, items]) => (
            <div key={label} className="mb-2">
              <div className="px-3 pt-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
              <ul>
                {items.map((c) => (
                  <li key={c.id} className="group relative">
                    <button
                      onClick={() => onSelect(c.id)}
                      aria-current={c.id === activeId ? 'page' : undefined}
                      className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 pr-9 text-left text-sm ${
                        c.id === activeId ? 'bg-panel text-ink shadow-sm' : 'text-muted hover:bg-panel/70 hover:text-ink'
                      }`}
                    >
                      <MessageSquare size={14} className="shrink-0" />
                      <span className="truncate">{c.title}</span>
                    </button>
                    <button
                      onClick={() => {
                        if (confirm('Delete this conversation?')) onDelete(c.id)
                      }}
                      aria-label={`Delete conversation ${c.title}`}
                      className="absolute top-1/2 right-1.5 -translate-y-1/2 rounded-md p-1.5 text-muted opacity-100 hover:text-warn md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="flex items-center justify-between border-t border-line px-4 py-3 text-[11px] text-muted">
          <span className="flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${health === undefined ? 'bg-line' : health === null ? 'bg-warn' : 'bg-ok'}`}
            />
            {status}
          </span>
          <button onClick={onToggleTheme} className="rounded-md p-1.5 hover:bg-panel hover:text-ink" aria-label="Toggle dark mode">
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </div>
      </aside>
    </>
  )
}
