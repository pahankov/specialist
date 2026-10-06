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
        // Include BUILD_ID in filename to guarantee cache busting
        // even when content hash is identical across deploys
        entryFileNames: `assets/[name]-[hash]-${process.env.BUILD_ID || 'dev'}.js`,
        chunkFileNames: `assets/[name]-[hash]-${process.env.BUILD_ID || 'dev'}.js`,
        assetFileNames: `assets/[name]-[hash]-${process.env.BUILD_ID || 'dev'}.[ext]`,
      },
    },
  },
  define: {
    // Inject build ID into code so it survives minification
    __BUILD_ID__: JSON.stringify(process.env.BUILD_ID || 'dev'),
    // Force Vite to invalidate its transformation cache on every build
    __BUILD_TIMESTAMP__: JSON.stringify(Date.now()),
  },
})
