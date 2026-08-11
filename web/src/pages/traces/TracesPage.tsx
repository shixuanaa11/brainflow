import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import { api } from '@/lib/api'
import { PageHeader } from '@/components/layout/page-header'
import { SpanDetailDialog, TaskDetailDialog } from '@/components/traces/trace-detail-dialog'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { formatDuration } from '@/lib/utils'
import type { Span, Task } from '@/lib/types'
import { SpanWorkflowTimeline } from '@/components/workflow/span-workflow-timeline'
import { ChevronDown, ChevronRight, Eye } from 'lucide-react'

const durationChartConfig = {
  duration: { label: '耗时 (ms)', color: 'hsl(var(--chart-2))' },
} satisfies ChartConfig

function NodeBadge({ status }: { status: string }) {
  const map: Record<string, 'success' | 'warning' | 'destructive' | 'secondary'> = {
    ok: 'success',
    error: 'destructive',
    running: 'warning',
  }
  return <Badge variant={map[status] ?? 'secondary'}>{status}</Badge>
}

function SpanDurationChart({ task }: { task: Task }) {
  const data = useMemo(
    () =>
      task.spans.map((s) => ({
        node: s.node,
        duration: Math.round(s.duration * 1000),
      })),
    [task.spans],
  )

  if (data.length === 0) return null

  return (
    <div className="mt-4">
      <p className="mb-2 text-xs font-medium text-muted-foreground">节点耗时分布</p>
      <ChartContainer config={durationChartConfig} className="h-[160px] w-full">
        <BarChart data={data} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="node"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11 }}
            interval={0}
          />
          <YAxis hide />
          <ChartTooltip
            cursor={false}
            content={
              <ChartTooltipContent
                formatter={(value) => [`${value} ms`, '耗时']}
              />
            }
          />
          <Bar dataKey="duration" fill="var(--color-duration)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ChartContainer>
    </div>
  )
}

function SpanTable({
  task,
  onViewSpan,
}: {
  task: Task
  onViewSpan: (span: Span) => void
}) {
  return (
    <div className="mt-3 overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
            <th className="p-2 font-medium">节点</th>
            <th className="p-2 font-medium">类型</th>
            <th className="p-2 font-medium">状态</th>
            <th className="p-2 font-medium">耗时</th>
            <th className="p-2 font-medium">Token</th>
            <th className="p-2 font-medium">输入</th>
            <th className="p-2 font-medium">输出</th>
            <th className="p-2 font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          {task.spans.map((s, i) => (
            <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
              <td className="p-2 font-medium">{s.node}</td>
              <td className="p-2 text-muted-foreground">{s.kind}</td>
              <td className="p-2">
                <NodeBadge status={s.status} />
              </td>
              <td className="p-2 tabular-nums">{formatDuration(s.duration * 1000)}</td>
              <td className="p-2 tabular-nums">{s.tokens ?? 0}</td>
              <td className="max-w-[160px] truncate p-2 text-muted-foreground" title={s.input}>
                {s.input || '-'}
              </td>
              <td className="max-w-[180px] truncate p-2 text-muted-foreground" title={s.output}>
                {s.output || '-'}
              </td>
              <td className="p-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  className="gap-1"
                  onClick={() => onViewSpan(s)}
                >
                  <Eye className="size-3.5" />
                  详情
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TaskItem({ task }: { task: Task }) {
  const [open, setOpen] = useState(false)
  const [taskDetailOpen, setTaskDetailOpen] = useState(false)
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null)
  const totalMs = task.spans.reduce((acc, s) => acc + s.duration * 1000, 0)

  return (
    <>
      <Card className="overflow-hidden">
        <div className="flex items-start gap-2 p-4">
          <button
            type="button"
            className="mt-0.5 shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            onClick={() => setOpen(!open)}
            aria-label={open ? '收起' : '展开'}
          >
            {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          </button>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{task.trace_id}</span>
              <Badge variant="secondary">{task.workflow}</Badge>
              <NodeBadge status={task.status} />
            </div>
            <p className="mt-1 line-clamp-2 text-sm">{task.input}</p>
          </div>

          <div className="flex shrink-0 flex-col items-end gap-2">
            <div className="text-right text-xs text-muted-foreground">
              <div>{new Date(task.timestamp * 1000).toLocaleTimeString('zh-CN')}</div>
              <div>
                {task.spans.length} 节点 · {formatDuration(totalMs)}
              </div>
            </div>
            <Button type="button" variant="outline" size="xs" className="gap-1" onClick={() => setTaskDetailOpen(true)}>
              <Eye className="size-3.5" />
              任务详情
            </Button>
          </div>
        </div>

        {open && (
          <div className="border-t px-4 pb-4">
            {task.spans.length > 0 ? (
              <>
                <SpanWorkflowTimeline spans={task.spans} />
                <SpanDurationChart task={task} />
                <SpanTable task={task} onViewSpan={setSelectedSpan} />
              </>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">无节点记录</p>
            )}
          </div>
        )}
      </Card>

      <TaskDetailDialog task={task} open={taskDetailOpen} onOpenChange={setTaskDetailOpen} />
      <SpanDetailDialog
        span={selectedSpan}
        traceId={task.trace_id}
        open={selectedSpan != null}
        onOpenChange={(next) => {
          if (!next) setSelectedSpan(null)
        }}
      />
    </>
  )
}

function TracesSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-20 rounded-xl" />
      ))}
    </div>
  )
}

export default function TracesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: api.tasks,
    refetchInterval: 10_000,
  })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="任务链路追踪"
        description="节点级观测 · 状态 / 耗时 / 输入输出 / Token · 每 10s 自动刷新"
        action={
          data?.count != null ? (
            <Badge variant="outline">{data.count} 条记录</Badge>
          ) : undefined
        }
      />

      {isLoading ? (
        <TracesSkeleton />
      ) : !data?.tasks.length ? (
        <Card>
          <CardHeader>
            <CardTitle>暂无任务</CardTitle>
            <CardDescription>先去 AI 对话页发起一次请求，链路数据将自动出现在这里</CardDescription>
          </CardHeader>
          <CardContent className="pb-8 text-center text-sm text-muted-foreground">
            等待第一条 trace 写入…
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {data.tasks.map((t) => (
            <TaskItem key={t.trace_id} task={t} />
          ))}
        </div>
      )}
    </div>
  )
}
