"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { nanoid } from "nanoid";
import type { DynamicToolUIPart } from "ai";
import { RouteIcon, SparklesIcon, WrenchIcon } from "lucide-react";
import { streamChat } from "@/lib/api";
import {
  applyStreamStep,
  chainStatus,
  SUGGESTIONS,
  toToolPart,
} from "@/lib/chat-workflow";
import type { WorkflowStep } from "@/lib/types";
import { PageHeader } from "@/components/layout/page-header";
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
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
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
import { Spinner } from "@/components/ui/spinner";

interface ToolRun {
  name: string
  part: DynamicToolUIPart
}

interface ChatMessage {
  key: string;
  from: "user" | "assistant";
  versions: { id: string; content: string }[];
  isContentComplete?: boolean;
  steps?: WorkflowStep[];
  tools?: ToolRun[];
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
    <div className="mb-3 flex w-full flex-col gap-3">
      {steps.length > 0 && (
        <ChainOfThought defaultOpen={isStreaming}>
          <ChainOfThoughtHeader>执行链路</ChainOfThoughtHeader>
          <ChainOfThoughtContent>
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
        <Tool key={name} defaultOpen={part.state === "output-available"}>
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
  const [status, setStatus] = useState<"ready" | "streaming" | "submitted">(
    "ready",
  );
  const [draft, setDraft] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const msgIdRef = useRef(0);

  const nextId = () => `msg-${msgIdRef.current++}-${nanoid()}`;

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

    try {
      await streamChat(
        text,
        "web",
        (ev) => {
          if (ev.type === "start") {
            setMessages((prev) =>
              prev.map((m) =>
                m.key === aiMsg.key
                  ? {
                      ...m,
                      steps: [
                        {
                          node: "router",
                          kind: "router",
                          label: "意图识别 (router)",
                          status: "running",
                        },
                      ],
                    }
                  : m,
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
                } else if (ev.kind === "tool" && ev.status === "running" && ev.tool) {
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

                return { ...m, steps, tools };
              }),
            );
          } else if (ev.type === "reply") {
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
      setMessages((prev) =>
        prev.map((m) =>
          m.key === aiMsg.key
            ? {
                ...m,
                isContentComplete: true,
                steps: (m.steps ?? []).map((s) =>
                  s.status === "running" ? { ...s, status: "done" as const } : s,
                ),
              }
            : m,
        ),
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
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
      }
    } finally {
      setStatus("ready");
    }
  }, []);

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
    <div className="flex h-[calc(100vh-3rem)] flex-col gap-4">
      <PageHeader
        title="AI 对话"
        description="参考 AI Elements Chatbot · 链路可视化 · 工具状态 · 流式回复"
      />

      <div className="relative flex flex-1 flex-col overflow-hidden rounded-xl border bg-card/80 shadow-sm backdrop-blur-sm">
        <Conversation>
          <ConversationContent>
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center gap-6 px-4 py-8 text-center">
                <div className="flex flex-col gap-2">
                  <p className="text-lg font-semibold tracking-tight">开始对话</p>
                  <p className="max-w-md text-sm text-muted-foreground">
                    输入消息或选择下方建议。执行过程中可查看 router → 工具 → summary 全链路状态。
                  </p>
                </div>
                <Suggestions className="max-w-lg justify-center px-2">
                  {SUGGESTIONS.map((s) => (
                    <Suggestion
                      key={s}
                      suggestion={s}
                      onClick={handleSuggestion}
                      disabled={isBusy}
                    />
                  ))}
                </Suggestions>
              </div>
            )}

            {messages.map((message) => (
              <Message
                from={message.from}
                key={message.key}
                className={message.from === "user" ? "max-w-[85%]" : "w-full max-w-full"}
              >
                <MessageContent className={message.from === "assistant" ? "w-full" : undefined}>
                  {message.from === "assistant" && (
                    <WorkflowPanel
                      isStreaming={!message.isContentComplete}
                      steps={message.steps ?? []}
                      tools={message.tools ?? []}
                    />
                  )}
                  {message.versions.map((version) =>
                    version.content ? (
                      <MessageResponse key={version.id}>{version.content}</MessageResponse>
                    ) : null,
                  )}
                  {message.from === "assistant" &&
                    !message.isContentComplete &&
                    !message.versions.some((v) => v.content) && (
                      <Shimmer className="text-sm">正在思考与执行工具…</Shimmer>
                    )}
                  {message.from === "assistant" &&
                    !message.isContentComplete &&
                    message.versions.some((v) => v.content) && (
                      <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-current align-middle text-muted-foreground" />
                    )}
                </MessageContent>
              </Message>
            ))}

            {status === "submitted" && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner />
                提交中…
              </div>
            )}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>

        <div className="shrink-0 border-t bg-background/80 p-3 backdrop-blur-sm">
          {messages.length > 0 && (
            <Suggestions className="mb-3 px-1">
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
          <PromptInput className="rounded-2xl border shadow-sm" onSubmit={handleSubmit}>
            <PromptInputTextarea
              className="min-h-[52px] px-4 md:text-base"
              placeholder="输入消息，Enter 发送，Shift+Enter 换行"
              value={draft}
              onChange={(e) => setDraft(e.currentTarget.value)}
            />
            <PromptInputFooter className="justify-end p-2">
              <PromptInputSubmit
                disabled={isBusy || !draft.trim()}
                status={status === "streaming" ? "streaming" : undefined}
                onStop={() => abortRef.current?.abort()}
              />
            </PromptInputFooter>
          </PromptInput>
          <p className="mt-2 text-center text-xs text-muted-foreground">
            AI 可能犯错，请核验重要信息
          </p>
        </div>
      </div>
    </div>
  );
}
