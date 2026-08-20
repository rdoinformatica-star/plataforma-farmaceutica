import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // 127.0.0.1 e nao localhost: no Windows o localhost resolve ::1 primeiro e o
    // proxy bate numa porta fechada, porque o uvicorn sobe so em IPv4.
    host: '127.0.0.1',
    port: 3000,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
