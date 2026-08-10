import { cn } from '@/lib/utils'
import type { Span } from '@/lib/types'
import { CheckCircle2, Circle, Loader2, Route, Sparkles, Wrench, XCircle } from 'lucide-react'

const KIND_META = {
  router: { icon: Route, label: 'Router' },
  tool: { icon: Wrench, label: 'Tool' },
  summary: { icon: Sparkles, label: 'Summary' },
} as const

function stepStatusIcon(status: string) {
  if (status === 'ok') return CheckCircle2
  if (status === 'error') return XCircle
  if (status === 'running') return Loader2
  return Circle
}

export function SpanWorkflowTimeline({ spans }: { spans: Span[] }) {
  if (!spans.length) return null

  return (
    <div className="mt-4 flex flex-col gap-2">
      <p className="text-xs font-medium text-muted-foreground">执行链路</p>
      <div className="flex flex-wrap items-center gap-2">
        {spans.map((span, i) => {
          const meta = KIND_META[span.kind] ?? KIND_META.tool
          const Icon = meta.icon
          const StatusIcon = stepStatusIcon(span.status)
          const isRunning = span.status === 'running'

          return (
            <div key={`${span.node}-${i}`} className="flex items-center gap-2">
              <div
                className={cn(
                  'flex items-center gap-2 rounded-lg border px-3 py-2 text-xs',
                  span.status === 'ok' && 'border-emerald-500/30 bg-emerald-500/5',
                  span.status === 'error' && 'border-destructive/30 bg-destructive/5',
                  span.status === 'running' && 'border-primary/30 bg-primary/5',
                  span.status !== 'ok' &&
                    span.status !== 'error' &&
                    span.status !== 'running' &&
                    'bg-muted/40',
                )}
              >
                <Icon className="size-3.5 text-muted-foreground" />
                <span className="font-medium">{span.node}</span>
                <StatusIcon
                  className={cn(
                    'size-3.5',
                    span.status === 'ok' && 'text-emerald-600 dark:text-emerald-400',
                    span.status === 'error' && 'text-destructive',
                    isRunning && 'animate-spin text-primary',
                    !isRunning && span.status !== 'ok' && span.status !== 'error' && 'text-muted-foreground',
                  )}
                />
              </div>
              {i < spans.length - 1 && (
                <div className="hidden h-px w-4 bg-border sm:block" aria-hidden />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
