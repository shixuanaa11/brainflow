"use client";

import {
  ArrowRightIcon,
  BrainIcon,
  CloudSunIcon,
  GitBranchIcon,
  NewspaperIcon,
  RouteIcon,
  SparklesIcon,
  UmbrellaIcon,
  WrenchIcon,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { SUGGESTIONS } from "@/lib/chat-workflow";

const CAPABILITIES = [
  {
    icon: RouteIcon,
    title: "意图识别",
    description: "理解问题并路由到合适节点",
  },
  {
    icon: WrenchIcon,
    title: "工具调用",
    description: "天气、新闻等能力按需执行",
  },
  {
    icon: SparklesIcon,
    title: "流式回复",
    description: "边执行边输出，链路可见",
  },
] as const;

const PROMPT_META: Record<
  string,
  { icon: LucideIcon; category: string }
> = {
  "深圳今天天气怎么样": { icon: CloudSunIcon, category: "天气查询" },
  "帮我查一下最新新闻": { icon: NewspaperIcon, category: "资讯检索" },
  "总结一下 LangGraph 工作流": { icon: GitBranchIcon, category: "知识问答" },
  "北京明天需要带伞吗": { icon: UmbrellaIcon, category: "生活助手" },
};

const WORKFLOW_STEPS = ["Router", "Tool", "Summary"] as const;

function ChatWelcomeBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      <div className="absolute left-1/2 top-1/2 h-[min(360px,70%)] w-[min(360px,85%)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground/[0.035] blur-3xl dark:bg-foreground/[0.07]" />
      <svg
        className="absolute inset-0 size-full opacity-[0.18] dark:opacity-[0.1]"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern
            id="chat-welcome-grid"
            width="32"
            height="32"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 32 0 L 0 0 0 32"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.5"
              className="text-border"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#chat-welcome-grid)" />
      </svg>
    </div>
  );
}

function HeroMark() {
  return (
    <div className="relative mx-auto size-16 shrink-0">
      <div className="absolute inset-0 animate-[spin_36s_linear_infinite] rounded-full border border-dashed border-border/70" />
      <div className="absolute inset-2.5 rounded-full border border-border/50 bg-background/80" />
      <div className="absolute inset-5 flex items-center justify-center rounded-xl bg-gradient-to-br from-foreground to-foreground/75 text-background shadow-[0_8px_28px_-10px_hsl(var(--foreground)/0.4)] ring-1 ring-foreground/10">
        <BrainIcon className="size-6" strokeWidth={1.75} />
      </div>
    </div>
  );
}

function WorkflowPreview() {
  return (
    <div className="inline-flex shrink-0 items-center gap-1 rounded-full border border-border/70 bg-background/70 px-2.5 py-1 text-[11px] shadow-sm backdrop-blur-sm">
      {WORKFLOW_STEPS.map((step, index) => (
        <span key={step} className="flex items-center gap-1">
          <span className="rounded-full bg-muted px-2 py-0.5 font-medium text-foreground">
            {step}
          </span>
          {index < WORKFLOW_STEPS.length - 1 && (
            <ArrowRightIcon className="size-2.5 text-muted-foreground/70" />
          )}
        </span>
      ))}
    </div>
  );
}

export function ChatWelcome({
  onSuggestion,
  disabled,
}: {
  onSuggestion: (text: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="relative flex h-full min-h-0 w-full flex-col overflow-hidden px-3 py-2 md:px-4 md:py-3">
      <ChatWelcomeBackground />

      <div className="relative z-10 flex min-h-0 flex-1 flex-col items-center justify-center gap-3 md:gap-4">
        <div className="flex shrink-0 flex-col items-center gap-3 text-center">
          <HeroMark />
          <div className="max-w-md space-y-1.5">
            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              BrainFlow Agent
            </p>
            <h2 className="text-xl font-semibold tracking-tight md:text-2xl">
              有什么可以帮你的？
            </h2>
            <p className="text-xs leading-relaxed text-muted-foreground md:text-sm">
              输入消息或选择下方示例，我会识别意图、调用工具并流式回复。
            </p>
          </div>
          <WorkflowPreview />
        </div>

        <div className="grid w-full max-w-2xl shrink-0 grid-cols-3 gap-2">
          {CAPABILITIES.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="group rounded-lg border border-border/70 bg-card/70 p-2.5 shadow-sm backdrop-blur-sm transition-all hover:border-foreground/15 hover:bg-card md:p-3"
            >
              <div className="mb-2 flex size-7 items-center justify-center rounded-md bg-muted transition-colors group-hover:bg-foreground group-hover:text-background md:size-8">
                <Icon className="size-3.5 md:size-4" strokeWidth={1.75} />
              </div>
              <p className="text-xs font-medium md:text-sm">{title}</p>
              <p className="mt-0.5 line-clamp-2 text-[10px] leading-snug text-muted-foreground md:text-[11px]">
                {description}
              </p>
            </div>
          ))}
        </div>

        <div className="w-full max-w-2xl shrink-0 space-y-2">
          <p className="text-center text-[11px] font-medium text-muted-foreground">
            试试这些示例
          </p>
          <div className="grid grid-cols-2 gap-2">
            {SUGGESTIONS.map((suggestion) => {
              const meta = PROMPT_META[suggestion] ?? {
                icon: SparklesIcon,
                category: "快捷提问",
              };
              const Icon = meta.icon;

              return (
                <button
                  key={suggestion}
                  type="button"
                  disabled={disabled}
                  onClick={() => onSuggestion(suggestion)}
                  className={cn(
                    "group flex items-center gap-2.5 rounded-lg border border-border/70 bg-background/80 p-2.5 text-left shadow-sm backdrop-blur-sm transition-all md:gap-3 md:p-3",
                    "hover:border-foreground/20 hover:bg-card hover:shadow-md",
                    "disabled:pointer-events-none disabled:opacity-50",
                  )}
                >
                  <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-muted transition-colors group-hover:bg-foreground group-hover:text-background md:size-8">
                    <Icon className="size-3.5 md:size-4" strokeWidth={1.75} />
                  </div>
                  <div className="min-w-0 space-y-0.5">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                      {meta.category}
                    </p>
                    <p className="line-clamp-2 text-xs font-medium leading-snug md:text-sm">
                      {suggestion}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
