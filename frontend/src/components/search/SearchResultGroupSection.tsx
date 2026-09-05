import { SearchResultCard } from '@/components/search/SearchResultCard'
import type { SearchResultGroup } from '@/types/search'

interface SearchResultGroupSectionProps {
  group: SearchResultGroup
  query: string
}

export function SearchResultGroupSection({ group, query }: SearchResultGroupSectionProps) {
  return (
    <section className="space-y-2.5">
      <div className="flex items-baseline gap-2 border-b border-border pb-1.5">
        <h2 className="text-sm font-semibold text-foreground">{group.label}</h2>
        <span className="text-xs text-muted-foreground">({group.count})</span>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {group.results.map((item) => (
          <SearchResultCard key={item.id} item={item} query={query} />
        ))}
      </div>
    </section>
  )
}
