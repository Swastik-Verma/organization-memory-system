import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'
import { MainLayout } from '@/components/layout/MainLayout'
import { ChatPage } from '@/pages/ChatPage'
import { ConflictsPage } from '@/pages/ConflictsPage'
import { EntitiesPage } from '@/pages/EntitiesPage'
import { EntityDetailPage } from '@/pages/EntityDetailPage'
import { EvidencePage } from '@/pages/EvidencePage'
import { GraphExplorerPage } from '@/pages/GraphExplorerPage'
import { HealthPage } from '@/pages/HealthPage'
import { MergesPage } from '@/pages/MergesPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

function App() {
  return (
    <Router>
      <Routes>
        <Route element={<MainLayout />}>
          <Route index element={<Navigate to="/chat" replace />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="graph" element={<GraphExplorerPage />} />
          <Route path="entities" element={<EntitiesPage />} />
          <Route path="entities/:id" element={<EntityDetailPage />} />
          <Route path="evidence/:id" element={<EvidencePage />} />
          <Route path="health" element={<HealthPage />} />
          <Route path="conflicts" element={<ConflictsPage />} />
          <Route path="merges" element={<MergesPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Router>
  )
}

export default App
