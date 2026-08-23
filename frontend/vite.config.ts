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
    // O Cloudflare Tunnel expoe o app num host tipo *.trycloudflare.com, que
    // o Vite bloquearia por padrao (protecao contra DNS rebinding). O trafego
    // ja passa pelo tunel do Cloudflare antes de chegar aqui, entao liberar
    // qualquer host nao abre a porta pra rebinding de verdade.
    allowedHosts: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
