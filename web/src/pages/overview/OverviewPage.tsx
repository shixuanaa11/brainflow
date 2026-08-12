import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, XAxis, YAxis } from 'recharts'
import { api } from '@/lib/api'
import { PageHeader } from '@/components/layout/page-header'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { cn, formatNumber } from '@/lib/utils'
import { Activity, Coins, AlertTriangle, Wrench, Server, KanbanSquare } from 'lucide-react'
import { Link } from 'react-router-dom'

const CHART_COLORS = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-4))',
  'hsl(var(--chart-5))',
]

const callsChartConfig = {
  calls: { label: '调用次数', color: 'hsl(var(--chart-1))' },
} satisfies ChartConfig

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  className,
}: {
  label: string
  value: string
  sub?: string
  icon: React.ComponentType<{ className?: string }>
  className?: string
}) {
  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex flex-col gap-1">
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="text-3xl font-bold tracking-tight tabular-nums">{value}</p>
            {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
          </div>
          <div className="rounded-lg bg-primary/10 p-2.5 text-primary">
            <Icon className="size-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function OverviewSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-4 w-72" />
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-80 rounded-xl lg:col-span-2" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
    </div>
  )
}

export default function OverviewPage() {
  const { data: board, isLoading } = useQuery({ queryKey: ['board'], queryFn: api.board })
  const { data: usage } = useQuery({ queryKey: ['usage'], queryFn: api.usage })

  const toolCallsData = useMemo(() => {
    return Object.entries(usage?.by_tool ?? {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([tool, calls]) => ({ tool, calls }))
  }, [usage?.by_tool])

  const tokenPieData = useMemo(() => {
    return Object.entries(usage?.by_tool_tokens ?? {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([tool, tokens], i) => ({
        tool,
        tokens,
        fill: CHART_COLORS[i % CHART_COLORS.length],
      }))
  }, [usage?.by_tool_tokens])

  const tokenChartConfig = useMemo(() => {
    const config: ChartConfig = { tokens: { label: 'Token' } }
    tokenPieData.forEach((item, i) => {
      config[item.tool] = {
        label: item.tool,
        color: CHART_COLORS[i % CHART_COLORS.length],
      }
    })
    return config
  }, [tokenPieData])

  if (isLoading || !board) {
    return <OverviewSkeleton />
  }

  const uptimeHours = (board.uptime_seconds / 3600).toFixed(1)
  const errorRatePct = (board.error_rate * 100).toFixed(2)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="总览看板"
        description="系统运行状态 · 调用量 · Token 消耗 · 工具活跃度"
        action={
          <Badge variant={board.status === 'healthy' ? 'success' : 'warning'}>
            {board.status === 'healthy' ? '运行健康' : '需要关注'}
          </Badge>
        }
      />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
        <StatCard label="总调用" value={formatNumber(board.total_calls)} icon={Activity} />
        <StatCard label="Token 消耗" value={formatNumber(board.total_tokens)} icon={Coins} />
        <StatCard
          label="错误"
          value={formatNumber(board.total_errors)}
          icon={AlertTriangle}
          sub={`错误率 ${errorRatePct}%`}
        />
        <StatCard label="活跃工具" value={formatNumber(board.active_tools)} icon={Wrench} />
        <Link to="/jobs" className="block">
          <StatCard
            label="进行中任务"
            value={formatNumber(board.tool_jobs?.active ?? 0)}
            icon={KanbanSquare}
            sub={
              board.tool_jobs?.total
                ? `累计 ${formatNumber(board.tool_jobs.total)} 个 job`
                : '异步工具任务'
            }
            className="transition-colors hover:border-primary/40"
          />
        </Link>
      </div>

      {(board.tool_jobs?.active ?? 0) > 0 && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <p className="text-sm font-medium">
                {board.tool_jobs?.active} 个工具任务正在后台执行
              </p>
              <p className="text-xs text-muted-foreground">
                可在工具任务看板查看全队列状态，或在 AI 对话中查看单会话进度
              </p>
            </div>
            <Button asChild size="sm" variant="outline">
              <Link to="/jobs">打开工具任务看板</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>工具调用分布</CardTitle>
            <CardDescription>各工具累计调用次数 Top 8</CardDescription>
          </CardHeader>
          <CardContent>
            {toolCallsData.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">暂无数据</p>
            ) : (
              <ChartContainer config={callsChartConfig} className="h-[280px] w-full">
                <BarChart data={toolCallsData} layout="vertical" margin={{ left: 8, right: 8 }}>
                  <CartesianGrid horizontal={false} />
                  <YAxis
                    dataKey="tool"
                    type="category"
                    width={100}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 12 }}
                  />
                  <XAxis type="number" hide />
                  <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
                  <Bar dataKey="calls" fill="var(--color-calls)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Token 分布</CardTitle>
            <CardDescription>按工具 Token 消耗占比</CardDescription>
          </CardHeader>
          <CardContent>
            {tokenPieData.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">暂无数据</p>
            ) : (
              <ChartContainer config={tokenChartConfig} className="mx-auto h-[280px] w-full">
                <PieChart>
                  <ChartTooltip content={<ChartTooltipContent nameKey="tool" hideLabel />} />
                  <Pie
                    data={tokenPieData}
                    dataKey="tokens"
                    nameKey="tool"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                  >
                    {tokenPieData.map((entry) => (
                      <Cell key={entry.tool} fill={entry.fill} />
                    ))}
                  </Pie>
                </PieChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>系统状态</CardTitle>
          <CardDescription>运行时长与关键指标摘要</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 sm:grid-cols-3">
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  'rounded-lg p-2.5',
                  board.status === 'healthy'
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                    : 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
                )}
              >
                <Server className="size-5" />
              </div>
              <div className="flex flex-col gap-0.5">
                <p className="text-sm font-medium">
                  {board.status === 'healthy' ? '服务正常' : '需要关注'}
                </p>
                <p className="text-xs text-muted-foreground">已运行 {uptimeHours} 小时</p>
              </div>
            </div>
            <div className="flex flex-col gap-1 rounded-lg border bg-muted/30 p-4">
              <span className="text-xs text-muted-foreground">累计 Token</span>
              <span className="text-xl font-semibold tabular-nums">
                {formatNumber(usage?.total_tokens ?? 0)}
              </span>
            </div>
            <div className="flex flex-col gap-1 rounded-lg border bg-muted/30 p-4">
              <span className="text-xs text-muted-foreground">错误调用</span>
              <span className="text-xl font-semibold tabular-nums">
                {formatNumber(board.total_errors)}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
