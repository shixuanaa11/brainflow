import { memo } from 'react'
import type { NodeProps } from '@xyflow/react'
import { Edge } from '@/components/ai-elements/edge'
import {
  Node as WorkflowNode,
  NodeContent,
  NodeDescription,
  NodeFooter,
  NodeHeader,
  NodeTitle,
} from '@/components/ai-elements/node'
import { Badge } from '@/components/ui/badge'
import type { BrainflowNodeData, BrainflowNodeKind } from '@/lib/mermaid-to-flow'
import { cn } from '@/lib/utils'
import { CircleDot, Play, Route, Sparkles, Square, Wrench } from 'lucide-react'

const KIND_META: Record<
  BrainflowNodeKind,
  { label: string; icon: typeof Route; badgeClass: string }
> = {
  start: {
    label: '入口',
    icon: Play,
    badgeClass: 'bg-muted text-muted-foreground',
  },
  router: {
    label: 'Router',
    icon: Route,
    badgeClass: 'bg-primary/10 text-primary',
  },
  tool: {
    label: 'Tool',
    icon: Wrench,
    badgeClass: 'bg-secondary text-secondary-foreground',
  },
  summary: {
    label: 'Summary',
    icon: Sparkles,
    badgeClass: 'bg-primary/10 text-primary',
  },
  end: {
    label: '出口',
    icon: Square,
    badgeClass: 'bg-muted text-muted-foreground',
  },
}

export const BrainflowWorkflowNode = memo(({ data }: NodeProps) => {
  const nodeData = data as unknown as BrainflowNodeData
  const meta = KIND_META[nodeData.kind]
  const Icon = meta.icon

  return (
    <WorkflowNode
      className={cn(
        'w-56 shadow-sm',
        nodeData.kind === 'router' && 'border-primary/30',
        nodeData.kind === 'summary' && 'border-primary/20',
      )}
      handles={nodeData.handles}
    >
      <NodeHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex items-center gap-2">
            <Icon className="size-3.5 shrink-0 text-muted-foreground" />
            <NodeTitle className="truncate text-sm">{nodeData.title}</NodeTitle>
          </div>
          <NodeDescription className="line-clamp-2 text-xs">
            {nodeData.description}
          </NodeDescription>
        </div>
        <Badge className={cn('shrink-0 rounded-full text-[10px]', meta.badgeClass)} variant="outline">
          {meta.label}
        </Badge>
      </NodeHeader>
      {nodeData.kind === 'tool' && nodeData.intent && (
        <NodeContent className="pt-0">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <CircleDot className="size-3" />
            条件边：<span className="font-medium text-foreground">{nodeData.intent}</span>
          </div>
        </NodeContent>
      )}
      <NodeFooter className="text-[10px] text-muted-foreground">
        {nodeData.kind === 'router' && '按 intent 路由至工具节点'}
        {nodeData.kind === 'tool' && '执行后进入 summary'}
        {nodeData.kind === 'summary' && '生成面向用户的最终回复'}
        {nodeData.kind === 'start' && 'START → router'}
        {nodeData.kind === 'end' && 'summary → END'}
      </NodeFooter>
    </WorkflowNode>
  )
})

BrainflowWorkflowNode.displayName = 'BrainflowWorkflowNode'

export const brainflowNodeTypes = {
  brainflow: BrainflowWorkflowNode,
}

export const brainflowEdgeTypes = {
  animated: Edge.Animated,
  temporary: Edge.Temporary,
}
