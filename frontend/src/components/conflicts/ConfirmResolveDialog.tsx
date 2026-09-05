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
import type { ConflictGroup } from '@/types/conflict'

/** Shared by "All Historical" and "Dismiss" — both are a single confirm with no extra input,
 *  differing only in copy and which action they submit. "Keep Best" needs its own dialog
 *  (KeepBestDialog.tsx) because it collects a winning claim first. */
export type SimpleResolveAction = 'all_historical' | 'dismiss'

interface ConfirmResolveDialogProps {
  conflict: ConflictGroup | null
  action: SimpleResolveAction | null
  submitting: boolean
  onCancel: () => void
  onConfirm: () => void
}

export function ConfirmResolveDialog({
  conflict,
  action,
  submitting,
  onCancel,
  onConfirm,
}: ConfirmResolveDialogProps) {
  const open = conflict !== null && action !== null

  const title = action === 'all_historical' ? 'Mark All as Historical' : 'Dismiss Conflict'
  const description =
    action === 'all_historical'
      ? `Mark all ${conflict?.claims.length ?? 0} claims as historical (superseded). None will be treated as the current reporting relationship.`
      : `Dismiss this conflict. All claims will be kept as current — this means ${conflict?.subject_name ?? 'this person'} legitimately reported to multiple people simultaneously.`

  return (
    <AlertDialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={submitting} onClick={onCancel}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction disabled={submitting} onClick={onConfirm}>
            {submitting ? 'Working…' : 'Confirm'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
