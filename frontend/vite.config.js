import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    headers: {
      'Cache-Control': 'no-store',
      Pragma: 'no-cache',
      Expires: '0',
    },
  },
})
