import { useCallback, useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatInput } from '@/components/chat/ChatInput'
import { ChatMessageList } from '@/components/chat/ChatMessageList'
import { EvidenceDrawer } from '@/components/evidence/EvidenceDrawer'
import { ApiError, sendChatMessage } from '@/lib/api'
import type { CitationItem, ConversationEntry } from '@/types/chat'

// User-facing copy for a failed /api/chat call. Kept here rather than reusing
// ApiErrorState because the chat page renders failures inline as a conversation entry with
// its own Retry affordance (Day 37), not as a whole-page error.
function chatErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.kind === 'network') {
      return 'Cannot connect to the backend. Make sure the API server is running on port 8000.'
    }
    if (err.kind === 'timeout') {
      return 'The backend took more than a minute to answer. A chat turn runs two language-model calls plus retrieval, so this usually means the LLM API is struggling — try again.'
    }
    if (err.kind === 'server') {
      return 'The backend hit an internal error answering this question. This is often an exhausted LLM API quota.'
    }
    return err.message
  }
  return 'Something went wrong. Please try again.'
}

export function ChatPage() {
  const [entries, setEntries] = useState<ConversationEntry[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [lastQuestion, setLastQuestion] = useState<string | null>(null)
  const [activeCitation, setActiveCitation] = useState<CitationItem | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const performRequest = useCallback(
    async (question: string) => {
      setIsLoading(true)
      try {
        const response = await sendChatMessage(question, sessionId)
        setSessionId(response.session_id)
        setEntries((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: 'assistant', response },
        ])
      } catch (err) {
        setEntries((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'error',
            questionText: question,
            message: chatErrorMessage(err),
          },
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [sessionId],
  )

  const handleSend = useCallback(
    (question: string) => {
      if (isLoading) return
      setEntries((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', text: question }])
      setLastQuestion(question)
      void performRequest(question)
    },
    [isLoading, performRequest],
  )

  const handleRetry = useCallback(() => {
    if (!lastQuestion || isLoading) return
    setEntries((prev) => {
      const last = prev[prev.length - 1]
      return last?.role === 'error' ? prev.slice(0, -1) : prev
    })
    void performRequest(lastQuestion)
  }, [lastQuestion, isLoading, performRequest])

  function handleCitationClick(citation: CitationItem) {
    setActiveCitation(citation)
    setDrawerOpen(true)
  }

  function handleNewChat() {
    setEntries([])
    setSessionId(null)
    setLastQuestion(null)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between border-b border-border px-8 py-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">Chat</h1>
          <p className="text-xs text-muted-foreground">Ask questions grounded in the knowledge graph</p>
        </div>
        <Button variant="outline" size="sm" onClick={handleNewChat} disabled={entries.length === 0}>
          <Plus className="size-3.5" />
          New Chat
        </Button>
      </div>

      <div className="min-h-0 flex-1">
        <ChatMessageList
          entries={entries}
          isLoading={isLoading}
          onCitationClick={handleCitationClick}
          onSelectClarificationOption={handleSend}
          onRetry={handleRetry}
          onSuggestionClick={handleSend}
        />
      </div>

      <div className="shrink-0 border-t border-border">
        <ChatInput disabled={isLoading} onSend={handleSend} />
      </div>

      <EvidenceDrawer citation={activeCitation} open={drawerOpen} onOpenChange={setDrawerOpen} />
    </div>
  )
}
