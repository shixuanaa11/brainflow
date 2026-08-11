import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { LayoutDashboard, GitBranch, Workflow, MessageSquare, Brain } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/theme-toggle'
import { Separator } from '@/components/ui/separator'

const nav = [
  { to: '/', icon: LayoutDashboard, label: '总览看板', end: true },
  { to: '/traces', icon: GitBranch, label: '任务链路' },
  { to: '/graph', icon: Workflow, label: '工作流图' },
  { to: '/chat', icon: MessageSquare, label: 'AI 对话' },
]

export default function Layout() {
  const location = useLocation()
  const isChat = location.pathname === '/chat'

  return (
    <div
      className={cn(
        'flex bg-background',
        isChat ? 'h-svh overflow-hidden' : 'min-h-screen',
      )}
    >
      <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-sidebar-border bg-sidebar/95 text-sidebar-foreground backdrop-blur-md">
        <div className="flex flex-col gap-1 p-5">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
              <Brain className="size-4" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight">BrainFlow</div>
              <div className="text-xs text-muted-foreground">智脑流 · 运营看板</div>
            </div>
          </div>
        </div>

        <Separator className="bg-sidebar-border" />

        <nav className="flex flex-1 flex-col gap-1 p-3">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-sidebar-primary text-sidebar-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                )
              }
            >
              <item.icon className="size-4 shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <Separator className="bg-sidebar-border" />

        <div className="flex items-center justify-between p-4">
          <span className="text-xs text-muted-foreground">v1.0 · 内部运营</span>
          <ThemeToggle />
        </div>
      </aside>

      <main className={cn('ml-60 flex-1', isChat && 'overflow-hidden')}>
        <div
          className={cn(
            isChat ? 'flex h-svh flex-col' : 'mx-auto max-w-7xl p-6',
          )}
        >
          <Outlet />
        </div>
      </main>
    </div>
  )
}
