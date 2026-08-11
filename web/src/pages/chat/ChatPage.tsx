"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { nanoid } from "nanoid";
import type { DynamicToolUIPart } from "ai";
import {
  BrainIcon,
  RouteIcon,
  SparklesIcon,
  WrenchIcon,
} from "lucide-react";
import { ChatHistorySidebar } from "@/components/chat/chat-history-sidebar";
import { ChatWelcome } from "@/components/chat/chat-welcome";
import { streamChat } from "@/lib/api";
import { chatHistoryApi } from "@/lib/chat-history";
import {
  buildStoredPair,
  storedToChatMessages,
  type ChatMessage,
} from "@/lib/chat-messages";
import {
  applyStreamStep,
  chainStatus,
  SUGGESTIONS,
  toToolPart,
} from "@/lib/chat-workflow";
import type { ChatSession, WorkflowStep } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtHeader,
  ChainOfThoughtStep,
} from "@/components/ai-elements/chain-of-thought";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  type PromptInputMessage,
} from "@/components/ai-elements/prompt-input";
import { Shimmer } from "@/components/ai-elements/shimmer";
import { Suggestion, Suggestions } from "@/components/ai-elements/suggestion";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import { cn } from "@/lib/utils";

const USER_ID = "web";

interface ToolRun {
  name: string;
  part: DynamicToolUIPart;
}

function WorkflowPanel({
  steps,
  tools,
  isStreaming,
}: {
  steps: WorkflowStep[];
  tools: ToolRun[];
  isStreaming: boolean;
}) {
  if (!steps.length && !tools.length) return null;

  const stepIcon = (kind: WorkflowStep["kind"]) => {
    if (kind === "router") return RouteIcon;
    if (kind === "tool") return WrenchIcon;
    return SparklesIcon;
  };

  return (
    <div className="flex w-full flex-col gap-2">
      {steps.length > 0 && (
        <ChainOfThought
          className="rounded-xl border border-border/60 bg-muted/30"
          defaultOpen={isStreaming}
        >
          <ChainOfThoughtHeader className="px-3 py-2 text-sm">
            执行链路
          </ChainOfThoughtHeader>
          <ChainOfThoughtContent className="px-3 pb-3">
            {steps.map((step) => (
              <ChainOfThoughtStep
                key={step.node}
                icon={stepIcon(step.kind)}
                label={step.label}
                status={chainStatus(step)}
                description={
                  step.intent
                    ? `识别意图：${step.intent}`
                    : step.error
                      ? step.error
                      : step.status === "running"
                        ? "执行中…"
                        : undefined
                }
              />
            ))}
          </ChainOfThoughtContent>
        </ChainOfThought>
      )}

      {tools.map(({ name, part }) => (
        <Tool
          key={name}
          className="rounded-xl border-border/60"
          defaultOpen={part.state === "output-available"}
        >
          <ToolHeader
            state={part.state}
            title={name}
            toolName={name}
            type="dynamic-tool"
          />
          <ToolContent>
            <ToolInput input={part.input} />
            <ToolOutput
              errorText={part.errorText}
              output={
                part.output ? (
                  <MessageResponse>{String(part.output)}</MessageResponse>
                ) : undefined
              }
            />
          </ToolContent>
        </Tool>
      ))}
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<"ready" | "streaming" | "submitted">(
    "ready",
  );
  const [draft, setDraft] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const msgIdRef = useRef(0);
  const sessionIdRef = useRef<string | null>(null);

  const nextId = () => `msg-${msgIdRef.current++}-${nanoid()}`;

  const refreshSessions = useCallback(async () => {
    try {
      const res = await chatHistoryApi.listSessions(USER_ID);
      setSessions(res.sessions);
    } catch {
      // 静默失败，不影响对话
    }
  }, []);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const handleNewChat = useCallback(() => {
    abortRef.current?.abort();
    setSessionId(null);
    setMessages([]);
    setDraft("");
    setStatus("ready");
  }, []);

  const handleSelectSession = useCallback(
    async (id: string) => {
      if (status !== "ready" || id === sessionId) return;
      abortRef.current?.abort();
      try {
        const detail = await chatHistoryApi.getSession(id);
        setSessionId(id);
        setMessages(storedToChatMessages(detail.messages));
        setDraft("");
        setStatus("ready");
      } catch {
        // ignore
      }
    },
    [sessionId, status],
  );

  const handleDeleteSession = useCallback(
    async (id: string) => {
      try {
        await chatHistoryApi.deleteSession(id);
        if (sessionId === id) handleNewChat();
        await refreshSessions();
      } catch {
        // ignore
      }
    },
    [handleNewChat, refreshSessions, sessionId],
  );

  const ensureSession = useCallback(
    async (text: string) => {
      if (sessionIdRef.current) return sessionIdRef.current;
      const session = await chatHistoryApi.createSession(
        USER_ID,
        text.slice(0, 40) || "新对话",
      );
      sessionIdRef.current = session.session_id;
      setSessionId(session.session_id);
      await refreshSessions();
      return session.session_id;
    },
    [refreshSessions],
  );

  const runChat = useCallback(async (text: string) => {
    const userMsg: ChatMessage = {
      key: nextId(),
      from: "user",
      versions: [{ id: nanoid(), content: text }],
      isContentComplete: true,
    };
    const aiMsg: ChatMessage = {
      key: nextId(),
      from: "assistant",
      versions: [{ id: nanoid(), content: "" }],
      isContentComplete: false,
      steps: [],
      tools: [],
    };

    setMessages((prev) => [...prev, userMsg, aiMsg]);
    setStatus("streaming");
    setDraft("");

    const controller = new AbortController();
    abortRef.current = controller;
    let userInput = text;
    let finalContent = "";
    let finalSteps: WorkflowStep[] = [];
    let finalTools: ToolRun[] = [];

    try {
      const sid = await ensureSession(text);

      await streamChat(
        text,
        USER_ID,
        (ev) => {
          if (ev.type === "start") {
            finalSteps = [
              {
                node: "router",
                kind: "router",
                label: "意图识别 (router)",
                status: "running",
              },
            ];
            setMessages((prev) =>
              prev.map((m) =>
                m.key === aiMsg.key ? { ...m, steps: finalSteps } : m,
              ),
            );
          } else if (ev.type === "step") {
            setMessages((prev) =>
              prev.map((m) => {
                if (m.key !== aiMsg.key) return m;
                const steps = applyStreamStep(m.steps ?? [], ev);
                let tools = m.tools ?? [];

                if (ev.kind === "tool" && ev.status === "done" && ev.tool) {
                  const part = toToolPart(
                    ev.tool,
                    "output-available",
                    { query: userInput },
                    ev.output,
                  );
                  tools = [
                    ...tools.filter((t) => t.name !== ev.tool),
                    { name: ev.tool, part },
                  ];
                } else if (
                  ev.kind === "tool" &&
                  ev.status === "running" &&
                  ev.tool
                ) {
                  const part = toToolPart(
                    ev.tool,
                    "input-available",
                    { query: userInput },
                  );
                  tools = [
                    ...tools.filter((t) => t.name !== ev.tool),
                    { name: ev.tool, part },
                  ];
                }

                finalSteps = steps;
                finalTools = tools;
                return { ...m, steps, tools };
              }),
            );
          } else if (ev.type === "reply") {
            finalContent += ev.reply;
            setMessages((prev) =>
              prev.map((m) =>
                m.key === aiMsg.key
                  ? {
                      ...m,
                      versions: m.versions.map((v) => ({
                        ...v,
                        content: v.content + ev.reply,
                      })),
                      steps: (m.steps ?? []).map((s) =>
                        s.node === "summary" && s.status === "running"
                          ? { ...s, status: "done" as const }
                          : s,
                      ),
                    }
                  : m,
              ),
            );
          } else if (ev.type === "error") {
            finalContent = finalContent || ev.message;
            setMessages((prev) =>
              prev.map((m) =>
                m.key === aiMsg.key
                  ? {
                      ...m,
                      versions: m.versions.map((v) => ({
                        ...v,
                        content: v.content || ev.message,
                      })),
                      steps: (m.steps ?? []).map((s) =>
                        s.status === "running"
                          ? { ...s, status: "error" as const, error: ev.message }
                          : s,
                      ),
                    }
                  : m,
              ),
            );
          }
        },
        controller.signal,
      );
      finalSteps = finalSteps.map((s) =>
        s.status === "running" ? { ...s, status: "done" as const } : s,
      );
      setMessages((prev) =>
        prev.map((m) =>
          m.key === aiMsg.key
            ? { ...m, isContentComplete: true, steps: finalSteps }
            : m,
        ),
      );

      await chatHistoryApi.appendMessages(
        sid,
        buildStoredPair(text, {
          content: finalContent,
          steps: finalSteps,
          tools: finalTools,
        }),
      );
      await refreshSessions();
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        finalContent = finalContent || "请求失败";
        setMessages((prev) =>
          prev.map((m) =>
            m.key === aiMsg.key
              ? {
                  ...m,
                  isContentComplete: true,
                  versions: m.versions.map((v) => ({
                    ...v,
                    content: v.content || "请求失败",
                  })),
                }
              : m,
          ),
        );
        const sid = sessionIdRef.current;
        if (sid) {
          try {
            await chatHistoryApi.appendMessages(
              sid,
              buildStoredPair(text, { content: finalContent, steps: finalSteps, tools: finalTools }),
            );
            await refreshSessions();
          } catch {
            // ignore persist error
          }
        }
      }
    } finally {
      setStatus("ready");
    }
  }, [ensureSession, refreshSessions]);

  const handleSubmit = useCallback(
    async (message: PromptInputMessage) => {
      const text = (message.text || "").trim();
      if (!text || status !== "ready") return;
      await runChat(text);
    },
    [runChat, status],
  );

  const handleSuggestion = useCallback(
    (suggestion: string) => {
      if (status !== "ready") return;
      setDraft(suggestion);
      void runChat(suggestion);
    },
    [runChat, status],
  );

  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [],
  );

  const isBusy = status !== "ready";

  return (
    <div className="relative flex min-h-0 flex-1">
      <ChatHistorySidebar
        activeSessionId={sessionId}
        sessions={sessions}
        onDeleteSession={(id) => void handleDeleteSession(id)}
        onNewChat={handleNewChat}
        onSelectSession={(id) => void handleSelectSession(id)}
      />

      <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
      <header
        className={cn(
          "flex shrink-0 items-center justify-between border-b px-5 py-3",
          messages.length === 0 && "border-border/60 bg-background/80 backdrop-blur-sm",
        )}
      >
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <BrainIcon className="size-4" />
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-tight">BrainFlow 助手</h1>
            <p className="text-xs text-muted-foreground">
              意图识别 · 工具调用 · 流式回复
            </p>
          </div>
        </div>
        {isBusy && (
          <Badge className="gap-1.5" variant="secondary">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/40 opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-primary" />
            </span>
            {status === "streaming" ? "执行中" : "提交中"}
          </Badge>
        )}
      </header>

      <Conversation
        className={cn("min-h-0 flex-1", messages.length === 0 && "overflow-hidden")}
      >
        <ConversationContent
          className={cn(
            "mx-auto w-full max-w-3xl gap-6 px-4 py-6 md:gap-8 md:px-6",
            messages.length === 0 && "h-full min-h-0 gap-0 overflow-hidden p-0",
          )}
        >
          {messages.length === 0 ? (
            <ChatWelcome disabled={isBusy} onSuggestion={handleSuggestion} />
          ) : (
            messages.map((message) => (
              <Message from={message.from} key={message.key}>
                {message.from === "assistant" &&
                  ((message.steps?.length ?? 0) > 0 ||
                    (message.tools?.length ?? 0) > 0) && (
                    <WorkflowPanel
                      isStreaming={!message.isContentComplete}
                      steps={message.steps ?? []}
                      tools={message.tools ?? []}
                    />
                  )}
                <MessageContent
                  className={cn(
                    message.from === "user" && "max-w-[min(85%,32rem)]",
                    message.from === "assistant" && "w-full max-w-full",
                  )}
                >
                  {message.versions.map((version) =>
                    version.content ? (
                      <MessageResponse key={version.id}>
                        {version.content}
                      </MessageResponse>
                    ) : null,
                  )}
                  {message.from === "assistant" &&
                    !message.isContentComplete &&
                    !message.versions.some((v) => v.content) && (
                      <Shimmer className="text-sm text-muted-foreground">
                        正在思考与执行工具…
                      </Shimmer>
                    )}
                  {message.from === "assistant" &&
                    !message.isContentComplete &&
                    message.versions.some((v) => v.content) && (
                      <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-foreground/70 align-middle" />
                    )}
                </MessageContent>
              </Message>
            ))
          )}
        </ConversationContent>
        <ConversationScrollButton className="bottom-28" />
      </Conversation>

      <div
        className={cn(
          "relative shrink-0 border-t backdrop-blur supports-[backdrop-filter]:bg-background/80",
          messages.length === 0
            ? "border-border/60 bg-background/90 px-4 pb-3 pt-3"
            : "bg-background/95 px-4 pb-5 pt-4",
        )}
      >
        <div className="pointer-events-none absolute inset-x-0 -top-8 h-8 bg-gradient-to-t from-background to-transparent" />
        <div className="mx-auto w-full max-w-2xl space-y-2 md:space-y-3">
          {messages.length > 0 && (
            <Suggestions>
              {SUGGESTIONS.slice(0, 3).map((s) => (
                <Suggestion
                  key={s}
                  suggestion={s}
                  onClick={handleSuggestion}
                  disabled={isBusy}
                  variant="secondary"
                />
              ))}
            </Suggestions>
          )}
          <PromptInput
            className="overflow-hidden rounded-[28px] border bg-background shadow-lg ring-1 ring-border/50 transition-shadow focus-within:shadow-xl focus-within:ring-primary/20"
            onSubmit={handleSubmit}
          >
            <PromptInputBody>
              <PromptInputTextarea
                className={cn(
                  "resize-none border-0 bg-transparent px-5 py-4 text-base shadow-none focus-visible:ring-0 md:text-base",
                  messages.length === 0 ? "min-h-[48px]" : "min-h-[56px]",
                )}
                placeholder="输入消息，Enter 发送，Shift+Enter 换行"
                value={draft}
                onChange={(e) => setDraft(e.currentTarget.value)}
              />
            </PromptInputBody>
            <PromptInputFooter className="items-center px-3 pb-3 pt-0">
              <PromptInputTools>
                <Badge
                  className="gap-1 rounded-full font-normal"
                  variant="outline"
                >
                  <BrainIcon className="size-3" />
                  BrainFlow
                </Badge>
              </PromptInputTools>
              <PromptInputSubmit
                disabled={isBusy || !draft.trim()}
                status={status === "streaming" ? "streaming" : undefined}
                onStop={() => abortRef.current?.abort()}
              />
            </PromptInputFooter>
          </PromptInput>
          {messages.length > 0 && (
            <p className="text-center text-xs text-muted-foreground">
              AI 可能犯错，请核验重要信息
            </p>
          )}
        </div>
      </div>
      </div>
    </div>
  );
}
