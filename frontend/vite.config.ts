/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const apiTarget = process.env.VITE_DEV_API_TARGET ?? 'http://127.0.0.1:5000'
// Nomes extra (além de localhost e IPs) aceites pelo `vite preview`, separados por vírgulas.
const previewAllowedHosts = process.env.VITE_PREVIEW_ALLOWED_HOSTS?.split(',')
  .map((host) => host.trim())
  .filter(Boolean)

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      // xfwd: a API recebe o IP real do cliente (rate limiting do login).
      '/api': { target: apiTarget, xfwd: true },
    },
  },
  preview: {
    allowedHosts: previewAllowedHosts,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
