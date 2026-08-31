import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">
        404 — Page not found
      </h1>
      <p className="text-sm text-muted-foreground">
        The page you're looking for doesn't exist.
      </p>
      <Link to="/chat" className="text-sm font-medium text-primary hover:underline">
        Back to Chat
      </Link>
    </div>
  )
}
