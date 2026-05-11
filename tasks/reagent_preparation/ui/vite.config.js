import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        port: 8501,
        host: '127.0.0.1',
        strictPort: true,
        cors: true,
        fs: {
            allow: ['..']
        },
        proxy: {
            // Agent Server (Chat)
            '/api': {
                target: 'http://127.0.0.1:8001',
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/api/, '')
            }
        }
    }
})
