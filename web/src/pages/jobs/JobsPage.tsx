import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Clock3,
  ExternalLink,
  Loader2,
  MessageSquare,
  RefreshCw,
  Wrench,
} from 'lucide-react'
import { PageHeader } from '@/components/layout/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { api, applyJobBoardEvent, subscribeJobBoardEvents } from '@/lib/api'
import {
  groupJobsByColumn,
  JOB_COLUMNS,
  jobStatusLabel,
  jobStatusVariant,
  summarizeJobs,
} from '@/lib/job-board'
import { formatNumber } from '@/lib/utils'
import type { JobEvent, StreamEvent, ToolJob } from '@/lib/types'

function formatTime(ts?: number) {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function JobCard({ job }: { job: ToolJob }) {
  const queryPreview = (job.user_query || job.input || '').slice(0, 120)

  return (
    <Card className="border-border/70 shadow-sm transition-shadow hover:shadow-md">
      <CardContent className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Wrench className="size-3.5 shrink-0 text-primary" />
              <span className="truncate font-medium">{job.tool_name}</span>
            </div>
            <p className="mt-1 truncate font-mono text-xs text-muted-foreground">
              {job.job_id}
            </p>
          </div>
          <Badge variant={jobStatusVariant(job.status)}>
            {jobStatusLabel(job.status)}
          </Badge>
        </div>

        {queryPreview ? (
          <p className="line-clamp-2 text-sm text-muted-foreground">{queryPreview}</p>
        ) : null}

        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Clock3 className="size-3" />
            {formatTime(job.updated_at ?? job.created_at)}
          </span>
          <span>{job.progress ?? 0}%</span>
        </div>

        {job.status === 'running' || job.status === 'submitted' ? (
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${Math.max(job.progress ?? 0, job.status === 'running' ? 10 : 4)}%` }}
            />
          </div>
        ) : null}

        {job.result ? (
          <p className="line-clamp-3 rounded-md bg-muted/40 p-2 text-xs">{job.result}</p>
        ) : null}
        {job.error ? (
          <p className="line-clamp-2 rounded-md bg-destructive/10 p-2 text-xs text-destructive">
            {job.error}
          </p>
        ) : null}

        <div className="flex items-center gap-2 pt-1">
          <Button asChild size="xs" variant="outline" className="gap-1">
            <Link to={`/chat?session=${job.session_id}`}>
              <MessageSquare className="size-3" />
              查看对话
            </Link>
          </Button>
          <span className="truncate font-mono text-[10px] text-muted-foreground">
            session:{job.session_id}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

function KanbanColumn({
  title,
  description,
  jobs,
  highlight,
}: {
  title: string
  description: string
  jobs: ToolJob[]
  highlight?: boolean
}) {
  return (
    <div className="flex min-h-[420px] flex-col rounded-xl border bg-muted/20">
      <div className="border-b px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold">{title}</h3>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
          <Badge variant={highlight ? 'warning' : 'secondary'}>{jobs.length}</Badge>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
        {jobs.length === 0 ? (
          <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed bg-background/40 p-6 text-center text-xs text-muted-foreground">
            暂无任务
          </div>
        ) : (
          jobs.map((job) => <JobCard key={job.job_id} job={job} />)
        )}
      </div>
    </div>
  )
}

function JobsSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-[420px] rounded-xl" />
      ))}
    </div>
  )
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<ToolJob[]>([])
  const [live, setLive] = useState(true)
  const eventsRef = useRef<AbortController | null>(null)

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => api.jobs(100),
  })

  useEffect(() => {
    if (data?.jobs) setJobs(data.jobs)
  }, [data?.jobs])

  const handleBoardEvent = useCallback((ev: StreamEvent | JobEvent) => {
    if (ev.type === 'heartbeat') return
    setJobs((prev) => applyJobBoardEvent(prev, ev))
  }, [])

  useEffect(() => {
    if (!live) {
      eventsRef.current?.abort()
      return
    }
    eventsRef.current?.abort()
    const controller = new AbortController()
    eventsRef.current = controller

    void (async () => {
      try {
        await subscribeJobBoardEvents(handleBoardEvent, controller.signal, {
          reconnect: true,
        })
      } catch (e) {
        if ((e as Error).name !== 'AbortError') {
          // 自动重连失败时静默，用户可手动刷新
        }
      }
    })()

    return () => controller.abort()
  }, [live, handleBoardEvent])

  const grouped = useMemo(() => groupJobsByColumn(jobs), [jobs])
  const stats = useMemo(() => summarizeJobs(jobs), [jobs])

  if (isLoading && jobs.length === 0) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="工具任务看板" description="异步工具 job 状态 · 实时 SSE 更新" />
        <JobsSkeleton />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="工具任务看板"
        description="异步工具 job 全览 · 按状态分列 · 实时推送"
        action={
          <div className="flex items-center gap-2">
            <Badge variant={live ? 'success' : 'secondary'} className="gap-1.5">
              {live ? (
                <>
                  <span className="relative flex size-2">
                    <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400/70 opacity-75" />
                    <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
                  </span>
                  实时
                </>
              ) : (
                '已断开'
              )}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5"
              disabled={isFetching}
              onClick={() => void refetch()}
            >
              {isFetching ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <RefreshCw className="size-3.5" />
              )}
              刷新
            </Button>
            {!live ? (
              <Button size="sm" onClick={() => setLive(true)}>
                重新连接
              </Button>
            ) : null}
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>进行中</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{stats.active}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>已提交</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{stats.pending}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>执行中</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{stats.running}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>已完成</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{stats.done}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>失败 / 取消</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{stats.failed}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-4">
        {JOB_COLUMNS.map((col) => (
          <KanbanColumn
            key={col.id}
            title={col.title}
            description={col.description}
            jobs={grouped[col.id]}
            highlight={col.id === 'pending' || col.id === 'running'}
          />
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">说明</CardTitle>
          <CardDescription>
            看板与 AI 对话共用同一套 job 状态机。对话内展示受理回执与结果推送，此处展示全局任务队列。
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <span>累计任务 {formatNumber(jobs.length)}</span>
          <Button asChild size="sm" variant="link" className="h-auto gap-1 px-0">
            <Link to="/chat">
              去发起对话
              <ExternalLink className="size-3" />
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
