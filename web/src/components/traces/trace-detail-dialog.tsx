import type { ReactNode } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { cn, formatDuration } from '@/lib/utils'
import type { Span, Task } from '@/lib/types'

/** 输入/输出块：高度随内容增长，超出 max-height 时在块内滚动 */
function DetailBlock({
  label,
  value,
  empty = '-',
  className,
  maxHeight = 'max-h-[min(32vh,280px)]',
}: {
  label: string
  value?: string
  empty?: string
  className?: string
  maxHeight?: string
}) {
  const text = value?.trim() || empty

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div
        className={cn(
          'min-h-[2.5rem] w-full overflow-y-auto overflow-x-hidden rounded-md border bg-muted/30',
          '[scrollbar-gutter:stable]',
          maxHeight,
        )}
      >
        <pre className="min-w-0 whitespace-pre-wrap break-words p-3 font-mono text-xs leading-relaxed text-foreground">
          {text}
        </pre>
      </div>
    </div>
  )
}

function MetaItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border bg-muted/20 px-3 py-2">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className="text-sm">{value}</span>
    </div>
  )
}

export function SpanDetailDialog({
  span,
  traceId,
  open,
  onOpenChange,
}: {
  span: Span | null
  traceId?: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  if (!span) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 overflow-hidden sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2 pr-6">
            <span>{span.node}</span>
            <Badge variant="secondary">{span.kind}</Badge>
            <Badge
              variant={
                span.status === 'ok'
                  ? 'success'
                  : span.status === 'error'
                    ? 'destructive'
                    : 'warning'
              }
            >
              {span.status}
            </Badge>
          </DialogTitle>
          <DialogDescription>
            {traceId ? `Trace ${traceId}` : '节点详情'} · Token {span.tokens ?? 0} ·{' '}
            {formatDuration(span.duration * 1000)}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <MetaItem label="节点" value={span.node} />
            <MetaItem label="类型" value={span.kind} />
            <MetaItem label="耗时" value={formatDuration(span.duration * 1000)} />
            <MetaItem label="Token" value={span.tokens ?? 0} />
          </div>

          {span.detail && (
            <>
              <DetailBlock
                label="错误 / 附加信息"
                maxHeight="max-h-[min(20vh,160px)]"
                value={span.detail}
              />
              <Separator />
            </>
          )}

          <DetailBlock label="输入" value={span.input} />
          <DetailBlock label="输出" value={span.output} />
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function TaskDetailDialog({
  task,
  open,
  onOpenChange,
}: {
  task: Task | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  if (!task) return null

  const totalMs = task.spans.reduce((acc, s) => acc + s.duration * 1000, 0)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 overflow-hidden sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2 pr-6">
            <span className="font-mono text-base">{task.trace_id}</span>
            <Badge variant="secondary">{task.workflow}</Badge>
            <Badge
              variant={
                task.status === 'ok'
                  ? 'success'
                  : task.status === 'error'
                    ? 'destructive'
                    : 'warning'
              }
            >
              {task.status}
            </Badge>
          </DialogTitle>
          <DialogDescription>
            {new Date(task.timestamp * 1000).toLocaleString('zh-CN')} · {task.spans.length} 节点 ·{' '}
            {formatDuration(totalMs)} · 用户 {task.user || '-'}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 flex flex-col gap-3">
          <DetailBlock label="用户输入" value={task.input} />
          <Separator />
          <p className="text-xs text-muted-foreground">
            共 {task.spans.length} 个节点，可在下方表格点击「详情」查看各节点完整输入输出
          </p>
        </div>
      </DialogContent>
    </Dialog>
  )
}
