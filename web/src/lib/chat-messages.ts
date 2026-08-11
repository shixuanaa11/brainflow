import { nanoid } from 'nanoid'
import type { DynamicToolUIPart } from 'ai'
import type { StoredChatMessage, WorkflowStep } from '@/lib/types'
import { toToolPart } from '@/lib/chat-workflow'

export interface ChatMessage {
  key: string
  from: 'user' | 'assistant'
  versions: { id: string; content: string }[]
  isContentComplete?: boolean
  steps?: WorkflowStep[]
  tools?: Array<{ name: string; part: DynamicToolUIPart }>
}

export function storedToChatMessages(stored: StoredChatMessage[]): ChatMessage[] {
  return stored.map((msg) => {
    const content = msg.content || ''
    const base: ChatMessage = {
      key: nanoid(),
      from: msg.role,
      versions: [{ id: nanoid(), content }],
      isContentComplete: true,
    }
    if (msg.role === 'assistant' && msg.meta) {
      base.steps = msg.meta.steps
      base.tools = (msg.meta.tools ?? []).map((t) => ({
        name: t.name,
        part: toToolPart(
          t.name,
          t.state as DynamicToolUIPart['state'],
          t.input,
          t.output,
          t.errorText,
        ),
      }))
    }
    return base
  })
}

export function buildStoredPair(
  userText: string,
  assistant: {
    content: string
    steps?: WorkflowStep[]
    tools?: Array<{ name: string; part: DynamicToolUIPart }>
  },
): StoredChatMessage[] {
  return [
    { role: 'user', content: userText },
    {
      role: 'assistant',
      content: assistant.content,
      meta: {
        steps: assistant.steps,
        tools: (assistant.tools ?? []).map((t) => ({
          name: t.name,
          state: t.part.state,
          input: t.part.input,
          output: t.part.output ? String(t.part.output) : undefined,
          errorText: t.part.errorText,
        })),
      },
    },
  ]
}
