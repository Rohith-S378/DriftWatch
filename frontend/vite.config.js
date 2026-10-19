import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // bind all interfaces (IPv4 + IPv6) so localhost works in any browser
    port: 5173,
    strictPort: true, // fail loudly instead of silently switching ports
  },
})
