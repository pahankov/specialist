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
        rewrite: (path) => path.replace(/^\/api\/dadata/, '/suggestions/api/4_1/rs/suggest/address'),
        headers: {
          'Origin': 'http://localhost:3000',
        },
      },
    },
  },
  build: {
    target: 'ES2020',
    outDir: 'dist',
    rollupOptions: {
      output: {
        // Force unique filename based on content hash
        entryFileNames: `assets/[name]-[hash].js`,
        chunkFileNames: `assets/[name]-[hash].js`,
      },
    },
  },
})
