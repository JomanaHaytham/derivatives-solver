import { Check, Copy } from 'lucide-react'
import { useState } from 'react'

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // Fallback for non-secure contexts
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    ta.remove()
    return ok
  }
}

export function CopyButton({ text, label, title }: { text: string; label: string; title?: string }) {
  const [done, setDone] = useState(false)
  return (
    <button
      type="button"
      title={title ?? label}
      onClick={async () => {
        if (await copyText(text)) {
          setDone(true)
          setTimeout(() => setDone(false), 1600)
        }
      }}
      className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-muted
        hover:bg-sidebar hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
    >
      {done ? <Check size={14} className="text-ok" /> : <Copy size={14} />}
      <span aria-live="polite">{done ? 'Copied' : label}</span>
    </button>
  )
}
