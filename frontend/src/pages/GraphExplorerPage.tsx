import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GraphCanvas } from '@/components/graph/GraphCanvas'
import { GraphControls } from '@/components/graph/GraphControls'
import { DEFAULT_CENTER_ID, mockFetchSubgraph, mockSearchEntities } from '@/mocks/graphMocks'
import type { GraphEdge, GraphNode, SubgraphResponse } from '@/types/graph'

function edgeKey(edge: GraphEdge): string {
  return `${edge.source}::${edge.type}::${edge.target}`
}

export function GraphExplorerPage() {
  const navigate = useNavigate()

  const nodeMapRef = useRef(new Map<string, GraphNode>())
  const edgeMapRef = useRef(new Map<string, GraphEdge>())
  // Mirrors the `hops` state for the mount-only effect below, which intentionally
  // does not depend on `hops` (changing the selector shouldn't auto-reload the
  // current view — only the next fetch it drives).
  const hopsRef = useRef<1 | 2>(1)

  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([])
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([])
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  const [query, setQuery] = useState('')
  const [hops, setHops] = useState<1 | 2>(1)
  const [isSearching, setIsSearching] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  useEffect(() => {
    hopsRef.current = hops
  }, [hops])

  // Commits the (mutated in place) node/edge maps to state as fresh array references.
  // Existing node objects keep their identity across merges — that's what lets
  // react-force-graph preserve their x/y simulation position instead of re-scattering
  // the whole graph on every expand.
  function commitGraph() {
    setGraphNodes(Array.from(nodeMapRef.current.values()))
    setGraphEdges(Array.from(edgeMapRef.current.values()))
  }

  function mergeSubgraph(subgraph: SubgraphResponse, options?: { replace?: boolean }) {
    if (options?.replace) {
      nodeMapRef.current = new Map()
      edgeMapRef.current = new Map()
    }
    for (const node of subgraph.nodes) {
      if (!nodeMapRef.current.has(node.id)) {
        nodeMapRef.current.set(node.id, node)
      }
    }
    for (const edge of subgraph.edges) {
      const key = edgeKey(edge)
      if (!edgeMapRef.current.has(key)) {
        edgeMapRef.current.set(key, edge)
      }
    }
    commitGraph()
  }

  async function loadDefaultView() {
    setIsLoading(true)
    try {
      const data = await mockFetchSubgraph(DEFAULT_CENTER_ID, hopsRef.current)
      mergeSubgraph(data, { replace: true })
      setExpandedIds(new Set())
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadDefaultView()
    // Mount-only: loads the initial default view once. Reset (below) re-triggers this
    // explicitly; the hops selector should not.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function handleExpandNode(node: GraphNode) {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      next.add(node.id)
      return next
    })
    setIsLoading(true)
    mockFetchSubgraph(node.id, hops)
      .then((data) => mergeSubgraph(data))
      .finally(() => setIsLoading(false))
  }

  function handleNavigateNode(node: GraphNode) {
    navigate(`/entities/${encodeURIComponent(node.id)}`)
  }

  function handleSubmitSearch() {
    const q = query.trim()
    if (!q) return

    setIsSearching(true)
    setSearchError(null)

    mockSearchEntities(q)
      .then(async (results) => {
        if (results.length === 0) {
          setSearchError(`No matching entity found for "${q}".`)
          return
        }
        const top = results[0]
        setIsLoading(true)
        try {
          const data = await mockFetchSubgraph(top.id, hops)
          mergeSubgraph(data, { replace: true })
          setExpandedIds(new Set([top.id]))
        } finally {
          setIsLoading(false)
        }
      })
      .finally(() => setIsSearching(false))
  }

  function handleReset() {
    setQuery('')
    setSearchError(null)
    void loadDefaultView()
  }

  return (
    <div className="flex h-full flex-col">
      <GraphControls
        query={query}
        onQueryChange={setQuery}
        onSubmitSearch={handleSubmitSearch}
        isSearching={isSearching}
        searchError={searchError}
        hops={hops}
        onHopsChange={setHops}
        onReset={handleReset}
      />
      <div className="relative min-h-0 flex-1">
        {isLoading && (
          <div className="pointer-events-none absolute right-4 top-4 z-10 rounded-md border border-border bg-popover px-3 py-1.5 text-xs text-muted-foreground shadow-sm">
            Loading neighborhood…
          </div>
        )}
        <GraphCanvas
          nodes={graphNodes}
          edges={graphEdges}
          expandedIds={expandedIds}
          onExpandNode={handleExpandNode}
          onNavigateNode={handleNavigateNode}
        />
      </div>
    </div>
  )
}
