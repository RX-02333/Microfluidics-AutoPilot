import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { uiMessageApiPlugin } from '../../../system/components/base/agent/ui/vite-plugin-ui-api.js'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react(), uiMessageApiPlugin()],
    server: {
        port: 8501,
        host: '127.0.0.1',
        strictPort: true,
        cors: true,
        fs: {
            allow: ['..']
        },
        proxy: {
            // Agent Server (Chat & UI)
            '/api': {
                target: 'http://127.0.0.1:8001',
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/api/, '')
            },
            '/ui': {
                target: 'http://127.0.0.1:8001',
                changeOrigin: true
            },
            // Task API Server (Control & Status)
            '/control': {
                target: 'http://127.0.0.1:8002',
                changeOrigin: true
            },
            '/status': {
                target: 'http://127.0.0.1:8002',
                changeOrigin: true
            }
        }
    }
})
