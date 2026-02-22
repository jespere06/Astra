import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      port: 3000,
      host: true,
      proxy: {
        '/api/orchestrator': {
          target: env.VITE_API_ORCHESTRATOR || 'http://localhost:8001',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/orchestrator/, '')
        },
        '/api/ingest': {
          target: env.VITE_API_INGEST || 'http://localhost:8003',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/ingest/, '')
        },
        '/api/core': {
          target: env.VITE_API_CORE || 'http://localhost:8002',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/core/, '')
        },
        '/api/learning': {
          target: env.VITE_API_LEARNING || 'http://localhost:8006',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/learning/, '/v1/learning')
        },
        '/api/review': {
            target: env.VITE_API_LEARNING || 'http://localhost:8006',
            changeOrigin: true,
            rewrite: (path) => path.replace(/^\/api\/review/, '/v1/review')
        }
      }
    }
  }
})
