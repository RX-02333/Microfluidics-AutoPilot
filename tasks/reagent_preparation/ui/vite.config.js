import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        port: 8501,
        host: '0.0.0.0',
        strictPort: true,
        cors: true,
        fs: {
            allow: ['..']
        },
        proxy: {
            // Agent Server (Chat)
            '/api': {
                target: 'http://192.168.31.176:8001',
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/api/, '')
            }
        }
    }
})
