import { create } from 'zustand'

type User = {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_admin: boolean
} | null

type AuthState = {
  accessToken: string | null
  user: User
  setAuth: (accessToken: string, user: NonNullable<User>) => void
  setAccessToken: (accessToken: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  setAuth: (accessToken, user) => set({ accessToken, user }),
  setAccessToken: (accessToken) => set({ accessToken }),
  logout: () => set({ accessToken: null, user: null }),
}))
