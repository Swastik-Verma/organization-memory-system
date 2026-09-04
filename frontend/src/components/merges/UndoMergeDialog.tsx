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
import type { MergeItem } from '@/types/merge'

interface UndoMergeDialogProps {
  /** null closes the dialog — there is nothing to confirm. */
  merge: MergeItem | null
  submitting: boolean
  onCancel: () => void
  onConfirm: () => void
}

export function UndoMergeDialog({ merge, submitting, onCancel, onConfirm }: UndoMergeDialogProps) {
  return (
    <AlertDialog open={merge !== null} onOpenChange={(open) => !open && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Undo Merge</AlertDialogTitle>
          <AlertDialogDescription>
            {merge && (
              <>
                This will restore <strong className="text-foreground">{merge.source_name}</strong> as
                a separate entity from <strong className="text-foreground">{merge.target_name}</strong>.
                Entity identity (names, aliases, emails) will be restored. Existing claims will NOT be
                reassigned. This action can be re-done by running the merge pipeline again.
              </>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={submitting} onClick={onCancel}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction variant="destructive" disabled={submitting} onClick={onConfirm}>
            {submitting ? 'Undoing…' : 'Confirm Undo'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
