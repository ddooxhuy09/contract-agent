import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Docker Desktop on Windows does not forward file-change events from bind-mounted
  // folders, so without polling the dev server keeps serving stale modules.
  server: { watch: { usePolling: true, interval: 300 } },
})
