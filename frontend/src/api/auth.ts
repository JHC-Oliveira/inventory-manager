import client from './client'

export type LoginPayload = {
  email: string
  password: string
}

export type RegisterPayload = {
  email: string
  password: string
  full_name: string
}

export type UserResponse = {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_admin: boolean
}

export type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  user: UserResponse
}

export type RefreshResponse = {
  access_token: string
  refresh_token: string
  token_type: string
}

export const login = (data: LoginPayload): Promise<TokenResponse> =>
  client.post('/auth/login', data).then((res) => res.data)

export const register = (data: RegisterPayload): Promise<TokenResponse> =>
  client.post('/auth/register', data).then((res) => res.data)

export const logout = (refreshToken: string): Promise<void> =>
  client.post('/auth/logout', { refresh_token: refreshToken }).then((res) => res.data)

export const refresh = (refreshToken: string): Promise<RefreshResponse> =>
  client.post('/auth/refresh', { refresh_token: refreshToken }).then((res) => res.data)