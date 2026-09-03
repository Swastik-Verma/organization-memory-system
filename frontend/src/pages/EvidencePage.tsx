import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ClaimSection } from '@/components/evidence/ClaimSection'
import { EvidenceQuote } from '@/components/evidence/EvidenceQuote'
import { SourceEmail } from '@/components/evidence/SourceEmail'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiErrorState } from '@/components/ApiErrorState'
import { fetchEvidence, isAbort } from '@/lib/api'
import type { EvidenceDetailResponse } from '@/types/evidence'

export function EvidencePage() {
  const { id: rawId } = useParams<{ id: string }>()
  const id = rawId ? decodeURIComponent(rawId) : ''
  const navigate = useNavigate()

  const [evidence, setEvidence] = useState<EvidenceDetailResponse | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setEvidence(null)
    setError(null)

    fetchEvidence(id, { signal: controller.signal })
      .then(setEvidence)
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(err)
      })

    return () => controller.abort()
  }, [id, reloadToken])

  // This page is usually opened in a new tab (from the chat evidence drawer or an entity's
  // claim card), so there's often no in-app history to go back to — fall back to /entities
  // rather than leaving the back link stranded.
  function handleBack() {
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      navigate('/entities')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <button
          type="button"
          onClick={handleBack}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          &larr; Back
        </button>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Evidence Detail</h1>
        <p className="text-sm text-muted-foreground">Evidence ID: {id}</p>
      </div>

      {error ? (
        <div className="space-y-3">
          <ApiErrorState
            error={error}
            onRetry={() => setReloadToken((n) => n + 1)}
            notFoundMessage={`No evidence with id "${id}" exists in the graph.`}
          />
          <p className="text-center text-sm text-muted-foreground">
            <Link to="/entities" className="font-medium text-primary hover:underline">
              Browse entities
            </Link>{' '}
            instead.
          </p>
        </div>
      ) : null}

      {!error && !evidence && (
        <div className="space-y-6">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {!error && evidence && (
        <div className="space-y-6">
          <ClaimSection evidence={evidence} />
          <EvidenceQuote quote={evidence.quote} />
          <SourceEmail evidence={evidence} />
        </div>
      )}
    </div>
  )
}
