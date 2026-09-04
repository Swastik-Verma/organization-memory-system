import type { TopPerson } from '@/types/health'

interface TopEntitiesTableProps {
  topPersons: TopPerson[]
}

export function TopEntitiesTable({ topPersons }: TopEntitiesTableProps) {
  if (topPersons.length === 0) {
    return <p className="text-sm text-muted-foreground">No entity data available.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="w-10 py-2 font-medium">#</th>
            <th className="py-2 font-medium">Name</th>
            <th className="py-2 text-right font-medium">Mentions</th>
          </tr>
        </thead>
        <tbody>
          {topPersons.map((person, i) => (
            <tr key={person.name} className="border-b border-border/60 last:border-0">
              <td className="py-2 tabular-nums text-muted-foreground">{i + 1}</td>
              <td className="py-2">
                <a
                  href={`/entities?search=${encodeURIComponent(person.name)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-foreground hover:text-primary hover:underline"
                >
                  {person.name}
                </a>
              </td>
              <td className="py-2 text-right tabular-nums text-foreground">
                {person.mentions.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
