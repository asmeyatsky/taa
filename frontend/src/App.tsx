import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './auth/AuthContext'
import ProtectedRoute from './auth/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import HomePage from './pages/HomePage'
import GeneratePage from './pages/GeneratePage'
import DomainsPage from './pages/DomainsPage'
import CompliancePage from './pages/CompliancePage'
import AnalyticsPage from './pages/AnalyticsPage'
import UsersPage from './pages/UsersPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000 } },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }>
              <Route path="/" element={<HomePage />} />
              <Route path="/generate" element={
                <ProtectedRoute permission="generate:run">
                  <GeneratePage />
                </ProtectedRoute>
              } />
              <Route path="/domains" element={
                <ProtectedRoute permission="domains:view">
                  <DomainsPage />
                </ProtectedRoute>
              } />
              <Route path="/compliance" element={
                <ProtectedRoute permission="compliance:view">
                  <CompliancePage />
                </ProtectedRoute>
              } />
              <Route path="/analytics" element={
                <ProtectedRoute permission="analytics:view">
                  <AnalyticsPage />
                </ProtectedRoute>
              } />
              <Route path="/users" element={
                <ProtectedRoute permission="users:manage">
                  <UsersPage />
                </ProtectedRoute>
              } />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
