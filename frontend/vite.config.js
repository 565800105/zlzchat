import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Vite 配置：单页应用 + /api 代理到后端 FastAPI(8100)
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8100',
        changeOrigin: true,
      },
      // 文章封面等静态资源
      '/uploadGZHFile': {
        target: 'http://localhost:8100',
        changeOrigin: true,
      },
      // 公众号封面静态资源
      '/uploadGZHCover': {
        target: 'http://localhost:8100',
        changeOrigin: true,
      },
      // 订阅源分类图标静态资源
      '/uploadCategoryIcon': {
        target: 'http://localhost:8100',
        changeOrigin: true,
      },
    },
  },
})
