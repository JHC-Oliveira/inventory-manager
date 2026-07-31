import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'

type Props = {
  adminOnly?: boolean
}

export default function ProtectedRoute({ adminOnly = false }: Props) {
  const { accessToken, user } = useAuthStore()

  if (!accessToken) return <Navigate to="/login" replace />
  if (adminOnly && !user?.is_admin) return <Navigate to="/products" replace />

  return <Outlet />
}
