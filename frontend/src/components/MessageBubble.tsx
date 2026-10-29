import { AlertTriangle, BadgeCheck, Cpu, RotateCcw, Sparkles } from 'lucide-react'
import type { ChatMessage } from '../lib/types'
import { CopyButton } from './CopyButton'
import { MathMarkdown } from './MathMarkdown'

interface Props {
  message: ChatMessage
  onSend: (text: string) => void
  onRetry?: () => void
  showFollowUps: boolean
  followUps: string[]
  disabled: boolean
}

function Badge({ tone, icon, children }: { tone: 'ok' | 'warn' | 'plain'; icon: React.ReactNode; children: React.ReactNode }) {
  const tones = {
    ok: 'bg-ok-soft text-ok',
    warn: 'bg-warn-soft text-warn',
    plain: 'bg-sidebar text-muted',
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>
      {icon}
      {children}
    </span>
  )
}

export function MessageBubble({ message, onSend, onRetry, showFollowUps, followUps, disabled }: Props) {
  if (message.role === 'user') {
    return (
      <div className="flex flex-col items-end gap-1">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-[15px] text-white dark:text-paper">
          {message.content}
        </div>
        {message.failed && (
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-1 text-xs text-warn hover:underline"
            type="button"
          >
            <RotateCcw size={12} /> Not sent — tap to retry
          </button>
        )}
      </div>
    )
  }

  const isSolution = message.kind === 'solution'
  return (
    <div className="flex gap-3">
      <div aria-hidden className="mt-1 hidden h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent font-serif text-[15px] italic text-white sm:grid dark:text-paper">
        f′
      </div>
      <div className="min-w-0 flex-1">
        <div className="rounded-2xl rounded-tl-md border border-line bg-panel px-4 py-3.5 shadow-[0_1px_0_rgba(0,0,0,0.03)] sm:px-5">
          {(isSolution || message.source || message.verified != null) && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {isSolution && message.verified === true && (
                <Badge tone="ok" icon={<BadgeCheck size={12} />}>Verified by SymPy</Badge>
              )}
              {isSolution && message.verified === false && (
                <Badge tone="warn" icon={<AlertTriangle size={12} />}>Not fully verified</Badge>
              )}
              {message.kind === 'follow_up' && message.verified === true && (
                <Badge tone="ok" icon={<BadgeCheck size={12} />}>Matches verified answer</Badge>
              )}
              {message.kind === 'follow_up' && message.verified === false && (
                <Badge tone="warn" icon={<AlertTriangle size={12} />}>Check failed</Badge>
              )}
              {message.source === 'ai' && <Badge tone="plain" icon={<Sparkles size={12} />}>AI explanation</Badge>}
              {message.source === 'engine' && isSolution && (
                <Badge tone="plain" icon={<Cpu size={12} />}>Step engine</Badge>
              )}
            </div>
          )}

          <MathMarkdown content={message.content} />

          {message.warnings && message.warnings.length > 0 && (
            <ul className="mt-3 space-y-1 rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn">
              {message.warnings.map((w) => (
                <li key={w} className="flex gap-1.5">
                  <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                  {w}
                </li>
              ))}
            </ul>
          )}

          {message.practice && message.practice.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {message.practice.map((p) => (
                <button
                  key={p}
                  type="button"
                  disabled={disabled}
                  onClick={() => onSend(p)}
                  className="rounded-lg border border-line bg-paper px-3 py-1.5 text-left text-xs text-ink hover:border-accent hover:text-accent disabled:opacity-50"
                >
                  Solve: <span className="font-mono">{p.replace(/^Differentiate\s+/i, '')}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="mt-1 flex flex-wrap items-center gap-1">
          <CopyButton text={message.content} label="Copy" title="Copy the whole explanation (Markdown + LaTeX)" />
          {isSolution && message.context?.answer_latex && (
            <CopyButton text={message.context.answer_latex} label="Copy answer" title="Copy the final answer as LaTeX" />
          )}
        </div>

        {showFollowUps && (
          <div className="mt-2 flex flex-wrap gap-2" aria-label="Suggested follow-up questions">
            {followUps.map((f) => (
              <button
                key={f}
                type="button"
                disabled={disabled}
                onClick={() => onSend(f)}
                className="rounded-full border border-line bg-panel px-3 py-1.5 text-xs text-muted hover:border-accent hover:text-accent disabled:opacity-50"
              >
                {f}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function TypingIndicator({ label }: { label?: string }) {
  return (
    <div className="flex gap-3" role="status" aria-live="polite">
      <div aria-hidden className="mt-1 hidden h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent font-serif italic text-white sm:grid dark:text-paper">
        f′
      </div>
      <div className="inline-flex items-center gap-3 rounded-2xl rounded-tl-md border border-line bg-panel px-4 py-3 text-sm text-muted">
        <span className="flex gap-1">
          <span className="dot h-1.5 w-1.5 rounded-full bg-accent" />
          <span className="dot h-1.5 w-1.5 rounded-full bg-accent" />
          <span className="dot h-1.5 w-1.5 rounded-full bg-accent" />
        </span>
        {label ?? 'Working it out and checking the math…'}
      </div>
    </div>
  )
}
