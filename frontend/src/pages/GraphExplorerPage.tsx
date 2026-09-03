import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiErrorState } from '@/components/ApiErrorState'
import { GraphCanvas } from '@/components/graph/GraphCanvas'
import { GraphControls } from '@/components/graph/GraphControls'
import { isAbort, searchGraph } from '@/lib/api'
import { edgeKey, fetchEntityGraph } from '@/lib/graphData'
import type { GraphEdge, GraphNode, SubgraphResponse } from '@/types/graph'

/** Entity loaded on first visit when the URL doesn't name one. Resolved by name through
 *  /api/graph/search rather than hard-coding an id, so it survives a graph rebuild. */
const DEFAULT_SEARCH = 'Sally Beck'

// Deliberately the same key function graphData.ts dedupes with — a symmetric relationship
// reached from each of its two endpoints in two separate fetches must merge here too, or it
// reappears as a mirrored duplicate edge.
function keyOf(edge: GraphEdge): string {
  return edgeKey(edge.source, edge.target, edge.type)
}

export function GraphExplorerPage() {
  // The entity detail page's "View in Graph Explorer" button passes ?entity=<id>, so
  // arriving from a profile opens that entity's neighbourhood rather than the default.
  const [searchParams] = useSearchParams()
  const entityParam = searchParams.get('entity')

  const nodeMapRef = useRef(new Map<string, GraphNode>())
  const edgeMapRef = useRef(new Map<string, GraphEdge>())

  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([])
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([])
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<unknown>(null)
  const [reloadToken, setReloadToken] = useState(0)

  // Commits the (mutated in place) node/edge maps to state as fresh array references.
  // Existing node objects keep their identity across merges — that's what lets
  // react-force-graph preserve their x/y simulation position instead of re-scattering
  // the whole graph on every expand.
  const commitGraph = useCallback(() => {
    setGraphNodes(Array.from(nodeMapRef.current.values()))
    setGraphEdges(Array.from(edgeMapRef.current.values()))
  }, [])

  const mergeSubgraph = useCallback(
    (subgraph: SubgraphResponse, options?: { replace?: boolean }) => {
      if (options?.replace) {
        nodeMapRef.current = new Map()
        edgeMapRef.current = new Map()
      }
      for (const node of subgraph.nodes) {
        const existing = nodeMapRef.current.get(node.id)
        if (existing) {
          // Mutate in place rather than replacing the object: force-graph stores x/y/vx/vy
          // directly on the node objects it was handed, so swapping in a new object would
          // drop the node's settled position and re-scatter it.
          //
          // A node first seen as a *neighbour* carries an estimated weight in place of a
          // real mention_count (see graphData.ts) — a later fetch that returns it as a
          // centre, or a search result, carries the real figure, so the larger value wins.
          existing.label = node.label
          existing.type = node.type
          existing.mention_count = Math.max(existing.mention_count, node.mention_count)
        } else {
          nodeMapRef.current.set(node.id, node)
        }
      }
      for (const edge of subgraph.edges) {
        const key = keyOf(edge)
        if (!edgeMapRef.current.has(key)) {
          edgeMapRef.current.set(key, edge)
        }
      }
      commitGraph()
    },
    [commitGraph],
  )

  const loadCenter = useCallback(
    async (entityId: string, options: { replace?: boolean; signal?: AbortSignal } = {}) => {
      setIsLoading(true)
      try {
        const data = await fetchEntityGraph(entityId, { signal: options.signal })
        mergeSubgraph(data, { replace: options.replace })
        setExpandedIds((prev) => {
          const next = options.replace ? new Set<string>() : new Set(prev)
          next.add(entityId)
          return next
        })
        setLoadError(null)
      } finally {
        setIsLoading(false)
      }
    },
    [mergeSubgraph],
  )

  // Initial view. Either the entity named in ?entity=, or whatever /api/graph/search says
  // the default name resolves to.
  useEffect(() => {
    const controller = new AbortController()

    async function loadInitial() {
      setLoadError(null)
      try {
        let centerId = entityParam
        if (!centerId) {
          const results = await searchGraph(DEFAULT_SEARCH, 1, { signal: controller.signal })
          centerId = results.results[0]?.id ?? null
        }
        if (!centerId) {
          setSearchError(
            `Could not resolve a default entity ("${DEFAULT_SEARCH}") — search for one above.`,
          )
          return
        }
        await loadCenter(centerId, { replace: true, signal: controller.signal })
      } catch (err) {
        if (!isAbort(err)) setLoadError(err)
      }
    }

    void loadInitial()
    return () => controller.abort()
  }, [entityParam, loadCenter, reloadToken])

  function handleExpandNode(node: GraphNode) {
    void loadCenter(node.id).catch((err: unknown) => {
      if (!isAbort(err)) setLoadError(err)
    })
  }

  // Opens the profile in a NEW TAB rather than navigating in place. Navigating away would
  // discard the whole explored graph — every expand the user has done — with no way back.
  // Ids are encoded here because they go into a URL; the node object's own id stays raw.
  function handleNavigateNode(node: GraphNode) {
    window.open(`/entities/${encodeURIComponent(node.id)}`, '_blank', 'noopener,noreferrer')
  }

  function handleSubmitSearch() {
    const q = query.trim()
    if (!q) return

    setIsSearching(true)
    setSearchError(null)
    setLoadError(null)

    searchGraph(q)
      .then(async (response) => {
        const top = response.results[0]
        if (!top) {
          setSearchError(`No matching entity found for "${q}".`)
          return
        }
        await loadCenter(top.id, { replace: true })
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) setLoadError(err)
      })
      .finally(() => setIsSearching(false))
  }

  function handleReset() {
    setQuery('')
    setSearchError(null)
    setLoadError(null)
    setReloadToken((n) => n + 1)
  }

  return (
    <div className="flex h-full flex-col">
      <GraphControls
        query={query}
        onQueryChange={setQuery}
        onSubmitSearch={handleSubmitSearch}
        isSearching={isSearching}
        searchError={searchError}
        onReset={handleReset}
      />
      <div className="relative min-h-0 flex-1">
        {loadError != null && graphNodes.length === 0 ? (
          <div className="flex h-full items-center justify-center px-8">
            <ApiErrorState error={loadError} onRetry={() => setReloadToken((n) => n + 1)} />
          </div>
        ) : (
          <>
            {isLoading && (
              <div className="pointer-events-none absolute right-4 top-4 z-10 rounded-md border border-border bg-popover px-3 py-1.5 text-xs text-muted-foreground shadow-sm">
                Loading neighborhood…
              </div>
            )}
            {/* A failed expand shouldn't blow away a graph the user has already built up. */}
            {Boolean(loadError) && graphNodes.length > 0 && (
              <div className="absolute left-4 top-4 z-10 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-1.5 text-xs text-destructive">
                Could not load that neighborhood.
              </div>
            )}
            <GraphCanvas
              nodes={graphNodes}
              edges={graphEdges}
              expandedIds={expandedIds}
              onExpandNode={handleExpandNode}
              onNavigateNode={handleNavigateNode}
            />
          </>
        )}
      </div>
    </div>
  )
}
