import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api/dadata': {
        target: 'https://suggestions.dadata.ru',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/dadata/, '/suggestions/api/v4/rich'),
      },
    },
  },
  build: {
    target: 'ES2020',
    outDir: 'dist',
  },
})