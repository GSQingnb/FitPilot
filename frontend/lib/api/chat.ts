import { apiFetch } from "./client"

export interface ChatResponse {
  conv_id: string
  response: string
  intent: string
  agent_type: string
  escalated: boolean
  latency_ms: number
  knowledge_used: boolean
}

export async function sendMessage(message: string, convId?: string): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, conv_id: convId || null }),
  })
}
