import type { LucideIcon } from 'lucide-react'
import { NavLink as RouterNavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface NavLinkProps {
  to: string
  icon: LucideIcon
  label: string
}

export function NavLink({ to, icon: Icon, label }: NavLinkProps) {
  return (
    <RouterNavLink
      to={to}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
          isActive
            ? 'bg-sidebar-primary text-sidebar-primary-foreground'
            : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span>{label}</span>
    </RouterNavLink>
  )
}
