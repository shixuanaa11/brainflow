"use client";

import { MessageSquarePlusIcon, Trash2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { ChatSession } from "@/lib/types";

function formatSessionTime(ts: number) {
  const d = new Date(ts * 1000);
  const now = new Date();
  const isToday =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (isToday) {
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

export function ChatHistorySidebar({
  sessions,
  activeSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  className,
}: {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onNewChat: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  className?: string;
}) {
  return (
    <aside
      className={cn(
        "flex w-56 shrink-0 flex-col border-r bg-muted/20",
        className,
      )}
    >
      <div className="shrink-0 border-b p-3">
        <Button
          className="w-full justify-start gap-2"
          type="button"
          variant="outline"
          onClick={onNewChat}
        >
          <MessageSquarePlusIcon className="size-4" />
          新对话
        </Button>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-0.5 p-2">
          {sessions.length === 0 ? (
            <p className="px-2 py-6 text-center text-xs text-muted-foreground">
              暂无历史记录
            </p>
          ) : (
            sessions.map((session) => {
              const active = session.session_id === activeSessionId;
              return (
                <div
                  key={session.session_id}
                  className={cn(
                    "group flex items-center gap-1 rounded-lg px-2 py-1.5 transition-colors",
                    active
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-muted",
                  )}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => onSelectSession(session.session_id)}
                  >
                    <p className="truncate text-sm font-medium">{session.title}</p>
                    <p
                      className={cn(
                        "text-[10px]",
                        active ? "text-primary-foreground/70" : "text-muted-foreground",
                      )}
                    >
                      {formatSessionTime(session.updated_at)}
                    </p>
                  </button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    className={cn(
                      "shrink-0 opacity-0 transition-opacity group-hover:opacity-100",
                      active && "text-primary-foreground hover:bg-primary-foreground/10",
                    )}
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession(session.session_id);
                    }}
                  >
                    <Trash2Icon className="size-3.5" />
                  </Button>
                </div>
              );
            })
          )}
        </div>
      </ScrollArea>
    </aside>
  );
}
