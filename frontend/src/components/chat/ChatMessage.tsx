import { RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CitationBadge } from '@/components/chat/CitationBadge'
import { ClarificationCard } from '@/components/chat/ClarificationCard'
import { EffectiveQuestion } from '@/components/chat/EffectiveQuestion'
import type { CitationItem, ConversationEntry } from '@/types/chat'

interface ChatMessageProps {
  entry: ConversationEntry
  onCitationClick: (citation: CitationItem) => void
  onSelectClarificationOption: (optionName: string) => void
  onRetry: () => void
}

function AnswerText({
  answer,
  citations,
  onCitationClick,
}: {
  answer: string
  citations: CitationItem[]
  onCitationClick: (citation: CitationItem) => void
}) {
  const parts = answer.split(/(\[\d+\])/g)
  return (
    <p className="text-sm leading-relaxed whitespace-pre-wrap text-foreground">
      {parts.map((part, i) => {
        const match = /^\[(\d+)\]$/.exec(part)
        if (match) {
          const citation = citations.find((c) => c.index === Number(match[1]))
          if (citation) {
            return <CitationBadge key={i} citation={citation} onClick={onCitationClick} />
          }
        }
        return <span key={i}>{part}</span>
      })}
    </p>
  )
}

export function ChatMessage({
  entry,
  onCitationClick,
  onSelectClarificationOption,
  onRetry,
}: ChatMessageProps) {
  if (entry.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-lg rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          {entry.text}
        </div>
      </div>
    )
  }

  if (entry.role === 'error') {
    return (
      <div className="flex justify-start">
        <div className="max-w-lg rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3">
          <p className="text-sm text-destructive">{entry.message}</p>
          <Button variant="outline" size="sm" className="mt-2.5" onClick={onRetry}>
            <RotateCcw className="size-3.5" />
            Retry
          </Button>
        </div>
      </div>
    )
  }

  const { response } = entry

  if (response.clarification) {
    return (
      <div className="flex justify-start">
        <ClarificationCard
          clarification={response.clarification}
          onSelectOption={onSelectClarificationOption}
        />
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-2xl">
        {response.effective_question && <EffectiveQuestion text={response.effective_question} />}
        <div className="rounded-2xl rounded-bl-sm border border-border bg-card px-4 py-2.5">
          <AnswerText
            answer={response.answer}
            citations={response.citations}
            onCitationClick={onCitationClick}
          />
        </div>
      </div>
    </div>
  )
}
