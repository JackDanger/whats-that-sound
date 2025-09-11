import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    hmr: {
      // Configure these via env if running behind a reverse proxy / TLS terminator
      // e.g. VITE_HMR_HOST=my.domain.com VITE_HMR_PORT=443 VITE_HMR_PROTOCOL=wss
      host: process.env.VITE_HMR_HOST as any,
      clientPort: process.env.VITE_HMR_PORT ? Number(process.env.VITE_HMR_PORT) : undefined,
      protocol: (process.env.VITE_HMR_PROTOCOL as any) || undefined,
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/api/events': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
