import client from './client'

export type LoginPayload = {
  email: string
  password: string
}

export type RegisterPayload = {
  email: string
  password: string
  is_admin?: boolean
}

export const login = (data: LoginPayload) =>
  client.post('/auth/login', data).then((res) => res.data)

export const register = (data: RegisterPayload) =>
  client.post('/auth/register', data).then((res) => res.data)

export const logout = () =>
  client.post('/auth/logout').then((res) => res.data)

export const refresh = () =>
  client.post('/auth/refresh').then((res) => res.data)