import { useAuthStore } from '../store/authStore'

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)

  return (
    <div className="min-h-screen bg-slate-950 p-8 text-white">
      <h1 className="text-3xl font-bold">Dashboard</h1>
      <p className="mt-2 text-slate-400">
        Welcome {user?.email ?? 'user'}
      </p>
    </div>
  )
}