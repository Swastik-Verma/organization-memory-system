import { useParams } from 'react-router-dom'
import { PagePlaceholder } from '@/components/PagePlaceholder'

export function EntityDetailPage() {
  const { id } = useParams<{ id: string }>()
  return (
    <PagePlaceholder
      title="Entity Detail"
      description={`Entity detail — Day 39 (id: ${id})`}
    />
  )
}
