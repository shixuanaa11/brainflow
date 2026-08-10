import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ReactFlowProvider } from '@xyflow/react'
import { api } from '@/lib/api'
import { mermaidToFlow } from '@/lib/mermaid-to-flow'
import { PageHeader } from '@/components/layout/page-header'
import { Canvas } from '@/components/ai-elements/canvas'
import { Connection } from '@/components/ai-elements/connection'
import { Controls } from '@/components/ai-elements/controls'
import { Panel } from '@/components/ai-elements/panel'
import {
  brainflowEdgeTypes,
  brainflowNodeTypes,
} from '@/components/workflow/brainflow-workflow-node'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { RefreshCw } from 'lucide-react'

function WorkflowCanvas({ mermaid }: { mermaid: string }) {
  const { nodes, edges } = useMemo(() => mermaidToFlow(mermaid), [mermaid])

  return (
    <ReactFlowProvider>
      <div className="h-[min(72vh,720px)] w-full overflow-hidden rounded-lg border bg-sidebar">
        <Canvas
          connectionLineComponent={Connection}
          edges={edges}
          edgeTypes={brainflowEdgeTypes}
          nodes={nodes}
          nodeTypes={brainflowNodeTypes}
          nodesConnectable={false}
          nodesDraggable={false}
          elementsSelectable={false}
          panOnDrag
          panOnScroll
          panActivationKeyCode="Space"
          selectionOnDrag={false}
          zoomOnScroll
          minZoom={0.35}
          maxZoom={1.25}
          proOptions={{ hideAttribution: true }}
        >
          <Controls showInteractive={false} />
          <Panel className="m-3 max-w-xs p-3 text-xs">
            <p className="font-medium text-foreground">图例</p>
            <div className="mt-2 flex flex-col gap-1.5 text-muted-foreground">
              <div className="flex items-center gap-2">
                <span className="inline-block h-0.5 w-6 bg-primary" />
                主路径 / 工具 → summary
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block w-6 border-t border-dashed border-ring" />
                router 条件边（intent）
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-1">
              <Badge variant="outline">节点 {nodes.length}</Badge>
              <Badge variant="outline">边 {edges.length}</Badge>
            </div>
            <p className="mt-3 text-[10px] leading-relaxed text-muted-foreground">
              拖拽空白区域平移 · 按住 Space 拖拽可越过节点 · 滚轮缩放
            </p>
          </Panel>
        </Canvas>
      </div>
    </ReactFlowProvider>
  )
}

export default function GraphPage() {
  const { data, isLoading, refetch, isFetching, isError } = useQuery({
    queryKey: ['graphs'],
    queryFn: api.graphs,
  })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="工作流图"
        description="AI Elements Workflow · React Flow 交互画布 · router → 工具 → summary"
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={cn(isFetching && 'animate-spin')} />
            刷新
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>LangGraph 工作流</CardTitle>
          <CardDescription>
            基于后端 Mermaid 自动布局，支持缩放 / 平移 / 动效连线（参考{' '}
            <a
              className="underline underline-offset-2 hover:text-foreground"
              href="https://elements.ai-sdk.dev/examples/workflow"
              rel="noreferrer"
              target="_blank"
            >
              AI Elements Workflow
            </a>
            ）
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col gap-3 py-12">
              <Skeleton className="mx-auto h-8 w-48" />
              <Skeleton className="h-[min(72vh,720px)] w-full rounded-lg" />
            </div>
          ) : isError || !data?.mermaid ? (
            <div className="py-20 text-center text-muted-foreground">
              工作流图加载失败，请查看后端日志
            </div>
          ) : (
            <WorkflowCanvas mermaid={data.mermaid} />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
