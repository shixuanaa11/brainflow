import type {
  BoardOverview,
  GraphResponse,
  LogsResponse,
  ProfilesResponse,
  StreamEvent,
  TasksResponse,
  UsageSummary,
} from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`请求失败: ${res.status} ${path}`)
  return res.json() as Promise<T>
}

export const api = {
  board: () => get<BoardOverview>('/board'),
  tasks: () => get<TasksResponse>('/tasks'),
  profiles: () => get<ProfilesResponse>('/profiles'),
  usage: () => get<UsageSummary>('/analytics/usage'),
  logs: (n = 50) => get<LogsResponse>(`/logs?n=${n}`),
  graphs: () => get<GraphResponse>('/graphs'),
}

export async function streamChat(
  text: string,
  user_id: string,
  onEvent: (ev: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, user_id }),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`请求失败: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      const raw = line.replace(/^data: /, '')
      if (raw === '[DONE]') return
      onEvent(JSON.parse(raw) as StreamEvent)
    }
  }
}
