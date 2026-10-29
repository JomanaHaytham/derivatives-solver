import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Two build modes:
//  - default: the UI talks to the FastAPI backend at /api (proxied in dev).
//  - "static": the Python math engine runs in the browser (Pyodide), so the
//    site is plain files that GitHub Pages can host. Assets come from static-public/.
export default defineConfig(({ mode }) => {
  const isStatic = mode === 'static'
  return {
    base: isStatic ? './' : '/',
    publicDir: isStatic ? 'static-public' : 'public',
    plugins: [react(), tailwindcss()],
    worker: { format: 'es' },
    build: { chunkSizeWarningLimit: 900 },
    server: {
      port: 5173,
      proxy: isStatic
        ? undefined
        : { '/api': { target: process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000', changeOrigin: true } },
    },
  }
})
