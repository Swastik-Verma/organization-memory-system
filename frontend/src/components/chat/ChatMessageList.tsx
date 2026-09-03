import { useEffect, useRef } from 'react'
import { MessageSquare } from 'lucide-react'
import { ChatMessage } from '@/components/chat/ChatMessage'
import type { CitationItem, ConversationEntry } from '@/types/chat'

// Day 41: these moved out of chatMocks.ts (which keyed its fixtures off them) and are now
// plain starter questions against the real corpus. The "Trigger a network error (demo)"
// chip is gone — it only existed to drive the mock's error branch, and every one of these
// now spends real Gemini quota when clicked (CLAUDE.md §9).
const SUGGESTED_PROMPTS = [
  'Who does Sally Beck report to?',
  'Who does Kay Mann work with?',
  'What is Vincent Kaminski involved in?',
]

interface ChatMessageListProps {
  entries: ConversationEntry[]
  isLoading: boolean
  onCitationClick: (citation: CitationItem) => void
  onSelectClarificationOption: (optionName: string) => void
  onRetry: () => void
  onSuggestionClick: (prompt: string) => void
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm border border-border bg-card px-4 py-3">
        <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
        <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
        <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground" />
      </div>
    </div>
  )
}

function EmptyState({ onSuggestionClick }: { onSuggestionClick: (prompt: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <div className="flex size-11 items-center justify-center rounded-full bg-accent">
        <MessageSquare className="size-5 text-accent-foreground" />
      </div>
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-foreground">Ask about the Enron corpus</h2>
        <p className="text-sm text-muted-foreground">
          Questions are answered with cited claims drawn from the knowledge graph.
        </p>
      </div>
      <div className="mt-2 flex flex-wrap justify-center gap-2">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onSuggestionClick(prompt)}
            className="rounded-full border border-border bg-background px-3 py-1.5 text-xs text-foreground transition-colors hover:border-primary hover:bg-accent hover:text-accent-foreground"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  )
}

export function ChatMessageList({
  entries,
  isLoading,
  onCitationClick,
  onSelectClarificationOption,
  onRetry,
  onSuggestionClick,
}: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [entries, isLoading])

  if (entries.length === 0) {
    return (
      <div className="h-full overflow-y-auto px-8 py-6">
        <EmptyState onSuggestionClick={onSuggestionClick} />
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto px-8 py-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        {entries.map((entry) => (
          <ChatMessage
            key={entry.id}
            entry={entry}
            onCitationClick={onCitationClick}
            onSelectClarificationOption={onSelectClarificationOption}
            onRetry={onRetry}
          />
        ))}
        {isLoading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
