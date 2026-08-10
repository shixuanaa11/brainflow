import { Moon, Sun, Monitor } from 'lucide-react'
import { useTheme } from 'next-themes'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export function ThemeToggle() {
  const { setTheme, theme } = useTheme()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" className="relative size-8">
          <Sun className="size-4 scale-100 rotate-0 transition-all dark:scale-0 dark:-rotate-90" />
          <Moon className="absolute size-4 scale-0 rotate-90 transition-all dark:scale-100 dark:rotate-0" />
          <span className="sr-only">切换主题</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => setTheme('light')} className="gap-2">
          <Sun className="size-4" />
          浅色
          {theme === 'light' && <span className="ml-auto text-xs text-muted-foreground">✓</span>}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme('dark')} className="gap-2">
          <Moon className="size-4" />
          深色
          {theme === 'dark' && <span className="ml-auto text-xs text-muted-foreground">✓</span>}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme('system')} className="gap-2">
          <Monitor className="size-4" />
          跟随系统
          {theme === 'system' && <span className="ml-auto text-xs text-muted-foreground">✓</span>}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
