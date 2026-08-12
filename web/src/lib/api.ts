import type {
  BoardOverview,
  GraphResponse,
  JobEvent,
  LogsResponse,
  ProfilesResponse,
  StreamEvent,
  TasksResponse,
  ToolJob,
  ToolJobsResponse,
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
  jobs: (limit = 100, activeOnly = false) =>
    get<ToolJobsResponse>(
      `/jobs?limit=${limit}&active_only=${activeOnly}`,
    ),
}

export async function streamChat(
  text: string,
  user_id: string,
  onEvent: (ev: StreamEvent) => void,
  signal?: AbortSignal,
  session_id?: string,
): Promise<void> {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, user_id, session_id: session_id ?? '' }),
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

export async function fetchSessionJobs(
  sessionId: string,
  activeOnly = true,
): Promise<ToolJob[]> {
  const res = await fetch(
    `/api/chat/sessions/${sessionId}/jobs?active_only=${activeOnly}`,
  )
  if (!res.ok) throw new Error(`请求失败: ${res.status}`)
  const data = (await res.json()) as ToolJobsResponse
  return data.jobs
}

export type SseSubscribeOptions = {
  /** 断线重连时从该时间点 replay job_events */
  since?: number
  /** 收到带时间戳的事件时回调，用于持久化 since */
  onTimestamp?: (ts: number) => void
  /** 流断开后自动重连（默认 true） */
  reconnect?: boolean
}

function eventTimestamp(ev: StreamEvent | JobEvent): number | null {
  if ('ts' in ev && typeof ev.ts === 'number') return ev.ts
  if (ev.type === 'heartbeat' && typeof ev.ts === 'number') return ev.ts
  return null
}

async function readSseStream(
  url: string,
  onEvent: (ev: StreamEvent | JobEvent) => void,
  signal: AbortSignal | undefined,
  onTimestamp?: (ts: number) => void,
): Promise<void> {
  const res = await fetch(url, { signal })
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
      const ev = JSON.parse(raw) as StreamEvent | JobEvent
      onEvent(ev)
      const ts = eventTimestamp(ev)
      if (ts != null) onTimestamp?.(ts)
    }
  }
}

const SSE_RECONNECT_MS = 2000

export async function subscribeJobBoardEvents(
  onEvent: (ev: StreamEvent | JobEvent) => void,
  signal?: AbortSignal,
  options?: SseSubscribeOptions,
): Promise<void> {
  let since = options?.since ?? 0
  const reconnect = options?.reconnect ?? true
  const onTimestamp =
    options?.onTimestamp ??
    ((ts: number) => {
      since = ts
    })

  while (true) {
    if (signal?.aborted) return
    const url =
      since > 0 ? `/api/jobs/events?since=${since}` : '/api/jobs/events'
    try {
      await readSseStream(url, onEvent, signal, onTimestamp)
    } catch (e) {
      if ((e as Error).name === 'AbortError' || signal?.aborted) return
      if (!reconnect) throw e
      await new Promise((r) => setTimeout(r, SSE_RECONNECT_MS))
      continue
    }
    if (!reconnect || signal?.aborted) return
    await new Promise((r) => setTimeout(r, SSE_RECONNECT_MS))
  }
}

function jobEventToToolJob(ev: JobEvent): ToolJob {
  return {
    job_id: ev.job_id,
    session_id: ev.session_id,
    tool_name: ev.tool,
    status: ev.status,
    progress: ev.progress,
    result: ev.result,
    error: ev.error,
    result_ref: ev.result_ref,
  }
}

export function applyJobBoardEvent(
  jobs: ToolJob[],
  ev: StreamEvent | JobEvent,
): ToolJob[] {
  if (ev.type === 'snapshot') {
    return ev.jobs
  }
  if (ev.type === 'job' || ev.type === 'job_done' || ev.type === 'job_error') {
    const incoming = jobEventToToolJob(ev)
    const idx = jobs.findIndex((j) => j.job_id === incoming.job_id)
    if (idx >= 0) {
      const next = [...jobs]
      next[idx] = { ...next[idx], ...incoming }
      return next
    }
    return [incoming, ...jobs]
  }
  return jobs
}

export async function subscribeSessionEvents(
  sessionId: string,
  onEvent: (ev: StreamEvent | JobEvent) => void,
  signal?: AbortSignal,
  options?: SseSubscribeOptions,
): Promise<void> {
  let since = options?.since ?? 0
  const reconnect = options?.reconnect ?? true
  const onTimestamp =
    options?.onTimestamp ??
    ((ts: number) => {
      since = ts
    })

  while (true) {
    if (signal?.aborted) return
    const url =
      since > 0
        ? `/api/chat/sessions/${sessionId}/events?since=${since}`
        : `/api/chat/sessions/${sessionId}/events`
    try {
      await readSseStream(url, onEvent, signal, onTimestamp)
    } catch (e) {
      if ((e as Error).name === 'AbortError' || signal?.aborted) return
      if (!reconnect) throw e
      await new Promise((r) => setTimeout(r, SSE_RECONNECT_MS))
      continue
    }
    if (!reconnect || signal?.aborted) return
    await new Promise((r) => setTimeout(r, SSE_RECONNECT_MS))
  }
}
