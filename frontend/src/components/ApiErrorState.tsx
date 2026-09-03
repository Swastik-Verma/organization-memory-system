import { Button } from '@/components/ui/button'
import { ApiError, type ApiErrorKind } from '@/lib/api'

interface ApiErrorStateProps {
  error: unknown
  /** Omit to render without a retry button (e.g. a 404, where retrying changes nothing). */
  onRetry?: () => void
  /** Overrides the default copy for a 404 — pages know what wasn't found, this file doesn't. */
  notFoundMessage?: string
}

// One place that turns an ApiError into user-facing copy, so "backend isn't running" reads
// the same on every page instead of each page inventing its own wording. Day 37's chat page
// already had an error+retry pattern; this generalises it to the rest of the app.
const MESSAGES: Record<ApiErrorKind, string> = {
  network:
    'Cannot connect to the backend. Start it with `python scripts/run_server.py` and make sure Neo4j and Qdrant are running.',
  timeout: 'The backend took more than 10 seconds to respond.',
  notfound: 'That item could not be found.',
  client: 'The backend rejected this request.',
  server: 'Something went wrong on the server.',
  parse: 'The backend returned a response that could not be read.',
}

const TITLES: Record<ApiErrorKind, string> = {
  network: 'Backend unavailable',
  timeout: 'Request timed out',
  notfound: 'Not found',
  client: 'Request failed',
  server: 'Something went wrong',
  parse: 'Unreadable response',
}

export function ApiErrorState({ error, onRetry, notFoundMessage }: ApiErrorStateProps) {
  const kind: ApiErrorKind = error instanceof ApiError ? error.kind : 'server'
  const message =
    kind === 'notfound' && notFoundMessage ? notFoundMessage : MESSAGES[kind]

  // Retrying a 404 re-fetches the same missing id and fails identically, so the button is
  // suppressed there even when the page passes a handler.
  const showRetry = Boolean(onRetry) && kind !== 'notfound'

  return (
    <div className="rounded-lg border border-dashed border-border px-4 py-10 text-center">
      <p className="text-sm font-medium text-foreground">{TITLES[kind]}</p>
      <p className="mx-auto mt-1.5 max-w-md text-sm text-muted-foreground">{message}</p>
      {showRetry && (
        <Button type="button" variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}
