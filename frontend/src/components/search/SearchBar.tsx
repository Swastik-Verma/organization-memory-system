import { Loader2, Search } from 'lucide-react'
import { Input } from '@/components/ui/input'

interface SearchBarProps {
  value: string
  onChange: (value: string) => void
  loading: boolean
}

// Deliberately larger/more padded than every other page's search box (Entities, Merges,
// Conflicts) — this is the one global, prominent entry point, per the Day 45 brief.
export function SearchBar({ value, onChange, loading }: SearchBarProps) {
  return (
    <div className="relative mx-auto w-full max-w-2xl">
      <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted-foreground" />
      <Input
        autoFocus
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Type to search..."
        className="h-14 rounded-xl pl-12 pr-12 text-base"
      />
      {loading && (
        <Loader2 className="absolute top-1/2 right-4 size-5 -translate-y-1/2 animate-spin text-muted-foreground" />
      )}
    </div>
  )
}
