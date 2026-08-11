import type {
  ChatSession,
  ChatSessionDetail,
  ChatSessionsResponse,
  StoredChatMessage,
} from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`请求失败: ${res.status} ${path}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`请求失败: ${res.status} ${path}`)
  return res.json() as Promise<T>
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`请求失败: ${res.status} ${path}`)
}

export const chatHistoryApi = {
  listSessions: (userId = 'web', limit = 50) =>
    get<ChatSessionsResponse>(`/chat/sessions?user_id=${encodeURIComponent(userId)}&limit=${limit}`),

  createSession: (userId = 'web', title = '新对话') =>
    post<ChatSession>('/chat/sessions', { user_id: userId, title }),

  getSession: (sessionId: string) =>
    get<ChatSessionDetail>(`/chat/sessions/${sessionId}`),

  appendMessages: (sessionId: string, messages: StoredChatMessage[]) =>
    post<{ ok: boolean; count: number }>(`/chat/sessions/${sessionId}/messages`, { messages }),

  deleteSession: (sessionId: string) => del(`/chat/sessions/${sessionId}`),
}
