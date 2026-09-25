import { Navigate, Route, Routes } from 'react-router'
import { useMe } from './api/hooks'
import { Layout } from './components/Layout'
import { Loading } from './components/ui'
import { AgentsPage } from './pages/AgentsPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { ProjectPage } from './pages/ProjectPage'
import { RunPage } from './pages/RunPage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { data: me, isLoading } = useMe()
  if (isLoading) return <Loading />
  if (!me) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/projects/:projectId" element={<ProjectPage />} />
        <Route path="/runs/:runId" element={<RunPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
