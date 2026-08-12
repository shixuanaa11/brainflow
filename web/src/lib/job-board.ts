import type { JobStatus, ToolJob } from '@/lib/types'

export type JobColumnId = 'pending' | 'running' | 'done' | 'failed'

export interface JobColumn {
  id: JobColumnId
  title: string
  description: string
}

export const JOB_COLUMNS: JobColumn[] = [
  {
    id: 'pending',
    title: '已提交',
    description: '等待调度或刚受理',
  },
  {
    id: 'running',
    title: '执行中',
    description: '工具正在后台运行',
  },
  {
    id: 'done',
    title: '已完成',
    description: '执行成功并写入对话',
  },
  {
    id: 'failed',
    title: '失败 / 取消',
    description: '执行异常或已终止',
  },
]

const PENDING: JobStatus[] = ['queued', 'submitted']
const RUNNING: JobStatus[] = ['running']
const DONE: JobStatus[] = ['done']
const FAILED: JobStatus[] = ['error', 'timeout', 'cancelled']

export function jobColumnId(status: JobStatus): JobColumnId {
  if (PENDING.includes(status)) return 'pending'
  if (RUNNING.includes(status)) return 'running'
  if (DONE.includes(status)) return 'done'
  return 'failed'
}

export function groupJobsByColumn(jobs: ToolJob[]): Record<JobColumnId, ToolJob[]> {
  const groups: Record<JobColumnId, ToolJob[]> = {
    pending: [],
    running: [],
    done: [],
    failed: [],
  }
  for (const job of jobs) {
    groups[jobColumnId(job.status)].push(job)
  }
  for (const col of Object.keys(groups) as JobColumnId[]) {
    groups[col].sort((a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0))
  }
  return groups
}

export function jobStatusLabel(status: JobStatus): string {
  const map: Record<JobStatus, string> = {
    queued: '排队中',
    submitted: '已提交',
    running: '执行中',
    done: '已完成',
    error: '失败',
    timeout: '超时',
    cancelled: '已取消',
  }
  return map[status] ?? status
}

export function jobStatusVariant(
  status: JobStatus,
): 'success' | 'warning' | 'destructive' | 'secondary' {
  if (status === 'done') return 'success'
  if (status === 'running') return 'warning'
  if (FAILED.includes(status)) return 'destructive'
  return 'secondary'
}

export function summarizeJobs(jobs: ToolJob[]) {
  const groups = groupJobsByColumn(jobs)
  return {
    pending: groups.pending.length,
    running: groups.running.length,
    done: groups.done.length,
    failed: groups.failed.length,
    active: groups.pending.length + groups.running.length,
  }
}
