import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { EntityTypeBadge } from '@/components/entity/EntityTypeBadge'
import { buttonVariants } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { claimTypeLabel } from '@/lib/claimTypes'
import { mockFetchSubgraph } from '@/mocks/graphMocks'
import type { GraphEdge, GraphNode } from '@/types/graph'

interface RelationshipsTabProps {
  entityId: string
}

interface Relationship {
  edge: GraphEdge
  node: GraphNode
}

export function RelationshipsTab({ entityId }: RelationshipsTabProps) {
  const [relationships, setRelationships] = useState<Relationship[] | null>(null)

  useEffect(() => {
    let cancelled = false
    setRelationships(null)

    mockFetchSubgraph(entityId, 1).then((subgraph) => {
      if (cancelled) return

      const nodesById = new Map(subgraph.nodes.map((n) => [n.id, n]))
      // The Relationships tab shows this entity's own connections only — a subgraph fixture
      // can include edges between two of its *other* nodes (see graphMocks.ts, e.g. the
      // Global Crossing deal's fixture includes a Zufferli↔Global Crossing Ltd edge), which
      // belong on the graph canvas but not on this flat list.
      const rows: Relationship[] = subgraph.edges
        .filter((e) => e.source === entityId || e.target === entityId)
        .map((e) => {
          const otherId = e.source === entityId ? e.target : e.source
          const node = nodesById.get(otherId)
          return node ? { edge: e, node } : null
        })
        .filter((r): r is Relationship => r !== null)

      setRelationships(rows)
    })

    return () => {
      cancelled = true
    }
  }, [entityId])

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Link to="/graph" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
          View in Graph Explorer
        </Link>
      </div>

      {relationships === null ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : relationships.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          No known relationships for this entity yet.
        </p>
      ) : (
        <div className="space-y-2">
          {relationships.map(({ edge, node }) => (
            <div
              key={`${edge.source}-${edge.type}-${edge.target}`}
              className="flex items-center justify-between gap-4 rounded-lg border border-border bg-card px-4 py-3"
            >
              <div className="flex min-w-0 items-center gap-3">
                <EntityTypeBadge type={node.type} />
                <Link
                  to={`/entities/${encodeURIComponent(node.id)}`}
                  className="truncate text-sm font-medium text-primary hover:underline"
                >
                  {node.label}
                </Link>
              </div>
              <div className="flex shrink-0 items-center gap-4 text-xs text-muted-foreground">
                <span>{claimTypeLabel(edge.claim_type ?? edge.type)}</span>
                <span>{edge.claim_count ?? 0} sources</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
