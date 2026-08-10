import type { Edge, Node } from '@xyflow/react'
import { MarkerType } from '@xyflow/react'

export type BrainflowNodeKind = 'start' | 'router' | 'tool' | 'summary' | 'end'

export interface BrainflowNodeData {
  title: string
  description?: string
  kind: BrainflowNodeKind
  intent?: string
  handles: { target: boolean; source: boolean }
}

const COLUMN_X = {
  start: 0,
  router: 320,
  tool: 640,
  summary: 960,
  end: 1280,
} as const

const ROW_GAP = 92

function stripHtml(value: string) {
  return value.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim()
}

function nodeKind(id: string): BrainflowNodeKind {
  if (id === '__start__') return 'start'
  if (id === '__end__') return 'end'
  if (id === 'router') return 'router'
  if (id === 'summary') return 'summary'
  return 'tool'
}

function nodeTitle(id: string, rawLabel: string) {
  const label = stripHtml(rawLabel)
  if (id === '__start__') return '开始'
  if (id === '__end__') return '结束'
  if (id === 'router') return 'Router'
  if (id === 'summary') return 'Summary'
  if (id.startsWith('tool_')) return id.replace('tool_', '')
  return label || id
}

function nodeDescription(kind: BrainflowNodeKind, intent?: string) {
  switch (kind) {
    case 'start':
      return 'LangGraph 入口'
    case 'router':
      return 'LLM 意图识别 · 条件边分发'
    case 'tool':
      return intent ? `路由意图 · ${intent}` : '工具节点执行'
    case 'summary':
      return 'LLM 总结工具结果'
    case 'end':
      return '工作流结束'
  }
}

function parseMermaid(mermaid: string) {
  const nodeLabels = new Map<string, string>()
  const solidEdges: Array<{ source: string; target: string }> = []
  const dashedEdges: Array<{ source: string; target: string; label: string }> = []

  for (const raw of mermaid.split('\n')) {
    const line = raw.trim()
    if (
      !line ||
      line.startsWith('---') ||
      line.startsWith('config:') ||
      line === 'graph TD;' ||
      line.startsWith('classDef')
    ) {
      continue
    }

    const solid = line.match(/^([\w]+)\s+-->\s+([\w]+)/)
    if (solid) {
      solidEdges.push({ source: solid[1], target: solid[2] })
      continue
    }

    const dashed =
      line.match(/^([\w]+)\s+-\.\s*(.*?)\s*\.->\s+([\w]+)/) ??
      line.match(/^([\w]+)\s+-\.\s*\.->\s+([\w]+)/)
    if (dashed) {
      if (dashed.length === 4) {
        dashedEdges.push({
          source: dashed[1],
          target: dashed[3],
          label: stripHtml(dashed[2]),
        })
      } else {
        dashedEdges.push({
          source: dashed[1],
          target: dashed[2],
          label: '',
        })
      }
      continue
    }

    const def = line.match(/^([\w]+)\(([^)]*)\)/)
    if (def && !line.includes('-->') && !line.includes('-.->')) {
      nodeLabels.set(def[1], def[2])
    }
  }

  const nodeIds = new Set<string>()
  for (const e of [...solidEdges, ...dashedEdges]) {
    nodeIds.add(e.source)
    nodeIds.add(e.target)
  }
  for (const id of nodeLabels.keys()) nodeIds.add(id)

  const toolIntents = new Map<string, string>()
  for (const e of dashedEdges) {
    if (e.label) toolIntents.set(e.target, e.label)
  }

  return { nodeIds, nodeLabels, solidEdges, dashedEdges, toolIntents }
}

function layoutNodes(nodeIds: Set<string>, toolIntents: Map<string, string>, nodeLabels: Map<string, string>) {
  const tools = [...nodeIds]
    .filter((id) => nodeKind(id) === 'tool')
    .sort((a, b) => a.localeCompare(b))

  const toolCount = tools.length
  const toolsHeight = Math.max(toolCount - 1, 0) * ROW_GAP
  const toolsStartY = -toolsHeight / 2

  const nodes: Node[] = []

  const pushNode = (id: string, x: number, y: number) => {
    if (!nodeIds.has(id)) return
    const kind = nodeKind(id)
    const intent = toolIntents.get(id)
    nodes.push({
      id,
      type: 'brainflow',
      position: { x, y },
      data: {
        title: nodeTitle(id, nodeLabels.get(id) ?? id),
        description: nodeDescription(kind, intent),
        kind,
        intent,
        handles: {
          target: kind !== 'start',
          source: kind !== 'end',
        },
      },
    } as Node)
  }

  pushNode('__start__', COLUMN_X.start, 0)
  pushNode('router', COLUMN_X.router, 0)
  tools.forEach((id, i) => pushNode(id, COLUMN_X.tool, toolsStartY + i * ROW_GAP))
  pushNode('summary', COLUMN_X.summary, 0)
  pushNode('__end__', COLUMN_X.end, 0)

  return nodes
}

export function mermaidToFlow(mermaid: string): {
  nodes: Node[]
  edges: Edge[]
} {
  const { nodeIds, nodeLabels, solidEdges, dashedEdges, toolIntents } = parseMermaid(mermaid)

  const nodes = layoutNodes(nodeIds, toolIntents, nodeLabels)

  const edges: Edge[] = []

  for (const e of solidEdges) {
    edges.push({
      id: `${e.source}->${e.target}`,
      source: e.source,
      target: e.target,
      type: 'animated',
      markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--primary)' },
      style: { stroke: 'var(--primary)', strokeWidth: 1.5 },
    })
  }

  for (const e of dashedEdges) {
    edges.push({
      id: `${e.source}-.${e.target}`,
      source: e.source,
      target: e.target,
      type: 'temporary',
      label: e.label || undefined,
      labelStyle: { fill: 'var(--foreground)', fontSize: 11 },
      labelBgStyle: { fill: 'var(--background)', fillOpacity: 0.85 },
      labelBgPadding: [4, 6] as [number, number],
      labelBgBorderRadius: 4,
    })
  }

  return { nodes, edges }
}
