import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',   // ← required for Docker
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://api:8000',  // ← 'api' is the Docker service name
        changeOrigin: true,
      }
    }
  }
})