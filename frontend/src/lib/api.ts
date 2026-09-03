// Centralised API client for the FastAPI backend (Day 41).
//
// This is a pure transport layer: one function per real endpoint, returning the backend's
// response shape verbatim. Anything that *composes* several endpoints into a view-specific
// shape lives elsewhere (see src/lib/graphData.ts) so this file stays a 1:1 map of the API.
//
// ── Entity IDs contain colons and email slugs ──────────────────────────────────────────
// e.g. `person:beck-sally:sally-beck-at-enron-com`. Every function that puts an id in a URL
// *path* runs it through encodeURIComponent(). Ids kept in application state (graph node
// objects, React state, comparisons) stay UN-encoded — encoding happens only at the
// network boundary, here.
//
// ── Auth ───────────────────────────────────────────────────────────────────────────────
// X-User-Clearance: 4 (max) is hard-coded for development, matching CLAUDE.md §7. This is
// deliberately not production-secure.

import type {
  EntityClaimsResponse,
  EntityDetailResponse,
  EntityListResponse,
  EntityTimelineResponse,
} from '@/types/entity'
import type { ChatResponse } from '@/types/chat'
import type { GraphSearchResponse, SubgraphResponse } from '@/types/graph'
import type { EvidenceDetailResponse } from '@/types/evidence'
import type { HealthResponse } from '@/types/health'

const API_BASE = 'http://localhost:8000'
const CLEARANCE = '4'

/** Read-only requests that outlive this are aborted and surface as a `timeout` ApiError.
 *  These only touch Neo4j/Qdrant and return in well under a second in practice. */
export const REQUEST_TIMEOUT_MS = 10_000

/**
 * POST /api/chat gets its own, much longer budget.
 *
 * A chat turn is not one query — it is a query-understanding LLM call, then graph +
 * semantic retrieval, then an answer-generation LLM call (plus a third LLM call to rewrite
 * a follow-up). Measured end-to-end against the live backend: **10.2 seconds** for
 * "Who does Sally Beck report to?" — 4.1s of retrieval between two Gemini round-trips.
 *
 * Under the 10s read timeout that request aborted client-side a fraction of a second after
 * the backend had already produced a correct 3-citation answer: the user would have seen a
 * timeout error, and the Gemini quota would have been spent anyway. A generous ceiling here
 * is what makes the timeout a real safety net rather than a guaranteed failure.
 */
export const CHAT_TIMEOUT_MS = 60_000

// ---------------------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------------------

export type ApiErrorKind =
  | 'network' // backend unreachable — not running, wrong port, CORS rejected
  | 'timeout' // exceeded REQUEST_TIMEOUT_MS
  | 'notfound' // 404 — the specific entity/evidence id does not exist
  | 'client' // other 4xx
  | 'server' // 5xx
  | 'parse' // 2xx but the body was not valid JSON

/**
 * Every failure from this module is an ApiError, so pages can branch on `kind` instead of
 * string-matching messages. `message` is written to be safe to show to a user directly.
 */
export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | null

  constructor(kind: ApiErrorKind, message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
  }

  static from(err: unknown): ApiError {
    if (err instanceof ApiError) return err
    // A genuine abort (component unmount, a superseded request, React StrictMode's dev-only
    // double-invoke) never reaches this function — fetchApi/postApi rethrow it raw before
    // calling ApiError.from(), specifically so it keeps its AbortError identity for
    // isAbort() to recognise downstream. An earlier version of this method didn't do that:
    // it fell through to the generic 'network' branch below for anything but TimeoutError,
    // silently turning a harmless cancelled request into a fake "backend unreachable" error
    // that isAbort() could no longer detect. See the comments in fetchApi/postApi.
    if (err instanceof DOMException && err.name === 'TimeoutError') {
      return new ApiError('timeout', 'The backend took too long to respond. Please try again.')
    }
    // fetch() rejects with a bare TypeError for DNS/connection-refused/CORS failures — it
    // deliberately does not distinguish them, so this is the best signal available.
    return new ApiError(
      'network',
      'Cannot connect to the backend. Make sure it is running at ' + API_BASE + '.',
    )
  }
}

function errorForStatus(status: number): ApiError {
  if (status === 404) return new ApiError('notfound', 'Not found.', 404)
  if (status >= 500) {
    return new ApiError('server', 'Something went wrong on the server.', status)
  }
  return new ApiError('client', `Request rejected by the backend (HTTP ${status}).`, status)
}

// ---------------------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------------------

interface RequestOptions {
  params?: Record<string, string | number | undefined>
  /** Passed through from a component's cleanup so an unmounted page's request is dropped. */
  signal?: AbortSignal
}

function buildUrl(path: string, params?: RequestOptions['params']): string {
  const url = new URL(path, API_BASE)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== '') url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

/**
 * Merges the caller's abort signal (if any) with the timeout signal. AbortSignal.any is
 * available in every browser this app targets; without it, a caller-supplied signal would
 * silently disable the timeout.
 */
function withTimeout(signal?: AbortSignal, timeoutMs = REQUEST_TIMEOUT_MS): AbortSignal {
  const timeout = AbortSignal.timeout(timeoutMs)
  return signal ? AbortSignal.any([signal, timeout]) : timeout
}

async function parseJson<T>(response: Response): Promise<T> {
  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError('parse', 'The backend returned a response that could not be read.')
  }
}

/**
 * True for an abort the app itself caused (unmount, a superseded request, or React
 * StrictMode's dev-only mount → cleanup → mount double-invocation of every effect, which
 * fires and then immediately aborts one throwaway request per effect on every mount).
 * Callers use this to discard the rejection rather than surface it as a real failure.
 *
 * MUST run on the raw error straight out of fetch(), before ApiError.from() sees it — see
 * the guard in fetchApi/postApi below for why.
 */
function isRawAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError'
}

/** True for an abort the app itself caused (unmount / superseded request) — never shown. */
export function isAbort(err: unknown): boolean {
  return isRawAbort(err)
}

async function fetchApi<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(buildUrl(path, options.params), {
      headers: { 'X-User-Clearance': CLEARANCE },
      signal: withTimeout(options.signal),
    })
  } catch (err) {
    // An aborted request must reach the caller as the ORIGINAL AbortError DOMException, not
    // as an ApiError. ApiError.from() only recognises TimeoutError explicitly; everything
    // else — including a genuine abort — falls through to a generic 'network' ApiError,
    // which silently destroys the identity isAbort() needs to see. Rethrowing here before
    // that wrap is what makes isAbort() actually work at every call site that uses it.
    if (isRawAbort(err)) throw err
    throw ApiError.from(err)
  }
  if (!response.ok) throw errorForStatus(response.status)
  return parseJson<T>(response)
}

async function postApi<T>(
  path: string,
  body: unknown,
  options: RequestOptions & { timeoutMs?: number } = {},
): Promise<T> {
  let response: Response
  try {
    response = await fetch(buildUrl(path), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Clearance': CLEARANCE,
      },
      body: JSON.stringify(body),
      signal: withTimeout(options.signal, options.timeoutMs),
    })
  } catch (err) {
    // See the matching comment in fetchApi above.
    if (isRawAbort(err)) throw err
    throw ApiError.from(err)
  }
  if (!response.ok) throw errorForStatus(response.status)
  return parseJson<T>(response)
}

// ---------------------------------------------------------------------------------------
// Chat — POST /api/chat
// ---------------------------------------------------------------------------------------

/**
 * Consumes Gemini quota on every call (1 chatbot call + 1 query-parse call, +1 more for a
 * follow-up) — see CLAUDE.md §9. Never call this in a retry/debug loop.
 */
export function sendChatMessage(
  question: string,
  sessionId: string | null,
  options: RequestOptions = {},
): Promise<ChatResponse> {
  return postApi<ChatResponse>(
    '/api/chat',
    { question, session_id: sessionId },
    { ...options, timeoutMs: CHAT_TIMEOUT_MS },
  )
}

// ---------------------------------------------------------------------------------------
// Entities
// ---------------------------------------------------------------------------------------

/**
 * GET /api/entities
 *
 * NOTE: the backend query param is `entity_type`, not `type`, and it only understands
 * "person" and "organization" — any other value silently falls through to the unfiltered
 * `(n:Person OR n:Organization)` branch and returns *everything* rather than erroring.
 * The UI must therefore never send "deal" or "decision" here. See EntitiesPage.tsx.
 */
export function fetchEntities(
  args: { type?: string; search?: string; skip?: number; limit?: number } = {},
  options: RequestOptions = {},
): Promise<EntityListResponse> {
  return fetchApi<EntityListResponse>('/api/entities', {
    ...options,
    params: {
      entity_type: args.type,
      search: args.search,
      skip: args.skip,
      limit: args.limit,
    },
  })
}

export function fetchEntityDetail(
  id: string,
  options: RequestOptions = {},
): Promise<EntityDetailResponse> {
  return fetchApi<EntityDetailResponse>(`/api/entities/${encodeURIComponent(id)}`, options)
}

/** `claimType` filters server-side (`c.claim_type = $claim_type`). There is no limit param
 *  on this route — it returns every matching claim, which for a busy person is 200+. */
export function fetchEntityClaims(
  id: string,
  claimType?: string,
  options: RequestOptions = {},
): Promise<EntityClaimsResponse> {
  return fetchApi<EntityClaimsResponse>(`/api/entities/${encodeURIComponent(id)}/claims`, {
    ...options,
    params: { claim_type: claimType },
  })
}

export function fetchEntityTimeline(
  id: string,
  options: RequestOptions = {},
): Promise<EntityTimelineResponse> {
  return fetchApi<EntityTimelineResponse>(
    `/api/entities/${encodeURIComponent(id)}/timeline`,
    options,
  )
}

// ---------------------------------------------------------------------------------------
// Graph
// ---------------------------------------------------------------------------------------

/**
 * GET /api/graph/{id}/subgraph — raw response, Claim/Message hops and all.
 *
 * The backend param is `depth` (1-2), not `hops`. Callers wanting a readable
 * entity-to-entity graph should use fetchEntityGraph() in src/lib/graphData.ts instead;
 * this raw call is what that function builds on. See graphData.ts for why.
 */
export function fetchSubgraph(
  entityId: string,
  depth = 1,
  limit = 200,
  options: RequestOptions = {},
): Promise<SubgraphResponse> {
  return fetchApi<SubgraphResponse>(`/api/graph/${encodeURIComponent(entityId)}/subgraph`, {
    ...options,
    params: { depth, limit },
  })
}

/** Searches Person, Organization, Deal and Decision — unlike /api/entities, which cannot
 *  reach Deal or Decision at all. Matches canonical_name and aliases, case-insensitively. */
export function searchGraph(
  query: string,
  limit = 20,
  options: RequestOptions = {},
): Promise<GraphSearchResponse> {
  return fetchApi<GraphSearchResponse>('/api/graph/search', {
    ...options,
    params: { q: query, limit },
  })
}

// ---------------------------------------------------------------------------------------
// Evidence
// ---------------------------------------------------------------------------------------

export function fetchEvidence(
  evidenceId: string,
  options: RequestOptions = {},
): Promise<EvidenceDetailResponse> {
  return fetchApi<EvidenceDetailResponse>(
    `/api/evidence/${encodeURIComponent(evidenceId)}`,
    options,
  )
}

// ---------------------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------------------

export function fetchHealth(options: RequestOptions = {}): Promise<HealthResponse> {
  return fetchApi<HealthResponse>('/api/health', options)
}
