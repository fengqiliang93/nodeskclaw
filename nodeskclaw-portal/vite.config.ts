import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

const apiTarget = process.env.API_PROXY_TARGET || 'http://localhost:8000'

const projectRoot = path.resolve(__dirname, '..')
const eePortalDir = path.resolve(projectRoot, 'ee/frontend/portal')
const hasEE = fs.existsSync(eePortalDir)

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      ...(hasEE
        ? { '@/router/ee-stub': path.resolve(eePortalDir, 'routes') }
        : {}),
    },
  },
  server: {
    port: 5174,
    fs: {
      allow: ['.', ...(hasEE ? [eePortalDir] : [])],
    },
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          three: ['three', 'troika-three-text'],
          d3: ['d3-zoom', 'd3-selection'],
        },
      },
    },
  },
})
