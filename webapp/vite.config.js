import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import pkg from './package.json' with { type: 'json' }

export default defineConfig({
  plugins: [vue()],
  // версия из package.json доступна в коде как __APP_VERSION__ (см.
  // src/services/version.js); в тестах она не определена — там гвард
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8088',
    },
  },
  test: {
    environment: 'happy-dom',
  },
})
