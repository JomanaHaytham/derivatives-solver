export type Role = 'user' | 'assistant'

export type MessageKind = 'solution' | 'follow_up' | 'clarification' | 'out_of_scope' | 'error'

/** Summary of the last solved problem, produced by the backend and echoed back on follow-ups. */
export interface SolutionContext {
  original: string
  original_latex: string
  variable: string
  order: number
  implicit: boolean
  derivative: string
  derivative_latex: string
  answer_latex: string
  rules: string[]
  verified: boolean
  verification_method: string
}

export interface ChatMessage {
  id: string
  role: Role
  content: string
  createdAt: number
  kind?: MessageKind
  source?: 'ai' | 'engine'
  verified?: boolean | null
  context?: SolutionContext | null
  warnings?: string[]
  practice?: string[]
  failed?: boolean
}

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}

export interface ChatResponse {
  content: string
  kind: MessageKind
  source: 'ai' | 'engine'
  verified: boolean | null
  context: SolutionContext | null
  warnings: string[]
  practice: string[]
}

export interface Health {
  status: string
  ai_enabled: boolean
  model: string | null
}
