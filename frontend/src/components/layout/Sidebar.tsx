import { AlertTriangle, GitMerge, MessageSquare, Share2, Users, Waves } from 'lucide-react'
import { NavLink } from '@/components/layout/NavLink'

const navItems = [
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/graph', icon: Share2, label: 'Graph Explorer' },
  { to: '/entities', icon: Users, label: 'Entities' },
  { to: '/health', icon: Waves, label: 'Health' },
  { to: '/merges', icon: GitMerge, label: 'Merges' },
  { to: '/conflicts', icon: AlertTriangle, label: 'Conflicts' },
]

export function Sidebar() {
  return (
    <aside className="flex h-svh w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground">
      <div className="px-4 py-5">
        <span className="text-lg font-semibold tracking-tight text-sidebar-accent-foreground">
          OrgMemory
        </span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 px-3">
        {navItems.map((item) => (
          <NavLink key={item.to} {...item} />
        ))}
      </nav>
    </aside>
  )
}
