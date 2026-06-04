import { create } from 'zustand'

type User = {
  id: string
  email: string
  is_admin: boolean
} | null

type AuthState = {
  accessToken: string | null
  user: User
  setAuth: (token: string, user: NonNullable<User>) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  setAuth: (token, user) => set({ accessToken: token, user }),
  logout: () => set({ accessToken: null, user: null }),
}))