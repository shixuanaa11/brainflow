import { nanoid } from 'nanoid'
import type { DynamicToolUIPart } from 'ai'
import type { JobEvent, JobStatus, StoredChatMessage, ToolJob, WorkflowStep } from '@/lib/types'
import { toToolPart } from '@/lib/chat-workflow'

export interface ChatMessage {
  key: string
  from: 'user' | 'assistant'
  versions: { id: string; content: string }[]
  isContentComplete?: boolean
  steps?: WorkflowStep[]
  tools?: Array<{ name: string; part: DynamicToolUIPart }>
  jobId?: string
  jobStatus?: JobStatus
  pendingJob?: boolean
}

const ACTIVE_JOB_STATUSES: JobStatus[] = ['queued', 'submitted', 'running']

function isActiveJobStatus(status?: JobStatus) {
  return status ? ACTIVE_JOB_STATUSES.includes(status) : false
}

function jobWorkflowSteps(job: ToolJob, running: boolean): WorkflowStep[] {
  const toolNode = `tool_${job.tool_name}`
  return [
    {
      node: 'router',
      kind: 'router',
      label: '意图识别 (router)',
      status: 'done',
    },
    {
      node: toolNode,
      kind: 'tool',
      label: `工具调用 (${job.tool_name})`,
      status: running ? 'running' : 'done',
      output: job.result?.slice(0, 500),
    },
  ]
}

function toolPartFromJob(job: ToolJob, running: boolean): DynamicToolUIPart {
  const failed = ['error', 'timeout', 'cancelled'].includes(job.status)
  return toToolPart(
    job.tool_name,
    running ? 'input-available' : failed ? 'output-error' : 'output-available',
    { query: job.user_query ?? '' },
    job.result,
    job.error,
  )
}

export function applyJobToMessage(msg: ChatMessage, job: ToolJob): ChatMessage {
  const running = isActiveJobStatus(job.status)
  const toolNode = `tool_${job.tool_name}`
  const steps = msg.steps?.length
    ? msg.steps.map((s) =>
        s.node === toolNode || (s.kind === 'tool' && s.label.includes(job.tool_name))
          ? {
              ...s,
              status: running ? ('running' as const) : ('done' as const),
              output: job.result?.slice(0, 500),
            }
          : s.node === 'router'
            ? { ...s, status: 'done' as const }
            : s,
      )
    : jobWorkflowSteps(job, running)

  let versions = msg.versions
  if (!running) {
    const vid = msg.versions[0]?.id ?? nanoid()
    if (job.result) {
      versions = [{ id: vid, content: job.result }]
    } else if (job.error) {
      versions = [{
        id: vid,
        content: `任务 ${job.job_id} 执行失败：${job.error}`,
      }]
    }
  }

  return {
    ...msg,
    versions,
    jobId: job.job_id,
    jobStatus: job.status,
    pendingJob: running,
    steps,
    tools: [
      ...(msg.tools ?? []).filter((t) => t.name !== job.tool_name),
      { name: job.tool_name, part: toolPartFromJob(job, running) },
    ],
  }
}

function isReceiptContent(content: string) {
  return content.includes('已受理') || content.includes('后台执行')
}

function mergeAssistantJobMessages(a: ChatMessage, b: ChatMessage): ChatMessage {
  const ca = a.versions[0]?.content ?? ''
  const cb = b.versions[0]?.content ?? ''
  let content = ca
  if (isReceiptContent(ca) && cb && !isReceiptContent(cb)) content = cb
  else if (isReceiptContent(cb) && ca && !isReceiptContent(ca)) content = ca
  else content = cb.length > ca.length ? cb : ca

  const terminal = [a, b].find(
    (m) => m.jobStatus && !isActiveJobStatus(m.jobStatus),
  )
  const shell = terminal ?? ((b.steps?.length ?? 0) >= (a.steps?.length ?? 0) ? b : a)
  const status = shell.jobStatus ?? b.jobStatus ?? a.jobStatus ?? 'submitted'
  const toolName =
    shell.tools?.[0]?.name ?? b.tools?.[0]?.name ?? a.tools?.[0]?.name ?? ''

  return applyJobToMessage(
    {
      ...shell,
      jobId: shell.jobId ?? a.jobId ?? b.jobId,
      versions: [{ id: shell.versions[0]?.id ?? nanoid(), content }],
    },
    {
      job_id: shell.jobId ?? a.jobId ?? b.jobId ?? '',
      session_id: '',
      tool_name: toolName,
      status,
      progress: 100,
      result: !isActiveJobStatus(status) && !isReceiptContent(content) ? content : '',
      error: ['error', 'timeout', 'cancelled'].includes(status)
        ? content.replace(/^任务 .+ 执行失败：/, '')
        : '',
    },
  )
}

/** 合并同一 job_id 的多条 assistant（历史 outbox append 遗留） */
export function dedupeAssistantJobMessages(messages: ChatMessage[]): ChatMessage[] {
  const out: ChatMessage[] = []
  const idxByJob = new Map<string, number>()

  for (const m of messages) {
    if (m.from !== 'assistant' || !m.jobId) {
      out.push(m)
      continue
    }
    const idx = idxByJob.get(m.jobId)
    if (idx === undefined) {
      idxByJob.set(m.jobId, out.length)
      out.push(m)
      continue
    }
    out[idx] = mergeAssistantJobMessages(out[idx], m)
  }
  return out
}

/** LangGraph join stream：找图流尚未绑定 job_id 的在途 assistant turn */
export function findInflightAssistant(
  messages: ChatMessage[],
): ChatMessage | undefined {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i]
    if (
      m.from === 'assistant' &&
      !m.jobId &&
      (m.pendingJob === true || m.isContentComplete === false)
    ) {
      return m
    }
  }
  return undefined
}

function upsertJobMessage(messages: ChatMessage[], job: ToolJob): ChatMessage[] {
  const idx = messages.findIndex(
    (m) => m.from === 'assistant' && m.jobId === job.job_id,
  )
  if (idx >= 0) {
    const next = [...messages]
    next[idx] = applyJobToMessage(next[idx], job)
    return dedupeAssistantJobMessages(next)
  }
  const inflight = findInflightAssistant(messages)
  if (inflight) {
    return dedupeAssistantJobMessages(
      messages.map((m) =>
        m.key === inflight.key
          ? applyJobToMessage({ ...m, jobId: job.job_id }, job)
          : m,
      ),
    )
  }
  return dedupeAssistantJobMessages([...messages, pendingAssistantFromJob(job)])
}

export type JobBoardEvent =
  | JobEvent
  | { type: 'snapshot'; jobs: ToolJob[] }

/**
 * LangGraph 双通道合并：
 * - graph stream（/chat/stream）：图节点 updates，绑定 in-flight turn
 * - join stream（session/job SSE）：后台 job 状态 patch 同一 job_id
 */
export function applyJobEventToMessages(
  ev: JobBoardEvent,
  messages: ChatMessage[],
  options?: { graphStreaming?: boolean },
): ChatMessage[] {
  if (ev.type === 'snapshot') {
    if (options?.graphStreaming) {
      return dedupeAssistantJobMessages(messages)
    }
    return reconcileSessionJobs(messages, ev.jobs)
  }

  const job: ToolJob = {
    job_id: ev.job_id,
    session_id: ev.session_id,
    tool_name: ev.tool,
    status: ev.status,
    progress: ev.progress,
    result: ev.result,
    error: ev.error,
  }

  if (ev.type === 'job' && options?.graphStreaming) {
    return dedupeAssistantJobMessages(messages)
  }

  return upsertJobMessage(messages, job)
}

function pendingAssistantFromJob(job: ToolJob): ChatMessage {
  const running = isActiveJobStatus(job.status)
  const receipt = running
    ? `已受理，任务 \`${job.job_id}\` 已在后台执行（${job.tool_name}）。你可以离开本页，完成后结果会自动出现在对话中。`
    : job.result || job.error || `任务 ${job.job_id} 已结束`
  return {
    key: nanoid(),
    from: 'assistant',
    versions: [{ id: nanoid(), content: receipt }],
    isContentComplete: true,
    pendingJob: running,
    jobId: job.job_id,
    jobStatus: job.status,
    steps: jobWorkflowSteps(job, running),
    tools: [{ name: job.tool_name, part: toolPartFromJob(job, running) }],
  }
}

/** 用 tool_jobs 权威状态对齐消息里的 job UI（加载会话 / SSE snapshot 时用） */
export function reconcileSessionJobs(
  messages: ChatMessage[],
  jobs: ToolJob[],
): ChatMessage[] {
  const base = dedupeAssistantJobMessages(messages)
  if (!jobs.length) return base

  const jobsById = new Map(jobs.map((j) => [j.job_id, j]))
  let next = base.map((m) => {
    if (m.jobId && jobsById.has(m.jobId)) {
      return applyJobToMessage(m, jobsById.get(m.jobId)!)
    }
    return m
  })

  for (const job of jobs) {
    const hasAssistant = next.some(
      (m) => m.from === 'assistant' && m.jobId === job.job_id,
    )
    if (hasAssistant) continue

    const inflight = findInflightAssistant(next)
    if (inflight) {
      const idx = next.findIndex((m) => m.key === inflight.key)
      next[idx] = applyJobToMessage({ ...next[idx], jobId: job.job_id }, job)
      continue
    }

    next.push(pendingAssistantFromJob(job))
  }

  return dedupeAssistantJobMessages(next)
}

export function storedToChatMessages(stored: StoredChatMessage[]): ChatMessage[] {
  return stored.map((msg) => {
    const content = msg.content || ''
    const base: ChatMessage = {
      key: nanoid(),
      from: msg.role,
      versions: [{ id: nanoid(), content }],
      isContentComplete: true,
    }
    if (msg.role === 'assistant' && msg.meta) {
      base.steps = msg.meta.steps
      base.tools = (msg.meta.tools ?? []).map((t) => ({
        name: t.name,
        part: toToolPart(
          t.name,
          t.state as DynamicToolUIPart['state'],
          t.input,
          t.output,
          t.errorText,
        ),
      }))
      if (msg.meta.job_id) {
        base.jobId = msg.meta.job_id
        base.jobStatus = msg.meta.job_status
        base.pendingJob = isActiveJobStatus(msg.meta.job_status)
      }
    }
    return base
  })
}

export function buildStoredAssistant(
  assistant: {
    content: string
    steps?: WorkflowStep[]
    tools?: Array<{ name: string; part: DynamicToolUIPart }>
    jobId?: string
    jobStatus?: JobStatus
    tool?: string
  },
): StoredChatMessage[] {
  const meta: StoredChatMessage['meta'] = {
    steps: assistant.steps,
    tools: (assistant.tools ?? []).map((t) => ({
      name: t.name,
      state: t.part.state,
      input: t.part.input,
      output: t.part.output ? String(t.part.output) : undefined,
      errorText: t.part.errorText,
    })),
  }
  if (assistant.jobId) {
    meta.job_id = assistant.jobId
    meta.job_status = assistant.jobStatus
    meta.tool = assistant.tool
  }
  return [{
    role: 'assistant',
    content: assistant.content,
    meta,
  }]
}

export function buildStoredPair(
  userText: string,
  assistant: {
    content: string
    steps?: WorkflowStep[]
    tools?: Array<{ name: string; part: DynamicToolUIPart }>
    jobId?: string
    jobStatus?: JobStatus
    tool?: string
  },
): StoredChatMessage[] {
  const meta: StoredChatMessage['meta'] = {
    steps: assistant.steps,
    tools: (assistant.tools ?? []).map((t) => ({
      name: t.name,
      state: t.part.state,
      input: t.part.input,
      output: t.part.output ? String(t.part.output) : undefined,
      errorText: t.part.errorText,
    })),
  }
  if (assistant.jobId) {
    meta.job_id = assistant.jobId
    meta.job_status = assistant.jobStatus
    meta.tool = assistant.tool
  }
  return [
    { role: 'user', content: userText },
    {
      role: 'assistant',
      content: assistant.content,
      meta,
    },
  ]
}

/** @deprecated 请用 reconcileSessionJobs */
export function mergeActiveJobsIntoMessages(
  messages: ChatMessage[],
  jobs: ToolJob[],
): ChatMessage[] {
  return reconcileSessionJobs(messages, jobs)
}

export function assistantMessageFromJob(
  job: Pick<ToolJob, 'job_id' | 'tool_name' | 'result' | 'error' | 'status' | 'user_query'>,
): ChatMessage {
  const failed = ['error', 'timeout', 'cancelled'].includes(job.status)
  const content = failed
    ? `任务 ${job.job_id} 执行失败：${job.error ?? '未知错误'}`
    : (job.result ?? '')
  return {
    key: nanoid(),
    from: 'assistant',
    versions: [{ id: nanoid(), content }],
    isContentComplete: true,
    jobId: job.job_id,
    jobStatus: job.status as JobStatus,
    pendingJob: false,
    steps: jobWorkflowSteps(job as ToolJob, false),
    tools: [{
      name: job.tool_name,
      part: toToolPart(
        job.tool_name,
        failed ? 'output-error' : 'output-available',
        { query: job.user_query ?? '' },
        job.result,
        job.error,
      ),
    }],
  }
}
