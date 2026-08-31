import { useParams } from 'react-router-dom'
import { PagePlaceholder } from '@/components/PagePlaceholder'

export function EvidencePage() {
  const { id } = useParams<{ id: string }>()
  return (
    <PagePlaceholder
      title="Evidence"
      description={`Evidence detail — Day 40 (id: ${id})`}
    />
  )
}
