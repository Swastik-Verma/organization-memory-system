import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'

// Chat needs the full height of <main> for its own internal scroll region
// (message list) plus a bottom-pinned input — the standard padded/page-scroll
// wrapper used by every other page would break that. So this route opts out
// of the wrapper instead of scrolling at the page level.
export function MainLayout() {
  const { pathname } = useLocation()
  const isFullBleed = pathname.startsWith('/chat')

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
