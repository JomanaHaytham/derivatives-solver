import { EXAMPLE_PROMPTS } from '../data/samples'

export function EmptyState({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center px-4 pt-[8vh] pb-8 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-accent font-serif text-2xl italic text-white dark:text-paper">f′</div>
      <h1 className="mt-5 font-serif text-3xl font-semibold tracking-tight sm:text-[34px]">What would you like to differentiate?</h1>
      <p className="mt-3 max-w-md text-[15px] text-muted">
        Type any function and get a step-by-step solution. Every answer is checked by a symbolic math engine, and you can
        ask follow-up questions about any step.
      </p>
      <div className="mt-8 grid w-full gap-2.5 sm:grid-cols-2">
        {EXAMPLE_PROMPTS.map((ex) => (
          <button
            key={ex.prompt}
            onClick={() => onPick(ex.prompt)}
            className="group rounded-xl border border-line bg-panel px-4 py-3 text-left transition hover:border-accent"
          >
            <div className="text-[11px] font-medium uppercase tracking-wide text-muted group-hover:text-accent">{ex.topic}</div>
            <div className="mt-0.5 font-serif text-[16px] text-ink">{ex.label}</div>
          </button>
        ))}
      </div>
      <p className="mt-6 text-xs text-muted">
        Tip: write powers with <code className="rounded bg-sidebar px-1">^</code>, e.g. <code className="rounded bg-sidebar px-1">(x^2+1)^5</code>. Implicit:{' '}
        <code className="rounded bg-sidebar px-1">find dy/dx if x^2 + y^2 = 25</code>
      </p>
    </div>
  )
}
