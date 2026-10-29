// Talks to the in-browser math engine running in a web worker.
// Used only in the static build (VITE_ENGINE=browser).

import type { ChatResponse } from '../lib/types'

const TIMEOUT_MS = 45_000

type Pending = { resolve: (r: ChatResponse) => void; reject: (e: Error) => void; timer: number }

let worker: Worker | null = null
let readyPromise: Promise<void> | null = null
let nextId = 1
const pending = new Map<number, Pending>()
const listeners = new Set<(stage: string) => void>()

export function onEngineProgress(fn: (stage: string) => void) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

function start(): Promise<void> {
  if (readyPromise) return readyPromise
  worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' })
  const base = new URL(import.meta.env.BASE_URL, document.baseURI).href
  readyPromise = new Promise<void>((resolve, reject) => {
    worker!.onmessage = (e: MessageEvent) => {
      const m = e.data
      if (m.type === 'progress') listeners.forEach((fn) => fn(m.stage))
      else if (m.type === 'ready') resolve()
      else if (m.type === 'failed') reject(new Error(m.error))
      else if (m.type === 'result' || m.type === 'error') {
        const p = pending.get(m.id)
        if (!p) return
        pending.delete(m.id)
        clearTimeout(p.timer)
        if (m.type === 'result') p.resolve(JSON.parse(m.result) as ChatResponse)
        else p.reject(new Error(m.error))
      }
    }
    worker!.onerror = (e) => reject(new Error(e.message || 'The math engine failed to start.'))
  })
  worker.postMessage({ type: 'init', base })
  readyPromise.catch(() => {
    readyPromise = null // allow a retry on the next request
    worker?.terminate()
    worker = null
  })
  return readyPromise
}

/** Restart the worker, e.g. after a computation ran too long. */
function restart() {
  worker?.terminate()
  worker = null
  readyPromise = null
  void start()
}

export function engineReady() {
  return start()
}

export async function engineChat(payload: object): Promise<ChatResponse> {
  await start()
  const id = nextId++
  return new Promise<ChatResponse>((resolve, reject) => {
    const timer = window.setTimeout(() => {
      pending.delete(id)
      restart()
      resolve({
        content:
          'That expression is too complex for me to simplify in a reasonable time. Could you try a smaller problem or split it into parts?',
        kind: 'error',
        source: 'engine',
        verified: null,
        context: null,
        warnings: [],
        practice: [],
      })
    }, TIMEOUT_MS)
    pending.set(id, { resolve, reject, timer })
    worker!.postMessage({ type: 'chat', id, payload: JSON.stringify(payload) })
  })
}
