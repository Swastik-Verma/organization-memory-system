import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ClaimSection } from '@/components/evidence/ClaimSection'
import { EvidenceQuote } from '@/components/evidence/EvidenceQuote'
import { SourceEmail } from '@/components/evidence/SourceEmail'
import { Skeleton } from '@/components/ui/skeleton'
import { mockFetchEvidence } from '@/mocks/evidenceMocks'
import type { EvidenceDetailResponse } from '@/types/evidence'

export function EvidencePage() {
  const { id: rawId } = useParams<{ id: string }>()
  const id = rawId ? decodeURIComponent(rawId) : ''
  const navigate = useNavigate()

  const [evidence, setEvidence] = useState<EvidenceDetailResponse | null>(null)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    let cancelled = false
    setEvidence(null)
    setNotFound(false)

    mockFetchEvidence(id)
      .then((res) => {
        if (!cancelled) setEvidence(res)
      })
      .catch(() => {
        if (!cancelled) setNotFound(true)
      })

    return () => {
      cancelled = true
    }
  }, [id])

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

      {notFound && (
        <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          Evidence "{id}" was not found.{' '}
          <Link to="/entities" className="font-medium text-primary hover:underline">
            Browse entities
          </Link>{' '}
          instead.
        </p>
      )}

      {!notFound && !evidence && (
        <div className="space-y-6">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {!notFound && evidence && (
        <div className="space-y-6">
          <ClaimSection evidence={evidence} />
          <EvidenceQuote quote={evidence.quote} />
          <SourceEmail evidence={evidence} />
        </div>
      )}
    </div>
  )
}
