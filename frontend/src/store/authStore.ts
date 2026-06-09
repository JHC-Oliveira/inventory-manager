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
  refreshToken: string | null
  user: User
  setAuth: (accessToken: string, refreshToken: string, user: NonNullable<User>) => void
  setAccessToken: (accessToken: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  setAuth: (accessToken, refreshToken, user) =>
    set({ accessToken, refreshToken, user }),
  setAccessToken: (accessToken) =>
    set({ accessToken }),
  logout: () =>
    set({ accessToken: null, refreshToken: null, user: null }),
}))