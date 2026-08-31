import { cn } from '@/lib/utils'
import type { ClarificationInfo } from '@/types/chat'

interface ClarificationCardProps {
  clarification: ClarificationInfo
  onSelectOption: (optionName: string) => void
}

const ENTITY_DOT_COLORS: Record<string, string> = {
  person: 'bg-entity-person',
  organization: 'bg-entity-organization',
  deal: 'bg-entity-deal',
  decision: 'bg-entity-decision',
}

export function ClarificationCard({ clarification, onSelectOption }: ClarificationCardProps) {
  return (
    <div className="max-w-lg rounded-lg border border-border bg-card p-3.5">
      <p className="text-sm text-foreground">{clarification.message}</p>
      <div className="mt-2.5 flex flex-wrap gap-2">
        {clarification.options.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => onSelectOption(option.name)}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1 text-xs font-medium text-foreground transition-colors hover:border-primary hover:bg-accent hover:text-accent-foreground"
          >
            <span
              className={cn(
                'size-1.5 shrink-0 rounded-full',
                ENTITY_DOT_COLORS[option.type] ?? 'bg-muted-foreground',
              )}
            />
            {option.name}
          </button>
        ))}
      </div>
    </div>
  )
}
