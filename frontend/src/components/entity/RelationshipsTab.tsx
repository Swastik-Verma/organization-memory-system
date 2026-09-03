import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Minus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { ApiErrorState } from '@/components/ApiErrorState'
import { EntityTypeBadge } from '@/components/entity/EntityTypeBadge'
import { buttonVariants } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { isAbort } from '@/lib/api'
import { fetchEntityGraph } from '@/lib/graphData'
import { isSymmetricRelationship, relationshipTypeLabel } from '@/lib/relationshipTypes'
import type { GraphEdge, GraphNode } from '@/types/graph'

interface RelationshipsTabProps {
  entityId: string
}

interface Relationship {
  edge: GraphEdge
  node: GraphNode
  /** 'out' = this entity is the subject, 'in' = the object, 'none' = symmetric. */
  direction: 'out' | 'in' | 'none'
}

function DirectionIcon({ direction }: { direction: Relationship['direction'] }) {
  if (direction === 'out') return <ArrowRight className="size-3.5" aria-label="outgoing" />
  if (direction === 'in') return <ArrowLeft className="size-3.5" aria-label="incoming" />
  return <Minus className="size-3.5" aria-label="mutual" />
}

export function RelationshipsTab({ entityId }: RelationshipsTabProps) {
  const [relationships, setRelationships] = useState<Relationship[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [reloadToken, setReloadToken] = useState(0)

  // Uses the same composed graph the Graph Explorer renders (see src/lib/graphData.ts), so
  // this list and the canvas always agree about which relationships exist and how strong
  // they are — rather than each reading a different endpoint and disagreeing.
  useEffect(() => {
    const controller = new AbortController()
    setRelationships(null)
    setError(null)

    fetchEntityGraph(entityId, { signal: controller.signal })
      .then((subgraph) => {
        const nodesById = new Map(subgraph.nodes.map((n) => [n.id, n]))
        // Only this entity's own connections. The composed subgraph can contain edges
        // between two of its *other* nodes, which belong on the canvas but not in a flat
        // list titled "relationships of this entity".
        const rows: Relationship[] = subgraph.edges
          .filter((e) => e.source === entityId || e.target === entityId)
          .map((e) => {
            const otherId = e.source === entityId ? e.target : e.source
            const node = nodesById.get(otherId)
            if (!node) return null
            const direction: Relationship['direction'] = isSymmetricRelationship(e.type)
              ? 'none'
              : e.source === entityId
                ? 'out'
                : 'in'
            return { edge: e, node, direction }
          })
          .filter((r): r is Relationship => r !== null)

        setRelationships(rows)
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(err)
      })

    return () => controller.abort()
  }, [entityId, reloadToken])

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Link
          to={`/graph?entity=${encodeURIComponent(entityId)}`}
          className={buttonVariants({ variant: 'outline', size: 'sm' })}
        >
          View in Graph Explorer
        </Link>
      </div>

      {error ? (
        <ApiErrorState error={error} onRetry={() => setReloadToken((n) => n + 1)} />
      ) : relationships === null ? (
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
          {relationships.map(({ edge, node, direction }) => (
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
                <span className="flex items-center gap-1.5">
                  <DirectionIcon direction={direction} />
                  {relationshipTypeLabel(edge.type)}
                </span>
                {/* Day 39 showed "N sources" here, meaning the number of evidence records
                    backing the relationship. That count is not obtainable from the live API
                    (see types/entity.ts on the ClaimResult.evidence backend gap), so this
                    now reports what the data does support: how many separate claims of this
                    type connect the two entities. Relabelled rather than left saying
                    "sources" over a different number. */}
                {edge.claim_count !== null && (
                  <span>
                    {edge.claim_count} {edge.claim_count === 1 ? 'claim' : 'claims'}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
