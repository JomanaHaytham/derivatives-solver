import type { ChatMessage, ChatResponse, Health, SolutionContext } from './types'

/** "browser" = static build, the math engine runs in a web worker (no server). */
export const BROWSER_ENGINE = import.meta.env.VITE_ENGINE === 'browser'

// Same-origin by default (Vite proxies /api in dev; FastAPI serves the build in prod).
const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

export class ApiError extends Error {}

export async function sendChat(
  message: string,
  history: ChatMessage[],
  context: SolutionContext | null,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const payload = {
    message,
    input_type: 'text',
    history: history.filter((m) => !m.failed).map((m) => ({ role: m.role, content: m.content })),
    context,
  }

  if (BROWSER_ENGINE) {
    const { engineChat } = await import('../engine/client')
    return engineChat(payload)
  }

  const res = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new ApiError(res.status === 422 ? 'That message could not be sent (it may be empty or too long).' : `Server error (${res.status}).`)
  }
  return (await res.json()) as ChatResponse
}

export async function getHealth(): Promise<Health | null> {
  if (BROWSER_ENGINE) {
    try {
      const { engineReady } = await import('../engine/client')
      await engineReady()
      return { status: 'ok', ai_enabled: false, model: null }
    } catch {
      return null
    }
  }
  try {
    const res = await fetch(`${BASE}/api/health`)
    return res.ok ? ((await res.json()) as Health) : null
  } catch {
    return null
  }
}
