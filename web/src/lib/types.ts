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
      kind: 'router' | 'tool' | 'summary'
      status: 'running' | 'done' | 'error'
      intent?: string
      tool?: string
      output?: string
      message?: string
    }
  | { type: 'reply'; reply: string }
  | { type: 'error'; message: string }

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