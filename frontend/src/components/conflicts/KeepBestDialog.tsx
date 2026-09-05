import { useEffect, useState } from 'react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { bestClaim } from '@/lib/conflictFilter'
import type { ConflictGroup } from '@/types/conflict'

interface KeepBestDialogProps {
  /** null closes the dialog. */
  conflict: ConflictGroup | null
  submitting: boolean
  onCancel: () => void
  onConfirm: (winningClaimId: string) => void
}

export function KeepBestDialog({ conflict, submitting, onCancel, onConfirm }: KeepBestDialogProps) {
  const [selected, setSelected] = useState<string | null>(null)

  // Re-seed the default selection (highest mention_count = most evidence) every time a
  // different conflict opens the dialog. The human still picks — this is only a starting point.
  useEffect(() => {
    setSelected(conflict ? (bestClaim(conflict.claims)?.claim_id ?? null) : null)
  }, [conflict])

  return (
    <AlertDialog open={conflict !== null} onOpenChange={(open) => !open && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Keep Best Claim</AlertDialogTitle>
          <AlertDialogDescription>
            Choose which claim to keep as{' '}
            <strong className="text-foreground">{conflict?.subject_name}</strong>&rsquo;s current
            reporting relationship. The others will be marked superseded.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-1.5">
          {conflict?.claims.map((c) => (
            <label
              key={c.claim_id}
              className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm transition-colors has-[:checked]:border-primary has-[:checked]:bg-primary/5"
            >
              <span className="flex items-center gap-2">
                <input
                  type="radio"
                  name="winning-claim"
                  value={c.claim_id}
                  checked={selected === c.claim_id}
                  onChange={() => setSelected(c.claim_id)}
                  className="accent-primary"
                />
                {c.object_name}
              </span>
              <span className="text-xs text-muted-foreground">{c.mention_count} mentions</span>
            </label>
          ))}
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={submitting} onClick={onCancel}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={submitting || !selected}
            onClick={() => selected && onConfirm(selected)}
          >
            {submitting ? 'Resolving…' : 'Confirm'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
