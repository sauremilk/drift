import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Base path for GitHub Pages deployment under /drift/playground/
  base: '/drift/playground/',
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        // Separate Monaco into its own chunk — it's large and rarely changes
        manualChunks: {
          'monaco-editor': ['@monaco-editor/react'],
        },
      },
    },
  },
  // Pyodide uses SharedArrayBuffer — these headers are required locally.
  // GitHub Pages doesn't support custom headers; for production, Pyodide
  // falls back to running without SharedArrayBuffer for basic micropip usage.
  server: {
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
})
