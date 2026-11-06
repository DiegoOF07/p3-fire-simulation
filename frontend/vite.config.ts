import { defineConfig } from 'vite'

const backend = 'http://127.0.0.1:8000'

export default defineConfig({
  server: {
    proxy: {
      '/api': backend,
      '/ws': { target: backend, ws: true },
    },
    // WSL doesn't get file events from /mnt/c.
    watch: process.env.VITE_POLL ? { usePolling: true, interval: 300 } : undefined,
  },
})
