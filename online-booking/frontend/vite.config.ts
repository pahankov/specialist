import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      // DaData goes through the backend proxy (server-side keys) in dev too,
      // exactly like prod (nginx -> backend). No secrets in the bundle, no
      // VITE_DADATA_TOKEN needed: direct calls always 401 without it.
      '/api/dadata': {
        target: 'http://localhost:8000',
        changeOrigin: true,
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
  },
})
