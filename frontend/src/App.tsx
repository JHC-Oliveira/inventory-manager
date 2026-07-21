import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import StockPage from './pages/StockPage'
import ProtectedRoute from './components/layout/ProtectedRoute'
import { refresh } from './api/auth'
import { useAuthStore } from './store/authStore'

export default function App() {
  const setAuth = useAuthStore((s) => s.setAuth)
  const [checkingAuth, setCheckingAuth] = useState(true)

  useEffect(() => {
    refresh()
      .then((data) => setAuth(data.access_token, data.user))
      .catch(() => {})
      .finally(() => setCheckingAuth(false))
  }, [])

  if (checkingAuth) return null

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/products/:id/stock" element={<StockPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
