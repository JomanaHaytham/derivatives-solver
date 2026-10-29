import { ArrowUp } from 'lucide-react'
import { useEffect, useRef } from 'react'

const SYMBOLS: { label: string; insert: string; title: string }[] = [
  { label: 'x²', insert: '^2', title: 'Power: ^' },
  { label: '√', insert: 'sqrt()', title: 'Square root' },
  { label: 'π', insert: 'pi', title: 'Pi' },
  { label: 'eˣ', insert: 'e^()', title: 'Exponential' },
  { label: 'ln', insert: 'ln()', title: 'Natural log' },
  { label: 'sin', insert: 'sin()', title: 'Sine' },
  { label: 'cos', insert: 'cos()', title: 'Cosine' },
  { label: 'd/dx', insert: 'd/dx ', title: 'Derivative with respect to x' },
]

interface Props {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  busy: boolean
}

export function Composer({ value, onChange, onSubmit, busy }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [value])

  useEffect(() => {
    if (!busy) ref.current?.focus({ preventScroll: true })
  }, [busy])

  function insert(snippet: string) {
    const el = ref.current
    if (!el) return onChange(value + snippet)
    const start = el.selectionStart ?? value.length
    const end = el.selectionEnd ?? value.length
    const next = value.slice(0, start) + snippet + value.slice(end)
    onChange(next)
    // Put the caret inside the parentheses if the snippet has them.
    const caret = start + (snippet.endsWith('()') ? snippet.length - 1 : snippet.length)
    requestAnimationFrame(() => {
      el.focus()
      el.setSelectionRange(caret, caret)
    })
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
      className="rounded-2xl border border-line bg-panel p-2 shadow-sm focus-within:border-accent"
    >
      <label htmlFor="problem" className="sr-only">
        Type a derivative problem or a question
      </label>
      <textarea
        id="problem"
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            onSubmit()
          }
        }}
        placeholder="Type a problem, e.g. Differentiate x^2 sin(x) — or ask a question"
        className="block max-h-[180px] w-full resize-none bg-transparent px-2.5 py-2 text-[15px] text-ink outline-none placeholder:text-muted"
        maxLength={2000}
        spellCheck={false}
        autoComplete="off"
      />
      <div className="flex items-center gap-2">
        <div className="flex flex-1 gap-1 overflow-x-auto pb-0.5 [scrollbar-width:none]">
          {SYMBOLS.map((s) => (
            <button
              key={s.label}
              type="button"
              title={s.title}
              onClick={() => insert(s.insert)}
              className="shrink-0 rounded-md border border-line px-2 py-1 font-serif text-[13px] text-muted hover:border-accent hover:text-accent"
            >
              {s.label}
            </button>
          ))}
        </div>
        <button
          type="submit"
          disabled={busy || !value.trim()}
          aria-label="Send"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-accent text-white transition disabled:opacity-40 dark:text-paper"
        >
          <ArrowUp size={18} />
        </button>
      </div>
    </form>
  )
}
