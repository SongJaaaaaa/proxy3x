import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// proxy3x 前端构建/开发配置。
// dev 期通过 VITE_API_TARGET 决定 /api 代理到哪个后端（本地 32180 或线上）。
// 生产期由后端 http.server 托管 dist 并做 SPA fallback，前端同源调用 /api，无需代理。
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:32180'
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 52180,
      strictPort: true,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          // 让 HttpOnly 的 proxy3x_session cookie 在 dev 代理下也能落到 localhost
          cookieDomainRewrite: 'localhost',
        },
      },
    },
    build: {
      outDir: 'dist',
      // 后端 index.html 引用 /assets/*，保持默认 assets 目录
      assetsDir: 'assets',
    },
  }
})
