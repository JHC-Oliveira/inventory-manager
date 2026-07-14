import { AxiosError } from 'axios'

export function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    const backendMessage = error.response?.data?.message
    if (typeof backendMessage === 'string' && backendMessage.trim()) {
      return backendMessage
    }
  }
  return fallback
}