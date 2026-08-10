import type { DynamicToolUIPart } from 'ai'
import type { WorkflowStep, WorkflowStepStatus } from '@/lib/types'

export const STEP_LABELS: Record<string, string> = {
  router: '意图识别',
  summary: '生成回复',
}

export function stepLabel(node: string, kind: WorkflowStep['kind'], tool?: string) {
  if (kind === 'router') return '意图识别 (router)'
  if (kind === 'summary') return '总结回复 (summary)'
  return `工具调用 (${tool ?? node.replace('tool_', '')})`
}

export function applyStreamStep(steps: WorkflowStep[], ev: {
  node: string
  kind: 'router' | 'tool' | 'summary'
  status: 'running' | 'done' | 'error'
  intent?: string
  tool?: string
  output?: string
  message?: string
}): WorkflowStep[] {
  const next = steps.map((s) => ({ ...s }))

  const upsert = (
    node: string,
    kind: WorkflowStep['kind'],
    status: WorkflowStepStatus,
    extra?: Partial<WorkflowStep>,
  ) => {
    const idx = next.findIndex((s) => s.node === node)
    const item: WorkflowStep = {
      node,
      kind,
      label: stepLabel(node, kind, ev.tool),
      status,
      ...extra,
    }
    if (idx >= 0) next[idx] = { ...next[idx], ...item }
    else next.push(item)
  }

  if (ev.status === 'running') {
    upsert(ev.node, ev.kind, 'running')
    return next
  }

  if (ev.status === 'error') {
    upsert(ev.node, ev.kind, 'error', { error: ev.message })
    return next
  }

  // done
  upsert(ev.node, ev.kind, 'done', {
    intent: ev.intent,
    output: ev.output,
  })

  if (ev.kind === 'router' && ev.intent) {
    const toolNode = `tool_${ev.intent}`
    if (!next.some((s) => s.node === toolNode)) {
      next.push({
        node: toolNode,
        kind: 'tool',
        label: stepLabel(toolNode, 'tool', ev.intent),
        status: 'running',
      })
    }
  }

  if (ev.kind === 'tool' && !next.some((s) => s.node === 'summary')) {
    next.push({
      node: 'summary',
      kind: 'summary',
      label: stepLabel('summary', 'summary'),
      status: 'running',
    })
  }

  if (ev.kind === 'tool') {
    const summary = next.find((s) => s.node === 'summary')
    if (summary && summary.status === 'pending') summary.status = 'running'
  }

  return next
}

export function toToolPart(
  toolName: string,
  state: DynamicToolUIPart['state'],
  input: unknown,
  output?: string,
  errorText?: string,
): DynamicToolUIPart {
  return {
    type: 'dynamic-tool',
    toolName,
    toolCallId: toolName,
    state,
    input,
    output,
    errorText,
  } as DynamicToolUIPart
}

export function chainStatus(step: WorkflowStep): 'complete' | 'active' | 'pending' {
  if (step.status === 'done') return 'complete'
  if (step.status === 'running') return 'active'
  return 'pending'
}

export const SUGGESTIONS = [
  '深圳今天天气怎么样',
  '帮我查一下最新新闻',
  '总结一下 LangGraph 工作流',
  '北京明天需要带伞吗',
]
