import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { Button } from '../ui/button'
import { logout as logoutApi } from '../../api/auth'

const tabs = [
  { to: '/products', label: 'Products' },
  { to: '/movements', label: 'Movements' },
  { to: '/orders', label: 'Orders' },
]

export default function AppHeader() {
  const location = useLocation()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const clearAuth = useAuthStore((s) => s.logout)

  const handleLogout = async () => {
    try {
      await logoutApi()
    } catch {
      // ignore — logging out regardless
    } finally {
      clearAuth()
      navigate('/login')
    }
  }

  return (
    <header className="border-b border-slate-800 bg-slate-900/60 px-8 py-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm text-slate-400">Inventory Manager</p>
          <nav className="mt-2 flex gap-4">
            {tabs.map((tab) => (
              <Link
                key={tab.to}
                to={tab.to}
                className={`text-sm font-medium transition ${
                  location.pathname.startsWith(tab.to)
                    ? 'text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {tab.label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <p className="text-sm text-slate-400">
            {user?.full_name ?? user?.email ?? 'user'}
          </p>
          <Button
            variant="outline"
            onClick={handleLogout}
            className="transition hover:bg-slate-800 hover:text-white"
          >
            Logout
          </Button>
        </div>
      </div>
    </header>
  )
}
