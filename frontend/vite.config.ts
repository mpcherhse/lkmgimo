import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// В разработке API и календари проксируются на бэкенд (:8800); в сборке фронтенд отдаёт тот же сервер.
const backend = { target: 'http://127.0.0.1:8800', changeOrigin: false }
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': backend, '/cal': backend, '/dav': backend, '/.well-known': backend } },
  build: { target: 'es2020', sourcemap: false, chunkSizeWarningLimit: 600, assetsInlineLimit: 0 }, // без data:-шрифтов — строгая CSP
})
