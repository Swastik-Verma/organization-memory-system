import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'

// Chat and the graph explorer both need the full height of <main> for their own
// content — chat for its internal scroll region plus bottom-pinned input, the graph
// explorer for its canvas, which needs to fill its container rather than sit inside a
// scrolling page. The standard padded/page-scroll wrapper used by every other page
// would break both, so these routes opt out of it.
export function MainLayout() {
  const { pathname } = useLocation()
  const isFullBleed = pathname.startsWith('/chat') || pathname.startsWith('/graph')

  return (
    <div className="flex h-svh overflow-hidden bg-background text-foreground">
      <Sidebar />
      <main className={isFullBleed ? 'flex-1 overflow-hidden' : 'flex-1 overflow-y-auto'}>
        {isFullBleed ? (
          <Outlet />
        ) : (
          <div className="mx-auto max-w-5xl px-8 py-8">
            <Outlet />
          </div>
        )}
      </main>
    </div>
  )
}
