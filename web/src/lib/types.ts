// BrainFlow 后端 API 数据结构定义

export interface BoardOverview {
  uptime_seconds: number
  total_calls: number
  total_tokens: number
  total_errors: number
  error_rate: number
  active_tools: number
  top_tools: [string, number][]
  status: 'healthy' | 'degraded'
  tool_jobs?: ToolJobSummary
}

export interface ToolJobSummary {
  total: number
  active: number
  by_status: Record<string, number>
}

export interface Span {
  node: string
  kind: 'router' | 'tool' | 'summary'
  duration: number
  status: string
  detail?: string
  input?: string
  output?: string
  tokens: number
}

export interface Task {
  trace_id: string
  workflow: string
  user: string
  input: string
  status: string
  timestamp: number
  spans: Span[]
}

export interface TasksResponse {
  tasks: Task[]
  count: number
}

export interface Profile {
  tool: string
  calls: number
  tokens: number
}

export interface ProfilesResponse {
  profiles: Profile[]
  count: number
}

export interface UsageSummary {
  total_calls: number
  total_tokens: number
  total_errors: number
  by_tool: Record<string, number>
  by_tool_tokens: Record<string, number>
}

export interface LogEntry {
  tool: string
  tokens: number
  error: string
  latency: number
  user: string
  time: number
}

export interface LogsResponse {
  logs: LogEntry[]
}

export interface GraphResponse {
  id: string
  mermaid: string
}

// SSE 流式对话事件
export type StreamEvent =
  | { type: 'start' }
  | { type: 'node'; node: string }
  | {
      type: 'step'
      node: string
      kind: 'router' | 'tool' | 'summary' | 'qa'
      status: 'running' | 'done' | 'error'
      intent?: string
      tool?: string
      output?: string
      message?: string
      async?: boolean
      job_id?: string
    }
  | { type: 'reply'; reply: string }
  | { type: 'error'; message: string }
  | JobEvent
  | { type: 'snapshot'; jobs: ToolJob[] }
  | { type: 'heartbeat'; ts?: number }

export type JobStatus =
  | 'queued'
  | 'submitted'
  | 'running'
  | 'done'
  | 'error'
  | 'timeout'
  | 'cancelled'

export interface ToolJob {
  job_id: string
  session_id: string
  tool_name: string
  status: JobStatus
  progress: number
  result?: string
  error?: string
  result_ref?: string
  user_query?: string
  created_at?: number
  updated_at?: number
}

export type JobEvent =
  | {
      type: 'job'
      job_id: string
      session_id: string
      tool: string
      status: JobStatus
      progress: number
      result?: string
      error?: string
      result_ref?: string
      ts?: number
      replay?: boolean
    }
  | {
      type: 'job_done'
      job_id: string
      session_id: string
      tool: string
      status: 'done'
      progress: number
      result?: string
      error?: string
      result_ref?: string
      ts?: number
      replay?: boolean
    }
  | {
      type: 'job_error'
      job_id: string
      session_id: string
      tool: string
      status: 'error' | 'timeout' | 'cancelled'
      progress: number
      result?: string
      error?: string
      result_ref?: string
      ts?: number
      replay?: boolean
    }

export type WorkflowStepStatus = 'pending' | 'running' | 'done' | 'error'

export interface WorkflowStep {
  node: string
  kind: 'router' | 'tool' | 'summary'
  label: string
  status: WorkflowStepStatus
  intent?: string
  output?: string
  error?: string
}

// 聊天历史
export interface ChatSession {
  session_id: string
  user_id: string
  title: string
  created_at: number
  updated_at: number
}

export interface ChatSessionsResponse {
  sessions: ChatSession[]
  count: number
}

export interface StoredChatMessage {
  role: 'user' | 'assistant'
  content: string
  created_at?: number
  meta?: {
    job_id?: string
    job_status?: JobStatus
    tool?: string
    steps?: WorkflowStep[]
    tools?: Array<{
      name: string
      state: string
      input?: unknown
      output?: string
      errorText?: string
    }>
  }
}

export interface ChatSessionDetail extends ChatSession {
  messages: StoredChatMessage[]
}

export interface ToolJobsResponse {
  jobs: ToolJob[]
  count: number
  summary?: ToolJobSummary
}